"""nodejs.org の配布一覧を取得する薄い I/O 層。"""

from __future__ import annotations

import urllib.request

INDEX_URL = "https://nodejs.org/dist/index.json"
_TIMEOUT_SECONDS = 30.0


def fetch_index() -> bytes:
    """配布一覧を取得し生バイト列を返す。失敗時は OSError 系を送出。"""
    with urllib.request.urlopen(INDEX_URL, timeout=_TIMEOUT_SECONDS) as resp:
        data: bytes = resp.read()
    return data
