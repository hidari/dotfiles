"""台帳の元データに増分と下ごしらえを合わせる。

使い方:
  python -m knowledge_ledger.merge <items-base.json> <delta.json> <prep.json>
  <out-items.json> <repo>
  --today YYYY-MM-DD
- 既存の件は ID・順序・判断の対象を変えない。追記があった件だけ原文を差し替え、
  report_count を足し、appended に日付を入れる
- 新しい件は末尾に足し、order は既存の最大の続きにする
- covered_quote は covered_path の実ファイルに逐語で含まれることを確かめ、
  含まれなければ none へ落として数える
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from knowledge_ledger.verify import make_file_reader


def _dump(item: dict[str, Any]) -> str:
    return json.dumps(item, ensure_ascii=False, sort_keys=True)


def _quote_in_file(repo: str, path: str, quote: str) -> bool:
    body = make_file_reader(repo)(path)
    return body is not None and quote in body


def merge(
    base: list[dict[str, Any]],
    delta: dict[str, Any],
    prep_list: list[dict[str, Any]],
    repo: str,
    today: str,
) -> tuple[list[dict[str, Any]], list[str]]:
    """合わせた件の一覧と、quote が確かめられず none へ落とした ID の一覧を返す"""
    prep = {p["id"]: p for p in prep_list}
    by_id = {i["id"]: i for i in base}

    before = {i["id"]: _dump(i) for i in base}
    for a in delta["appended"]:
        it = by_id[a["id"]]
        if a["new_text"] is not None:
            it["text"] = a["new_text"]
        else:
            it["text"] = it["text"] + "\n" + "\n".join("  " + c for c in a["added_children"])
        it["report_count"] = (it.get("report_count") or 1) + len(a["added_children"])
        it["appended"] = today

    missing = [i["id"] for i in delta["new"] if i["id"] not in prep]
    if missing:
        raise ValueError(f"下ごしらえが無い件: {missing}")

    quote_fail: list[str] = []
    order = max(i["order"] for i in base)
    out = list(base)
    for n in delta["new"]:
        p = prep[n["id"]]
        status, path, quote = (
            p["covered_status"],
            p["covered_path"] or None,
            p["covered_quote"] or None,
        )
        if status != "none" and not (path and quote and _quote_in_file(repo, path, quote)):
            quote_fail.append(n["id"])
            status, path, quote = "none", None, None
        order += 1
        out.append(
            {
                "id": n["id"],
                "order": order,
                "issue": n["issue"],
                "section": n["section"],
                "text": n["text"],
                "basis": n.get("basis", ""),
                "reports": [],
                "summary": p["summary"],
                "labels": p["labels"],
                "report_count": max(1, p["report_count"]),
                "covered": {
                    "status": status,
                    "path": path,
                    "quote": quote,
                    "searched": p["searched"],
                },
                "placement": p["placement"],
                "placement_detail": p["placement_detail"],
                "recommendation": p["recommendation"],
                "reason": p["reason"],
                "version_dependent": p["version_dependent"],
                "added": today,
            }
        )

    # 追記の無い既存の件はバイト単位で不変であること
    changed = {a["id"] for a in delta["appended"]}
    for i in base:
        if i["id"] not in changed and _dump(i) != before[i["id"]]:
            raise ValueError(f"追記の無い件が変わった: {i['id']}")
    ids = [i["id"] for i in out]
    if len(ids) != len(set(ids)):
        raise ValueError("ID が重複している")
    return out, quote_fail


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="knowledge_ledger.merge")
    for name in ("base", "delta", "prep", "out", "repo"):
        ap.add_argument(name)
    ap.add_argument("--today", required=True, help="追加・追記の日付 (YYYY-MM-DD)")
    a = ap.parse_args(argv)

    def load(p: str) -> Any:
        return json.loads(Path(p).read_text(encoding="utf-8"))

    delta = load(a.delta)
    out, quote_fail = merge(load(a.base), delta, load(a.prep), a.repo, a.today)
    Path(a.out).write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print(
        "total", len(out), "new", len(delta["new"]), "appended", len(delta["appended"]),
        "quote_fail", len(quote_fail), quote_fail,
    )  # fmt: skip
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
