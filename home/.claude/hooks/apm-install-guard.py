#!/usr/bin/env python3
"""apm の書き込みを伴うサブコマンドを、ツリーが汚れているときだけ止める PreToolUse フック。

apm install は deploy 先を rsync --delete 相当で書き換え、git tracked かつ手書きのファイルも
黙って上書きし、パッケージに含まれないファイルを削除する。しかもログには (files unchanged) と
表示されるため差分に気づけない。

目的は破壊の防止ではなく復旧可能性の確保である。ツリーが clean なら apm が何を壊しても git から
戻せるが、汚れていれば未コミットの作業が復旧不能に消える。この整理から検査範囲は deploy 先では
なくリポジトリ全体になる。

判定は「止めるものを並べる」denylist ではなく「通すものを並べる」allowlist に置く。apm は
pre-1.0 でサブコマンドが 34 個あり今後も増えるため、denylist は上流が増えるたびに黙って穴が
開く。しかも false negative は「何も起きない」形で返るので、ガードの主張が偽になったことに
気づけない。false positive は「コミットするか stash する」という可視で安価な失敗で済む。

検査対象は session cwd が属する git リポジトリと、コマンド中の cd で移動できると分かった先。
apm の破壊性はどのリポジトリでも同じなので特定のリポジトリに限定しない。git リポジトリの外では
「git から戻す」前提そのものが無いので検査しない。

緊急時は APM_INSTALL_GUARD_DISABLE=1 で無効化できるが、これはフックのプロセス環境を見る。
フックは Claude Code が起動するため、Bash コマンドへ前置しても届かない (実測で確認)。
settings.json の env に置くか Claude Code の起動環境に入れること。ターミナルから直接 apm を
叩く場合はそもそもフックを通らない。

deny のときだけ JSON を出し、それ以外は無出力の exit 0 とする。複数の PreToolUse フックが deny と
allow を同時に返したときの合成規則は公式ドキュメントに記載が無いため (「All matching hooks run in
parallel」までしか書かれていない)、allow を出さないことで既存フックの判定を打ち消す経路を
原理的に無くしている。

bootstrap.sh の install_apm_skills にも同じ判定がある。あちらは自動実行経路を、こちらは手打ちと
エージェント経由を塞ぐ。プロセスが別なので実装は共有できない。両者の判定が一致していることは
scripts/tests/bootstrap.bats の cross-pin テストが見る。
"""

from __future__ import annotations

import json
import os
import re
import shlex
import sys
from typing import TYPE_CHECKING, Any, NoReturn

if TYPE_CHECKING:
    import subprocess

# 読み取り専用と確認できた apm のサブコマンド。ここに無いものは書き込みうるものとして扱う。
# 名前と性質は apm --help および各 --help (0.27.0) の実際の出力から採った。
READONLY_COMMANDS: tuple[tuple[str, ...], ...] = (
    ("audit",),
    ("doctor",),
    ("find",),
    ("list",),
    ("outdated",),
    ("policy",),
    ("preview",),
    ("search",),
    ("targets",),
    ("view",),
    ("deps", "list"),
    ("deps", "tree"),
)

# apm install の入出力なので、これらだけが変更された状態は正常な中間状態として許可する。
# 例外が無いと pin を更新するたびにガードが手順を止める。
ALLOWED_DIRTY_BASENAMES = frozenset({"apm.yml", "apm.lock.yaml"})

# 診断に並べるパスの上限。長大な一覧は読まれないので頭だけ出して残りは件数で示す。
MAX_LISTED_PATHS = 20

# shlex が punctuation_chars モードで独立トークンにする文字。これだけで構成されたトークンを
# シェル演算子とみなす。`;;` や `>&` のような組み合わせを列挙して維持しなくて済む。
_PUNCTUATION_CHARS = "();<>|&"

# apm を包んで起動する前置コマンド。この直後もコマンド位置として扱う。
# apm のサブコマンドと違い顔ぶれが変わらないので列挙で足りる。
_COMMAND_WRAPPERS = frozenset({"command", "env", "exec", "nice", "nohup", "stdbuf", "sudo", "time"})

# コマンドの前に置く VAR=value 形式の環境変数指定。
_ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")

# git のサブプロセスに与える上限 (秒)。status は巨大なツリーで時間がかかりうる。
_ROOT_TIMEOUT = 10
_STATUS_TIMEOUT = 30


class GitUnavailableError(RuntimeError):
    """git を実行できなかった。検査不能なので deny へ倒す。

    「リポジトリ外なので守備範囲外」(意図された allow) と区別するために型を分ける。
    同じ戻り値へ潰すと、検査できなかったことが無音 allow に化ける。
    """


def get(data: dict[str, Any], *keys: str) -> Any:
    """snake_case と camelCase の両方でフィールドを引く。"""
    for key in keys:
        if key in data:
            return data[key]
    return None


def deny(reason: str) -> NoReturn:
    # ensure_ascii=False にするのは、理由文が日本語でログをそのまま読むため。
    # JSON としての意味は変わらない (受け取り側はどちらでも同じ文字列を得る)。
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": reason,
                }
            },
            ensure_ascii=False,
        )
    )
    sys.exit(0)


def allow_silently() -> NoReturn:
    """判定を出さずに通す。stdout が空なので通常の権限フローがそのまま続く。"""
    sys.exit(0)


def is_operator(token: str) -> bool:
    """トークンがシェル演算子か。"""
    return bool(token) and all(char in _PUNCTUATION_CHARS for char in token)


def tokenize(command: str) -> list[str] | None:
    """コマンド文字列をシェルに近い規則でトークン化する。解釈できなければ None。

    shlex.split は ; & | ( ) を区切りとして扱わないため、演算子が語へ密着すると
    `apm install; git status` が `install;` という 1 トークンになり判定が外れる (実測)。
    punctuation_chars=True で演算子を独立トークンにする。クォートされた文字列は 1 トークンの
    ままなので `echo "apm install"` は誤検出しない。
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def is_command_position(tokens: list[str], index: int) -> bool:
    """そのトークンがコマンド語の位置にあるか。

    位置を問わずに拾うと `grep -rn apm bootstrap.sh` のような検索まで対象になる。
    allowlist 方式では「読み取り専用一覧に無い語」が全て止まるので、位置の判定が要る。
    `sudo -u other apm install` のように wrapper が引数を取る形は検出できないが、apm は
    ユーザー権限のツールでその形を採る理由が無く、自動実行経路は層 1 が塞いでいる。
    """
    for previous in reversed(tokens[:index]):
        if is_operator(previous):
            return True
        if previous.startswith("-"):
            continue
        if _ENV_ASSIGNMENT.match(previous):
            continue
        if previous.rsplit("/", 1)[-1] in _COMMAND_WRAPPERS:
            continue
        return False
    return True


def invocation_args(tokens: list[str], index: int) -> list[str]:
    """apm トークンに続く、その呼び出しの非フラグ引数を返す。演算子で打ち切る。"""
    args: list[str] = []
    for token in tokens[index + 1 :]:
        if is_operator(token):
            break
        if token.startswith("-"):
            continue
        args.append(token)
    return args


def guarded_command(tokens: list[str]) -> str | None:
    """ツリーが汚れているとき止めるべき apm 呼び出しを返す。無ければ None。

    サブコマンドを伴わない呼び出し (apm / apm --help / apm --version) は help を出すだけ
    なので対象外。読み取り専用と確認できたサブコマンドも対象外。
    """
    for index, token in enumerate(tokens):
        if token.rsplit("/", 1)[-1] != "apm" or not is_command_position(tokens, index):
            continue
        args = invocation_args(tokens, index)
        if not args:
            continue
        if any(tuple(args[: len(readonly)]) == readonly for readonly in READONLY_COMMANDS):
            continue
        return " ".join(args[:2])
    return None


def cd_targets(tokens: list[str], cwd: str) -> list[str]:
    """コマンド中の cd で移動する先のうち、展開なしで解決できるものを返す。

    session cwd だけを見ると、別リポジトリへ移ってから apm を走らせる経路が素通りする。
    展開が要るもの ($VAR や $(...)) は解決できないので集めない。これは検査の追加であって
    置換ではないため、集められなかった場合も session cwd の判定はそのまま残る。
    """
    targets: list[str] = []
    for index, token in enumerate(tokens):
        if token != "cd" or not is_command_position(tokens, index):
            continue
        arguments = invocation_args(tokens, index)
        if not arguments:
            continue
        target = arguments[0]
        if "$" in target:
            continue
        targets.append(os.path.normpath(os.path.join(cwd, os.path.expanduser(target))))
    return targets


def run_git(cwd: str, *args: str, timeout: int) -> subprocess.CompletedProcess[str]:
    """git を実行する。起動そのものに失敗したら GitUnavailableError。

    import を関数内へ置いているのは、subprocess の import が実測で 6.8ms かかり、apm を
    含まない大多数の Bash 呼び出しではここへ到達しないため。
    """
    import subprocess

    try:
        return subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GitUnavailableError(f"git を実行できませんでした: {exc}") from exc


def repo_root(cwd: str) -> str | None:
    """cwd が属する git リポジトリのルートを返す。リポジトリ外なら None。"""
    proc = run_git(cwd, "rev-parse", "--show-toplevel", timeout=_ROOT_TIMEOUT)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip() or None


def dirty_paths(root: str) -> list[str]:
    """未コミットの変更のうち、apm の入出力でないものを列挙する。

    パスは NUL 区切りで受け取る。空白や日本語を含むパスを空白分割すると分断され、落ちた分は
    「エラー」ではなく「短い正常な結果」として返るため出力を見ても気づけない。git は既定で
    非 ASCII をクォート表記にするが -z ならそのまま返る。
    """
    proc = run_git(root, "status", "--porcelain", "-z", timeout=_STATUS_TIMEOUT)
    if proc.returncode != 0:
        raise GitUnavailableError(f"git status が失敗しました: {proc.stderr.strip()}")

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


def blocked_repository(candidates: list[str]) -> tuple[str, list[str]] | None:
    """検査対象のディレクトリ群から、未コミットの変更を持つ最初のリポジトリを返す。"""
    seen: set[str] = set()
    for candidate in candidates:
        root = repo_root(candidate)
        if root is None or root in seen:
            continue
        seen.add(root)
        blockers = dirty_paths(root)
        if blockers:
            return root, blockers
    return None


def format_reason(subcommand: str, root: str, blockers: list[str]) -> str:
    listed = "\n".join(f"  {path}" for path in blockers[:MAX_LISTED_PATHS])
    remainder = len(blockers) - MAX_LISTED_PATHS
    more = f"\n  ... 他 {remainder} 件" if remainder > 0 else ""
    return (
        f"apm {subcommand} は deploy 先を上書きし、パッケージに含まれないファイルを削除します。"
        f"{root} に未コミットの変更が {len(blockers)} 件あるため中止しました。\n"
        f"{listed}{more}\n"
        "コミットまたは stash してから再実行してください。"
        "無効化する場合は settings.json の env に APM_INSTALL_GUARD_DISABLE=1 を置きます "
        "(コマンドへの前置ではフックのプロセスに届きません)。"
    )


def main() -> None:
    if os.environ.get("APM_INSTALL_GUARD_DISABLE") == "1":
        allow_silently()

    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else None
    except OSError:
        deny("apm-install-guard: フックの入力を読み取れませんでした")
    except json.JSONDecodeError:
        deny("apm-install-guard: フックの入力を JSON として解釈できませんでした")

    if data is None:
        deny("apm-install-guard: フックの入力が空でした")
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

    # トークン化はコマンド長に比例して重く、16KB のコマンドで 3.7ms かかる (実測)。
    # apm を含まないコマンドが判定に一致することは原理的に無いので、先に安く落とす。
    if "apm" not in command:
        allow_silently()

    tokens = tokenize(command)
    if tokens is None:
        # クォートが不整合でトークン化できないものは判定しない
        allow_silently()

    subcommand = guarded_command(tokens)
    if subcommand is None:
        allow_silently()

    cwd = get(data, "cwd")
    if not isinstance(cwd, str) or not cwd:
        deny(f"apm-install-guard: cwd が取れないため apm {subcommand} を許可できません")

    try:
        blocked = blocked_repository([cwd, *cd_targets(tokens, cwd)])
    except GitUnavailableError as exc:
        deny(f"apm-install-guard: 検査できませんでした: {exc}")

    if blocked is None:
        allow_silently()

    deny(format_reason(subcommand, *blocked))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # SystemExit は BaseException 直下なのでここを通らない
        deny(f"apm-install-guard: 予期しない例外: {exc}")
