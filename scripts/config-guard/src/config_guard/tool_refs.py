"""ツール名トークンの妥当性を判定する純粋関数。

Hybrid 方式: 既知の legacy/誤名を denylist で弾き、それ以外は形（shape）だけ
検証する。built-in 名の完全 allowlist 照合はしない（Claude Code のツール追加で
検証器が drift しないため）。
"""

from __future__ import annotations

import re

# plugin 化で legacy 化した un-prefixed MCP server。新たな移行時にここへ 1 行追加する。
LEGACY_MCP_PREFIXES: tuple[str, ...] = (
    "mcp__chrome-devtools__",
    "mcp__claude-in-chrome__",
)

# 既知の誤名・タイポ。実在しない bare ツール名。再混入防止のため列挙する。
KNOWN_BAD_NAMES: frozenset[str] = frozenset({"Git", "NoteboolEdit"})

# MCP ツール形: mcp__<server>__<tool>（plugin 形・非 plugin 形の双方を許容）
_MCP_SHAPE = re.compile(r"^mcp__[A-Za-z0-9_-]+__[A-Za-z0-9_]+$")

# built-in 形: 英大文字始まりのツール名ヘッド + 任意の (...) permission specifier
_BUILTIN_SHAPE = re.compile(r"^[A-Z][A-Za-z0-9]*(\(.*\))?$")


def validate_tool_token(token: str) -> str | None:
    """ツール名トークン 1 個を検証する。妥当なら None、問題があれば理由を返す。"""
    stripped = token.strip()
    if not stripped:
        return "空のツール名"
    for prefix in LEGACY_MCP_PREFIXES:
        if stripped.startswith(prefix):
            return f"legacy な未 prefix MCP ツール名 (plugin 形へ移行済み): {stripped}"
    if stripped in KNOWN_BAD_NAMES:
        return f"実在しないツール名: {stripped}"
    if _MCP_SHAPE.match(stripped) or _BUILTIN_SHAPE.match(stripped):
        return None
    return f"不正な形のツール名: {stripped}"
