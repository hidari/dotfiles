"""フック本体が settings.json のどこかへ配線されているかの検査。

必須であることの宣言は settings_invariants が名前で持つ。こちらは逆向きで、
「本体があるのにどこにも現れない」を導出で拾う。導出でよいのは、ファイルが消えても
要求が消えないためである (要求は名前で宣言する層が別に持っている)。

フック本体と共有モジュールの区別に実行ビットを使う。追跡下の mode は本体が 100755、
共有モジュールが 100644 で既に分かれており、新しい規約を作らずに済む。ただし
`_executable_hooks` は 100755 だけを母集団に入れるので、実行ビットを落とすとフック
本体が孤児検出の母集団から静かに外れる。`check_hook_mode_shebang` が shebang の
有無という独立の手掛かりで mode との対応を双方向に検査し、その穴を塞ぐ。

settings.json 全体を走査して、どこかの文字列にフック本体の basename が現れるかで見る。
イベントも matcher も問わない。どのイベントへ配線するのが正しいかは名前で宣言する層の
担当で、ここは「どこにも無い」だけを見る。

settings は呼び出し側が渡す。committed scope で読むか working tree で読むかを
このモジュールが決めると、他の検査 (settings_invariants 等) が read_committed_settings
経由で守っている「working tree の書き換えを検査対象にしない」規約から外れうる。
引数で受け取れば、settings.json の読み方はここで選べなくなる。
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from config_guard.extractors import iter_strings
from config_guard.git_run import isolated_git_env, run_git_checked
from config_guard.models import Finding

_SRC = "home/.claude/hooks"

# フック本体の追跡下 mode。共有モジュールは 100644 なのでここに一致しない。
_EXECUTABLE_MODE = "100755"


def _hook_entries(repo_root: str) -> list[tuple[str, str, str]]:
    """追跡下の home/.claude/hooks 配下を (mode, blob_sha, path) の一覧で返す。

    NUL 区切りで受けるのは、改行区切りだと非 ASCII のパスがクォートされて件数が
    静かに落ちるためである (git ls-files の既定の挙動)。孤児検出 (mode だけを見る)
    と mode/shebang 対応検査 (blob 内容も見る) の両方がこの 1 回の呼び出しを共有する。
    """
    stdout = run_git_checked(repo_root, "ls-files", "-s", "-z", _SRC)
    entries: list[tuple[str, str, str]] = []
    for record in stdout.split("\0"):
        if not record or "\t" not in record:
            continue
        meta, path = record.split("\t", 1)
        fields = meta.split()
        if len(fields) < 2:
            continue
        entries.append((fields[0], fields[1], path))
    return entries


def _executable_hooks(repo_root: str) -> list[str]:
    """追跡下のフック本体の basename を返す。"""
    return [
        Path(path).name
        for mode, _blob, path in _hook_entries(repo_root)
        if mode == _EXECUTABLE_MODE
    ]


def _blob_first_lines(repo_root: str, blob_shas: list[str]) -> dict[str, bytes]:
    """指定した blob の先頭 1 行を bytes で返す (改行を含まない)。

    `git cat-file --batch` へ SHA をまとめて流すことで、ファイル数ぶんの `git show`
    呼び出しを避ける (working tree ではなく index から読む、というこのモジュールの
    規約とも整合する。git_source.py の `git show :path` と同じ index 読みの形)。
    テキストモードだと改行変換で header の size (バイト数) と実際の文字数がずれうる
    ため、bytes のまま扱う。
    """
    if not blob_shas:
        return {}
    proc = subprocess.run(
        ["git", "-C", repo_root, "cat-file", "--batch"],
        input="\n".join(blob_shas).encode() + b"\n",
        capture_output=True,
        check=False,
        env=isolated_git_env(),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git cat-file が失敗しました (exit {proc.returncode})")
    out = proc.stdout
    first_lines: dict[str, bytes] = {}
    pos = 0
    while pos < len(out):
        header_end = out.index(b"\n", pos)
        header = out[pos:header_end].split(b" ")
        if len(header) != 3:
            raise RuntimeError(f"git cat-file の出力を解釈できません: {header!r}")
        sha = header[0].decode("ascii")
        size = int(header[2])
        content_start = header_end + 1
        content = out[content_start : content_start + size]
        first_lines[sha] = content.split(b"\n", 1)[0]
        pos = content_start + size + 1  # 内容末尾の LF 区切りを飛ばす
    return first_lines


def check_hook_mode_shebang(repo_root: str) -> list[Finding]:
    """追跡下のフックファイルで shebang の有無と実行ビットが食い違うものを検出する。

    `_executable_hooks` は mode 100755 だけを母集団に入れるので、実行ビットを落とすと
    フック本体が孤児検出の母集団から静かに外れ、検査は 0 件を返す (変異注入で確認済み)。
    shebang の有無という独立の手掛かりで mode との対応を双方向に検査すれば、mode だけを
    操作する変異を検出できる。フック本体は shebang を持ち共有モジュールは持たない、
    という性質は追跡下の全ファイルで既に成立しているもので、新しい規約は作らない。
    """
    entries = _hook_entries(repo_root)
    blob_shas = sorted({blob for _mode, blob, _path in entries})
    first_lines = _blob_first_lines(repo_root, blob_shas)
    findings: list[Finding] = []
    for mode, blob, path in entries:
        has_shebang = first_lines.get(blob, b"").startswith(b"#!")
        is_executable = mode == _EXECUTABLE_MODE
        if has_shebang and not is_executable:
            findings.append(
                Finding(_SRC, path, f"shebang があるのに実行ビットがありません: {path}")
            )
        elif is_executable and not has_shebang:
            findings.append(
                Finding(_SRC, path, f"実行ビットがあるのに shebang がありません: {path}")
            )
    return findings


def check_hook_wiring(repo_root: str, settings: dict[str, Any]) -> list[Finding]:
    """フック本体で settings に一度も現れないものを Finding で返す。

    settings は呼び出し側が読んだものをそのまま渡す (モジュール docstring 参照)。
    settings.json を読めない場合の扱いは呼び出し側の責務であり、ここでは扱わない。
    """
    wired = iter_strings(settings)
    findings: list[Finding] = []
    for name in sorted(_executable_hooks(repo_root)):
        if not any(name in text for text in wired):
            findings.append(
                Finding(
                    _SRC, name, f"フック本体が settings.json のどこにも配線されていません: {name}"
                )
            )
    return findings
