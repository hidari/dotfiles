"""index_flags の仕様テスト。

状態タグの判定 (pure)、tmp リポジトリでの検出、実リポジトリのガードと対照を検証する。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.git_source import SETTINGS_PATH
from config_guard.index_flags import (
    check_index_flags,
    hidden_flag_reason,
    tracked_index_entries,
)
from tests.conftest import REPO_ROOT, init_repo, run_git, write_file


def _init_committed_repo(repo: Path, names: list[str]) -> None:
    """指定した名前のファイルを 1 コミット済みの状態で持つリポジトリを作る。"""
    init_repo(repo)
    for name in names:
        write_file(repo, name, "x\n")
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-m", "init")


# -----------------------------------------------------------------------------
# hidden_flag_reason (pure)
# -----------------------------------------------------------------------------


def test_hidden_flag_reason_flags_skip_worktree() -> None:
    reason = hidden_flag_reason("S")

    assert reason is not None
    assert "skip-worktree" in reason


def test_hidden_flag_reason_flags_assume_unchanged() -> None:
    # assume-unchanged は専用タグを持たず、通常タグを小文字にした形で表れる。
    # S だけを見ると assume-unchanged が素通りする (同じく変更を git から隠す)
    for tag in ("h", "s", "m", "r", "c", "k"):
        reason = hidden_flag_reason(tag)

        assert reason is not None, tag
        assert "assume-unchanged" in reason, tag


def test_hidden_flag_reason_passes_normal_tags() -> None:
    # 偽陽性防止。大文字は変更を隠さない状態なので、どれも報告しない
    for tag in ("H", "M", "R", "C", "K", "?"):
        assert hidden_flag_reason(tag) is None, tag


# -----------------------------------------------------------------------------
# check_index_flags
# -----------------------------------------------------------------------------


def test_check_index_flags_detects_skip_worktree(tmp_path: Path) -> None:
    # 検出したい本体。Issue #8 が解消した二重管理そのもの
    _init_committed_repo(tmp_path, ["a.txt", "b.txt"])
    run_git(tmp_path, "update-index", "--skip-worktree", "a.txt")

    findings = check_index_flags(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].source == "a.txt"
    assert findings[0].detail == "S"
    assert "skip-worktree" in findings[0].message


def test_check_index_flags_detects_assume_unchanged(tmp_path: Path) -> None:
    _init_committed_repo(tmp_path, ["a.txt", "b.txt"])
    run_git(tmp_path, "update-index", "--assume-unchanged", "b.txt")

    findings = check_index_flags(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].source == "b.txt"
    assert findings[0].detail == "h"
    assert "assume-unchanged" in findings[0].message


def test_check_index_flags_passes_a_clean_repo(tmp_path: Path) -> None:
    # 判別力の確認。bit を立てなければ 0 件になる (何を渡しても赤くなる形ではない)
    _init_committed_repo(tmp_path, ["a.txt", "b.txt"])

    assert check_index_flags(str(tmp_path)) == []


def test_check_index_flags_keeps_paths_with_spaces_and_multibyte(tmp_path: Path) -> None:
    # NUL 区切りで受けないと空白や日本語を含むパスが分断される。落ちた分は「エラー」
    # ではなく「短い正常な結果」として返るので、出力を見ても気づけない
    _init_committed_repo(tmp_path, ["b c.txt", "日本語.txt"])
    run_git(tmp_path, "update-index", "--skip-worktree", "b c.txt")
    run_git(tmp_path, "update-index", "--assume-unchanged", "日本語.txt")

    findings = check_index_flags(str(tmp_path))

    assert [finding.source for finding in findings] == ["b c.txt", "日本語.txt"]


def test_check_index_flags_scans_every_tracked_file(tmp_path: Path) -> None:
    # 走査が空振りしていないことの対照。列挙数が追跡ファイル数と一致する
    names = ["a.txt", "b c.txt", "日本語.txt"]
    _init_committed_repo(tmp_path, names)

    assert [path for _, path in tracked_index_entries(str(tmp_path))] == sorted(names)


# -----------------------------------------------------------------------------
# 実リポジトリのガードと、その対照
# -----------------------------------------------------------------------------


def test_repo_has_no_hidden_index_flags() -> None:
    # Issue #8 の帰結を守る。settings.json の skip-worktree を解除して live と committed を
    # 1 本にした。bit が復活すると変更が git から見えなくなり、CI が捕捉できない drift へ戻る
    assert check_index_flags(str(REPO_ROOT)) == []


def test_repo_index_scan_covers_the_settings_file() -> None:
    # 上の 0 件が「健全」であって「1 件も見ていない」ではないことの対照。
    # bit が実際に立っていた settings.json が走査に入っていることを直接確かめる
    paths = {path for _, path in tracked_index_entries(str(REPO_ROOT))}

    assert SETTINGS_PATH in paths
