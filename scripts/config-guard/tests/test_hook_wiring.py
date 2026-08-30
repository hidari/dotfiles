"""hook_wiring の仕様。

使い捨てリポジトリを作り、実行ビットと settings.json の組み合わせを変えて検査する。
本体リポジトリを対象にすると、実装の変更ではなく本体の状態でテストの意味が変わる。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config_guard.hook_wiring import check_hook_wiring
from tests.conftest import init_repo, run_git, write_file

_WIRED: dict[str, Any] = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": 'python3 "$HOME/.claude/hooks/a.py"'}],
            }
        ]
    }
}


def _repo(tmp_path: Path, hooks: dict[str, int], settings: dict[str, Any]) -> Path:
    """フックと settings.json を持つ使い捨てリポジトリを作って commit する。

    hooks は「ファイル名 -> mode」。mode は 0o755 か 0o644 を渡す。
    """
    root = tmp_path / "repo"
    root.mkdir()
    init_repo(root)
    write_file(root, "home/.claude/settings.json", json.dumps(settings, ensure_ascii=False))
    for name, mode in hooks.items():
        path = write_file(root, f"home/.claude/hooks/{name}", "#!/usr/bin/env python3\n")
        path.chmod(mode)
    run_git(root, "add", "-A")
    run_git(root, "commit", "-qm", "init")
    return root


def test_配線されたフックは孤児にしない(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"a.py": 0o755}, _WIRED)
    assert check_hook_wiring(str(root)) == []


def test_どこにも現れないフックを孤児として検出する(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"a.py": 0o755, "orphan.py": 0o755}, _WIRED)
    findings = check_hook_wiring(str(root))
    assert [f.detail for f in findings] == ["orphan.py"]


def test_実行ビットの無いファイルは共有モジュールとして除く(tmp_path: Path) -> None:
    """共有モジュールは配線されないのが正しい。実行ビットが本体と分けている。"""
    root = _repo(tmp_path, {"a.py": 0o755, "shared.py": 0o644}, _WIRED)
    assert check_hook_wiring(str(root)) == []


def test_どのイベントに現れてもよい(tmp_path: Path) -> None:
    """どのイベントへ配線するのが正しいかは名前で宣言する層の担当で、ここは所在だけを見る。"""
    settings: dict[str, Any] = {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "*",
                    "hooks": [{"type": "command", "command": 'python3 "$HOME/.claude/hooks/a.py"'}],
                }
            ]
        }
    }
    root = _repo(tmp_path, {"a.py": 0o755}, settings)
    assert check_hook_wiring(str(root)) == []


def test_settings_json_が読めなければ検査できないと告げる(tmp_path: Path) -> None:
    """読めないことを「孤児なし」へ潰さない。"""
    root = _repo(tmp_path, {"a.py": 0o755}, _WIRED)
    (root / "home" / ".claude" / "settings.json").write_text("{ broken", encoding="utf-8")
    findings = check_hook_wiring(str(root))
    assert len(findings) == 1
    assert "settings.json" in findings[0].detail
