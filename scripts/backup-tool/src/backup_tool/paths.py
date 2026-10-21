"""パス種別判定とマウント確認。

純粋関数 (classify / extract_volume_path) と
副作用境界 (is_mounted / ensure_readable / ensure_writable) を分離する。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Literal

PathKind = Literal["volume", "directory", "local"]

# /Volumes/<name> ちょうどにマッチ (末尾スラッシュは許容)
_VOLUME_ROOT = re.compile(r"^/Volumes/[^/]+/?$")
# 先頭に /Volumes/<name> を含む任意のパス
_VOLUME_PREFIX = re.compile(r"^(/Volumes/[^/]+)(?:/|$)")


def classify(path: str) -> PathKind:
    """パスを volume / directory / local のいずれかに分類する。"""
    if _VOLUME_ROOT.match(path):
        return "volume"
    if _VOLUME_PREFIX.match(path):
        return "directory"
    return "local"


def extract_volume_path(path: str) -> str | None:
    """/Volumes/<name> までを抽出する。Volume 配下でなければ None。"""
    match = _VOLUME_PREFIX.match(path)
    if match is None:
        return None
    return match.group(1)


def is_mounted(mount_point: str) -> bool:
    """指定パスがマウントポイントかを返す。シンボリックリンクはマウントポイントとみなさない。"""
    return os.path.ismount(mount_point)


def ensure_readable(path: Path) -> bool:
    return os.access(path, os.R_OK)


def ensure_writable(path: Path) -> bool:
    return os.access(path, os.W_OK)
