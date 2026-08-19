"""pretooluse (PreToolUse フックの共有プロトコル層) の仕様。

このモジュールは純関数だけを持つ。どの異常でどう倒すか (fail-closed / 無条件 deny / 逃げ道の
有無) はフックごとに違うため共有せず、異常は problem 付きの例外で返して呼び出し側が捌く。
ここではその境界と、判定 JSON の exact な形を pin する。

フック本体を通した経路は test_tirith_hook.py / test_apm_install_guard.py が黒箱で見る。
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from pretooluse import (
    HookInputError,
    InputProblem,
    bash_command,
    decision_payload,
    get,
    parse_payload,
)


def _payload(**overrides: Any) -> dict[str, Any]:
    """PreToolUse/Bash の最小構成。上書きしたいフィールドだけ渡す。"""
    base: dict[str, Any] = {
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "ls -la"},
    }
    base.update(overrides)
    return base


# --- get: snake_case と camelCase の橋渡し ---------------------------------


def test_get_は引数の順で最初に見つかったキーを返す() -> None:
    assert get({"b": 2, "a": 1}, "a", "b") == 1
    assert get({"b": 2}, "a", "b") == 2


def test_get_はどのキーも無ければ_None_を返す() -> None:
    assert get({"x": 1}, "a", "b") is None


def test_get_は値が_None_のキーでもそこで打ち切る() -> None:
    # 「キーが無い」と「値が None」を区別しない。両方を後段の型検査が同じ扱いにするため。
    assert get({"a": None, "b": 2}, "a", "b") is None


# --- parse_payload: stdin の JSON を dict にする ---------------------------


@pytest.mark.parametrize("raw", ["", "   ", "\n\t "])
def test_空の入力は_EMPTY_で拒否する(raw: str) -> None:
    with pytest.raises(HookInputError) as excinfo:
        parse_payload(raw)
    assert excinfo.value.problem is InputProblem.EMPTY


def test_JSON_として壊れた入力は_MALFORMED_JSON_で拒否する() -> None:
    with pytest.raises(HookInputError) as excinfo:
        parse_payload("{not json")
    assert excinfo.value.problem is InputProblem.MALFORMED_JSON


@pytest.mark.parametrize("raw", ["[]", '["a"]', '"text"', "null", "42", "true"])
def test_object_でない_JSON_は_NOT_OBJECT_で拒否する(raw: str) -> None:
    with pytest.raises(HookInputError) as excinfo:
        parse_payload(raw)
    assert excinfo.value.problem is InputProblem.NOT_OBJECT


def test_object_の入力はそのまま_dict_で返る() -> None:
    assert parse_payload('{"a": 1, "b": [2]}') == {"a": 1, "b": [2]}


# --- bash_command: 介在対象の判定と command の取り出し ---------------------


def test_PreToolUse_かつ_Bash_なら_command_を返す() -> None:
    assert bash_command(_payload()) == "ls -la"


def test_camelCase_のフィールド名でも同じ_command_を返す() -> None:
    payload = {
        "hookEventName": "PreToolUse",
        "toolName": "Bash",
        "toolInput": {"command": "ls -la"},
    }
    assert bash_command(payload) == "ls -la"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("hook_event_name", "PostToolUse"),
        ("hook_event_name", "SessionStart"),
        ("tool_name", "Read"),
        ("tool_name", "Edit"),
    ],
)
def test_PreToolUse_と_Bash_が揃わなければ介在しない(field: str, value: str) -> None:
    assert bash_command(_payload(**{field: value})) is None


def test_イベントもツールも欠けていれば介在しない() -> None:
    assert bash_command({"tool_input": {"command": "ls"}}) is None


def test_介在しない判定は_tool_input_の型より先に効く() -> None:
    # 対象外のツールに壊れた tool_input が付いていても、こちらの守備範囲ではない。
    assert bash_command(_payload(tool_name="Read", tool_input=["broken"])) is None


@pytest.mark.parametrize("tool_input", [[], ["x"], "text", 42, 0, ""])
def test_tool_input_が_object_でなければ_TOOL_INPUT_NOT_OBJECT(tool_input: Any) -> None:
    # falsy な非 object ([] や "" や 0) も型の誤りとして扱う。既定値へ化かすと
    # 「型が違う」が「コマンドが無い」に化けて、報告される理由が実態とずれる。
    with pytest.raises(HookInputError) as excinfo:
        bash_command(_payload(tool_input=tool_input))
    assert excinfo.value.problem is InputProblem.TOOL_INPUT_NOT_OBJECT


def test_tool_input_の欠落は_NO_COMMAND_で拒否する() -> None:
    payload = {"hook_event_name": "PreToolUse", "tool_name": "Bash"}
    with pytest.raises(HookInputError) as excinfo:
        bash_command(payload)
    assert excinfo.value.problem is InputProblem.NO_COMMAND


@pytest.mark.parametrize("command", [None, 42, [], {}, "", "   ", "\n"])
def test_command_が文字列でないか空なら_NO_COMMAND_で拒否する(command: Any) -> None:
    with pytest.raises(HookInputError) as excinfo:
        bash_command(_payload(tool_input={"command": command}))
    assert excinfo.value.problem is InputProblem.NO_COMMAND


# --- decision_payload: 判定 JSON の形 --------------------------------------


def test_deny_の判定は_hookSpecificOutput_の形で返る() -> None:
    assert json.loads(decision_payload("deny", "理由")) == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": "理由",
        }
    }


def test_additional_context_を渡すと_allow_の判定に付く() -> None:
    assert json.loads(decision_payload("allow", "警告", additional_context="警告")) == {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "警告",
            "additionalContext": "警告",
        }
    }


def test_日本語の理由文はエスケープせず生のまま出す() -> None:
    # 判定はログでそのまま読む。JSON としての意味は ensure_ascii のどちらでも同じなので、
    # 読める側へ倒す。負の対照として \\u エスケープが現れないことも見る。
    text = decision_payload("deny", "危険なコマンドです")
    assert "危険なコマンドです" in text
    assert "\\u" not in text
