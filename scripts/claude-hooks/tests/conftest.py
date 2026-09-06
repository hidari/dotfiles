"""テスト共通の定数とヘルパ。

フック本体は symlink 都合で `home/.claude/hooks/` にあるため、tests からの相対で解決する。
階層に依存する深さをここ 1 箇所へ閉じ、tests の位置が変わっても各テストが独立に壊れないようにする。

共有モジュール `pretooluse` はフック本体と同じディレクトリにあり、フックは実行時に
`sys.path[0]` (スクリプトのディレクトリ) 経由で解決する。テストからも同じモジュールを
直接 import するため、ここで探索パスへ加える。
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "home" / ".claude" / "hooks"
BOOTSTRAP = REPO_ROOT / "bootstrap.sh"

if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))


def git_scope_free_env() -> dict[str, str]:
    """git がどのリポジトリを見るかを決める環境変数を落とした環境を返す。

    pre-commit の commit hook は `git commit` のプロセス下で走るため GIT_DIR や GIT_WORK_TREE
    が環境に入る。これを継承すると cwd よりそちらが勝ち、テストが tmp に作った使い捨ての
    リポジトリではなく本体を操作してしまう。本体チェックアウトでは GIT_DIR が相対値になり
    cwd 変更で外れるので、worktree で commit したときだけ現れる。

    テストは使い捨てリポジトリしか触らないので、選別せず GIT_ 接頭辞ごと落とす。フック本体で
    落とす対象を所在の指定だけに絞っているものは hook_git.py で、その理由もあちらが持つ
    (apm-install-guard.py はフックだが、あちらは GIT_ 接頭辞ごと落とす別の方針である)。
    """
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}


def make_git_repo(path: Path) -> Path:
    """使い捨ての git リポジトリを 1 つ作って返す。"""
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["git", "init", "-q"],
        cwd=path,
        check=True,
        capture_output=True,
        env=git_scope_free_env(),
    )
    return path


@pytest.fixture
def git_location_vars_stripped(monkeypatch: pytest.MonkeyPatch) -> None:
    """ロケーション系 GIT_* を環境から落とす。

    pre-commit の commit hook 下で走ると git がこれらを子へ渡し、`-C` で指した使い捨ての
    リポジトリではなく本体が解決される。落とさないと本体の名前が返るので、判定は「エラー」
    ではなく、もっともらしい別の値として外れる。

    hook_git の import をここで行うのは、探索パスへ HOOKS_DIR を足すのがこのファイルの
    上の行だからである。モジュール直下へ置くとその行より前に解決されて失敗する。
    """
    import hook_git

    for name in hook_git.LOCATION_VARS:
        monkeypatch.delenv(name, raising=False)


def bash_symlink_pairs() -> list[str]:
    """bootstrap.sh の SYMLINK_PAIRS を bash 自身に解釈させて読む。

    text-parse せずに source する。regex で拾うと、配列内のコメント行を要素と誤読したり
    引用規約をテスト側へ二重実装して drift させる。BASH_SOURCE ガードがあるので source
    しても main は走らない。

    conftest.py に置くのは、呼ぶ側がテスト本体とは別ファイルになったため、bash に
    source させて読む実装をここへ共通化したから。呼び出し元の一覧は grep で分かるので
    ここには書かない。
    """
    script = f"source {shlex.quote(str(BOOTSTRAP))}; printf '%s\\n' \"${{SYMLINK_PAIRS[@]}}\""
    proc = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        env=git_scope_free_env(),
        check=True,
    )
    return [line for line in proc.stdout.splitlines() if line]
