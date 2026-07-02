"""tool_refs.validate_tool_token の仕様テスト。"""

from __future__ import annotations

from config_guard.tool_refs import validate_tool_token


class TestValidTokens:
    def test_builtin_bare(self) -> None:
        assert validate_tool_token("Read") is None

    def test_builtin_all_caps(self) -> None:
        # LS のような全大文字の実在ツール名も shape で通す
        assert validate_tool_token("LS") is None

    def test_builtin_with_specifier(self) -> None:
        assert validate_tool_token("Bash(git *)") is None

    def test_builtin_with_glob_specifier(self) -> None:
        assert validate_tool_token("Read(.hidari/**)") is None

    def test_mcp_plugin_form(self) -> None:
        token = "mcp__plugin_chrome-devtools-mcp_chrome-devtools__take_snapshot"
        assert validate_tool_token(token) is None

    def test_mcp_non_plugin_form(self) -> None:
        assert validate_tool_token("mcp__claude_ai_Gmail__authenticate") is None

    def test_notebook_read_is_valid(self) -> None:
        # NotebookRead は実在ツール名（allowlist 照合しないため shape で通る）
        assert validate_tool_token("NotebookRead") is None


class TestInvalidTokens:
    def test_legacy_un_prefixed_mcp(self) -> None:
        reason = validate_tool_token("mcp__chrome-devtools__navigate_page")
        assert reason is not None
        assert "legacy" in reason

    def test_legacy_claude_in_chrome(self) -> None:
        assert validate_tool_token("mcp__claude-in-chrome__open") is not None

    def test_known_bad_git(self) -> None:
        reason = validate_tool_token("Git")
        assert reason is not None
        assert "実在しない" in reason

    def test_known_typo_notebool_edit(self) -> None:
        reason = validate_tool_token("NoteboolEdit")
        assert reason is not None
        assert "実在しない" in reason

    def test_empty(self) -> None:
        assert validate_tool_token("") is not None

    def test_lowercase_garbage(self) -> None:
        reason = validate_tool_token("git")
        assert reason is not None
        assert "不正な形" in reason
