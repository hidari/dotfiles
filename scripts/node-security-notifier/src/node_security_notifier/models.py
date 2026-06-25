"""フィードの 1 エントリを表す値型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeedEntry:
    """Node 脆弱性フィードの 1 リリース。guid は安定 ID、link は advisory URL。"""

    guid: str
    title: str
    link: str
    pub_date: str
