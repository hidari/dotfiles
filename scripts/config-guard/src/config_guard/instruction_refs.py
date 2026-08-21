"""指示ファイルどうしの参照が実在するかを検査する。

参照は 2 種類ある。どちらも壊れ方が「探すと 0 件」の沈黙で、改名や移動をしても
誰も赤くならない。

- パス参照: `~/.claude/<path>` が repo の `home/.claude/<path>` に実在するか
- 見出し参照: `~/.claude/<file>` の「<name>」 の <name> が <file> の見出しに実在するか

`markdown_links` はインラインコードを除去してからリンクを探すので、この 2 種はどちらも
1 件も見えない。捨てている領域がこちらの検査対象そのものなので、隣に別モジュールを置く。

参照先を CLAUDE.md へ決め打ちしない。rules を指す references が実在するため。
見出しレベルも決め打ちしない (CLAUDE.md のカテゴリは H2、rules の見出しは H1)。

既知の限界: regex による近似であり Markdown パーサではない。バッククォート記法で
書かれた参照だけを見るので、素の散文中に書かれた参照は検査から漏れる (このリポジトリの
参照は全てバッククォート記法で、素の言及と参照を記法以外で区別できない)。
閉じないフェンスは以降を skip する (検出漏れ側)。
"""

from __future__ import annotations

import re
from pathlib import Path

from config_guard.instruction_budget import CLAUDE_MD_PATH, RULES_GLOB
from config_guard.models import Finding

HOME_PREFIX = "~/.claude/"
REPO_PREFIX = "home/.claude/"

# 検査対象。ここを広げると Issue ドキュメントの「撤去済みプローブへの言及」まで
# 拾って誤検出になる。母集団は常時層と、そこから名指しされる先。
#
# home/.claude/**/*.md へまとめない。glob はファイルシステムを見るので、apm の deploy 先
# である home/.claude/skills/ を巻き込む (gitignore されていても実体は在る)。
# 明示リストの取りこぼしは tests の test_real_repo_covers_every_tracked_instruction_file が縛る。
#
# 常時層の 2 つは instruction_budget が canonical を持つ。再宣言すると、予算検査と
# 参照検査が別の規約で別の集合を見たまま両方緑になる
SOURCE_GLOBS = (CLAUDE_MD_PATH, RULES_GLOB, "home/.claude/references/*.md")

_INLINE_CODE = re.compile(r"`([^`]*)`")
_FENCE = re.compile(r"^\s*(`{3,})")
_HEADING = re.compile(r"^#{1,6}\s+(.*?)\s*$")

# 見出し行頭の強度ラベル。参照側は本文だけを書くので、比較の前に落とす
_STRENGTH_LABEL = re.compile(r"^\[[A-Z ]+\]\s*")

# 見出し参照。バッククォートで囲んだファイル参照の直後に鉤括弧が続く形だけを見る。
# 鉤括弧は本文でも使うので、ファイル参照とセットであることを要求する
_HEADING_REF = re.compile(r"`(" + re.escape(HOME_PREFIX) + r"[^`]*)`\s*の\s*「([^」]+)」")

# 実在を問えない参照。理由ごと持たせないと、次に見た人が「漏れている」と判断して足す
UNCHECKABLE: dict[str, str] = {
    "<": "穴埋めのプレースホルダ (<plugin 名> 等) で、実体を持たない",
    "*": "glob のパターンであってパスではない",
}


def prose_lines(text: str) -> list[str]:
    """コードフェンス内を除いた行を返す。

    フェンス内は例示で、実在しないパスや見出しを書くことがある。本文を読む 3 つ
    (参照 2 種と見出し) が別々にフェンスを判定すると、一部だけが例示を拾って誤検出
    または fail-open になるので判定をここへ 1 つ置く。
    閉じないままファイル末尾に達したフェンスは以降を skip する (検出漏れ側)。
    """
    lines: list[str] = []
    fence: str | None = None

    for line in text.split("\n"):
        opener = _FENCE.match(line)
        if fence is not None:
            if opener and opener.group(1).startswith(fence):
                fence = None
            continue
        if opener:
            fence = opener.group(1)
            continue
        lines.append(line)

    return lines


def extract_home_refs(text: str) -> list[str]:
    """インラインコード内の `~/.claude/...` を記法のまま返す。"""
    return [
        match
        for line in prose_lines(text)
        for match in _INLINE_CODE.findall(line)
        if match.startswith(HOME_PREFIX)
    ]


def is_checkable_ref(ref: str) -> bool:
    """実在を問える参照かを返す。除外の理由は UNCHECKABLE が持つ。"""
    return not any(mark in ref for mark in UNCHECKABLE)


def repo_path(ref: str) -> str:
    """`~/.claude/X` を `home/.claude/X` へ写す。~ は live 側の配置を指すため。"""
    return REPO_PREFIX + ref[len(HOME_PREFIX) :]


def extract_heading_refs(text: str) -> list[tuple[str, str]]:
    """`~/.claude/<file>` の「<name>」 の形から (file, name) を返す。

    ファイル参照と鉤括弧は改行をまたいでよい (実物が折り返している) ので、行ごとではなく
    フェンスを除いた本文全体へ当てる。
    """
    return _HEADING_REF.findall("\n".join(prose_lines(text)))


def heading_names(text: str) -> set[str]:
    """Markdown の見出しから強度ラベルを落とした名前の集合を返す。"""
    return {
        _STRENGTH_LABEL.sub("", m.group(1))
        for line in prose_lines(text)
        if (m := _HEADING.match(line))
    }


def source_files(repo_root: str) -> dict[str, str]:
    """SOURCE_GLOBS に一致する指示ファイルを {リポジトリ相対パス: 本文} で返す。"""
    root = Path(repo_root)
    return {
        str(path.relative_to(root)): path.read_text(encoding="utf-8")
        for pattern in SOURCE_GLOBS
        for path in sorted(root.glob(pattern))
    }


def check_instruction_refs(repo_root: str) -> list[Finding]:
    """指示ファイルどうしの参照が実在するかを検査する。"""
    root = Path(repo_root)
    findings: list[Finding] = []

    for rel, text in source_files(repo_root).items():
        for ref in extract_home_refs(text):
            if is_checkable_ref(ref) and not (root / repo_path(ref)).exists():
                findings.append(
                    Finding(
                        rel,
                        ref,
                        "参照先が実在しない。改名や移動をしても参照側は変更されないので、"
                        "探すと 0 件という沈黙で壊れる",
                    )
                )

        for file_ref, name in extract_heading_refs(text):
            if not is_checkable_ref(file_ref):
                continue
            target = root / repo_path(file_ref)
            # 参照先そのものが無いケースは上のループが既に報告している。見出し参照の
            # ファイル名は必ずインラインコードなので、そちらから漏れることはない
            if not target.is_file():
                continue
            if name not in heading_names(target.read_text(encoding="utf-8")):
                findings.append(
                    Finding(
                        rel,
                        f"{file_ref} 「{name}」",
                        "参照先にその見出しが無い。見出しを書き換えても参照側は変更されないので、"
                        "探すと 0 件という沈黙で壊れる",
                    )
                )

    return findings
