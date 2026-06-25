"""既読 GUID 集合を JSON で永続化する。"""

from __future__ import annotations

import json
from pathlib import Path


def load_seen(path: Path) -> set[str]:
    """既読 GUID 集合を読む。欠落・破損・非リストの場合は空集合を返す。"""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return set()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return set()
    if not isinstance(data, list):
        return set()
    return {str(item) for item in data}


def save_seen(path: Path, seen: set[str]) -> None:
    """既読 GUID 集合を JSON 配列で書き込む。親ディレクトリは自動作成する。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
