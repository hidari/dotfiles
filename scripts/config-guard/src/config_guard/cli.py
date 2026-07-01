"""リポジトリをスキャンして構造逸脱を検出する。

stale なツール名参照 / committed settings.json の不変条件 / apm.lock.yaml の
deployed_files が gitignore されているか(追記漏れ)を検査する。
"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

from config_guard.apm_gitignore import check_apm_deployed_files_ignored
from config_guard.extractors import extract_skill_tokens
from config_guard.git_source import read_committed_settings
from config_guard.models import Finding
from config_guard.settings_invariants import check_settings_invariants
from config_guard.tool_refs import validate_tool_token

SKILLS_GLOB = "home/.claude/skills/*/SKILL.md"


def scan(repo_root: str) -> list[Finding]:
    """skills の allowed-tools と committed settings.json を検査する。"""
    root = Path(repo_root).resolve()
    findings: list[Finding] = []

    # skills の allowed-tools
    for skill_path in sorted(glob.glob(str(root / SKILLS_GLOB))):
        text = Path(skill_path).read_text(encoding="utf-8")
        rel = str(Path(skill_path).relative_to(root))
        for token in extract_skill_tokens(text):
            reason = validate_tool_token(token)
            if reason is not None:
                findings.append(Finding(rel, token, reason))

    # committed settings.json の不変条件（permissions のツール名検証を含む）
    settings = read_committed_settings(str(root))
    findings.extend(check_settings_invariants(settings))

    # apm.lock.yaml の deployed_files が全て gitignore されているか（追記漏れ検出）
    findings.extend(check_apm_deployed_files_ignored(str(root)))

    return findings


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    repo_root = args[0] if args else "."
    findings = scan(repo_root)
    if not findings:
        print("config-guard: 問題は検出されませんでした")
        return 0
    for finding in findings:
        print(f"config-guard: {finding.source}: {finding.message} [{finding.detail}]")
    print(f"config-guard: {len(findings)} 件の問題を検出しました")
    return 1
