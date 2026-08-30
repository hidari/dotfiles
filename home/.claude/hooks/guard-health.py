#!/usr/bin/env python3
"""SessionStart で検査層の生存を測り、沈黙していれば 1 通で告げる。

SessionStart はセッションを止められない (exit 2 でも続行し stderr が出るだけ) ので、
この層は告げるだけである。強制は PreToolUse 側の責務のまま変わらない。

告げ先を 2 つ持つのは、届く相手が違うためである。systemMessage はトップレベルの
フィールドでユーザーの UI へ出る。additionalContext は hookSpecificOutput の中で
モデルの文脈へ入る。両方へ同じ文面を載せて、ユーザーとモデルの双方が同じものを見る。

健全なときは何も出さない。毎セッションの出力はノイズになるためである。この選択で
「健全」と「この検査自体が走らなかった」は実行時には区別できなくなるが、その区別は
配線を静的に pin する層 (config-guard) が持つ。実行時は黙り、配線は叫ぶ。

matcher は settings.json 側で全開始理由を覆う。compact でも発火するので、長時間走る
セッションでは再告知が自動的に起きる。再告知の機構をここへ書かずに済む。
"""

from __future__ import annotations

import contextlib
import json
import sys

import guard_probes

_HOOK_EVENT_NAME = "SessionStart"


def collect() -> list[tuple[str, guard_probes.ProbeResult]]:
    """登録簿を回して、沈黙しているものだけを名前つきで返す。

    1 件が例外を投げても他は走らせる。落ちたプローブは沈黙として報告する。検査できな
    かったことを健全へ潰すと、この層自身が沈黙する側へ回る。
    """
    silent: list[tuple[str, guard_probes.ProbeResult]] = []
    for name, probe in guard_probes.PROBES:
        try:
            result = probe()
        except Exception as exc:  # プローブの失敗はすべて沈黙として扱う
            silent.append((name, guard_probes.ProbeResult(False, f"プローブ自身が失敗した: {exc}")))
            continue
        if not result.healthy:
            silent.append((name, result))
    return silent


def format_message(silent: list[tuple[str, guard_probes.ProbeResult]]) -> str:
    """沈黙しているプローブを 1 通の文面にまとめる。"""
    head = f"検査層の健全性: {len(silent)} 件が沈黙している"
    body = "\n".join(f"[{name}] {result.detail}" for name, result in silent)
    return f"{head}\n\n{body}"


def emit(message: str) -> None:
    """ユーザーの UI とモデルの文脈の両方へ同じ文面を載せる。

    systemMessage だけだとモデルが知らないまま作業を続け、additionalContext だけだと
    ユーザーの端末が静かなままになる。直せるのはユーザーだけなので両方へ載せる。
    """
    print(
        json.dumps(
            {
                "systemMessage": message,
                "hookSpecificOutput": {
                    "hookEventName": _HOOK_EVENT_NAME,
                    "additionalContext": message,
                },
            },
            ensure_ascii=False,
        )
    )


def main() -> int:
    # 入力は使わないが読む。読まないと書き手が EPIPE を受けうる。
    with contextlib.suppress(OSError):
        sys.stdin.read()

    silent = collect()
    if not silent:
        return 0
    emit(format_message(silent))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # この層が落ちたこと自体を告げる。stderr だとモデルの文脈へ入らない
        emit(f"検査層の健全性チェック自体が失敗した: {exc}")
        sys.exit(0)
