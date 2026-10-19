"""runner モジュールのテスト。

終了コード集約と excludes 合成を純粋関数として検証し、run_backup は
実在しないディレクトリ、偽の du / rsync と差し替えた disk_usage で失敗経路を通す。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from backup_tool import disk, runner
from backup_tool.config import BackupPair, Config, ErrorBehavior
from backup_tool.runner import (
    BackupAbortedError,
    ExitCode,
    _build_excludes,
    _determine_exit_code,
    _verify_path,
    run_backup,
)

if TYPE_CHECKING:
    from tests.conftest import FakeCommand

_LOGGER_NAME = "tests.runner"
_PAIR_STARTED = re.compile(r"\[(.+)\] バックアップ開始")
_GB_IN_KB = 1024 * 1024


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


def _pairs_config(
    *pairs: BackupPair, error_behavior: ErrorBehavior, minimum_free_space_gb: int = 0
) -> Config:
    return Config(
        minimum_free_space_gb=minimum_free_space_gb,
        log_retention_days=90,
        error_behavior=error_behavior,
        backup_pairs=pairs,
    )


def _install_du(fake_command: FakeCommand, *, body: str) -> None:
    fake_command("du", body)


def _du_prints(size_kb: int) -> str:
    return f"printf '%s\\t%s\\n' {size_kb} /src"


def _set_dest_total(monkeypatch: pytest.MonkeyPatch, *, total_kb: int | None) -> None:
    """宛先の総容量を total_kb にする。None なら disk_usage が OSError を送出する。"""

    def fake(path: Path) -> SimpleNamespace:
        if total_kb is None:
            raise OSError("fake disk_usage failure")
        return SimpleNamespace(total=total_kb * 1024, used=0, free=total_kb * 1024)

    monkeypatch.setattr(disk, "disk_usage", fake)


def _install_rsync(fake_command: FakeCommand, tmp_path: Path, *, rsync_exit: int) -> Path:
    """rsync_exit で終わる偽の rsync を置き、呼び出し記録のパスを返す。

    記録があれば、手前のパス検証や容量チェックで落ちずに rsync の分岐まで届いたと言える。
    """
    calls = tmp_path / "rsync-calls"
    fake_command("rsync", f"printf '%s\\n' called >> '{calls}'\nexit {rsync_exit}")
    return calls


def _install_tools(
    fake_command: FakeCommand,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    rsync_exit: int,
) -> Path:
    """容量チェックは通り rsync だけが rsync_exit で終わる状態を作り、呼び出し記録を返す。"""
    _install_du(fake_command, body=_du_prints(1))
    _set_dest_total(monkeypatch, total_kb=1000000)
    return _install_rsync(fake_command, tmp_path, rsync_exit=rsync_exit)


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
        self,
        fake_command: FakeCommand,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        rsync_calls = _install_tools(fake_command, monkeypatch, tmp_path, rsync_exit=1)
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
        self,
        fake_command: FakeCommand,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        rsync_calls = _install_tools(fake_command, monkeypatch, tmp_path, rsync_exit=1)
        config = _pairs_config(
            _existing_pair(tmp_path, "p1"),
            _existing_pair(tmp_path, "p2"),
            error_behavior="stop",
        )

        _, started = _run(config, caplog)

        assert started == ["p1"]
        assert _count_lines(rsync_calls) == 1

    def test_rsync_code_23_is_not_a_failure_even_with_stop(
        self,
        fake_command: FakeCommand,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        rsync_calls = _install_tools(fake_command, monkeypatch, tmp_path, rsync_exit=23)
        config = _pairs_config(
            _existing_pair(tmp_path, "p1"),
            _existing_pair(tmp_path, "p2"),
            error_behavior="stop",
        )

        exit_code, started = _run(config, caplog)

        assert started == ["p1", "p2"]
        assert _count_lines(rsync_calls) == 2
        assert exit_code == ExitCode.SUCCESS


class TestCapacityCheck:
    @pytest.mark.parametrize(
        ("source_kb", "dest_total_kb", "expected_calls", "expected_exit"),
        [
            # 空のソース (du の0) でも、マージンちょうどの宛先なら進む
            pytest.param(0, _GB_IN_KB, 1, ExitCode.SUCCESS, id="empty-source-fits"),
            # 空のソースでも、マージンに届かない宛先なら中断する
            pytest.param(0, 10, 0, ExitCode.TOTAL_FAILURE, id="empty-source-too-small"),
            # ソースの使用量も必要容量に入る (1KB + マージンが総容量を1KB超える)
            pytest.param(1, _GB_IN_KB, 0, ExitCode.TOTAL_FAILURE, id="source-counts"),
        ],
    )
    def test_compares_source_plus_margin_with_dest_total(
        self,
        fake_command: FakeCommand,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        source_kb: int,
        dest_total_kb: int,
        expected_calls: int,
        expected_exit: ExitCode,
    ) -> None:
        _install_du(fake_command, body=_du_prints(source_kb))
        _set_dest_total(monkeypatch, total_kb=dest_total_kb)
        rsync_calls = _install_rsync(fake_command, tmp_path, rsync_exit=0)
        config = _pairs_config(
            _existing_pair(tmp_path, "p1"), error_behavior="continue", minimum_free_space_gb=1
        )

        exit_code, _ = _run(config, caplog)

        assert _count_lines(rsync_calls) == expected_calls
        assert exit_code == expected_exit

    # どの場合も、容量を比べれば中断する組み合わせにしておき、
    # rsync まで届いたことを「比べずに飛ばした」証拠にする
    @pytest.mark.parametrize(
        ("du_body", "dest_total_kb"),
        [
            pytest.param(f"{_du_prints(1)}\nexit 1", 10, id="du-fails"),
            pytest.param(_du_prints(1), None, id="disk-usage-raises"),
            pytest.param(_du_prints(1), 0, id="dest-total-zero"),
        ],
    )
    def test_skips_check_and_runs_rsync_when_a_size_is_unavailable(
        self,
        fake_command: FakeCommand,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        du_body: str,
        dest_total_kb: int | None,
    ) -> None:
        _install_du(fake_command, body=du_body)
        _set_dest_total(monkeypatch, total_kb=dest_total_kb)
        rsync_calls = _install_rsync(fake_command, tmp_path, rsync_exit=0)
        config = _pairs_config(
            _existing_pair(tmp_path, "p1"), error_behavior="continue", minimum_free_space_gb=1
        )

        exit_code, _ = _run(config, caplog)

        assert _count_lines(rsync_calls) == 1
        assert exit_code == ExitCode.SUCCESS


class TestVerifyPathMount:
    @pytest.mark.parametrize(
        "path",
        ["/Volumes/BackupToolFake", "/Volumes/BackupToolFake/sub"],
    )
    def test_aborts_when_the_volume_is_not_mounted(
        self, monkeypatch: pytest.MonkeyPatch, path: str
    ) -> None:
        queried: list[str] = []

        def fake_is_mounted(mount_point: str) -> bool:
            queried.append(mount_point)
            return False

        monkeypatch.setattr(runner, "is_mounted", fake_is_mounted)

        with pytest.raises(BackupAbortedError, match="マウントされていません"):
            _verify_path(Path(path), role="ソース", mode="read")
        assert queried == ["/Volumes/BackupToolFake"]
