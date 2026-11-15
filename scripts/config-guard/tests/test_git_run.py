"""git_run.isolated_git_env の仕様テスト。"""

from __future__ import annotations

import importlib.util
from typing import Any

import pytest

from config_guard import git_run
from config_guard.git_run import isolated_git_env
from tests.conftest import REPO_ROOT

# フックは zero-dep standalone (venv 外の system python 起動) で config_guard を import できず、
# 同じ GIT_* 隔離ロジックを独立コピーで持つ (共有不能な設計境界)。両者の除外集合が silent に
# drift すると片方の GIT_* leak が残るため import 照合で pin する。
# フック側の canonical は hook_git で、フック群はそこを共有する。
_HOOK_PATH = REPO_ROOT / "home" / ".claude" / "hooks" / "hook_git.py"


# knowledge-ledger も依存を持たない別パッケージで、同じ集合を独立コピーで持つ
_LEDGER_DELTA_PATH = (
    REPO_ROOT / "scripts" / "knowledge-ledger" / "src" / "knowledge_ledger" / "delta.py"
)


def _load_module(name: str, path: Any) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_hook_module() -> Any:
    return _load_module("hook_git_under_test", _HOOK_PATH)


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
    # フック側の独立コピーが config-guard と同じ GIT_* 除外集合であることを pin する。
    # 片方に GIT_* を足し忘れると leak が silent に残るため、この import 照合が赤で検出する。
    hook = _load_hook_module()
    assert hook.LOCATION_VARS == git_run._GIT_LOCATION_VARS


def test_knowledge_ledger_location_vars_match_config_guard() -> None:
    delta = _load_module("knowledge_ledger_delta_under_test", _LEDGER_DELTA_PATH)
    assert delta._GIT_LOCATION_VARS == git_run._GIT_LOCATION_VARS
