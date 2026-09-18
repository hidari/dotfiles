"""tgrep serve の寿命をセッションへ合わせる hook の仕様。

判定ロジックは in-process で呼び、起動形だけ最後に 1 件 subprocess で見る
(test_guard_health.py と同じ形)。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import tgrep_serve_state as state


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
