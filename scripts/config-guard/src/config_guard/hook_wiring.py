"""フック本体が settings.json のどこかへ配線されているかの検査。

必須であることの宣言は settings_invariants が名前で持つ。こちらは逆向きで、
「本体があるのにどこにも現れない」を導出で拾う。導出でよいのは、ファイルが消えても
要求が消えないためである (要求は名前で宣言する層が別に持っている)。

フック本体と共有モジュールの区別に実行ビットを使う。追跡下の mode は本体が 100755、
共有モジュールが 100644 で既に分かれており、新しい規約を作らずに済む。実行ビットを
落とすと検出から外れるので、その形は変異注入で確認する。

配線されているかはコマンド文字列に basename が現れるかで見る。イベントも matcher も
問わない。どのイベントへ配線するのが正しいかは名前で宣言する層の担当で、ここは
「どこにも無い」だけを見る。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config_guard.git_run import run_git_checked
from config_guard.models import Finding

_SRC = "home/.claude/hooks"

# フック本体の追跡下 mode。共有モジュールは 100644 なのでここに一致しない。
_EXECUTABLE_MODE = "100755"

# 走査する pathspec。
_HOOKS_PATHSPEC = "home/.claude/hooks"

# 配線の宣言を読む先。
_SETTINGS_PATH = "home/.claude/settings.json"


def _executable_hooks(repo_root: str) -> list[str]:
    """追跡下のフック本体の basename を返す。

    NUL 区切りで受けるのは、改行区切りだと非 ASCII のパスがクォートされて件数が
    静かに落ちるためである (git ls-files の既定の挙動)。
    """
    stdout = run_git_checked(repo_root, "ls-files", "-s", "-z", _HOOKS_PATHSPEC)
    names: list[str] = []
    for record in stdout.split("\0"):
        if not record or "\t" not in record:
            continue
        meta, path = record.split("\t", 1)
        fields = meta.split()
        if not fields or fields[0] != _EXECUTABLE_MODE:
            continue
        names.append(Path(path).name)
    return names


def _iter_strings(obj: Any) -> list[str]:
    """オブジェクトを再帰的に走査してすべての文字列を返す。"""
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            out.extend(_iter_strings(value))
    elif isinstance(obj, list):
        for value in obj:
            out.extend(_iter_strings(value))
    return out


def check_hook_wiring(repo_root: str) -> list[Finding]:
    """フック本体で settings.json に一度も現れないものを Finding で返す。"""
    settings_file = Path(repo_root) / _SETTINGS_PATH
    if not settings_file.exists():
        return []
    try:
        settings = json.loads(settings_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # 読めないことを「孤児なし」へ潰さない。settings.json の構造は
        # settings_invariants が別途見るので、ここは検査できなかったことだけを告げる。
        return [Finding(_SRC, _SETTINGS_PATH, "settings.json を読めないため配線を検査できません")]

    wired = _iter_strings(settings)
    findings: list[Finding] = []
    for name in sorted(_executable_hooks(repo_root)):
        if not any(name in text for text in wired):
            findings.append(
                Finding(
                    _SRC, name, f"フック本体が settings.json のどこにも配線されていません: {name}"
                )
            )
    return findings
