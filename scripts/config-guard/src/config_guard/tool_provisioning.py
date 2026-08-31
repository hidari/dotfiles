"""リポジトリが要求するコマンドが bootstrap の実体化経路で供給されるか検査する。

bootstrap.sh がツールを実体化する経路は brew bundle (home/.Brewfile) と mise install
(home/.config/mise/config.toml) の 2 つで、どちらの宣言にも無いコマンドは新しいマシンで
入らない。実際 just / pnpm / tirith を mise の pin から外して brew 管理へ移したとき
Brewfile へ足し忘れ、pre-commit も CI も素通りした。uv と bats は最初からどちらにも
無かった。手元のマシンには手で入れた実体があるので、壊れているのは再現性だけであり
エラーとしては一度も現れない。

**ただし、この検査が覆うのはその 3 つのうち tirith だけである。** pnpm と just は下の射程の
とおり要求側に入らないので、同じ事故がもう一度起きても緑のまま通る。動機に挙げた事故が
まるごと再発防止されたと読まないこと。

要求側は .pre-commit-config.yaml から導出する。手で維持する一覧にすると、足し忘れが
この検査自身の穴になるためである。pre-commit の外で要る分だけを ALSO_REQUIRED が理由を
添えて持つ。

## この検査の射程

見るのは「リポジトリの検査とテストを回すために要るコマンド」だけである。個人の作業で
使うだけのコマンド (pnpm / just など) は要求側に入らないので、それらが Brewfile から
消えてもここは赤くならない。射程を広げるなら要求の導出元を足すこと。

## Brewfile を行で読む理由

Brewfile は Ruby の DSL でパーサを持てない。brew bundle を呼べば正確だが、検査が
外部 CLI とネットワークに依存し CI で動かせなくなる。そこで受け付ける形を BREW_ENTRY へ
狭く固定して行で読む。コメント行や phantom entry の誤読は tests が pin する
(apm_gitignore.py が YAML を stdlib だけで読むのと同じ判断)。

go 行 (`go "golang.org/x/tools/gopls"`) は供給側に数えない。brew bundle がこの型を
実体化するかを確かめていないためで、確かめずに数えると「供給されている」という未検証の
主張を検査が持つことになる。
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path

import yaml

from config_guard.mise_pins import MISE_CONFIG_PATH, load_mise_tools
from config_guard.models import Finding

PRECOMMIT_CONFIG_PATH = ".pre-commit-config.yaml"
BREWFILE_PATH = "home/.Brewfile"

# Brewfile のうち供給側に数える行。`brew "x", trusted: true` のような後続オプションは
# 閉じ引用符で切れるので拾わない。行頭が `#` のコメントはそもそも一致しない。
BREW_ENTRY = re.compile(r'^\s*(?:brew|cask)\s+"([^"]+)"')

# entry の先頭が shell のとき、-c の本体からもコマンドを取り出す。ここを見ないと
# `bash -c '<tool> ...'` の形で要求が隠れ、検査が静かに取りこぼす。
SHELLS = frozenset({"bash", "sh", "zsh"})

# shlex が punctuation_chars モードで独立トークンにする文字。これだけで構成された
# トークンをシェル演算子とみなす。`;;` や `>&` のような組み合わせを列挙せずに済む。
# 素の shlex.split は演算子を区切らないので `foo && bar` の bar がコマンド位置として
# 見えなくなる。同じ判断を home/.claude/hooks/apm-install-guard.py の tokenize が持つが、
# あちらは別のデプロイ単位 (フックは ~/.claude へ配られる) なので共有していない。
_PUNCTUATION_CHARS = "();<>|&"

# formula 名と、それが提供するコマンド名が違うもの。既定は名前の最後の `/` 区切り。
# `brew info --json=v2 <formula>` を引けば正確に導出できるが、Brewfile を行で読む判断と
# 同じ理由 (外部 CLI とネットワークへの依存で CI から外れる) で pin にした。例外は少ないので
# 列挙で足りる。新しい formula を足すときは、コマンド名が formula 名と違う場合だけここへ書く。
FORMULA_COMMANDS: dict[str, tuple[str, ...]] = {
    "powershell": ("pwsh",),
    "bats-core": ("bats",),
}

# pre-commit の entry からは導出できないが、供給されていないと困るコマンドと、その理由。
ALSO_REQUIRED: dict[str, str] = {
    "tirith": (
        "PreToolUse(Bash) フックが検査を委譲する先。不在時は意図した fail-open で "
        "検査が無音のまま通るので、欠けてもエラーにならない"
    ),
    "bats": (
        "scripts/tests/ のテストランナー。CI は setup-bats composite で別経路から入れるが、"
        "ローカルで CI と同じテストを回す経路は Brewfile しかない"
    ),
    "pre-commit": "フック自身の実行系。これが無いと下の要求すべてが走らない",
}

# 供給を要求しないコマンドと、その理由。
# 今のところ SHELLS と同じ 3 つだが、SHELLS から導出してはいけない。SHELLS は「-c の本体を
# 展開する対象」、こちらは「OS が同梱するので供給を求めない」で、概念が違う。たまたま
# 一致しているだけである。`fish -c` を展開したくなって SHELLS へ fish を足すと、導出形は
# fish を「OS が同梱する」と偽って免除する (macOS も Linux も同梱しない)。
NOT_PROVISIONED: dict[str, str] = {
    "bash": "OS が同梱する。pre-commit が起動するのも PATH 上の実体で Brewfile 版ではない",
    "sh": "bash と同じ理由",
    "zsh": "bash と同じ理由",
}


def required_commands(repo_root: str) -> dict[str, str]:
    """pre-commit の entry から要求コマンドを導出し、由来 (hook id) を添えて返す。

    対象は language: system のフックだけである。それ以外は pre-commit が自分で環境を
    作るのでホストの PATH を要求しない。
    """
    config_path = Path(repo_root) / PRECOMMIT_CONFIG_PATH
    if not config_path.is_file():
        return {}

    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    found: dict[str, str] = {}
    for repo in config.get("repos") or []:
        for hook in repo.get("hooks") or []:
            if hook.get("language") != "system":
                continue
            entry = hook.get("entry")
            if not isinstance(entry, str):
                continue
            origin = str(hook.get("id", entry))
            for command in _entry_commands(entry):
                found.setdefault(command, origin)
    return found


def _tokenize(command: str) -> list[str] | None:
    """演算子を独立トークンにしてコマンド文字列を分解する。解釈できなければ None。

    クォートされた文字列は 1 トークンのままなので、引数に現れる `$(...)` を
    コマンド位置と誤読しない。
    """
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    try:
        return list(lexer)
    except ValueError:
        return None


def _split_on_operators(tokens: list[str]) -> list[list[str]]:
    """演算子トークンで区切る。各区間の先頭がコマンド位置になる。"""
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token and all(char in _PUNCTUATION_CHARS for char in token):
            segments.append([])
        else:
            segments[-1].append(token)
    return segments


def _entry_commands(entry: str) -> list[str]:
    """entry から起動されるコマンド名を取り出す。shell の -c 本体まで 1 段だけ潜る。"""
    tokens = _tokenize(entry)
    if tokens is None:
        # 引用符が閉じていない entry。解釈できないので要求を推測せず空で返す
        return []

    commands: list[str] = []
    for segment in _split_on_operators(tokens):
        if not segment:
            continue
        commands.append(segment[0])
        if segment[0] in SHELLS and "-c" in segment:
            body_index = segment.index("-c") + 1
            if body_index < len(segment):
                commands.extend(_entry_commands(segment[body_index]))
    return commands


def provided_commands(repo_root: str) -> set[str]:
    """bootstrap が実体化するコマンド名の集合 (Brewfile ∪ mise config の [tools])。"""
    provided: set[str] = set()

    brewfile = Path(repo_root) / BREWFILE_PATH
    if brewfile.is_file():
        for line in brewfile.read_text(encoding="utf-8").splitlines():
            matched = BREW_ENTRY.match(line)
            if matched is None:
                continue
            formula = matched.group(1)
            provided.update(FORMULA_COMMANDS.get(formula, (formula.rsplit("/", 1)[-1],)))

    tools = load_mise_tools(repo_root)
    if isinstance(tools, dict):
        # mise の backend 修飾 ("cargo:sqlx-cli") は最後の区切りがコマンド名になる
        provided.update(str(tool).rsplit(":", 1)[-1] for tool in tools)

    return provided


def uses_provisioning_manifests(repo_root: str) -> bool:
    """このリポジトリが brew bundle / mise install で供給する形を取っているか。"""
    root = Path(repo_root)
    return (root / BREWFILE_PATH).is_file() or (root / MISE_CONFIG_PATH).is_file()


def check_tool_provisioning(repo_root: str) -> list[Finding]:
    """要求されるコマンドが 1 つでも供給側の宣言に無ければ報告する。

    供給側の宣言を 1 つも持たないリポジトリは、この供給モデルを採っていないので
    検査対象にしない。この early return は宣言ファイルごと消したケースを見逃すが、
    そこは tests の test_real_repo_has_provisioning_manifests が実リポジトリに対して縛る。
    """
    if not uses_provisioning_manifests(repo_root):
        return []

    required = required_commands(repo_root)
    required.update({name: "pre-commit の外" for name in ALSO_REQUIRED if name not in required})

    provided = provided_commands(repo_root)

    findings: list[Finding] = []
    for command, origin in sorted(required.items()):
        if command in NOT_PROVISIONED or command in provided:
            continue
        reason = ALSO_REQUIRED.get(command)
        detail = command if reason is None else f"{command} ({reason})"
        findings.append(
            Finding(
                BREWFILE_PATH,
                detail,
                f"{origin} が要求するが {BREWFILE_PATH} にも {MISE_CONFIG_PATH} にも宣言が無い。"
                "bootstrap.sh は新しいマシンでこれを実体化しない",
            )
        )
    return findings
