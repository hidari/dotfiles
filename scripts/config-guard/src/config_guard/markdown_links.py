"""追跡下の Markdown の相対リンクが実在するかを検査する。

Issue を docs/issues/closed/ へ移すたびに、その Issue を指す相対リンクと、その Issue から
出ているリンクの両方が切れる。`../10_...` と `../closed/10_...` の書き分けが両端の
open / closed 状態に依存するためで、close する側とは別のファイルへ波及編集が要る。
実際 closed/9_.../issue.md のリンクは導入時点で壊れており main 上に残っていた。

扱うのはインラインリンク `[text](target)` のみ。参照リンク定義・HTML タグ・自動リンクは
リポジトリに 1 件も無いため対象外とする。画像記法は同じ形なので自然にカバーされる。

既知の限界: この検査は regex による行単位の近似であり、Markdown パーサではない。
記法の変種 (タイトル付きリンク・山括弧や釣り合った括弧を含む destination)、コード領域の
変種 (~~~ フェンス・HTML コメント・4 スペースインデントのコードブロック・複数行にまたがる
インラインコード・同一行のバッククォートが奇数個のときのインラインコード除去の乱れ。
釣り合ったペアはリンク文字列中でも正しく扱える)、分類の穴 (EXTERNAL_SCHEME に無い
スキームやプロトコル相対 URL は相対パス扱いになり誤検出する)、解決の癖 (クエリ文字列・
ルート相対パス・macOS では Path.exists が大文字小文字を区別しないこと) などは、いずれも
扱わない (カテゴリも括弧内の例も代表であって網羅ではない)。また閉じないまま EOF に達した
フェンスは以降の行を黙って skip する (こちらは誤検出ではなく検出漏れ側)。構文としては
HTML コメントと 4 スペースインデント行が追跡下に実在するが、
これらの領域内 (フェンス除外が既に効く箇所を除く) にリンク記法を含む例は無く、
上記スキームのリンクも無いため、現状の誤検出は 0 件 (2026-08-01 に grep と scan で実測)。
近似の穴を regex の逐次強化で塞ぐのは別の取りこぼしと引き換えになりやすく (例えば
終了フェンスの「info string 不可」を行末アンカーで表現すると、開始フェンスの
info string にマッチしなくなりフェンスが一度も開かない)、限界を明文化して実害が
出た時点で個別に足す。
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
# バッククォート数をグループで捕捉し、開始フェンスの長さを覚えて終了判定に使う
# (CommonMark: 終了フェンスは開始フェンス以上の長さが要る。`` ```` `` で囲んだ
# 「markdown について書く markdown」の内側に ``` ``` `` を書く入れ子で、長さを見ずに
# トグルすると内側の 3 本で誤って閉じてしまう)。
# ~~~ によるフェンスは扱わない。リポジトリに 0 件で、扱わない副作用は
# 「フェンス内が検査される」だけなので実害が出た時点で足せる
FENCE_PATTERN = re.compile(r"^\s*(`{3,})")

# インラインコード。バッククォートのペアで囲まれた範囲
INLINE_CODE_PATTERN = re.compile(r"`[^`]*`")


def extract_link_targets(text: str) -> list[str]:
    """Markdown 本文からインラインリンクのターゲット文字列を抽出する。

    コードフェンス内の行と、インラインコードの中身は対象外。設計ドキュメントが
    リンク記法そのものを例示することがあり、それを実リンクと読むと存在しない
    パスを指摘し続けるため。
    """
    targets: list[str] = []
    fence_length = 0  # 0 はフェンス外。フェンス中は開始行のバッククォート数を保持する
    for line in text.splitlines():
        match = FENCE_PATTERN.match(line)
        if match:
            length = len(match.group(1))
            if fence_length == 0:
                # フェンス開始。以後の終了判定のため長さを記憶する
                fence_length = length
            elif length >= fence_length:
                # 終了フェンスは開始以上の長さが要る (CommonMark)。それ未満の
                # バッククォート行は入れ子の例示コードであり、フェンスは閉じない
                fence_length = 0
            continue
        if fence_length:
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
        # git ls-files は index を列挙するが read は worktree を見る。追跡下の .md を
        # rm しただけの状態 (commit 前の削除途中) では index にあって worktree に無く、
        # 読むと FileNotFoundError で落ちる。削除途中のファイル自身のリンクは検査対象と
        # して意味を持たないので skip する。そのファイルへ向かう他ファイルのリンク切れは
        # 下の実在判定が worktree を見るため通常どおり検出される
        if not source.is_file():
            continue
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
