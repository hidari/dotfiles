"""disk モジュールの純粋関数に対するテスト。

実際に du / df を呼ぶ副作用レイヤーは結合レベルで検証する。
"""

from __future__ import annotations

import pytest

from backup_tool.disk import check_capacity, required_total_kb


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
