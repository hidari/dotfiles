"""extractors のトークン抽出仕様テスト。"""

from __future__ import annotations

from config_guard.extractors import (
    extract_settings_permission_tokens,
    extract_skill_tokens,
)

SKILL_WITH_TOOLS = """\
---
name: sample
description: サンプル
allowed-tools:
  - Read
  - Bash(git *)
  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__take_snapshot
---

本文
"""

SKILL_NO_TOOLS = """\
---
name: sample
description: allowed-tools を持たない skill
---

本文
"""

SKILL_TOOLS_NOT_LAST = """\
---
name: sample
allowed-tools:
  - Read
  - Write
description: allowed-tools の後に別キーがある
---
"""


class TestExtractSkillTokens:
    def test_extracts_list(self) -> None:
        assert extract_skill_tokens(SKILL_WITH_TOOLS) == [
            "Read",
            "Bash(git *)",
            "mcp__plugin_chrome-devtools-mcp_chrome-devtools__take_snapshot",
        ]

    def test_empty_when_absent(self) -> None:
        assert extract_skill_tokens(SKILL_NO_TOOLS) == []

    def test_stops_at_next_key(self) -> None:
        assert extract_skill_tokens(SKILL_TOOLS_NOT_LAST) == ["Read", "Write"]

    def test_empty_when_no_frontmatter(self) -> None:
        assert extract_skill_tokens("# 本文だけ\n") == []


class TestExtractSettingsPermissionTokens:
    def test_collects_allow_deny_ask(self) -> None:
        settings = {
            "permissions": {
                "allow": ["Bash(cat:*)", "WebSearch"],
                "deny": ["NoteboolEdit"],
                "ask": ["Bash(git commit:*)"],
            }
        }
        assert extract_settings_permission_tokens(settings) == [
            "Bash(cat:*)",
            "WebSearch",
            "NoteboolEdit",
            "Bash(git commit:*)",
        ]

    def test_empty_when_no_permissions(self) -> None:
        assert extract_settings_permission_tokens({}) == []
