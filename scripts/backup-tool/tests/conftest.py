"""外部コマンド (du / rsync) の偽物を PATH に置くフィクスチャと、disk_usage の偽物。

subprocess などモジュールの属性を差し替えると同じモジュールの全員に効くので、
偽の実行ファイルを PATH の先頭へ置き、プロダクトコードには本物の起動経路を通らせる。
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

from backup_tool import disk

FakeCommand = Callable[[str, str], None]
FakeDiskUsage = Callable[[int | None], list[Path]]


@pytest.fixture
def fake_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeCommand:
    """name の偽コマンドを本文 body の sh スクリプトとして PATH の先頭に置く。

    shebang は絶対パスなので、本文が sh の組み込み (printf / exit) だけなら
    PATH の残りに依存しない。
    """
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    monkeypatch.setenv("PATH", str(bin_dir), prepend=os.pathsep)

    def install(name: str, body: str) -> None:
        command = bin_dir / name
        command.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
        command.chmod(0o755)

    return install


@pytest.fixture
def empty_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PATH を空のディレクトリだけにして、どの外部コマンドも見つからない状態を作る。"""
    empty_dir = tmp_path / "empty-bin"
    empty_dir.mkdir()
    monkeypatch.setenv("PATH", str(empty_dir))


def du_prints(size_kb: int) -> str:
    """size_kb を du -sk と同じ「サイズ<TAB>パス」の1行で出す偽の du の本文。"""
    return f"printf '%s\\t%s\\n' {size_kb} /src"


def rsync_calls_path(tmp_path: Path) -> Path:
    """install_rsync の偽の rsync が呼ばれるたびに1行足す記録ファイルのパス。"""
    return tmp_path / "rsync-calls"


def install_rsync(fake_command: FakeCommand, tmp_path: Path, *, rsync_exit: int = 0) -> Path:
    """rsync_exit で終わる偽の rsync を置き、rsync_calls_path の記録のパスを返す。

    記録があれば、手前のパス検証や容量チェックで落ちずに rsync の起動まで届いたと言える。
    """
    calls = rsync_calls_path(tmp_path)
    fake_command("rsync", f"printf '%s\\n' called >> '{calls}'\nexit {rsync_exit}")
    return calls


def count_lines(path: Path) -> int:
    return len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0


@pytest.fixture
def fake_disk_usage(monkeypatch: pytest.MonkeyPatch) -> FakeDiskUsage:
    """disk モジュールの disk_usage を総容量 total_bytes を返す偽物にする。

    問い合わせたパスの記録を返す。total_bytes が None なら OSError を送出する。
    """

    def install(total_bytes: int | None) -> list[Path]:
        queried: list[Path] = []

        def fake(path: Path) -> SimpleNamespace:
            queried.append(path)
            if total_bytes is None:
                raise OSError("fake disk_usage failure")
            return SimpleNamespace(total=total_bytes)

        monkeypatch.setattr(disk, "disk_usage", fake)
        return queried

    return install
