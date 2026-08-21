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
from typing import Any

from config_guard.git_run import isolated_git_env

# 実リポジトリ (dotfiles) のルート。tests/ からの相対段数はレイアウト変更で壊れるので
# 各ファイルに散らさずここだけに置く
REPO_ROOT = Path(__file__).resolve().parents[3]

# config-guard パッケージのルート (pyproject.toml と src/ が在る)。REPO_ROOT と同じ理由で
# 相対段数はここだけに置く
PACKAGE_ROOT = Path(__file__).resolve().parents[1]

# 必須フックの起動コマンド。settings_invariants の定数から生成しないこと。生成すると
# clean フィクスチャが常に検査を満たし、pin が自己参照で空虚になる。
TIRITH_HOOK_COMMAND = 'python3 "$HOME/.claude/hooks/tirith-check.py"'
APM_GUARD_HOOK_COMMAND = 'python3 "$HOME/.claude/hooks/apm-install-guard.py"'


def hook_group(*commands: str, matcher: str | None = "Bash") -> dict[str, Any]:
    """PreToolUse の 1 グループを作る。matcher=None で matcher キー自体を持たない形にする。"""
    group: dict[str, Any] = {"hooks": [{"type": "command", "command": c} for c in commands]}
    if matcher is not None:
        group["matcher"] = matcher
    return group


def pretooluse(*groups: dict[str, Any]) -> dict[str, Any]:
    """hooks セクションを作る。グループの分け方は配線の自由度なので呼び出し側が決める。"""
    return {"PreToolUse": list(groups)}


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


def configure_identity(repo: Path) -> None:
    """commit するテストのための user 設定。init した repo と clone した repo の両方で要る。"""
    run_git(repo, "config", "user.email", "test@example.com")
    run_git(repo, "config", "user.name", "test")


def init_repo(repo: Path) -> None:
    """テスト用の git repo を初期化する。commit するテストのため user 設定も入れる。"""
    run_git(repo, "init", "-q")
    configure_identity(repo)


def write_file(repo: Path, rel: str, text: str) -> Path:
    """repo 相対パス rel へ親ディレクトリごとファイルを書き、その絶対パスを返す。"""
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path
