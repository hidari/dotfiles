"""追跡下の Markdown の相対リンクが実在するかを検査する。

Issue を docs/issues/closed/ へ移すたびに、その Issue を指す相対リンクと、その Issue から
出ているリンクの両方が切れる。`../10_...` と `../closed/10_...` の書き分けが両端の
open / closed 状態に依存するためで、close する側とは別のファイルへ波及編集が要る。
実際 closed/9_.../issue.md のリンクは導入時点で壊れており main 上に残っていた。

扱うのはインラインリンク `[text](target)` のみ。参照リンク定義・HTML タグ・自動リンクは
リポジトリに 1 件も無いため対象外とする。画像記法は同じ形なので自然にカバーされる。
"""

from __future__ import annotations

import os.path
import re
import urllib.parse
from pathlib import Path

from config_guard.git_run import run_git
from config_guard.models import Finding

# インラインリンクのターゲット部分。画像記法 ![alt](target) も同じ形なので拾える
LINK_PATTERN = re.compile(r"\]\(([^)]+)\)")

# ネットワークを叩かないためスキップするスキーム
EXTERNAL_SCHEME = re.compile(r"^(?:https?|mailto|ftp):", re.IGNORECASE)

# コードフェンスの開始と終了。行頭のインデントを許す
# (home/.claude/skills/windows-vm-verification/SKILL.md に 3 スペースの例が実在する)。
# ~~~ によるフェンスは扱わない。リポジトリに 0 件で、扱わない副作用は
# 「フェンス内が検査される」だけなので実害が出た時点で足せる
FENCE_PATTERN = re.compile(r"^\s*`{3,}")

# インラインコード。バッククォートのペアで囲まれた範囲
INLINE_CODE_PATTERN = re.compile(r"`[^`]*`")


def extract_link_targets(text: str) -> list[str]:
    """Markdown 本文からインラインリンクのターゲット文字列を抽出する。

    コードフェンス内の行と、インラインコードの中身は対象外。設計ドキュメントが
    リンク記法そのものを例示することがあり、それを実リンクと読むと存在しない
    パスを指摘し続けるため。
    """
    targets: list[str] = []
    in_fence = False
    for line in text.splitlines():
        if FENCE_PATTERN.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        targets.extend(LINK_PATTERN.findall(INLINE_CODE_PATTERN.sub("", line)))
    return targets


def link_path_to_check(target: str) -> str | None:
    """検査すべきパス部分を URL デコードして返す。検査不要なら None を返す。"""
    if EXTERNAL_SCHEME.match(target):
        return None
    if target.startswith("#"):
        return None
    # アンカーを先に切り落としてからデコードする。逆順にすると %23 (ファイル名中の #) が
    # 裸の # になり、パスの一部が誤ってアンカーとして切り落とされる
    path_part = target.split("#", 1)[0]
    return urllib.parse.unquote(path_part)


def _tracked_markdown_files(repo_root: str) -> list[str]:
    """追跡下の .md を repo 相対パスで列挙する。"""
    proc = run_git(repo_root, "ls-files", "-z", "*.md")
    # 0 以外 (128 = git repo でない等) を「対象なし」と誤解して検査を素通りさせず、
    # 明示的に失敗させる (git エラーと「リンクが無い」を取り違えない)
    if proc.returncode != 0:
        raise RuntimeError(f"git ls-files が失敗しました (exit {proc.returncode})")
    return [path for path in proc.stdout.split("\0") if path]


def check_markdown_links(repo_root: str) -> list[Finding]:
    """追跡下の Markdown の相対リンクが実在するか検査する。"""
    root = Path(repo_root).resolve()
    findings: list[Finding] = []
    for rel in _tracked_markdown_files(repo_root):
        source = root / rel
        for target in extract_link_targets(source.read_text(encoding="utf-8")):
            path_part = link_path_to_check(target)
            if path_part is None:
                continue
            resolved = (source.parent / path_part).resolve()
            if resolved.exists():
                continue
            # 解決先はマシン依存の絶対パスにせず repo 相対で示す。repo 外へ出るリンクも
            # ../ で表現でき、テストが tmp_path に縛られない
            shown = os.path.relpath(resolved, root)
            findings.append(Finding(rel, target, f"リンク先が存在しません (解決先 {shown})"))
    return findings
