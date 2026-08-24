"""rules_paths の仕様テスト。

`home/.claude/rules/*.md` の paths 宣言が pin と一致するかを検査する。
誤った paths は scoped と判定されて予算にも計上されないため、この検査が無いと
全緑のままルールが永久に沈黙する。glob の意味論を検証しない理由と、`cli.scan()` へ
載せてある理由はモジュール側の docstring が持つ。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.rules_paths import (
    DELIBERATELY_EXCLUDED,
    EXPECTED_PATHS,
    check_rules_paths,
)
from tests.conftest import REPO_ROOT, write_file

RULES_DIR = "home/.claude/rules"

# 実体を組み立てる素材。pin の 1 つ目を借りる
PINNED_NAME = "frontend-practices.md"
PINNED_GLOBS = EXPECTED_PATHS[PINNED_NAME]


def _rule(globs: list[str]) -> str:
    joined = ", ".join(f'"{g}"' for g in globs)
    return f"---\npaths: [{joined}]\n---\n\n# rule\n"


def _repo_with(tmp_path: Path, files: dict[str, list[str]]) -> str:
    for name, globs in files.items():
        write_file(tmp_path, f"{RULES_DIR}/{name}", _rule(globs))
    return str(tmp_path)


def _all_pinned(tmp_path: Path) -> str:
    return _repo_with(tmp_path, dict(EXPECTED_PATHS))


# -----------------------------------------------------------------------------
# check_rules_paths (pure)
# -----------------------------------------------------------------------------


def test_pinned_rules_produce_no_finding(tmp_path: Path) -> None:
    assert check_rules_paths(_all_pinned(tmp_path)) == []


def test_missing_glob_is_reported(tmp_path: Path) -> None:
    root = _all_pinned(tmp_path)
    write_file(tmp_path, f"{RULES_DIR}/{PINNED_NAME}", _rule(PINNED_GLOBS[:-1]))
    findings = check_rules_paths(root)
    assert len(findings) == 1
    assert findings[0].source == f"{RULES_DIR}/{PINNED_NAME}"
    assert PINNED_GLOBS[-1] in findings[0].detail


def test_reordered_globs_are_reported(tmp_path: Path) -> None:
    # 並べ替えも編集なので可視化する
    root = _all_pinned(tmp_path)
    write_file(tmp_path, f"{RULES_DIR}/{PINNED_NAME}", _rule(list(reversed(PINNED_GLOBS))))
    assert len(check_rules_paths(root)) == 1


def test_broken_frontmatter_is_reported(tmp_path: Path) -> None:
    # paths が読めないと rule_paths は None を返す。予算側は常時ロード扱いへ倒すが、
    # こちらは pin と違うこととして報告する
    root = _all_pinned(tmp_path)
    write_file(tmp_path, f"{RULES_DIR}/{PINNED_NAME}", "# frontmatter が無い\n")
    findings = check_rules_paths(root)
    assert len(findings) == 1
    assert "None" in findings[0].detail


def test_unpinned_rule_file_is_reported(tmp_path: Path) -> None:
    # 予算検査は scoped な rules を計上しないので、増えても気づかない
    root = _repo_with(tmp_path, {**EXPECTED_PATHS, "surprise.md": ["**/*.md"]})
    findings = check_rules_paths(root)
    assert len(findings) == 1
    assert findings[0].source == f"{RULES_DIR}/surprise.md"
    assert findings[0].detail == "pin が無い"


def test_pinned_rule_file_without_a_body_is_reported(tmp_path: Path) -> None:
    root = _repo_with(tmp_path, {PINNED_NAME: PINNED_GLOBS})
    findings = check_rules_paths(root)
    # 実体を置いたのは pin の 1 つだけなので、残りが「実体が無い」で報告される。
    # 期待を pin の件数から導出しないと、rules を 1 枚足した瞬間にこのテストが
    # 無関係な理由で赤くなる (実際に markdown-practices を足したとき赤くなった)
    assert [f.detail for f in findings] == ["実体が無い"] * (len(EXPECTED_PATHS) - 1)


def test_excluded_glob_is_reported_with_its_reason(tmp_path: Path) -> None:
    # ファイルと pin の両方を更新する「正しく見える編集」でも、除外は独立に報告される
    excluded = next(iter(DELIBERATELY_EXCLUDED))
    root = _all_pinned(tmp_path)
    write_file(tmp_path, f"{RULES_DIR}/{PINNED_NAME}", _rule([*PINNED_GLOBS, excluded]))
    findings = check_rules_paths(root)
    reasons = [f.message for f in findings if f.detail == excluded]
    assert len(reasons) == 1
    assert DELIBERATELY_EXCLUDED[excluded] in reasons[0]


def test_empty_rules_dir_reports_every_pinned_file(tmp_path: Path) -> None:
    # 0 件を健全と読まないための対照。ディレクトリがあって実体が無ければ pin の枚数だけ出る
    (tmp_path / RULES_DIR).mkdir(parents=True)
    assert len(check_rules_paths(str(tmp_path))) == len(EXPECTED_PATHS)


def test_repo_without_a_rules_dir_is_out_of_scope(tmp_path: Path) -> None:
    # rules を管理していないリポジトリへ「pin したファイルが無い」と言っても意味がない
    assert check_rules_paths(str(tmp_path)) == []


# -----------------------------------------------------------------------------
# pin そのものの不変条件
# -----------------------------------------------------------------------------


def test_pins_are_not_empty() -> None:
    # どちらかを空にすると、上の検査群が「報告するものが無い」状態へ静かに倒れる
    assert EXPECTED_PATHS
    assert DELIBERATELY_EXCLUDED


def test_excluded_globs_are_absent_from_the_pin() -> None:
    # 実ファイル側は check_rules_paths が見る。pin 側だけを緩める編集をここで止める
    for name, globs in EXPECTED_PATHS.items():
        for glob, reason in DELIBERATELY_EXCLUDED.items():
            assert glob not in globs, f"{name} に {glob} が入っている。載せない理由: {reason}"


def test_every_pinned_glob_list_is_non_empty() -> None:
    # 空リストを pin すると、実体が空でも「一致」と読んでしまう
    assert all(EXPECTED_PATHS.values())


# -----------------------------------------------------------------------------
# 実リポジトリ (回帰防止)
# -----------------------------------------------------------------------------


def test_real_repo_has_a_rules_dir() -> None:
    # check_rules_paths はディレクトリが無いと何も見ない。実リポジトリで消えたら
    # 下の回帰テストが vacuous に通るので、存在をここで縛る
    assert (REPO_ROOT / RULES_DIR).is_dir()


def test_real_repo_matches_the_pin() -> None:
    assert check_rules_paths(str(REPO_ROOT)) == []
