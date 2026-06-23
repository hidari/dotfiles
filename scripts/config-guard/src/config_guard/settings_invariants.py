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

# committed に含めてはならないキー（PR #22 で消した dead config 等）
_FORBIDDEN_KEYS: tuple[str, ...] = ("enabledMcpjsonServers",)

# ユーザーのローカル絶対パス（gitleaks との多層防御）
_USER_PATH = re.compile(r"/(Users|home)/[a-z_][a-z0-9._-]*")

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

    # 5. permissions のツール名妥当性
    for token in extract_settings_permission_tokens(settings):
        reason = validate_tool_token(token)
        if reason is not None:
            findings.append(Finding(_SRC, token, reason))

    return findings
