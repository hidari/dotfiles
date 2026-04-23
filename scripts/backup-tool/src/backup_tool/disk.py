"""ディスク容量計算と測定。

純粋関数 (required_total_kb / check_capacity) と
副作用境界 (measure_source_size_kb / measure_dest_total_kb) を分離する。
issue #3 で修正した「総容量ベース判定」のロジックを踏襲する。
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

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


def check_capacity(*, dest_total_kb: int, required_kb: int) -> CapacityReport:
    """バックアップ先の総容量が必要容量を満たすか判定する。"""
    return CapacityReport(dest_total_kb=dest_total_kb, required_kb=required_kb)


def measure_source_size_kb(path: Path) -> int | None:
    """du -sk でディレクトリ使用容量 (KB) を返す。取得失敗時は None。"""
    return _measure_kb(["du", "-sk", str(path)], field=0)


def measure_dest_total_kb(path: Path) -> int | None:
    """df -k でファイルシステム総容量 (KB) を返す。取得失敗時は None。"""
    # df 出力: Filesystem 1024-blocks Used Available Capacity iused ifree %iused Mounted on
    return _measure_kb(["df", "-k", str(path)], field=1, use_last_line=True)


def _measure_kb(argv: list[str], *, field: int, use_last_line: bool = False) -> int | None:
    try:
        completed = subprocess.run(argv, capture_output=True, text=True, check=False)
    except FileNotFoundError:
        return None
    if completed.returncode != 0:
        return None
    lines = completed.stdout.strip().splitlines()
    if not lines:
        return None
    target = lines[-1] if use_last_line else lines[0]
    fields = target.split()
    if len(fields) <= field:
        return None
    try:
        size = int(fields[field])
    except ValueError:
        return None
    return size if size > 0 else None


def format_gb(kb: int) -> str:
    """KB を GB 表記 (小数点 2 桁) に整形する。"""
    return f"{kb / _GB_TO_KB:.2f} GB"
