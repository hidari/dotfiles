"""instructions-loaded-log hook の黒箱テスト。

hook 本体をサブプロセス起動し、stdin に InstructionsLoaded の JSON を流して JSONL へ書かれた
内容を検証する。モックは使わず、書き込み先は tmp_path 配下へ向ける。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from conftest import HOOKS_DIR

HOOK = HOOKS_DIR / "instructions-loaded-log.py"

DEFAULT_LOG_RELPATH = Path(".cache") / "claude" / "instructions-loaded.jsonl"


def run_hook_raw(payload: str, log_path: Path) -> subprocess.CompletedProcess[str]:
    """stdin へ生の文字列を流してフックを起動する。

    基底環境から INSTRUCTIONS_LOADED_LOG を除いてから log_path だけを適用する。実行環境に
    別の書き込み先が設定されていると、テストが実ログを汚しつつ空の tmp を見て緑になる。
    この除去を書き写した経路を作らないため、JSON を送る場合も生文字列を送る場合もここを通す。

    「常に exit 0 で無出力」はどの入力でも守られるべき契約なので、個別のテストへ書き写さず
    ここで pin する。テストを足した人が書き忘れても、契約が破れれば必ず落ちる。
    """
    env = {k: v for k, v in os.environ.items() if k != "INSTRUCTIONS_LOADED_LOG"}
    env["INSTRUCTIONS_LOADED_LOG"] = str(log_path)
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert proc.returncode == 0, f"観測器は作業を止めない契約: stderr={proc.stderr}"
    assert proc.stdout == "", f"観測器は無出力の契約: stdout={proc.stdout!r}"
    return proc


def run_hook(body: dict[str, Any], log_path: Path) -> subprocess.CompletedProcess[str]:
    return run_hook_raw(json.dumps(body), log_path)


def read_records(log_path: Path) -> list[dict[str, Any]]:
    """JSONL を 1 行 1 レコードとして読む。ファイルが無ければ空リストを返す。"""
    if not log_path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line:
            records.append(json.loads(line))
    return records


class TestFailSafe:
    """観測器の故障で作業を止めない。どの入力でも記録せずに素通りする。

    exit code と stdout の契約は run_hook_raw が全呼び出しで pin しているので、
    ここでは「記録が起きないこと」だけを見る。
    """

    def test_非JSONのstdinは記録しない(self, tmp_path: Path) -> None:
        log = tmp_path / "out.jsonl"
        run_hook_raw("not json at all", log)
        assert read_records(log) == []

    def test_空stdinは記録しない(self, tmp_path: Path) -> None:
        log = tmp_path / "out.jsonl"
        run_hook_raw("", log)
        assert read_records(log) == []

    def test_dictでないJSONは記録しない(self, tmp_path: Path) -> None:
        # 空 list を使う。要素のある list だと dict ガードを外しても payload[k] が
        # TypeError になり fail-safe に捕まるため、ガードを壊しても緑のままになる。
        log = tmp_path / "out.jsonl"
        run_hook_raw(json.dumps([]), log)
        assert read_records(log) == []

    def test_dictでないJSONは文字列でも記録しない(self, tmp_path: Path) -> None:
        log = tmp_path / "out.jsonl"
        run_hook_raw(json.dumps(""), log)
        assert read_records(log) == []

    def test_書き込めないパスでも素通りする(self, tmp_path: Path) -> None:
        # 既存ファイルを親ディレクトリに指定すると mkdir が失敗する。
        blocker = tmp_path / "blocker"
        blocker.write_text("", encoding="utf-8")
        run_hook({"hook_event_name": "InstructionsLoaded"}, blocker / "out.jsonl")


class TestRecordedFields:
    """受け取ったフィールドをそのまま通し、未知のフィールドも取りこぼさない。"""

    def test_既知フィールドはそのまま記録される(self, tmp_path: Path) -> None:
        log = tmp_path / "out.jsonl"
        run_hook(
            {
                "session_id": "s-1",
                "cwd": "/tmp/work",
                "hook_event_name": "InstructionsLoaded",
                "file_path": "/tmp/work/CLAUDE.md",
                "memory_type": "project",
                "load_reason": "session_start",
                "globs": ["**/*.ts"],
                "trigger_file_path": "/tmp/work/src/a.ts",
                "parent_file_path": "/tmp/work/AGENTS.md",
            },
            log,
        )
        records = read_records(log)
        assert len(records) == 1
        record = records[0]
        assert record["session_id"] == "s-1"
        assert record["cwd"] == "/tmp/work"
        assert record["hook_event_name"] == "InstructionsLoaded"
        assert record["file_path"] == "/tmp/work/CLAUDE.md"
        assert record["memory_type"] == "project"
        assert record["load_reason"] == "session_start"
        assert record["globs"] == ["**/*.ts"]
        assert record["trigger_file_path"] == "/tmp/work/src/a.ts"
        assert record["parent_file_path"] == "/tmp/work/AGENTS.md"
        assert "_unknown_fields" not in record

    def test_observed_atがISO8601のUTCで付く(self, tmp_path: Path) -> None:
        log = tmp_path / "out.jsonl"
        run_hook({"hook_event_name": "InstructionsLoaded"}, log)
        observed_at = read_records(log)[0]["observed_at"]
        assert observed_at.endswith("+00:00")
        assert datetime.fromisoformat(observed_at).utcoffset() == timedelta(0)

    def test_未知フィールドは_unknown_fieldsへ畳まれる(self, tmp_path: Path) -> None:
        log = tmp_path / "out.jsonl"
        run_hook(
            {"hook_event_name": "InstructionsLoaded", "brand_new": 42, "another": {"k": "v"}},
            log,
        )
        record = read_records(log)[0]
        assert record["_unknown_fields"] == {"another": {"k": "v"}, "brand_new": 42}

    def test_transcript_pathとprompt_idは捨てられる(self, tmp_path: Path) -> None:
        log = tmp_path / "out.jsonl"
        run_hook(
            {
                "hook_event_name": "InstructionsLoaded",
                "transcript_path": "/tmp/transcript.jsonl",
                "prompt_id": "p-1",
            },
            log,
        )
        record = read_records(log)[0]
        assert "transcript_path" not in record
        assert "prompt_id" not in record
        assert "_unknown_fields" not in record

    def test_日本語を含む値はエスケープせず保存される(self, tmp_path: Path) -> None:
        log = tmp_path / "out.jsonl"
        run_hook({"hook_event_name": "InstructionsLoaded", "cwd": "/tmp/作業"}, log)
        raw = log.read_text(encoding="utf-8")
        assert "/tmp/作業" in raw
        assert "\\u" not in raw


class TestLogFile:
    """書き込み先の解決と追記の挙動。"""

    def test_env未指定なら既定のパスへ書く(self, tmp_path: Path) -> None:
        # ここだけ run_hook_raw を通さない。既定パスの解決そのものが検証対象なので、
        # INSTRUCTIONS_LOADED_LOG を設定してしまうとその経路を踏めない。
        env = {k: v for k, v in os.environ.items() if k != "INSTRUCTIONS_LOADED_LOG"}
        env["HOME"] = str(tmp_path)
        proc = subprocess.run(
            [sys.executable, str(HOOK)],
            input=json.dumps({"hook_event_name": "InstructionsLoaded"}),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        assert proc.returncode == 0
        assert proc.stdout == ""
        assert len(read_records(tmp_path / DEFAULT_LOG_RELPATH)) == 1

    def test_親ディレクトリが無ければ作る(self, tmp_path: Path) -> None:
        log = tmp_path / "deep" / "nested" / "out.jsonl"
        run_hook({"hook_event_name": "InstructionsLoaded"}, log)
        assert len(read_records(log)) == 1

    def test_二度目の呼び出しは追記される(self, tmp_path: Path) -> None:
        log = tmp_path / "out.jsonl"
        run_hook({"hook_event_name": "InstructionsLoaded", "file_path": "/a"}, log)
        run_hook({"hook_event_name": "InstructionsLoaded", "file_path": "/b"}, log)
        records = read_records(log)
        assert [r["file_path"] for r in records] == ["/a", "/b"]

    def test_1レコードが1行に収まる(self, tmp_path: Path) -> None:
        log = tmp_path / "out.jsonl"
        run_hook({"hook_event_name": "InstructionsLoaded", "cwd": "/tmp/a\nb"}, log)
        assert len(log.read_text(encoding="utf-8").splitlines()) == 1
