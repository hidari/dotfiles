"""追跡下の docs/ 直下が規約のサブディレクトリだけで構成されているか検査する。

PUBLIC リポジトリへの private な固有名詞の流入は、規約に無いディレクトリ (セッションの
メモや受け箱の add -f など) へ着地する形で起きた。名前そのものは禁止語リストの hook が
見るが、リストは開発機にしか無く CI では走らない。こちらは名前を知らずに置き場だけを
見るので CI でも走り、--no-verify で入った分の backstop になる。

母集団は追跡ファイルだけ。コミットされ得るのは index に入ったものだけで、ignore された
受け箱が手元に在っても赤くしない。
"""

from __future__ import annotations

from config_guard.git_run import run_git_checked
from config_guard.models import Finding

# docs/ 直下に置いてよいサブディレクトリ。足すときは置き場の規約ごと決める
ALLOWED_DOCS_DIRS: frozenset[str] = frozenset({"issues", "known-issues", "superpowers"})


def docs_layout_reason(path: str) -> str | None:
    """repo 相対パスが docs/ の規約に反するなら理由を返す。"""
    parts = path.split("/")
    if parts[0] != "docs":
        return None
    if len(parts) == 2:
        return "docs/ 直下にファイルを置かない"
    if parts[1] not in ALLOWED_DOCS_DIRS:
        return f"docs/{parts[1]}/ は規約のサブディレクトリではない"
    return None


def check_docs_layout(repo_root: str) -> list[Finding]:
    """規約外の置き場にある追跡ファイルを検査する。

    NUL 区切りで受ける。既定の出力は非 ASCII パスをクォートするので、先頭要素が
    "docs ではない" と読まれて黙って落ちる。
    """
    stdout = run_git_checked(repo_root, "ls-files", "-z", "--", "docs")
    findings: list[Finding] = []
    for path in (p for p in stdout.split("\0") if p):
        reason = docs_layout_reason(path)
        if reason is not None:
            findings.append(Finding(path, path.split("/")[1], reason))
    return findings
