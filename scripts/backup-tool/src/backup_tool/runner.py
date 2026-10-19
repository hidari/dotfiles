"""バックアップ全体の orchestration。

CLI 層から config + dry_run を受け取り、各ペアごとに
パス検証 → 容量チェック → rsync 実行 を順次行う。
終了コード(0/2/3) の集約ロジックもここ。
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, IntEnum, auto
from pathlib import Path
from typing import Literal

from backup_tool.config import BackupPair, Config
from backup_tool.disk import (
    CapacityReport,
    format_gb,
    measure_dest_total_kb,
    measure_source_size_kb,
    required_total_kb,
)
from backup_tool.excludes import DEFAULT_EXCLUDES
from backup_tool.paths import (
    classify,
    ensure_readable,
    ensure_writable,
    extract_volume_path,
    is_mounted,
)
from backup_tool.rsync import RsyncResult, build_options, summarize_filtered_errors
from backup_tool.rsync import run as rsync_run

PathMode = Literal["read", "write"]


class ExitCode(IntEnum):
    SUCCESS = 0
    USER_ABORT = 1
    PARTIAL_FAILURE = 2
    TOTAL_FAILURE = 3


class BackupAbortedError(RuntimeError):
    """パス未マウント / 権限不足 / 容量不足など、ペア実行前に失敗したとき送出。"""


class PairStatus(Enum):
    SUCCESS = auto()
    PARTIAL = auto()
    FAILED = auto()
    ABORTED = auto()
    SKIPPED = auto()


# 完了 = 成功か部分的成功。終了コードはこの集合に入るペアの数で決まる
_COMPLETED = frozenset({PairStatus.SUCCESS, PairStatus.PARTIAL})
# error_behavior=stop で残りのペアを止める状態
_STOPS_RUN = frozenset({PairStatus.FAILED, PairStatus.ABORTED})


@dataclass(frozen=True)
class PairOutcome:
    name: str
    status: PairStatus
    filtered_errors: tuple[str, ...] = ()


def run_backup(
    config: Config,
    *,
    dry_run: bool,
    logger: logging.Logger,
) -> ExitCode:
    """全ペアを実行し、ペアごとの結果から要約と終了コードを導く。"""
    outcomes = _run_pairs(config, dry_run=dry_run, logger=logger)
    statuses = [outcome.status for outcome in outcomes]
    _log_summary(logger, statuses)
    _log_filtered_errors(
        logger, [error for outcome in outcomes for error in outcome.filtered_errors]
    )
    return _determine_exit_code(statuses)


def _run_pairs(
    config: Config,
    *,
    dry_run: bool,
    logger: logging.Logger,
) -> list[PairOutcome]:
    """全ペアの結果を設定の順に返す。stop で中断した後のペアは SKIPPED として並べる。"""
    outcomes: list[PairOutcome] = []
    stopped = False
    for pair in config.backup_pairs:
        if stopped:
            outcomes.append(PairOutcome(name=pair.name, status=PairStatus.SKIPPED))
            continue
        outcome = _run_pair(config, pair, dry_run=dry_run, logger=logger)
        outcomes.append(outcome)
        if outcome.status in _STOPS_RUN and config.error_behavior == "stop":
            logger.error("error_behavior=stop のため処理を中断します")
            stopped = True
    return outcomes


def _run_pair(
    config: Config,
    pair: BackupPair,
    *,
    dry_run: bool,
    logger: logging.Logger,
) -> PairOutcome:
    logger.info("========== [%s] バックアップ開始 ==========", pair.name)
    logger.info("source: %s", pair.source)
    logger.info("destination: %s", pair.destination)

    try:
        result = _execute_pair(config, pair, dry_run=dry_run, logger=logger)
    except BackupAbortedError as err:
        logger.error("[%s] %s", pair.name, err)
        return PairOutcome(name=pair.name, status=PairStatus.ABORTED)

    if result.exit_code == 0:
        status = PairStatus.SUCCESS
    elif result.exit_code == 23:
        logger.warning("[%s] 部分的成功 (rsync code 23)", pair.name)
        status = PairStatus.PARTIAL
    else:
        logger.error("[%s] 失敗 (rsync code %d)", pair.name, result.exit_code)
        status = PairStatus.FAILED
    return PairOutcome(name=pair.name, status=status, filtered_errors=tuple(result.filtered_errors))


def _execute_pair(
    config: Config,
    pair: BackupPair,
    *,
    dry_run: bool,
    logger: logging.Logger,
) -> RsyncResult:
    source = Path(pair.source)
    destination = Path(pair.destination)

    _verify_path(source, role="ソース", mode="read")
    _verify_path(destination, role="デスティネーション", mode="write")
    _verify_capacity(
        source=source,
        destination=destination,
        minimum_free_space_gb=config.minimum_free_space_gb,
        pair_name=pair.name,
        logger=logger,
    )

    excludes = _build_excludes(config=config, pair=pair)
    options = build_options(excludes=excludes, dry_run=dry_run)
    logger.info("[%s] rsync %s", pair.name, " ".join(options))

    return rsync_run(
        source=source,
        destination=destination,
        options=options,
        on_output=lambda line: logger.info("[%s] %s", pair.name, line),
    )


def _verify_path(path: Path, *, role: str, mode: PathMode) -> None:
    kind = classify(str(path))
    if kind == "volume":
        if not is_mounted(str(path)):
            raise BackupAbortedError(f"{role}のボリュームがマウントされていません: {path}")
    elif kind == "directory":
        volume = extract_volume_path(str(path))
        if volume is None or not is_mounted(volume):
            raise BackupAbortedError(f"{role}の親ボリュームがマウントされていません: {path}")
        if not path.is_dir():
            raise BackupAbortedError(f"{role}のディレクトリが存在しません: {path}")
    elif not path.is_dir():
        raise BackupAbortedError(f"{role}のディレクトリが存在しません: {path}")

    if mode == "read" and not ensure_readable(path):
        raise BackupAbortedError(f"{role}に読み取り権限がありません: {path}")
    if mode == "write" and not ensure_writable(path):
        raise BackupAbortedError(f"{role}に書き込み権限がありません: {path}")


def _verify_capacity(
    *,
    source: Path,
    destination: Path,
    minimum_free_space_gb: int,
    pair_name: str,
    logger: logging.Logger,
) -> None:
    logger.info("[%s] ディスク容量をチェック中", pair_name)
    source_size_kb = measure_source_size_kb(source)
    if source_size_kb is None:
        logger.warning(
            "[%s] ソース容量を取得できませんでした。容量チェックをスキップします", pair_name
        )
        return
    dest_total_kb = measure_dest_total_kb(destination)
    if dest_total_kb is None:
        logger.warning(
            "[%s] 宛先総容量を取得できませんでした。容量チェックをスキップします", pair_name
        )
        return
    required = required_total_kb(source_size_kb=source_size_kb, margin_gb=minimum_free_space_gb)
    report = CapacityReport(dest_total_kb=dest_total_kb, required_kb=required)

    logger.info("[%s] ソース使用量: %s", pair_name, format_gb(source_size_kb))
    logger.info("[%s] 宛先総容量:   %s", pair_name, format_gb(dest_total_kb))
    logger.info(
        "[%s] 必要容量 (data + margin %dGB): %s",
        pair_name,
        minimum_free_space_gb,
        format_gb(required),
    )
    if not report.is_sufficient:
        raise BackupAbortedError(
            f"バックアップ先の総容量が不足しています (不足 {format_gb(report.shortage_kb)})"
        )


def _build_excludes(*, config: Config, pair: BackupPair) -> Sequence[str]:
    return (*DEFAULT_EXCLUDES, *config.additional_excludes, *pair.excludes)


def _log_summary(logger: logging.Logger, statuses: Sequence[PairStatus]) -> None:
    total = len(statuses)
    # 中断は失敗の行にまとめ、各行の合計が total になるようにする
    rows = (
        ("成功:        ", (PairStatus.SUCCESS,)),
        ("部分的成功:  ", (PairStatus.PARTIAL,)),
        ("失敗:        ", (PairStatus.FAILED, PairStatus.ABORTED)),
        ("未実行:      ", (PairStatus.SKIPPED,)),
    )
    logger.info("========== バックアップ結果サマリー ==========")
    for label, members in rows:
        count = sum(1 for status in statuses if status in members)
        logger.info("%s %d / %d", label, count, total)


def _log_filtered_errors(logger: logging.Logger, filtered: Sequence[str]) -> None:
    if not filtered:
        return
    summary = summarize_filtered_errors(filtered)
    if not summary:
        return
    logger.info("---------- 抑制されたシステムエラーのサマリー ----------")
    for directory, count in summary.items():
        logger.info(" %s: %d 件", directory, count)
    logger.info("これらは macOS 保護ディレクトリの既知エラーで、データには影響しません")


def _determine_exit_code(statuses: Sequence[PairStatus]) -> ExitCode:
    # 完了が無い判定を先に置き、空の列や未実行だけの列を成功に倒さない
    completed = sum(1 for status in statuses if status in _COMPLETED)
    if completed == 0:
        return ExitCode.TOTAL_FAILURE
    if completed == len(statuses):
        return ExitCode.SUCCESS
    return ExitCode.PARTIAL_FAILURE
