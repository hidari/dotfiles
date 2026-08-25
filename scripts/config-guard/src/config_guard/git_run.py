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


def run_git(
    repo_root: str, *args: str, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    """`git -C repo_root <args>` を GIT_* 隔離環境で実行して結果を返す。

    stdin を渡すと --stdin 系サブコマンド (check-ignore 等) へ標準入力として供給する。
    """
    return subprocess.run(
        ["git", "-C", repo_root, *args],
        capture_output=True,
        text=True,
        check=False,
        input=stdin,
        env=isolated_git_env(),
    )


def run_git_checked(repo_root: str, *args: str) -> str:
    """`git -C repo_root <args>` を実行して stdout を返す。非ゼロ exit は RuntimeError。

    非ゼロ (128 = git repo でない等) を「結果なし」と黙って読み替えると、git エラーと
    「対象が無い」を取り違えて検査が素通りするため、明示的に失敗させる。
    非ゼロが正常な答えを持つコマンド (check-ignore の 1=not ignored 等) には使わず、
    run_git を直接使うこと。
    """
    proc = run_git(repo_root, *args)
    if proc.returncode != 0:
        raise RuntimeError(f"git {args[0]} が失敗しました (exit {proc.returncode})")
    return proc.stdout


def tracked_files(repo_root: str, pathspec: str) -> list[str]:
    """`git ls-files -z <pathspec>` の結果を repo 相対パスのリストで返す。

    NUL 区切りで受けて件数を落とさない作法は「パースが静かに欠ける」経路として CLAUDE.md が
    名指ししており、手当ての canonical は references/observation.md が持つ。分割の実装を
    ここへ 1 つだけ置くのは、モジュールごとに書くと片方だけが改行区切りへ戻っても
    両方緑のまま通るため。
    """
    stdout = run_git_checked(repo_root, "ls-files", "-z", pathspec)
    return [path for path in stdout.split("\0") if path]
