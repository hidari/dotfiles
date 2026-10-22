"""判定結果の状態ファイルの仕様テスト。

読み手は guard_probes (claude-hooks) で、形の一致はあちらのテストがこのモジュールを直接
読み込んで pin する。ここでは書き手としての振る舞いを見る。
"""

from __future__ import annotations

import json
from pathlib import Path

from node_security_notifier.state import STATE_RELPATH, save_status


class TestSaveStatus:
    def test_writes_fetched_at_and_versions(self, tmp_path: Path) -> None:
        path = tmp_path / "status.json"
        save_status(path, fetched_at=1_761_100_000, security_versions=["24.22.1", "24.18.1"])
        assert json.loads(path.read_text(encoding="utf-8")) == {
            "fetched_at": 1_761_100_000,
            "security_versions": ["24.22.1", "24.18.1"],
        }

    def test_creates_parent_directory(self, tmp_path: Path) -> None:
        path = tmp_path / "a" / "b" / "status.json"
        save_status(path, fetched_at=1, security_versions=["24.22.1"])
        assert path.is_file()

    def test_overwrites_and_leaves_no_temporary_file(self, tmp_path: Path) -> None:
        path = tmp_path / "status.json"
        save_status(path, fetched_at=1, security_versions=["24.18.1"])
        save_status(path, fetched_at=2, security_versions=["24.22.1"])
        assert json.loads(path.read_text(encoding="utf-8"))["fetched_at"] == 2
        assert sorted(p.name for p in tmp_path.iterdir()) == ["status.json"]

    def test_state_lives_under_the_home_relative_state_directory(self) -> None:
        assert Path(".local/state/node-security-notifier/security-releases.json") == STATE_RELPATH
