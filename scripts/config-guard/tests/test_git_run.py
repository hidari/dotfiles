"""git_run.isolated_git_env の仕様テスト。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

import pytest

from config_guard import git_run
from config_guard.git_run import isolated_git_env

# handoff-sentinel hook は zero-dep standalone (venv 外の system python 起動) で config_guard を
# import できず同じ GIT_* 隔離ロジックを独立コピーで持つ (共有不能な設計境界)。両者の除外集合が
# silent に drift すると片方の GIT_* leak が残るため import 照合で pin する。
_HOOK_PATH = (
    Path(__file__).resolve().parents[3] / "home" / ".claude" / "hooks" / "handoff-sentinel.py"
)


def _load_hook_module() -> Any:
    spec = importlib.util.spec_from_file_location("handoff_sentinel_under_test", _HOOK_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_hook_git_location_vars_match_config_guard() -> None:
    # handoff-sentinel hook の独立コピーが config-guard と同じ GIT_* 除外集合であることを pin する。
    # 片方に GIT_* を足し忘れると leak が silent に残るため、この import 照合が赤で検出する。
    hook = _load_hook_module()
    assert hook._GIT_LOCATION_VARS == git_run._GIT_LOCATION_VARS
