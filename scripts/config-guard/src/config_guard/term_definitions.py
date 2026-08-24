"""rules が定義する語が、定義の届かない層で使われていないかの検査。

規範を rules へ切り出すと、語の操作的定義も一緒に移る。移設先の rules が注入されない
文脈では語だけが常時層に残り、定義が届かない。実際に `変異注入` が委譲カテゴリに残った
まま定義だけ testing-practices へ移った状態が起き、レビューで見つかった (Issue #36 の
「移した先にしか定義が無い語が常時層に残る」節)。

母集団は「テストファイルを Read せずに到達しうる集合」で、instruction_refs が参照検査に
使う集合をそのまま使う。再宣言すると参照検査と語の検査が別の規約で別の集合を見たまま
両方緑になる。

外すのは語を宣言した rules 自身だけ。定義を書いてある当のファイルなので、含めると宣言が
毎回報告される。他の rules は外さない。paths が違う rules は同時に注入されないので、
そこでの使用は CLAUDE.md での使用と同じく定義が届かない。

「出現している」と「定義が届いていない」は機械には区別できない。括弧で操作的定義を
併記した箇所も、定義の所在を名指しした箇所も、語としては同じに見える。そこで出現のうち
手当て済みのものを `ACKNOWLEDGED` へ理由ごと記録し、新しい出現だけが報告される形にした。

免除は緩める方向の変更なので、実態から乖離した免除も報告する。語を宣言から外したり
出現を消したりしたあと免除だけが残ると、検査が静かに緩んだことに誰も気づけない。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.instruction_budget import (
    RULES_GLOB,
    is_always_loaded_rule,
    rule_files,
    rule_frontmatter,
)
from config_guard.instruction_refs import SOURCE_GLOBS
from config_guard.models import Finding

_RULES_DIR = RULES_GLOB.rsplit("/", 1)[0]

# 母集団での出現のうち、定義が届く形になっていると確認したもの。
# (語, リポジトリ相対パス) -> なぜ問題にならないか。
# 新しい出現は報告されるので、手当てしてからここへ足す。
ACKNOWLEDGED: dict[tuple[str, str], str] = {
    ("変異注入", "home/.claude/CLAUDE.md"): "委譲カテゴリの当該行が括弧で操作的定義を併記している",
    ("変異注入", "home/.claude/references/observation.md"): (
        "定義を持つ場所を名指ししている (定義を書き足すと三重管理になる)"
    ),
    ("変異注入", "home/.claude/references/testing.md"): (
        "testing-practices が冒頭で名指しする読み先なので、rules と同じ文脈でしか読まれない"
    ),
    ("dead pin", "home/.claude/references/observation.md"): "定義を持つ場所を名指ししている",
    ("dead pin", "home/.claude/references/testing.md"): (
        "testing-practices の読み先なので、rules と同じ文脈でしか読まれない"
    ),
}


def rule_defines(text: str) -> list[str]:
    """rules の frontmatter が宣言する defines を返す。無い・型が違うときは空リスト。

    リストでない値を 1 要素として扱わないのは、`defines: "a"` を通すと語が 1 文字ずつ
    検索され、本文のあらゆる箇所に当たるため。要素も str 以外は落とす (YAML は `12` を
    int で読むので、str へ落として検索すると本文の数字へ無関係に当たる)。
    落とした事実そのものは `malformed_defines` が報告する。
    """
    front = rule_frontmatter(text)
    if front is None:
        return []
    declared = front.get("defines")
    if not isinstance(declared, list):
        return []
    return [d for d in declared if isinstance(d, str)]


def malformed_defines(text: str) -> object | None:
    """`defines` を宣言しているのに文字列のリストでないとき、その値を返す。正しければ None。

    キー自体が無いのは正当なので None。型違いを黙って捨てると、その rules について語の
    検査だけが永久に沈黙する。paths は正しいままなので rules_paths も赤くならず、
    「宣言したのに一度も見られていない」状態がどの検査からも見えない。
    """
    front = rule_frontmatter(text)
    if front is None or "defines" not in front:
        return None
    declared = front["defines"]
    if isinstance(declared, list) and all(isinstance(d, str) for d in declared):
        return None
    return declared


def declared_terms(repo_root: str) -> dict[str, str]:
    """rules が宣言する語を {語: 宣言した rules のリポジトリ相対パス} で返す。

    paths を持たない rules は session_start で常時ロードされる (instruction_budget が
    予算へ計上する層と同じ) ので、そこが宣言した語は定義が必ず届く。検査すると全ての
    出現が偽陽性になり、意味のない免除だけが増える。
    """
    return {
        term: f"{_RULES_DIR}/{name}"
        for name, text in rule_files(repo_root).items()
        if not is_always_loaded_rule(text)
        for term in rule_defines(text)
    }


def population_files(repo_root: str) -> dict[str, str]:
    """母集団のファイルを {リポジトリ相対パス: 本文} で返す。"""
    root = Path(repo_root)
    return {
        str(path.relative_to(root)): path.read_text(encoding="utf-8")
        for pattern in SOURCE_GLOBS
        for path in sorted(root.glob(pattern))
    }


def check_term_definitions(
    repo_root: str,
    acknowledged: dict[tuple[str, str], str] | None = None,
) -> list[Finding]:
    """rules が定義する語が母集団に出現していないかを検査する。

    rules ディレクトリが無いリポジトリは対象外にする。`scan()` は任意のルートへ走るので、
    rules を管理していないリポジトリへ語の検査をしても意味がない。
    """
    if not (Path(repo_root) / _RULES_DIR).is_dir():
        return []

    exempt = ACKNOWLEDGED if acknowledged is None else acknowledged
    terms = declared_terms(repo_root)

    findings: list[Finding] = []

    for name, text in sorted(rule_files(repo_root).items()):
        declared = malformed_defines(text)
        if declared is not None:
            findings.append(
                Finding(
                    f"{_RULES_DIR}/{name}",
                    f"defines: {declared!r}",
                    "defines が文字列のリストではない。この形は黙って捨てられるので、"
                    "宣言したつもりの語がどこからも検査されない状態になる",
                )
            )

    seen: set[tuple[str, str]] = set()

    for rel, text in population_files(repo_root).items():
        for term, origin in sorted(terms.items()):
            # 宣言した rules 自身は定義を書いてある側なので、出現しているのが正しい
            if rel == origin or term not in text:
                continue
            seen.add((term, rel))
            if (term, rel) in exempt:
                continue
            findings.append(
                Finding(
                    rel,
                    term,
                    f"この語の定義は {origin} にあり、そこは条件付きロードなので届かない"
                    "ことがある。定義を併記するか所在を名指しし、"
                    f"手当てしたら {__name__} の ACKNOWLEDGED へ理由ごと足すこと",
                )
            )

    # 免除の乖離。実態を指さない免除が残ると、検査が緩んだことに気づけない。
    # 出現が消えた場合と宣言から語が落ちた場合で手当てが逆になるので、文言を分ける
    for term, rel in sorted(exempt):
        if (term, rel) in seen:
            continue
        if term in terms:
            message = (
                f"免除が実態と合っていない。{rel} にこの語は出現しないので、"
                f"{__name__} の ACKNOWLEDGED から消すこと"
            )
        else:
            message = (
                "免除が実態と合っていない。この語は rules の defines で宣言されていない。"
                f"宣言から落ちたのが誤りなら戻し、意図して外したなら {__name__} の "
                "ACKNOWLEDGED から消すこと"
            )
        findings.append(Finding(rel, term, message))

    return findings
