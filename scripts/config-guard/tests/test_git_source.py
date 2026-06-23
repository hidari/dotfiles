"""git_source の仕様テスト。working tree を読まないことを実 git リポで検証する。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from config_guard.git_source import SETTINGS_PATH, read_committed_settings


def _run(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    _run(repo, "init", "-q")
    _run(repo, "config", "user.email", "test@example.com")
    _run(repo, "config", "user.name", "test")


def _write_settings(repo: Path, payload: dict[str, object]) -> None:
    path = repo / SETTINGS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_prefers_staged_over_head_and_ignores_working(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    # HEAD には head 版を commit
    _write_settings(tmp_path, {"marker": "head"})
    _run(tmp_path, "add", SETTINGS_PATH)
    _run(tmp_path, "commit", "-q", "-m", "head")
    # index には staged 版を stage
    _write_settings(tmp_path, {"marker": "staged"})
    _run(tmp_path, "add", SETTINGS_PATH)
    # working tree には working 版（stage しない）
    _write_settings(tmp_path, {"marker": "working"})

    result = read_committed_settings(str(tmp_path))
    assert result == {"marker": "staged"}


def test_returns_committed_content_when_only_working_differs(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write_settings(tmp_path, {"marker": "head"})
    _run(tmp_path, "add", SETTINGS_PATH)
    _run(tmp_path, "commit", "-q", "-m", "head")
    # index は HEAD と同一、working だけ変更（stage しない）
    _write_settings(tmp_path, {"marker": "working"})

    result = read_committed_settings(str(tmp_path))
    assert result == {"marker": "head"}


def test_raises_when_absent(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write_settings(tmp_path, {"marker": "x"})
    _run(tmp_path, "add", "home")
    _run(tmp_path, "commit", "-q", "-m", "init")
    _run(tmp_path, "rm", "-q", SETTINGS_PATH)

    try:
        read_committed_settings(str(tmp_path))
    except RuntimeError:
        pass
    else:
        raise AssertionError("RuntimeError が送出されるべき")


def test_raises_when_json_root_not_object(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    path = tmp_path / SETTINGS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    # ルートがオブジェクトでない（配列）不正な settings
    path.write_text("[]", encoding="utf-8")
    _run(tmp_path, "add", SETTINGS_PATH)
    _run(tmp_path, "commit", "-q", "-m", "array root")

    try:
        read_committed_settings(str(tmp_path))
    except RuntimeError:
        pass
    else:
        raise AssertionError("RuntimeError が送出されるべき")
