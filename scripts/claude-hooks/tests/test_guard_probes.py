"""guard_probes の述語の仕様。

フック本体を subprocess 起動せず、共有層を直接 import して検査する。副作用 (print /
sys.exit) を持たない層なので、この形で仕様を読める。
"""

from __future__ import annotations

from pathlib import Path

import guard_probes
import pytest
from conftest import bash_symlink_pairs


def test_shim_へ解決すれば健全(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shim = tmp_path / "libexec" / "apm"
    shim.parent.mkdir(parents=True)
    shim.write_text("#!/bin/sh\n", encoding="utf-8")
    shim.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "apm").symlink_to(shim)

    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("APM_INSTALL_GUARD_SHIM", str(shim))

    assert guard_probes.shim_resolves() is True
    assert guard_probes.probe_apm().healthy is True


def test_別の実体へ解決すれば沈黙(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shim = tmp_path / "libexec" / "apm"
    shim.parent.mkdir(parents=True)
    shim.write_text("#!/bin/sh\n", encoding="utf-8")
    other = tmp_path / "bin" / "apm"
    other.parent.mkdir(parents=True)
    other.write_text("#!/bin/sh\n", encoding="utf-8")
    other.chmod(0o755)

    monkeypatch.setenv("PATH", str(other.parent))
    monkeypatch.setenv("APM_INSTALL_GUARD_SHIM", str(shim))

    assert guard_probes.shim_resolves() is False
    result = guard_probes.probe_apm()
    assert result.healthy is False
    assert "bootstrap" in result.detail


def test_PATH_に_apm_が無ければ沈黙(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.setenv("APM_INSTALL_GUARD_SHIM", str(tmp_path / "nonexistent" / "apm"))

    assert guard_probes.shim_resolves() is False
    assert guard_probes.probe_apm().healthy is False


def test_shim_の置き場が配布先と一致する() -> None:
    """bootstrap.sh の SYMLINK_PAIRS を bash 自身に解釈させて読み、定数と突き合わせる。

    どちらか片方を直しても、もう片方が古いまま実配置と食い違う。bash に解釈させる読み方は
    conftest.bash_symlink_pairs に 1 つだけ置いてあり、ここではそれを呼ぶだけで
    インライン実装を持たない。
    """
    pairs = bash_symlink_pairs()
    assert pairs, "SYMLINK_PAIRS を 1 件も読めていない"

    expected = guard_probes.DEFAULT_SHIM_PATH.removeprefix("~/")
    targets = [line.split("|", 1)[1] for line in pairs if "|" in line]
    assert expected in targets


def _fake_tirith(path: Path, exit_code: int) -> Path:
    """指定の exit code を返す偽 tirith を作る。"""
    path.write_text(f"#!/bin/sh\nexit {exit_code}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_tirith_が_clean_へ応答すれば健全(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_tirith(tmp_path / "tirith", 0)
    monkeypatch.setenv("TIRITH_BIN", str(fake))
    assert guard_probes.probe_tirith().healthy is True


def test_TIRITH_BIN_未設定で解決しなければ沈黙(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.delenv("TIRITH_BIN", raising=False)
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.setenv("HOME", str(tmp_path))

    result = guard_probes.probe_tirith()
    assert result.healthy is False
    assert "沈黙" in result.detail


def test_TIRITH_BIN_のパスが無ければ全_Bash_が止まると告げる(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TIRITH_BIN", str(tmp_path / "nonexistent" / "tirith"))

    result = guard_probes.probe_tirith()
    assert result.healthy is False
    assert "Bash" in result.detail


def test_clean_なコマンドに_clean_を返さなければ沈黙(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """応答はするが clean を clean と判定しない状態。フックは fail-closed に倒れる。"""
    fake = _fake_tirith(tmp_path / "tirith", 1)
    monkeypatch.setenv("TIRITH_BIN", str(fake))

    result = guard_probes.probe_tirith()
    assert result.healthy is False


def test_登録簿は名前と関数の組を持つ() -> None:
    """呼び出し自体が例外で落ちたときにも名前が要るので、名前は結果ではなく登録簿が持つ。"""
    names = [name for name, _ in guard_probes.PROBES]
    assert names == ["apm", "tirith"]
    for _, probe in guard_probes.PROBES:
        assert callable(probe)
