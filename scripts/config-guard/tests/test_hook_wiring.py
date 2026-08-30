"""hook_wiring の仕様。

使い捨てリポジトリを作り、実行ビットと settings dict の組み合わせを変えて検査する。
本体リポジトリを対象にすると、実装の変更ではなく本体の状態でテストの意味が変わる。
settings.json の読み方 (committed か working tree か) は呼び出し側の責務なので、
ここでは settings を dict で直接渡す。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from config_guard.hook_wiring import check_hook_mode_shebang, check_hook_wiring
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


def _repo(tmp_path: Path, hooks: dict[str, int]) -> Path:
    """フックを持つ使い捨てリポジトリを作って commit する。

    hooks は「ファイル名 -> mode」。mode は 0o755 か 0o644 を渡す。
    check_hook_wiring は _executable_hooks で git ls-files を使うため、
    フック本体の commit 自体は settings の受け渡し方を変えても引き続き要る。
    """
    root = tmp_path / "repo"
    root.mkdir()
    init_repo(root)
    for name, mode in hooks.items():
        path = write_file(root, f"home/.claude/hooks/{name}", "#!/usr/bin/env python3\n")
        path.chmod(mode)
    run_git(root, "add", "-A")
    run_git(root, "commit", "-qm", "init")
    return root


def test_配線されたフックは孤児にしない(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"a.py": 0o755})
    assert check_hook_wiring(str(root), _WIRED) == []


def test_どこにも現れないフックを孤児として検出する(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"a.py": 0o755, "orphan.py": 0o755})
    findings = check_hook_wiring(str(root), _WIRED)
    assert [f.detail for f in findings] == ["orphan.py"]


def test_実行ビットの無いファイルは共有モジュールとして除く(tmp_path: Path) -> None:
    """共有モジュールは配線されないのが正しい。実行ビットが本体と分けている。"""
    root = _repo(tmp_path, {"a.py": 0o755, "shared.py": 0o644})
    assert check_hook_wiring(str(root), _WIRED) == []


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
    root = _repo(tmp_path, {"a.py": 0o755})
    assert check_hook_wiring(str(root), settings) == []


def _repo_with_content(tmp_path: Path, files: dict[str, tuple[str, int]]) -> Path:
    """content と mode の組でフックを持つ使い捨てリポジトリを作って commit する。

    `_repo` は shebang を常に足すので shebang 無しのケースを表現できない。
    check_hook_mode_shebang の検証には両方の組み合わせが要る。
    """
    root = tmp_path / "repo"
    root.mkdir()
    init_repo(root)
    for name, (content, mode) in files.items():
        path = write_file(root, f"home/.claude/hooks/{name}", content)
        path.chmod(mode)
    run_git(root, "add", "-A")
    run_git(root, "commit", "-qm", "init")
    return root


def test_shebang_があり実行ビットが無ければ検出する(tmp_path: Path) -> None:
    """実行ビットを落とすフック本体を、孤児検出の母集団から漏れても shebang 側で拾う (M14)。"""
    root = _repo_with_content(tmp_path, {"guard-health.py": ("#!/usr/bin/env python3\n", 0o644)})
    findings = check_hook_mode_shebang(str(root))
    assert [f.detail for f in findings] == ["home/.claude/hooks/guard-health.py"]
    assert "shebang があるのに実行ビットがありません" in findings[0].message


def test_実行ビットがあり_shebang_が無ければ検出する(tmp_path: Path) -> None:
    """共有モジュールに誤って実行ビットが付いた形も逆向きに検出する。"""
    root = _repo_with_content(tmp_path, {"leaf.py": ('"""docstring"""\n', 0o755)})
    findings = check_hook_mode_shebang(str(root))
    assert [f.detail for f in findings] == ["home/.claude/hooks/leaf.py"]
    assert "実行ビットがあるのに shebang がありません" in findings[0].message


def test_shebang_と実行ビットが一致していれば検出しない(tmp_path: Path) -> None:
    root = _repo_with_content(
        tmp_path,
        {
            "a.py": ("#!/usr/bin/env python3\n", 0o755),
            "shared.py": ('"""docstring"""\n', 0o644),
        },
    )
    assert check_hook_mode_shebang(str(root)) == []
