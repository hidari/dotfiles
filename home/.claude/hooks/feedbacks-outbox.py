#!/usr/bin/env python3
"""Claude Code hook: 他リポジトリのセッションの知見を dotfiles の feedbacks-box へ送る側の骨格。

user スコープで全リポジトリに配線し、サブコマンド (session / stop / end) で
SessionStart / Stop / SessionEnd の処理へ分ける。この骨格は除外の判定だけを持つ。

動かない場合: subagent (agent_id を持つ payload)、cwd が無いか実在しない、
cwd のリポジトリが受け箱 (main checkout の docs/.feedbacks-box/) を持つ、
skill (cross-repo-learnings) が入っていない。

箱の位置は絶対パスを設定へ書かず、この hook の実体の位置から導く。
hook として呼ばれる経路は fail-safe (無出力 + exit 0)。
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

import hook_git

SKILL_NAME = "cross-repo-learnings"

# リポジトリルートから見たまとめの置き場
OUTBOX_RELATIVE = Path(".cache") / "feedbacks-outbox"

# 受け箱のリポジトリルートからの位置 (feedbacks-box.py の BOX_RELATIVE と同じ約束)
_BOX_RELATIVE = Path("docs") / ".feedbacks-box"

SUBCOMMANDS = ("session", "stop", "end")


def _sanitize(name: str) -> str:
    """ファイル名に使う識別子の区切り文字等を潰す (handoff-sentinel と同じ文字集合)。"""
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)


def dotfiles_box() -> Path:
    """dotfiles の受け箱。環境変数があればそれを、無ければ自分の実体から導いた位置を返す。

    hooks → .claude → home → dotfiles の順に辿る。実体を解決するので live の symlink 経由でも
    dotfiles のチェックアウトに着く。
    """
    override = os.environ.get("FEEDBACKS_BOX_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[3] / _BOX_RELATIVE


def outbox_path(cwd: str, session_id: str) -> Path:
    return hook_git.repo_root(cwd) / OUTBOX_RELATIVE / f"{_sanitize(session_id)}.md"


def skill_installed() -> bool:
    config_dir = os.environ.get("CLAUDE_CONFIG_DIR") or str(Path.home() / ".claude")
    return (Path(config_dir) / "skills" / SKILL_NAME / "SKILL.md").is_file()


def active(payload: dict[str, Any]) -> Path | None:
    """hook が動いてよいならリポジトリルートを、だめなら None を返す。"""
    if payload.get("agent_id"):
        return None
    cwd = payload.get("cwd")
    if not (isinstance(cwd, str) and os.path.isdir(cwd)):
        return None
    if not skill_installed():
        return None
    # 受け箱は ignore されて linked worktree には無いので、本体のチェックアウトで探す
    main_root = hook_git.main_checkout_root(cwd) or hook_git.repo_root(cwd)
    if (main_root / _BOX_RELATIVE).is_dir():
        return None
    return hook_git.repo_root(cwd)


def main(argv: list[str]) -> int:
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict) or not argv or argv[0] not in SUBCOMMANDS:
            return 0
        # 各サブコマンドの本体は後続のタスクで足す
        active(payload)
    except Exception:
        # fail-safe: 送る側の故障で作業を止めない
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
