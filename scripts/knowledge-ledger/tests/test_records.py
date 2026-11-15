"""records の規則を固定する: 判断の保存先の写しから Issue ごとの採否の表を生成する。"""

import json
from pathlib import Path
from typing import Any

import pytest

from knowledge_ledger.records import issue_dir, main, render

SNAP = "2026-11-15"


def items() -> list[dict[str, Any]]:
    return [
        {"id": "K1-001", "order": 1, "issue": "ISSUE-1", "text": "- 一行目 | 区切りを含む\n  - 子"},
        {"id": "K1-002", "order": 2, "issue": "ISSUE-1", "text": "- " + "あ" * 50},
        {"id": "K1-003", "order": 3, "issue": "ISSUE-1", "text": "- まだの件"},
        {"id": "INS-1", "order": 4, "issue": "ISSUE-1", "text": "表の内容"},
    ]


def decisions() -> dict[str, dict[str, Any]]:
    return {
        "K1-001": {"decision": "採る", "note": "NOTE-SENTINEL"},
        "K1-002": {
            "decision": "採らない",
            "decidedBy": "claude",
            "claudeRule": "R5",
            "claudeReason": "REASON-SENTINEL",
            "claudeDest": "",
        },
        "INS-1": {
            "decision": "採る",
            "decidedBy": "claude",
            "claudeRule": "14",
            "claudeDest": "references/testing.md の「変異注入」",
        },
    }


def test_render_lists_items_in_order_with_decider_rule_and_dest_but_no_reason_or_note() -> None:
    out = render("ISSUE-1", items(), decisions(), SNAP)
    table = [line for line in out.split("\n") if line.startswith("| ")]
    rows = table[2:]
    assert rows == [
        "| K1-001 | 一行目 \\| 区切りを含む | 採る | 人 |  |  |",
        "| K1-002 | " + "あ" * 40 + "… | 採らない | Claude | R5 |  |",
        "| K1-003 | まだの件 | まだ |  |  |  |",
        "| INS-1 | 表の内容 | 採る | Claude | 14 | references/testing.md の「変異注入」 |",
    ]
    assert "REASON-SENTINEL" not in out
    assert "NOTE-SENTINEL" not in out


def test_render_header_has_snapshot_date_and_generator() -> None:
    out = render("ISSUE-1", items(), {}, SNAP)
    assert out.startswith("# ISSUE-1 の採否 (2026-11-15 に判断の保存先から写した)\n")
    assert "knowledge_ledger.records" in out.split("\n| 件")[0]


def test_render_reads_null_decision_as_undecided() -> None:
    out = render("ISSUE-1", items()[2:3], {"K1-003": {"decision": None, "note": "x"}}, SNAP)
    assert "| K1-003 | まだの件 | まだ |  |  |  |" in out


def test_issue_dir_matches_id_with_separator_and_searches_closed(tmp_path: Path) -> None:
    issues = tmp_path / "docs/issues"
    (issues / "ISSUE-134_別の件").mkdir(parents=True)
    (issues / "ISSUE-1_本命").mkdir()
    (issues / "closed/37_閉じた件").mkdir(parents=True)
    assert issue_dir(tmp_path, "ISSUE-1") == issues / "ISSUE-1_本命"
    assert issue_dir(tmp_path, "37") == issues / "closed/37_閉じた件"
    with pytest.raises(ValueError):
        issue_dir(tmp_path, "ISSUE-9")


def test_main_writes_decisions_md_per_issue_with_items(tmp_path: Path) -> None:
    (tmp_path / "docs/issues/ISSUE-1_本命").mkdir(parents=True)
    (tmp_path / "docs/issues/ISSUE-2_別").mkdir()
    its = [*items(), {"id": "K2-001", "order": 5, "issue": "ISSUE-2", "text": "- 二"}]
    (tmp_path / "items.json").write_text(json.dumps(its, ensure_ascii=False), encoding="utf-8")
    ddir = tmp_path / "decisions"
    ddir.mkdir()
    for k, v in decisions().items():
        (ddir / f"{k}.json").write_text(json.dumps(v, ensure_ascii=False), encoding="utf-8")
    rc = main([str(tmp_path), str(tmp_path / "items.json"), str(ddir), "--snapshot", SNAP])
    assert rc == 0
    one = tmp_path / "docs/issues/ISSUE-1_本命/ISSUE-1-decisions.md"
    two = tmp_path / "docs/issues/ISSUE-2_別/ISSUE-2-decisions.md"
    assert one.read_text(encoding="utf-8") == render("ISSUE-1", items(), decisions(), SNAP)
    assert "| K2-001 | 二 | まだ |  |  |  |" in two.read_text(encoding="utf-8")


def test_main_rejects_decision_for_unknown_id(tmp_path: Path) -> None:
    (tmp_path / "docs/issues/ISSUE-1_本命").mkdir(parents=True)
    (tmp_path / "items.json").write_text(json.dumps(items(), ensure_ascii=False), encoding="utf-8")
    ddir = tmp_path / "decisions"
    ddir.mkdir()
    (ddir / "K9-999.json").write_text(json.dumps({"decision": "採る"}), encoding="utf-8")
    with pytest.raises(ValueError, match="K9-999"):
        main([str(tmp_path), str(tmp_path / "items.json"), str(ddir), "--snapshot", SNAP])


def test_render_does_not_double_escape_an_already_escaped_pipe() -> None:
    """表の行から取った原文は `\\|` を既に持つ。二重に逃がすと GFM で列がずれる"""
    its = [{"id": "INS-1", "order": 1, "issue": "ISSUE-1", "text": "既定値を `a \\|\\| b` で出す"}]
    out = render("ISSUE-1", its, {}, SNAP)
    assert "| INS-1 | 既定値を `a \\|\\| b` で出す | まだ |  |  |  |" in out


def test_render_unescapes_before_truncation_so_the_cut_never_splits_an_escape() -> None:
    text = "x" * 39 + "\\|y" + "z" * 10
    out = render(
        "ISSUE-1", [{"id": "K1-001", "order": 1, "issue": "ISSUE-1", "text": text}], {}, SNAP
    )
    assert "| K1-001 | " + "x" * 39 + "\\|… | まだ |  |  |  |" in out
