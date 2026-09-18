"""tgrep serve の寿命をセッションへ合わせる hook の仕様。

判定ロジックは in-process で呼び、起動形だけ最後に 1 件 subprocess で見る
(test_guard_health.py と同じ形)。
"""

from __future__ import annotations

import importlib.util
import json
import os
import shlex
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


def test_起動コマンドは_argv_全体が完全一致する() -> None:
    hook = _load_hook()
    # 「特定のフラグが含まれない」という部分一致だと、tgrep が受け付ける ignore 無視系の
    # 別綴り (-u / -uu / --no-ignore-dot / --no-ignore-exclude / --no-ignore-files /
    # --no-ignore-global) を足す変異が生き残る。argv 全体を完全一致で固定して pin する
    # (資源上限が渡ることも同時に検証する)
    assert hook.serve_argv(Path("/tmp/repo")) == [
        hook.tgrep_bin(),
        "serve",
        "/tmp/repo",
        "--max-memory",
        hook.MAX_MEMORY_MB,
        "--max-cpu",
        hook.MAX_CPU_PERCENT,
    ]


def test_serve_pid_は生きていない_pid_を_None_に落とす(tmp_path: Path) -> None:
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    (idx / "serve.json").write_text(json.dumps({"pid": 2**22 - 1, "port": 1}), encoding="utf-8")
    assert hook.serve_pid(tmp_path) is None


def test_serve_pid_は生きている_pid_を返す(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    (idx / "serve.json").write_text(json.dumps({"pid": os.getpid(), "port": 1}), encoding="utf-8")
    _fake_ps(tmp_path, monkeypatch, "tgrep")
    assert hook.serve_pid(tmp_path) == os.getpid()


def test_serve_pid_は_comm_が_tgrep_でなければ_None_に落とす(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    # 生存している (このテストプロセス自身の) pid だが、別プロセスへ再利用されていた
    # 想定。このマシンの ~/Develop 配下に実在した「serve.json は残るが指す pid は
    # 死んでいる」状態から、さらに一歩進めて「pid が生きてはいるが tgrep ではない」
    # ケースを再現する
    (idx / "serve.json").write_text(json.dumps({"pid": os.getpid(), "port": 1}), encoding="utf-8")
    _fake_ps(tmp_path, monkeypatch, "python3")
    assert hook.serve_pid(tmp_path) is None


def test_serve_が動いていれば起動しない(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    (idx / "serve.json").write_text(json.dumps({"pid": os.getpid(), "port": 1}), encoding="utf-8")
    _fake_ps(tmp_path, monkeypatch, "tgrep")
    launched: list[list[str]] = []
    real_popen = hook.subprocess.Popen

    def fake_popen(cmd: list[str], **kwargs: object) -> object:
        # serve_pid の pid 同一性確認 (subprocess.run 経由の ps 呼び出し) も同じ
        # subprocess.Popen を通るため、無条件に差し替えると壊れる (実測)。
        # tgrep serve の起動だけを横取りし、それ以外は本物へ委譲する
        if cmd and cmd[0] == hook.tgrep_bin():
            launched.append(cmd)
            return None
        return real_popen(cmd, **kwargs)

    monkeypatch.setattr(hook.subprocess, "Popen", fake_popen)
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
    _fake_ps(tmp_path, monkeypatch, "tgrep")
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


def test_停止は_死んでいる_pid_には送らない(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    # 実在しない pid を直接書き込む。stop_serve が serve_pid を経由せず serve.json を
    # 直読みする変異が入ると、mutant も except OSError で False を返すので戻り値だけでは
    # 区別できない (実測)。SIGINT を伴う os.kill 呼び出しが実際に無かったことまで見る
    dead_pid = 2**22 - 1
    (idx / "serve.json").write_text(json.dumps({"pid": dead_pid, "port": 1}), encoding="utf-8")
    sent: list[tuple[int, int]] = []

    def fake_kill(pid: int, sig: int) -> None:
        # is_alive の生存確認プローブ (sig=0) も同じ os.kill を通るため、本物同様に
        # ProcessLookupError を送出して「死んでいる」という判定結果を保つ。そのうえで
        # 呼び出し自体は記録し、SIGINT を伴う呼び出しの有無を後で検証する
        sent.append((pid, sig))
        raise ProcessLookupError

    monkeypatch.setattr(hook.os, "kill", fake_kill)
    assert hook.stop_serve(tmp_path) is False
    assert hook.signal.SIGINT not in [sig for _pid, sig in sent]


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


def test_clear_では停止も回収もしない(
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
    hook.handle_end({"cwd": str(repo), "reason": "clear"}, os.getpid())
    assert stopped == []
    # /clear では unregister 自体も走らない (登録がそのまま残る) ことまで確認する。
    # ここが空だと上の空も意味を持たない
    assert state.live_pids(root) == [os.getpid()]


def _fake_ps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, comm: str) -> None:
    """serve_pid の pid 同一性確認に使う ps を、常に comm を返す偽コマンドへ差し替える。

    既存の TGREP_BIN と同じ形。引数 (`-o comm= -p <pid>`) は無視して固定文字列を返すだけの
    偽コマンドにする。本物の ps を叩くと、テスト実行中の pytest プロセス自身の comm
    (python/Python 等) が返り、"tgrep" と一致しない。
    """
    script = tmp_path / f"fake-ps-{comm}"
    script.write_text(f"#!/bin/sh\necho {comm}\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("TGREP_PS_BIN", str(script))


def test_reap_は自分の_root_を除外する(
    tmp_path: Path, state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    repo = make_git_repo(tmp_path / "repo")
    root = hook.resolve_root({"cwd": str(repo)})
    assert root is not None
    # クラッシュ (SIGKILL) したセッションの痕跡: 登録された生存 pid は 0 件だが、
    # serve 自体はまだ生きている (孤児)
    state_file = state.state_file(root)
    state_file.parent.mkdir(parents=True, exist_ok=True)
    state_file.write_text(
        json.dumps({"root": str(root), "pids": [2**22 - 1]}) + "\n", encoding="utf-8"
    )
    idx = root / ".tgrep"
    idx.mkdir()
    (idx / "serve.json").write_text(json.dumps({"pid": os.getpid(), "port": 1}), encoding="utf-8")
    _fake_ps(tmp_path, monkeypatch, "tgrep")

    stopped: list[Path] = []

    def _fake_stop(r: Path) -> bool:
        stopped.append(r)
        return True

    monkeypatch.setattr(hook, "stop_serve", _fake_stop)
    launched: list[list[str]] = []
    real_popen = hook.subprocess.Popen

    def fake_popen(cmd: list[str], **kwargs: object) -> object:
        # subprocess.Popen は os.kill と同じ共有シングルトンなので、無条件に差し替えると
        # handle_start 内部の resolve_root が使う git (subprocess.run 経由) まで壊れる
        # (実測: subprocess.run が None を返す Popen を with 文へ渡し TypeError になる)。
        # tgrep serve の起動だけを横取りし、それ以外 (git) は本物へ委譲する
        if cmd and cmd[0] == hook.tgrep_bin():
            launched.append(cmd)
            return None
        return real_popen(cmd, **kwargs)

    monkeypatch.setattr(hook.subprocess, "Popen", fake_popen)

    # register する新セッションの pid は state.live_pids がアライブ判定するので、
    # 実在しない値 (4242 等) ではなく実際に生きている pid を使う
    new_pid = os.getppid()
    hook.handle_start({"cwd": str(repo)}, new_pid)

    # 自分の root は reap の対象から除外されるので、健全な孤児 serve を誤って
    # 止めない。除外しなければ stopped == [root] になり、続く start_serve が
    # shutting-down の pid をまだ alive と見て起動を見送る (無言のフォールバック)
    assert stopped == []
    assert launched == []  # 既に生きている serve があるので新規起動もしない
    assert state.live_pids(root) == [new_pid]


def test_handle_start_は登録と起動の両方を行う(
    tmp_path: Path, state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    repo = make_git_repo(tmp_path / "repo")
    launched: list[list[str]] = []
    real_popen = hook.subprocess.Popen

    def fake_popen(cmd: list[str], **kwargs: object) -> object:
        # test_reap_は自分の_root_を除外する と同じ理由で、git 呼び出しは本物へ委譲する
        if cmd and cmd[0] == hook.tgrep_bin():
            launched.append(cmd)
            return None
        return real_popen(cmd, **kwargs)

    monkeypatch.setattr(hook.subprocess, "Popen", fake_popen)
    hook.handle_start({"cwd": str(repo)}, os.getpid())
    root = hook.resolve_root({"cwd": str(repo)})
    assert root is not None
    # register の効果 (状態ファイルに自分の pid が入る)
    assert state.live_pids(root) == [os.getpid()]
    # start_serve の効果 (serve が未起動で、断りのマーカーも無いので Popen が呼ばれる)。
    # マーカー側のテストの対照
    assert not (root / hook.NO_SERVE_MARKER).exists()
    assert launched and launched[0][:3] == [hook.tgrep_bin(), "serve", str(root)]


def test_断りのマーカーがある_root_では登録だけ行い起動しない(
    tmp_path: Path, state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    repo = make_git_repo(tmp_path / "repo")
    (repo / hook.NO_SERVE_MARKER).touch()
    launched: list[list[str]] = []
    real_popen = hook.subprocess.Popen

    def fake_popen(cmd: list[str], **kwargs: object) -> object:
        if cmd and cmd[0] == hook.tgrep_bin():
            launched.append(cmd)
            return None
        return real_popen(cmd, **kwargs)

    monkeypatch.setattr(hook.subprocess, "Popen", fake_popen)
    hook.handle_start({"cwd": str(repo)}, os.getpid())
    root = hook.resolve_root({"cwd": str(repo)})
    assert root is not None
    # 登録までは通っている (対照。ここが空だと下の空は resolve_root で落ちただけと区別できない)
    assert state.live_pids(root) == [os.getpid()]
    # 断りが止めるのは起動だけ。起動の試み (Popen) が無いことを見る
    assert launched == []


def test_断りのマーカーがある_root_の_SessionEnd_は停止経路を通るが何も止めない(
    tmp_path: Path, state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    repo = make_git_repo(tmp_path / "repo")
    (repo / hook.NO_SERVE_MARKER).touch()
    root = hook.resolve_root({"cwd": str(repo)})
    assert root is not None
    state.register(root, os.getpid())
    # 停止経路が実際に通ったことと、通った先が空振り (起動していないので serve.json が無い)
    # で終わることの両方を見る。stop_serve は本物へ委譲して結果だけ記録する
    real_stop = hook.stop_serve
    results: list[tuple[Path, bool]] = []

    def spy_stop(r: Path) -> bool:
        results.append((r, real_stop(r)))
        return results[-1][1]

    monkeypatch.setattr(hook, "stop_serve", spy_stop)
    sent: list[int] = []
    real_kill = os.kill

    def fake_kill(pid: int, sig: int) -> None:
        # 生存確認のプローブ (sig=0) は本物へ委譲し、SIGINT だけを記録する
        if sig == hook.signal.SIGINT:
            sent.append(pid)
            return
        real_kill(pid, sig)

    monkeypatch.setattr(hook.os, "kill", fake_kill)
    hook.handle_end({"cwd": str(repo)}, os.getpid())
    assert results == [(root, False)]
    assert sent == []
    assert not state.state_file(root).exists()


def _fake_ps_script(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> Path:
    """任意の本文を持つ偽 ps を置き、TGREP_PS_BIN を向ける。_fake_ps の一般形。"""
    script = tmp_path / "fake-ps"
    script.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    script.chmod(0o755)
    monkeypatch.setenv("TGREP_PS_BIN", str(script))
    return script


def _fake_ps_with_marker(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """呼ばれた痕跡をファイルに残してから tgrep を返す偽 ps。戻り値は痕跡のパス。"""
    marker = tmp_path / "ps-invoked"
    _fake_ps_script(tmp_path, monkeypatch, f"touch {shlex.quote(str(marker))}\necho tgrep")
    return marker


@pytest.mark.parametrize("pid", [-1, 0, True, "12"], ids=["negative", "zero", "bool", "str"])
def test_serve_pid_は正でない_pid_を外部確認の手前で落とす(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pid: object
) -> None:
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    (idx / "serve.json").write_text(json.dumps({"pid": pid, "port": 1}), encoding="utf-8")
    marker = _fake_ps_with_marker(tmp_path, monkeypatch)
    # is_alive を常に True に固定し、残る層を ps だけにする。本物の ps は -1 と 0 を拒む
    # (実測) ので「常に失敗する偽 ps」では guard の有無で戻り値が変わらず dead pin になる。
    # guard が ps より手前で止めていることを、ps が呼ばれた痕跡の不在で見る
    monkeypatch.setattr(state, "is_alive", lambda p: True)
    assert hook.serve_pid(tmp_path) is None
    assert not marker.exists()


def test_serve_pid_は正の_pid_なら外部確認まで進む(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 上の「痕跡が無い」の対照。同じ偽 ps が正の pid では呼ばれて痕跡を残す
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    (idx / "serve.json").write_text(json.dumps({"pid": os.getpid(), "port": 1}), encoding="utf-8")
    marker = _fake_ps_with_marker(tmp_path, monkeypatch)
    assert hook.serve_pid(tmp_path) == os.getpid()
    assert marker.exists()


def test_live_pids_は正でない_pid_を生存確認の手前で落とす(
    state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path("/tmp/repo-eight")
    path = state.state_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"root": str(root), "pids": [-1, 0, True, "7", os.getpid()]}) + "\n",
        encoding="utf-8",
    )
    probed: list[int] = []

    def fake_alive(pid: int) -> bool:
        probed.append(pid)
        return True

    monkeypatch.setattr(state, "is_alive", fake_alive)
    assert state.live_pids(root) == [os.getpid()]
    # kill -0 のプローブ自体が正の pid にしか届いていない
    assert probed == [os.getpid()]


def test_serve_pid_は_comm_が絶対パスでも_basename_で_tgrep_と認める(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    (idx / "serve.json").write_text(json.dumps({"pid": os.getpid(), "port": 1}), encoding="utf-8")
    # 絶対パスで起動したプロセスの comm はそのパスになる (実測: /bin/sleep で起動すると
    # /bin/sleep)。文字列比較のままだと TGREP_BIN を絶対パスにした環境の serve が hook から
    # 見えなくなり、止められないうえに start_serve が 2 本目を起こす
    _fake_ps_script(tmp_path, monkeypatch, "echo /usr/local/bin/tgrep")
    assert hook.serve_pid(tmp_path) == os.getpid()


@pytest.mark.parametrize(
    ("body", "expected"),
    [
        ("echo tgrep", "tgrep"),
        ("echo tgrep; exit 1", None),
        ("exit 0", None),
    ],
    ids=["ok", "nonzero-exit-with-output", "empty-stdout"],
)
def test_pid_command_name_は_ps_の失敗を_None_に潰す(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str, expected: str | None
) -> None:
    # 非 0 終了は stdout に名前があっても None (rc を見ていることの pin)。空の stdout も None
    hook = _load_hook()
    _fake_ps_script(tmp_path, monkeypatch, body)
    assert hook._pid_command_name(os.getpid()) == expected


def test_pid_command_name_は_ps_が無ければ_None(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    monkeypatch.setenv("TGREP_PS_BIN", str(tmp_path / "missing-ps"))
    assert hook._pid_command_name(os.getpid()) is None


def test_pid_command_name_は_ps_のタイムアウトを_None_に潰す(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    # exec で sh を sleep に置き換え、timeout 時の kill が sleep 自身へ届くようにする
    # (sh を殺しても子の sleep が残ると、テスト終了後まで孤児が生きる)
    _fake_ps_script(tmp_path, monkeypatch, "exec sleep 5")
    monkeypatch.setattr(hook, "PS_IDENTITY_TIMEOUT", 0.2)
    assert hook._pid_command_name(os.getpid()) is None


@pytest.mark.parametrize(
    ("exc", "expected"),
    [(ProcessLookupError, False), (PermissionError, True), (OSError, False)],
    ids=["not-found", "permission", "other-oserror"],
)
def test_is_alive_は_kill_の失敗の種類で生死を分ける(
    monkeypatch: pytest.MonkeyPatch, exc: type[OSError], expected: bool
) -> None:
    # 他ユーザーのプロセス (PermissionError) は「存在する」ので生存、それ以外の OSError は
    # 確認できないので死亡側へ倒す。os.kill は共有シングルトン (state が呼ぶ os.kill も
    # ここで差し替える os.kill も同じ) なので、番兵の pid にだけ例外を返し、他のプローブは
    # 本物へ委譲する
    sentinel = 2**22 - 2
    real_kill = os.kill

    def fake_kill(pid: int, sig: int) -> None:
        if pid == sentinel:
            raise exc
        real_kill(pid, sig)

    monkeypatch.setattr(os, "kill", fake_kill)
    assert state.is_alive(sentinel) is expected


def test_フックは_stdin_を読んで_exit_0_で終わる(tmp_path: Path, state_dir: Path) -> None:
    # 元は非 git の tmp_path を cwd にしていたため resolve_root が None を返し、
    # register にも start_serve にも到達しない dead setup だった
    # (state.register(root, pid) の行を消しても 22 件すべて緑のままだったことを実測で確認済み)。
    # git リポジトリにして handle_start の効果まで検証する
    repo = make_git_repo(tmp_path / "repo")
    env = dict(os.environ)
    env["TGREP_SERVE_STATE_DIR"] = str(state_dir)
    env["TGREP_BIN"] = "/usr/bin/false"
    pid = os.getpid()
    payload = json.dumps({"hook_event_name": "SessionStart", "cwd": str(repo)})
    result = subprocess.run(
        [sys.executable, str(HOOK), "start", str(pid)],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""
    # register の効果を状態ファイル越しに確認する (親プロセスとサブプロセスで
    # TGREP_SERVE_STATE_DIR を揃えているので同じ状態ファイルを見る)
    assert state.live_pids(repo.resolve()) == [pid]
