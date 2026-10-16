"""運用指示 (PRIVATE_CLAUDE.md) を読む SessionStart コマンドの黒箱テスト。

コマンドは settings.json に直接書かれていてフック本体を持たないので、追跡下の settings.json から
文字列を取り出してそのまま実行する。写しをテストに持つと、settings.json だけ変えたときに
テストが古い文字列を検証し続ける。
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from conftest import REPO_ROOT, git_scope_free_env, make_git_repo

SETTINGS = REPO_ROOT / "home" / ".claude" / "settings.json"
PRIVATE_FILE = Path(".hidari") / "private-ops" / "PRIVATE_CLAUDE.md"


def private_ops_command() -> str:
    """SessionStart のうち PRIVATE_CLAUDE.md を読むコマンドを 1 つだけ取り出す。"""
    settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
    commands: list[str] = [
        hook["command"]
        for group in settings["hooks"]["SessionStart"]
        for hook in group["hooks"]
        if PRIVATE_FILE.name in hook.get("command", "")
    ]
    assert len(commands) == 1, commands
    return commands[0]


def run_command(cwd: Path, project_dir: Path | None) -> subprocess.CompletedProcess[str]:
    """Claude Code と同じく CLAUDE_PROJECT_DIR を与えてシェルで実行する。

    project_dir が None なら環境変数を持たない起動経路を作る。テストを走らせるシェル自身が
    Claude Code の下にいると CLAUDE_PROJECT_DIR を継承しているので、渡さないだけでは足りず
    明示的に落とす。
    """
    env = {k: v for k, v in git_scope_free_env().items() if k != "CLAUDE_PROJECT_DIR"}
    if project_dir is not None:
        env["CLAUDE_PROJECT_DIR"] = str(project_dir)
    return subprocess.run(
        ["/bin/sh", "-c", private_ops_command()],
        capture_output=True,
        text=True,
        env=env,
        cwd=cwd,
        timeout=10,
        check=False,
    )


def test_運用指示が無いリポジトリでは何も出さず成功する(tmp_path: Path) -> None:
    """.hidari を持たないリポジトリは正常な状態なので、hook の失敗として報告させない。

    読めなかったことの告知は guard-health の probe が持つ。
    """
    result = run_command(tmp_path, tmp_path)
    assert (result.returncode, result.stdout, result.stderr) == (0, "", "")


def test_運用指示があれば中身をそのまま出す(tmp_path: Path) -> None:
    private = tmp_path / PRIVATE_FILE
    private.parent.mkdir(parents=True)
    private.write_text("# 運用指示\n- 項目\n", encoding="utf-8")
    result = run_command(tmp_path, tmp_path)
    assert (result.returncode, result.stdout) == (0, "# 運用指示\n- 項目\n")


def test_環境変数が無ければgitのルートから探す(tmp_path: Path) -> None:
    """CLAUDE_PROJECT_DIR が無い起動経路でも、サブディレクトリからリポジトリの根を引く。"""
    make_git_repo(tmp_path)
    private = tmp_path / PRIVATE_FILE
    private.parent.mkdir(parents=True)
    private.write_text("根の運用指示\n", encoding="utf-8")
    sub = tmp_path / "sub"
    sub.mkdir()
    result = run_command(sub, None)
    assert (result.returncode, result.stdout) == (0, "根の運用指示\n")
