#!/usr/bin/env python3
"""Claude Code hook: セッション引き継ぎ検知器 (handoff-sentinel)。

第1引数で分岐する: posttool (コンテキスト使用率とレートリミットの監視) / stop (ツール呼び出し
破損の通算検知) / session (.cache/handoff.md の自動注入) / record (skill からの provenance 記録)。
しきい値等の canonical はこのファイルの定数であり、HANDOFF_* 環境変数で上書きできる。
検知機構の故障で作業を止めないため、全経路 fail-safe (無出力 + exit 0)。
仕様: docs/superpowers/archive/2026-07-03-session-handoff-design.md
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypeGuard

# canonical な既定値。他ファイル (SKILL.md / template.md) はこれらの値を再掲しない。
DEFAULT_CONTEXT_WINDOW_TOKENS = 1_000_000
DEFAULT_CONTEXT_THRESHOLD_PCT = 50
DEFAULT_BROKEN_COUNT = 5
DEFAULT_INJECT_MAX_BYTES = 32_768
DEFAULT_TAIL_BYTES = 1_048_576
DEFAULT_RATELIMIT_WARN_PCT = 90
DEFAULT_RATELIMIT_URGENT_PCT = 95

# 「消費したが読まれていないかもしれない」記録の拡張子。書く側 (_mark_unread) と消す側
# (_clear_unread) がファイル名を離れた場所で組み立てるので、綴りをここに 1 つだけ置く。
# session_id 起点の state (.notified / .blocked / .ratelimit) とは接尾辞が交わらないため、
# repo_id と session_id がたまたま同じ文字列でも同じファイルを指さない。
_UNREAD_SUFFIX = "unread"

# 窓名の表示ラベル。サーバは窓を追加しうるので監視対象は名指しで持たず、読み手に伝わらない
# 名前だけをここで訳す。未知の窓は名前をそのまま出す。
_WINDOW_LABELS = {
    "five_hour": "5 時間",
    "seven_day": "週次",
}

# 本文に漏れた tool-call の開始署名 (破損イベントの判定に使う)。
# 実漏洩は崩れたトークンに続いて桁0の行頭に tool-call ブロックが現れる構造なので、
# `<invoke name=` / `<parameter name=` (antml: 付き含む) が桁0の行頭に来る場合のみ数える。
# これで 'antml'/'<invoke>' 単体の言及、name= 付き署名のインライン引用、字下げした例示は数えない。
# ただし桁0の独立行やコードフェンス内に marker を書いた散文は依然数えうる (漏洩ブロックと文字列上
# 完全同型で弁別不能)。has_tool_use ガード (_is_broken) と併せ現実的な自己誤検知を減らす狙い。
BROKEN_TOOL_CALL_RE = re.compile(r"(?:^|\n)<(?:antml:)?(?:invoke|parameter)\s+name=")


def _sanitize(name: str) -> str:
    """state ファイル名に使う識別子から区切り文字等を潰し、_state_dir 外への書き込みを防ぐ。

    session_id は Claude Code 内部フィールドで攻撃者非制御だが、path separator や `..` を
    含む値が来ても _state_dir 内に閉じ込める多層防御。canonical な charset はこの1箇所のみ。
    """
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)


def _env_int(name: str, default: int) -> int:
    """正の整数の環境変数を読む。未設定・不正・0 以下は default に落とす。"""
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


def _cache_root() -> Path:
    """このフックが使うキャッシュの根。statusline-command.sh の CACHE_DIR と同じ規則。

    規則を 1 つに閉じないと、XDG_CACHE_HOME を設定したマシンで state とレートリミットの
    キャッシュが別の根へ落ち、statusline とも片方だけ食い違う。
    """
    cache_home = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache_home) / "claude"


def _state_dir() -> Path:
    override = os.environ.get("HANDOFF_STATE_DIR", "")
    if override:
        return Path(override)
    return _cache_root() / "handoff-sentinel"


def _notify_once(state_file: Path) -> bool:
    """state ファイルを新規作成できたら True (初回)。既存なら False (通知済み)。"""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(state_file, "x", encoding="utf-8") as fp:
            fp.write(datetime.now(UTC).isoformat() + "\n")
    except FileExistsError:
        return False
    return True


def _session_state_file(session_id: str, suffix: str) -> Path:
    """session_id 起点の state ファイルパスを作る唯一の経路。必ず _sanitize を通す。

    .notified / .blocked を両方これ経由にすることで、traversal ガード (_sanitize) の適用を
    call site の記憶に依存させず構造的に強制する (_provenance_path と対称)。
    """
    return _state_dir() / f"{_sanitize(session_id)}.{suffix}"


def _session_and_transcript(payload: dict[str, Any]) -> tuple[str, str] | None:
    """payload から session_id と実在する transcript_path を検証付きで取り出す。

    posttool / stop 共通の入力ガード。どちらか欠ければ None を返し呼び出し側は no-op。
    """
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")
    if not (isinstance(session_id, str) and session_id):
        return None
    if not (isinstance(transcript_path, str) and os.path.isfile(transcript_path)):
        return None
    return session_id, transcript_path


def _read_tail_entries(transcript_path: str) -> list[dict[str, Any]]:
    """transcript JSONL の末尾 (既定 DEFAULT_TAIL_BYTES) を読み、entry 一覧を返す。

    ツール実行ごとに走るため全量パースを避けてコストを一定に抑える。判定に必要なのは
    末尾近傍のみ (最後の usage / 破損の通算)。壊れた行と subagent の isSidechain な
    entry は捨てる。行分割は JSONL の区切り (\\n) のみで行う (str.splitlines は U+2028 等の
    Unicode 行境界でも割ってしまい、それらを含む正当な JSON 行を取りこぼすため使わない)。
    """
    tail_bytes = _env_int("HANDOFF_TAIL_BYTES", DEFAULT_TAIL_BYTES)
    size = os.path.getsize(transcript_path)
    with open(transcript_path, "rb") as fp:
        if size > tail_bytes:
            fp.seek(size - tail_bytes)
            fp.readline()  # seek で切れた部分行を捨てる
        data = fp.read()
    entries: list[dict[str, Any]] = []
    for line in data.decode("utf-8", errors="replace").split("\n"):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict) and not entry.get("isSidechain"):
            entries.append(entry)
    return entries


def _context_tokens(entries: list[dict[str, Any]]) -> int:
    """最後の assistant メッセージの usage からコンテキスト占有量 (tokens) を推定する。"""
    for entry in reversed(entries):
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue
        total = 0
        for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            value = usage.get(key)
            if isinstance(value, int):
                total += value
        return total
    return 0


def _account_tag(config_dir: str) -> str:
    """設定ディレクトリを識別する短いタグ。statusline-command.sh の account_tag と同一の導出。

    アカウントごとにキャッシュを分けるためだけに使う。分けないと 2 アカウントが同じファイルを
    潰し合い、片方のレートリミットでもう片方が発火する。
    """
    if config_dir == str(Path.home() / ".claude"):
        return "default"
    return _hash_bytes(config_dir.encode("utf-8"))[:8]


def _rate_limits_path() -> Path:
    """statusline が書くレートリミットのキャッシュ。hook はここを読むしかない。

    Claude Code がレートリミットを渡すのは statusLine の stdin だけで、hook の入力にも
    transcript にも値が無い (実測)。したがって供給は statusline 経由に限られる。
    """
    override = os.environ.get("HANDOFF_RATE_LIMITS_FILE", "")
    if override:
        return Path(override)
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return _cache_root() / f"rate-limits-{_account_tag(config_dir)}.json"


def _read_json_dict(path: Path) -> dict[str, Any]:
    """JSON オブジェクトとして読む。不在・壊れ・型違いはすべて空として返す。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _is_number(value: Any) -> TypeGuard[float]:
    """真偽値を除いた数値かどうか。bool は int の派生なので明示的に外す。"""
    return isinstance(value, int | float) and not isinstance(value, bool)


def _ratelimit_notices(session_id: str) -> list[str]:
    """逼迫した窓ごとに通知を作る。窓と段の組ごとに 1 回だけ鳴る。

    再武装の契機は窓のリセットで、state には発火時の resets_at を記録する。次に読んだ
    resets_at が違えば別の窓なので鳴り直す。コンテキストしきい値のように「いつ再武装するか」を
    決める必要が無いのは、レートリミットが窓を持つおかげである。
    """
    windows = _read_json_dict(_rate_limits_path())
    if not windows:
        return []
    warn_pct = _env_int("HANDOFF_RATELIMIT_WARN_PCT", DEFAULT_RATELIMIT_WARN_PCT)
    urgent_pct = _env_int("HANDOFF_RATELIMIT_URGENT_PCT", DEFAULT_RATELIMIT_URGENT_PCT)
    now = datetime.now(UTC).timestamp()
    state_path = _session_state_file(session_id, "ratelimit")
    fired = _read_json_dict(state_path)
    notices: list[str] = []
    for name in sorted(windows):
        info = windows[name]
        if not isinstance(info, dict):
            continue
        pct = info.get("used_percentage")
        resets_at = info.get("resets_at")
        # 欠落を 0% と読むと、値が無いときに必ず「余裕あり」へ倒れる。判定不能として飛ばす
        if not _is_number(pct):
            continue
        # 失効した窓は見ない。本体は落として渡すが、キャッシュが古いときはここで落とす。
        # 落とさないとリセットで圧が下がった瞬間に撃つ
        if not (_is_number(resets_at) and resets_at > now):
            continue
        if pct >= urgent_pct:
            threshold, urgent = urgent_pct, True
        elif pct >= warn_pct:
            threshold, urgent = warn_pct, False
        else:
            continue
        key = f"{name}:{threshold}"
        if fired.get(key) == resets_at:
            continue
        fired[key] = resets_at
        notices.append(_ratelimit_message(name, pct, threshold, urgent=urgent))
    if notices:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(fired), encoding="utf-8")
    return notices


def _ratelimit_message(name: str, pct: float, threshold: int, *, urgent: bool) -> str:
    """段の違いは求める行動に出す。しきい値との大小関係はどちらの段でも同じなので書き分けない。"""
    action = (
        "他の作業を中断し、直ちに session-handoff スキルを発動して引き継ぎを "
        ".cache/handoff.md へ書き出し、記憶すべきことをメモリへ保存すること。"
        if urgent
        else "区切りの良いところで session-handoff スキルを発動し、引き継ぎを "
        ".cache/handoff.md に書き出すこと。"
    )
    label = _WINDOW_LABELS.get(name, name)
    return f"{label}のレートリミットが {threshold}% を超えた (現在 {pct:g}%)。{action}"


def _context_notices(session_id: str, transcript_path: str) -> list[str]:
    # 通知は 1 セッション 1 回なので、鳴った後は transcript を読む意味が無い。
    # posttool はツール呼び出しのたびに走るため、この stat 1 回が末尾 1MB の読み込みを丸ごと省く
    notified = _session_state_file(session_id, "notified")
    if notified.exists():
        return []
    window = _env_int("HANDOFF_CONTEXT_WINDOW_TOKENS", DEFAULT_CONTEXT_WINDOW_TOKENS)
    threshold_pct = _env_int("HANDOFF_CONTEXT_THRESHOLD_PCT", DEFAULT_CONTEXT_THRESHOLD_PCT)
    tokens = _context_tokens(_read_tail_entries(transcript_path))
    if tokens * 100 < window * threshold_pct:
        return []
    if not _notify_once(notified):
        return []
    return [
        f"コンテキスト使用率がしきい値を超えた (推定 {tokens} tokens)。"
        "session-handoff スキルを発動して引き継ぎを .cache/handoff.md に書き出し、"
        "ユーザーにセッション切替 (/clear または新セッション) を促すこと。"
    ]


def _clear_unread(session_id: str) -> None:
    """自分が消費した引き継ぎを読んだ証跡として、未読の記録を消す (対は _mark_unread)。

    記録は repo 単位のファイル名なので、本来なら cwd から repo_id を導いて直接開きたい。
    しかしその導出は git の起動を伴い (_repo_root の docstring 参照)、この関数はツール
    呼び出しごとに走る。代わりに state ディレクトリ側を舐めて session_id で照合する。
    他セッションの記録を消さないことは、この照合だけが担保している。
    """
    try:
        candidates = list(_state_dir().glob(f"*.{_UNREAD_SUFFIX}"))
    except OSError:
        return
    for path in candidates:
        if _read_json_dict(path).get("session_id") == session_id:
            path.unlink(missing_ok=True)


def handle_posttool(payload: dict[str, Any]) -> dict[str, Any] | None:
    """コンテキストとレートリミットを両方見る。片方で早期 return すると他方が飛ぶ。"""
    # 未読の消去は _session_and_transcript より前に独立して置く。同関数は transcript が
    # 欠けただけで早期 return するので、後ろに置くとその条件のセッションが永久に未読扱いになる
    own_session = payload.get("session_id")
    if isinstance(own_session, str) and own_session:
        _clear_unread(own_session)
    pair = _session_and_transcript(payload)
    if pair is None:
        return None
    session_id, transcript_path = pair
    notices = _context_notices(session_id, transcript_path) + _ratelimit_notices(session_id)
    if not notices:
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(notices),
        }
    }


def _is_broken(entry: dict[str, Any]) -> bool:
    """entry が破損イベント (assistant text に漏れた tool-call の開始署名) かを判定する。

    正常な tool_use を伴わない assistant の text に tool-call の開始署名が桁0で現れたものだけを
    破損とみなす。tool_result の is_error は数えない: コマンドの非ゼロ終了・権限 deny・想定内の
    失敗など良性エラーが大半で、ツール呼び出し破損の指標にならず健全な探索セッションを誤検知する。
    tool_use のみのメッセージ・通常会話・tool_result は破損ではない。
    """
    if entry.get("type") != "assistant":
        return False
    message = entry.get("message")
    if not isinstance(message, dict):
        return False
    content = message.get("content")
    if not isinstance(content, list):
        return False
    has_tool_use = any(
        isinstance(block, dict) and block.get("type") == "tool_use" for block in content
    )
    if has_tool_use:
        # tool-call 記法を話題として扱う会話の誤検知ガード
        return False
    for block in content:
        if not (isinstance(block, dict) and block.get("type") == "text"):
            continue
        text = block.get("text")
        if isinstance(text, str) and BROKEN_TOOL_CALL_RE.search(text):
            return True
    return False


def _broken_count(entries: list[dict[str, Any]]) -> int:
    """tail ウィンドウ内の破損イベントの通算数を数える。

    連続 (streak) ではなく累積。破損の間に成功実行や通常会話が挟まってもリセットしない。
    実セッションの劣化はモデルが「壊れる→出し直して成功→また壊れる」を繰り返すため、
    連続判定では成功のたびにリセットされ、破損が多数あるセッションでも一度も発火しなかった。
    通算なら劣化を取りこぼさない。tail ウィンドウ (DEFAULT_TAIL_BYTES) が古い破損を自然に
    スクロールアウトさせるため、完全復調した長寿命セッションで古い破損まで数え続けることはない。
    """
    return sum(1 for entry in entries if _is_broken(entry))


def handle_stop(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("stop_hook_active"):
        # block 由来の再入では判定しない (無限 block ループ防止の一段目)
        return None
    pair = _session_and_transcript(payload)
    if pair is None:
        return None
    session_id, transcript_path = pair
    count_limit = _env_int("HANDOFF_BROKEN_COUNT", DEFAULT_BROKEN_COUNT)
    if _broken_count(_read_tail_entries(transcript_path)) < count_limit:
        return None
    if not _notify_once(_session_state_file(session_id, "blocked")):
        # 1 セッション 1 回 (無限 block ループ防止の二段目)
        return None
    reason = (
        "ツール呼び出しの破損が通算で規定回数に達した。停止する前に session-handoff スキルを"
        "発動して引き継ぎを .cache/handoff.md に書き出し、ユーザーに Claude Code の再起動を"
        "促してから停止すること。"
    )
    return {"decision": "block", "reason": reason}


# git の repo / worktree / index の位置を上書きする環境変数。git hook 経由の実行では git が
# これらを子へ渡すため、継承すると `git -C <cwd>` の repo 探索が hook 側の repo に上書きされる。
# repo の指定を -C に一本化するため、これらを除いた環境で git を起動する。
_GIT_LOCATION_VARS = frozenset(
    {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_COMMON_DIR",
        "GIT_PREFIX",
        "GIT_NAMESPACE",
    }
)


def _isolated_git_env() -> dict[str, str]:
    """ロケーション系 GIT_* を除いた環境変数を返す。"""
    return {k: v for k, v in os.environ.items() if k not in _GIT_LOCATION_VARS}


def _repo_root(cwd: str) -> Path:
    """cwd の git リポルートを返す。リポ外・git 不在は cwd に落とす。

    subprocess をここで import するのは、この関数へ来るのが record / session の 2 経路だけで、
    ツール呼び出しごとに走る posttool と stop は一度も通らないため。トップレベルへ置くと
    全経路が起動のたびにインタプリタの import コストを払う。
    """
    import subprocess

    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            env=_isolated_git_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return Path(cwd)
    top = result.stdout.strip()
    return Path(top) if result.returncode == 0 and top else Path(cwd)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _repo_id(repo_root: Path) -> str:
    """リポルートのパスから安定した識別子を作る (provenance state のキー)。"""
    return _hash_bytes(str(repo_root).encode("utf-8"))[:16]


def _handoff_path(repo_root: Path) -> Path:
    """引き継ぎ書のパス。record と session が同一パスを共有するための単一の真実。"""
    return repo_root / ".cache" / "handoff.md"


def _provenance_path(repo_root: Path) -> Path:
    """このリポの handoff provenance (内容ハッシュ) を置く user スコープの state ファイル。"""
    return _state_dir() / f"{_repo_id(repo_root)}.provenance"


def _read_provenance(prov: Path) -> str | None:
    try:
        return prov.read_text(encoding="utf-8").strip() or None
    except OSError:
        return None


def _unread_path(repo_root: Path) -> Path:
    """消費したが読まれていないかもしれない引き継ぎの記録 (対は _clear_unread)。

    provenance と同じく repo 単位で置く。session 単位にすると、次のセッションは前の
    セッションの id を知らないので自分宛でない記録を見つけられない。
    """
    return _state_dir() / f"{_repo_id(repo_root)}.{_UNREAD_SUFFIX}"


def _mark_unread(repo_root: Path, session_id: str, consumed_name: str) -> None:
    """消費を記録する。消費したセッションがツールを 1 度でも使えば _clear_unread が消す。"""
    path = _unread_path(repo_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"session_id": session_id, "consumed": consumed_name}), encoding="utf-8"
    )


def _unread_notice(repo_root: Path, session_id: str) -> list[str]:
    """前のセッションが消費したまま読まなかった引き継ぎがあれば告げ、記録を消す。

    自動で復帰はさせない。provenance を消した後の内容を何を根拠に信用するかという問いに
    なり、決定待ちの prompt injection の議論へ巻き込まれるため、判断は読み手へ渡す。

    自分自身の記録は告げない。compact や resume で同じ session_id の SessionStart が
    再発火したとき、まだ読んでいる最中の引き継ぎを「失われた」と誤報しないため。
    """
    path = _unread_path(repo_root)
    if not path.is_file():
        return []
    record = _read_json_dict(path)
    if record.get("session_id") == session_id:
        return []
    consumed = record.get("consumed")
    path.unlink(missing_ok=True)  # 壊れて読めない記録もここで片付ける (毎回の再読を防ぐ)
    if not (isinstance(consumed, str) and consumed):
        return []
    return [
        f"前のセッションが消費した引き継ぎ (.cache/{consumed}) は、読まれないまま終わった"
        "可能性がある。必要なら内容を確認すること。"
    ]


def _created_at(handoff: Path) -> str:
    """引き継ぎ書そのものが書かれた時刻 (mtime) を UTC の絶対時刻で返す。

    消費の瞬間に打つファイル名の stamp しか出ないと、1 か月前の引き継ぎが今日の日付を
    添えて「前セッションからの」として届き、新しく見える方向へバイアスがかかる。
    経過日数は添えない。腐りは「書いた後にリポジトリが動いたか」で測るもので経過日数では
    測れず、日数を出すとそれが判断の指標に見えてしまう。判断は読み手へ渡す。
    """
    return datetime.fromtimestamp(handoff.stat().st_mtime, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def handle_record(cwd: str) -> None:
    """session-handoff skill が書き出した handoff.md の provenance (内容ハッシュ) を記録する。

    SessionStart はこの記録に一致する handoff.md のみ注入する。リポにコミットされた第三者作成の
    handoff.md を信頼された引き継ぎとして注入しない (prompt injection 防御) ための user スコープの
    provenance。skill が書き出し直後に `handoff-sentinel.py record` として呼ぶ。
    """
    repo_root = _repo_root(cwd)
    handoff = _handoff_path(repo_root)
    if not handoff.is_file():
        return
    prov = _provenance_path(repo_root)
    prov.parent.mkdir(parents=True, exist_ok=True)
    prov.write_text(_hash_bytes(handoff.read_bytes()) + "\n", encoding="utf-8")


def _inject_handoff(repo_root: Path, session_id: str) -> str | None:
    """provenance を通った .cache/handoff.md を消費し、注入する文面を返す。"""
    handoff = _handoff_path(repo_root)
    if not handoff.is_file():
        return None
    raw = handoff.read_bytes()
    prov = _provenance_path(repo_root)
    if _read_provenance(prov) != _hash_bytes(raw):
        # skill が record した内容と一致しない handoff は信頼しない (prompt injection 防御)。
        # 未記録・改竄・第三者作成はすべてここで弾く (fail-closed)
        return None
    # リネームより前に読む。mtime はリネームを跨いでも保たれるが、リネームが失敗したときに
    # consumed 側は存在しないので、読む対象を消費前のパスに固定しておく
    created = _created_at(handoff)
    max_bytes = _env_int("HANDOFF_INJECT_MAX_BYTES", DEFAULT_INJECT_MAX_BYTES)
    text = raw[:max_bytes].decode("utf-8", errors="ignore")
    if len(raw) > max_bytes:
        text += "\n\n(引き継ぎ書が大きいため先頭のみ注入した。全文は consumed リネーム先を読むこと)"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    consumed = handoff.with_name(f"handoff-consumed-{stamp}.md")
    try:
        handoff.rename(consumed)
    except OSError:
        # リネームに失敗したら注入もしない (毎セッション再注入される重複より欠落を選ぶ)
        return None
    prov.unlink(missing_ok=True)  # 消費した provenance を片付ける (二重注入防止)
    _mark_unread(repo_root, session_id, consumed.name)
    return (
        f"前セッションからの引き継ぎ ({created} に作成、"
        f".cache/{consumed.name} として保存済み):\n\n{text}"
    )


def handle_session(payload: dict[str, Any]) -> dict[str, Any] | None:
    """未読の告知と引き継ぎの注入を集めて返す。

    どちらか一方で早期 return しないこと。handoff の有無で先に返すと、消費だけされて
    読まれなかった記録が誰にも告げられないまま次の消費に上書きされる。
    """
    cwd = payload.get("cwd")
    if not (isinstance(cwd, str) and os.path.isdir(cwd)):
        return None
    raw_session = payload.get("session_id")
    session_id = raw_session if isinstance(raw_session, str) else ""
    repo_root = _repo_root(cwd)
    parts = _unread_notice(repo_root, session_id)
    injected = _inject_handoff(repo_root, session_id)
    if injected is not None:
        parts.append(injected)
    if not parts:
        return None
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n\n".join(parts),
        }
    }


HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any] | None]] = {
    "posttool": handle_posttool,
    "stop": handle_stop,
    "session": handle_session,
}


def main() -> int:
    try:
        action = sys.argv[1] if len(sys.argv) > 1 else ""
        if action == "record":
            # skill から呼ばれる副作用コマンド (hook JSON は受けず cwd から解決する)
            handle_record(os.getcwd())
            return 0
        handler = HANDLERS.get(action)
        if handler is None:
            return 0
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict) or payload.get("agent_id"):
            # subagent では動かない (spec: 共通ガード)
            return 0
        output = handler(payload)
        if output is not None:
            print(json.dumps(output, ensure_ascii=False))
    except Exception:
        # fail-safe: 検知器の故障で作業を止めない
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
