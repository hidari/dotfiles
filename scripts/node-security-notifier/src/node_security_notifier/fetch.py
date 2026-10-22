"""nodejs.org の配布一覧を取得する薄い I/O 層。"""

from __future__ import annotations

import urllib.request

INDEX_URL = "https://nodejs.org/dist/index.json"


def fetch_index(url: str = INDEX_URL, *, timeout: float = 30.0) -> bytes:
    """配布一覧を取得し生バイト列を返す。失敗時は OSError 系を送出。"""
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data: bytes = resp.read()
    return data
