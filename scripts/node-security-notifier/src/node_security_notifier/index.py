"""nodejs.org/dist/index.json から security リリースの版を取り出す純粋関数。

形の崩れはすべて IndexFormatError にする。空の一覧や崩れた要素を「該当なし」へ潰すと、
判定が壊れていても遅れなしとして記録され、告知が黙る。
"""

from __future__ import annotations

import json
import re

_VERSION = re.compile(r"v(\d+\.\d+\.\d+)")


class IndexFormatError(ValueError):
    """index.json が想定した形でない。"""


def parse_index(raw: bytes) -> list[str]:
    """security: true の版を、先頭の v を外した形で出現順に返す。"""
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise IndexFormatError(f"JSON として読めない: {exc}") from exc
    if not isinstance(data, list):
        raise IndexFormatError("最上位がリストではない")

    versions: list[str] = []
    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            raise IndexFormatError(f"{i} 番目の要素がオブジェクトではない")
        version = entry.get("version")
        match = _VERSION.fullmatch(version) if isinstance(version, str) else None
        if match is None:
            raise IndexFormatError(f"{i} 番目の要素の version が v<数>.<数>.<数> ではない")
        security = entry.get("security")
        if not isinstance(security, bool):
            raise IndexFormatError(f"{i} 番目の要素の security が bool ではない")
        if security:
            versions.append(match.group(1))

    # 空のリストもここで落ちる
    if not versions:
        raise IndexFormatError("security: true の版が 1 件も無い")
    return versions
