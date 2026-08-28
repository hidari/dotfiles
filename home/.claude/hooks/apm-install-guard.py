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

deny のときだけ JSON を出し、それ以外は無出力の exit 0 とする。複数の PreToolUse フックの合成は
precedence が deny > defer > ask > allow と公式ドキュメントに定められているので、allow を出しても
他フックの deny が消えることはない。それでも allow は出さない。フックの allow は permission
プロンプトを飛ばすため、このガードが「通した」ことが他の検査の省略に化ける。

判定の網はこの層ではなく PATH shim (scripts/apm-guard/apm) が持つ。shim は apm が exec される
瞬間に立つので、コマンド文字列がどう書かれていたかに依存しない。このフックが受け持つのは、shim を
迂回できる 2 形 (絶対パスでの起動、PATH の一時差し替え) と、それらを判定する過程で shim の
配置漏れに気づくことである。配置漏れの検出はこの層がパースできる形にしか効かない (下の
shim_resolves の呼び出し位置を参照)。

したがってここでのトークン化の射程は「トップレベルのトークンとして apm が現れる形」までとする。
包み込み (sh -c / バッククォート / eval) と変数展開は追わない。追ってもシェル文法の近似は
終わらないことを実測で確かめた (26 ケース中 7 件が残り、区切りの集合を広げるたびに新しい形が
出た)。絶対パスを変数やコピー経由で叩く形は shim とこの層のどちらにも掛からないが、事故としては
発生しない形なので受容している。

未コミット変更の判定そのものは scripts/apm-guard/lib.sh にあり、bootstrap.sh の
install_apm_packages と shim の両方がそれを source する。この Python 側の判定と bash 側の判定が
一致していることは scripts/claude-hooks/tests/test_apm_install_guard.py の cross-pin テストが
見る (bats 側にはこの一致を見るテストは無い)。
"""

from __future__ import annotations

import os
import re
import shlex
import sys
from typing import TYPE_CHECKING, NoReturn

import guard_probes
import pretooluse

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

# git へ渡す環境から落とす変数の接頭辞。git はこれらを `-C` で渡したパスより優先し、所在
# (GIT_DIR / GIT_WORK_TREE) も探索の境界 (GIT_CEILING_DIRECTORIES) も外から動かせる。しかも
# 誤りは例外ではなく「そちらは clean なので許可」という無音 allow で返るため、ガードが外れた
# こと自体に気づけない。
#
# 危険なものを列挙する形は採らない。git が変数を増やすたびに黙って穴が開き、漏れは検査でも
# 見えないためである。ここで git へ渡したい GIT_ 変数は 1 つも無いので、接頭辞ごと落として
# 漏れを原理的に無くす。落ちて困る変数 (GIT_CONFIG_GLOBAL 等) があっても、その向きの誤りは
# ignore の解釈が緩まらない側 = 未コミット扱いが増えて deny が出る側なので、このガードが
# 設計上受け入れている安価な失敗で済む。
_DROPPED_ENV_PREFIX = "GIT_"

# 入力を解釈できなかったときの deny 理由。共有層は理由を problem で返すだけで文面を持たない。
# このフックは検査不能をすべて deny へ倒すので、tirith 側のような逃げ道は用意しない。
_INPUT_PROBLEM_REASONS: dict[pretooluse.InputProblem, str] = {
    pretooluse.InputProblem.EMPTY: "apm-install-guard: フックの入力が空でした",
    pretooluse.InputProblem.MALFORMED_JSON: (
        "apm-install-guard: フックの入力を JSON として解釈できませんでした"
    ),
    pretooluse.InputProblem.NOT_OBJECT: "apm-install-guard: フックの入力が object ではありません",
    pretooluse.InputProblem.TOOL_INPUT_NOT_OBJECT: (
        "apm-install-guard: tool_input が object ではありません"
    ),
    pretooluse.InputProblem.NO_COMMAND: "apm-install-guard: Bash コマンドを読み取れませんでした",
}


class GitUnavailableError(RuntimeError):
    """git を実行できなかった。検査不能なので deny へ倒す。

    「リポジトリ外なので守備範囲外」(意図された allow) と区別するために型を分ける。
    同じ戻り値へ潰すと、検査できなかったことが無音 allow に化ける。
    """


def deny(reason: str) -> NoReturn:
    print(pretooluse.decision_payload("deny", reason))
    sys.exit(0)


def allow_silently() -> NoReturn:
    """判定を出さずに通す。stdout が空なので通常の権限フローがそのまま続く。"""
    sys.exit(0)


def is_operator(token: str) -> bool:
    """トークンがシェル演算子か。"""
    return bool(token) and all(char in _PUNCTUATION_CHARS for char in token)


def is_redirect(token: str) -> bool:
    """トークンがリダイレクト演算子か。

    制御演算子 (; | && || 括弧) の直後はコマンド位置だが、リダイレクト演算子の直後は
    出力先のファイル名でコマンドではない。両者を区別しないと
    `printf x >> scripts/apm-guard/apm` が apm の呼び出しに化ける (実測)。
    リダイレクトは必ず < か > を含み、制御演算子はどちらも含まない。
    """
    return is_operator(token) and ("<" in token or ">" in token)


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

    誤検知の側も同じだけ重い。apm と無関係のコマンドが止まると、ガードが日常の操作を壊す。
    リダイレクト先と環境変数代入はどちらもコマンドではないので、コマンド位置から外す。
    """
    for previous in reversed(tokens[:index]):
        if is_operator(previous):
            return not is_redirect(previous)
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
        # VAR=... は代入であってコマンドではない。basename だけで見ると
        # FOO=/opt/homebrew/bin/apm が apm の呼び出しに化ける。代入かどうかの規則は
        # is_command_position が手前のトークンに対して既に持っており、判定する側の
        # トークンにも同じ規則が要る。
        if _ENV_ASSIGNMENT.match(token):
            continue
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

    GIT_ で始まる環境変数は落としてから呼ぶ (_DROPPED_ENV_PREFIX のコメント参照)。
    """
    import subprocess

    env = {
        key: value for key, value in os.environ.items() if not key.startswith(_DROPPED_ENV_PREFIX)
    }
    try:
        return subprocess.run(
            ["git", "-C", cwd, *args],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            env=env,
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

    entries = [entry for entry in proc.stdout.split("\0") if entry]
    blockers: list[str] = []
    index = 0
    while index < len(entries):
        # porcelain の各エントリは "XY <path>" 形式。先頭 3 文字が状態フィールド
        status, path = entries[index][:2], entries[index][3:]
        index += 1
        paths = [path]
        # rename と copy だけは "XY <to>\0<from>\0" の 2 チャンクで返る。from 側は状態
        # フィールドを持たないので、同じ規則で切ると先頭 3 文字が削れて実在しないパスになる。
        if ("R" in status or "C" in status) and index < len(entries):
            paths.append(entries[index])
            index += 1
        # 1 つの記録が指すパスがすべて apm の入出力のときだけ許可する。移動先が apm.yml でも
        # 移動元が違えば、それは失われうる変更である。
        if all(p.rsplit("/", 1)[-1] in ALLOWED_DIRTY_BASENAMES for p in paths):
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
    except OSError:
        deny("apm-install-guard: フックの入力を読み取れませんでした")

    try:
        payload = pretooluse.parse_payload(raw)
        command = pretooluse.bash_command(payload)
    except pretooluse.HookInputError as exc:
        deny(_INPUT_PROBLEM_REASONS[exc.problem])

    if command is None:
        allow_silently()

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

    # shim が PATH 上に無ければ、包み込みや変数展開の形はどこにも掛からない。ここで倒すのは
    # そのことに気づける形を 1 つでも残すためで、配置漏れ全体を捕まえる検査ではない。
    # この判定へ来るのは guarded_command がパースできた形だけなので、shim だけが担当する
    # 包み込み・変数展開・xargs の形では、配置漏れは無音の素通りのまま残る (実測)。
    # 配置漏れそのものを検出する層は、コマンド単位ではなくセッション単位に置く必要がある。
    if not guard_probes.shim_resolves():
        deny(
            f"apm-install-guard: apm ガードの shim が PATH 上に見つからないため apm {subcommand} を"
            "許可できません。"
            f"{guard_probes.shim_path()} が配置され、PATH の先頭にあることを確認してください "
            "(bootstrap.sh が SYMLINK_PAIRS で張り、.zshrc が mise activate の直後で PATH へ"
            "足します)。"
        )

    cwd = pretooluse.get(payload, "cwd")
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
