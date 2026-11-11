"""merge の規則を固定する: 既存の件は不変、追記は件数と日付、quote は逐語確認。"""

import json
from pathlib import Path
from typing import Any

from knowledge_ledger.merge import main, merge

TODAY = "2026-12-01"


def base_items() -> list[dict[str, Any]]:
    return [
        {"id": "K1-001", "order": 1, "issue": "ISSUE-1", "text": "- a", "report_count": 2},
        {"id": "K1-002", "order": 2, "issue": "ISSUE-1", "text": "- b"},
        {"id": "K1-003", "order": 3, "issue": "ISSUE-1", "text": "- c"},
    ]


def prep_for(item_id: str, **over: Any) -> dict[str, Any]:
    p: dict[str, Any] = {
        "id": item_id,
        "summary": "要約",
        "labels": ["l"],
        "report_count": 1,
        "covered_status": "none",
        "covered_path": "",
        "covered_quote": "",
        "searched": ["語"],
        "placement": "p",
        "placement_detail": "d",
        "recommendation": "採る",
        "reason": "r",
        "version_dependent": False,
    }
    p.update(over)
    return p


def new_item(item_id: str) -> dict[str, Any]:
    return {"id": item_id, "issue": "ISSUE-1", "section": "s", "text": "- new", "added": TODAY}


def test_existing_items_unchanged_byte_for_byte() -> None:
    base = base_items()
    snapshot = [json.dumps(i, ensure_ascii=False, sort_keys=True) for i in base]
    delta = {"new": [new_item("K1-004")], "appended": [], "unmatched": []}
    out, _ = merge(base, delta, [prep_for("K1-004")], "/nonexistent", TODAY)
    assert [json.dumps(i, ensure_ascii=False, sort_keys=True) for i in out[:3]] == snapshot
    assert out[3]["order"] == 4
    assert out[3]["added"] == TODAY


def test_append_bumps_report_count_and_sets_appended() -> None:
    delta = {
        "new": [],
        "appended": [
            {"id": "K1-001", "new_text": None, "added_children": ["- c1", "- c2"]},
            {"id": "K1-002", "new_text": "- b\n  - x", "added_children": ["- x"]},
        ],
        "unmatched": [],
    }
    out, _ = merge(base_items(), delta, [], "/nonexistent", TODAY)
    by_id = {i["id"]: i for i in out}
    assert by_id["K1-001"]["report_count"] == 4
    assert by_id["K1-001"]["text"] == "- a\n  - c1\n  - c2"
    assert by_id["K1-001"]["appended"] == TODAY
    assert by_id["K1-002"]["report_count"] == 2
    assert by_id["K1-002"]["text"] == "- b\n  - x"
    assert "appended" not in by_id["K1-003"]


def test_quote_missing_from_referenced_file_falls_back_to_none(tmp_path: Path) -> None:
    (tmp_path / "rule.md").write_text("規範の本文にある一文\n", encoding="utf-8")
    delta = {"new": [new_item("K1-004"), new_item("K1-005")], "appended": [], "unmatched": []}
    prep = [
        prep_for(
            "K1-004",
            covered_status="covered",
            covered_path="rule.md",
            covered_quote="本文にある一文",
        ),
        prep_for(
            "K1-005", covered_status="covered", covered_path="rule.md", covered_quote="無い一文"
        ),
    ]
    out, quote_fail = merge(base_items(), delta, prep, str(tmp_path), TODAY)
    by_id = {i["id"]: i for i in out}
    assert by_id["K1-004"]["covered"]["status"] == "covered"
    assert by_id["K1-004"]["covered"]["quote"] == "本文にある一文"
    assert by_id["K1-005"]["covered"] == {
        "status": "none",
        "path": None,
        "quote": None,
        "searched": ["語"],
    }
    assert quote_fail == ["K1-005"]


def test_quote_with_unreadable_referenced_file_falls_back_to_none(tmp_path: Path) -> None:
    delta = {"new": [new_item("K1-004")], "appended": [], "unmatched": []}
    prep = [
        prep_for("K1-004", covered_status="partial", covered_path="nope.md", covered_quote="一文")
    ]
    out, quote_fail = merge(base_items(), delta, prep, str(tmp_path), TODAY)
    assert out[-1]["covered"]["status"] == "none"
    assert quote_fail == ["K1-004"]


def test_main_takes_today_and_writes_out(tmp_path: Path) -> None:
    files = {
        "base.json": base_items(),
        "delta.json": {
            "new": [],
            "appended": [{"id": "K1-003", "new_text": None, "added_children": ["- z"]}],
            "unmatched": [],
        },
        "prep.json": [],
    }
    for name, body in files.items():
        (tmp_path / name).write_text(json.dumps(body, ensure_ascii=False), encoding="utf-8")
    out_path = tmp_path / "out.json"
    argv = [str(tmp_path / n) for n in ("base.json", "delta.json", "prep.json")]
    argv += [str(out_path), str(tmp_path), "--today", TODAY]
    assert main(argv) == 0
    out = json.loads(out_path.read_text(encoding="utf-8"))
    assert {i["id"]: i for i in out}["K1-003"]["appended"] == TODAY
