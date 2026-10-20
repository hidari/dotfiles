#!/usr/bin/env python3
"""Claude Code hook: 他リポジトリのセッションの知見を dotfiles の feedbacks-box へ送る側。

user スコープで全リポジトリに配線し、サブコマンド (session / stop / end) で
SessionStart / Stop / SessionEnd の処理へ分ける。
SessionEnd (end) は持ち時間が短いので git を起動せず、状態ファイルの指すまとめを届けるだけ。

動かない場合: subagent (agent_id を持つ payload)、cwd が無いか実在しない、
cwd のリポジトリが受け箱 (main checkout の docs/.feedbacks-box/) を持つ、
skill (cross-repo-learnings) が入っていない。

箱の位置は絶対パスを設定へ書かず、この hook の実体の位置から導く。
hook として呼ばれる経路は fail-safe (無出力 + exit 0)。
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import hook_git

SKILL_NAME = "cross-repo-learnings"

# リポジトリルートから見たまとめの置き場
OUTBOX_RELATIVE = Path(".cache") / "feedbacks-outbox"

# 受け箱のリポジトリルートからの位置 (feedbacks-box.py の BOX_RELATIVE と同じ約束)
_BOX_RELATIVE = Path("docs") / ".feedbacks-box"

SUBCOMMANDS = ("session", "stop", "end")

# 1セッションで案内する回数の上限
MAX_NUDGES = 3

# 他のセッションのまとめを取り残しとして回収する最終更新からの経過秒。
# 同じリポジトリで並行して生きているセッションのまとめを、後から起動したセッションが奪わないため
RECOVER_AFTER_SECONDS = 86400

# 届けるまとめの大きさの上限 (バイト)。超えたものは読まず届けず消さない
MAX_SUMMARY_BYTES = 1_048_576

# コミットを作った reflog の件名。amend / checkout / reset / pull / rebase / fast-forward は含めない
_COMMIT_SUBJECTS = ("commit:", "commit (initial):", "commit (merge):")


def _sanitize(name: str) -> str:
    """ファイル名に使う識別子の区切り文字等を潰す (handoff-sentinel と同じ文字集合)。"""
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)


def dotfiles_box() -> Path:
    """dotfiles の受け箱。環境変数があればそれを、無ければ自分の実体から導いた位置を返す。

    hooks → .claude → home → dotfiles の順に辿る。実体を解決するので live の symlink 経由でも
    dotfiles のチェックアウトに着く。
    """
    override = os.environ.get("FEEDBACKS_BOX_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / _BOX_RELATIVE


def outbox_path(cwd: str, session_id: str) -> Path:
    return hook_git.repo_root(cwd) / OUTBOX_RELATIVE / f"{_sanitize(session_id)}.md"


def skill_installed() -> bool:
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return (Path(config_dir) / "skills" / SKILL_NAME / "SKILL.md").is_file()


def active(payload: dict[str, Any]) -> Path | None:
    """hook が動いてよいならリポジトリルートを、だめなら None を返す。"""
    if payload.get("agent_id"):
        return None
    cwd = payload.get("cwd")
    if not (isinstance(cwd, str) and os.path.isdir(cwd)):
        return None
    if not skill_installed():
        return None
    # 受け箱は ignore されて linked worktree には無いので、本体のチェックアウトで探す
    main_root = hook_git.main_checkout_root(cwd) or hook_git.repo_root(cwd)
    if (main_root / _BOX_RELATIVE).is_dir():
        return None
    return hook_git.repo_root(cwd)


def state_dir() -> Path:
    """セッションごとの状態ファイルの置き場。Stop と SessionEnd が同じ場所を読む。"""
    override = os.environ.get("FEEDBACKS_OUTBOX_STATE_DIR")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "claude" / "feedbacks-outbox"


def _write_state(path: Path, state: dict[str, Any]) -> None:
    """一時ファイルへ書いてから置き換え、書きかけを読ませない。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    try:
        tmp.write_text(json.dumps(state, ensure_ascii=False))
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def _read_state(path: Path) -> dict[str, Any] | None:
    """状態ファイルを読む。無い、読めない、形が違うときは None (状態が無いのと同じ扱い)。"""
    try:
        state = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(state, dict):
        return None
    since, nudges, outbox = state.get("since"), state.get("nudges"), state.get("outbox")
    # bool は int の部分型なので除く
    if any(isinstance(v, bool) or not isinstance(v, int) for v in (since, nudges)):
        return None
    if not isinstance(outbox, str):
        return None
    return state


def commits_since(repo_root: Path, since: int) -> list[int]:
    """HEAD の reflog のうち、since より後に作ったコミットの unix 秒。

    読めない (git の失敗、タイムアウト、コミットが無い) ときは空を返す。
    """
    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(repo_root),
                "log",
                "-g",
                "--date=unix",
                "--format=%gd%x09%gs",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            timeout=hook_git.RESOLVE_TIMEOUT,
            check=False,
            env=hook_git.isolated_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    times: list[int] = []
    for line in result.stdout.splitlines():
        selector, _, subject = line.partition("\t")
        match = re.fullmatch(r"HEAD@\{(\d+)\}", selector)
        if match and subject.startswith(_COMMIT_SUBJECTS) and int(match.group(1)) > since:
            times.append(int(match.group(1)))
    return times


def stop_notice(outbox: str) -> str:
    quoted = json.dumps(outbox, ensure_ascii=False)
    return (
        f"コミットを作りました。このセッションのまとめの置き場は {quoted} です。"
        "リポジトリを越えて効く知見が出ていれば、"
        f"{SKILL_NAME} skill に従ってそこを更新してください。"
        "知見が無ければ何もしないでください。"
    )


def notice(outbox: Path) -> str:
    # 外から来たパスは引用して載せる
    quoted = json.dumps(str(outbox), ensure_ascii=False)
    return (
        f"このセッションのまとめの置き場は {quoted} です。"
        "リポジトリを越えて効く知見が出たら、"
        f"{SKILL_NAME} skill に従ってそこを更新してください。"
        "ユーザーが dotfiles へ送ってと頼んだときも同じ場所へ書いてください。"
        "セッションの終わりに hook が dotfiles へ届けるので、箱へ直接は書かないでください。"
    )


def _deliverable(path: Path) -> bool:
    """symlink を辿らず、上限以下の大きさの通常のファイルであるか。

    リンク先の私的ファイルを箱へ複製しないため、FIFO などの read が戻らないファイルで
    hook を固めないため、大きなファイルを丸ごと読まないため。
    """
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode) and st.st_size <= MAX_SUMMARY_BYTES


def _in_plain_dirs(directory: Path) -> bool:
    """置き場とその親が symlink でないか。リポジトリの外を走査・読み出ししないための検査。"""
    return not (directory.is_symlink() or directory.parent.is_symlink())


def deliver(outbox: Path, box: Path, repo_name: str, today: str) -> Path | None:
    """まとめを箱へ届け、成功したら元を消して届け先を返す。届けなかったときは None。

    箱が無い、まとめが無い (上限以下の通常のファイル以外は無いものとして扱い、読まず消さない)、
    届け先に同名のファイルがある場合は元を残す。
    中身が空白だけのまとめは届ける価値が無いので、届けずに消す。
    名前は受け取る側の告知がシェルのコマンドへ引用して載せるので、識別子の文字だけにする。
    """
    if not (_deliverable(outbox) and box.is_dir()):
        return None
    body = outbox.read_bytes()
    if not body.strip():
        outbox.unlink(missing_ok=True)
        return None
    dest = box / f"from-{repo_name}-{today}-{_sanitize(outbox.stem[:8])}.md"
    if dest.exists():
        return None
    # 受け取る側が書きかけを読まないよう、箱の中の一時ファイルへ書いてから名前を付ける
    tmp = box / f".{dest.name}.{os.getpid()}.tmp"
    try:
        tmp.write_bytes(body)
        os.replace(tmp, dest)
    finally:
        tmp.unlink(missing_ok=True)
    outbox.unlink(missing_ok=True)
    return dest


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _tracked_names(directory: Path) -> set[bytes] | None:
    """directory の直下で git の追跡下にある名前。確かめられなければ None。

    名前の復号に失敗して例外で告知ごと落ちないよう、バイト列のまま比べる。
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(directory), "ls-files", "-z", "--", "."],
            capture_output=True,
            timeout=hook_git.RESOLVE_TIMEOUT,
            check=False,
            env=hook_git.isolated_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode != 0:
        return None
    return set(result.stdout.split(b"\0"))


def recover_stale(outbox: Path, box: Path, repo_name: str) -> None:
    """同じリポジトリの置き場にある、他のセッションの古いまとめを箱へ届ける。

    回収は持ち主の居ないファイルを動かすので、hook が作る形 (識別子の stem) のものだけを
    対象にし、追跡下のものは動かさない。追跡下を確かめられなければ回収しない。
    ドットで始まる名前は `_sanitize` で形が変わるので、形の検査で一緒に除かれる。
    """
    if not _in_plain_dirs(outbox.parent):
        return
    candidates = [
        path
        for path in sorted(outbox.parent.glob("*.md"))
        if path != outbox and _sanitize(path.stem) == path.stem
    ]
    if not candidates:
        return
    tracked = _tracked_names(outbox.parent)
    if tracked is None:
        return
    cutoff = time.time() - RECOVER_AFTER_SECONDS
    today = _today()
    for path in candidates:
        if os.fsencode(path.name) in tracked:
            continue
        try:
            if path.stat().st_mtime <= cutoff:
                deliver(path, box, repo_name, today)
        except OSError:
            # 1件の失敗で SessionStart の告知まで止めない。次の機会に回収する
            continue


def handle_session(payload: dict[str, Any]) -> dict[str, Any] | None:
    root = active(payload)
    session_id = payload.get("session_id")
    if root is None or not (isinstance(session_id, str) and session_id):
        return None
    cwd = str(payload["cwd"])
    outbox = outbox_path(cwd, session_id)
    state_path = state_dir() / f"{_sanitize(session_id)}.json"
    main_root = hook_git.main_checkout_root(cwd) or root
    recover_stale(outbox, dotfiles_box(), _sanitize(main_root.name))
    # compact や resume でも SessionStart は再発火するので、既存の基準時刻は巻き戻さない
    if not state_path.exists():
        _write_state(
            state_path,
            {
                "since": int(time.time()),
                "nudges": 0,
                "outbox": str(outbox),
                "repo": _sanitize(main_root.name),
            },
        )
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": notice(outbox),
        }
    }


def handle_stop(payload: dict[str, Any]) -> dict[str, Any] | None:
    root = active(payload)
    session_id = payload.get("session_id")
    if root is None or not (isinstance(session_id, str) and session_id):
        return None
    # 案内で続いた2回目の Stop。判定も状態の更新もしない
    if payload.get("stop_hook_active"):
        return None
    state_path = state_dir() / f"{_sanitize(session_id)}.json"
    state = _read_state(state_path)
    if state is None:
        # hook を入れる前から続いているセッション、または壊れた状態。その時点を基準にする
        cwd = str(payload["cwd"])
        main_root = hook_git.main_checkout_root(cwd) or root
        _write_state(
            state_path,
            {
                "since": int(time.time()),
                "nudges": 0,
                "outbox": str(outbox_path(cwd, session_id)),
                "repo": _sanitize(main_root.name),
            },
        )
        return None
    if state["nudges"] >= MAX_NUDGES:
        return None
    commits = commits_since(root, state["since"])
    if not commits:
        return None
    _write_state(state_path, {**state, "since": max(commits), "nudges": state["nudges"] + 1})
    return {
        "hookSpecificOutput": {
            "hookEventName": "Stop",
            "additionalContext": stop_notice(state["outbox"]),
        }
    }


def handle_end(payload: dict[str, Any]) -> None:
    """このセッションのまとめを箱へ届ける。

    SessionEnd の持ち時間は短いので git を起動せず、active も通さない。状態ファイルが無い
    (除外された、hook 導入前のセッション) ときは何もせず、次の SessionStart の回収に任せる。
    """
    session_id = payload.get("session_id")
    if payload.get("agent_id") or not (isinstance(session_id, str) and session_id):
        return None
    state = _read_state(state_dir() / f"{_sanitize(session_id)}.json")
    repo_name = state.get("repo") if state else None
    if state is None or not isinstance(repo_name, str):
        return None
    outbox = Path(state["outbox"])
    if not _in_plain_dirs(outbox.parent):
        return None
    deliver(outbox, dotfiles_box(), _sanitize(repo_name), _today())
    return None


def main(argv: list[str]) -> int:
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict) or not argv or argv[0] not in SUBCOMMANDS:
            return 0
        handlers = {"session": handle_session, "stop": handle_stop, "end": handle_end}
        handler = handlers.get(argv[0])
        output = handler(payload) if handler else None
        if output is not None:
            print(json.dumps(output, ensure_ascii=False))
    except Exception:
        # fail-safe: 送る側の故障で作業を止めない
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
