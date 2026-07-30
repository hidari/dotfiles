"""追跡下の Markdown の相対リンクが実在するかを検査する。

Issue を docs/issues/closed/ へ移すたびに、その Issue を指す相対リンクと、その Issue から
出ているリンクの両方が切れる。`../10_...` と `../closed/10_...` の書き分けが両端の
open / closed 状態に依存するためで、close する側とは別のファイルへ波及編集が要る。
実際 closed/9_.../issue.md のリンクは導入時点で壊れており main 上に残っていた。

扱うのはインラインリンク `[text](target)` のみ。参照リンク定義・HTML タグ・自動リンクは
リポジトリに 1 件も無いため対象外とする。画像記法は同じ形なので自然にカバーされる。
"""

from __future__ import annotations

import re
import urllib.parse

# インラインリンクのターゲット部分。画像記法 ![alt](target) も同じ形なので拾える
LINK_PATTERN = re.compile(r"\]\(([^)]+)\)")

# ネットワークを叩かないためスキップするスキーム
EXTERNAL_SCHEME = re.compile(r"^(?:https?|mailto|ftp):", re.IGNORECASE)


def extract_link_targets(text: str) -> list[str]:
    """Markdown 本文からインラインリンクのターゲット文字列を抽出する。"""
    return LINK_PATTERN.findall(text)


def link_path_to_check(target: str) -> str | None:
    """検査すべきパス部分を URL デコードして返す。検査不要なら None を返す。"""
    if EXTERNAL_SCHEME.match(target):
        return None
    if target.startswith("#"):
        return None
    # アンカーを先に切り落としてからデコードする。逆順にすると %23 (ファイル名中の #) が
    # 裸の # になり、パスの一部が誤ってアンカーとして切り落とされる
    path_part = target.split("#", 1)[0]
    return urllib.parse.unquote(path_part)
