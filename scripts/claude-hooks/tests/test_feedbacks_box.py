"""feedbacks-box フックの仕様。

判定のロジックはフックを in-process にロードして検査する。起動形 (subprocess として走り、
exit 0 で、出力が空か hookSpecificOutput 形の JSON) は subprocess で見る。SessionStart の
JSON はこの形でないと黙って捨てられるので、形そのものを pin する。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
from conftest import HOOKS_DIR, git_scope_free_env, make_git_repo

HOOK = HOOKS_DIR / "feedbacks-box.py"


def _load_hook() -> ModuleType:
    """ハイフンを含むファイル名のフックをモジュールとして読む。"""
    spec = importlib.util.spec_from_file_location("feedbacks_box", HOOK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _box(root: Path) -> Path:
    box = root / "docs" / ".feedbacks-box"
    box.mkdir(parents=True)
    return box


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


def test_箱が無ければ何も告げない(tmp_path: Path) -> None:
    hook = _load_hook()
    repo = make_git_repo(tmp_path / "repo")
    assert hook.handle_session({"cwd": str(repo)}) is None


def test_箱が空なら何も告げない(tmp_path: Path) -> None:
    hook = _load_hook()
    repo = make_git_repo(tmp_path / "repo")
    _box(repo)
    assert hook.handle_session({"cwd": str(repo)}) is None


def test_ドットで始まる名前だけなら何も告げない(tmp_path: Path) -> None:
    """Finder が作る .DS_Store を未処理のフィードバックと数えない。"""
    hook = _load_hook()
    repo = make_git_repo(tmp_path / "repo")
    (_box(repo) / ".DS_Store").write_text("")
    assert hook.handle_session({"cwd": str(repo)}) is None


def test_置かれたものを全て名前で告げる(tmp_path: Path) -> None:
    hook = _load_hook()
    repo = make_git_repo(tmp_path / "repo")
    box = _box(repo)
    (box / "relay-20261007-mise.md").write_text("x")
    (box / "日本語 の 名前.md").write_text("x")
    (box / "束").mkdir()
    (box / ".DS_Store").write_text("")

    context = hook.handle_session({"cwd": str(repo)})["hookSpecificOutput"]["additionalContext"]

    assert str(box) in context
    assert "relay-20261007-mise.md" in context
    assert "日本語 の 名前.md" in context
    assert "束/" in context
    assert ".DS_Store" not in context


def test_worktree_から起動しても本体のチェックアウトの箱を見る(tmp_path: Path) -> None:
    """書く側は本体のチェックアウトの絶対パスへ置く。箱は ignore されるので worktree には無い。"""
    hook = _load_hook()
    repo = make_git_repo(tmp_path / "repo")
    env = git_scope_free_env()
    subprocess.run(
        ["git", "commit", "-q", "--allow-empty", "-m", "init"],
        cwd=repo,
        check=True,
        capture_output=True,
        env=env,
    )
    worktree = tmp_path / "wt"
    subprocess.run(
        ["git", "worktree", "add", "-q", "-b", "wt", str(worktree)],
        cwd=repo,
        check=True,
        capture_output=True,
        env=env,
    )
    (_box(repo) / "from-worktree.md").write_text("x")

    output = hook.handle_session({"cwd": str(worktree)})

    assert output is not None
    assert "from-worktree.md" in output["hookSpecificOutput"]["additionalContext"]


def test_リポジトリの外では_cwd_の箱を見る(tmp_path: Path) -> None:
    hook = _load_hook()
    plain = tmp_path / "plain"
    (_box(plain) / "note.md").write_text("x")
    output = hook.handle_session({"cwd": str(plain)})
    assert output is not None
    assert "note.md" in output["hookSpecificOutput"]["additionalContext"]


@pytest.mark.parametrize("cwd", [None, 1, "/nonexistent/feedbacks-box-test"])
def test_cwd_が使えなければ何も告げない(cwd: object) -> None:
    hook = _load_hook()
    assert hook.handle_session({"cwd": cwd}) is None


def test_起動形は_SessionStart_の_hookSpecificOutput_を返す(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    (_box(repo) / "note.md").write_text("x")

    proc = _run({"cwd": str(repo), "session_id": "test"}, repo)

    assert proc.returncode == 0
    output = json.loads(proc.stdout)
    assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "note.md" in output["hookSpecificOutput"]["additionalContext"]


def test_subagent_では告げない(tmp_path: Path) -> None:
    repo = make_git_repo(tmp_path / "repo")
    (_box(repo) / "note.md").write_text("x")

    proc = _run({"cwd": str(repo), "agent_id": "sub"}, repo)

    assert (proc.returncode, proc.stdout) == (0, "")


@pytest.mark.parametrize("stdin", ["", "not json", "[]"])
def test_壊れた入力でも作業を止めない(tmp_path: Path, stdin: str) -> None:
    proc = _run(stdin, tmp_path)
    assert (proc.returncode, proc.stdout) == (0, "")
