"""ディスク容量計算と測定。

純粋な計算 (required_total_kb / CapacityReport) と
副作用境界 (measure_source_size_kb / measure_dest_total_kb) を分離する。
容量の判定は、空き容量ではなくバックアップ先の総容量で行う。
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path
from shutil import disk_usage

_GB_TO_KB = 1024 * 1024


@dataclass(frozen=True, slots=True)
class CapacityReport:
    dest_total_kb: int
    required_kb: int

    @property
    def is_sufficient(self) -> bool:
        return self.dest_total_kb >= self.required_kb

    @property
    def shortage_kb(self) -> int:
        return max(0, self.required_kb - self.dest_total_kb)


def required_total_kb(*, source_size_kb: int, margin_gb: int) -> int:
    """ソースデータ + マージン (GB) を合算した KB を返す。"""
    if source_size_kb < 0:
        raise ValueError(f"source_size_kb は 0 以上である必要があります: {source_size_kb}")
    if margin_gb < 0:
        raise ValueError(f"margin_gb は 0 以上である必要があります: {margin_gb}")
    return source_size_kb + margin_gb * _GB_TO_KB


def measure_source_size_kb(path: Path) -> int | None:
    """du -sk でディレクトリ使用容量 (KB) を返す。取得できないか値が範囲外なら None。"""
    try:
        completed = subprocess.run(
            ["du", "-sk", str(path)], capture_output=True, text=True, check=False
        )
    except FileNotFoundError:
        return None
    if completed.returncode != 0:
        return None
    # du -sk の出力: <KB>\t<path>
    fields = completed.stdout.split()
    if not fields:
        return None
    try:
        size = int(fields[0])
    except ValueError:
        return None
    # 空のディレクトリでは0になるので、0は正当な使用量
    return size if size >= 0 else None


def measure_dest_total_kb(path: Path) -> int | None:
    """path を含むファイルシステムの総容量 (KB) を返す。取得できないか値が範囲外なら None。"""
    try:
        total_kb = disk_usage(path).total // 1024
    except OSError:
        return None
    # 総容量が0のファイルシステムには書けないので、測定の異常として扱う
    return total_kb if total_kb > 0 else None


def format_gb(kb: int) -> str:
    """KB を GB 表記 (小数点 2 桁) に整形する。"""
    return f"{kb / _GB_TO_KB:.2f} GB"
