"""cli.scan の統合テスト。実 git リポジトリで検証する。"""

from __future__ import annotations

import json
from pathlib import Path

from config_guard.cli import scan
from tests.conftest import (
    APM_GUARD_HOOK_COMMAND,
    TIRITH_HOOK_COMMAND,
    hook_group,
    init_repo,
    pretooluse,
    run_git,
    write_file,
)

GOOD_SETTINGS = {
    "permissions": {"allow": ["Bash(cat:*)"], "deny": ["NotebookRead"], "ask": []},
    "enabledPlugins": {"feature-dev@claude-plugins-official": True},
    # 必須フックの配線。欠けていると他の検査の統合テストにも findings が混ざる
    "hooks": pretooluse(hook_group(TIRITH_HOOK_COMMAND, APM_GUARD_HOOK_COMMAND)),
    # nested traversal の除外。フックの配線と同じ理由でここへ置く
    "claudeMdExcludes": ["**/home/.claude/CLAUDE.md"],
}

GOOD_SKILL = """\
---
name: good
allowed-tools:
  - Read
  - Bash(git *)
---
本文
"""

BAD_SKILL = """\
---
name: bad
allowed-tools:
  - Git
  - mcp__chrome-devtools__navigate_page
---
本文
"""


def _make_repo(
    tmp_path: Path, skill_name: str, skill_body: str, settings: dict[str, object]
) -> Path:
    repo = tmp_path
    init_repo(repo)
    write_file(repo, "home/.claude/settings.json", json.dumps(settings))
    write_file(repo, f"home/.claude/skills/{skill_name}/SKILL.md", skill_body)
    run_git(repo, "add", "-A")
    run_git(repo, "commit", "-q", "-m", "init")
    return repo


def test_clean_repo_has_no_findings(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, GOOD_SETTINGS)
    assert scan(str(repo)) == []


def test_bad_skill_is_detected(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, "bad", BAD_SKILL, GOOD_SETTINGS)
    findings = scan(str(repo))
    details = {f.detail for f in findings}
    assert "Git" in details
    assert "mcp__chrome-devtools__navigate_page" in details


def test_bad_settings_is_detected(tmp_path: Path) -> None:
    bad_settings = {**GOOD_SETTINGS, "enabledMcpjsonServers": ["x"]}
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, bad_settings)
    findings = scan(str(repo))
    assert any(f.detail == "enabledMcpjsonServers" for f in findings)


def test_bad_herdr_keys_is_detected(tmp_path: Path) -> None:
    # herdr の keybinding 検査が scan に配線されていること (next に前方向キー)
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, GOOD_SETTINGS)
    write_file(repo, "home/.config/herdr/config.toml", '[keys]\nnext_workspace = "ctrl+alt+["\n')

    findings = scan(str(repo))

    assert any(f.detail == "next_workspace = ctrl+alt+[" for f in findings)


def test_hidden_index_flag_is_detected(tmp_path: Path) -> None:
    # index bit 検査が scan に配線されていること。実装だけ足して配線を忘れると
    # 単体テストは緑のまま検査が一度も走らない
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, GOOD_SETTINGS)
    run_git(repo, "update-index", "--skip-worktree", "home/.claude/settings.json")

    findings = scan(str(repo))

    assert [(f.source, f.detail) for f in findings] == [("home/.claude/settings.json", "S")]


def test_apm_pin_mismatch_is_detected(tmp_path: Path) -> None:
    # apm pin 検査が scan に配線されていること。実装だけ足して配線を忘れると
    # 単体テストは緑のまま検査が一度も走らない
    # ref は 40 桁の SHA にする。短縮形だと手前の SHA 検査に捕まり、
    # 群の一致検査へ届かないまま別の理由で赤くなる
    a = "a" * 40
    b = "b" * 40
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, GOOD_SETTINGS)
    write_file(
        repo,
        "home/apm.yml",
        f"name: t\ndependencies:\n  apm:\n  - owner/repo/a#{a}\n  - owner/repo/b#{b}\n",
    )

    findings = scan(str(repo))

    assert any(f.detail == f"owner/repo: {a} (1), {b} (1)" for f in findings)


def test_broken_markdown_link_is_detected(tmp_path: Path) -> None:
    # リンク検査が scan に配線されていること
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, GOOD_SETTINGS)
    write_file(repo, "docs/a/index.md", "[先](../b/missing.md)\n")
    run_git(repo, "add", "-A")

    findings = scan(str(repo))

    assert any(f.detail == "../b/missing.md" for f in findings)
