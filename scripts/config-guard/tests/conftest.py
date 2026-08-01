"""テスト共通の git ヘルパと定数。

ここの git 呼び出しは必ず isolated_git_env を通す。pre-commit / git hook 経由の実行では
git がロケーション系 GIT_* (GIT_DIR / GIT_WORK_TREE 等) を子プロセスへ渡し、継承すると
tmp_path への git init / add が hook 側の repo へ向いて非決定的に失敗する
(test_git_source.py::test_ignores_leaked_git_location_env が pin するリークと同根)。
各テストファイルが subprocess.run を手書きすると 5 つ目のファイルで隔離を忘れる形の
穴が開くため、テストからの git 起動はここへ一本化する。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from config_guard.git_run import isolated_git_env

# 実リポジトリ (dotfiles) のルート。tests/ からの相対段数はレイアウト変更で壊れるので
# 各ファイルに散らさずここだけに置く
REPO_ROOT = Path(__file__).resolve().parents[3]


def run_git(repo: Path, *args: str) -> None:
    """`git -C repo <args>` を GIT_* 隔離環境で実行する。失敗は CalledProcessError。

    exit code を答えとして使う検査 (check-ignore 等) は config_guard.git_run 側の
    ヘルパの領分。ここはテストの前提を組む fixture 用途なので check=True で即死させる。
    """
    subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        env=isolated_git_env(),
    )


def init_repo(repo: Path) -> None:
    """テスト用の git repo を初期化する。commit するテストのため user 設定も入れる。"""
    run_git(repo, "init", "-q")
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "test")


def write_file(repo: Path, rel: str, text: str) -> Path:
    """repo 相対パス rel へ親ディレクトリごとファイルを書き、その絶対パスを返す。"""
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
