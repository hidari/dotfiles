"""cli.scan の統合テスト。実 git リポジトリで検証する。"""

from __future__ import annotations

import json
from pathlib import Path

from config_guard.cli import scan
from tests.conftest import init_repo, run_git, write_file

GOOD_SETTINGS = {
    "permissions": {"allow": ["Bash(cat:*)"], "deny": ["NotebookRead"], "ask": []},
    "enabledPlugins": {"feature-dev@claude-plugins-official": True},
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


def test_broken_markdown_link_is_detected(tmp_path: Path) -> None:
    # リンク検査が scan に配線されていること
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, GOOD_SETTINGS)
    write_file(repo, "docs/a/index.md", "[先](../b/missing.md)\n")
    run_git(repo, "add", "-A")

    findings = scan(str(repo))

    assert any(f.detail == "../b/missing.md" for f in findings)
