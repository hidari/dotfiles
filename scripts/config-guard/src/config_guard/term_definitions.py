"""rules が定義する語が、定義の届かない層で使われていないかの検査。

規範を rules へ切り出すと、語の操作的定義も一緒に移る。移設先の rules が注入されない
文脈では語だけが常時層に残り、定義が届かない。実際に `変異注入` が委譲カテゴリに残った
まま定義だけ testing-practices へ移った状態が起き、レビューで見つかった (Issue #36 の
「移した先にしか定義が無い語が常時層に残る」節)。

母集団は `instruction_refs` が参照検査に使う集合をそのまま使う。再宣言すると参照検査と
語の検査が別の規約で別の集合を見たまま両方緑になる。母集団から外すのは宣言元の rules
1 ファイルだけで、理由は除外している分岐が持つ。

「出現している」と「定義が届いていない」は機械には区別できない。括弧で操作的定義を
併記した箇所も、定義の所在を名指しした箇所も、語としては同じに見える。そこで出現のうち
手当て済みのものを `ACKNOWLEDGED` へ理由ごと記録し、新しい出現だけが報告される形にした。

既知の限界: 照合は本文全体への部分文字列一致で、コードフェンス・インラインコード・
frontmatter を区別しない。語境界は CJK に無いので regex を挟んでも近似の精度は上がらない。
誤って報告する側へ倒れるぶんには免除で吸収できるので、その方向のまま置いている。
"""

from __future__ import annotations

from typing import TypeGuard

from config_guard.instruction_budget import (
    RULES_DIR,
    has_rules_dir,
    is_always_loaded_rule,
    rule_body,
    rule_files,
    rule_frontmatter,
)
from config_guard.instruction_refs import source_files
from config_guard.models import Finding

# 手当てが「名指し」で揃っているのは、references へ定義を書き足すと rules と
# references の二重管理になるため。同じ事実には同じ文字列を使う
_NAMES_THE_DEFINITION = "定義を持つ場所を名指ししている"

# 母集団での出現のうち、定義が届く形になっていると確認したもの。
# (語, リポジトリ相対パス) -> なぜ問題にならないか。
# 新しい出現は報告されるので、手当てしてからここへ足す。
ACKNOWLEDGED: dict[tuple[str, str], str] = {
    ("変異注入", "home/.claude/CLAUDE.md"): "委譲カテゴリの当該行が括弧で操作的定義を併記している",
    ("変異注入", "home/.claude/references/observation.md"): _NAMES_THE_DEFINITION,
    ("変異注入", "home/.claude/references/testing.md"): _NAMES_THE_DEFINITION,
    ("dead pin", "home/.claude/references/observation.md"): _NAMES_THE_DEFINITION,
    ("dead pin", "home/.claude/references/testing.md"): _NAMES_THE_DEFINITION,
}


def _is_term_list(value: object) -> TypeGuard[list[str]]:
    """`defines` として正しい形かを返す。

    文字列を 1 要素として受けると語が 1 文字ずつ検索され、本文のあらゆる箇所に当たる。
    要素も str に限る (YAML は `12` を int で読むので、str へ落として検索すると本文の
    数字へ無関係に当たる)。判定をここに 1 つだけ置くのは、正しい形の定義が 2 箇所に
    散ると片方だけを緩めたときに両方緑で通るため。
    """
    return isinstance(value, list) and all(isinstance(d, str) for d in value)


def rule_defines(text: str) -> list[str]:
    """rules の frontmatter が宣言する defines を返す。無い・形が違うときは空リスト。"""
    declared = (rule_frontmatter(text) or {}).get("defines")
    return declared if _is_term_list(declared) else []


def malformed_defines(text: str) -> object | None:
    """`defines` を宣言しているのに形が違うとき、その値を返す。正しい・無いときは None。

    黙って捨てると、その rules が宣言したはずの語だけが検査されない状態になる。
    paths は正しいままなので rules_paths も赤くならず、どの検査からも見えない。
    """
    front = rule_frontmatter(text) or {}
    if "defines" not in front or _is_term_list(front["defines"]):
        return None
    return front["defines"]


def declared_terms(rules: dict[str, str]) -> dict[str, str]:
    """rules が宣言する語を {語: 宣言した rules のリポジトリ相対パス} で返す。

    paths を持たない rules は session_start で常時ロードされる (instruction_budget が
    予算へ計上する層と同じ) ので、そこが宣言した語は定義が必ず届く。検査すると全ての
    出現が偽陽性になるため外すが、外したこと自体は `check_term_definitions` が報告する。
    """
    return {
        term: f"{RULES_DIR}/{name}"
        for name, text in rules.items()
        if not is_always_loaded_rule(text)
        for term in rule_defines(text)
    }


def _check_declarations(rules: dict[str, str]) -> list[Finding]:
    """宣言そのものの形と、宣言が実態を指しているかを検査する。"""
    findings: list[Finding] = []
    for name, text in rules.items():
        source = f"{RULES_DIR}/{name}"
        declared = malformed_defines(text)
        if declared is not None:
            findings.append(
                Finding(
                    source,
                    f"defines: {declared!r}",
                    "defines が文字列のリストではない。この形は黙って捨てられるので、"
                    "宣言したつもりの語がどこからも検査されない状態になる",
                )
            )
        if rule_defines(text) and is_always_loaded_rule(text):
            findings.append(
                Finding(
                    source,
                    "defines",
                    "paths を持たない rules は常時ロードされるので、宣言しても定義は必ず届く。"
                    "宣言は黙って捨てられるため、scoped にするか defines を消すこと",
                )
            )
        body = rule_body(text)
        for term in rule_defines(text):
            if term not in body:
                findings.append(
                    Finding(
                        source,
                        term,
                        "宣言した語が本文に無い。綴り違いか定義を消したかで、"
                        "この語はどこで使われても報告されない状態になっている",
                    )
                )
    return findings


def check_term_definitions(
    repo_root: str,
    acknowledged: dict[tuple[str, str], str] | None = None,
) -> list[Finding]:
    """rules が定義する語が母集団に出現していないかを検査する。

    rules ディレクトリが無いリポジトリは対象外にする (判定は `has_rules_dir`)。
    """
    if not has_rules_dir(repo_root):
        return []

    exempt = ACKNOWLEDGED if acknowledged is None else acknowledged
    rules = rule_files(repo_root)
    terms = declared_terms(rules)

    findings = _check_declarations(rules)

    # 出現を先に集合として作る。報告の副作用で組み立てると、免除の乖離検査が
    # 「報告ループが母集団を最後まで回ったこと」に暗黙依存する
    occurrences = {
        (term, rel)
        for rel, text in source_files(repo_root).items()
        for term, origin in terms.items()
        # 宣言した rules 自身は定義を書いてある側なので、出現しているのが正しい
        if rel != origin and term in text
    }

    for term, rel in sorted(occurrences - set(exempt)):
        findings.append(
            Finding(
                rel,
                term,
                f"この語の定義は {terms[term]} にあり、そこは条件付きロードなので届かない"
                "ことがある。定義を併記するか所在を名指しし、"
                f"手当てしたら {__name__} の ACKNOWLEDGED へ理由ごと足すこと",
            )
        )

    # 実態を指さない免除が残ると、検査が緩んだことに気づけない。
    # 出現が消えた場合と宣言から語が落ちた場合で手当てが逆になるので、文言を分ける
    for term, rel in sorted(set(exempt) - occurrences):
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
