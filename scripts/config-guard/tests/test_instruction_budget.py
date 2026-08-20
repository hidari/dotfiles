"""instruction_budget の仕様テスト。

常時ロードされる指示ファイルの総バイト数が予算内かを検査する。
「常時ロード」の判定は Claude Code の実測仕様に従う。User スコープの CLAUDE.md は
session_start で必ずロードされ、~/.claude/rules/*.md は paths frontmatter が
無いときだけ常時ロードされる (paths があれば該当ファイルに触れたときだけ)。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.instruction_budget import (
    ALWAYS_LOADED_BUDGET_BYTES,
    CLAUDE_MD_PATH,
    always_loaded_bytes,
    check_instruction_budget,
    is_always_loaded_rule,
)
from tests.conftest import REPO_ROOT, write_file

# -----------------------------------------------------------------------------
# is_always_loaded_rule (pure)
# -----------------------------------------------------------------------------


def test_rule_without_frontmatter_is_always_loaded() -> None:
    # frontmatter を持たない rules は session_start でロードされる
    assert is_always_loaded_rule("# core\n\n- 規範\n")


def test_rule_with_paths_frontmatter_is_not_always_loaded() -> None:
    # paths があると該当ファイルに触れたときだけロードされるので常時層に載らない
    assert not is_always_loaded_rule('---\npaths: ["**/*.test.ts"]\n---\n\n# testing\n')


def test_rule_with_frontmatter_but_no_paths_is_always_loaded() -> None:
    # frontmatter があっても paths が無ければ常時ロード。description だけの形を弾かない
    assert is_always_loaded_rule("---\ndescription: core rules\n---\n\n# core\n")


def test_paths_inside_body_does_not_exempt() -> None:
    # 本文中の paths: は frontmatter ではない。text-parse だと拾ってしまう形
    assert is_always_loaded_rule("# core\n\n- paths: を本文で説明するだけの行\n")


def test_empty_paths_is_treated_as_always_loaded() -> None:
    # 空・null の paths を Claude Code が scoped 扱いにするかは未実測。
    # Issue #36 の probe は非空の値しか使っていないので、キーの有無だけで
    # 除外すると未確認の前提を検査の土台にすることになる。計上側へ倒す
    for body in ("---\npaths: []\n---\n\n# x\n", "---\npaths:\n---\n\n# x\n"):
        assert is_always_loaded_rule(body), body


def test_broken_frontmatter_is_treated_as_always_loaded() -> None:
    # YAML が壊れているときは安全側 (常時ロード扱い = 予算に計上) へ倒す。
    # 計上漏れは予算を無言ですり抜けるので、誤って厳しい方が安全
    assert is_always_loaded_rule("---\npaths: [unclosed\n---\n\n# broken\n")


# -----------------------------------------------------------------------------
# always_loaded_bytes (実ファイル)
# -----------------------------------------------------------------------------


def test_counts_claude_md_alone_when_no_rules(tmp_path: Path) -> None:
    write_file(tmp_path, CLAUDE_MD_PATH, "12345")
    assert always_loaded_bytes(str(tmp_path)) == 5


def test_adds_pathless_rules(tmp_path: Path) -> None:
    write_file(tmp_path, CLAUDE_MD_PATH, "12345")
    write_file(tmp_path, "home/.claude/rules/core.md", "678")
    assert always_loaded_bytes(str(tmp_path)) == 8


def test_excludes_scoped_rules(tmp_path: Path) -> None:
    write_file(tmp_path, CLAUDE_MD_PATH, "12345")
    write_file(tmp_path, "home/.claude/rules/scoped.md", '---\npaths: ["**/*.ts"]\n---\nbody')
    assert always_loaded_bytes(str(tmp_path)) == 5


def test_counts_utf8_bytes_not_characters(tmp_path: Path) -> None:
    # 日本語が主体のファイルなので、文字数で数えると 3 倍近く過小評価する
    write_file(tmp_path, CLAUDE_MD_PATH, "規範")
    assert always_loaded_bytes(str(tmp_path)) == 6


def test_missing_claude_md_counts_zero(tmp_path: Path) -> None:
    # ファイルが無い状態を例外にすると、検査が落ちて他の Finding ごと失われる
    assert always_loaded_bytes(str(tmp_path)) == 0


# -----------------------------------------------------------------------------
# check_instruction_budget
# -----------------------------------------------------------------------------


def test_within_budget_yields_no_finding(tmp_path: Path) -> None:
    write_file(tmp_path, CLAUDE_MD_PATH, "x" * (ALWAYS_LOADED_BUDGET_BYTES - 1))
    assert check_instruction_budget(str(tmp_path)) == []


def test_exactly_at_budget_yields_no_finding(tmp_path: Path) -> None:
    # 予算は上限であって禁止値ではない。境界で誤検出すると現状の維持ができない
    write_file(tmp_path, CLAUDE_MD_PATH, "x" * ALWAYS_LOADED_BUDGET_BYTES)
    assert check_instruction_budget(str(tmp_path)) == []


def test_one_byte_over_budget_yields_finding(tmp_path: Path) -> None:
    write_file(tmp_path, CLAUDE_MD_PATH, "x" * (ALWAYS_LOADED_BUDGET_BYTES + 1))
    findings = check_instruction_budget(str(tmp_path))
    assert len(findings) == 1
    # 超過量が読めないと「どれだけ削るか」が分からず、報告として役に立たない
    assert str(ALWAYS_LOADED_BUDGET_BYTES + 1) in findings[0].detail
    assert str(ALWAYS_LOADED_BUDGET_BYTES) in findings[0].detail


def test_scoped_rule_does_not_push_over_budget(tmp_path: Path) -> None:
    # paths 付き rules を計上してしまうと、正しい移設が予算超過として弾かれる
    write_file(tmp_path, CLAUDE_MD_PATH, "x" * ALWAYS_LOADED_BUDGET_BYTES)
    write_file(
        tmp_path,
        "home/.claude/rules/scoped.md",
        '---\npaths: ["**/*.ts"]\n---\n' + "y" * 1000,
    )
    assert check_instruction_budget(str(tmp_path)) == []


# -----------------------------------------------------------------------------
# 実リポジトリ (回帰防止)
# -----------------------------------------------------------------------------


def test_real_repo_is_within_budget() -> None:
    assert check_instruction_budget(str(REPO_ROOT)) == []


def test_budget_tracks_the_real_repo_closely() -> None:
    # 予算が実態から離れると「守っているのに減らない」状態になり pin が空虚になる。
    # 移設でカテゴリを切り出したら予算も同時に下げる運用を、この幅で強制する
    actual = always_loaded_bytes(str(REPO_ROOT))
    assert ALWAYS_LOADED_BUDGET_BYTES - actual < 2000, (
        f"予算 {ALWAYS_LOADED_BUDGET_BYTES} が実態 {actual} から離れすぎている"
    )
