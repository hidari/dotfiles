"""判定結果を状態ファイルへ書く。

読み手は SessionStart のプローブ (home/.claude/hooks/guard_probes.py) で、別の uv
プロジェクトから import できない。あちらのテストがこのファイルをパスで直接読み込んで
書き手と読み手の形を突き合わせるので、標準ライブラリ以外を import しないこと。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

STATE_RELPATH = Path(".local/state/node-security-notifier/security-releases.json")


def save_status(path: Path, *, fetched_at: int, security_versions: list[str]) -> None:
    """取得時刻 (epoch 秒) と security の版の一覧を書く。

    一時ファイルから rename で置き換えるので、プローブが書きかけを読むことは無い。
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        json.dumps({"fetched_at": fetched_at, "security_versions": security_versions}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    os.replace(tmp, path)
