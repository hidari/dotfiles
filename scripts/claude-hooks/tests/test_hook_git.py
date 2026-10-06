"""hook_git の仕様。

フックから git へ問い合わせる leaf。作業ツリーの根の解決規則と、git hook 経由で起動された
ときに環境変数が探索先を横取りする経路を検査する。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import hook_git
import pytest
from conftest import git_scope_free_env, make_git_repo


def test_リポジトリのルートを返す(tmp_path: Path, git_location_vars_stripped: None) -> None:
    repo = make_git_repo(tmp_path / "myrepo")

    assert hook_git.repo_root(repo) == repo.resolve()


def test_サブディレクトリからでもルートを返す(
    tmp_path: Path, git_location_vars_stripped: None
) -> None:
    """サブディレクトリごとに別の根を返すと、同じリポジトリの状態が経路で割れる。"""
    repo = make_git_repo(tmp_path / "myrepo")
    deep = repo / "frontend" / "src"
    deep.mkdir(parents=True)

    assert hook_git.repo_root(deep) == repo.resolve()


def test_リポジトリ外では受け取った作業ディレクトリを返す(
    tmp_path: Path, git_location_vars_stripped: None
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    assert hook_git.repo_root(plain) == plain


def test_リポジトリ外では_symlink_を解決しない(
    tmp_path: Path, git_location_vars_stripped: None
) -> None:
    """呼び出し側の 1 つがこの根から状態ファイルの名前を作るため、解決の有無を変えると
    既存の状態ファイルが別名になって参照できなくなる。
    """
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
    target = make_git_repo(tmp_path / "target")
    other = make_git_repo(tmp_path / "other")
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
    repo = make_git_repo(tmp_path / "myrepo")
    empty = tmp_path / "empty-path"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))

    assert hook_git.repo_root(repo) == repo


def test_文字列でもパスでも同じ根を返す(tmp_path: Path, git_location_vars_stripped: None) -> None:
    """呼び出し側が 2 つあり、片方は hook payload の文字列をそのまま渡す。"""
    repo = make_git_repo(tmp_path / "myrepo")

    assert hook_git.repo_root(str(repo)) == hook_git.repo_root(repo)


def _commit_and_add_worktree(repo: Path, worktree: Path) -> None:
    env = git_scope_free_env()
    for args in (
        ["commit", "-q", "--allow-empty", "-m", "init"],
        ["worktree", "add", "-q", "-b", worktree.name, str(worktree)],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env)


def test_本体のチェックアウトは本体の中からも_worktree_からも同じ根を返す(
    tmp_path: Path, git_location_vars_stripped: None
) -> None:
    repo = make_git_repo(tmp_path / "myrepo")
    worktree = tmp_path / "wt"
    _commit_and_add_worktree(repo, worktree)
    (repo / "sub").mkdir()

    assert hook_git.main_checkout_root(repo / "sub") == repo.resolve()
    assert hook_git.main_checkout_root(worktree) == repo.resolve()


def test_git_dir_を分けたリポジトリでは本体のチェックアウトを辿れない(
    tmp_path: Path, git_location_vars_stripped: None
) -> None:
    """common dir が .git という名前でないと、その親はチェックアウトではない。"""
    repo = tmp_path / "myrepo"
    subprocess.run(
        ["git", "init", "-q", "--separate-git-dir", str(tmp_path / "gitdir"), str(repo)],
        check=True,
        capture_output=True,
        env=git_scope_free_env(),
    )

    assert hook_git.main_checkout_root(repo) is None


def test_リポジトリ外では本体のチェックアウトを返さない(
    tmp_path: Path, git_location_vars_stripped: None
) -> None:
    plain = tmp_path / "plain"
    plain.mkdir()

    assert hook_git.main_checkout_root(plain) is None


def test_答えが得られなければ_None_を返す(tmp_path: Path, git_location_vars_stripped: None) -> None:
    """失敗の種類を呼び出し側へ伝えない。どれも同じ手当てになるので分岐を増やさない。"""
    plain = tmp_path / "plain"
    plain.mkdir()

    assert hook_git.rev_parse(plain, "--show-toplevel") is None
