"""cli オーケストレーションの仕様テスト (依存注入、モック不使用)。

失敗はどれも非 0 で終わり、前回の状態ファイルを上書きしない。上書きすると取得時刻が
新しくなり、判定が止まっていることをプローブが告げられなくなる。
"""

from __future__ import annotations

import json
import time
from pathlib import Path

from node_security_notifier.cli import run
from node_security_notifier.state import save_status

FIXTURE = Path(__file__).parent / "fixtures" / "index_excerpt.json"


def _fetch_ok() -> bytes:
    return FIXTURE.read_bytes()


def _previous_state(tmp_path: Path) -> tuple[Path, bytes]:
    path = tmp_path / "status.json"
    save_status(path, fetched_at=1, security_versions=["24.18.1"])
    return path, path.read_bytes()


class TestRun:
    def test_success_writes_versions_and_fetch_time(self, tmp_path: Path) -> None:
        path = tmp_path / "status.json"
        rc = run(fetcher=_fetch_ok, state_path=path, clock=lambda: 1_761_100_000.9)
        assert rc == 0
        assert json.loads(path.read_text(encoding="utf-8")) == {
            "fetched_at": 1_761_100_000,
            "security_versions": ["26.12.1", "25.8.2", "24.22.1", "24.18.1", "22.22.0"],
        }

    def test_fetch_failure_keeps_previous_state(self, tmp_path: Path) -> None:
        path, before = _previous_state(tmp_path)

        def _fetch_fail() -> bytes:
            raise OSError("nodename nor servname provided, or not known")

        rc = run(fetcher=_fetch_fail, state_path=path, clock=lambda: 2.0)
        assert rc == 1
        assert path.read_bytes() == before

    def test_malformed_index_keeps_previous_state(self, tmp_path: Path) -> None:
        path, before = _previous_state(tmp_path)
        rc = run(fetcher=lambda: b"[]", state_path=path, clock=lambda: 2.0)
        assert rc == 1
        assert path.read_bytes() == before

    def test_default_clock_is_wall_clock(self, tmp_path: Path) -> None:
        path = tmp_path / "status.json"
        before = int(time.time())
        assert run(fetcher=_fetch_ok, state_path=path) == 0
        after = int(time.time())
        fetched_at = json.loads(path.read_text(encoding="utf-8"))["fetched_at"]
        assert before <= fetched_at <= after
