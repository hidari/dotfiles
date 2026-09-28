"""runner モジュールのテスト。

終了コード集約と excludes 合成を純粋関数として検証し、run_backup は
実在しないディレクトリと偽の du / df / rsync で失敗経路を通す。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from backup_tool.config import BackupPair, Config, ErrorBehavior
from backup_tool.runner import ExitCode, _build_excludes, _determine_exit_code, run_backup

if TYPE_CHECKING:
    from tests.conftest import FakeCommand

_LOGGER_NAME = "tests.runner"
_PAIR_STARTED = re.compile(r"\[(.+)\] バックアップ開始")


def _make_config(*, additional: tuple[str, ...] = ()) -> Config:
    return Config(
        minimum_free_space_gb=100,
        log_retention_days=90,
        additional_excludes=additional,
        backup_pairs=(BackupPair(name="p", source="/Volumes/A", destination="/Volumes/B"),),
    )


class TestDetermineExitCode:
    def test_all_success(self) -> None:
        assert _determine_exit_code(fail=0, total=3) == ExitCode.SUCCESS

    def test_partial_success_counts_as_success(self) -> None:
        # rsync code 23 は「部分的成功」で fail には入らない
        assert _determine_exit_code(fail=0, total=2) == ExitCode.SUCCESS

    def test_partial_failure(self) -> None:
        assert _determine_exit_code(fail=1, total=2) == ExitCode.PARTIAL_FAILURE

    def test_total_failure(self) -> None:
        assert _determine_exit_code(fail=3, total=3) == ExitCode.TOTAL_FAILURE


class TestBuildExcludes:
    def test_merges_default_additional_and_pair_excludes(self) -> None:
        config = _make_config(additional=("custom_a",))
        pair = BackupPair(
            name="p",
            source="/Volumes/A",
            destination="/Volumes/B",
            excludes=("pair_specific",),
        )
        result = _build_excludes(config=config, pair=pair)
        # DEFAULT_EXCLUDES (.DS_Store など) + additional + pair 固有
        assert ".DS_Store" in result
        assert "custom_a" in result
        assert "pair_specific" in result

    def test_preserves_order_default_additional_pair(self) -> None:
        config = _make_config(additional=("custom",))
        pair = BackupPair(
            name="p",
            source="/Volumes/A",
            destination="/Volumes/B",
            excludes=("pair_only",),
        )
        result = list(_build_excludes(config=config, pair=pair))
        # custom は全デフォルト除外リストの後
        custom_idx = result.index("custom")
        ds_store_idx = result.index(".DS_Store")
        pair_only_idx = result.index("pair_only")
        assert ds_store_idx < custom_idx < pair_only_idx


def _missing_pair(tmp_path: Path, name: str) -> BackupPair:
    # ソースが存在しないのでパス検証で BackupAbortedError になる
    return BackupPair(
        name=name,
        source=str(tmp_path / f"{name}-missing-src"),
        destination=str(tmp_path / f"{name}-dst"),
    )


def _existing_pair(tmp_path: Path, name: str) -> BackupPair:
    source = tmp_path / f"{name}-src"
    destination = tmp_path / f"{name}-dst"
    source.mkdir()
    destination.mkdir()
    return BackupPair(name=name, source=str(source), destination=str(destination))


def _pairs_config(*pairs: BackupPair, error_behavior: ErrorBehavior) -> Config:
    return Config(
        minimum_free_space_gb=0,
        log_retention_days=90,
        error_behavior=error_behavior,
        backup_pairs=pairs,
    )


def _install_tools(fake_command: FakeCommand, tmp_path: Path, *, rsync_exit: int) -> Path:
    """容量チェックは通り rsync だけが rsync_exit で終わる偽物を置き、rsync の呼び出し記録を返す。

    記録があれば、手前のパス検証や容量チェックで落ちずに rsync の分岐まで届いたと言える。
    """
    calls = tmp_path / "rsync-calls"
    fake_command("du", "printf '%s\\t%s\\n' 1 /src")
    fake_command("df", "printf '%s\\n' 'fakefs 1000000 1 999999 1% /dst'")
    fake_command("rsync", f"printf '%s\\n' called >> '{calls}'\nexit {rsync_exit}")
    return calls


def _count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


def _run(config: Config, caplog: pytest.LogCaptureFixture) -> tuple[ExitCode, list[str]]:
    """run_backup を実行し、終了コードと開始したペア名の並びを返す。"""
    caplog.set_level(logging.INFO, logger=_LOGGER_NAME)
    exit_code = run_backup(config, dry_run=False, logger=logging.getLogger(_LOGGER_NAME))
    started = [
        match.group(1)
        for record in caplog.records
        if (match := _PAIR_STARTED.search(record.getMessage())) is not None
    ]
    return exit_code, started


class TestRunBackup:
    def test_counts_aborted_pairs_as_failures_and_continues(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        config = _pairs_config(
            _missing_pair(tmp_path, "p1"),
            _missing_pair(tmp_path, "p2"),
            error_behavior="continue",
        )

        exit_code, started = _run(config, caplog)

        assert started == ["p1", "p2"]
        assert exit_code == ExitCode.TOTAL_FAILURE

    def test_stop_skips_remaining_pairs_after_abort(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        config = _pairs_config(
            _missing_pair(tmp_path, "p1"),
            _missing_pair(tmp_path, "p2"),
            error_behavior="stop",
        )

        _, started = _run(config, caplog)

        assert started == ["p1"]

    def test_counts_rsync_failures_and_continues(
        self, fake_command: FakeCommand, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        rsync_calls = _install_tools(fake_command, tmp_path, rsync_exit=1)
        config = _pairs_config(
            _existing_pair(tmp_path, "p1"),
            _existing_pair(tmp_path, "p2"),
            error_behavior="continue",
        )

        exit_code, started = _run(config, caplog)

        assert started == ["p1", "p2"]
        assert _count_lines(rsync_calls) == 2
        assert exit_code == ExitCode.TOTAL_FAILURE

    def test_stop_skips_remaining_pairs_after_rsync_failure(
        self, fake_command: FakeCommand, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        rsync_calls = _install_tools(fake_command, tmp_path, rsync_exit=1)
        config = _pairs_config(
            _existing_pair(tmp_path, "p1"),
            _existing_pair(tmp_path, "p2"),
            error_behavior="stop",
        )

        _, started = _run(config, caplog)

        assert started == ["p1"]
        assert _count_lines(rsync_calls) == 1

    def test_rsync_code_23_is_not_a_failure_even_with_stop(
        self, fake_command: FakeCommand, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        rsync_calls = _install_tools(fake_command, tmp_path, rsync_exit=23)
        config = _pairs_config(
            _existing_pair(tmp_path, "p1"),
            _existing_pair(tmp_path, "p2"),
            error_behavior="stop",
        )

        exit_code, started = _run(config, caplog)

        assert started == ["p1", "p2"]
        assert _count_lines(rsync_calls) == 2
        assert exit_code == ExitCode.SUCCESS
