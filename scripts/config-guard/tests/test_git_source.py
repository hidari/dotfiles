"""git_source の仕様テスト。working tree を読まないことを実 git リポで検証する。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from config_guard.git_source import SETTINGS_PATH, read_committed_settings
from tests.conftest import init_repo, run_git, write_file


def _write_settings(repo: Path, payload: dict[str, object]) -> None:
    write_file(repo, SETTINGS_PATH, json.dumps(payload))


def test_prefers_staged_over_head_and_ignores_working(tmp_path: Path) -> None:
    init_repo(tmp_path)
    # HEAD には head 版を commit
    _write_settings(tmp_path, {"marker": "head"})
    run_git(tmp_path, "add", SETTINGS_PATH)
    run_git(tmp_path, "commit", "-q", "-m", "head")
    # index には staged 版を stage
    _write_settings(tmp_path, {"marker": "staged"})
    run_git(tmp_path, "add", SETTINGS_PATH)
    # working tree には working 版（stage しない）
    _write_settings(tmp_path, {"marker": "working"})

    result = read_committed_settings(str(tmp_path))
    assert result == {"marker": "staged"}


def test_returns_committed_content_when_only_working_differs(tmp_path: Path) -> None:
    init_repo(tmp_path)
    _write_settings(tmp_path, {"marker": "head"})
    run_git(tmp_path, "add", SETTINGS_PATH)
    run_git(tmp_path, "commit", "-q", "-m", "head")
    # index は HEAD と同一、working だけ変更（stage しない）
    _write_settings(tmp_path, {"marker": "working"})

    result = read_committed_settings(str(tmp_path))
    assert result == {"marker": "head"}


def test_raises_when_absent(tmp_path: Path) -> None:
    init_repo(tmp_path)
    _write_settings(tmp_path, {"marker": "x"})
    run_git(tmp_path, "add", "home")
    run_git(tmp_path, "commit", "-q", "-m", "init")
    run_git(tmp_path, "rm", "-q", SETTINGS_PATH)

    try:
        read_committed_settings(str(tmp_path))
    except RuntimeError as exc:
        # どのファイルの取得に失敗したかがメッセージから読めること。git の汎用エラー
        # (サブコマンド名と exit code だけ) では、複数の git 呼び出しのどれが落ちたか判らない
        assert SETTINGS_PATH in str(exc)
    else:
        raise AssertionError("RuntimeError が送出されるべき")


def test_ignores_leaked_git_location_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # git hook 経由の実行では git が GIT_DIR / GIT_WORK_TREE を子へ渡す。これらを継承すると
    # `git -C <repo>` の repo 探索が hook 側の repo へ上書きされ別の index を読んでしまう。
    # ロケーション系 GIT_* を無視して -C で指定した repo を読むことを検証する。
    leaked = tmp_path / "leaked"
    leaked.mkdir()
    init_repo(leaked)
    _write_settings(leaked, {"marker": "leaked"})
    run_git(leaked, "add", SETTINGS_PATH)
    run_git(leaked, "commit", "-q", "-m", "leaked")

    target = tmp_path / "target"
    target.mkdir()
    init_repo(target)
    _write_settings(target, {"marker": "target"})
    run_git(target, "add", SETTINGS_PATH)
    run_git(target, "commit", "-q", "-m", "target")

    # hook が漏らす env を模擬（setup 完了後に設定する）
    monkeypatch.setenv("GIT_DIR", str(leaked / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(leaked))

    result = read_committed_settings(str(target))
    assert result == {"marker": "target"}


def test_raises_when_json_root_not_object(tmp_path: Path) -> None:
    init_repo(tmp_path)
    # ルートがオブジェクトでない（配列）不正な settings
    write_file(tmp_path, SETTINGS_PATH, "[]")
    run_git(tmp_path, "add", SETTINGS_PATH)
    run_git(tmp_path, "commit", "-q", "-m", "array root")

    try:
        read_committed_settings(str(tmp_path))
    except RuntimeError:
        pass
    else:
        raise AssertionError("RuntimeError が送出されるべき")
