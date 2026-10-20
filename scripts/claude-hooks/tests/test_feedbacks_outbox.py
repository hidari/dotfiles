"""feedbacks-outbox フック (送る側) の骨格と除外の仕様。

判定のロジックはフックを in-process にロードして検査し、起動形 (どの引数でも exit 0 で
無出力) は subprocess で見る。箱の位置は literal で pin するので、箱の位置を差し替える
FEEDBACKS_BOX_DIR は落とした環境で見る。
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest
from conftest import HOOKS_DIR, REPO_ROOT, git_scope_free_env, load_hook, make_git_repo

HOOK = HOOKS_DIR / "feedbacks-outbox.py"
hook = load_hook(HOOK.name)


@pytest.fixture
def config_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """skill が入った設定ディレクトリ。除外の対照を作る土台。"""
    path = tmp_path / "claude-config"
    skill = path / "skills" / hook.SKILL_NAME / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("x")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(path))
    return path


@pytest.fixture
def state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """状態ファイルの置き場を tmp へ向ける。"""
    path = tmp_path / "state"
    monkeypatch.setenv("FEEDBACKS_OUTBOX_STATE_DIR", str(path))
    return path


@pytest.fixture
def repo(tmp_path: Path, git_location_vars_stripped: None) -> Path:
    return make_git_repo(tmp_path / "repo")


def _payload(cwd: Path, **extra: object) -> dict[str, object]:
    return {"cwd": str(cwd), "session_id": "s1", **extra}


def test_全条件を満たすとリポジトリルートを返す(repo: Path, config_dir: Path) -> None:
    assert hook.active(_payload(repo)) == repo.resolve()


def test_subagentでは動かない(repo: Path, config_dir: Path) -> None:
    assert hook.active(_payload(repo, agent_id="a1")) is None


@pytest.mark.parametrize("cwd", [None, 1, "/nonexistent-dir-for-test"])
def test_cwdが無いか実在しなければ動かない(cwd: object, config_dir: Path) -> None:
    assert hook.active({"cwd": cwd}) is None


def test_cwdの欠落では動かない(config_dir: Path) -> None:
    assert hook.active({}) is None


def test_受け箱を持つリポジトリでは動かない(repo: Path, config_dir: Path) -> None:
    (repo / "docs" / ".feedbacks-box").mkdir(parents=True)
    assert hook.active(_payload(repo)) is None


def test_skillが入っていなければ動かない(
    repo: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty-config"
    empty.mkdir()
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(empty))
    assert hook.active(_payload(repo)) is None


def test_CLAUDE_CONFIG_DIRが無ければホームの設定を見る(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert not hook.skill_installed()
    skill = tmp_path / ".claude" / "skills" / "cross-repo-learnings" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("x")
    assert hook.skill_installed()


def test_まとめの置き場はリポジトリ直下のcacheディレクトリになる(repo: Path) -> None:
    assert (
        hook.outbox_path(str(repo), "abc")
        == repo.resolve() / ".cache" / "feedbacks-outbox" / "abc.md"
    )


def test_session_idの区切り文字は潰して置き場の外へ出さない(repo: Path) -> None:
    path = hook.outbox_path(str(repo), "../../x/y")
    assert path.parent == repo.resolve() / ".cache" / "feedbacks-outbox"
    assert path.name == "______x_y.md"


def test_dotfilesの箱は自分の実体から導く(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FEEDBACKS_BOX_DIR", raising=False)
    assert hook.dotfiles_box() == REPO_ROOT / "docs" / ".feedbacks-box"


def test_環境変数があれば箱の位置を差し替える(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FEEDBACKS_BOX_DIR", str(tmp_path / "box"))
    assert hook.dotfiles_box() == tmp_path / "box"


@pytest.mark.parametrize("subcommand", ["session", "stop", "end", "unknown"])
@pytest.mark.parametrize("stdin", ["{not json", "[]", ""])
def test_壊れた入力でも無出力でexit0(subcommand: str, stdin: str, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(HOOK), subcommand],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=git_scope_free_env(),
        check=False,
    )
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_引数が無くても無出力でexit0(tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=json.dumps({}),
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=git_scope_free_env(),
        check=False,
    )
    assert (result.returncode, result.stdout) == (0, "")


def _context(output: dict[str, object] | None) -> str:
    assert output is not None
    specific = output["hookSpecificOutput"]
    assert isinstance(specific, dict)
    assert specific["hookEventName"] == "SessionStart"
    return str(specific["additionalContext"])


def test_置き場とskill名を告げる(repo: Path, config_dir: Path, state_dir: Path) -> None:
    context = _context(hook.handle_session(_payload(repo)))
    assert json.dumps(str(hook.outbox_path(str(repo), "s1")), ensure_ascii=False) in context
    assert hook.SKILL_NAME in context


def test_基準時刻を記録する(repo: Path, config_dir: Path, state_dir: Path) -> None:
    before = int(time.time())
    hook.handle_session(_payload(repo))
    after = int(time.time())
    state = json.loads((state_dir / "s1.json").read_text())
    assert before <= state["since"] <= after
    assert state["nudges"] == 0
    assert state["outbox"] == str(hook.outbox_path(str(repo), "s1"))
    assert state["repo"] == "repo"
    assert list(state_dir.iterdir()) == [state_dir / "s1.json"]


def test_compactやresumeで再実行しても基準時刻を巻き戻さない(
    repo: Path, config_dir: Path, state_dir: Path
) -> None:
    state_dir.mkdir()
    existing = {"since": 1, "nudges": 2, "outbox": "/x.md", "repo": "old"}
    (state_dir / "s1.json").write_text(json.dumps(existing))
    assert hook.handle_session(_payload(repo)) is not None
    assert json.loads((state_dir / "s1.json").read_text()) == existing


def test_除外の条件では何も告げず状態も作らない(
    repo: Path, config_dir: Path, state_dir: Path
) -> None:
    assert hook.handle_session(_payload(repo, agent_id="a1")) is None
    assert not state_dir.exists()


def test_受け箱を持つリポジトリのlinked_worktreeでも告げず状態も作らない(
    repo: Path, config_dir: Path, state_dir: Path, tmp_path: Path
) -> None:
    (repo / "docs" / ".feedbacks-box").mkdir(parents=True)
    env = git_scope_free_env()
    for args in (
        ["commit", "-q", "--allow-empty", "-m", "x"],
        ["worktree", "add", "-q", str(tmp_path / "wt")],
    ):
        subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env)
    assert not (tmp_path / "wt" / "docs" / ".feedbacks-box").exists()
    assert hook.handle_session(_payload(tmp_path / "wt")) is None
    assert not state_dir.exists()


def test_repo名は区切り文字を潰して記録する(
    tmp_path: Path, git_location_vars_stripped: None, config_dir: Path, state_dir: Path
) -> None:
    odd = make_git_repo(tmp_path / "my repo.x")
    hook.handle_session(_payload(odd))
    assert json.loads((state_dir / "s1.json").read_text())["repo"] == "my_repo_x"
