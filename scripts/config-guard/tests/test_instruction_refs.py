"""instruction_refs の仕様テスト。

指示ファイルどうしの参照が実在するかを検査する。参照 2 種の定義と、母集団を明示リストで
持つ理由はモジュール側の docstring が持つ。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.git_run import run_git_checked
from config_guard.instruction_budget import CLAUDE_MD_PATH
from config_guard.instruction_refs import (
    SOURCE_GLOBS,
    check_instruction_refs,
    extract_heading_refs,
    extract_home_refs,
    heading_names,
    is_checkable_ref,
    repo_path,
    source_files,
)
from tests.conftest import REPO_ROOT, write_file

# -----------------------------------------------------------------------------
# extract_home_refs (pure)
# -----------------------------------------------------------------------------


def test_extracts_a_ref_from_inline_code() -> None:
    assert extract_home_refs("詳細は `~/.claude/references/observation.md` が持つ") == [
        "~/.claude/references/observation.md"
    ]


def test_extracts_multiple_refs_from_one_line() -> None:
    text = "`~/.claude/CLAUDE.md` と `~/.claude/settings.json` を見る"
    assert extract_home_refs(text) == ["~/.claude/CLAUDE.md", "~/.claude/settings.json"]


def test_ignores_refs_outside_inline_code() -> None:
    # このリポジトリの参照は全てバッククォート記法。素の散文中の言及と
    # 参照を区別できないので、記法を手がかりにする (限界は docstring)
    assert extract_home_refs("~/.claude/CLAUDE.md を読む") == []


def test_ignores_refs_inside_a_fenced_block() -> None:
    # フェンス内は例示。実在しないパスを書くことがある
    text = "```\n`~/.claude/does-not-exist.md`\n```\n"
    assert extract_home_refs(text) == []


def test_ignores_inline_code_that_is_not_a_home_ref() -> None:
    assert extract_home_refs("`git status` と `~/.config/mise` を使う") == []


# -----------------------------------------------------------------------------
# is_checkable_ref (pure)
# -----------------------------------------------------------------------------


def test_a_concrete_path_is_checkable() -> None:
    assert is_checkable_ref("~/.claude/references/observation.md")


def test_a_placeholder_is_not_checkable() -> None:
    # <plugin 名> のような穴埋めは実在しなくて当然
    assert not is_checkable_ref("~/.claude/plugins/<plugin 名>")


def test_a_glob_is_not_checkable() -> None:
    # rules/*.md はパターンであってパスではない
    assert not is_checkable_ref("~/.claude/rules/*.md")


# -----------------------------------------------------------------------------
# repo_path (pure)
# -----------------------------------------------------------------------------


def test_maps_home_ref_to_repo_path() -> None:
    # ~ は live 側の配置。リポジトリ内の実体は home/ 配下にある
    assert repo_path("~/.claude/references/observation.md") == (
        "home/.claude/references/observation.md"
    )


# -----------------------------------------------------------------------------
# extract_heading_refs (pure)
# -----------------------------------------------------------------------------


def test_extracts_a_heading_ref() -> None:
    text = "`~/.claude/CLAUDE.md` の「語彙と前提」カテゴリが持つ規範の、そう決めた理由。"
    assert extract_heading_refs(text) == [("~/.claude/CLAUDE.md", "語彙と前提")]


def test_extracts_a_heading_ref_pointing_at_rules() -> None:
    # 参照先を CLAUDE.md へ決め打ちすると rules を指す参照を取りこぼす
    text = "`~/.claude/rules/testing-practices.md` の「テストが緑であること」\nカテゴリの実測。"
    assert extract_heading_refs(text) == [
        ("~/.claude/rules/testing-practices.md", "テストが緑であること")
    ]


def test_ignores_a_quoted_phrase_without_a_file_ref() -> None:
    # 鉤括弧は本文でも使う。直前のファイル参照とセットのときだけ見出し参照
    assert extract_heading_refs("「列挙は網羅ではない」を明示する") == []


def test_ignores_a_heading_ref_inside_a_fenced_block() -> None:
    # フェンス内は例示。パス参照と同じ規約で見ないと、例示だけが検査されて誤検出になる
    text = "```\n`~/.claude/CLAUDE.md` の「実在しない見出し」\n```\n"
    assert extract_heading_refs(text) == []


# -----------------------------------------------------------------------------
# heading_names (pure)
# -----------------------------------------------------------------------------


def test_reads_headings_at_any_level() -> None:
    # CLAUDE.md のカテゴリは H2、rules の見出しは H1。レベルを決め打ちできない
    assert heading_names("# 一\n\n## 二\n\n### 三\n") == {"一", "二", "三"}


def test_strips_the_strength_label() -> None:
    # 見出しは [MUST] 等のラベルを持つが、参照側は本文だけを書く
    assert heading_names("## [MUST] 名前\n") == {"名前"}
    assert heading_names("## [MUST GLOBAL] 名前\n") == {"名前"}
    assert heading_names("## [SHOULD] 名前\n") == {"名前"}


def test_a_document_without_headings_has_no_names() -> None:
    assert heading_names("本文だけ\n") == set()


def test_ignores_headings_inside_a_fenced_block() -> None:
    # 参照先のフェンス内にある見出しを実在と数えると、本物の見出しを改名しても
    # 緑のまま通る (fail-open)。抽出 2 種と同じフェンス判定を通す
    assert heading_names("# 本物\n\n```\n## 例\n```\n") == {"本物"}


# -----------------------------------------------------------------------------
# check_instruction_refs (ファイルシステムを見る)
# -----------------------------------------------------------------------------


def _repo(tmp_path: Path, files: dict[str, str]) -> str:
    for rel, text in files.items():
        write_file(tmp_path, rel, text)
    return str(tmp_path)


def test_an_existing_path_ref_produces_no_finding(tmp_path: Path) -> None:
    root = _repo(
        tmp_path,
        {
            CLAUDE_MD_PATH: "詳細は `~/.claude/references/observation.md` が持つ\n",
            "home/.claude/references/observation.md": "# 観測\n",
        },
    )
    assert check_instruction_refs(root) == []


def test_a_missing_path_ref_is_reported(tmp_path: Path) -> None:
    root = _repo(tmp_path, {CLAUDE_MD_PATH: "詳細は `~/.claude/references/missing.md` が持つ\n"})
    findings = check_instruction_refs(root)
    assert [(f.source, f.detail) for f in findings] == [
        (CLAUDE_MD_PATH, "~/.claude/references/missing.md")
    ]


def test_an_unresolvable_ref_is_not_reported(tmp_path: Path) -> None:
    # プレースホルダと glob は実在しなくて当然。除外の理由は UNCHECKABLE が持つ
    body = "`~/.claude/plugins/<plugin 名>` と `~/.claude/rules/*.md`\n"
    assert check_instruction_refs(_repo(tmp_path, {CLAUDE_MD_PATH: body})) == []


def test_a_broken_ref_in_a_references_file_is_reported(tmp_path: Path) -> None:
    root = _repo(
        tmp_path, {"home/.claude/references/observation.md": "`~/.claude/references/gone.md`\n"}
    )
    assert [f.source for f in check_instruction_refs(root)] == [
        "home/.claude/references/observation.md"
    ]


def test_a_broken_ref_in_a_rules_file_is_reported(tmp_path: Path) -> None:
    # rules も名指しする側になる (testing-practices.md が references/testing.md を指す)
    root = _repo(
        tmp_path, {"home/.claude/rules/testing-practices.md": "`~/.claude/references/gone.md`\n"}
    )
    assert [f.source for f in check_instruction_refs(root)] == [
        "home/.claude/rules/testing-practices.md"
    ]


def test_an_existing_heading_produces_no_finding(tmp_path: Path) -> None:
    root = _repo(
        tmp_path,
        {
            CLAUDE_MD_PATH: "## [MUST] 名前\n",
            "home/.claude/references/premises.md": "`~/.claude/CLAUDE.md` の「名前」カテゴリ\n",
        },
    )
    assert check_instruction_refs(root) == []


def test_a_missing_heading_is_reported(tmp_path: Path) -> None:
    root = _repo(
        tmp_path,
        {
            CLAUDE_MD_PATH: "## 別の名前\n",
            "home/.claude/references/premises.md": "`~/.claude/CLAUDE.md` の「名前」カテゴリ\n",
        },
    )
    # detail は exact で比較する。部分一致だと、参照側の「名前」を報告しても実在側の
    # 「別の名前」を報告しても通ってしまい、このテストが区別したい当のケースを見分けられない
    assert [(f.source, f.detail) for f in check_instruction_refs(root)] == [
        ("home/.claude/references/premises.md", "~/.claude/CLAUDE.md 「名前」")
    ]


def test_a_heading_ref_into_a_rules_file_is_checked(tmp_path: Path) -> None:
    # 参照先を CLAUDE.md へ決め打ちすると rules を指す references を取りこぼす
    root = _repo(
        tmp_path,
        {
            "home/.claude/rules/testing-practices.md": "# 別の名前\n",
            "home/.claude/references/testing.md": (
                "`~/.claude/rules/testing-practices.md` の「名前」\n"
            ),
        },
    )
    assert [f.source for f in check_instruction_refs(root)] == [
        "home/.claude/references/testing.md"
    ]


def test_a_heading_ref_into_a_missing_file_is_reported_once(tmp_path: Path) -> None:
    # パス参照のループが既に報告している。見出し検査は二重に出さない
    body = "`~/.claude/references/gone.md` の「名前」\n"
    findings = check_instruction_refs(_repo(tmp_path, {"home/.claude/references/a.md": body}))
    assert [f.detail for f in findings] == ["~/.claude/references/gone.md"]


def test_a_repo_without_instruction_files_is_out_of_scope(tmp_path: Path) -> None:
    # scan() は任意のルートへ走る。指示ファイルを管理していないリポジトリは対象外
    assert check_instruction_refs(str(tmp_path)) == []


# -----------------------------------------------------------------------------
# 実リポジトリ (回帰防止)
# -----------------------------------------------------------------------------


def test_real_repo_has_source_files() -> None:
    # 対象が 0 件なら check は何も見ずに緑になる。下の回帰テストを vacuous にしない pin
    assert source_files(str(REPO_ROOT))


def test_real_repo_covers_every_tracked_instruction_file() -> None:
    # 母集団を明示リストで持つ以上、追跡下の指示ファイルが増えたときに漏れる。
    # ファイルシステム glob を home/.claude/**/*.md へ広げる案は採れない
    # (apm の deploy 先 home/.claude/skills/ は ignore されていても実在する)
    out = run_git_checked(str(REPO_ROOT), "ls-files", "-z", "--", "home/.claude/*.md")
    tracked = {path for path in out.split("\0") if path}
    assert tracked, "追跡下の指示ファイルが 0 件。pathspec が壊れている"
    assert tracked == set(source_files(str(REPO_ROOT))), (
        f"母集団から外れた指示ファイルがある。{SOURCE_GLOBS} へ足すこと"
    )


def test_real_repo_has_refs_of_both_kinds() -> None:
    # 「緑」が「そもそも見ていない」でないことの対照。両種が非空であることを要求する
    texts = list(source_files(str(REPO_ROOT)).values())
    paths = [r for t in texts for r in extract_home_refs(t) if is_checkable_ref(r)]
    headings = [h for t in texts for h in extract_heading_refs(t)]
    assert paths, "パス参照が見えていない"
    assert headings, "見出し参照が見えていない"


def test_real_repo_has_no_broken_refs() -> None:
    assert check_instruction_refs(str(REPO_ROOT)) == []
