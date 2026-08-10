"""追跡ファイルに変更を隠す index の bit が立っていないか検査する。

skip-worktree と assume-unchanged は working tree の変更を git から隠す。
`home/.claude/settings.json` はこの skip-worktree で live と committed を分けて運用して
いたが、分ける理由 (ローカル絶対パスを持つ directory source の marketplace 宣言と、そこから
来る plugin エントリ) が apm 配布への移行で消えたため解除した。bit が復活すると、live 側の
変更が git diff にも CI にも現れないまま乖離する形へ戻る。

bit は index が持つローカル固有の状態なので、clean clone の CI では常に 0 件になる。
この検査が働くのは pre-commit から走るときである。CI の 0 件は健全の証拠ではなく、そもそも
立ちようがないためであることに注意する。
"""

from __future__ import annotations

from config_guard.git_run import run_git_checked
from config_guard.models import Finding

_HIDDEN_EFFECT = "(working tree の変更が git から見えなくなり live と committed が静かに乖離します)"


def hidden_flag_reason(tag: str) -> str | None:
    """`git ls-files -v` の状態タグが変更を隠す bit を示すなら理由を返す。

    skip-worktree だけが専用タグ S を持ち、assume-unchanged は通常タグを小文字にした形で
    表れる (H -> h)。S だけを見ると assume-unchanged が素通りする。
    """
    if tag == "S":
        return f"skip-worktree が立っています {_HIDDEN_EFFECT}"
    if tag.islower():
        return f"assume-unchanged が立っています {_HIDDEN_EFFECT}"
    return None


def tracked_index_entries(repo_root: str) -> list[tuple[str, str]]:
    """追跡ファイルを (状態タグ, repo 相対パス) で列挙する。

    NUL 区切りで受ける。空白や日本語を含むパスを行やスペースで切ると分断され、落ちた分は
    「エラー」ではなく「短い正常な結果」として返るため出力からは気づけない。`-z` は
    パスのクォートも外すのでデコードが要らない。
    """
    stdout = run_git_checked(repo_root, "ls-files", "-v", "-z")
    # 各エントリは "<タグ><空白><パス>" の形
    return [(entry[0], entry[2:]) for entry in stdout.split("\0") if entry]


def check_index_flags(repo_root: str) -> list[Finding]:
    """変更を隠す bit が立った追跡ファイルを検査する。"""
    findings: list[Finding] = []
    for tag, path in tracked_index_entries(repo_root):
        reason = hidden_flag_reason(tag)
        if reason is not None:
            findings.append(Finding(path, tag, reason))
    return findings
