"""committed（staged を優先し HEAD にフォールバック）な settings.json を git から読む。

settings.json は skip-worktree のため working tree = live superset である。
working file を読むと個人トグルや /Users パスを誤検出するため、必ず git から読む。
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

SETTINGS_PATH = "home/.claude/settings.json"


def _git_show(repo_root: str, ref: str) -> str | None:
    proc = subprocess.run(
        ["git", "-C", repo_root, "show", ref],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def read_committed_settings(repo_root: str) -> dict[str, Any]:
    """index（staged）の settings.json を取得して JSON として返す。

    index には commit 直後（未変更時）は HEAD と同一内容が入っているため、
    staged 優先・HEAD フォールバックの両方を index 一本で実現できる。
    working tree は決して読まない。index にない場合（削除含む）は RuntimeError。
    """
    # index からの読み取り。staged 削除時は :path が失敗するため RuntimeError になる
    content = _git_show(repo_root, f":{SETTINGS_PATH}")
    if content is not None:
        parsed: dict[str, Any] = json.loads(content)
        return parsed
    raise RuntimeError(f"git から {SETTINGS_PATH} を取得できませんでした (index に存在しない)")
