#!/usr/bin/env python3
"""Claude Code hook: セッション引き継ぎ検知器 (handoff-sentinel)。

第1引数で分岐する: posttool (コンテキスト使用率の監視) / stop (ツール呼び出し破損の
連続検知) / session (tmp/handoff.md の自動注入)。しきい値等の canonical はこのファイルの
定数であり、HANDOFF_* 環境変数で上書きできる。検知機構の故障で作業を止めないため、
全経路 fail-safe (無出力 + exit 0)。
仕様: docs/superpowers/specs/2026-07-03-session-handoff-design.md
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# canonical な既定値。他ファイル (SKILL.md / template.md) はこれらの値を再掲しない。
DEFAULT_CONTEXT_WINDOW_TOKENS = 200_000
DEFAULT_CONTEXT_THRESHOLD_PCT = 50
DEFAULT_BROKEN_STREAK = 5
DEFAULT_INJECT_MAX_BYTES = 32_768
DEFAULT_TAIL_BYTES = 1_048_576


def _env_int(name: str, default: int) -> int:
    """正の整数の環境変数を読む。未設定・不正・0 以下は default に落とす。"""
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


def _state_dir() -> Path:
    override = os.environ.get("HANDOFF_STATE_DIR", "")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "claude" / "handoff-sentinel"


def _notify_once(state_file: Path) -> bool:
    """state ファイルを新規作成できたら True (初回)。既存なら False (通知済み)。"""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(state_file, "x", encoding="utf-8") as fp:
            fp.write(datetime.now(UTC).isoformat() + "\n")
    except FileExistsError:
        return False
    return True


def _read_tail_entries(transcript_path: str) -> list[dict[str, Any]]:
    """transcript JSONL の末尾 (既定 DEFAULT_TAIL_BYTES) を読み、entry 一覧を返す。

    ツール実行ごとに走るため全量パースを避けてコストを一定に抑える。判定に必要なのは
    末尾近傍のみ (最後の usage / 破損 streak)。壊れた行と subagent の isSidechain な
    entry は捨てる。
    """
    tail_bytes = _env_int("HANDOFF_TAIL_BYTES", DEFAULT_TAIL_BYTES)
    size = os.path.getsize(transcript_path)
    with open(transcript_path, "rb") as fp:
        if size > tail_bytes:
            fp.seek(size - tail_bytes)
            fp.readline()  # seek で切れた部分行を捨てる
        data = fp.read()
    entries: list[dict[str, Any]] = []
    for line in data.decode("utf-8", errors="replace").splitlines():
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


def handle_posttool(payload: dict[str, Any]) -> dict[str, Any] | None:
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")
    if not (isinstance(session_id, str) and session_id):
        return None
    if not (isinstance(transcript_path, str) and os.path.isfile(transcript_path)):
        return None
    window = _env_int("HANDOFF_CONTEXT_WINDOW_TOKENS", DEFAULT_CONTEXT_WINDOW_TOKENS)
    threshold_pct = _env_int("HANDOFF_CONTEXT_THRESHOLD_PCT", DEFAULT_CONTEXT_THRESHOLD_PCT)
    tokens = _context_tokens(_read_tail_entries(transcript_path))
    if tokens * 100 < window * threshold_pct:
        return None
    if not _notify_once(_state_dir() / f"{session_id}.notified"):
        return None
    context = (
        f"コンテキスト使用率がしきい値を超えた (推定 {tokens} tokens)。"
        "session-handoff スキルを発動して引き継ぎを tmp/handoff.md に書き出し、"
        "ユーザーにセッション切替 (/clear または新セッション) を促すこと。"
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }


# 本文に漏れた tool-call 断片の目印 (破損イベントの判定に使う)
BROKEN_MARKERS = ("<invoke", "</invoke>", "<parameter", "antml")


def _classify(entry: dict[str, Any]) -> str:
    """entry を broken / reset / neutral に分類する。

    broken: 正常な tool_use を伴わない text への tool-call 断片の漏れ、
            または is_error な tool_result。
    reset: 正常に完了した tool_result (is_error が偽)。
    """
    message = entry.get("message")
    if not isinstance(message, dict):
        return "neutral"
    content = message.get("content")
    if not isinstance(content, list):
        return "neutral"
    if entry.get("type") == "assistant":
        has_tool_use = any(
            isinstance(block, dict) and block.get("type") == "tool_use" for block in content
        )
        if has_tool_use:
            # tool-call 記法を話題として扱う会話の誤検知ガード
            return "neutral"
        for block in content:
            if not (isinstance(block, dict) and block.get("type") == "text"):
                continue
            text = block.get("text")
            if isinstance(text, str) and any(marker in text for marker in BROKEN_MARKERS):
                return "broken"
        return "neutral"
    if entry.get("type") == "user":
        results = [
            block
            for block in content
            if isinstance(block, dict) and block.get("type") == "tool_result"
        ]
        if not results:
            return "neutral"
        if any(block.get("is_error") for block in results):
            return "broken"
        return "reset"
    return "neutral"


def _broken_streak(entries: list[dict[str, Any]]) -> int:
    """末尾から遡り、最新イベントで終わる破損イベントの連続数を数える。

    reset (正常完了の tool_result) のときのみ連続を打ち切る。neutral
    (通常の会話や tool_use のみのメッセージ) はカウントもリセットもせず
    素通りするため、間に neutral を挟んでいても broken は連続として数える
    (成功した tool_result が挟まらない限り連続とみなす、という仕様通りの挙動)。
    """
    streak = 0
    for entry in reversed(entries):
        kind = _classify(entry)
        if kind == "broken":
            streak += 1
        elif kind == "reset":
            break
    return streak


def handle_stop(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("stop_hook_active"):
        # block 由来の再入では判定しない (無限 block ループ防止の一段目)
        return None
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")
    if not (isinstance(session_id, str) and session_id):
        return None
    if not (isinstance(transcript_path, str) and os.path.isfile(transcript_path)):
        return None
    streak_limit = _env_int("HANDOFF_BROKEN_STREAK", DEFAULT_BROKEN_STREAK)
    if _broken_streak(_read_tail_entries(transcript_path)) < streak_limit:
        return None
    if not _notify_once(_state_dir() / f"{session_id}.blocked"):
        # 1 セッション 1 回 (無限 block ループ防止の二段目)
        return None
    reason = (
        "ツール呼び出しの破損が連続して検知された。停止する前に session-handoff スキルを"
        "発動して引き継ぎを tmp/handoff.md に書き出し、ユーザーに Claude Code の再起動を"
        "促してから停止すること。"
    )
    return {"decision": "block", "reason": reason}


def _repo_root(cwd: str) -> Path:
    """cwd の git リポルートを返す。リポ外・git 不在は cwd に落とす。"""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return Path(cwd)
    top = result.stdout.strip()
    return Path(top) if result.returncode == 0 and top else Path(cwd)


def handle_session(payload: dict[str, Any]) -> dict[str, Any] | None:
    cwd = payload.get("cwd")
    if not (isinstance(cwd, str) and os.path.isdir(cwd)):
        return None
    handoff = _repo_root(cwd) / "tmp" / "handoff.md"
    if not handoff.is_file():
        return None
    max_bytes = _env_int("HANDOFF_INJECT_MAX_BYTES", DEFAULT_INJECT_MAX_BYTES)
    raw = handoff.read_bytes()
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
    context = f"前セッションからの引き継ぎ (tmp/{consumed.name} として保存済み):\n\n{text}"
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
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
