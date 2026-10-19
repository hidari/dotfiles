"""runner モジュールのテスト。

終了コード集約・サマリー・excludes 合成を純粋関数として検証し、ペアごとの結果の列は
実在しないディレクトリ、偽の du / rsync と差し替えた disk_usage で失敗経路を通して検証する。
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from backup_tool import disk, runner
from backup_tool.config import BackupPair, Config, ErrorBehavior
from backup_tool.runner import (
    BackupAbortedError,
    ExitCode,
    PairStatus,
    _build_excludes,
    _determine_exit_code,
    _log_summary,
    _run_pairs,
    _verify_path,
    run_backup,
)

if TYPE_CHECKING:
    from tests.conftest import FakeCommand

_LOGGER_NAME = "tests.runner"
_SUMMARY_ROW = re.compile(r"^(成功|部分的成功|失敗|未実行):\s+(\d+) / (\d+)$")
_STOP_MESSAGE = "error_behavior=stop のため処理を中断します"
_GB_IN_KB = 1024 * 1024

S, P, F, A, K = (
    PairStatus.SUCCESS,
    PairStatus.PARTIAL,
    PairStatus.FAILED,
    PairStatus.ABORTED,
    PairStatus.SKIPPED,
)


def _make_config(*, additional: tuple[str, ...] = ()) -> Config:
    return Config(
        minimum_free_space_gb=100,
        log_retention_days=90,
        additional_excludes=additional,
        backup_pairs=(BackupPair(name="p", source="/Volumes/A", destination="/Volumes/B"),),
    )


class TestDetermineExitCode:
    # 完了 (成功か部分的成功) の数だけで決まる: 全ペア完了で 0、完了0件で 3、それ以外は 2
    @pytest.mark.parametrize(
        ("statuses", "expected"),
        [
            pytest.param([S, S], ExitCode.SUCCESS, id="all-success"),
            pytest.param([P, P], ExitCode.SUCCESS, id="partial-success-counts-as-completed"),
            pytest.param([S, F], ExitCode.PARTIAL_FAILURE, id="success-and-failure"),
            pytest.param([P, A, K], ExitCode.PARTIAL_FAILURE, id="partial-then-stop"),
            pytest.param([S, A, K], ExitCode.PARTIAL_FAILURE, id="success-then-stop"),
            pytest.param([A, K], ExitCode.TOTAL_FAILURE, id="stop-at-first-abort"),
            pytest.param([F, K], ExitCode.TOTAL_FAILURE, id="stop-at-first-failure"),
            pytest.param([F, F], ExitCode.TOTAL_FAILURE, id="all-failed"),
            pytest.param([A], ExitCode.TOTAL_FAILURE, id="single-abort"),
            # 以下は到達しない入力。成功に倒れないことを pin する
            pytest.param([K], ExitCode.TOTAL_FAILURE, id="only-skipped"),
            pytest.param([], ExitCode.TOTAL_FAILURE, id="empty"),
        ],
    )
    def test_decision_table(self, statuses: list[PairStatus], expected: ExitCode) -> None:
        assert _determine_exit_code(statuses) == expected


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


def _run(config: Config) -> ExitCode:
    return run_backup(config, dry_run=False, logger=logging.getLogger(_LOGGER_NAME))


def _statuses(config: Config) -> list[tuple[str, PairStatus]]:
    outcomes = _run_pairs(config, dry_run=False, logger=logging.getLogger(_LOGGER_NAME))
    return [(outcome.name, outcome.status) for outcome in outcomes]


def _summary_rows(caplog: pytest.LogCaptureFixture) -> dict[str, tuple[int, int]]:
    """サマリーの各行を 見出し -> (件数, total) で返す。"""
    return {
        match.group(1): (int(match.group(2)), int(match.group(3)))
        for message in caplog.messages
        if (match := _SUMMARY_ROW.match(message)) is not None
    }


PairFactory = Callable[[Path, str], BackupPair]


class TestRunPairs:
    # 中断は _missing_pair がパス検証で起こし、失敗と部分的成功は rsync の終了コードで起こす。
    # rsync の呼び出し回数は、手前で落ちずに rsync の分岐まで届いた独立の証拠
    @pytest.mark.parametrize(
        ("error_behavior", "make_pair", "rsync_exit", "expected", "rsync_count", "stops"),
        [
            pytest.param("continue", _missing_pair, 0, [A, A], 0, False, id="continue-abort"),
            pytest.param("stop", _missing_pair, 0, [A, K], 0, True, id="stop-abort"),
            pytest.param("continue", _existing_pair, 1, [F, F], 2, False, id="continue-rsync-fail"),
            pytest.param("stop", _existing_pair, 1, [F, K], 1, True, id="stop-rsync-fail"),
            pytest.param("continue", _existing_pair, 23, [P, P], 2, False, id="continue-code-23"),
            # code 23 は失敗に数えないので stop でも止まらない
            pytest.param("stop", _existing_pair, 23, [P, P], 2, False, id="stop-code-23"),
        ],
    )
    def test_two_pairs(
        self,
        fake_command: FakeCommand,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
        error_behavior: ErrorBehavior,
        make_pair: PairFactory,
        rsync_exit: int,
        expected: list[PairStatus],
        rsync_count: int,
        stops: bool,
    ) -> None:
        caplog.set_level(logging.INFO, logger=_LOGGER_NAME)
        rsync_calls = _install_tools(fake_command, monkeypatch, tmp_path, rsync_exit=rsync_exit)
        config = _pairs_config(
            make_pair(tmp_path, "p1"), make_pair(tmp_path, "p2"), error_behavior=error_behavior
        )

        assert _statuses(config) == list(zip(["p1", "p2"], expected, strict=True))
        assert _count_lines(rsync_calls) == rsync_count
        assert (_STOP_MESSAGE in caplog.messages) is stops

    def test_stop_after_success_then_abort_skips_the_rest(
        self,
        fake_command: FakeCommand,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
    ) -> None:
        rsync_calls = _install_tools(fake_command, monkeypatch, tmp_path, rsync_exit=0)
        config = _pairs_config(
            _existing_pair(tmp_path, "p1"),
            _missing_pair(tmp_path, "p2"),
            _existing_pair(tmp_path, "p3"),
            error_behavior="stop",
        )

        assert _statuses(config) == [("p1", S), ("p2", A), ("p3", K)]
        assert _count_lines(rsync_calls) == 1


class TestRunBackup:
    def test_stop_at_first_abort_is_total_failure_and_summary_adds_up(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO, logger=_LOGGER_NAME)
        config = _pairs_config(
            _missing_pair(tmp_path, "p1"),
            _missing_pair(tmp_path, "p2"),
            _missing_pair(tmp_path, "p3"),
            error_behavior="stop",
        )

        exit_code = _run(config)

        assert _summary_rows(caplog) == {
            "成功": (0, 3),
            "部分的成功": (0, 3),
            "失敗": (1, 3),
            "未実行": (2, 3),
        }
        assert exit_code == ExitCode.TOTAL_FAILURE


class TestLogSummary:
    def test_rows_add_up_to_total_with_abort_counted_as_failure(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO, logger=_LOGGER_NAME)

        _log_summary(logging.getLogger(_LOGGER_NAME), [S, P, F, A, K, K])

        rows = _summary_rows(caplog)
        assert rows == {"成功": (1, 6), "部分的成功": (1, 6), "失敗": (2, 6), "未実行": (2, 6)}
        assert sum(count for count, _ in rows.values()) == 6


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

        exit_code = _run(config)

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
        du_body: str,
        dest_total_kb: int | None,
    ) -> None:
        _install_du(fake_command, body=du_body)
        _set_dest_total(monkeypatch, total_kb=dest_total_kb)
        rsync_calls = _install_rsync(fake_command, tmp_path, rsync_exit=0)
        config = _pairs_config(
            _existing_pair(tmp_path, "p1"), error_behavior="continue", minimum_free_space_gb=1
        )

        exit_code = _run(config)

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


def _abort_lines(caplog: pytest.LogCaptureFixture, marker: str) -> list[str]:
    """marker を含む ERROR 行だけを返す。中断以外の ERROR 行の増減に左右されないよう絞る。"""
    return [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.ERROR and marker in record.getMessage()
    ]


class TestAbortLogPrefix:
    # ペア名は中断をログへ出す側だけが付けるので、どの中断の行にもちょうど1回だけ現れる
    def test_source_missing_logs_pair_name_once(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO, logger=_LOGGER_NAME)
        pair = _missing_pair(tmp_path, "p1")

        _run(_pairs_config(pair, error_behavior="continue"))

        assert _abort_lines(caplog, pair.source) == [
            f"[p1] ソースのディレクトリが存在しません: {pair.source}"
        ]

    def test_destination_missing_logs_pair_name_once(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        caplog.set_level(logging.INFO, logger=_LOGGER_NAME)
        source = tmp_path / "p1-src"
        source.mkdir()
        pair = BackupPair(name="p1", source=str(source), destination=str(tmp_path / "p1-dst"))

        _run(_pairs_config(pair, error_behavior="continue"))

        assert _abort_lines(caplog, pair.destination) == [
            f"[p1] デスティネーションのディレクトリが存在しません: {pair.destination}"
        ]

    def test_capacity_shortage_logs_pair_name_once(
        self,
        fake_command: FakeCommand,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        caplog.set_level(logging.INFO, logger=_LOGGER_NAME)
        _install_du(fake_command, body=_du_prints(1))
        _set_dest_total(monkeypatch, total_kb=10)
        _install_rsync(fake_command, tmp_path, rsync_exit=0)
        config = _pairs_config(
            _existing_pair(tmp_path, "p1"), error_behavior="continue", minimum_free_space_gb=1
        )

        _run(config)

        # 不足量の文面は format_gb に任せるので、前方一致と出現回数で縛る
        lines = _abort_lines(caplog, "総容量が不足しています")
        assert len(lines) == 1
        assert lines[0].startswith("[p1] バックアップ先の総容量が不足しています (不足 ")
        assert lines[0].count("[p1]") == 1


class TestVerifyPathMessage:
    # role の直後に助詞が続き、ペア名などの接頭辞を持たないことを全分岐で見る
    @pytest.mark.parametrize(
        ("path", "mode", "mounted", "readable", "writable"),
        [
            pytest.param("/Volumes/BackupToolFake", "read", False, True, True, id="volume"),
            pytest.param(
                "/Volumes/BackupToolFake/sub", "read", False, True, True, id="parent-volume"
            ),
            pytest.param(
                "/Volumes/BackupToolFake/sub", "read", True, True, True, id="volume-subdir-missing"
            ),
            pytest.param("<missing>", "read", True, True, True, id="directory-missing"),
            pytest.param("<existing>", "read", True, False, True, id="unreadable"),
            pytest.param("<existing>", "write", True, True, False, id="unwritable"),
        ],
    )
    def test_message_starts_with_role(
        self,
        monkeypatch: pytest.MonkeyPatch,
        tmp_path: Path,
        path: str,
        mode: runner.PathMode,
        mounted: bool,
        readable: bool,
        writable: bool,
    ) -> None:
        monkeypatch.setattr(runner, "is_mounted", lambda _: mounted)
        monkeypatch.setattr(runner, "ensure_readable", lambda _: readable)
        monkeypatch.setattr(runner, "ensure_writable", lambda _: writable)
        targets = {"<missing>": tmp_path / "missing", "<existing>": tmp_path}
        target = targets.get(path, Path(path))

        with pytest.raises(BackupAbortedError) as excinfo:
            _verify_path(target, role="ロール", mode=mode)

        message = str(excinfo.value)
        assert re.match(r"ロール[のに]\S", message)
        assert "[" not in message
