"""census の参照を族分類に当てて、族の内側と族またぎへ機械的に振り分ける。

族分類の草案が持つ散文リストは手で数えたもので、見つけた分しか載らない。
canonical は cross-reference-census.json 側に置き、族への振り分けはここで生成する。

使い方 (引数は省略可、既定はこのファイルと同じディレクトリ):
    python3 classify-crossrefs.py [family-classification.md] [cross-reference-census.json]
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DRAFT = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE / "family-classification.md"
CENSUS = (
    Path(sys.argv[2]) if len(sys.argv) > 2 else HERE / "cross-reference-census.json"
)

ID_PAT = re.compile(r"H\d+-\d+")
ENUM_LINE = re.compile(r"^[H0-9\-,\s]+$")


def load_family_map(draft):
    """草案から ID -> 族名 のマップを作る。

    見出し名の literal ではなく「ID 列挙行」と「表の ID セル」という形で拾う。
    見出しを直したときに黙って 0 件になるのを避けるため。
    """
    family = {}
    section = None
    for line in draft.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("## "):
            section = stripped[3:]
            continue
        if stripped.startswith("### "):
            section = stripped[4:]
            continue
        if not stripped:
            continue
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if cells and ID_PAT.fullmatch(cells[0]):
                family[cells[0]] = section
            continue
        if ENUM_LINE.match(stripped):
            for found in ID_PAT.findall(stripped):
                family[found] = section
    return family


def short(sec):
    """「verification-signal (21 項目 / 最大の族)」を「verification-signal」へ。

    族に番号は振らない。番号は繰り下がるたびに参照が壊れるので、見出しの飾りとしても
    持たせていない。
    """
    if sec is None:
        return "未割り当て"
    m = re.match(r"^([\w-]+)", sec)
    return m.group(1) if m else sec


family = load_family_map(DRAFT)
census = json.loads(CENSUS.read_text(encoding="utf-8"))
refs = census["references"]

inside, across, unknown_target, unassigned = [], [], [], []
for rec in refs:
    if not rec["breaks_on_split"]:
        continue
    src = rec["from_id"]
    for dst in rec["to_ids"]:
        if not ID_PAT.fullmatch(dst):
            unknown_target.append((src, dst, rec["kind"]))
            continue
        fs, fd = family.get(src), family.get(dst)
        # 片方でも族マップに無いと fs == fd が None == None で真になり、族の内側へ
        # 紛れ込む。ID 集合の入れ替わりは実際に起きるので別枠へ落とす
        if fs is None or fd is None:
            unassigned.append((src, dst, short(fs), short(fd), rec["kind"]))
            continue
        row = (src, dst, short(fs), short(fd), rec["kind"])
        (inside if fs == fd else across).append(row)

print(
    f"census breaks_on_split=true: {sum(1 for r in refs if r['breaks_on_split'])} レコード"
)
print(f"  ID へのエッジに展開: {len(inside) + len(across)}")
print(f"  ID ではない参照先: {len(unknown_target)}")
for src, dst, kind in unknown_target:
    print(f"    {src} -> {dst!r} ({kind})")
print(f"  族マップで解決できない ID: {len(unassigned)}")
for src, dst, fs, fd, kind in unassigned:
    print(f"    {src} [{fs}] -> {dst} [{fd}]  ({kind})")
print()

print(f"族の内側に収まるエッジ: {len(inside)}")
for src, dst, fs, _fd, kind in sorted(inside):
    print(f"  {src} -> {dst}  [{fs}]  ({kind})")
print()

print(f"族をまたぐエッジ: {len(across)}")
for src, dst, fs, fd, kind in sorted(across):
    print(f"  {src} -> {dst}  [{fs}] -> [{fd}]  ({kind})")
print()

# 草案の箇条書きは発信項目の単位で書かれているので、束の数も出す
bundles = {}
for src, dst, fs, fd, _kind in across:
    bundles.setdefault((src, fs), []).append((dst, fd))
print(f"族をまたぐ束 (発信項目でまとめた数): {len(bundles)}")
for (src, fs), targets in sorted(bundles.items()):
    dsts = ", ".join(f"{d} [{f}]" for d, f in sorted(targets))
    print(f"  {src} [{fs}] -> {dsts}")
