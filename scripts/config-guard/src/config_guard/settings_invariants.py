"""committed settings.json の構造不変条件を検証する。

セキュリティ・正当性に絞ったハードフェイルのみ。個人の好み（通知トグル等）は咎めない。
"""

from __future__ import annotations

import re
from typing import Any

from config_guard.extractors import extract_settings_permission_tokens
from config_guard.models import Finding
from config_guard.tool_refs import validate_tool_token

_SRC = "settings.json (committed)"

# committed に含めてはならないキー（過去に混入した dead config の再滞留防止）
_FORBIDDEN_KEYS: tuple[str, ...] = ("enabledMcpjsonServers",)

# ユーザーのローカル絶対パス（gitleaks との多層防御）
_USER_PATH = re.compile(r"/(Users|home)/[a-z_][a-z0-9._-]*")

# path 付き Glob(...)/Grep(...) permission 規則の検出パターン（bare は対象外）。
_INEFFECTIVE_PATH_RULE = re.compile(r"^(?:Glob|Grep)\((.+)\)$")

# PreToolUse に必ず配線されていなければならないフック（本体のファイル名で照合する）。
# フック本体が存在しても settings.json から外れれば何も守らないため、取り付け自体を
# 不変条件にする。これが無いと検査機構の 3 種変異のうち「取り付けを外す」をテストで
# 捕まえられない（実際この検査を足すまで、tirith-check.py の配線を外しても全テストが緑だった）。
_REQUIRED_PRETOOLUSE_HOOKS: tuple[str, ...] = ("tirith-check.py", "apm-install-guard.py")

# 必須フックが守るツール。matcher がこれに一致しないグループは配線として数えない。
_GUARDED_TOOL = "Bash"

# nested traversal から必ず除外しなければならない CLAUDE.md（glob で照合する）。
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


def _iter_strings(obj: Any) -> list[str]:
    """オブジェクトを再帰的に走査してすべての文字列を返す。"""
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            out.extend(_iter_strings(value))
    elif isinstance(obj, list):
        for value in obj:
            out.extend(_iter_strings(value))
    return out


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


def _pretooluse_commands(settings: dict[str, Any]) -> list[str]:
    """hooks.PreToolUse で対象ツールに配線された command 文字列を集める。

    グループを分けるか 1 グループに複数要素を置くかは配線の自由度なので、両方を平らに集める。
    イベントは PreToolUse だけを見る。PostToolUse に置いても呼び出し前には走らないため。
    matcher が対象ツールに一致しないグループは数えない。本体が残っていても起動しないので、
    それは配線を外したのと同じである。
    """
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return []
    groups = hooks.get("PreToolUse")
    if not isinstance(groups, list):
        return []

    commands: list[str] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        if not _matcher_covers_guarded_tool(group.get("matcher")):
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
    for text in _iter_strings(settings):
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

    # 6. 必須フックが PreToolUse に配線されているか
    commands = _pretooluse_commands(settings)
    for script in _REQUIRED_PRETOOLUSE_HOOKS:
        if not any(script in command for command in commands):
            findings.append(
                Finding(_SRC, script, f"PreToolUse に必須フックが配線されていません: {script}")
            )

    # 7. nested traversal の除外が配線されているか。
    #    型を間違えた値は Claude Code 側では無警告で無視されるため、list 以外は空として扱う
    excludes = settings.get("claudeMdExcludes")
    listed = excludes if isinstance(excludes, list) else []
    for pattern in _REQUIRED_CLAUDE_MD_EXCLUDES:
        if pattern not in listed:
            findings.append(
                Finding(_SRC, pattern, f"claudeMdExcludes に必須の除外がありません: {pattern}")
            )

    return findings
