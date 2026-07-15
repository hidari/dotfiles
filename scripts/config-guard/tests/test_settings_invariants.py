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
        assert [f.detail for f in findings] == ["enabledMcpjsonServers"]

    def test_user_absolute_path(self) -> None:
        settings = {
            **GOOD,
            "extraKnownMarketplaces": {
                "hidari-plugins": {"source": {"source": "directory", "path": "/Users/example/x"}}
            },
        }
        findings = check_settings_invariants(settings)
        # ユーザーパス と directory marketplace の 2 件だけが検出される
        assert {f.detail for f in findings} == {"/Users/example/x", "hidari-plugins"}
        assert len(findings) == 2

    def test_non_public_marketplace_plugin(self) -> None:
        settings = {
            **GOOD,
            "enabledPlugins": {"security@hidari-plugins": True},
        }
        findings = check_settings_invariants(settings)
        assert [f.detail for f in findings] == ["security@hidari-plugins"]

    def test_invalid_permission_tool_name(self) -> None:
        settings = {**GOOD, "permissions": {"deny": ["NoteboolEdit"]}}
        findings = check_settings_invariants(settings)
        assert [f.detail for f in findings] == ["NoteboolEdit"]


class TestIneffectiveFilePathRules:
    """file permission check は Read(...) のみ file access を gate する。

    Glob(...)/Grep(...) に path を書いても無視される（Claude Code 仕様）ため、
    inert な規則として検出し Read(...) への書き換えを促す。bare な Glob/Grep は
    ツール全体を gate する有効な形なので対象外。
    """

    def test_glob_path_rule_in_deny_flagged(self) -> None:
        settings = {**GOOD, "permissions": {"deny": ["Glob(.hidari/**)"]}}
        findings = check_settings_invariants(settings)
        assert [f.detail for f in findings] == ["Glob(.hidari/**)"]
        assert "Read(.hidari/**)" in findings[0].message

    def test_grep_path_rule_in_ask_flagged(self) -> None:
        settings = {**GOOD, "permissions": {"ask": ["Grep(secret/**)"]}}
        findings = check_settings_invariants(settings)
        assert [f.detail for f in findings] == ["Grep(secret/**)"]
        assert "Read(secret/**)" in findings[0].message

    def test_read_path_rule_not_flagged(self) -> None:
        # Read(...) は canonical な形。誤検知しないこと（negative case）
        settings = {**GOOD, "permissions": {"deny": ["Read(.hidari/**)"]}}
        assert check_settings_invariants(settings) == []

    def test_bare_glob_and_grep_not_flagged(self) -> None:
        # bare な Glob/Grep はツール全体の gate として有効なので対象外
        settings = {**GOOD, "permissions": {"deny": ["Glob", "Grep"]}}
        assert check_settings_invariants(settings) == []
