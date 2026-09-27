"""rsync モジュールのテスト。

build_options / is_suppressible_error / summarize_filtered_errors を検証し、
run() は偽の rsync を PATH に置いて失敗の返し方を確かめる。
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from backup_tool.rsync import (
    build_options,
    is_suppressible_error,
    run,
    summarize_filtered_errors,
)

if TYPE_CHECKING:
    from tests.conftest import FakeCommand


class TestBuildOptions:
    def test_core_flags(self) -> None:
        options = build_options(excludes=(), dry_run=False)
        assert "-avh" in options
        assert "--delete-before" in options
        assert "--progress" in options
        assert "--stats" in options
        assert "--dry-run" not in options

    def test_does_not_include_delete_excluded(self) -> None:
        options = build_options(excludes=(".DS_Store",), dry_run=False)
        assert "--delete-excluded" not in options

    def test_dry_run_appends_flag(self) -> None:
        options = build_options(excludes=(), dry_run=True)
        assert "--dry-run" in options

    def test_expands_exclude_patterns(self) -> None:
        options = build_options(excludes=(".DS_Store", "node_modules"), dry_run=False)
        assert "--exclude=.DS_Store" in options
        assert "--exclude=node_modules" in options

    def test_preserves_exclude_order(self) -> None:
        options = build_options(excludes=("a", "b", "c"), dry_run=False)
        exclude_positions = [options.index(f"--exclude={x}") for x in ("a", "b", "c")]
        assert exclude_positions == sorted(exclude_positions)


class TestIsSuppressibleError:
    def test_suppresses_trashes_operation_not_permitted(self) -> None:
        line = (
            'rsync: [sender] readdir("/Volumes/Src/.Trashes") failed: Operation not permitted (1)'
        )
        assert is_suppressible_error(line) is True

    def test_suppresses_spotlight_operation_not_permitted(self) -> None:
        line = "delete_file: rmdir(.Spotlight-V100) failed: Operation not permitted (1)"
        assert is_suppressible_error(line) is True

    def test_suppresses_fseventsd(self) -> None:
        line = "delete_file: unlink(.fseventsd/no_log) failed: Operation not permitted (1)"
        assert is_suppressible_error(line) is True

    def test_suppresses_temporary_items(self) -> None:
        line = 'rsync: readdir("/.TemporaryItems") failed: Operation not permitted (1)'
        assert is_suppressible_error(line) is True

    def test_suppresses_io_error_skipping_deletion(self) -> None:
        assert is_suppressible_error("IO error encountered -- skipping file deletion") is True

    def test_suppresses_code_23(self) -> None:
        line = "rsync error: some files/attrs were not transferred (see previous errors) (code 23)"
        assert is_suppressible_error(line) is True

    def test_does_not_suppress_regular_error(self) -> None:
        assert is_suppressible_error("rsync: connection unexpectedly closed") is False

    def test_does_not_suppress_empty_line(self) -> None:
        assert is_suppressible_error("") is False


class TestSummarizeFilteredErrors:
    def test_counts_each_pattern(self) -> None:
        lines = [
            'rsync: readdir("/Volumes/X/.Trashes") failed: Operation not permitted',
            "delete_file: rmdir(.Spotlight-V100) failed: Operation not permitted",
            "delete_file: unlink(.Spotlight-V100/foo) failed: Operation not permitted",
            "delete_file: unlink(.fseventsd/bar) failed: Operation not permitted",
        ]
        summary = summarize_filtered_errors(lines)
        assert summary == {
            ".Trashes": 1,
            ".Spotlight-V100": 2,
            ".fseventsd": 1,
        }

    def test_returns_empty_dict_when_no_matches(self) -> None:
        assert summarize_filtered_errors([]) == {}


class TestRun:
    def test_propagates_nonzero_exit_code_with_stderr_lines(
        self, fake_command: FakeCommand, tmp_path: Path
    ) -> None:
        # 失敗の理由は stderr に出るので、stdout と同じ経路で上位へ渡ることまで確かめる
        fake_command(
            "rsync",
            "printf '%s\\n' 'sending incremental file list'\n"
            "printf '%s\\n' 'rsync: connection unexpectedly closed' >&2\n"
            "exit 12",
        )
        lines: list[str] = []

        result = run(
            source=tmp_path / "src",
            destination=tmp_path / "dst",
            options=[],
            on_output=lines.append,
        )

        assert result.exit_code == 12
        assert result.filtered_errors == ()
        assert lines == [
            "sending incremental file list",
            "rsync: connection unexpectedly closed",
        ]

    @pytest.mark.usefixtures("empty_path")
    def test_raises_when_rsync_is_missing(self, tmp_path: Path) -> None:
        # rsync が無いことは終了コードに畳まず、FileNotFoundError として呼び出し元へ渡す
        lines: list[str] = []
        with pytest.raises(FileNotFoundError):
            run(
                source=tmp_path / "src",
                destination=tmp_path / "dst",
                options=[],
                on_output=lines.append,
            )
        assert lines == []
