"""guard_probes の述語の仕様。

フック本体を subprocess 起動せず、共有層を直接 import して検査する。副作用 (print /
sys.exit) を持たない層なので、この形で仕様を読める。
"""

from __future__ import annotations

from pathlib import Path

import guard_probes
import guard_resolve
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

    result = guard_probes.probe_apm()

    assert guard_resolve.shim_resolves() is True
    assert result.healthy is True
    assert result.detail == ""


def _apm_elsewhere(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """shim ではない実体の apm だけが PATH に載っている状態を作る。

    沈黙の理由を「shim があるか」の 1 点だけに絞るための共通の土台。PATH 側を各テストで
    作り分けると、落ちたときにどちらの条件が効いたのか読めなくなる。
    """
    other = tmp_path / "bin" / "apm"
    other.parent.mkdir(parents=True)
    other.write_text("#!/bin/sh\n", encoding="utf-8")
    other.chmod(0o755)
    monkeypatch.setenv("PATH", str(other.parent))


def test_shim_は配置済みで_PATH_に載っていなければ起動元のシェルを告げる(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """今日 (2026-08-31) 実際に起きた状態。bootstrap.sh を勧めてはならない。

    shim は配置されているのに Claude Code の PATH へ載っていない。原因は起動元のシェルが
    古いことで、bootstrap.sh は何も直さない。実際にこの状態で bootstrap.sh と Claude Code
    の再起動を勧める文面に従い、1 往復を空振りさせた。
    """
    shim = tmp_path / "libexec" / "apm"
    shim.parent.mkdir(parents=True)
    shim.write_text("#!/bin/sh\n", encoding="utf-8")
    _apm_elsewhere(tmp_path, monkeypatch)
    monkeypatch.setenv("APM_INSTALL_GUARD_SHIM", str(shim))

    assert guard_resolve.shim_exists() is True
    assert guard_resolve.shim_resolves() is False
    result = guard_probes.probe_apm()
    assert result.healthy is False
    assert guard_probes.APM_REMEDY_STALE_SHELL in result.detail
    assert guard_probes.APM_REMEDY_MISSING_SHIM not in result.detail


def test_shim_が未配置なら配置からやり直すよう告げる(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """shim の実体が無い状態。ここでだけ bootstrap.sh が手当てになる。"""
    _apm_elsewhere(tmp_path, monkeypatch)
    monkeypatch.setenv("APM_INSTALL_GUARD_SHIM", str(tmp_path / "nonexistent" / "apm"))

    assert guard_resolve.shim_exists() is False
    result = guard_probes.probe_apm()
    assert result.healthy is False
    assert guard_probes.APM_REMEDY_MISSING_SHIM in result.detail
    assert guard_probes.APM_REMEDY_STALE_SHELL not in result.detail


def test_辿れない_symlink_の_shim_は未配置として扱う(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """symlink はあるが実体が無い状態。shim は symlink として配置されるので実際に起きうる。

    リポジトリを移動したあとや bootstrap.sh を通す前がこれにあたる。symlink の存在だけを
    見ると配置済みと読めてしまい、起動元のシェルを疑わせる誤った手当てへ倒れる。
    """
    shim = tmp_path / "libexec" / "apm"
    shim.parent.mkdir(parents=True)
    shim.symlink_to(tmp_path / "nonexistent" / "apm")
    _apm_elsewhere(tmp_path, monkeypatch)
    monkeypatch.setenv("APM_INSTALL_GUARD_SHIM", str(shim))

    assert shim.is_symlink()
    assert guard_resolve.shim_exists() is False
    assert guard_probes.APM_REMEDY_MISSING_SHIM in guard_probes.probe_apm().detail


def test_PATH_に_apm_が無ければ沈黙(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.setenv("APM_INSTALL_GUARD_SHIM", str(tmp_path / "nonexistent" / "apm"))

    assert guard_resolve.shim_resolves() is False
    assert guard_probes.probe_apm().healthy is False


def test_shim_の置き場が配布先と一致する() -> None:
    """bootstrap.sh の SYMLINK_PAIRS を bash 自身に解釈させて読み、定数と突き合わせる。

    どちらか片方を直しても、もう片方が古いまま実配置と食い違う。bash に解釈させる読み方は
    conftest.bash_symlink_pairs に 1 つだけ置いてあり、ここではそれを呼ぶだけで
    インライン実装を持たない。
    """
    pairs = bash_symlink_pairs()
    assert pairs, "SYMLINK_PAIRS を 1 件も読めていない"

    expected = guard_resolve.DEFAULT_SHIM_PATH.removeprefix("~/")
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
    # 復旧手順を pin する。apm 側は "bootstrap" を pin していたが tirith 側は無く、
    # 実体化経路が mise から brew へ移ったとき案内だけが古びて誰も赤くならなかった。
    assert "brew install tirith" in result.detail
    # この分岐は「入っていない」と「入っているが PATH に載っていない」の両方で通る。
    # この層は区別できないので、片方だけを勧めてはならない。2026-08-31 に PATH から
    # /opt/homebrew/bin を外して実測したところ、tirith は brew で入っているのに
    # brew install tirith だけを勧めた。apm 側で同じ形が空振りを生んでいる。
    assert "PATH に載っていない" in result.detail


def test_TIRITH_BIN_のパスが無ければ全_Bash_が止まると告げる(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("TIRITH_BIN", str(tmp_path / "nonexistent" / "tirith"))

    result = guard_probes.probe_tirith()
    assert result.healthy is False
    # "Bash" だけでは駄目: tmp_path 名がこの関数名から作られ "_Bash0" で終わるため、
    # フォールバック分岐の文面 (tirith_bin をそのまま埋め込む) にも偶然 "Bash" が含まれる。
    assert "TIRITH_BIN=" in result.detail


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
