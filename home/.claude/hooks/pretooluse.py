"""PreToolUse フックの入力解釈と判定出力を共有する。

tirith-check.py と apm-install-guard.py が同じプロトコルを写経しており、片方だけ直したときに
沈黙した差 (ensure_ascii が 1 つだけ違う等) が実際に生まれていたため切り出した。

共有するのは純関数だけで、fail ポリシーは共有しない。tirith は環境変数の逃げ道を持つ
fail-closed、apm は無条件 deny で、同じ関数へ潰すと security guard の倒れ方が静かに変わる。
異常は problem 付きの例外で返し、各フックが自分のポリシーで捌く。

print と sys.exit も持たない。副作用を持ち込むと、この層だけを直接テストできなくなり、
2 つのフックを通した黒箱テストからしか仕様を読めなくなる。

フックからは sys.path[0] (スクリプトのディレクトリ) 経由で解決される。~/.claude/hooks は
リポジトリへのディレクトリ symlink だが、Python は sys.path[0] を実パスへ解決するため
symlink 経由で起動しても、cwd がどこであっても同じモジュールを指す (実測で確認)。
"""

from __future__ import annotations

import enum
import json
from typing import Any, Literal

# 判定 JSON が名乗るイベント名。このモジュールは PreToolUse 専用で、他イベントの
# フック (SessionStart 等) は判定 JSON の形自体が違うので相乗りさせない。
_HOOK_EVENT_NAME = "PreToolUse"

# 介在する対象のツール。これ以外は判定を出さずに通す。
_GUARDED_TOOL = "Bash"

# この層は deny しか出さない。allow は permission プロンプトを飛ばすため、検査が「通した」
# ことが他の検査の省略に化ける。文脈だけを載せたいときは notice_payload を使う。
# 型で閉じているのは、規律をコメントに置くと引数 1 つで復活してしまうため。
Decision = Literal["deny"]


class InputProblem(enum.Enum):
    """フック入力を解釈できなかった理由。

    フックごとに倒し方 (fail-closed か無条件 deny か) もメッセージの言語も違うため、
    理由を 1 つへ潰さず区別できる形で返す。
    """

    EMPTY = "empty"
    MALFORMED_JSON = "malformed_json"
    NOT_OBJECT = "not_object"
    TOOL_INPUT_NOT_OBJECT = "tool_input_not_object"
    NO_COMMAND = "no_command"


class HookInputError(Exception):
    """フック入力を解釈できなかった。呼び出し側が problem を見て倒し方を決める。"""

    def __init__(self, problem: InputProblem) -> None:
        super().__init__(problem.value)
        self.problem = problem


def get(data: dict[str, Any], *keys: str) -> Any:
    """snake_case と camelCase の両方でフィールドを引く。先に渡したキーが優先される。"""
    for key in keys:
        if key in data:
            return data[key]
    return None


def parse_payload(raw: str) -> dict[str, Any]:
    """stdin から読んだ hook 入力を dict にする。

    stdin の読み取り自体はここで行わない。読み取り失敗 (OSError) をどう倒すかはフックごとに
    違ううえ、純関数に保つとこの層のテストが subprocess を経由せずに済む。
    """
    if not raw.strip():
        raise HookInputError(InputProblem.EMPTY)
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HookInputError(InputProblem.MALFORMED_JSON) from exc
    if not isinstance(payload, dict):
        raise HookInputError(InputProblem.NOT_OBJECT)
    return payload


def bash_command(payload: dict[str, Any]) -> str | None:
    """PreToolUse かつ Bash なら実行される command を返す。介在対象外なら None。

    tool_input の欠落だけを既定値へ倒す。falsy な非 object ([] や "" や 0) まで既定値へ
    化かすと「型が違う」が「コマンドが無い」として報告され、理由が実態とずれる。
    """
    event = get(payload, "hook_event_name", "hookEventName")
    tool = get(payload, "tool_name", "toolName")
    if event != _HOOK_EVENT_NAME or tool != _GUARDED_TOOL:
        return None

    tool_input = get(payload, "tool_input", "toolInput")
    if tool_input is None:
        tool_input = {}
    if not isinstance(tool_input, dict):
        raise HookInputError(InputProblem.TOOL_INPUT_NOT_OBJECT)

    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        raise HookInputError(InputProblem.NO_COMMAND)
    return command


def notice_payload(context: str) -> str:
    """判定を出さずに文脈だけを載せる JSON を組み立てる。

    permissionDecision を持たないので、通常の権限フローがそのまま続く。allow を明示すると
    permission プロンプトを飛ばしてしまい、「検査が何か言った」ことが「検査を省く」に化ける。

    この形を harness が受理し additionalContext が実際に届くことは live で確認済み
    (判定を持たない hookSpecificOutput を返して、セッションへ文脈が入ることを見た)。
    """
    return json.dumps(
        {"hookSpecificOutput": {"hookEventName": _HOOK_EVENT_NAME, "additionalContext": context}},
        ensure_ascii=False,
    )


def decision_payload(decision: Decision, reason: str) -> str:
    """権限判定の JSON 文字列を組み立てる。stdout へ出すのは呼び出し側の役目。

    ensure_ascii=False は判定理由をログでそのまま読むため。JSON としての意味は変わらない
    (受け取り側はどちらでも同じ文字列を得る)。
    """
    output: dict[str, str] = {
        "hookEventName": _HOOK_EVENT_NAME,
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }
    return json.dumps({"hookSpecificOutput": output}, ensure_ascii=False)
