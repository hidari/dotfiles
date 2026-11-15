"""references_reach の仕様テスト。

references は名指しされて初めて読まれる。根 (常時層と rules) から参照の連鎖で届かない
references を見つける。根と辺の定義はモジュール側の docstring が持つ。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.instruction_budget import CLAUDE_MD_PATH
from config_guard.references_reach import (
    REFERENCES_GLOB,
    check_references_reach,
    reached_references,
)
from tests.conftest import REPO_ROOT, write_file

REF_A = "home/.claude/references/a.md"
REF_B = "home/.claude/references/b.md"
RULE = "home/.claude/rules/x-practices.md"


def _reached(repo: Path) -> set[str]:
    return reached_references(str(repo))


def _flagged(repo: Path) -> set[str]:
    return {f.source for f in check_references_reach(str(repo))}


def test_reference_named_from_claude_md_is_reached(tmp_path: Path) -> None:
    write_file(tmp_path, CLAUDE_MD_PATH, "詳細は `~/.claude/references/a.md` が持つ\n")
    write_file(tmp_path, REF_A, "# a\n")
    assert _reached(tmp_path) == {REF_A}
    assert _flagged(tmp_path) == set()


def test_reference_named_from_a_scoped_rule_is_reached(tmp_path: Path) -> None:
    # paths 付き rules も Read で発火して読まれるので根に入れる
    write_file(tmp_path, CLAUDE_MD_PATH, "# 本体\n")
    write_file(
        tmp_path, RULE, '---\npaths:\n  - "**/*.x"\n---\n\n症状は `~/.claude/references/a.md`\n'
    )
    write_file(tmp_path, REF_A, "# a\n")
    assert _reached(tmp_path) == {REF_A}


def test_reference_named_only_from_a_reached_reference_is_reached(tmp_path: Path) -> None:
    # 索引や分割した参照は、名指しされた参照を開いた読み手から届く
    write_file(tmp_path, CLAUDE_MD_PATH, "`~/.claude/references/a.md`\n")
    write_file(tmp_path, REF_A, "続きは `~/.claude/references/b.md`\n")
    write_file(tmp_path, REF_B, "# b\n")
    assert _reached(tmp_path) == {REF_A, REF_B}


def test_unnamed_reference_is_flagged(tmp_path: Path) -> None:
    write_file(tmp_path, CLAUDE_MD_PATH, "# 本体\n")
    write_file(tmp_path, REF_A, "# a\n")
    assert _flagged(tmp_path) == {REF_A}


def test_references_naming_each_other_without_a_root_are_flagged(tmp_path: Path) -> None:
    # 互いに名指ししていても、根から入口が無ければ誰も開かない
    write_file(tmp_path, CLAUDE_MD_PATH, "# 本体\n")
    write_file(tmp_path, REF_A, "`~/.claude/references/b.md`\n")
    write_file(tmp_path, REF_B, "`~/.claude/references/a.md`\n")
    assert _flagged(tmp_path) == {REF_A, REF_B}


def test_mention_inside_a_fence_does_not_reach(tmp_path: Path) -> None:
    # フェンス内は例示で、読み手への名指しではない
    write_file(tmp_path, CLAUDE_MD_PATH, "```\n`~/.claude/references/a.md`\n```\n")
    write_file(tmp_path, REF_A, "# a\n")
    assert _flagged(tmp_path) == {REF_A}


def test_mention_outside_inline_code_does_not_reach(tmp_path: Path) -> None:
    # 参照はバッククォート記法で書く規約 (instruction_refs の docstring)
    write_file(tmp_path, CLAUDE_MD_PATH, "~/.claude/references/a.md を読む\n")
    write_file(tmp_path, REF_A, "# a\n")
    assert _flagged(tmp_path) == {REF_A}


def test_heading_reference_reaches_the_file(tmp_path: Path) -> None:
    write_file(tmp_path, CLAUDE_MD_PATH, "`~/.claude/references/a.md` の「節」\n")
    write_file(tmp_path, REF_A, "# 節\n")
    assert _flagged(tmp_path) == set()


def test_no_references_dir_yields_nothing(tmp_path: Path) -> None:
    write_file(tmp_path, CLAUDE_MD_PATH, "# 本体\n")
    assert _flagged(tmp_path) == set()


def test_real_repo_has_references_to_check() -> None:
    # 対照: 母集団が空なら下の緑は何も見ていない
    assert len(list(REPO_ROOT.glob(REFERENCES_GLOB))) >= 5


def test_real_repo_reaches_every_reference() -> None:
    assert check_references_reach(str(REPO_ROOT)) == []
