"""rsync 起動・オプション構築・出力フィルタリング。

純粋関数 (build_options / is_suppressible_error / summarize_filtered_errors) と
副作用境界 (run) を明示的に分けている。
"""

from __future__ import annotations

import re
import subprocess
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path

# backup.sh:280 で定義されていたフィルタ正規表現を 1:1 で移植。
# macOS が保護しているシステムディレクトリへのアクセス/削除エラーを抑制する。
_SUPPRESSIBLE_PATTERN = re.compile(
    r"\.(Trashes|Spotlight-V100|fseventsd|TemporaryItems).*failed: Operation not permitted"
    r"|IO error encountered -- skipping file deletion"
    r"|rsync error:.*some files/attrs were not transferred.*code 23"
)

_TRACKED_DIRS: tuple[str, ...] = (
    ".Trashes",
    ".Spotlight-V100",
    ".fseventsd",
    ".TemporaryItems",
)


@dataclass(frozen=True, slots=True)
class RsyncResult:
    exit_code: int
    filtered_errors: tuple[str, ...]


def build_options(*, excludes: Sequence[str], dry_run: bool) -> list[str]:
    """rsync に渡すオプション列を組み立てる。

    --delete-excluded は意図的に付けていない。destination 側の .Trashes /
    .Spotlight-V100 を削除しようとして macOS の保護で Operation not permitted
    を引き起こし、毎回 rsync code 23 のノイズになるため。
    destination は backup 専用運用を前提に、excludes 対象は触らない。
    """
    options: list[str] = [
        "-avh",
        "--delete-before",
        "--progress",
        "--stats",
    ]
    options.extend(f"--exclude={pattern}" for pattern in excludes)
    if dry_run:
        options.append("--dry-run")
    return options


def is_suppressible_error(line: str) -> bool:
    """行が「抑制して良い既知の無害エラー」にマッチするかを判定する。"""
    if not line:
        return False
    return _SUPPRESSIBLE_PATTERN.search(line) is not None


def summarize_filtered_errors(lines: Iterable[str]) -> dict[str, int]:
    """抑制したエラーをディレクトリ単位でカウントして返す。"""
    counts: dict[str, int] = {}
    for line in lines:
        for directory in _TRACKED_DIRS:
            if directory in line:
                counts[directory] = counts.get(directory, 0) + 1
    return counts


def run(
    *,
    source: Path,
    destination: Path,
    options: Sequence[str],
    on_output: Callable[[str], None],
) -> RsyncResult:
    """rsync をサブプロセスで起動し、1 行ごとに on_output に渡す。

    抑制対象の行は画面には出さず、RsyncResult.filtered_errors に蓄積する。
    それ以外の行は on_output で上位レイヤーに渡し、標準出力/ログに流す。
    """
    source_arg = f"{str(source).rstrip('/')}/"
    destination_arg = str(destination).rstrip("/")

    argv = ["rsync", *options, source_arg, destination_arg]

    filtered: list[str] = []
    with subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    ) as process:
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.rstrip("\n")
            if is_suppressible_error(line):
                filtered.append(line)
            else:
                on_output(line)
        process.wait()
        exit_code = process.returncode

    return RsyncResult(exit_code=exit_code, filtered_errors=tuple(filtered))
