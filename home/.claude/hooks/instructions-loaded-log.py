#!/usr/bin/env python3
"""Claude Code hook: 指示ファイルのロードを観測して JSONL へ記録する。

InstructionsLoaded イベント (Claude Code 2.1.233 で確認) を受け取り、どの指示ファイルが
いつ何故ロードされたかを追記する。イベントの schema はバイナリの zod 定義が canonical で、
このファイルは値を再掲せず受け取ったフィールドをそのまま通す。

このフックは observability-only で blocking をサポートしないため、常に exit 0 で返す。
観測器の故障で作業を止めない。
"""

from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path


def _log_path() -> Path:
    override = os.environ.get("INSTRUCTIONS_LOADED_LOG", "")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "claude" / "instructions-loaded.jsonl"


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            return 0
        record: dict[str, object] = {"observed_at": datetime.now(UTC).isoformat()}
        # イベント固有フィールドと、どのセッション由来かを残す共通フィールドのみ拾う。
        # 未知のフィールドが増えた場合に取りこぼさないよう payload 全体も畳んで持つ。
        for key in (
            "session_id",
            "cwd",
            "hook_event_name",
            "file_path",
            "memory_type",
            "load_reason",
            "globs",
            "trigger_file_path",
            "parent_file_path",
        ):
            if key in payload:
                record[key] = payload[key]
        unknown = sorted(set(payload) - set(record) - {"transcript_path", "prompt_id"})
        if unknown:
            record["_unknown_fields"] = {k: payload[k] for k in unknown}
        path = _log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fp:
            fp.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        # fail-safe: 観測器の故障で作業を止めない
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
