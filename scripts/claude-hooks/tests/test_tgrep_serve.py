"""tgrep serve の寿命をセッションへ合わせる hook の仕様。

判定ロジックは in-process で呼び、起動形だけ最後に 1 件 subprocess で見る
(test_guard_health.py と同じ形)。
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest
import tgrep_serve_state as state
from conftest import HOOKS_DIR, make_git_repo

HOOK = HOOKS_DIR / "tgrep-serve.py"


def _load_hook() -> ModuleType:
    """ハイフンを含むファイル名のフックをモジュールとして読む。"""
    spec = importlib.util.spec_from_file_location("tgrep_serve", HOOK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """状態ファイルの置き場を使い捨てディレクトリへ向ける。"""
    target = tmp_path / "state"
    monkeypatch.setenv("TGREP_SERVE_STATE_DIR", str(target))
    return target


def test_状態ファイル名は_charset_を潰すと衝突する_2_つの_root_で別になる(state_dir: Path) -> None:
    # sanitize (非英数を _ へ潰す) を使うとこの 2 つは同じ名前へ落ちる
    a = state.state_file(Path("/tmp/a/b"))
    b = state.state_file(Path("/tmp/a_b"))
    assert a != b


def test_register_した_pid_が_live_pids_に現れる(state_dir: Path) -> None:
    root = Path("/tmp/repo-one")
    assert state.register(root, os.getpid()) == [os.getpid()]
    assert state.live_pids(root) == [os.getpid()]


def test_死んでいる_pid_は数えない(state_dir: Path) -> None:
    root = Path("/tmp/repo-two")
    state.register(root, os.getpid())
    # 実在しない PID を直接書き込む。記録はスナップショットなので信じて数えない
    path = state.state_file(root)
    path.write_text(
        json.dumps({"root": str(root), "pids": [os.getpid(), 2**22 - 1]}) + "\n",
        encoding="utf-8",
    )
    assert state.live_pids(root) == [os.getpid()]


def test_unregister_で_0_件になると状態ファイルごと消える(state_dir: Path) -> None:
    root = Path("/tmp/repo-three")
    state.register(root, os.getpid())
    assert state.unregister(root, os.getpid()) == []
    assert not state.state_file(root).exists()


def test_unregister_は他の生存_pid_を残す(state_dir: Path) -> None:
    root = Path("/tmp/repo-four")
    state.register(root, os.getpid())
    state.register(root, os.getppid())
    remaining = state.unregister(root, os.getpid())
    assert remaining == [os.getppid()]
    assert state.state_file(root).exists()


def test_known_roots_は記録された_root_を返す(state_dir: Path) -> None:
    state.register(Path("/tmp/repo-five"), os.getpid())
    state.register(Path("/tmp/repo-six"), os.getpid())
    assert sorted(state.known_roots()) == [Path("/tmp/repo-five"), Path("/tmp/repo-six")]


def test_壊れた状態ファイルは空として扱う(state_dir: Path) -> None:
    root = Path("/tmp/repo-seven")
    path = state.state_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not json", encoding="utf-8")
    assert state.live_pids(root) == []


def test_cache_root_は_XDG_CACHE_HOME_に従う(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert state.cache_root() == tmp_path / "xdg" / "claude"


def test_起動コマンドに_ignore_無視のフラグを渡さない() -> None:
    hook = _load_hook()
    argv = hook.serve_argv(Path("/tmp/repo"))
    # 「含まれない」ことが安全側の決定なので、部分一致ではなく集合として見る。
    # 部分一致だと変異でフラグを足しても赤くならない
    assert "--no-ignore" not in argv
    assert "--no-ignore-parent" not in argv
    assert "--no-ignore-vcs" not in argv
    assert "--hidden" not in argv


def test_起動コマンドに資源上限が渡る() -> None:
    hook = _load_hook()
    argv = hook.serve_argv(Path("/tmp/repo"))
    assert "--max-memory" in argv
    assert "--max-cpu" in argv
    assert argv[:3] == [hook.tgrep_bin(), "serve", "/tmp/repo"]


def test_serve_pid_は生きていない_pid_を_None_に落とす(tmp_path: Path) -> None:
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    (idx / "serve.json").write_text(json.dumps({"pid": 2**22 - 1, "port": 1}), encoding="utf-8")
    assert hook.serve_pid(tmp_path) is None


def test_serve_pid_は生きている_pid_を返す(tmp_path: Path) -> None:
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    (idx / "serve.json").write_text(json.dumps({"pid": os.getpid(), "port": 1}), encoding="utf-8")
    assert hook.serve_pid(tmp_path) == os.getpid()


def test_serve_が動いていれば起動しない(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    (idx / "serve.json").write_text(json.dumps({"pid": os.getpid(), "port": 1}), encoding="utf-8")
    launched: list[list[str]] = []
    monkeypatch.setattr(hook.subprocess, "Popen", lambda cmd, **kw: launched.append(cmd))
    assert hook.start_serve(tmp_path) is False
    assert launched == []


def test_起動は待たずに独立セッションで行う(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    captured: dict[str, object] = {}

    def fake_popen(cmd: list[str], **kwargs: object) -> None:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs

    monkeypatch.setattr(hook.subprocess, "Popen", fake_popen)
    assert hook.start_serve(tmp_path) is True
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    # detach の 3 点。1 つでも欠けるとセッション起動がブロックされるか出力が汚れる
    assert kwargs["start_new_session"] is True
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["stdout"] == subprocess.DEVNULL
    assert kwargs["stderr"] == subprocess.DEVNULL


def test_git_管理外では_root_を返さない(tmp_path: Path) -> None:
    hook = _load_hook()
    assert hook.resolve_root({"cwd": str(tmp_path)}) is None


def test_git_リポジトリなら_root_を返す(tmp_path: Path) -> None:
    hook = _load_hook()
    repo = make_git_repo(tmp_path / "repo")
    resolved = hook.resolve_root({"cwd": str(repo)})
    assert resolved is not None
    assert resolved.resolve() == repo.resolve()


def test_session_pid_は引数を優先し展開されなければ親へ落とす() -> None:
    hook = _load_hook()
    assert hook.session_pid(["tgrep-serve.py", "start", "4242"]) == 4242
    # シェルを経由せず $PPID が展開されなかった場合
    assert hook.session_pid(["tgrep-serve.py", "start", "$PPID"]) == os.getppid()
    assert hook.session_pid(["tgrep-serve.py", "start"]) == os.getppid()


def test_停止は_SIGINT_を送る(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    (idx / "serve.json").write_text(json.dumps({"pid": os.getpid(), "port": 1}), encoding="utf-8")
    sent: list[tuple[int, int]] = []
    # hook.os は os モジュールそのもの (共有シングルトン) なので、ここを差し替えると
    # tgrep_serve_state.is_alive が内部で呼ぶ os.kill(pid, 0) の生存確認プローブも一緒に
    # 記録されてしまう (実測)。is_alive はここでは常に True で固定し、記録対象を
    # stop_serve 自身が送る SIGINT だけに絞る
    monkeypatch.setattr(state, "is_alive", lambda pid: True)
    monkeypatch.setattr(hook.os, "kill", lambda pid, sig: sent.append((pid, sig)))
    assert hook.stop_serve(tmp_path) is True
    # SIGTERM は graceful handler を通らず serve.json を古いまま残す (実測)
    assert sent == [(os.getpid(), hook.signal.SIGINT)]


def test_生存セッションが残っていれば止めない(
    tmp_path: Path, state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    # git リポジトリにしないと resolve_root が手前で None を返し、狙った分岐へ届かない。
    # register する root も resolve_root が返すものに揃える (tmp_path と --show-toplevel は
    # symlink の解決で食い違いうる)
    repo = make_git_repo(tmp_path / "repo")
    root = hook.resolve_root({"cwd": str(repo)})
    assert root is not None
    state.register(root, os.getpid())
    state.register(root, os.getppid())
    stopped: list[Path] = []

    def _fake_stop(r: Path) -> bool:
        stopped.append(r)
        return True

    monkeypatch.setattr(hook, "stop_serve", _fake_stop)
    hook.handle_end({"cwd": str(repo)}, os.getpid())
    assert stopped == []
    # 手前の検査を通過していることの対照。ここが空だと上の空も意味を持たない
    assert state.live_pids(root) == sorted({os.getppid()})


def test_最後の_1_人が抜けたら止める(
    tmp_path: Path, state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    repo = make_git_repo(tmp_path / "repo")
    root = hook.resolve_root({"cwd": str(repo)})
    assert root is not None
    state.register(root, os.getpid())
    stopped: list[Path] = []

    def _fake_stop(r: Path) -> bool:
        stopped.append(r)
        return True

    monkeypatch.setattr(hook, "stop_serve", _fake_stop)
    hook.handle_end({"cwd": str(repo)}, os.getpid())
    assert stopped == [root]
    assert not state.state_file(root).exists()


def test_回収は生存_0_の_root_だけを止める(
    tmp_path: Path, state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    alive = tmp_path / "alive"
    dead = tmp_path / "dead"
    state.register(alive, os.getpid())
    # 実在しない PID だけが記録された root
    dead_file = state.state_file(dead)
    dead_file.parent.mkdir(parents=True, exist_ok=True)
    dead_file.write_text(
        json.dumps({"root": str(dead), "pids": [2**22 - 1]}) + "\n", encoding="utf-8"
    )
    stopped: list[Path] = []

    def _fake_stop(r: Path) -> bool:
        stopped.append(r)
        return True

    monkeypatch.setattr(hook, "stop_serve", _fake_stop)
    assert hook.reap() == [dead]
    assert stopped == [dead]
    assert not dead_file.exists()
    assert state.state_file(alive).exists()


def test_フックは_stdin_を読んで_exit_0_で終わる(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["TGREP_SERVE_STATE_DIR"] = str(tmp_path / "state")
    env["TGREP_BIN"] = "/usr/bin/false"
    payload = json.dumps({"hook_event_name": "SessionStart", "cwd": str(tmp_path)})
    result = subprocess.run(
        [sys.executable, str(HOOK), "start", str(os.getpid())],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""
