"""既読集合に基づき新着エントリを抽出する純粋関数。"""

from __future__ import annotations

from node_security_notifier.models import FeedEntry


def new_entries(current: list[FeedEntry], seen: set[str]) -> list[FeedEntry]:
    """current のうち guid が seen に含まれないものを出現順で返す。"""
    return [entry for entry in current if entry.guid not in seen]
