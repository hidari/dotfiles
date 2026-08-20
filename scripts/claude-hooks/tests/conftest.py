"""テスト共通の定数とヘルパ。

フック本体は symlink 都合で `home/.claude/hooks/` にあるため、tests からの相対で解決する。
階層に依存する深さをここ 1 箇所へ閉じ、tests の位置が変わっても各テストが独立に壊れないようにする。

共有モジュール `pretooluse` はフック本体と同じディレクトリにあり、フックは実行時に
`sys.path[0]` (スクリプトのディレクトリ) 経由で解決する。テストからも同じモジュールを
直接 import するため、ここで探索パスへ加える。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "home" / ".claude" / "hooks"

if str(HOOKS_DIR) not in sys.path:
    sys.path.insert(0, str(HOOKS_DIR))


def git_scope_free_env() -> dict[str, str]:
    """git がどのリポジトリを見るかを決める環境変数を落とした環境を返す。

    pre-commit の commit hook は `git commit` のプロセス下で走るため GIT_DIR や GIT_WORK_TREE
    が環境に入る。これを継承すると cwd よりそちらが勝ち、テストが tmp に作った使い捨ての
    リポジトリではなく本体を操作してしまう。本体チェックアウトでは GIT_DIR が相対値になり
    cwd 変更で外れるので、worktree で commit したときだけ現れる。

    テストは使い捨てリポジトリしか触らないので、選別せず GIT_ 接頭辞ごと落とす。フック本体は
    本番環境で動くため、落とす対象を所在の指定だけに絞っている (apm-install-guard.py 参照)。
    """
    return {key: value for key, value in os.environ.items() if not key.startswith("GIT_")}
