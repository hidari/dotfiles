"""handoff-sentinel.py（Claude Code PostToolUse/Stop/SessionStart フック）の黒箱統合テスト。

フックを subprocess 起動し、stdin に hook JSON を、HANDOFF_* 環境変数にテスト用の
しきい値・state ディレクトリを与えて stdout (hook output JSON) と exit code を
exact 検証する。transcript は一時ファイルに JSONL で生成する（CLAUDE.md: モック回避）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / "home" / ".claude" / "hooks" / "handoff-sentinel.py"


def run_hook(
    action: str | None,
    hook_input: dict[str, object] | str | None,
    *,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """フックを subprocess 起動する。基底環境から HANDOFF_* を除去し extra_env のみ適用する。"""
    env = {k: v for k, v in os.environ.items() if not k.startswith("HANDOFF_")}
    if extra_env:
        env.update(extra_env)
    stdin = json.dumps(hook_input) if isinstance(hook_input, dict) else hook_input or ""
    argv = [sys.executable, str(HOOK)]
    if action is not None:
        argv.append(action)
    return subprocess.run(argv, input=stdin, capture_output=True, text=True, env=env, timeout=10)


class TestFailSafeSkeleton:
    """骨格の fail-safe: どんな不正入力でも無出力 + exit 0 で作業を止めない。"""

    def test_未知のactionは無出力でexit0(self) -> None:
        result = run_hook("unknown-action", {"session_id": "s1"})
        assert result.returncode == 0
        assert result.stdout == ""

    def test_action無しは無出力でexit0(self) -> None:
        result = run_hook(None, {"session_id": "s1"})
        assert result.returncode == 0
        assert result.stdout == ""

    def test_非JSONのstdinは無出力でexit0(self) -> None:
        result = run_hook("posttool", "this is not json")
        assert result.returncode == 0
        assert result.stdout == ""

    def test_空stdinは無出力でexit0(self) -> None:
        result = run_hook("posttool", None)
        assert result.returncode == 0
        assert result.stdout == ""
