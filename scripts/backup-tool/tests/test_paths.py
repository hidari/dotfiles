"""paths モジュールの純粋関数に対するテスト。"""

from __future__ import annotations

from backup_tool.paths import classify, extract_volume_path


class TestClassify:
    def test_volume_root(self) -> None:
        assert classify("/Volumes/Luna-P") == "volume"

    def test_volume_with_trailing_slash(self) -> None:
        # ボリューム直下にスラッシュが付いていても volume 扱い
        assert classify("/Volumes/Luna-P/") == "volume"

    def test_directory_under_volume(self) -> None:
        assert classify("/Volumes/Luna-P/Photos") == "directory"

    def test_nested_directory_under_volume(self) -> None:
        assert classify("/Volumes/Luna-P/Photos/2024") == "directory"

    def test_local_path_outside_volumes(self) -> None:
        assert classify("/Users/example/Documents") == "local"

    def test_root_is_local(self) -> None:
        assert classify("/Volumes") == "local"


class TestExtractVolumePath:
    def test_extracts_volume_from_directory_path(self) -> None:
        assert extract_volume_path("/Volumes/Luna-P/Photos/2024") == "/Volumes/Luna-P"

    def test_returns_same_path_for_volume_root(self) -> None:
        assert extract_volume_path("/Volumes/Luna-P") == "/Volumes/Luna-P"

    def test_returns_none_for_non_volume_path(self) -> None:
        assert extract_volume_path("/Users/example/Documents") is None

    def test_returns_none_for_volumes_root(self) -> None:
        assert extract_volume_path("/Volumes") is None
