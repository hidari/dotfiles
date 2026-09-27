"""paths モジュールのテスト。

is_mounted は偽の mount を PATH に置いて、mount の失敗を False へ畳むことを確かめる。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from backup_tool.paths import classify, extract_volume_path, is_mounted

if TYPE_CHECKING:
    from tests.conftest import FakeCommand

# どの検査も、偽の mount が効いていなければ落ちる形にする。
# True を期待する検査は、本物の mount には載らないボリューム名を問う。
# False を期待する検査は、本物の mount なら必ず載る / を問う。
_FAKE_VOLUME = "/Volumes/BackupToolFakeVolume"
_FAKE_MOUNT_LINE = f"/dev/disk99s1 on {_FAKE_VOLUME} (apfs, local, journaled)"
_ROOT_MOUNT_LINE = "/dev/disk99s1 on / (apfs, local, journaled)"


class TestClassify:
    def test_volume_root(self) -> None:
        assert classify("/Volumes/Primary") == "volume"

    def test_volume_with_trailing_slash(self) -> None:
        # ボリューム直下にスラッシュが付いていても volume 扱い
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
    def test_true_when_mount_lists_the_path(self, fake_command: FakeCommand) -> None:
        fake_command("mount", f"printf '%s\\n' '{_FAKE_MOUNT_LINE}'")
        assert is_mounted(_FAKE_VOLUME) is True

    @pytest.mark.usefixtures("empty_path")
    def test_false_when_mount_command_is_missing(self) -> None:
        assert is_mounted("/") is False

    def test_false_when_mount_exits_nonzero(self, fake_command: FakeCommand) -> None:
        # 出力には対象の行があっても、非0終了なら出力を信用しない
        fake_command("mount", f"printf '%s\\n' '{_ROOT_MOUNT_LINE}'\nexit 1")
        assert is_mounted("/") is False
