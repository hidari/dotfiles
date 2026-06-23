"""settings_invariants の仕様テスト。"""

from __future__ import annotations

from typing import Any

from config_guard.settings_invariants import check_settings_invariants

GOOD: dict[str, Any] = {
    "permissions": {
        "allow": ["Bash(cat:*)", "WebSearch"],
        "deny": ["NotebookRead"],
        "ask": ["Bash(git commit:*)"],
    },
    "extraKnownMarketplaces": {
        "superpowers-marketplace": {
            "source": {"source": "github", "repo": "obra/superpowers-marketplace"}
        }
    },
    "enabledPlugins": {
        "feature-dev@claude-plugins-official": True,
        "superpowers@superpowers-marketplace": True,
    },
}


class TestGood:
    def test_clean_settings_has_no_findings(self) -> None:
        assert check_settings_invariants(GOOD) == []


class TestInvariantViolations:
    def test_forbidden_key_enabled_mcp_servers(self) -> None:
        settings = {**GOOD, "enabledMcpjsonServers": ["chrome-devtools"]}
        findings = check_settings_invariants(settings)
        assert any(f.detail == "enabledMcpjsonServers" for f in findings)

    def test_user_absolute_path(self) -> None:
        settings = {
            **GOOD,
            "extraKnownMarketplaces": {
                "hidari-plugins": {"source": {"source": "directory", "path": "/Users/example/x"}}
            },
        }
        findings = check_settings_invariants(settings)
        # ユーザーパス かつ directory marketplace の双方が検出される
        assert any("絶対パス" in f.message for f in findings)
        assert any("directory" in f.message for f in findings)

    def test_non_public_marketplace_plugin(self) -> None:
        settings = {
            **GOOD,
            "enabledPlugins": {"security@hidari-plugins": True},
        }
        findings = check_settings_invariants(settings)
        assert any("hidari-plugins" in f.detail for f in findings)

    def test_invalid_permission_tool_name(self) -> None:
        settings = {**GOOD, "permissions": {"deny": ["NoteboolEdit"]}}
        findings = check_settings_invariants(settings)
        assert any(f.detail == "NoteboolEdit" for f in findings)
