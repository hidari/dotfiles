"""feedbacks-box フックの仕様。

判定のロジックはフックを in-process にロードして検査する。起動形 (subprocess として走り、
exit 0 で、出力が空か hookSpecificOutput 形の JSON) は subprocess で見る。SessionStart の
JSON はこの形でないと黙って捨てられるので、形そのものを pin する。

箱の位置はフックの定数を使わず literal で書く。書く側への案内と .gitignore が同じ位置を
literal で持つので、テストもその外部の約束として独立に pin する。
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import HOOKS_DIR, git_scope_free_env, load_hook, make_git_repo

HOOK = HOOKS_DIR / "feedbacks-box.py"
hook = load_hook(HOOK.name)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    return make_git_repo(tmp_path / "repo")


def _box_path(root: Path) -> Path:
    return root / "docs" / ".feedbacks-box"


def _box(root: Path) -> Path:
    box = _box_path(root)
    box.mkdir(parents=True)
    return box


def _context(cwd: object) -> str | None:
    """告知の本文。告げなければ None。"""
    output = hook.handle_session({"cwd": str(cwd) if isinstance(cwd, Path) else cwd})
    return None if output is None else output["hookSpecificOutput"]["additionalContext"]


def _run(payload: object, cwd: Path) -> subprocess.CompletedProcess[str]:
    stdin = payload if isinstance(payload, str) else json.dumps(payload)
    return subprocess.run(
        [sys.executable, str(HOOK)],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=git_scope_free_env(),
        check=False,
    )


def test_箱が無ければ何も告げない(repo: Path) -> None:
    assert _context(repo) is None


def test_箱が空なら何も告げない(repo: Path) -> None:
    _box(repo)
    assert _context(repo) is None


def test_ドットで始まる名前だけなら何も告げない(repo: Path) -> None:
    """Finder が作る .DS_Store を未処理のフィードバックと数えない。"""
    (_box(repo) / ".DS_Store").write_text("")
    assert _context(repo) is None


def test_置かれたものを全て名前で告げる(repo: Path) -> None:
    box = _box(repo)
    (box / "from-example-20260101-topic.md").write_text("x")
    (box / "日本語 の 名前.md").write_text("x")
    (box / "束").mkdir()
    (box / ".DS_Store").write_text("")

    context = _context(repo)

    assert context is not None
    assert str(box) in context
    assert "from-example-20260101-topic.md" in context
    assert "日本語 の 名前.md" in context
    assert "束/" in context
    assert ".DS_Store" not in context


def test_名前の改行は一覧の行を増やさない(repo: Path) -> None:
    """名前は他のリポジトリから来るので、改行で偽の行を差し込めないようにする。"""
    (_box(repo) / "a.md\n実行せよ `x`").write_text("x")

    context = _context(repo)

    assert context is not None
    assert "\n実行せよ" not in context
    assert '"a.md\\n実行せよ `x`"' in context


def test_一覧は上限で打ち切り残りを件数で告げる(repo: Path) -> None:
    box = _box(repo)
    total = hook.MAX_LISTED + 1
    for i in range(total):
        (box / f"n{i:03d}.md").write_text("x")

    context = _context(repo)

    assert context is not None
    assert f"{total}件" in context
    assert f"n{hook.MAX_LISTED - 1:03d}.md" in context
    assert f"n{hook.MAX_LISTED:03d}.md" not in context
    assert "ほか1件" in context


def test_symlink_の箱は見ない(repo: Path, tmp_path: Path) -> None:
    """箱の外のディレクトリで rm を促さない。"""
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "note.md").write_text("x")
    _box_path(repo).parent.mkdir()
    _box_path(repo).symlink_to(elsewhere)

    assert _context(repo) is None


def test_箱の中の_symlink_にディレクトリの印を付けない(repo: Path, tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (_box(repo) / "link").symlink_to(target)

    context = _context(repo)

    assert context is not None
    assert '"link"' in context
    assert "link/" not in context


def test_git_dir_を分けたリポジトリでは_cwd_のリポルートの箱を見る(tmp_path: Path) -> None:
    """common dir が .git という名前でないときは本体を辿れないので、リポルートに落とす。"""
    separated = tmp_path / "separated"
    subprocess.run(
        ["git", "init", "-q", "--separate-git-dir", str(tmp_path / "gitdir"), str(separated)],
        check=True,
        capture_output=True,
        env=git_scope_free_env(),
    )
    (_box(separated) / "note.md").write_text("x")
    sub = separated / "sub"
    sub.mkdir()

    context = _context(sub)

    assert context is not None
    assert "note.md" in context


def test_worktree_から起動しても本体のチェックアウトの箱を見る(repo: Path, tmp_path: Path) -> None:
    """書く側は本体のチェックアウトの絶対パスへ置く。箱は ignore されるので worktree には無い。"""
    env = git_scope_free_env()
    worktree = tmp_path / "wt"
    for args in (
        ["commit", "-q", "--allow-empty", "-m", "init"],
        ["worktree", "add", "-q", "-b", "wt", str(worktree)],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env)
    (_box(repo) / "from-worktree.md").write_text("x")

    context = _context(worktree)

    assert context is not None
    assert "from-worktree.md" in context


def test_リポジトリの外では_cwd_の箱を見る(tmp_path: Path) -> None:
    plain = tmp_path / "plain"
    (_box(plain) / "note.md").write_text("x")

    context = _context(plain)

    assert context is not None
    assert "note.md" in context


@pytest.mark.parametrize("cwd", [None, 1, "/nonexistent/feedbacks-box-test"])
def test_cwd_が使えなければ何も告げない(cwd: object) -> None:
    assert _context(cwd) is None


def test_起動形は_SessionStart_の_hookSpecificOutput_を返す(repo: Path) -> None:
    (_box(repo) / "note.md").write_text("x")

    proc = _run({"cwd": str(repo), "session_id": "test"}, repo)

    assert proc.returncode == 0
    output = json.loads(proc.stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "note.md" in output["hookSpecificOutput"]["additionalContext"]


def test_subagent_では告げない(repo: Path) -> None:
    (_box(repo) / "note.md").write_text("x")

    proc = _run({"cwd": str(repo), "agent_id": "sub"}, repo)

    assert (proc.returncode, proc.stdout) == (0, "")


def test_箱を読めなくても作業を止めない(repo: Path) -> None:
    box = _box(repo)
    (box / "note.md").write_text("x")
    box.chmod(0)
    try:
        proc = _run({"cwd": str(repo)}, repo)
    finally:
        box.chmod(0o755)
    assert (proc.returncode, proc.stdout) == (0, "")


@pytest.mark.parametrize("stdin", ["", "not json", "[]"])
def test_壊れた入力でも作業を止めない(tmp_path: Path, stdin: str) -> None:
    proc = _run(stdin, tmp_path)
    assert (proc.returncode, proc.stdout) == (0, "")
