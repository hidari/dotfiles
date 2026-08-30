"""検査対象からツール名トークンを抽出する。

SKILL.md は frontmatter の allowed-tools リスト（フラットなリスト）を標準ライブラリ
だけで抽出する（YAML パーサ依存を避ける）。settings.json は dict から permissions を
取り出す。
"""

from __future__ import annotations

import re
from typing import Any

_FRONTMATTER_DELIM = re.compile(r"^---\s*$")
_ALLOWED_TOOLS_KEY = re.compile(r"^allowed-tools\s*:")
_LIST_ITEM = re.compile(r"^\s*-\s+(.+?)\s*$")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def iter_strings(obj: Any) -> list[str]:
    """オブジェクトを再帰的に走査してすべての文字列を返す。

    settings.json のような入れ子の dict/list から文字列だけを集める純関数。
    hook_wiring と settings_invariants の両方がこれを使う。分割の実装をここへ
    1 つだけ置くのは、モジュールごとに書くと片方だけが振る舞いを変えても他方が
    気づかず両方緑のまま通るためである (git_run.tracked_files の前例に揃える)。
    """
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            out.extend(iter_strings(value))
    elif isinstance(obj, list):
        for value in obj:
            out.extend(iter_strings(value))
    return out


def extract_skill_tokens(skill_md: str) -> list[str]:
    """SKILL.md の frontmatter から allowed-tools のツール名を抽出する。無ければ空。"""
    lines = skill_md.splitlines()
    delims = [i for i, ln in enumerate(lines) if _FRONTMATTER_DELIM.match(ln)]
    if len(delims) < 2:
        return []
    front = lines[delims[0] + 1 : delims[1]]
    tokens: list[str] = []
    in_block = False
    for ln in front:
        if _ALLOWED_TOOLS_KEY.match(ln):
            in_block = True
            continue
        if in_block:
            item = _LIST_ITEM.match(ln)
            if item:
                tokens.append(_unquote(item.group(1)))
            elif ln.strip() == "":
                continue
            else:
                break
    return tokens


def extract_settings_permission_tokens(settings: dict[str, Any]) -> list[str]:
    """settings.json の permissions.{allow,deny,ask} の全トークンを抽出する。"""
    perms = settings.get("permissions", {})
    tokens: list[str] = []
    if isinstance(perms, dict):
        for key in ("allow", "deny", "ask"):
            value = perms.get(key, [])
            if isinstance(value, list):
                tokens.extend(str(token) for token in value)
    return tokens
