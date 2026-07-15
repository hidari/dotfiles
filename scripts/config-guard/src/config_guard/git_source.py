"""committed な settings.json を git の index（staged）経由で読む。

settings.json は skip-worktree のため working tree = live superset である。
working file を読むと個人トグルや /Users パスを誤検出するため、必ず git の
index から読む（clean commit 後は index = HEAD 内容、dance 後は staged 内容）。
"""

from __future__ import annotations

import json
from typing import Any

from config_guard.git_run import run_git

SETTINGS_PATH = "home/.claude/settings.json"


def _git_show(repo_root: str, ref: str) -> str | None:
    proc = run_git(repo_root, "show", ref)
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
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise RuntimeError(f"{SETTINGS_PATH} の JSON ルートがオブジェクトではありません")
        return parsed
    raise RuntimeError(f"git から {SETTINGS_PATH} を取得できませんでした (index に存在しない)")
