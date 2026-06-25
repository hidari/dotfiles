"""Node 脆弱性 RSS を取得する薄い I/O 層。"""

from __future__ import annotations

import urllib.request

FEED_URL = "https://nodejs.org/en/feed/vulnerability.xml"


def fetch_feed(url: str = FEED_URL, *, timeout: float = 30.0) -> bytes:
    """フィード URL を取得し生バイト列を返す。失敗時は OSError 系を送出。"""
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data: bytes = resp.read()
    return data
