"""build_page の組み立て規則を固定する。

出力のバイト一致は移行時に一度確かめただけで、ここでは持たない。
"""

import json
import re
from pathlib import Path
from typing import Any

import pytest

from knowledge_ledger.build import build_page, main

ITEMS: list[dict[str, Any]] = [
    {"id": "K1-001", "text": "原文 <b>強調</b>"},
    {"id": "K1-002", "text": "二件目"},
]
HEAD = "<title>t</title>\n"


def test_build_page_structure() -> None:
    out = build_page(ITEMS, HEAD, ["const a = 1;\n", "const b = 2;\n"])
    assert out.startswith("<!DOCTYPE html>\n" + HEAD)
    tags = re.findall(r"<script[^>]*>", out)
    assert tags == ['<script id="data" type="application/json">', "<script>", "<script>"]
    data = re.search(r'<script id="data" type="application/json">(.*?)</script>', out, re.S)
    assert data is not None
    assert [
        {k: v for k, v in i.items() if k != "verified"} for i in json.loads(data.group(1))
    ] == ITEMS
    assert out.index("const a = 1;") < out.index("const b = 2;")
    assert out.index('id="data"') < out.index("const a = 1;")


def test_build_page_escapes_lt() -> None:
    out = build_page(ITEMS, HEAD, ["x\n"])
    data = re.search(r'<script id="data" type="application/json">(.*?)</script>', out, re.S)
    assert data is not None
    assert "<" not in data.group(1)
    assert "\\u003cb>" in data.group(1)


def test_build_page_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="重複"):
        build_page([{"id": "A"}, {"id": "A"}], HEAD, ["x\n"])


def test_build_page_rejects_script_close_in_template() -> None:
    with pytest.raises(ValueError, match="script"):
        build_page(ITEMS, HEAD, ['const s = "</script>";\n'])


def test_build_page_embeds_verified_without_mutating_input() -> None:
    items = [{"id": "K1-001", "text": "alpha", "basis": "", "labels": ["alpha"]}]
    out = build_page(items, HEAD, ["x\n"], read_ref=lambda p: None)
    data = re.search(r'<script id="data" type="application/json">(.*?)</script>', out, re.S)
    assert data is not None
    assert json.loads(data.group(1))[0]["verified"] == {
        "labels_ok": ["alpha"],
        "labels_ng": [],
        "quote_ok": False,
    }
    assert "verified" not in items[0]


def test_main_embeds_logic_before_script(tmp_path: Path) -> None:
    items_path = tmp_path / "items.json"
    out_path = tmp_path / "out.html"
    items_path.write_text(json.dumps(ITEMS), encoding="utf-8")
    assert main([str(items_path), str(out_path)]) == 0
    out = out_path.read_text(encoding="utf-8")
    # 文書型の宣言を先頭に置き、文字コードの宣言をその直後に置く (head.html の先頭が meta charset)
    assert out.startswith('<!DOCTYPE html>\n<meta charset="utf-8">\n')
    assert out.index('id="data"') < out.index("LedgerLogic") < out.index("const ITEMS")
    assert len(re.findall(r"<script[^>]*>", out)) == 3
