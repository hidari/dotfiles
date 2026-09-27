"""disk モジュールのテスト。

du / df を呼ぶ測定関数は偽の du / df を PATH に置いて、取得に失敗した形を
すべて None へ畳むことを確かめる。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from backup_tool.disk import (
    check_capacity,
    measure_dest_total_kb,
    measure_source_size_kb,
    required_total_kb,
)

if TYPE_CHECKING:
    from tests.conftest import FakeCommand

_DF_HEADER = "Filesystem 1024-blocks Used Available Capacity Mounted on"


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


class TestCheckCapacity:
    def test_sufficient_when_dest_exceeds_required(self) -> None:
        report = check_capacity(dest_total_kb=200, required_kb=100)
        assert report.is_sufficient is True
        assert report.shortage_kb == 0

    def test_sufficient_when_equal(self) -> None:
        report = check_capacity(dest_total_kb=100, required_kb=100)
        assert report.dest_total_kb == 100
        assert report.required_kb == 100
        assert report.is_sufficient is True
        assert report.shortage_kb == 0

    def test_insufficient_reports_shortage(self) -> None:
        report = check_capacity(dest_total_kb=90, required_kb=100)
        assert report.is_sufficient is False
        assert report.shortage_kb == 10


# du の出力は1行目の先頭が必ず非空白なので、欄が足りない分岐は du からは到達しない。
# その分岐は欄1を読む df の側で確かめる。
class TestMeasureSourceSizeKb:
    def test_reads_size_from_du(self, fake_command: FakeCommand, tmp_path: Path) -> None:
        # 偽の du の出力を読めることの対照。下の None は偽の du の出力から来ている
        fake_command("du", "printf '%s\\t%s\\n' 2048 /Volumes/Source")
        assert measure_source_size_kb(tmp_path) == 2048

    @pytest.mark.usefixtures("empty_path")
    def test_none_when_du_is_missing(self, tmp_path: Path) -> None:
        # 本物の du が見つかれば正の値になるよう中身を置く (空のディレクトリは0で None に紛れる)
        (tmp_path / "data").write_bytes(b"x" * 65536)
        assert measure_source_size_kb(tmp_path) is None

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

    def test_none_when_size_is_zero(self, fake_command: FakeCommand, tmp_path: Path) -> None:
        fake_command("du", "printf '%s\\t%s\\n' 0 /Volumes/Source")
        assert measure_source_size_kb(tmp_path) is None


class TestMeasureDestTotalKb:
    def test_reads_total_from_last_line_of_df(
        self, fake_command: FakeCommand, tmp_path: Path
    ) -> None:
        # 下の None の対照。見出し行を飛ばして最終行の欄1 (総容量) を読む
        fake_command(
            "df", f"printf '%s\\n' '{_DF_HEADER}' 'fakefs 4000 1000 3000 25% /Volumes/Dest'"
        )
        assert measure_dest_total_kb(tmp_path) == 4000

    @pytest.mark.usefixtures("empty_path")
    def test_none_when_df_is_missing(self, tmp_path: Path) -> None:
        assert measure_dest_total_kb(tmp_path) is None

    def test_none_when_df_exits_nonzero(self, fake_command: FakeCommand, tmp_path: Path) -> None:
        fake_command(
            "df",
            f"printf '%s\\n' '{_DF_HEADER}' 'fakefs 4000 1000 3000 25% /Volumes/Dest'\nexit 1",
        )
        assert measure_dest_total_kb(tmp_path) is None

    def test_none_when_df_prints_nothing(self, fake_command: FakeCommand, tmp_path: Path) -> None:
        fake_command("df", "exit 0")
        assert measure_dest_total_kb(tmp_path) is None

    def test_none_when_last_line_lacks_total_field(
        self, fake_command: FakeCommand, tmp_path: Path
    ) -> None:
        fake_command("df", f"printf '%s\\n' '{_DF_HEADER}' fakefs")
        assert measure_dest_total_kb(tmp_path) is None

    def test_none_when_total_is_not_a_number(
        self, fake_command: FakeCommand, tmp_path: Path
    ) -> None:
        fake_command(
            "df", f"printf '%s\\n' '{_DF_HEADER}' 'fakefs abc 1000 3000 25% /Volumes/Dest'"
        )
        assert measure_dest_total_kb(tmp_path) is None

    def test_none_when_total_is_zero(self, fake_command: FakeCommand, tmp_path: Path) -> None:
        fake_command("df", f"printf '%s\\n' '{_DF_HEADER}' 'fakefs 0 0 0 0% /Volumes/Dest'")
        assert measure_dest_total_kb(tmp_path) is None
