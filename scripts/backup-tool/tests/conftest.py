"""外部コマンド (mount / du / df / rsync) の偽物を PATH に置くフィクスチャ。

subprocess などモジュールの属性を差し替えると同じモジュールの全員に効くので、
偽の実行ファイルを PATH の先頭へ置き、プロダクトコードには本物の起動経路を通らせる。
"""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path

import pytest

FakeCommand = Callable[[str, str], None]


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
