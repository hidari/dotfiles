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
import sys
from collections.abc import Callable
from typing import Any

# canonical な既定値。他ファイル (SKILL.md / template.md) はこれらの値を再掲しない。
DEFAULT_CONTEXT_WINDOW_TOKENS = 200_000
DEFAULT_CONTEXT_THRESHOLD_PCT = 50
DEFAULT_BROKEN_STREAK = 5
DEFAULT_INJECT_MAX_BYTES = 32_768
DEFAULT_TAIL_BYTES = 1_048_576

# handler は後続タスクで追加する
HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any] | None]] = {}


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
