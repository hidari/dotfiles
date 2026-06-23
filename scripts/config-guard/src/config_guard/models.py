"""検出結果を表す値型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    """1 件の検出。source は検出元、detail は該当トークン/キー、message は理由。"""

    source: str
    detail: str
    message: str
