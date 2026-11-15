"""判断の保存先の写しから、Issue ごとの採否の表 (<ID>-decisions.md) を生成する。

使い方:
  python -m knowledge_ledger.records <repo> <items.json> <decisions-dir> --snapshot YYYY-MM-DD
- decisions-dir は判断の保存先の写し (ArtifactData の out_dir)。ファイル名が件の ID
- 理由の文面と人のメモは追跡下へ出さない。判断の保存先が持つ
- issue.md には書かない。台帳の差分抽出が issue.md の節と箇条を読むため
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HEAD_LEN = 40
HEADER = (
    "| 件 | 箇条の冒頭 | 採否 | 判断した側 | 記号 | 反映先 |\n| --- | --- | --- | --- | --- | --- |"
)


def _cell(s: str) -> str:
    return s.replace("|", "\\|")


def _head(text: str) -> str:
    # 表の行から取った原文は既に `\\|` を持つ。逃がしを戻してから切り、_cell で1回だけ逃がす
    first = text.split("\n")[0].removeprefix("- ").replace("\\|", "|")
    return first if len(first) <= HEAD_LEN else first[:HEAD_LEN] + "…"


def _row(item: dict[str, Any], doc: dict[str, Any] | None) -> str:
    doc = doc or {}
    d = doc.get("decision")
    if not d:
        tail = ["まだ", "", "", ""]
    elif doc.get("decidedBy") == "claude":
        tail = [d, "Claude", doc.get("claudeRule") or "", doc.get("claudeDest") or ""]
    else:
        tail = [d, "人", "", ""]
    cols = [item["id"], _head(item["text"]), *tail]
    return "| " + " | ".join(_cell(c) for c in cols) + " |"


def render(
    issue: str, items: list[dict[str, Any]], decisions: dict[str, dict[str, Any]], snapshot: str
) -> str:
    rows = [_row(i, decisions.get(i["id"])) for i in sorted(items, key=lambda i: i["order"])]
    return (
        f"# {issue} の採否 ({snapshot} に判断の保存先から写した)\n\n"
        "この表は `knowledge_ledger.records` が台帳の判断の保存先から生成する。手で直さない。"
        "記号の意味は ISSUE-146-spec.md の判定表が持ち、理由の文面は判断の保存先が持つ。\n\n"
        + HEADER + "\n" + "\n".join(rows) + "\n"
    )  # fmt: skip


def issue_dir(repo: str | Path, issue: str) -> Path:
    """Issue のディレクトリ。active を先に、無ければ closed を探す"""
    base = Path(repo) / "docs/issues"
    for parent in (base, base / "closed"):
        hits = sorted(parent.glob(f"{issue}_*"))
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:
            raise ValueError(f"{issue} のディレクトリが複数ある: {hits}")
    raise ValueError(f"{issue} のディレクトリが無い")


def load_decisions(ddir: str | Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for f in sorted(Path(ddir).glob("*.json")):
        out[f.stem] = json.loads(f.read_text(encoding="utf-8"))
    return out


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="knowledge_ledger.records")
    for name in ("repo", "items", "decisions"):
        ap.add_argument(name)
    ap.add_argument("--snapshot", required=True, help="写した日 (YYYY-MM-DD)")
    a = ap.parse_args(argv)
    items = json.loads(Path(a.items).read_text(encoding="utf-8"))
    decisions = load_decisions(a.decisions)
    unknown = sorted(set(decisions) - {i["id"] for i in items})
    if unknown:
        raise ValueError(f"台帳に無い ID の判断がある: {unknown}")
    by_issue: dict[str, list[dict[str, Any]]] = {}
    for i in items:
        by_issue.setdefault(i["issue"], []).append(i)
    for issue, its in sorted(by_issue.items()):
        out = issue_dir(a.repo, issue) / f"{issue}-decisions.md"
        out.write_text(render(issue, its, decisions, a.snapshot), encoding="utf-8")
    print(len(by_issue), "件の Issue に書いた")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
