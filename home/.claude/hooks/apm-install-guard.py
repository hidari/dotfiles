#!/usr/bin/env python3
"""apm の破壊的サブコマンドを、ツリーが汚れているときだけ止める PreToolUse フック。

apm install は deploy 先を rsync --delete 相当で書き換え、git tracked かつ手書きのファイルも
黙って上書きし、パッケージに含まれないファイルを削除する。しかもログには (files unchanged) と
表示されるため差分に気づけない。

目的は破壊の防止ではなく復旧可能性の確保である。ツリーが clean なら apm が何を壊しても git から
戻せるが、汚れていれば未コミットの作業が復旧不能に消える。この整理から検査範囲は deploy 先では
なくリポジトリ全体になる。

対象は cwd が属する git リポジトリ。apm install の破壊性はどのリポジトリでも同じなので特定の
リポジトリに限定しない。git リポジトリの外では「git から戻す」前提そのものが無いので検査しない。
緊急時は APM_INSTALL_GUARD_DISABLE=1 で無効化できる。

deny のときだけ JSON を出し、それ以外は無出力の exit 0 とする。複数の PreToolUse フックが deny と
allow を同時に返したときの合成規則は公式ドキュメントに記載が無いため (「All matching hooks run in
parallel」までしか書かれていない)、allow を出さないことで既存フックの判定を打ち消す経路を
原理的に無くしている。

bootstrap.sh の install_apm_skills にも同じ判定がある。あちらは自動実行経路を、こちらは手打ちと
エージェント経由を塞ぐ。プロセスが別なので実装は共有できない。
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from typing import Any, NoReturn

# deploy 先を書き換える apm のコマンド。前方一致で判定するため tuple の tuple で持つ。
# 名前は apm --help の実際の一覧から採った。読み取り専用 (list / audit / outdated /
# deps list / deps tree 等) は対象外。
DESTRUCTIVE_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("install",),
    ("update",),
    ("prune",),
    ("deps", "clean"),
    ("deps", "update"),
)

# apm install の入出力なので、これらだけが変更された状態は正常な中間状態として許可する。
# 例外が無いと pin を更新するたびにガードが手順を止める。
ALLOWED_DIRTY_BASENAMES = frozenset({"apm.yml", "apm.lock.yaml"})

# 診断に並べるパスの上限。長大な一覧は読まれないので頭だけ出して残りは件数で示す。
MAX_LISTED_PATHS = 20


def get(data: dict[str, Any], *keys: str) -> Any:
    """snake_case と camelCase の両方でフィールドを引く。"""
    for key in keys:
        if key in data:
            return data[key]
    return None


def deny(reason: str) -> NoReturn:
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            }
        )
    )
    sys.exit(0)


def allow_silently() -> NoReturn:
    """判定を出さずに通す。stdout が空なので通常の権限フローがそのまま続く。"""
    sys.exit(0)


def destructive_command(command: str) -> str | None:
    """コマンド文字列から apm の破壊的コマンドを取り出す。無ければ None。

    正規表現ではなく shlex でトークン化する。クォートされた文字列は 1 トークンになるので
    `echo "apm install"` は誤検出しない。一方で裸の `apm install` は位置を問わず検出する。
    誤爆より bypass の方が危険 (ガードの主張が偽になる) なので保守的に倒している。
    クォートが不整合でトークン化できないものは判定しない。
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None

    for index, token in enumerate(tokens):
        if token.rsplit("/", 1)[-1] != "apm":
            continue
        # apm の後ろに続く非フラグ引数だけを取り出して前方一致を見る
        args = [arg for arg in tokens[index + 1 :] if not arg.startswith("-")]
        for candidate in DESTRUCTIVE_COMMANDS:
            if tuple(args[: len(candidate)]) == candidate:
                return " ".join(candidate)
    return None


def repo_root(cwd: str) -> str | None:
    """cwd が属する git リポジトリのルートを返す。リポジトリ外なら None。"""
    try:
        proc = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def dirty_paths(root: str) -> list[str]:
    """未コミットの変更のうち、apm の入出力でないものを列挙する。

    パスは NUL 区切りで受け取る。空白や日本語を含むパスを空白分割すると分断され、落ちた分は
    「エラー」ではなく「短い正常な結果」として返るため出力を見ても気づけない。git は既定で
    非 ASCII をクォート表記にするが -z ならそのまま返る。
    """
    proc = subprocess.run(
        ["git", "-C", root, "status", "--porcelain", "-z"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git status failed: {proc.stderr.strip()}")

    blockers: list[str] = []
    for entry in proc.stdout.split("\0"):
        if not entry:
            continue
        # porcelain の各エントリは "XY <path>" 形式。先頭 3 文字が状態フィールド
        path = entry[3:]
        if path.rsplit("/", 1)[-1] in ALLOWED_DIRTY_BASENAMES:
            continue
        blockers.append(path)
    return blockers


def main() -> None:
    if os.environ.get("APM_INSTALL_GUARD_DISABLE") == "1":
        allow_silently()

    raw = sys.stdin.read()
    if not raw.strip():
        deny("apm-install-guard: フックの入力が空でした")

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError):
        deny("apm-install-guard: フックの入力を JSON として解釈できませんでした")

    if not isinstance(data, dict):
        deny("apm-install-guard: フックの入力が object ではありません")

    event = get(data, "hook_event_name", "hookEventName")
    tool = get(data, "tool_name", "toolName")
    if event != "PreToolUse" or tool != "Bash":
        allow_silently()

    tool_input = get(data, "tool_input", "toolInput") or {}
    if not isinstance(tool_input, dict):
        deny("apm-install-guard: tool_input が object ではありません")

    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        deny("apm-install-guard: Bash コマンドを読み取れませんでした")

    subcommand = destructive_command(command)
    if subcommand is None:
        allow_silently()

    cwd = get(data, "cwd")
    if not isinstance(cwd, str) or not cwd:
        deny(f"apm-install-guard: cwd が取れないため apm {subcommand} を許可できません")

    root = repo_root(cwd)
    if root is None:
        allow_silently()

    try:
        blockers = dirty_paths(root)
    except (OSError, subprocess.SubprocessError, RuntimeError) as exc:
        deny(f"apm-install-guard: git status を実行できませんでした: {exc}")

    if not blockers:
        allow_silently()

    listed = "\n".join(f"  {path}" for path in blockers[:MAX_LISTED_PATHS])
    remainder = len(blockers) - MAX_LISTED_PATHS
    more = f"\n  ... 他 {remainder} 件" if remainder > 0 else ""
    deny(
        f"apm {subcommand} は deploy 先を上書きし、パッケージに含まれないファイルを削除します。"
        f"{root} に未コミットの変更が {len(blockers)} 件あるため中止しました。\n"
        f"{listed}{more}\n"
        "コミットまたは stash してから再実行してください。"
        "緊急時は APM_INSTALL_GUARD_DISABLE=1 で無効化できます。"
    )


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        deny(f"apm-install-guard: 予期しない例外: {exc}")
