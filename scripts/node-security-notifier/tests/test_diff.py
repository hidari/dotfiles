"""diff（新着抽出）の仕様テスト。"""

from __future__ import annotations

from node_security_notifier.diff import new_entries
from node_security_notifier.models import FeedEntry

A = FeedEntry("g-a", "A", "https://x/a", "d")
B = FeedEntry("g-b", "B", "https://x/b", "d")
C = FeedEntry("g-c", "C", "https://x/c", "d")


class TestNewEntries:
    def test_returns_unseen_in_order(self) -> None:
        assert new_entries([A, B, C], {"g-b"}) == [A, C]

    def test_empty_when_all_seen(self) -> None:
        assert new_entries([A, B], {"g-a", "g-b"}) == []

    def test_all_when_seen_empty(self) -> None:
        assert new_entries([A, B], set()) == [A, B]
