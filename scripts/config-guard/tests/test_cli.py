"""cli.scan の統合テスト。実 git リポジトリで検証する。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from config_guard.cli import scan

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


def _run(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _make_repo(
    tmp_path: Path, skill_name: str, skill_body: str, settings: dict[str, object]
) -> Path:
    repo = tmp_path
    _run(repo, "init", "-q")
    _run(repo, "config", "user.email", "t@example.com")
    _run(repo, "config", "user.name", "t")
    settings_path = repo / "home/.claude/settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings), encoding="utf-8")
    skill_path = repo / f"home/.claude/skills/{skill_name}/SKILL.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(skill_body, encoding="utf-8")
    _run(repo, "add", "-A")
    _run(repo, "commit", "-q", "-m", "init")
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
