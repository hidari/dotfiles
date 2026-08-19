"""テスト共通の定数。

フック本体は symlink 都合で `home/.claude/hooks/` にあるため、tests からの相対で解決する。
階層に依存する深さをここ 1 箇所へ閉じ、tests の位置が変わっても各テストが独立に壊れないようにする。
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOKS_DIR = REPO_ROOT / "home" / ".claude" / "hooks"
