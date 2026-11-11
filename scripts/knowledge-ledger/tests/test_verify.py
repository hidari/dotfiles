"""確かめ済みの印 (札の実在と引用の逐語一致) の判定規則を固定する。"""

from typing import Any

from knowledge_ledger.verify import verify_item


def _item(**kw: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "text": "本文 alpha",
        "basis": "根拠 beta",
        "reports": ["報告 gamma"],
        "labels": [],
        "covered": {"status": "none", "path": None, "quote": None},
    }
    base.update(kw)
    return base


def _reader(files: dict[str, str]) -> Any:
    return lambda p: files.get(p)


def test_labels_checked_against_text_and_basis() -> None:
    v = verify_item(_item(labels=["alpha", "beta"]), _reader({}))
    assert v["labels_ok"] == ["alpha", "beta"]
    assert v["labels_ng"] == []


def test_label_missing_goes_ng() -> None:
    # reports にだけ在る札は照らす原文に含めない
    v = verify_item(_item(labels=["alpha", "gamma", "zzz"]), _reader({}))
    assert v["labels_ok"] == ["alpha"]
    assert v["labels_ng"] == ["gamma", "zzz"]


def test_zero_labels() -> None:
    v = verify_item(_item(labels=[]), _reader({}))
    assert v["labels_ok"] == [] and v["labels_ng"] == []


def _covered(path: str | None, quote: str | None) -> dict[str, Any]:
    return {"status": "covered", "path": path, "quote": quote}


def test_quote_ok_only_when_ref_contains_quote() -> None:
    files = {"~/.claude/a.md": "前 引用文 後"}
    ok = verify_item(_item(covered=_covered("~/.claude/a.md", "引用文")), _reader(files))
    ng = verify_item(_item(covered=_covered("~/.claude/a.md", "無い文")), _reader(files))
    assert ok["quote_ok"] is True
    assert ng["quote_ok"] is False


def test_quote_ng_when_ref_unreadable() -> None:
    v = verify_item(_item(covered=_covered("x.md", "q")), _reader({}))
    assert v["quote_ok"] is False


def test_no_quote_means_quote_ok_false() -> None:
    files = {"x.md": "abc"}
    assert verify_item(_item(), _reader(files))["quote_ok"] is False
    assert verify_item(_item(covered=_covered("x.md", "")), _reader(files))["quote_ok"] is False
    assert verify_item(_item(covered=_covered(None, "q")), _reader(files))["quote_ok"] is False
