#!/usr/bin/env python3
"""Claude Code hook: 他リポジトリのセッションの知見を dotfiles の feedbacks-box へ送る側の骨格。

user スコープで全リポジトリに配線し、サブコマンド (session / stop / end) で
SessionStart / Stop / SessionEnd の処理へ分ける。現状は除外の判定と session の処理を持つ。

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


def handle_session(payload: dict[str, Any]) -> dict[str, Any] | None:
    root = active(payload)
    session_id = payload.get("session_id")
    if root is None or not (isinstance(session_id, str) and session_id):
        return None
    cwd = str(payload["cwd"])
    outbox = outbox_path(cwd, session_id)
    state_path = state_dir() / f"{_sanitize(session_id)}.json"
    # compact や resume でも SessionStart は再発火するので、既存の基準時刻は巻き戻さない
    if not state_path.exists():
        main_root = hook_git.main_checkout_root(cwd) or root
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


def main(argv: list[str]) -> int:
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict) or not argv or argv[0] not in SUBCOMMANDS:
            return 0
        # end の本体は後続のタスクで足す
        handlers = {"session": handle_session, "stop": handle_stop}
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
