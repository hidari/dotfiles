"""committed settings.json の構造不変条件を検証する。

セキュリティ・正当性に絞ったハードフェイルのみ。個人の好み（通知トグル等）は咎めない。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any, NamedTuple

from config_guard.extractors import extract_settings_permission_tokens, iter_strings
from config_guard.models import Finding
from config_guard.tool_refs import validate_tool_token

_SRC = "settings.json (committed)"

# committed に含めてはならないキー（過去に混入した dead config の再滞留防止）
_FORBIDDEN_KEYS: tuple[str, ...] = ("enabledMcpjsonServers",)

# ユーザーのローカル絶対パス（gitleaks との多層防御）
_USER_PATH = re.compile(r"/(Users|home)/[a-z_][a-z0-9._-]*")

# path 付き Glob(...)/Grep(...) permission 規則の検出パターン（bare は対象外）。
_INEFFECTIVE_PATH_RULE = re.compile(r"^(?:Glob|Grep)\((.+)\)$")

# 必須フックが守るツール。matcher がこれに一致しないグループは配線として数えない。
_GUARDED_TOOL = "Bash"


def _matcher_covers_guarded_tool(matcher: Any) -> bool:
    """グループの matcher が対象ツールに一致するか。

    省略・空文字・"*" は全ツールに一致する。それ以外は正規表現として完全一致で照合する。
    Claude Code が部分一致で解決する場合、`ash` のような書き方をここでは一致とみなさないが、
    この向きの誤りは「動いている配線を config-guard が咎める」可視で安価な失敗で済む。
    逆向きに緩めると、起動しない配線を配線済みと読む沈黙した失敗になる。
    """
    if matcher is None or matcher in ("", "*"):
        return True
    if not isinstance(matcher, str):
        return False
    try:
        return re.fullmatch(matcher, _GUARDED_TOOL) is not None
    except re.error:
        return False


def _matcher_covers_all_sources(matcher: Any) -> bool:
    """SessionStart のグループが全開始理由を覆うか。

    SessionStart の matcher はツール名ではなく開始理由 (startup / resume / clear /
    compact / fork) を見る。PreToolUse の述語を使い回すと、ツール名を書いたグループが
    全一致して配線済みに見える。

    全理由に一致する書き方 (省略・空文字・"*") だけを配線として数える。個々の理由を
    列挙する形は数えない。理由の一覧を literal で持つと、Claude Code が理由を増やした
    ときに検査側だけが古くなるためである。この向きの誤りは「動いている配線を咎める」
    可視で安価な失敗で済み、逆向きに緩めると発火しない配線を配線済みと読む。
    """
    return matcher is None or matcher in ("", "*")


class _EventRequirement(NamedTuple):
    """イベントごとの必須フックの組と matcher 述語をまとめる。

    2 つの並列 dict (スクリプトの組 / matcher 述語) を手で同期させると、イベントを
    足すとき片方の編集を忘れても気づけない (`_wired_commands` は `.get` 無しで
    引くため、欠けていれば scan 時に KeyError で落ちる)。1 つの表にすれば
    同期漏れが構造的に起こらない。
    """

    scripts: tuple[str, ...]
    matcher_covers: Callable[[Any], bool]


# 必ず配線されていなければならないフック（本体のファイル名で照合する）。
# フック本体が存在しても settings.json から外れれば何も守らないため、取り付け自体を
# 不変条件にする。これが無いと検査機構の 3 種変異のうち「取り付けを外す」をテストで
# 捕まえられない（実際この検査を足すまで、tirith-check.py の配線を外しても全テストが緑だった）。
#
# 名前で宣言するのは、存在するファイルの集合から必須集合を導くと、本体を消せば要求も
# 消えて緑になるためである。それは検査が必要な状況でだけ検査が動かない自己敗北にあたる。
# 配線漏れの検出は逆向きなので導出でよく、hook_wiring が持つ。
#
# matcher の意味はイベントで違うので述語を使い回さない (使い回すと SessionStart に
# ツール名を書いた配線が全一致で通る)。
_REQUIRED_HOOKS: dict[str, _EventRequirement] = {
    "PreToolUse": _EventRequirement(
        ("tirith-check.py", "apm-install-guard.py"), _matcher_covers_guarded_tool
    ),
    "SessionStart": _EventRequirement(("guard-health.py",), _matcher_covers_all_sources),
}

# nested traversal から必ず除外しなければならない CLAUDE.md（glob 値を完全一致で照合する）。
# home/.claude/CLAUDE.md は ~/.claude/CLAUDE.md の symlink 実体なので、この配置のまま
# home/.claude/ 配下のファイルを Read すると、User memory として既にロード済みの同一内容が
# もう一度コンテキストへ入る。subagent は起動ごとに新鮮なコンテキストを持つため、
# 起動した本数だけ二重化する（2026-08-20 に除外あり/なしの対照で実測）。
# 外しても例外は出ず静かに二重化するだけなので、フックの配線と同じく取り付けを pin する。
_REQUIRED_CLAUDE_MD_EXCLUDES: tuple[str, ...] = ("**/home/.claude/CLAUDE.md",)

# committed に許可する公開 marketplace。ここに無い marketplace を参照する plugin は弾く。
_PUBLIC_MARKETPLACES: frozenset[str] = frozenset(
    {
        "claude-plugins-official",
        "superpowers-marketplace",
        "googlechrome",
        "chrome-devtools-plugins",
    }
)


def _wired_commands(settings: dict[str, Any], event: str) -> list[str]:
    """hooks[event] で、そのイベントの述語を満たすグループの command 文字列を集める。

    グループを分けるか 1 グループに複数要素を置くかは配線の自由度なので、両方を平らに集める。
    述語を満たさないグループは数えない。本体が残っていても起動しないので、
    それは配線を外したのと同じである。
    """
    covers = _REQUIRED_HOOKS[event].matcher_covers
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return []
    groups = hooks.get(event)
    if not isinstance(groups, list):
        return []

    commands: list[str] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        if not covers(group.get("matcher")):
            continue
        entries = group.get("hooks")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            command = entry.get("command")
            if isinstance(command, str):
                commands.append(command)
    return commands


def _ineffective_path_rule_reason(token: str) -> str | None:
    """inert な file-path permission 規則の書き換え理由を返す（該当しなければ None）。

    file access を gate する file permission check は Read(...) 規則のみを見る（Claude Code 仕様）。
    permissions に Glob(...)/Grep(...) と path を書いても無視されるため Read(...) へ寄せる。
    bare な Glob/Grep はツール全体を gate する有効な形なので括弧付きのみ対象。
    """
    match = _INEFFECTIVE_PATH_RULE.match(token.strip())
    if match is None:
        return None
    return f"file permission check は Read(...) のみ有効: Read({match.group(1)}) を使う"


def check_settings_invariants(settings: dict[str, Any]) -> list[Finding]:
    """committed settings.json の不変条件を検証し、違反を Finding リストで返す。"""
    findings: list[Finding] = []

    # 1. 禁止キー
    for key in _FORBIDDEN_KEYS:
        if key in settings:
            findings.append(Finding(_SRC, key, f"committed に含めてはならないキー: {key}"))

    # 2. ユーザー絶対パス
    for text in iter_strings(settings):
        if _USER_PATH.search(text):
            findings.append(Finding(_SRC, text, "ユーザーのローカル絶対パスを含む"))

    # 3. directory source の marketplace
    markets = settings.get("extraKnownMarketplaces", {})
    if isinstance(markets, dict):
        for name, spec in markets.items():
            source = spec.get("source", {}) if isinstance(spec, dict) else {}
            if isinstance(source, dict) and source.get("source") == "directory":
                findings.append(Finding(_SRC, name, f"directory source の marketplace: {name}"))

    # 4. 非公開 marketplace を参照する plugin
    plugins = settings.get("enabledPlugins", {})
    if isinstance(plugins, dict):
        for plugin_key in plugins:
            if "@" in plugin_key:
                market = plugin_key.split("@", 1)[1]
                if market not in _PUBLIC_MARKETPLACES:
                    findings.append(
                        Finding(_SRC, plugin_key, f"非公開 marketplace を参照する plugin: {market}")
                    )

    # 5. permissions のトークンごとに shape 妥当性と file-path 規則の canonical 化を委譲判定する
    for token in extract_settings_permission_tokens(settings):
        for reason in (validate_tool_token(token), _ineffective_path_rule_reason(token)):
            if reason is not None:
                findings.append(Finding(_SRC, token, reason))

    # 6. 必須フックが各イベントへ配線されているか
    for event, requirement in _REQUIRED_HOOKS.items():
        commands = _wired_commands(settings, event)
        for script in requirement.scripts:
            if not any(script in command for command in commands):
                findings.append(
                    Finding(_SRC, script, f"{event} に必須フックが配線されていません: {script}")
                )

    # 7. nested traversal の除外が配線されているか。
    #    型を間違えた値は Claude Code 側では無警告で無視される。加えて文字列を渡されると
    #    `in` が部分一致で満たされて検査が素通りするため、list 以外は空として扱う
    excludes = settings.get("claudeMdExcludes")
    if not isinstance(excludes, list):
        excludes = []
    for pattern in _REQUIRED_CLAUDE_MD_EXCLUDES:
        if pattern not in excludes:
            findings.append(
                Finding(_SRC, pattern, f"claudeMdExcludes に必須の除外がありません: {pattern}")
            )

    return findings
