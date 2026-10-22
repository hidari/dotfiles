"""docs_layout の仕様テスト。

パスの判定 (pure)、tmp リポジトリでの検出、実リポジトリのガードと対照を検証する。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.docs_layout import check_docs_layout, docs_layout_reason
from config_guard.git_run import tracked_files
from tests.conftest import REPO_ROOT, init_repo, run_git, write_file

# -----------------------------------------------------------------------------
# docs_layout_reason (pure)
# -----------------------------------------------------------------------------


def test_docs_layout_reason_allows_the_conventional_subdirectories() -> None:
    for path in (
        "docs/issues/12_title/issue.md",
        "docs/issues/closed/29_title/issue.md",
        "docs/known-issues/x.md",
        "docs/superpowers/archive/a.md",
    ):
        assert docs_layout_reason(path) is None, path


def test_docs_layout_reason_flags_a_subdirectory_outside_the_allowlist() -> None:
    # 規約に無いディレクトリへ着地する露出の形
    reason = docs_layout_reason("docs/notes/a.md")

    assert reason is not None
    assert "docs/notes/" in reason


def test_docs_layout_reason_flags_a_dot_directory() -> None:
    # 受け箱は ignore されているので、追跡下に現れるのは add -f したときだけ
    assert docs_layout_reason("docs/.feedbacks-box/a.md") is not None


def test_docs_layout_reason_flags_a_file_directly_under_docs() -> None:
    reason = docs_layout_reason("docs/README.md")

    assert reason is not None
    assert "docs/ 直下" in reason


def test_docs_layout_reason_does_not_match_by_prefix() -> None:
    # 前方一致で判定すると allowlist の名前を接頭辞に持つディレクトリが通る
    assert docs_layout_reason("docs/issues-archive/a.md") is not None
    assert docs_layout_reason("docs/superpowersx/a.md") is not None


def test_docs_layout_reason_treats_a_case_variant_of_docs_as_docs() -> None:
    assert docs_layout_reason("Docs/notes/a.md") is not None
    # 置き場が規約どおりでも止める (allowlist の側では止まらない検体)
    reason = docs_layout_reason("Docs/issues/1_a/issue.md")
    assert reason is not None
    assert "大小文字" in reason


def test_docs_layout_reason_ignores_paths_outside_docs() -> None:
    for path in ("README.md", "docsx/a.md", "scripts/docs/a.md", "home/docs/notes/a.md"):
        assert docs_layout_reason(path) is None, path


# -----------------------------------------------------------------------------
# check_docs_layout
# -----------------------------------------------------------------------------


def test_check_docs_layout_reports_only_tracked_files(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_file(tmp_path, "docs/issues/1_a/issue.md", "x\n")
    write_file(tmp_path, "docs/notes/a.md", "x\n")
    run_git(tmp_path, "add", "-A")
    write_file(tmp_path, "docs/scratch/b.md", "x\n")

    findings = check_docs_layout(str(tmp_path))

    assert [(f.source, f.detail) for f in findings] == [("docs/notes/a.md", "notes")]


def test_check_docs_layout_reads_non_ascii_paths(tmp_path: Path) -> None:
    # -z を落とすとクォートされた形が "docs ではない" と読まれて落ちる
    init_repo(tmp_path)
    write_file(tmp_path, "docs/メモ/a.md", "x\n")
    run_git(tmp_path, "add", "-A")

    findings = check_docs_layout(str(tmp_path))

    assert [f.source for f in findings] == ["docs/メモ/a.md"]


def test_check_docs_layout_reads_a_case_variant_of_docs(tmp_path: Path) -> None:
    # 判定側だけ直しても、pathspec の icase を落とすと列挙で落ちる
    init_repo(tmp_path)
    write_file(tmp_path, "Docs/notes/a.md", "x\n")
    run_git(tmp_path, "add", "-A")

    findings = check_docs_layout(str(tmp_path))

    assert [f.source for f in findings] == ["Docs/notes/a.md"]


def test_check_docs_layout_is_clean_on_the_real_repository() -> None:
    assert check_docs_layout(str(REPO_ROOT)) == []


def test_real_repository_has_tracked_docs_files_to_check() -> None:
    # 対照。0件の緑は docs/ を1件も見ていなくても同じ形になる
    assert len(tracked_files(str(REPO_ROOT), "docs")) > 0
