"""各件に「確かめ済み」の印を付ける。

- 札は text と basis を改行で繋いだ原文に含まれるかで ok / ng に分ける
  (reports は照らさない)
- 引用は covered.path の実ファイルに逐語で含まれるときだけ ok
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

# 既定の repo ルート。`~/` 始まりでない参照はここから引く
DEFAULT_REPO = Path(__file__).resolve().parents[4]


def make_file_reader(repo: str | Path = DEFAULT_REPO) -> Callable[[str], str | None]:
    """`~/` 始まりはホーム、それ以外は repo ルートから読む。読めなければ None"""

    def read(path: str) -> str | None:
        target = Path(path).expanduser() if path.startswith("~/") else Path(repo) / path
        try:
            return target.read_text(encoding="utf-8")
        except OSError:
            return None

    return read


def verify_item(item: dict[str, Any], read_ref: Callable[[str], str | None]) -> dict[str, Any]:
    source = (item.get("text") or "") + "\n" + (item.get("basis") or "")
    labels = item.get("labels") or []
    covered = item.get("covered") or {}
    path, quote = covered.get("path"), covered.get("quote")
    quote_ok = False
    if path and quote:
        body = read_ref(path)
        quote_ok = body is not None and quote in body
    return {
        "labels_ok": [lb for lb in labels if lb in source],
        "labels_ng": [lb for lb in labels if lb not in source],
        "quote_ok": quote_ok,
    }
