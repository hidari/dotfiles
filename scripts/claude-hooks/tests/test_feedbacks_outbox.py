"""feedbacks-outbox フック (送る側) の骨格と除外の仕様。

判定のロジックはフックを in-process にロードして検査し、起動形 (どの引数でも exit 0 で
無出力) は subprocess で見る。箱の位置は literal で pin するので、箱の位置を差し替える
FEEDBACKS_BOX_DIR は落とした環境で見る。
"""

from __future__ import annotations

import json
import os
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


# --- Stop: コミットのあとに案内する ---

T0 = 1_700_000_000


def _git(repo: Path, *args: str, at: int) -> None:
    """reflog の時刻を固定して git を打つ (reflog は秒単位なので sleep に頼らない)。"""
    stamp = f"{at} +0000"
    env = {**git_scope_free_env(), "GIT_COMMITTER_DATE": stamp, "GIT_AUTHOR_DATE": stamp}
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, env=env)


def _commit(repo: Path, at: int, message: str = "c") -> None:
    _git(repo, "commit", "-q", "--allow-empty", "-m", message, at=at)


def _write_state(state_dir: Path, **fields: object) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    state = {"since": T0, "nudges": 0, "outbox": "/o/s1.md", "repo": "repo", **fields}
    path = state_dir / "s1.json"
    path.write_text(json.dumps(state))
    return path


def _stop_context(output: dict[str, object] | None) -> str:
    assert output is not None
    specific = output["hookSpecificOutput"]
    assert isinstance(specific, dict)
    assert specific["hookEventName"] == "Stop"
    assert "decision" not in output
    return str(specific["additionalContext"])


def test_基準のあとのコミットで案内する(repo: Path, config_dir: Path, state_dir: Path) -> None:
    _write_state(state_dir, outbox="/o/s 1.md")
    _commit(repo, T0 + 10)
    context = _stop_context(hook.handle_stop(_payload(repo)))
    assert json.dumps("/o/s 1.md", ensure_ascii=False) in context
    assert hook.SKILL_NAME in context
    assert "知見が無ければ何もしない" in context


def test_基準より前のコミットでは案内しない(repo: Path, config_dir: Path, state_dir: Path) -> None:
    _commit(repo, T0 - 10)
    _write_state(state_dir)
    assert hook.handle_stop(_payload(repo)) is None


def test_基準と同じ秒のコミットでは案内しない(
    repo: Path, config_dir: Path, state_dir: Path
) -> None:
    _commit(repo, T0)
    _write_state(state_dir)
    assert hook.handle_stop(_payload(repo)) is None


def test_ブランチの切り替えだけでは案内しない(
    repo: Path, config_dir: Path, state_dir: Path
) -> None:
    _commit(repo, T0 - 10)
    _write_state(state_dir)
    _git(repo, "checkout", "-q", "-b", "other", at=T0 + 10)
    _git(repo, "checkout", "-q", "-", at=T0 + 20)
    assert hook.handle_stop(_payload(repo)) is None


def test_amendだけでは案内しない(repo: Path, config_dir: Path, state_dir: Path) -> None:
    _commit(repo, T0 - 10)
    _write_state(state_dir)
    _git(repo, "commit", "-q", "--amend", "--allow-empty", "-m", "again", at=T0 + 10)
    assert hook.handle_stop(_payload(repo)) is None


def test_resetだけでは案内しない(repo: Path, config_dir: Path, state_dir: Path) -> None:
    _commit(repo, T0 - 20)
    _commit(repo, T0 - 10)
    _write_state(state_dir)
    _git(repo, "reset", "-q", "--hard", "HEAD~1", at=T0 + 10)
    assert hook.handle_stop(_payload(repo)) is None


def test_commits_sinceは件名の接頭辞で数える(repo: Path) -> None:
    _commit(repo, T0 + 1)
    _git(repo, "checkout", "-q", "-b", "side", at=T0 + 2)
    _commit(repo, T0 + 3)
    _git(repo, "checkout", "-q", "-", at=T0 + 4)
    _commit(repo, T0 + 5)
    _git(repo, "merge", "-q", "--no-ff", "-m", "m", "side", at=T0 + 6)
    _git(repo, "commit", "-q", "--amend", "--allow-empty", "-m", "a", at=T0 + 7)
    # initial と通常のコミットを数え、checkout・merge の自動コミット・amend は数えない
    assert sorted(hook.commits_since(repo, 0)) == [T0 + 1, T0 + 3, T0 + 5]
    assert sorted(hook.commits_since(repo, T0 + 3)) == [T0 + 5]


def test_衝突を解いたマージのコミットは数える(repo: Path) -> None:
    (repo / "f").write_text("base")
    _git(repo, "add", "f", at=T0)
    _commit(repo, T0 + 1)
    _git(repo, "checkout", "-q", "-b", "side", at=T0 + 2)
    (repo / "f").write_text("side")
    _git(repo, "commit", "-q", "-am", "side", at=T0 + 3)
    _git(repo, "checkout", "-q", "-", at=T0 + 4)
    (repo / "f").write_text("main")
    _git(repo, "commit", "-q", "-am", "main", at=T0 + 5)
    stamp = f"{T0 + 6} +0000"
    env = {**git_scope_free_env(), "GIT_COMMITTER_DATE": stamp, "GIT_AUTHOR_DATE": stamp}
    merge = subprocess.run(
        ["git", "merge", "-q", "side"], cwd=repo, capture_output=True, env=env, check=False
    )
    assert merge.returncode != 0
    (repo / "f").write_text("resolved")
    _git(repo, "commit", "-q", "-a", "--no-edit", at=T0 + 7)
    assert T0 + 7 in hook.commits_since(repo, T0 + 6)


def test_案内したコミットでは二度案内しない(repo: Path, config_dir: Path, state_dir: Path) -> None:
    path = _write_state(state_dir)
    _commit(repo, T0 + 10)
    assert hook.handle_stop(_payload(repo)) is not None
    state = json.loads(path.read_text())
    assert (state["since"], state["nudges"]) == (T0 + 10, 1)
    assert hook.handle_stop(_payload(repo)) is None


def test_新しいコミットがあれば再び案内する(repo: Path, config_dir: Path, state_dir: Path) -> None:
    path = _write_state(state_dir)
    _commit(repo, T0 + 10)
    assert hook.handle_stop(_payload(repo)) is not None
    _commit(repo, T0 + 20)
    _commit(repo, T0 + 30)
    assert hook.handle_stop(_payload(repo)) is not None
    state = json.loads(path.read_text())
    assert (state["since"], state["nudges"]) == (T0 + 30, 2)


def test_案内はMAX_NUDGES回まで(repo: Path, config_dir: Path, state_dir: Path) -> None:
    path = _write_state(state_dir)
    for i in range(hook.MAX_NUDGES):
        _commit(repo, T0 + 10 * (i + 1))
        assert hook.handle_stop(_payload(repo)) is not None
    _commit(repo, T0 + 1000)
    before = path.read_bytes()
    assert hook.handle_stop(_payload(repo)) is None
    assert path.read_bytes() == before


def test_stop_hook_activeでは判定せず状態も変えない(
    repo: Path, config_dir: Path, state_dir: Path
) -> None:
    path = _write_state(state_dir)
    _commit(repo, T0 + 10)
    before = path.read_bytes()
    assert hook.handle_stop(_payload(repo, stop_hook_active=True)) is None
    assert path.read_bytes() == before


def test_状態が無ければ基準を作るだけで案内しない(
    repo: Path, config_dir: Path, state_dir: Path
) -> None:
    _commit(repo, T0 + 10)
    before = int(time.time())
    assert hook.handle_stop(_payload(repo)) is None
    state = json.loads((state_dir / "s1.json").read_text())
    assert before <= state["since"] <= int(time.time())
    assert state["nudges"] == 0
    assert state["outbox"] == str(hook.outbox_path(str(repo), "s1"))
    assert state["repo"] == "repo"


@pytest.mark.parametrize(
    "content",
    [
        "{not json",
        "[]",
        '"x"',
        # 各検査を単独で外すと対応する形だけが生き残るよう、他の項目は正しい値にする
        json.dumps({"since": "1", "nudges": 0, "outbox": "/o"}),
        json.dumps({"nudges": 0, "outbox": "/o"}),
        json.dumps({"since": True, "nudges": 0, "outbox": "/o"}),
        json.dumps({"since": 1, "nudges": "0", "outbox": "/o"}),
        json.dumps({"since": 1, "nudges": 0}),
        json.dumps({"since": 1, "nudges": 0, "outbox": 1}),
    ],
)
def test_壊れた状態は無いものとして基準を作り直し案内しない(
    content: str, repo: Path, config_dir: Path, state_dir: Path
) -> None:
    state_dir.mkdir()
    (state_dir / "s1.json").write_text(content)
    _commit(repo, T0 + 10)
    before = int(time.time())
    assert hook.handle_stop(_payload(repo)) is None
    state = json.loads((state_dir / "s1.json").read_text())
    assert before <= state["since"] <= int(time.time())
    assert state["nudges"] == 0


def test_コミットが無いリポジトリでは案内せず状態も変えない(
    repo: Path, config_dir: Path, state_dir: Path
) -> None:
    path = _write_state(state_dir)
    before = path.read_bytes()
    assert hook.handle_stop(_payload(repo)) is None
    assert path.read_bytes() == before


def test_reflogを読めなければコミットが無いものとして扱う(
    repo: Path, config_dir: Path, state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write_state(state_dir)
    _commit(repo, T0 + 10)
    before = path.read_bytes()

    def boom(*args: object, **kwargs: object) -> None:
        raise subprocess.TimeoutExpired("git", 1)

    monkeypatch.setattr(hook.subprocess, "run", boom)
    assert hook.handle_stop(_payload(repo)) is None
    assert path.read_bytes() == before


def test_除外の条件ではStopも状態を読み書きしない(
    repo: Path, config_dir: Path, state_dir: Path
) -> None:
    assert hook.handle_stop(_payload(repo, agent_id="a1")) is None
    assert not state_dir.exists()


# --- SessionEnd と次の SessionStart: 箱へ届ける ---

TODAY = "2026-10-20"


@pytest.fixture
def box(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """handle_end / handle_session が届ける先の箱。実在する空の箱を tmp に作る。"""
    path = tmp_path / "box"
    path.mkdir()
    monkeypatch.setenv("FEEDBACKS_BOX_DIR", str(path))
    return path


def _summary(repo: Path, session_id: str, body: bytes = "知見\n".encode()) -> Path:
    path: Path = hook.outbox_path(str(repo), session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    return path


def _boxed(box: Path) -> list[Path]:
    return sorted(box.iterdir())


def test_まとめを箱へ届けて元を消す(tmp_path: Path, box: Path) -> None:
    outbox = tmp_path / "sessionabc.md"
    body = "知見\r\n末尾なし".encode()
    outbox.write_bytes(body)
    delivered = hook.deliver(outbox, box, "repo", TODAY)
    assert delivered == box / "from-repo-2026-10-20-sessiona.md"
    assert delivered.read_bytes() == body
    assert _boxed(box) == [delivered]
    assert not outbox.exists()


def test_まとめが無ければ何もしない(tmp_path: Path, box: Path) -> None:
    assert hook.deliver(tmp_path / "none.md", box, "repo", TODAY) is None
    assert _boxed(box) == []


def test_箱が無ければまとめを残す(tmp_path: Path) -> None:
    outbox = tmp_path / "s1.md"
    outbox.write_text("x")
    assert hook.deliver(outbox, tmp_path / "no-box", "repo", TODAY) is None
    assert outbox.read_text() == "x"
    assert not (tmp_path / "no-box").exists()


def test_同名のファイルが箱にあれば上書きしない(tmp_path: Path, box: Path) -> None:
    outbox = tmp_path / "s1.md"
    outbox.write_text("new")
    existing = box / "from-repo-2026-10-20-s1.md"
    existing.write_text("old")
    assert hook.deliver(outbox, box, "repo", TODAY) is None
    assert existing.read_text() == "old"
    assert outbox.read_text() == "new"
    assert _boxed(box) == [existing]


@pytest.mark.parametrize("body", [b"", b" \n\t\n"])
def test_空のまとめは届けずに消す(tmp_path: Path, box: Path, body: bytes) -> None:
    outbox = tmp_path / "s1.md"
    outbox.write_bytes(body)
    assert hook.deliver(outbox, box, "repo", TODAY) is None
    assert not outbox.exists()
    assert _boxed(box) == []


def test_書きかけを箱に残さない(tmp_path: Path, box: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    outbox = tmp_path / "s1.md"
    outbox.write_text("x")

    def boom(*args: object, **kwargs: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(hook.os, "replace", boom)
    with pytest.raises(OSError):
        hook.deliver(outbox, box, "repo", TODAY)
    assert _boxed(box) == []
    assert outbox.read_text() == "x"


def test_SessionEndは自分のまとめを届ける(
    repo: Path, config_dir: Path, state_dir: Path, box: Path
) -> None:
    hook.handle_session(_payload(repo))
    outbox = _summary(repo, "s1")
    assert hook.handle_end(_payload(repo)) is None
    (delivered,) = _boxed(box)
    assert delivered.name.startswith("from-repo-")
    assert delivered.name.endswith("-s1.md")
    assert delivered.read_bytes() == "知見\n".encode()
    assert not outbox.exists()


def test_二重に届けない(repo: Path, config_dir: Path, state_dir: Path, box: Path) -> None:
    hook.handle_session(_payload(repo))
    _summary(repo, "s1")
    hook.handle_end(_payload(repo))
    hook.handle_end(_payload(repo))
    assert len(_boxed(box)) == 1


def test_SessionEndは状態が無ければ何もしない(repo: Path, state_dir: Path, box: Path) -> None:
    outbox = _summary(repo, "s1")
    assert hook.handle_end(_payload(repo)) is None
    assert outbox.exists()
    assert _boxed(box) == []


def test_SessionEndは壊れた状態では何もしない(repo: Path, state_dir: Path, box: Path) -> None:
    outbox = _summary(repo, "s1")
    state_dir.mkdir()
    (state_dir / "s1.json").write_text("{not json")
    assert hook.handle_end(_payload(repo)) is None
    assert outbox.exists()
    assert _boxed(box) == []


def test_SessionEndはsubagentでは何もしない(
    repo: Path, config_dir: Path, state_dir: Path, box: Path
) -> None:
    hook.handle_session(_payload(repo))
    outbox = _summary(repo, "s1")
    assert hook.handle_end(_payload(repo, agent_id="a1")) is None
    assert outbox.exists()
    assert _boxed(box) == []


def test_SessionEndはsession_idが無ければ何もしない(state_dir: Path, box: Path) -> None:
    assert hook.handle_end({"cwd": "/"}) is None
    assert _boxed(box) == []


def test_SessionEndはgitを起動しない(
    repo: Path, config_dir: Path, state_dir: Path, box: Path, tmp_path: Path
) -> None:
    hook.handle_session(_payload(repo))
    outbox = _summary(repo, "s1")
    # PATH 上の git は起動されたら印を残す偽物。起動していなければ印は無い
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    marker = tmp_path / "git-was-run"
    fake = bin_dir / "git"
    # PATH には偽の git しか無いので、印は外部コマンドを使わずシェルの組み込みで残す
    fake.write_text(f"#!/bin/sh\n: > {marker}\nexit 1\n")
    fake.chmod(0o755)
    env = {
        **git_scope_free_env(),
        "PATH": str(bin_dir),
        "FEEDBACKS_BOX_DIR": str(box),
        "FEEDBACKS_OUTBOX_STATE_DIR": str(state_dir),
    }
    result = subprocess.run(
        [sys.executable, str(HOOK), "end"],
        input=json.dumps(_payload(repo)),
        capture_output=True,
        text=True,
        cwd=tmp_path,
        env=env,
        check=False,
    )
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")
    assert not marker.exists()
    assert len(_boxed(box)) == 1
    assert not outbox.exists()


def _age(path: Path, seconds: int) -> None:
    old = time.time() - seconds
    os.utime(path, (old, old))


def test_次のSessionStartで古い取り残しを届ける(
    repo: Path, config_dir: Path, state_dir: Path, box: Path
) -> None:
    stale = _summary(repo, "other1")
    _age(stale, hook.RECOVER_AFTER_SECONDS + 60)
    current = _summary(repo, "s1")
    _age(current, hook.RECOVER_AFTER_SECONDS + 60)
    assert hook.handle_session(_payload(repo)) is not None
    (delivered,) = _boxed(box)
    # 名前の repo と日付は回収する今のセッションのもの、末尾は取り残しの持ち主のもの
    today = time.strftime("%Y-%m-%d", time.gmtime())
    assert delivered.name == f"from-repo-{today}-other1.md"
    assert not stale.exists()
    # 今のセッションのまとめは古くても届けない
    assert current.exists()


def test_新しい他のセッションのまとめは回収しない(
    repo: Path, config_dir: Path, state_dir: Path, box: Path
) -> None:
    live = _summary(repo, "other1")
    _age(live, hook.RECOVER_AFTER_SECONDS - 600)
    assert hook.handle_session(_payload(repo)) is not None
    assert live.exists()
    assert _boxed(box) == []


def test_回収は他のセッションの取り残しを全て届ける(
    repo: Path, config_dir: Path, state_dir: Path, box: Path
) -> None:
    for name in ("aaa", "bbb"):
        _age(_summary(repo, name), hook.RECOVER_AFTER_SECONDS + 60)
    hook.handle_session(_payload(repo))
    assert len(_boxed(box)) == 2


def test_箱が無ければ回収せずSessionStartの告知は返す(
    repo: Path, config_dir: Path, state_dir: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FEEDBACKS_BOX_DIR", str(tmp_path / "no-box"))
    stale = _summary(repo, "other1")
    _age(stale, hook.RECOVER_AFTER_SECONDS + 60)
    assert hook.handle_session(_payload(repo)) is not None
    assert stale.exists()


def test_回収に失敗してもSessionStartの告知と状態は作る(
    repo: Path, config_dir: Path, state_dir: Path, box: Path
) -> None:
    stale = _summary(repo, "other1")
    _age(stale, hook.RECOVER_AFTER_SECONDS + 60)
    box.chmod(0o500)
    try:
        assert hook.handle_session(_payload(repo)) is not None
    finally:
        box.chmod(0o700)
    assert stale.exists()
    assert (state_dir / "s1.json").exists()


def test_除外の条件では回収もしない(
    repo: Path, config_dir: Path, state_dir: Path, box: Path
) -> None:
    stale = _summary(repo, "other1")
    _age(stale, hook.RECOVER_AFTER_SECONDS + 60)
    assert hook.handle_session(_payload(repo, agent_id="a1")) is None
    assert stale.exists()


def test_linked_worktreeのまとめは本体のディレクトリ名で届く(
    tmp_path: Path, git_location_vars_stripped: None, config_dir: Path, state_dir: Path, box: Path
) -> None:
    main = make_git_repo(tmp_path / "main-repo")
    _git(main, "commit", "-q", "--allow-empty", "-m", "x", at=T0)
    _git(main, "worktree", "add", "-q", str(tmp_path / "wt-name"), at=T0)
    wt = tmp_path / "wt-name"
    hook.handle_session(_payload(wt))
    _summary(wt, "s1")
    hook.handle_end(_payload(wt))
    (delivered,) = _boxed(box)
    assert delivered.name.startswith("from-main-repo-")
    assert "wt-name" not in delivered.name
