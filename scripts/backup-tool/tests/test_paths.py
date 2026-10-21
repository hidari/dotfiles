"""paths モジュールのテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from backup_tool.paths import classify, extract_volume_path, is_mounted


class TestClassify:
    def test_volume_root(self) -> None:
        assert classify("/Volumes/Primary") == "volume"

    def test_volume_with_trailing_slash(self) -> None:
        assert classify("/Volumes/Primary/") == "volume"

    def test_directory_under_volume(self) -> None:
        assert classify("/Volumes/Primary/Photos") == "directory"

    def test_nested_directory_under_volume(self) -> None:
        assert classify("/Volumes/Primary/Photos/2024") == "directory"

    def test_local_path_outside_volumes(self) -> None:
        assert classify("/Users/example/Documents") == "local"

    def test_root_is_local(self) -> None:
        assert classify("/Volumes") == "local"


class TestExtractVolumePath:
    def test_extracts_volume_from_directory_path(self) -> None:
        assert extract_volume_path("/Volumes/Primary/Photos/2024") == "/Volumes/Primary"

    def test_returns_same_path_for_volume_root(self) -> None:
        assert extract_volume_path("/Volumes/Primary") == "/Volumes/Primary"

    def test_returns_none_for_non_volume_path(self) -> None:
        assert extract_volume_path("/Users/example/Documents") is None

    def test_returns_none_for_volumes_root(self) -> None:
        assert extract_volume_path("/Volumes") is None


class TestIsMounted:
    # / はどのホストでも必ずマウントポイントなので、True の対照に使える
    @pytest.mark.usefixtures("empty_path")
    def test_root_is_mounted_without_any_external_command(self) -> None:
        assert is_mounted("/") is True

    def test_plain_directory_is_not_mounted(self, tmp_path: Path) -> None:
        assert is_mounted(str(tmp_path)) is False

    def test_symlink_to_root_is_not_mounted(self, tmp_path: Path) -> None:
        link = tmp_path / "link-to-root"
        link.symlink_to("/")
        assert is_mounted(str(link)) is False

    def test_missing_path_is_not_mounted(self, tmp_path: Path) -> None:
        assert is_mounted(str(tmp_path / "missing")) is False
