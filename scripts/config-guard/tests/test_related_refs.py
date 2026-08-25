"""`## 関連` 節の Issue 参照検査。

陰性対照 (免除が効くこと) は必ず陽性対照 (免除が効かない側が検出されること) と対で置く。
免除が広がりすぎて全件素通りしても結果は「違反 0 件」の緑にしかならず、出力から
気づけないため。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from config_guard.related_refs import (
    FOREIGN_REPOS,
    LINK_BASELINE,
    check_related_refs,
    issue_number_of,
    issue_numbers,
    local_link_targets,
    related_lines,
    related_refs_summary,
    self_identifiers,
)
from tests.conftest import REPO_ROOT, init_repo, run_git, write_file

FOREIGN = FOREIGN_REPOS[0]


# --- related_lines (節の切り出し) ---------------------------------------------


def test_related_lines_returns_only_the_related_section() -> None:
    text = "# t\n\n## 背景\n\n背景の行\n\n## 関連\n\n- Issue 1\n\n## タスク\n\n- [ ] x\n"

    assert [ln for ln in related_lines(text) if ln.strip()] == ["- Issue 1"]


def test_related_lines_is_empty_when_the_section_is_absent() -> None:
    assert related_lines("# t\n\n## 背景\n\n- Issue 1\n") == []


def test_related_lines_ignores_a_heading_inside_a_code_fence() -> None:
    # フェンス内は例示。節の走査を自前で持たず prose_lines を借りていることの pin でもある
    text = "# t\n\n## 背景\n\n```markdown\n## 関連\n\n- Issue 999\n```\n\n本文\n"

    assert related_lines(text) == []


def test_related_lines_drops_a_fenced_example_inside_the_section() -> None:
    text = "# t\n\n## 関連\n\n- Issue 1\n\n```markdown\n- Issue 999\n```\n\n- Issue 2\n"

    assert [ln for ln in related_lines(text) if ln.strip()] == ["- Issue 1", "- Issue 2"]


# --- self_identifiers (識別子の抽出と免除) --------------------------------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("- ISSUE-46: 台帳", ["46"]),
        ("- Issue 43 の本体", ["43"]),
        ("- Issue #17 と Issue #18", ["17", "18"]),
        ("- #21 の管轄", ["21"]),
        ("- ISSUE-12 と ISSUE-13", ["12", "13"]),
    ],
)
def test_self_identifiers_accepts_every_notation_in_use(line: str, expected: list[str]) -> None:
    assert self_identifiers(line) == expected


def test_self_identifiers_skips_github_pull_request_numbers() -> None:
    # `PR #22` を自リポの Issue 22 として解決すると、実在するので緑のまま誤った先を指す
    assert self_identifiers("- PR #22 のレビューで検出") == []


def test_self_identifiers_still_reads_a_bare_number_on_the_same_line_as_a_pr() -> None:
    # 免除が行全体へ広がっていないことの対。広がっても違反 0 件の緑にしかならない
    assert self_identifiers("- PR #22 のレビューで検出。#40 と同種") == ["40"]


def test_self_identifiers_skips_a_number_qualified_by_owner_and_repo() -> None:
    assert self_identifiers("- owner/repo#12 を参照") == []


def test_self_identifiers_skips_an_identifier_prefixed_with_a_foreign_repository() -> None:
    assert self_identifiers(f"- {FOREIGN} の ISSUE-22: 記法混在") == []


def test_self_identifiers_reads_an_identifier_written_before_the_foreign_prefix() -> None:
    # 免除は識別子より前に前置がある場合だけ。行全体を免除すると自リポ参照が素通りする
    assert self_identifiers(f"- ISSUE-46 と {FOREIGN} の ISSUE-22") == ["46"]


def test_self_identifiers_ignores_identifiers_inside_a_link() -> None:
    # リンクは形式検査と markdown_links が見る。角括弧が `PR ` の直前判定を壊すため、
    # リンクごと落としてから識別子を読む (`- relay PR [#588](url)` が実在する)
    assert self_identifiers("- relay PR [#588](https://example.test/pull/588)") == []


def test_self_identifiers_reads_a_bare_identifier_next_to_a_link() -> None:
    assert self_identifiers("- [Issue #10](../10_x/issue.md) と #11") == ["11"]


# --- local_link_targets --------------------------------------------------------


def test_local_link_targets_returns_relative_targets_only() -> None:
    line = "- [a](../10_x/issue.md) [b](https://example.test/) [c](#anchor)"

    assert local_link_targets(line) == ["../10_x/issue.md"]


# --- issue_numbers -------------------------------------------------------------


def _issue_repo(tmp_path: Path) -> Path:
    repo = tmp_path
    init_repo(repo)
    return repo


def test_issue_numbers_reads_both_notations_and_both_locations(tmp_path: Path) -> None:
    repo = _issue_repo(tmp_path)
    write_file(repo, "docs/issues/7_old/issue.md", "# t\n")
    write_file(repo, "docs/issues/ISSUE-8_new/issue.md", "# t\n")
    write_file(repo, "docs/issues/closed/9_done/issue.md", "# t\n")
    write_file(repo, "docs/issues/templates/issue.md", "# t\n")
    run_git(repo, "add", "-A")

    assert sorted(issue_numbers(str(repo))) == ["7", "8", "9"]


# --- check_related_refs --------------------------------------------------------


def _repo_with_related(tmp_path: Path, body: str, *, others: tuple[str, ...] = ()) -> Path:
    repo = _issue_repo(tmp_path)
    write_file(repo, "docs/issues/1_a/issue.md", f"# a\n\n## 関連\n\n{body}\n")
    for name in others:
        write_file(repo, f"docs/issues/{name}/issue.md", "# t\n")
    run_git(repo, "add", "-A")
    return repo


def test_an_identifier_without_a_matching_directory_is_reported(tmp_path: Path) -> None:
    repo = _repo_with_related(tmp_path, "- Issue 99 を参照")

    findings = check_related_refs(str(repo), baseline={})

    assert [(f.source, f.detail) for f in findings] == [("docs/issues/1_a/issue.md", "Issue 99")]


def test_an_identifier_with_a_matching_directory_is_not_reported(tmp_path: Path) -> None:
    repo = _repo_with_related(tmp_path, "- Issue 2 を参照", others=("2_b",))

    assert check_related_refs(str(repo), baseline={}) == []


def test_a_foreign_identifier_is_not_resolved_against_this_repository(tmp_path: Path) -> None:
    # 前置があれば、自リポに同番号が無くても報告しない
    repo = _repo_with_related(tmp_path, f"- {FOREIGN} の ISSUE-99")

    assert check_related_refs(str(repo), baseline={}) == []


def test_a_foreign_scope_heading_is_reported(tmp_path: Path) -> None:
    # `<repo> 側:` の下の識別子は前置を持たないので自リポで解決される。番号が実在すると
    # 誤った Issue へ静かに解決されるため、見出しの形そのものを報告する
    repo = _repo_with_related(tmp_path, f"{FOREIGN} 側:\n\n- ISSUE-2 を参照", others=("2_b",))

    findings = check_related_refs(str(repo), baseline={})

    assert [f.detail for f in findings] == [f"{FOREIGN} 側:"]


def test_links_beyond_the_baseline_are_reported(tmp_path: Path) -> None:
    repo = _repo_with_related(tmp_path, "- [x](../2_b/issue.md)", others=("2_b",))

    findings = check_related_refs(str(repo), baseline={})

    assert [(f.source, f.detail) for f in findings] == [("docs/issues/1_a/issue.md", "1 > 0")]


def test_links_recorded_in_the_baseline_are_not_reported(tmp_path: Path) -> None:
    repo = _repo_with_related(tmp_path, "- [x](../2_b/issue.md)", others=("2_b",))

    assert check_related_refs(str(repo), baseline={"docs/issues/1_a/issue.md": 1}) == []


def test_a_baseline_larger_than_reality_is_reported(tmp_path: Path) -> None:
    # 単調非増加を成立させる側。減らしたのに baseline を残すと、次の 1 本が無検査で入る
    repo = _repo_with_related(tmp_path, "- Issue 2", others=("2_b",))

    findings = check_related_refs(str(repo), baseline={"docs/issues/1_a/issue.md": 1})

    assert [(f.source, f.detail) for f in findings] == [("docs/issues/1_a/issue.md", "0 < 1")]


def test_a_baseline_entry_for_a_missing_file_is_reported(tmp_path: Path) -> None:
    repo = _repo_with_related(tmp_path, "- Issue 2", others=("2_b",))

    findings = check_related_refs(str(repo), baseline={"docs/issues/gone/issue.md": 1})

    assert [f.source for f in findings] == ["docs/issues/gone/issue.md"]


def test_a_repository_without_an_issue_directory_is_skipped(tmp_path: Path) -> None:
    repo = _issue_repo(tmp_path)
    write_file(repo, "README.md", "# t\n")
    run_git(repo, "add", "-A")

    assert check_related_refs(str(repo), baseline={}) == []


def test_the_summary_reports_what_was_scanned(tmp_path: Path) -> None:
    # 0 件で緑になる経路と、見ていないから 0 件の経路を区別できるようにする
    repo = _repo_with_related(tmp_path, "- Issue 2 と Issue 3", others=("2_b", "3_c"))

    summary = related_refs_summary(str(repo))

    assert "1 節" in summary
    assert "2 件" in summary


# --- 実リポジトリ ---------------------------------------------------------------


def test_real_repo_parses_every_issue_directory_name() -> None:
    # 記法の canonical は in-repo-issue skill の issue-id.py で、こちらは import できない
    # 位置にある。記法が変わったとき検査側だけが取り残されて「違反 0 件」を返す形を、
    # 実ディレクトリ名との突き合わせで赤へ変える
    root = REPO_ROOT / "docs" / "issues"
    names = [
        d.name
        for parent in (root, root / "closed")
        if parent.is_dir()
        for d in parent.iterdir()
        if d.is_dir() and d.name not in {"closed", "templates"}
    ]
    assert names, "Issue ディレクトリが 1 件も無い。走査そのものが空振りしている"

    unparsed = [name for name in names if issue_number_of(name) is None]

    assert unparsed == []


def test_real_repo_has_no_related_ref_findings() -> None:
    assert check_related_refs(str(REPO_ROOT)) == []


def test_real_repo_baseline_has_no_dead_entries() -> None:
    # baseline のキーが実在しないと、その行は永久に減らせないまま残る
    for rel in LINK_BASELINE:
        assert (REPO_ROOT / rel).is_file(), rel
