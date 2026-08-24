"""term_definitions の仕様テスト。

rules が `defines` で宣言した語が、定義の届かない層 (CLAUDE.md + references) に
出現していないかを検査する。出現のうち手当て済みのものは免除へ理由ごと記録し、
新しい出現だけが報告される。免除が実態から乖離した場合も報告する。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.models import Finding
from config_guard.term_definitions import (
    ACKNOWLEDGED,
    check_term_definitions,
    declared_terms,
    rule_defines,
)
from tests.conftest import REPO_ROOT, write_file

RULES_DIR = "home/.claude/rules"
CLAUDE_MD = "home/.claude/CLAUDE.md"
REFERENCES = "home/.claude/references"

TERM = "架空の造語ゼペット"


def _rule(defines: list[str] | None, paths: list[str] | None = None) -> str:
    lines = ["---"]
    if paths is not None:
        joined = ", ".join(f'"{p}"' for p in paths)
        lines.append(f"paths: [{joined}]")
    if defines is not None:
        joined = ", ".join(f'"{d}"' for d in defines)
        lines.append(f"defines: [{joined}]")
    lines += ["---", "", "# rule", "", f"- {TERM} とは、そういうものである", ""]
    return "\n".join(lines)


def _repo(tmp_path: Path, *, rule: str, claude_md: str = "# CLAUDE\n") -> str:
    write_file(tmp_path, f"{RULES_DIR}/testing-practices.md", rule)
    write_file(tmp_path, CLAUDE_MD, claude_md)
    return str(tmp_path)


def _check(root: str) -> list[Finding]:
    """免除を空にして呼ぶ。

    既定の `ACKNOWLEDGED` は実リポジトリの出現を指すので、tmp_path に対しては
    全件が「免除の乖離」として報告される。既定値そのものの検証は
    `test_real_repo_is_clean` が実リポジトリに対して行う。
    """
    return check_term_definitions(root, acknowledged={})


# -----------------------------------------------------------------------------
# rule_defines (pure)
# -----------------------------------------------------------------------------


def test_defines_is_read_from_frontmatter() -> None:
    assert rule_defines(_rule(["a", "b"])) == ["a", "b"]


def test_missing_defines_is_empty() -> None:
    assert rule_defines(_rule(None, paths=["**/*.md"])) == []


def test_broken_frontmatter_is_empty() -> None:
    assert rule_defines("paths: [\n---\n# no frontmatter open\n") == []


def test_non_list_defines_is_empty() -> None:
    # 型が違う宣言を黙って 1 要素として扱うと、語が 1 文字ずつ検索される
    assert rule_defines('---\ndefines: "a"\n---\n') == []


def test_non_string_element_is_dropped() -> None:
    # YAML は 12 を int で読む。str へ落として検索すると本文の数字に無関係に当たる
    assert rule_defines('---\ndefines: ["a", 12]\n---\n') == ["a"]


# -----------------------------------------------------------------------------
# check_term_definitions (pure)
# -----------------------------------------------------------------------------


def test_term_absent_from_population_is_clean(tmp_path: Path) -> None:
    root = _repo(tmp_path, rule=_rule([TERM]))
    assert _check(root) == []


def test_term_present_in_claude_md_is_reported(tmp_path: Path) -> None:
    root = _repo(tmp_path, rule=_rule([TERM]), claude_md=f"# CLAUDE\n\n- {TERM} を使うこと\n")
    findings = _check(root)
    assert len(findings) == 1
    assert findings[0].source == CLAUDE_MD
    assert findings[0].detail == TERM
    assert f"{RULES_DIR}/testing-practices.md" in findings[0].message


def test_term_present_in_references_is_reported(tmp_path: Path) -> None:
    root = _repo(tmp_path, rule=_rule([TERM]))
    write_file(tmp_path, f"{REFERENCES}/observation.md", f"# obs\n\n{TERM} で確かめる\n")
    findings = _check(root)
    assert [f.source for f in findings] == [f"{REFERENCES}/observation.md"]


def test_occurrence_inside_rules_is_not_reported(tmp_path: Path) -> None:
    # rules は定義を持つ側なので母集団から外れる。ここを含めると宣言自体が毎回報告される
    root = _repo(tmp_path, rule=_rule([TERM]))
    write_file(tmp_path, f"{RULES_DIR}/other.md", f'---\npaths: ["**/*.x"]\n---\n\n{TERM}\n')
    assert _check(root) == []


def test_rule_without_defines_contributes_nothing(tmp_path: Path) -> None:
    root = _repo(
        tmp_path,
        rule=_rule(None, paths=["**/*.md"]),
        claude_md=f"# CLAUDE\n\n- {TERM} を使うこと\n",
    )
    assert _check(root) == []


def test_multiple_terms_are_reported_independently(tmp_path: Path) -> None:
    other = "架空の造語ダイダロス"
    root = _repo(
        tmp_path,
        rule=_rule([TERM, other]),
        claude_md=f"# CLAUDE\n\n- {TERM} と {other} を使う\n",
    )
    findings = _check(root)
    assert sorted(f.detail for f in findings) == sorted([TERM, other])


def test_missing_rules_dir_is_out_of_scope(tmp_path: Path) -> None:
    # scan() は任意のルートへ走るので、rules を持たないリポジトリは対象外
    write_file(tmp_path, CLAUDE_MD, f"# CLAUDE\n\n{TERM}\n")
    assert check_term_definitions(str(tmp_path)) == []


# -----------------------------------------------------------------------------
# 免除 (ACKNOWLEDGED)
# -----------------------------------------------------------------------------


def test_acknowledged_occurrence_is_suppressed(tmp_path: Path) -> None:
    root = _repo(tmp_path, rule=_rule([TERM]), claude_md=f"# CLAUDE\n\n- {TERM}\n")
    assert check_term_definitions(root, acknowledged={(TERM, CLAUDE_MD): "理由"}) == []


def test_acknowledged_entry_without_occurrence_is_reported(tmp_path: Path) -> None:
    # 免除が実態から乖離したまま残ると、検査が静かに緩んだことに誰も気づけない
    root = _repo(tmp_path, rule=_rule([TERM]))
    findings = check_term_definitions(root, acknowledged={(TERM, CLAUDE_MD): "理由"})
    assert len(findings) == 1
    assert findings[0].source == CLAUDE_MD
    assert "免除" in findings[0].message


def test_acknowledged_only_suppresses_its_own_file(tmp_path: Path) -> None:
    # 免除はファイル単位。1 箇所を免除したら他のファイルでの出現まで黙るのは緩すぎる
    root = _repo(tmp_path, rule=_rule([TERM]), claude_md=f"# CLAUDE\n\n- {TERM}\n")
    write_file(tmp_path, f"{REFERENCES}/observation.md", f"# obs\n\n{TERM}\n")
    findings = check_term_definitions(root, acknowledged={(TERM, CLAUDE_MD): "理由"})
    assert [f.source for f in findings] == [f"{REFERENCES}/observation.md"]


def test_acknowledged_for_undeclared_term_is_reported(tmp_path: Path) -> None:
    # 宣言から語を消したのに免除だけ残る形。免除が実態を指さない点で上と同種
    root = _repo(tmp_path, rule=_rule([]), claude_md=f"# CLAUDE\n\n- {TERM}\n")
    findings = check_term_definitions(root, acknowledged={(TERM, CLAUDE_MD): "理由"})
    assert len(findings) == 1
    assert "免除" in findings[0].message


# -----------------------------------------------------------------------------
# 実リポジトリ
# -----------------------------------------------------------------------------


def test_real_repo_is_clean() -> None:
    assert check_term_definitions(str(REPO_ROOT)) == []


def test_real_repo_declares_terms() -> None:
    # 宣言が 0 件だと上のテストは何も見ずに緑になる。検査が実際に語を見ていることを縛る
    assert declared_terms(str(REPO_ROOT)), "rules が defines を 1 つも宣言していない"


def test_real_repo_acknowledgements_are_not_empty() -> None:
    # 免除が空だと「免除の乖離」検査が実リポジトリに対して一度も働かない
    assert ACKNOWLEDGED, "免除が空。移設で語が漏れた実績があるので、空なら宣言側を疑う"
