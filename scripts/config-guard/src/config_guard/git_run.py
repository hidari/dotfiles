"""git をロケーション系 GIT_* の継承から隔離して起動するヘルパ。

pre-commit / git hook 経由で実行されると git は GIT_DIR / GIT_WORK_TREE /
GIT_INDEX_FILE 等を子プロセスへ渡す。これらを継承すると `git -C <repo>` の repo 探索が
hook 側の repo に上書きされ、別の index / worktree を読んでしまう(worktree からの
コミットで実際に踏んだ)。repo 指定を -C に一本化するため、ロケーション系 GIT_* を
除いた環境で git を起動する。
"""

from __future__ import annotations

import os
import subprocess

# git の repo / worktree / index の位置を上書きする環境変数。継承すると -C を無効化する。
_GIT_LOCATION_VARS: frozenset[str] = frozenset(
    {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_COMMON_DIR",
        "GIT_PREFIX",
        "GIT_NAMESPACE",
    }
)


def isolated_git_env() -> dict[str, str]:
    """ロケーション系 GIT_* を除いた環境変数を返す。"""
    return {k: v for k, v in os.environ.items() if k not in _GIT_LOCATION_VARS}


def run_git(repo_root: str, *args: str) -> subprocess.CompletedProcess[str]:
    """`git -C repo_root <args>` を GIT_* 隔離環境で実行して結果を返す。"""
    return subprocess.run(
        ["git", "-C", repo_root, *args],
        capture_output=True,
        text=True,
        check=False,
        env=isolated_git_env(),
    )
