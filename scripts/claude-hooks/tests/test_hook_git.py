"""hook_git の仕様。

フックから git の作業ツリーの根を解決する leaf。解決の規則そのものと、git hook 経由で
起動されたときに環境変数が探索先を横取りする経路を検査する。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import hook_git
import pytest
from conftest import git_scope_free_env


def _git_repo(path: Path) -> Path:
    """使い捨ての git リポジトリを 1 つ作る。"""
    path.mkdir(parents=True)
    subprocess.run(
        ["git", "init", "-q"],
        cwd=path,
        check=True,
        capture_output=True,
        env=git_scope_free_env(),
    )
    return path


def test_リポジトリのルートを返す(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in hook_git.LOCATION_VARS:
        monkeypatch.delenv(name, raising=False)
    repo = _git_repo(tmp_path / "myrepo")

    assert hook_git.repo_root(repo) == repo.resolve()


def test_サブディレクトリからでもルートを返す(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """サブディレクトリごとに別の根を返すと、同じリポジトリの状態が経路で割れる。"""
    for name in hook_git.LOCATION_VARS:
        monkeypatch.delenv(name, raising=False)
    repo = _git_repo(tmp_path / "myrepo")
    deep = repo / "frontend" / "src"
    deep.mkdir(parents=True)

    assert hook_git.repo_root(deep) == repo.resolve()


def test_リポジトリ外では受け取った作業ディレクトリをそのまま返す(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """symlink を解決しない。呼び出し側の 1 つがこの根から状態ファイルの名前を作るため、
    解決の有無を変えると既存の状態ファイルが別名になって参照できなくなる。
    """
    for name in hook_git.LOCATION_VARS:
        monkeypatch.delenv(name, raising=False)
    real = tmp_path / "real"
    real.mkdir()
    link = tmp_path / "link"
    link.symlink_to(real)

    assert hook_git.repo_root(link) == link


def test_ロケーション系の_GIT_変数は探索先を横取りしない(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """git hook 経由で起動されると git がこれらを子へ渡し、-C より優先される。

    落とさないと、引数で指したリポジトリではなくフック側のリポジトリが返る。呼び出し側は
    引数のとおりに解決されたと信じるので、間違った根に対して状態を書きに行く。
    """
    target = _git_repo(tmp_path / "target")
    other = _git_repo(tmp_path / "other")
    monkeypatch.setenv("GIT_DIR", str(other / ".git"))
    monkeypatch.setenv("GIT_WORK_TREE", str(other))

    assert hook_git.repo_root(target) == target.resolve()


def test_落とすのはロケーション系だけで他の_GIT_変数は残す(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """全 GIT_ 接頭辞を落とすと、認証やページャの設定まで剥がれて別物を測る。"""
    monkeypatch.setenv("GIT_AUTHOR_NAME", "keep-me")
    monkeypatch.setenv("GIT_DIR", str(tmp_path / "nowhere" / ".git"))

    env = hook_git.isolated_env()

    assert env["GIT_AUTHOR_NAME"] == "keep-me"
    assert "GIT_DIR" not in env


def test_git_が起動できなくても作業ディレクトリに落ちる(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """git 不在は「リポジトリではない」と同じ扱いにする。フックは止めない。"""
    repo = _git_repo(tmp_path / "myrepo")
    empty = tmp_path / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    assert hook_git.repo_root(repo) == repo


def test_文字列でもパスでも同じ根を返す(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """呼び出し側が 2 つあり、片方は hook payload の文字列をそのまま渡す。"""
    for name in hook_git.LOCATION_VARS:
        monkeypatch.delenv(name, raising=False)
    repo = _git_repo(tmp_path / "myrepo")

    assert hook_git.repo_root(str(repo)) == hook_git.repo_root(repo)
