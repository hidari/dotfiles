"""term_definitions の仕様テスト。

rules が `defines` で宣言した語が、定義の届かない層に出現していないかを検査する。
宣言そのものの形と、宣言が本文の実態を指しているかも見る。出現のうち手当て済みのものは
免除へ理由ごと記録し、新しい出現だけが報告される。免除が実態から乖離した場合も報告する。
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from config_guard.instruction_budget import CLAUDE_MD_PATH, RULES_DIR, rule_files
from config_guard.models import Finding
from config_guard.term_definitions import (
    ACKNOWLEDGED,
    check_term_definitions,
    declared_terms,
    malformed_defines,
    rule_defines,
)
from tests.conftest import REPO_ROOT, write_file

REFERENCES = "home/.claude/references"
RULE_NAME = "testing-practices.md"
RULE_PATH = f"{RULES_DIR}/{RULE_NAME}"

TERM = "架空の造語ゼペット"

# 既定は scoped。paths を省いた rules は常時ロード扱いになり検査対象から外れるので、
# 既定をそちらにすると語の検査を見ているつもりのテストが全て素通りする
SCOPED_PATHS = ("**/*.test.*",)


def _rule(defines: list[str] | None, paths: Sequence[str] | None = SCOPED_PATHS) -> str:
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
    write_file(tmp_path, RULE_PATH, rule)
    write_file(tmp_path, CLAUDE_MD_PATH, claude_md)
    return str(tmp_path)


def _check(root: str) -> list[Finding]:
    """免除を空にして呼ぶ。

    既定の `ACKNOWLEDGED` は実リポジトリの出現を指すので、tmp_path に対しては
    全件が「免除の乖離」として報告される。既定値そのものの検証は
    `test_real_repo_is_clean` が実リポジトリに対して行う。
    """
    return check_term_definitions(root, acknowledged={})


# -----------------------------------------------------------------------------
# rule_defines / malformed_defines (pure)
# -----------------------------------------------------------------------------


def test_defines_is_read_from_frontmatter() -> None:
    assert rule_defines(_rule(["a", "b"])) == ["a", "b"]


def test_missing_defines_is_empty() -> None:
    assert rule_defines(_rule(None, paths=["**/*.md"])) == []


def test_broken_frontmatter_is_empty() -> None:
    assert rule_defines("paths: [\n---\n# no frontmatter open\n") == []


def test_non_list_defines_is_empty() -> None:
    assert rule_defines('---\ndefines: "a"\n---\n') == []


def test_defines_with_a_non_string_element_is_empty() -> None:
    # 形が違う宣言は部分的にも採らない。半端に採ると「捨てられた要素」が報告と食い違う
    assert rule_defines('---\ndefines: ["a", 12]\n---\n') == []


def test_list_of_strings_is_not_malformed() -> None:
    assert malformed_defines(_rule(["a", "b"])) is None


def test_missing_defines_key_is_not_malformed() -> None:
    # 宣言しないのは正当。ここを報告すると defines を持たない rules が全て赤くなる
    assert malformed_defines(_rule(None, paths=["**/*.md"])) is None


def test_empty_defines_is_not_malformed() -> None:
    assert malformed_defines(_rule([])) is None


def test_bare_string_defines_is_malformed() -> None:
    assert malformed_defines('---\ndefines: "a"\n---\n') == "a"


def test_non_string_element_is_malformed() -> None:
    assert malformed_defines('---\ndefines: ["a", 12]\n---\n') == ["a", 12]


def test_broken_frontmatter_is_not_malformed() -> None:
    # frontmatter ごと壊れている場合は paths も読めないので rules_paths が拾う
    assert malformed_defines("paths: [\n---\n# no frontmatter open\n") is None


# -----------------------------------------------------------------------------
# 宣言そのものの検査
# -----------------------------------------------------------------------------


def test_malformed_defines_is_reported(tmp_path: Path) -> None:
    # 形が違う宣言は黙って捨てられるので、報告しないと語の検査だけが沈黙する
    root = _repo(tmp_path, rule='---\npaths: ["**/*.x"]\ndefines: 架空の造語\n---\n\n# rule\n')
    findings = _check(root)
    assert [f.source for f in findings] == [RULE_PATH]
    assert "架空の造語" in findings[0].detail


def test_declared_term_absent_from_the_rule_body_is_reported(tmp_path: Path) -> None:
    # 綴り違いや定義の削除で、その語はどこで使われても報告されない状態になる
    root = _repo(
        tmp_path,
        rule=f'---\npaths: ["**/*.x"]\ndefines: ["{TERM}"]\n---\n\n# rule\n\n定義は無い\n',
        claude_md=f"# CLAUDE\n\n- {TERM} を使うこと\n",
    )
    findings = _check(root)
    assert RULE_PATH in [f.source for f in findings]
    assert any(f.source == RULE_PATH and f.detail == TERM for f in findings)


def test_defines_on_an_always_loaded_rule_is_reported(tmp_path: Path) -> None:
    # paths が無い rules は常時ロードされるので宣言は効かない。黙って捨てると、
    # 宣言したつもりの語がどこからも検査されないまま気づけない
    root = _repo(
        tmp_path,
        rule=_rule([TERM], paths=None),
        claude_md=f"# CLAUDE\n\n- {TERM} を使うこと\n",
    )
    findings = _check(root)
    assert [(f.source, f.detail) for f in findings] == [(RULE_PATH, "defines")]


# -----------------------------------------------------------------------------
# check_term_definitions (pure)
# -----------------------------------------------------------------------------


def test_term_absent_from_population_is_clean(tmp_path: Path) -> None:
    # 宣言元の本文にだけ在る語。母集団のどこにも出ないので報告は 0 件
    root = _repo(tmp_path, rule=_rule([TERM]))
    assert _check(root) == []


def test_term_present_in_claude_md_is_reported(tmp_path: Path) -> None:
    root = _repo(tmp_path, rule=_rule([TERM]), claude_md=f"# CLAUDE\n\n- {TERM} を使うこと\n")
    findings = _check(root)
    assert len(findings) == 1
    assert findings[0].source == CLAUDE_MD_PATH
    assert findings[0].detail == TERM
    assert RULE_PATH in findings[0].message


def test_term_present_in_references_is_reported(tmp_path: Path) -> None:
    root = _repo(tmp_path, rule=_rule([TERM]))
    write_file(tmp_path, f"{REFERENCES}/observation.md", f"# obs\n\n{TERM} で確かめる\n")
    findings = _check(root)
    assert [f.source for f in findings] == [f"{REFERENCES}/observation.md"]


def test_occurrence_in_the_declaring_rule_is_not_reported(tmp_path: Path) -> None:
    # 宣言した rules は定義を書いてある側。ここを報告すると宣言自体が毎回赤くなる
    root = _repo(tmp_path, rule=_rule([TERM]))
    write_file(tmp_path, CLAUDE_MD_PATH, "# CLAUDE\n")
    assert [f.source for f in _check(root)] == []


def test_occurrence_in_another_scoped_rule_is_reported(tmp_path: Path) -> None:
    # paths が違う rules は同時に注入されないので、そこでの使用も定義が届かない。
    # 宣言元を外すために rules 全体を母集団から外すと、この経路が黙って素通りする
    root = _repo(tmp_path, rule=_rule([TERM]))
    write_file(tmp_path, f"{RULES_DIR}/other.md", f'---\npaths: ["**/*.x"]\n---\n\n{TERM}\n')
    findings = _check(root)
    assert [f.source for f in findings] == [f"{RULES_DIR}/other.md"]


def test_rule_without_defines_contributes_nothing(tmp_path: Path) -> None:
    root = _repo(
        tmp_path,
        rule=_rule(None, paths=["**/*.md"]),
        claude_md=f"# CLAUDE\n\n- {TERM} を使うこと\n",
    )
    assert _check(root) == []


def test_multiple_terms_are_reported_independently(tmp_path: Path) -> None:
    other = "架空の造語ダイダロス"
    rule = _rule([TERM, other]).replace("# rule", f"# rule\n\n- {other} とは、そういうものである")
    root = _repo(
        tmp_path,
        rule=rule,
        claude_md=f"# CLAUDE\n\n- {TERM} と {other} を使う\n",
    )
    findings = _check(root)
    assert sorted(f.detail for f in findings) == sorted([TERM, other])


def test_missing_rules_dir_is_out_of_scope(tmp_path: Path) -> None:
    # scan() は任意のルートへ走るので、rules を持たないリポジトリは対象外
    write_file(tmp_path, CLAUDE_MD_PATH, f"# CLAUDE\n\n{TERM}\n")
    assert check_term_definitions(str(tmp_path)) == []


# -----------------------------------------------------------------------------
# 免除 (ACKNOWLEDGED)
# -----------------------------------------------------------------------------


def test_acknowledged_occurrence_is_suppressed(tmp_path: Path) -> None:
    root = _repo(tmp_path, rule=_rule([TERM]), claude_md=f"# CLAUDE\n\n- {TERM}\n")
    assert check_term_definitions(root, acknowledged={(TERM, CLAUDE_MD_PATH): "理由"}) == []


def test_acknowledged_entry_without_occurrence_is_reported(tmp_path: Path) -> None:
    # 免除が実態から乖離したまま残ると、検査が静かに緩んだことに誰も気づけない
    root = _repo(tmp_path, rule=_rule([TERM]))
    findings = check_term_definitions(root, acknowledged={(TERM, CLAUDE_MD_PATH): "理由"})
    assert len(findings) == 1
    assert findings[0].source == CLAUDE_MD_PATH
    assert "出現しない" in findings[0].message


def test_acknowledged_only_suppresses_its_own_file(tmp_path: Path) -> None:
    # 免除はファイル単位。1 箇所を免除したら他のファイルでの出現まで黙るのは緩すぎる
    root = _repo(tmp_path, rule=_rule([TERM]), claude_md=f"# CLAUDE\n\n- {TERM}\n")
    write_file(tmp_path, f"{REFERENCES}/observation.md", f"# obs\n\n{TERM}\n")
    findings = check_term_definitions(root, acknowledged={(TERM, CLAUDE_MD_PATH): "理由"})
    assert [f.source for f in findings] == [f"{REFERENCES}/observation.md"]


def test_acknowledged_for_undeclared_term_says_the_declaration_is_missing(
    tmp_path: Path,
) -> None:
    # 宣言から語を消したのに免除だけ残る形。語は現に出現しているので、
    # 「出現しないので免除を消せ」と言うと手当ての向きが逆になる
    root = _repo(tmp_path, rule=_rule([]), claude_md=f"# CLAUDE\n\n- {TERM}\n")
    findings = check_term_definitions(root, acknowledged={(TERM, CLAUDE_MD_PATH): "理由"})
    assert len(findings) == 1
    assert "宣言されていない" in findings[0].message
    assert "出現しない" not in findings[0].message


# -----------------------------------------------------------------------------
# 実リポジトリ
# -----------------------------------------------------------------------------


def test_real_repo_is_clean() -> None:
    assert check_term_definitions(str(REPO_ROOT)) == []


def test_real_repo_declares_terms() -> None:
    # 宣言が 0 件だと上のテストは何も見ずに緑になる。検査が実際に語を見ていることを縛る
    assert declared_terms(rule_files(str(REPO_ROOT))), "rules が defines を 1 つも宣言していない"


def test_real_repo_acknowledgements_are_not_empty() -> None:
    # 免除が空だと「免除の乖離」検査が実リポジトリに対して一度も働かない
    assert ACKNOWLEDGED, "免除が空。移設で語が漏れた実績があるので、空なら宣言側を疑う"
