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


def assistant_usage(tokens: int, *, sidechain: bool = False) -> dict[str, object]:
    """usage 合算が tokens になる assistant entry を作る (input に全量を寄せる)。"""
    entry: dict[str, object] = {
        "type": "assistant",
        "message": {
            "usage": {
                "input_tokens": tokens,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
            "content": [],
        },
    }
    if sidechain:
        entry["isSidechain"] = True
    return entry


def write_transcript(path: Path, entries: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def base_env(tmp_path: Path) -> dict[str, str]:
    """テスト用の小さいしきい値: window=1000 tokens, 50% (= 500 tokens で発火)。"""
    return {
        "HANDOFF_STATE_DIR": str(tmp_path / "state"),
        "HANDOFF_CONTEXT_WINDOW_TOKENS": "1000",
        "HANDOFF_CONTEXT_THRESHOLD_PCT": "50",
        "HANDOFF_BROKEN_STREAK": "5",
    }


def posttool_input(tmp_path: Path, transcript: Path) -> dict[str, object]:
    return {
        "session_id": "sess-1",
        "transcript_path": str(transcript),
        "cwd": str(tmp_path),
        "hook_event_name": "PostToolUse",
    }


class TestPostToolContextWatch:
    """posttool: 最後の assistant usage 合算がしきい値以上のとき、1 回だけ通知する。"""

    def test_しきい値直下では発火しない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, [assistant_usage(499)])
        result = run_hook(
            "posttool", posttool_input(tmp_path, transcript), extra_env=base_env(tmp_path)
        )
        assert result.returncode == 0
        assert result.stdout == ""

    def test_しきい値ちょうどで発火しskill名を含む(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, [assistant_usage(500)])
        result = run_hook(
            "posttool", posttool_input(tmp_path, transcript), extra_env=base_env(tmp_path)
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert "session-handoff" in output["hookSpecificOutput"]["additionalContext"]
        assert (tmp_path / "state" / "sess-1.notified").is_file()

    def test_usage3フィールドは合算される(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        entry = assistant_usage(0)
        message = entry["message"]
        assert isinstance(message, dict)
        message["usage"] = {
            "input_tokens": 100,
            "cache_read_input_tokens": 300,
            "cache_creation_input_tokens": 100,
        }
        write_transcript(transcript, [entry])
        result = run_hook(
            "posttool", posttool_input(tmp_path, transcript), extra_env=base_env(tmp_path)
        )
        assert result.stdout != ""  # 100+300+100=500 >= 500 で発火

    def test_通知済みセッションでは再発火しない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, [assistant_usage(999)])
        env = base_env(tmp_path)
        first = run_hook("posttool", posttool_input(tmp_path, transcript), extra_env=env)
        second = run_hook("posttool", posttool_input(tmp_path, transcript), extra_env=env)
        assert first.stdout != ""
        assert second.returncode == 0
        assert second.stdout == ""

    def test_sidechainのassistantは無視される(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(
            transcript,
            [assistant_usage(200), assistant_usage(9999, sidechain=True)],
        )
        result = run_hook(
            "posttool", posttool_input(tmp_path, transcript), extra_env=base_env(tmp_path)
        )
        assert result.stdout == ""  # 本編の 200 tokens のみで判定される

    def test_agent_id付きのsubagentでは発火しない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, [assistant_usage(999)])
        hook_input = posttool_input(tmp_path, transcript)
        hook_input["agent_id"] = "agent-x"
        result = run_hook("posttool", hook_input, extra_env=base_env(tmp_path))
        assert result.returncode == 0
        assert result.stdout == ""

    def test_transcript不在は無出力でexit0(self, tmp_path: Path) -> None:
        hook_input = posttool_input(tmp_path, tmp_path / "missing.jsonl")
        result = run_hook("posttool", hook_input, extra_env=base_env(tmp_path))
        assert result.returncode == 0
        assert result.stdout == ""

    def test_壊れたJSONL行は無視して判定する(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        valid = json.dumps(assistant_usage(999))
        transcript.write_text(f"{{broken json\n{valid}\n[1,2]\n", encoding="utf-8")
        result = run_hook(
            "posttool", posttool_input(tmp_path, transcript), extra_env=base_env(tmp_path)
        )
        assert result.stdout != ""  # 有効行のみで判定して発火

    def test_空のtranscriptは無出力でexit0(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("", encoding="utf-8")
        result = run_hook(
            "posttool", posttool_input(tmp_path, transcript), extra_env=base_env(tmp_path)
        )
        assert result.returncode == 0
        assert result.stdout == ""


LEAKED_TOOL_CALL = (
    'court\n<invoke name="Bash">\n<parameter name="command">echo ready</parameter>\n</invoke>'
)


def assistant_text(text: str, *, with_tool_use: bool = False) -> dict[str, object]:
    content: list[dict[str, object]] = [{"type": "text", "text": text}]
    if with_tool_use:
        content.append({"type": "tool_use", "id": "toolu_x", "name": "Bash", "input": {}})
    return {"type": "assistant", "message": {"content": content}}


def tool_result(*, is_error: bool) -> dict[str, object]:
    return {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_x",
                    "is_error": is_error,
                    "content": "",
                }
            ]
        },
    }


def stop_input(tmp_path: Path, transcript: Path) -> dict[str, object]:
    return {
        "session_id": "sess-1",
        "transcript_path": str(transcript),
        "cwd": str(tmp_path),
        "hook_event_name": "Stop",
        "stop_hook_active": False,
    }


class TestStopBrokenStreak:
    """stop: 末尾から連続する破損イベントが規定数に達したら 1 回だけ停止をブロックする。"""

    def leaks(self, n: int) -> list[dict[str, object]]:
        return [assistant_text(LEAKED_TOOL_CALL) for _ in range(n)]

    def test_破損5連続でblockしreasonにskill名を含む(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, [tool_result(is_error=False), *self.leaks(5)])
        result = run_hook("stop", stop_input(tmp_path, transcript), extra_env=base_env(tmp_path))
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["decision"] == "block"
        assert "session-handoff" in output["reason"]
        assert (tmp_path / "state" / "sess-1.blocked").is_file()

    def test_破損4連続では発火しない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, self.leaks(4))
        result = run_hook("stop", stop_input(tmp_path, transcript), extra_env=base_env(tmp_path))
        assert result.stdout == ""

    def test_正常なtool_resultでカウントがリセットされる(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, [*self.leaks(4), tool_result(is_error=False), *self.leaks(4)])
        result = run_hook("stop", stop_input(tmp_path, transcript), extra_env=base_env(tmp_path))
        assert result.stdout == ""  # リセット後の 4 連続のみで判定

    def test_エラーtool_resultも破損イベントとして数える(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(
            transcript,
            [
                *self.leaks(2),
                tool_result(is_error=True),
                tool_result(is_error=True),
                *self.leaks(1),
            ],
        )
        result = run_hook("stop", stop_input(tmp_path, transcript), extra_env=base_env(tmp_path))
        assert json.loads(result.stdout)["decision"] == "block"

    def test_正常なtool_use付きメッセージの断片は数えない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        entries = [assistant_text(LEAKED_TOOL_CALL, with_tool_use=True) for _ in range(5)]
        write_transcript(transcript, entries)
        result = run_hook("stop", stop_input(tmp_path, transcript), extra_env=base_env(tmp_path))
        assert result.stdout == ""

    def test_断片を含まない通常テキストは数えない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, [assistant_text("普通の応答です") for _ in range(5)])
        result = run_hook("stop", stop_input(tmp_path, transcript), extra_env=base_env(tmp_path))
        assert result.stdout == ""

    def test_stop_hook_activeのときはblockしない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, self.leaks(5))
        hook_input = stop_input(tmp_path, transcript)
        hook_input["stop_hook_active"] = True
        result = run_hook("stop", hook_input, extra_env=base_env(tmp_path))
        assert result.stdout == ""

    def test_block済みセッションでは再blockしない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, self.leaks(5))
        env = base_env(tmp_path)
        first = run_hook("stop", stop_input(tmp_path, transcript), extra_env=env)
        second = run_hook("stop", stop_input(tmp_path, transcript), extra_env=env)
        assert json.loads(first.stdout)["decision"] == "block"
        assert second.stdout == ""

    def test_成功と失敗が混在するtool_resultは破損として数える(self, tmp_path: Path) -> None:
        """並列ツール呼び出しで1エントリに成功/失敗が混在する場合、any(is_error) で broken 扱い。"""
        transcript = tmp_path / "t.jsonl"
        mixed_result: dict[str, object] = {
            "type": "user",
            "message": {
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_ok",
                        "is_error": False,
                        "content": "",
                    },
                    {
                        "type": "tool_result",
                        "tool_use_id": "toolu_ng",
                        "is_error": True,
                        "content": "",
                    },
                ]
            },
        }
        write_transcript(transcript, [*self.leaks(4), mixed_result])
        result = run_hook("stop", stop_input(tmp_path, transcript), extra_env=base_env(tmp_path))
        assert json.loads(result.stdout)["decision"] == "block"  # 4連続+混在1件=5でblock

    def test_HANDOFF_BROKEN_STREAKの上書きが閾値に反映される(self, tmp_path: Path) -> None:
        """既定の5ではなく3を境界値として使うことで、env override が実際に読まれることを示す。"""
        env = base_env(tmp_path) | {"HANDOFF_BROKEN_STREAK": "3"}

        miss_transcript = tmp_path / "miss.jsonl"
        write_transcript(miss_transcript, self.leaks(2))
        miss = run_hook("stop", stop_input(tmp_path, miss_transcript), extra_env=env)
        assert miss.stdout == ""

        hit_transcript = tmp_path / "hit.jsonl"
        write_transcript(hit_transcript, self.leaks(3))
        hit = run_hook("stop", stop_input(tmp_path, hit_transcript), extra_env=env)
        assert json.loads(hit.stdout)["decision"] == "block"
