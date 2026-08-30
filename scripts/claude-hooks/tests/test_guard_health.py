"""guard-health フックの仕様。

判定のロジックはフックを in-process にロードして検査する。フックはファイル名に
ハイフンを含み通常の import では解決できないので、既存のフックテストと同じく
importlib で読む。

起動形そのもの (subprocess として走り、exit 0 で、出力が空か妥当な JSON) は
最後に 1 件だけ subprocess で見る。この主張は実環境の健全性に依存しない。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from types import ModuleType

import guard_probes
import pytest
from conftest import HOOKS_DIR

HOOK = HOOKS_DIR / "guard-health.py"

SESSION_INPUT = json.dumps(
    {"hook_event_name": "SessionStart", "source": "startup", "session_id": "test"}
)


def _load_hook() -> ModuleType:
    """ハイフンを含むファイル名のフックをモジュールとして読む。"""
    spec = importlib.util.spec_from_file_location("guard_health", HOOK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ok() -> guard_probes.ProbeResult:
    return guard_probes.ProbeResult(True)


def _silent(detail: str) -> guard_probes.ProbeResult:
    return guard_probes.ProbeResult(False, detail)


def test_全て健全なら沈黙は_0_件(monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_hook()
    monkeypatch.setattr(guard_probes, "PROBES", (("apm", _ok), ("tirith", _ok)))
    assert hook.collect() == []


def test_沈黙しているものだけを名前つきで返す(monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_hook()
    monkeypatch.setattr(
        guard_probes,
        "PROBES",
        (("apm", lambda: _silent("shim が横取りしていない")), ("tirith", _ok)),
    )
    silent = hook.collect()
    assert [name for name, _ in silent] == ["apm"]
    assert silent[0][1].detail == "shim が横取りしていない"


def test_プローブが落ちても他は走り落ちたことを報告する(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """検査できなかったことを健全へ潰さない。名前は登録簿が持つので落ちても分かる。"""
    hook = _load_hook()

    def boom() -> guard_probes.ProbeResult:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        guard_probes,
        "PROBES",
        (("apm", boom), ("tirith", lambda: _silent("tirith が沈黙している"))),
    )
    silent = hook.collect()
    assert [name for name, _ in silent] == ["apm", "tirith"]
    assert "boom" in silent[0][1].detail


def test_文面は名前と件数と_detail_を持つ() -> None:
    hook = _load_hook()
    message = hook.format_message(
        [("apm", _silent("shim が横取りしていない")), ("tirith", _silent("解決しない"))]
    )
    assert "2 件" in message
    assert "[apm]" in message
    assert "[tirith]" in message
    assert "shim が横取りしていない" in message


def test_沈黙を両方の経路へ載せる(capsys: pytest.CaptureFixture[str]) -> None:
    """systemMessage はユーザーの UI へ、additionalContext はモデルの文脈へ届く。

    片方だけでは届かない相手が出る。両方に同じ文面を載せることを pin する。
    """
    hook = _load_hook()
    hook.emit("テスト文面")
    payload = json.loads(capsys.readouterr().out)
    assert payload["systemMessage"] == "テスト文面"
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert payload["hookSpecificOutput"]["additionalContext"] == "テスト文面"


def test_全て健全なら_main_は何も出さない(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """『健全なときは何も出さない』(guard-health.py の docstring) を main() 経由で pin する。

    collect / format_message / emit を個別に見るだけでは、main() 内の
    `if not silent: return 0` 分岐そのものは検査を経由しない。ここでは main() を
    直接呼び、健全なら emit が一度も呼ばれず出力が空であることを見る。
    """
    hook = _load_hook()
    monkeypatch.setattr(guard_probes, "PROBES", (("apm", _ok), ("tirith", _ok)))
    assert hook.main() == 0
    assert capsys.readouterr().out == ""


def test_沈黙があれば_main_は文面を出す(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """健全なら何も出さない分岐の対照。沈黙があるときは main() が実際に出力することを見る。"""
    hook = _load_hook()
    monkeypatch.setattr(
        guard_probes,
        "PROBES",
        (("apm", lambda: _silent("shim が横取りしていない")), ("tirith", _ok)),
    )
    assert hook.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert "[apm]" in payload["systemMessage"]
    assert "shim が横取りしていない" in payload["systemMessage"]
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert payload["hookSpecificOutput"]["additionalContext"] == payload["systemMessage"]


def test_起動形が壊れていない() -> None:
    """実際の起動形で走り、exit 0 で、出力が空か妥当な JSON であること。

    実環境のガードが健全かどうかには依存しない主張にしてある。健全性まで見ると、
    テストの意味が実行環境で変わる。
    """
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=SESSION_INPUT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    if proc.stdout.strip():
        payload = json.loads(proc.stdout)
        assert "systemMessage" in payload
        assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
