"""apm_gitignore の仕様テスト。

deployed_files パーサ(pure)と、gitignore 網羅検査(実 git repo)を検証する。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from config_guard.apm_gitignore import (
    LOCKFILE_PATH,
    check_apm_deployed_files_ignored,
    parse_deployed_files,
)
from config_guard.git_run import isolated_git_env

# deployed_files を 2 件持ち、hashes ブロックへ漏れないことを試す最小 lockfile
SAMPLE_LOCKFILE = """lockfile_version: '1'
apm_version: 0.23.1
dependencies:
- repo_url: mizchi/skills
  virtual_path: testing/playwright-cli
  package_type: claude_skill
  deployed_files:
  - .claude/skills/playwright-cli
  - .claude/skills/playwright-cli/README.md
  - .claude/skills/playwright-cli/SKILL.md
  deployed_file_hashes:
    .claude/skills/playwright-cli/README.md: sha256:aaa
    .claude/skills/playwright-cli/SKILL.md: sha256:bbb
  content_hash: sha256:ccc
- repo_url: mizchi/skills
  virtual_path: testing/playwright-test
  package_type: claude_skill
  deployed_files:
  - .claude/skills/playwright-test
  - .claude/skills/playwright-test/SKILL.md
  deployed_file_hashes:
    .claude/skills/playwright-test/SKILL.md: sha256:ddd
  content_hash: sha256:eee
"""


def test_parse_deployed_files_extracts_exact_paths() -> None:
    assert parse_deployed_files(SAMPLE_LOCKFILE) == [
        ".claude/skills/playwright-cli",
        ".claude/skills/playwright-cli/README.md",
        ".claude/skills/playwright-cli/SKILL.md",
        ".claude/skills/playwright-test",
        ".claude/skills/playwright-test/SKILL.md",
    ]


def test_parse_deployed_files_does_not_leak_into_hashes() -> None:
    # sha256 を含む deployed_file_hashes / content_hash 行は 1 つも混入しない
    for path in parse_deployed_files(SAMPLE_LOCKFILE):
        assert "sha256" not in path


def test_parse_deployed_files_empty_when_no_block() -> None:
    assert parse_deployed_files("dependencies: []\napm_version: 0.23.1\n") == []


def _init_repo(repo: Path) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "init", "-q"],
        check=True,
        capture_output=True,
        env=isolated_git_env(),
    )


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_check_passes_when_all_deployed_files_ignored(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write(tmp_path, LOCKFILE_PATH, SAMPLE_LOCKFILE)
    _write(
        tmp_path,
        "home/.gitignore",
        ".claude/skills/playwright-cli/\n.claude/skills/playwright-test/\n",
    )

    assert check_apm_deployed_files_ignored(str(tmp_path)) == []


def test_check_flags_unignored_deployed_file(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write(tmp_path, LOCKFILE_PATH, SAMPLE_LOCKFILE)
    # playwright-test の追記漏れを再現(playwright-cli だけ ignore)
    _write(tmp_path, "home/.gitignore", ".claude/skills/playwright-cli/\n")

    findings = check_apm_deployed_files_ignored(str(tmp_path))

    detected = {f.detail for f in findings}
    # dir placeholder は検査対象外なので、leaf の SKILL.md だけが未 ignore として検出される
    assert detected == {"home/.claude/skills/playwright-test/SKILL.md"}
    # playwright-cli 側は ignore 済みなので検出されない(negative)
    assert not any("playwright-cli" in d for d in detected)
    assert all(f.source == LOCKFILE_PATH for f in findings)


def test_check_empty_when_no_lockfile(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    assert check_apm_deployed_files_ignored(str(tmp_path)) == []


def test_check_raises_on_git_error(tmp_path: Path) -> None:
    # git repo でないディレクトリでは git check-ignore が 128 を返す。追記漏れ(1)と
    # git エラー(128)を取り違えず、明示的に失敗することを検証する(git init しない)。
    _write(tmp_path, LOCKFILE_PATH, SAMPLE_LOCKFILE)

    try:
        check_apm_deployed_files_ignored(str(tmp_path))
    except RuntimeError:
        pass
    else:
        raise AssertionError("git エラー時は RuntimeError が送出されるべき")
