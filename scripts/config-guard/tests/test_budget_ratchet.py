"""budget_ratchet の仕様テスト。

常時ロード層の予算定数が origin/main の値から増えていないことを検査する。
増やすこと自体は禁じない。禁じるのは「無音で増やすこと」で、引き上げには
BUDGET_RAISES への記録を要求する (起票理由は 9 日 +44% の無音な増加だった)。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.budget_ratchet import (
    BUDGET_MODULE_PATH,
    check_budget_ratchet,
    evaluate_ratchet,
    parse_budget,
)
from config_guard.instruction_budget import ALWAYS_LOADED_BUDGET_BYTES, BUDGET_RAISES
from tests.conftest import REPO_ROOT, init_repo, run_git, write_file

# -----------------------------------------------------------------------------
# parse_budget (pure)
# -----------------------------------------------------------------------------


def test_reads_the_module_level_constant() -> None:
    assert parse_budget("ALWAYS_LOADED_BUDGET_BYTES = 12345\n") == 12345


def test_reads_an_annotated_assignment() -> None:
    # 型注釈を足しただけで baseline が読めなくなると、無関係な編集で赤くなる
    assert parse_budget("ALWAYS_LOADED_BUDGET_BYTES: int = 12345\n") == 12345


def test_ignores_the_name_inside_a_comment() -> None:
    # regex で探すと拾う形。ast は Python のパーサ自身なのでコメントを見ない
    source = "# ALWAYS_LOADED_BUDGET_BYTES = 99999\nALWAYS_LOADED_BUDGET_BYTES = 100\n"
    assert parse_budget(source) == 100


def test_ignores_the_name_inside_a_string() -> None:
    # 定数名は docstring や Finding のメッセージにも出る。実際に同居している
    source = (
        '"""ALWAYS_LOADED_BUDGET_BYTES = 99999 と説明する docstring"""\n'
        "ALWAYS_LOADED_BUDGET_BYTES = 100\n"
    )
    assert parse_budget(source) == 100


def test_ignores_assignment_inside_a_function() -> None:
    # canonical は module レベルの代入。関数内のローカルは同名でも別物
    source = (
        "def f() -> int:\n"
        "    ALWAYS_LOADED_BUDGET_BYTES = 99999\n"
        "    return ALWAYS_LOADED_BUDGET_BYTES\n"
    )
    assert parse_budget(source) is None


def test_returns_none_when_the_constant_is_absent() -> None:
    assert parse_budget("OTHER = 1\n") is None


def test_returns_none_for_a_non_integer_value() -> None:
    # 文字列を int として読むと baseline が壊れたまま比較が成立してしまう
    assert parse_budget('ALWAYS_LOADED_BUDGET_BYTES = "29012"\n') is None


def test_returns_none_for_unparsable_source() -> None:
    # baseline 側が壊れているのは「取れない」であって「0」ではない。
    # 0 として読むと、どんな値でも「増えている」と報告する誤検出になる
    assert parse_budget("def broken(\n") is None


# -----------------------------------------------------------------------------
# evaluate_ratchet (pure)
# -----------------------------------------------------------------------------


def test_lowering_the_budget_needs_no_record() -> None:
    # 引き下げは常に歓迎される方向。記録を要求すると移設のたびに手間が増える
    assert evaluate_ratchet(100, 200, ()) == []


def test_keeping_the_budget_needs_no_record() -> None:
    # 据え置きが大多数のケース。ここで記録を要求すると検査が邪魔になる
    assert evaluate_ratchet(200, 200, ()) == []


def test_raising_without_a_record_is_reported() -> None:
    # 起票理由そのもの。定数を書き換えるだけで無音に通る経路を塞ぐ
    assert len(evaluate_ratchet(300, 200, ())) == 1


def test_raising_with_a_matching_record_is_allowed() -> None:
    # 上げること自体は禁じない。禁じるのは無音で上げること
    assert evaluate_ratchet(300, 200, (("2026-08-22", 300, "理由"),)) == []


def test_record_for_a_different_value_is_reported() -> None:
    # 記録だけ足して定数を別の値にすると、記録が実態を指さなくなる
    findings = evaluate_ratchet(300, 200, (("2026-08-22", 250, "理由"),))
    assert len(findings) == 1
    assert "250" in findings[0].detail


def test_record_with_a_blank_reason_is_reported() -> None:
    # 理由の非空を要求しないと、記録が「上げた」以上の情報を持たない
    for reason in ("", "   ", "\n"):
        assert evaluate_ratchet(300, 200, (("2026-08-22", 300, reason),)) != [], repr(reason)


def test_record_with_a_malformed_date_is_reported() -> None:
    # 日付が読めないと増加の傾向 (起票理由の「9 日で +44%」) を後から測れない。
    # 形の regex ではなく date.fromisoformat に解釈させるので 13 月 45 日も落ちる
    assert evaluate_ratchet(300, 200, (("2026-13-45", 300, "理由"),)) != []


def test_only_the_last_record_is_consulted() -> None:
    # 過去の記録は履歴。今回の引き上げを説明する責任を持つのは末尾だけ
    raises = (("2026-08-01", 250, "前回"), ("2026-08-22", 300, "今回"))
    assert evaluate_ratchet(300, 200, raises) == []


def test_independent_problems_are_reported_independently() -> None:
    # 値・理由・日付のどれかの検査を他へ従属させると、そこを緩めた瞬間に
    # 残りが無言で vacuous になる (rules_paths の除外検査と同じ理由)
    assert len(evaluate_ratchet(300, 200, (("bad-date", 250, ""),))) == 3


# -----------------------------------------------------------------------------
# check_budget_ratchet (git 越しの baseline)
# -----------------------------------------------------------------------------


def _commit_budget_module(repo: Path, body: str) -> None:
    """予算モジュールだけを持つ repo を作って 1 コミットする。"""
    write_file(repo, BUDGET_MODULE_PATH, body)
    init_repo(repo)
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "init")


def test_repo_without_the_budget_module_is_out_of_scope(tmp_path: Path) -> None:
    # scan() は任意のルートへ走る。config-guard を持たないリポジトリへ
    # 「baseline が取れない」と言っても意味がない
    assert check_budget_ratchet(str(tmp_path), 100, ()) == []


def test_unreachable_baseline_is_reported(tmp_path: Path) -> None:
    # 取れないときに [] を返すと、検査が黙って無効になったのか健全なのかを
    # 区別できなくなる。CI の checkout は既定で PR の merge ref しか持たない
    write_file(tmp_path, BUDGET_MODULE_PATH, "ALWAYS_LOADED_BUDGET_BYTES = 100\n")
    init_repo(tmp_path)

    findings = check_budget_ratchet(str(tmp_path), 100, (), ref="origin/main")

    assert len(findings) == 1
    assert "origin/main" in findings[0].detail


def test_baseline_without_the_constant_is_reported(tmp_path: Path) -> None:
    # 定数を改名すると baseline が読めなくなる。0 と読み替えず落とす
    _commit_budget_module(tmp_path, "OTHER = 1\n")

    findings = check_budget_ratchet(str(tmp_path), 100, (), ref="HEAD")

    assert len(findings) == 1


def test_the_baseline_from_git_drives_the_comparison(tmp_path: Path) -> None:
    # 配線の確認。git から読んだ値が比較へ渡らないと、どんな値でも緑になる。
    # 据え置きの緑だけでは「そもそも見ていない」と区別できないので対照を並べる
    _commit_budget_module(tmp_path, "ALWAYS_LOADED_BUDGET_BYTES = 100\n")

    assert check_budget_ratchet(str(tmp_path), 100, (), ref="HEAD") == []
    assert check_budget_ratchet(str(tmp_path), 101, (), ref="HEAD") != []


# -----------------------------------------------------------------------------
# 実リポジトリ (回帰防止)
# -----------------------------------------------------------------------------


def test_real_repo_has_the_budget_module() -> None:
    # check_budget_ratchet はモジュールが無いと何も見ない。実リポジトリで消えたら
    # 下の回帰テストが vacuous に通るので、存在をここで縛る
    assert (REPO_ROOT / BUDGET_MODULE_PATH).is_file()


def test_real_repo_is_within_the_ratchet() -> None:
    findings = check_budget_ratchet(str(REPO_ROOT), ALWAYS_LOADED_BUDGET_BYTES, BUDGET_RAISES)
    assert findings == [], [f.detail for f in findings]
