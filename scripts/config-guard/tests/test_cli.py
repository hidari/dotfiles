"""cli.scan の統合テスト。実 git リポジトリで検証する。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from config_guard.budget_ratchet import BUDGET_MODULE_PATH
from config_guard.cli import main, scan
from config_guard.instruction_budget import (
    ALWAYS_LOADED_BUDGET_BYTES,
    CLAUDE_MD_PATH,
)
from tests.conftest import (
    APM_GUARD_HOOK_COMMAND,
    GUARD_HEALTH_HOOK_COMMAND,
    TIRITH_HOOK_COMMAND,
    hook_group,
    init_repo,
    pretooluse,
    run_git,
    session_start,
    write_file,
)

GOOD_SETTINGS = {
    "permissions": {"allow": ["Bash(cat:*)"], "deny": ["NotebookRead"], "ask": []},
    "enabledPlugins": {"feature-dev@claude-plugins-official": True},
    # 必須フックの配線。欠けていると他の検査の統合テストにも findings が混ざる。
    # SessionStart の matcher は開始理由を見るので "*" を明示する
    "hooks": {
        **pretooluse(hook_group(TIRITH_HOOK_COMMAND, APM_GUARD_HOOK_COMMAND)),
        **session_start(hook_group(GUARD_HEALTH_HOOK_COMMAND, matcher="*")),
    },
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


def test_instruction_budget_is_detected(tmp_path: Path) -> None:
    # 予算検査が scan に配線されていること。実装だけ足して配線を忘れると
    # 常時ロード層が無言で膨らみ続け、検査を足した意味が消える
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, GOOD_SETTINGS)
    write_file(repo, CLAUDE_MD_PATH, "x" * (ALWAYS_LOADED_BUDGET_BYTES + 1))

    findings = scan(str(repo))

    assert any(f.source == CLAUDE_MD_PATH for f in findings)


def test_budget_ratchet_is_detected(tmp_path: Path) -> None:
    # ラチェットが scan に配線されていること。配線を忘れると予算定数が
    # 無音で上がり続け、上限が上限でなくなる状態へ戻る。
    # この repo には origin/main が無いので「baseline を取得できない」で赤くなる
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, GOOD_SETTINGS)
    write_file(repo, BUDGET_MODULE_PATH, "ALWAYS_LOADED_BUDGET_BYTES = 1\n")

    findings = scan(str(repo))

    assert any(f.source == BUDGET_MODULE_PATH for f in findings)


def test_broken_instruction_ref_is_detected(tmp_path: Path) -> None:
    # 参照検査が scan に配線されていること。配線を忘れると、指示ファイルの改名で
    # 参照が切れても誰も赤くならない状態 (探すと 0 件の沈黙) へ戻る
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, GOOD_SETTINGS)
    write_file(repo, CLAUDE_MD_PATH, "詳細は `~/.claude/references/gone.md` が持つ\n")

    findings = scan(str(repo))

    assert any(f.detail == "~/.claude/references/gone.md" for f in findings)


def test_term_without_reachable_definition_is_detected(tmp_path: Path) -> None:
    # 語の検査が scan に配線されていること。配線を忘れると、移設で語だけが常時層に
    # 残っても誰も赤くならない状態へ戻る (実装とテストは緑のまま通る)
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, GOOD_SETTINGS)
    term = "架空の造語ゼペット"
    write_file(
        repo,
        "home/.claude/rules/testing-practices.md",
        f'---\npaths: ["**/*.x"]\ndefines: ["{term}"]\n---\n\n# rule\n',
    )
    write_file(repo, CLAUDE_MD_PATH, f"{term} を使うこと\n")

    findings = scan(str(repo))

    assert any(f.detail == term for f in findings)


def test_unresolvable_related_ref_is_detected(tmp_path: Path) -> None:
    # 関連の識別子検査が scan に配線されていること。リンクを外すと markdown_links の
    # 検査は届かなくなるので、配線を忘れると参照を見る検査が 1 つも無い状態へ戻る
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, GOOD_SETTINGS)
    write_file(repo, "docs/issues/1_a/issue.md", "# a\n\n## 関連\n\n- Issue 99\n")
    run_git(repo, "add", "-A")

    findings = scan(str(repo))

    assert any(f.detail == "Issue 99" for f in findings)


def test_scan_は孤児検出を含む(tmp_path: Path) -> None:
    """cli への取り付けを外すと本体スキャンから孤児検出が消える。単体テストは通り続ける。"""
    root = tmp_path / "repo"
    root.mkdir()
    init_repo(root)
    write_file(root, "home/.claude/settings.json", "{}")
    path = write_file(root, "home/.claude/hooks/orphan.py", "#!/usr/bin/env python3\n")
    path.chmod(0o755)
    run_git(root, "add", "-A")
    run_git(root, "commit", "-qm", "init")

    findings = scan(str(root))
    assert any("orphan.py" in f.detail for f in findings)


def test_main_prints_the_budget_summary(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    # 問題が無いときも出す。移設の効果は「赤くならなかった」では見えない
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, GOOD_SETTINGS)

    main([str(repo)])

    assert "常時" in capsys.readouterr().out


def test_main_prints_the_related_refs_summary(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # 走査した節と抽出した識別子の数を出す。0 件で緑になる経路と、そもそも見ていないから
    # 0 件の経路は、どちらも「問題は検出されませんでした」で区別が付かない
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, GOOD_SETTINGS)
    write_file(repo, "docs/issues/1_a/issue.md", "# a\n\n## 関連\n\n- Issue 1\n")
    run_git(repo, "add", "-A")

    main([str(repo)])

    assert "識別子 1 件" in capsys.readouterr().out
