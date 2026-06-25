"""state（既読集合の永続化）の仕様テスト。"""

from __future__ import annotations

from pathlib import Path

from node_security_notifier.state import load_seen, save_seen


class TestState:
    def test_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "seen.json"
        save_seen(path, {"g-b", "g-a"})
        assert load_seen(path) == {"g-a", "g-b"}

    def test_load_missing_returns_empty(self, tmp_path: Path) -> None:
        assert load_seen(tmp_path / "absent.json") == set()

    def test_load_corrupt_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "seen.json"
        path.write_text("{ not json", encoding="utf-8")
        assert load_seen(path) == set()

    def test_load_non_list_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "seen.json"
        path.write_text("{}", encoding="utf-8")
        assert load_seen(path) == set()

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "deep" / "seen.json"
        save_seen(path, {"g-a"})
        assert path.exists()
        assert load_seen(path) == {"g-a"}
