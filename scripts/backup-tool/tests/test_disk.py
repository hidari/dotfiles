"""disk モジュールのテスト。

measure_source_size_kb は偽の du を PATH に置き、measure_dest_total_kb は
disk モジュールの disk_usage を差し替えて、取得できない形と範囲外の値を None へ畳むことを確かめる。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from backup_tool.disk import (
    CapacityReport,
    measure_dest_total_kb,
    measure_source_size_kb,
    required_total_kb,
)

if TYPE_CHECKING:
    from tests.conftest import FakeCommand, FakeDiskUsage


class TestRequiredTotalKb:
    def test_adds_source_and_margin(self) -> None:
        # 1GB source + 100GB margin = 101 GB 相当の KB
        assert required_total_kb(source_size_kb=1024 * 1024, margin_gb=100) == (
            1024 * 1024 + 100 * 1024 * 1024
        )

    def test_zero_margin_returns_source_size(self) -> None:
        assert required_total_kb(source_size_kb=5000, margin_gb=0) == 5000

    def test_zero_source_returns_margin(self) -> None:
        assert required_total_kb(source_size_kb=0, margin_gb=50) == 50 * 1024 * 1024

    def test_rejects_negative_source_size(self) -> None:
        with pytest.raises(ValueError, match="source_size_kb"):
            required_total_kb(source_size_kb=-1, margin_gb=10)

    def test_rejects_negative_margin(self) -> None:
        with pytest.raises(ValueError, match="margin_gb"):
            required_total_kb(source_size_kb=100, margin_gb=-1)


class TestCapacityReport:
    def test_sufficient_when_dest_exceeds_required(self) -> None:
        report = CapacityReport(dest_total_kb=200, required_kb=100)
        assert report.is_sufficient is True
        assert report.shortage_kb == 0

    def test_sufficient_when_equal(self) -> None:
        report = CapacityReport(dest_total_kb=100, required_kb=100)
        assert report.is_sufficient is True
        assert report.shortage_kb == 0

    def test_insufficient_reports_shortage(self) -> None:
        report = CapacityReport(dest_total_kb=90, required_kb=100)
        assert report.is_sufficient is False
        assert report.shortage_kb == 10


class TestMeasureSourceSizeKb:
    def test_reads_size_from_du(self, fake_command: FakeCommand, tmp_path: Path) -> None:
        # 偽の du の出力を読めることの対照。下の None は偽の du の出力から来ている
        fake_command("du", "printf '%s\\t%s\\n' 2048 /Volumes/Source")
        assert measure_source_size_kb(tmp_path) == 2048

    def test_zero_from_du_is_a_valid_size(self, fake_command: FakeCommand, tmp_path: Path) -> None:
        # 空のディレクトリで du は0を返す。取得の失敗とは区別する
        fake_command("du", "printf '%s\\t%s\\n' 0 /Volumes/Source")
        assert measure_source_size_kb(tmp_path) == 0

    def test_none_when_du_size_is_negative(self, fake_command: FakeCommand, tmp_path: Path) -> None:
        fake_command("du", "printf '%s\\t%s\\n' -1 /Volumes/Source")
        assert measure_source_size_kb(tmp_path) is None

    @pytest.mark.usefixtures("empty_path")
    def test_raises_when_du_is_missing(self, tmp_path: Path) -> None:
        # du の不在は cli の事前検査が扱うので、ここでは None に畳まず呼び出し元へ渡す
        with pytest.raises(FileNotFoundError):
            measure_source_size_kb(tmp_path)

    def test_none_when_du_exits_nonzero(self, fake_command: FakeCommand, tmp_path: Path) -> None:
        # 出力が読める形でも、非0終了なら値を信用しない
        fake_command("du", "printf '%s\\t%s\\n' 2048 /Volumes/Source\nexit 1")
        assert measure_source_size_kb(tmp_path) is None

    def test_none_when_du_prints_nothing(self, fake_command: FakeCommand, tmp_path: Path) -> None:
        fake_command("du", "exit 0")
        assert measure_source_size_kb(tmp_path) is None

    def test_none_when_size_is_not_a_number(
        self, fake_command: FakeCommand, tmp_path: Path
    ) -> None:
        fake_command("du", "printf '%s\\t%s\\n' abc /Volumes/Source")
        assert measure_source_size_kb(tmp_path) is None


class TestMeasureDestTotalKb:
    def test_reads_total_of_the_queried_path_in_kb(
        self, fake_disk_usage: FakeDiskUsage, tmp_path: Path
    ) -> None:
        # 端数の1023バイトは切り捨てる
        queried = fake_disk_usage(4000 * 1024 + 1023)
        assert measure_dest_total_kb(tmp_path) == 4000
        assert queried == [tmp_path]

    @pytest.mark.parametrize(
        ("total_bytes", "expected"),
        [
            (0, None),
            # KB に切り捨てると0になるので、総容量としては不正
            (1023, None),
            (1024, 1),
        ],
    )
    def test_total_must_be_at_least_one_kb(
        self,
        fake_disk_usage: FakeDiskUsage,
        tmp_path: Path,
        total_bytes: int,
        expected: int | None,
    ) -> None:
        fake_disk_usage(total_bytes)
        assert measure_dest_total_kb(tmp_path) == expected

    def test_none_when_disk_usage_raises(
        self, fake_disk_usage: FakeDiskUsage, tmp_path: Path
    ) -> None:
        fake_disk_usage(None)
        assert measure_dest_total_kb(tmp_path) is None
