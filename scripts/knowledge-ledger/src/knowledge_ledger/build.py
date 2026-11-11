"""台帳ページを雛形・データ・スクリプトから組み立てる。

使い方: python -m knowledge_ledger.build <items.json> <out.html>
データの JSON は script 要素の中へ埋めるので、
< を \\u003c に逃がして </script> で切れないようにする。
"""

import json
import sys
from pathlib import Path
from typing import Any

# 雛形はパッケージの外 (scripts/knowledge-ledger/page/) に置く
PAGE_DIR = Path(__file__).resolve().parents[2] / "page"


def build_page(items: list[dict[str, Any]], head: str, scripts: list[str]) -> str:
    ids = [i["id"] for i in items]
    if len(ids) != len(set(ids)):
        raise ValueError("ID が重複している")
    if any("</script" in s for s in scripts):
        raise ValueError("雛形の script に </script が含まれている")
    data = json.dumps(items, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    out = head + '<script id="data" type="application/json">' + data + "</script>\n"
    for s in scripts:
        out += "<script>\n" + s + "</script>\n"
    return out


def main(argv: list[str]) -> int:
    items_path, out_path = argv
    items = json.loads(Path(items_path).read_text(encoding="utf-8"))
    head = (PAGE_DIR / "head.html").read_text(encoding="utf-8")
    script = (PAGE_DIR / "script.js").read_text(encoding="utf-8")
    out = build_page(items, head, [script])
    Path(out_path).write_text(out, encoding="utf-8")
    print(len(items), "件", len(out.encode()), "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
