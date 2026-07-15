"""git_run.isolated_git_env の仕様テスト。"""

from __future__ import annotations

import pytest

from config_guard.git_run import isolated_git_env


def test_strips_git_location_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GIT_DIR", "/x/.git")
    monkeypatch.setenv("GIT_WORK_TREE", "/x")
    monkeypatch.setenv("GIT_INDEX_FILE", "/x/.git/index")
    env = isolated_git_env()
    assert "GIT_DIR" not in env
    assert "GIT_WORK_TREE" not in env
    assert "GIT_INDEX_FILE" not in env


def test_keeps_non_location_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    # ロケーション系でない変数(PATH や git の author 設定)は保持する
    monkeypatch.setenv("PATH", "/custom/bin")
    monkeypatch.setenv("GIT_AUTHOR_NAME", "someone")
    env = isolated_git_env()
    assert env["PATH"] == "/custom/bin"
    assert env["GIT_AUTHOR_NAME"] == "someone"
