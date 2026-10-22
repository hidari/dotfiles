"""guard_probes.probe_node_security の仕様。

状態ファイルの書き手は scripts/node-security-notifier で、別の uv プロジェクトにある。
ここでは書き手の state.py をパスで直接読み込み、本物の書き手が作ったファイルをプローブに
読ませる。手で書いた fixture を使うと、書き手の形が変わってもここが緑のまま残る。

HOME を差し替えて状態を作る。プローブは HOME 配下の mise の設定と状態ファイルだけを読む。
"""

from __future__ import annotations

import json
import plistlib
import subprocess
import sys
import time
from pathlib import Path
from types import ModuleType

import guard_probes
import pytest
from conftest import HOOKS_DIR, REPO_ROOT, load_module

NOW = 1_761_100_000
DAY = 86_400
# 実データ (2026-10-22 の nodejs.org/dist/index.json) の security: true から抜き出した版
SECURITY_VERSIONS = ["26.12.1", "25.8.2", "24.22.1", "24.18.1", "22.22.0"]


def _writer() -> ModuleType:
    return load_module(
        REPO_ROOT / "scripts/node-security-notifier/src/node_security_notifier/state.py"
    )


def _home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


def _pin(home: Path, body: str) -> None:
    config = home / ".config" / "mise" / "config.toml"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(body, encoding="utf-8")


def _status(home: Path, *, fetched_at: int = NOW, versions: list[str] | None = None) -> Path:
    writer = _writer()
    path: Path = home / writer.STATE_RELPATH
    writer.save_status(
        path,
        fetched_at=fetched_at,
        security_versions=SECURITY_VERSIONS if versions is None else versions,
    )
    return path


def test_状態ファイルの置き場は書き手と一致する() -> None:
    assert _writer().STATE_RELPATH == guard_probes.NODE_SECURITY_STATE_RELPATH


def test_告げるラベルとログの置き場は_plist_と一致する() -> None:
    notifier = REPO_ROOT / "scripts/node-security-notifier"
    with (notifier / "com.hidari.node-security-notifier.plist").open("rb") as f:
        plist = plistlib.load(f)

    assert plist["Label"] == guard_probes._NODE_SECURITY_LABEL
    assert plist["StandardErrorPath"].replace("__HOME__", "~") == guard_probes._NODE_SECURITY_LOG


def test_pin_が最新の_security_版なら健全(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = _home(tmp_path, monkeypatch)
    _pin(home, '[tools]\nnode = "24.22.1"\n')
    _status(home)

    result = guard_probes.probe_node_security(now=NOW)

    assert result.healthy is True
    assert result.detail == ""


def test_pin_より新しい同じメジャーの_security_版を列挙する(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """2026-07-28 から 10-22 まで実際に続いていた状態。他のメジャーの版は挙げない。"""
    home = _home(tmp_path, monkeypatch)
    _pin(home, '[tools]\nnode = "24.18.0"\n')
    _status(home)

    result = guard_probes.probe_node_security(now=NOW)

    assert result.healthy is False
    assert "24.18.0" in result.detail
    assert "24.18.1, 24.22.1" in result.detail
    for other in ("26.12.1", "25.8.2", "22.22.0"):
        assert other not in result.detail


def test_版は数として比べる(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """文字列で比べると 24.9.0 は 24.22.1 より新しく見え、遅れを見落とす。"""
    home = _home(tmp_path, monkeypatch)
    _pin(home, '[tools]\nnode = "24.9.0"\n')
    _status(home)

    result = guard_probes.probe_node_security(now=NOW)

    assert result.healthy is False
    assert "24.18.1, 24.22.1" in result.detail


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(None, id="config-missing"),
        pytest.param("[tools\n", id="config-not-toml"),
        pytest.param('[tools]\npython = "3.12.0"\n', id="node-absent"),
        pytest.param('[tools]\nnode = "24"\n', id="pin-not-exact"),
        pytest.param('[tools]\nnode = "lts"\n', id="pin-alias"),
        pytest.param("[tools]\nnode = 24\n", id="pin-not-str"),
    ],
)
def test_pin_が読めなければ沈黙(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str | None
) -> None:
    home = _home(tmp_path, monkeypatch)
    if body is not None:
        _pin(home, body)
    _status(home)

    result = guard_probes.probe_node_security(now=NOW)

    assert result.healthy is False
    assert "pin を読めない" in result.detail


def test_状態ファイルが無ければ一度も判定していないと告げる(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _home(tmp_path, monkeypatch)
    _pin(home, '[tools]\nnode = "24.22.1"\n')

    result = guard_probes.probe_node_security(now=NOW)

    assert result.healthy is False
    assert "一度も判定していない" in result.detail
    assert "com.hidari.node-security-notifier" in result.detail


@pytest.mark.parametrize(
    "content",
    [
        pytest.param("not json", id="not-json"),
        pytest.param("[]", id="not-object"),
        pytest.param('{"security_versions": ["24.22.1"]}', id="fetched-at-missing"),
        pytest.param('{"fetched_at": "1", "security_versions": ["24.22.1"]}', id="fetched-at-str"),
        pytest.param(
            '{"fetched_at": true, "security_versions": ["24.22.1"]}', id="fetched-at-bool"
        ),
        pytest.param('{"fetched_at": 1}', id="versions-missing"),
        pytest.param('{"fetched_at": 1, "security_versions": ["v24.22.1"]}', id="version-with-v"),
        pytest.param('{"fetched_at": 1, "security_versions": "24.22.1"}', id="versions-not-list"),
    ],
)
def test_状態ファイルの形が崩れていれば沈黙(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, content: str
) -> None:
    home = _home(tmp_path, monkeypatch)
    _pin(home, '[tools]\nnode = "24.22.1"\n')
    path = _status(home)
    path.write_text(content, encoding="utf-8")

    result = guard_probes.probe_node_security(now=NOW)

    assert result.healthy is False
    assert "形が崩れている" in result.detail


def test_取得から_3_日ちょうどなら健全(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = _home(tmp_path, monkeypatch)
    _pin(home, '[tools]\nnode = "24.22.1"\n')
    _status(home, fetched_at=NOW - 3 * DAY)

    assert guard_probes.probe_node_security(now=NOW).healthy is True


def test_取得から_3_日を超えたら判定が止まっていると告げる(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = _home(tmp_path, monkeypatch)
    _pin(home, '[tools]\nnode = "24.22.1"\n')
    _status(home, fetched_at=NOW - 3 * DAY - 1)

    result = guard_probes.probe_node_security(now=NOW)

    assert result.healthy is False
    assert "判定が止まっている" in result.detail
    assert "launchd.log" in result.detail


def test_古さと遅れは両方とも告げる(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    home = _home(tmp_path, monkeypatch)
    _pin(home, '[tools]\nnode = "24.18.0"\n')
    _status(home, fetched_at=NOW - 10 * DAY)

    result = guard_probes.probe_node_security(now=NOW)

    assert result.healthy is False
    assert "判定が止まっている" in result.detail
    assert "24.18.1, 24.22.1" in result.detail


def test_既定の時刻は実時間(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """now を渡さない本番の経路。既定引数はテストが毎回上書きすると pin されない。"""
    home = _home(tmp_path, monkeypatch)
    _pin(home, '[tools]\nnode = "24.22.1"\n')
    _status(home, fetched_at=int(time.time()) - 3 * DAY - 60)

    result = guard_probes.probe_node_security()

    assert result.healthy is False
    assert "判定が止まっている" in result.detail


def _run_guard_health(home: Path) -> str:
    proc = subprocess.run(
        [sys.executable, str(HOOKS_DIR / "guard-health.py")],
        input="{}",
        capture_output=True,
        text=True,
        env={"HOME": str(home), "PATH": "/usr/bin:/bin"},
        check=True,
        timeout=60,
    )
    return proc.stdout


def test_guard_health_を別プロセスで起動すると旧_pin_の遅れを告げる(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """実際の消費者 (SessionStart のフック) の側から見る。現在の pin では告げない。"""
    home = _home(tmp_path, monkeypatch)
    _status(home, fetched_at=int(time.time()))

    _pin(home, '[tools]\nnode = "24.18.0"\n')
    old = json.loads(_run_guard_health(home))
    assert "[node-security]" in old["systemMessage"]
    assert "24.18.1, 24.22.1" in old["hookSpecificOutput"]["additionalContext"]

    _pin(home, '[tools]\nnode = "24.22.1"\n')
    current = _run_guard_health(home)
    assert "[node-security]" not in current
