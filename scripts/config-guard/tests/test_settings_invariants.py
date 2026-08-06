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
    # 必須フックの配線。欠けていると他の検査のテストにも findings が混ざるため、
    # 「狙った検査だけが落とす」最小の差分を保つ意味でも clean な形をここに置く
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [
                    {"type": "command", "command": 'python3 "$HOME/.claude/hooks/tirith-check.py"'}
                ],
            },
            {
                "matcher": "Bash",
                "hooks": [
                    {
                        "type": "command",
                        "command": 'python3 "$HOME/.claude/hooks/apm-install-guard.py"',
                    }
                ],
            },
        ]
    },
}


def _pretooluse(*commands: str) -> dict[str, Any]:
    """PreToolUse に指定のコマンドだけを持つ hooks セクションを作る。"""
    return {
        "PreToolUse": [
            {"matcher": "Bash", "hooks": [{"type": "command", "command": c}]} for c in commands
        ]
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


class TestRequiredHooks:
    """フック本体が存在しても settings.json から外れれば何も守らない。

    取り付けそのものを不変条件として pin する。これが無いと「本体のロジックは pin されて
    いるが配線が外れても誰も気づかない」状態になり、検査機構の 3 種変異のうち
    「取り付けを外す」がテストで捕まえられなくなる。
    """

    def test_missing_apm_install_guard_is_flagged(self) -> None:
        settings = {
            **GOOD,
            "hooks": _pretooluse('python3 "$HOME/.claude/hooks/tirith-check.py"'),
        }
        findings = check_settings_invariants(settings)
        assert [f.detail for f in findings] == ["apm-install-guard.py"]

    def test_missing_tirith_check_is_flagged(self) -> None:
        settings = {
            **GOOD,
            "hooks": _pretooluse('python3 "$HOME/.claude/hooks/apm-install-guard.py"'),
        }
        findings = check_settings_invariants(settings)
        assert [f.detail for f in findings] == ["tirith-check.py"]

    def test_missing_hooks_section_flags_every_required_hook(self) -> None:
        settings = {k: v for k, v in GOOD.items() if k != "hooks"}
        findings = check_settings_invariants(settings)
        assert {f.detail for f in findings} == {"tirith-check.py", "apm-install-guard.py"}

    def test_hook_wired_to_another_event_does_not_count(self) -> None:
        # PostToolUse に置いても PreToolUse の呼び出しは守られない。
        # イベントを見ない実装だとこの pin は空虚になる
        settings = {
            **GOOD,
            "hooks": {
                **_pretooluse('python3 "$HOME/.claude/hooks/tirith-check.py"'),
                "PostToolUse": [
                    {
                        "matcher": "*",
                        "hooks": [
                            {
                                "type": "command",
                                "command": 'python3 "$HOME/.claude/hooks/apm-install-guard.py"',
                            }
                        ],
                    }
                ],
            },
        }
        findings = check_settings_invariants(settings)
        assert [f.detail for f in findings] == ["apm-install-guard.py"]

    def test_matcher_that_misses_bash_is_flagged(self) -> None:
        # 配線を外す方法はイベントの差し替えだけではない。matcher を別ツールへ変えると
        # フック本体は残ったまま Bash 呼び出しで一切起動しなくなる。実測で確認した穴
        settings = {
            **GOOD,
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": 'python3 "$HOME/.claude/hooks/tirith-check.py"',
                            }
                        ],
                    },
                    {
                        "matcher": "Read",
                        "hooks": [
                            {
                                "type": "command",
                                "command": 'python3 "$HOME/.claude/hooks/apm-install-guard.py"',
                            }
                        ],
                    },
                ]
            },
        }
        findings = check_settings_invariants(settings)
        assert [f.detail for f in findings] == ["apm-install-guard.py"]

    def test_matchers_that_cover_bash_are_accepted(self) -> None:
        # 省略・空文字・"*" は全ツールに一致する。選言も Bash を含めば守られている
        for matcher in (None, "", "*", "Bash", "Bash|Read"):
            group: dict[str, Any] = {
                "hooks": [
                    {"type": "command", "command": 'python3 "$HOME/.claude/hooks/tirith-check.py"'},
                    {
                        "type": "command",
                        "command": 'python3 "$HOME/.claude/hooks/apm-install-guard.py"',
                    },
                ]
            }
            if matcher is not None:
                group["matcher"] = matcher
            settings = {**GOOD, "hooks": {"PreToolUse": [group]}}
            assert check_settings_invariants(settings) == [], matcher

    def test_unparsable_matcher_is_flagged(self) -> None:
        # 正規表現として壊れた matcher は「一致するかもしれない」と楽観しない
        settings = {
            **GOOD,
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": 'python3 "$HOME/.claude/hooks/tirith-check.py"',
                            }
                        ],
                    },
                    {
                        "matcher": "[Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": 'python3 "$HOME/.claude/hooks/apm-install-guard.py"',
                            }
                        ],
                    },
                ]
            },
        }
        findings = check_settings_invariants(settings)
        assert [f.detail for f in findings] == ["apm-install-guard.py"]

    def test_both_hooks_in_one_group_is_accepted(self) -> None:
        # グループを分けるか 1 グループに 2 要素を置くかは配線の自由度。
        # 形ではなく「PreToolUse から呼ばれること」を仕様にする
        settings = {
            **GOOD,
            "hooks": {
                "PreToolUse": [
                    {
                        "matcher": "Bash",
                        "hooks": [
                            {
                                "type": "command",
                                "command": 'python3 "$HOME/.claude/hooks/tirith-check.py"',
                            },
                            {
                                "type": "command",
                                "command": 'python3 "$HOME/.claude/hooks/apm-install-guard.py"',
                            },
                        ],
                    }
                ]
            },
        }
        assert check_settings_invariants(settings) == []
