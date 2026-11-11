"""仕分けの差分から台帳の増分を作る。

使い方:
  python -m knowledge_ledger.delta <worktree> <base-items.json> <out-delta.json>
  --today YYYY-MM-DD
- 追記された最上位の箇条 (子を含む) は新しい件。ID は ISSUE-133 が K133-<続き番号>、
  ISSUE-134 が K134-<続き番号>、ISSUE-88 は箇条の INS 番号、ほかの Issue は K<番号>-<連番>
- 既存の箇条の子として足された行は、親の箇条の1行目で台帳の件を引き、
  原文へ足して report_count を増やす
- 台帳に無い既存の箇条へ足された子は、親の1行目と足した子を合わせて新しい件にする
"""

import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

SKIP_SECTIONS = {"タスク", "関連", "未決", "背景", "予算", "反証された前提"}


def _issue_of(path: str) -> tuple[str, str]:
    m = re.search(r"/(ISSUE-)?(\d+)_", path)
    if m is None:
        raise ValueError(f"Issue の番号を読めないパス: {path}")
    return m.group(2), (m.group(1) or "") + m.group(2)


def _parse(lines: list[str]) -> list[dict[str, Any]]:
    """箇条を (節, 最上位の行番号, [行番号...]) のまとまりに分ける"""
    blocks: list[dict[str, Any]] = []
    section: str | None = None
    cur: dict[str, Any] | None = None
    for n, line in enumerate(lines):
        if line.startswith("#"):
            section = line.lstrip("#").strip()
            cur = None
            continue
        if line.startswith("- "):
            cur = {"section": section, "rows": [n]}
            blocks.append(cur)
        elif line.startswith("  ") and line.strip() and cur is not None:
            cur["rows"].append(n)
        elif not line.strip():
            continue
        else:
            cur = None
    return blocks


def _git(wt: str, *args: str) -> str:
    return subprocess.run(["git", "-C", wt, *args], capture_output=True, check=True).stdout.decode()


def _added_lines(wt: str, path: str) -> set[int]:
    """作業ツリーの側で追加された行の番号 (0 始まり) の集合"""
    diff = _git(wt, "diff", "-U0", "origin/main...HEAD", "--", path)
    added: set[int] = set()
    n: int | None = None
    for line in diff.split("\n"):
        m = re.match(r"@@ -\S+ \+(\d+)(?:,(\d+))? @@", line)
        if m:
            n = int(m.group(1)) - 1
            continue
        if n is None:
            continue
        if line.startswith("+") and not line.startswith("+++"):
            added.add(n)
            n += 1
        elif line.startswith(" "):
            n += 1
    return added


def build_delta(wt: str, base: list[dict[str, Any]], today: str) -> dict[str, Any]:
    out = _git(wt, "-c", "core.quotePath=false", "diff", "--name-only", "-z", "origin/main...HEAD")
    files = [f for f in out.split("\0") if f.endswith("issue.md")]

    # 台帳の件を親の1行目で引く表。原文の1行目は Issue 側の書き換えで
    # 変わっていない前提で照合し、外れは報告する
    by_first: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for it in base:
        by_first.setdefault((it["issue"], it["text"].split("\n")[0]), []).append(it)

    maxno: dict[str, int] = {}
    for it in base:
        m = re.match(r"K(\d+)-(\d+)$", it["id"])
        if m:
            maxno[m.group(1)] = max(maxno.get(m.group(1), 0), int(m.group(2)))

    new_items: list[dict[str, Any]] = []
    appended: dict[str, dict[str, Any]] = {}
    unmatched: list[dict[str, Any]] = []
    for path in sorted(files):
        num, issue = _issue_of(path)
        lines = (Path(wt) / path).read_text(encoding="utf-8").split("\n")
        add = _added_lines(wt, path)
        section: str | None = None
        for n, line in enumerate(lines):
            if line.startswith("#"):
                section = line.lstrip("#").strip()
            # ISSUE-88 の新しい INS は表の行で足される。台帳の原文は2列目
            m = re.match(r"\| (INS-\d+) \| (.*?) \|(.*)\|\s*$", line)
            if m and n in add:
                new_items.append(
                    {
                        "id": m.group(1),
                        "issue": issue,
                        "section": section,
                        "text": m.group(2),
                        "basis": m.group(3).strip(" |"),
                        "added": today,
                    }
                )
        for b in _parse(lines):
            rows = b["rows"]
            top, kids = rows[0], rows[1:]
            new_kids = [r for r in kids if r in add]
            text_all = "\n".join(lines[r] for r in rows)
            if (
                b["section"] in SKIP_SECTIONS
                or lines[top].startswith("- [")
                or not (top in add or new_kids)
            ):
                continue
            # 「INS-n の再報告」の箇条は既存の INS の件へ足す
            ref = re.match(r"- (INS-\d+) の", lines[top])
            if ref and top in add:
                tid = ref.group(1)
                if any(i["id"] == tid for i in base):
                    a = appended.setdefault(
                        tid, {"id": tid, "new_text": None, "added_children": []}
                    )
                    a["added_children"].append(text_all)
                else:
                    unmatched.append({"issue": issue, "first": lines[top][:80], "hits": []})
                continue
            if top in add:
                maxno[num] = maxno.get(num, 0) + 1
                iid = f"K{num}-{maxno[num]:03d}"
                new_items.append(
                    {
                        "id": iid,
                        "issue": issue,
                        "section": b["section"],
                        "text": text_all,
                        "added": today,
                    }
                )
            else:
                hits = by_first.get((issue, lines[top]), [])
                if len(hits) == 1:
                    it = hits[0]
                    appended[it["id"]] = {
                        "id": it["id"],
                        "new_text": text_all,
                        "added_children": [lines[r].strip() for r in new_kids],
                    }
                else:
                    if hits:
                        unmatched.append(
                            {
                                "issue": issue,
                                "first": lines[top][:80],
                                "hits": [h["id"] for h in hits],
                            }
                        )
                    maxno[num] = maxno.get(num, 0) + 1
                    iid = f"K{num}-{maxno[num]:03d}"
                    # 台帳に無い親へ足された子は、親の1行目と足した子を1件にする
                    new_items.append(
                        {
                            "id": iid,
                            "issue": issue,
                            "section": b["section"],
                            "text": "\n".join([lines[top]] + [lines[r] for r in new_kids]),
                            "added": today,
                            "parent_existing": True,
                        }
                    )

    ids = [i["id"] for i in base] + [i["id"] for i in new_items]
    dup = [k for k, v in Counter(ids).items() if v > 1]
    if dup:
        raise ValueError(f"ID が重複している: {dup}")
    return {"new": new_items, "appended": list(appended.values()), "unmatched": unmatched}


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="knowledge_ledger.delta")
    for name in ("worktree", "base", "out"):
        ap.add_argument(name)
    ap.add_argument("--today", required=True, help="追加の日付 (YYYY-MM-DD)")
    a = ap.parse_args(argv)
    base = json.loads(Path(a.base).read_text(encoding="utf-8"))
    delta = build_delta(a.worktree, base, a.today)
    Path(a.out).write_text(json.dumps(delta, ensure_ascii=False, indent=1), encoding="utf-8")
    print(
        "new",
        len(delta["new"]),
        "appended",
        len(delta["appended"]),
        "unmatched",
        len(delta["unmatched"]),
    )
    print(Counter(i["issue"] for i in delta["new"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
