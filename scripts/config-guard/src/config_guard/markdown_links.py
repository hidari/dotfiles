"""追跡下の Markdown の相対リンクが実在するかを検査する。

Issue を docs/issues/closed/ へ移すたびに、その Issue を指す相対リンクと、その Issue から
出ているリンクの両方が切れる。`../10_...` と `../closed/10_...` の書き分けが両端の
open / closed 状態に依存するためで、close する側とは別のファイルへ波及編集が要り、
壊れたリンクが検出されないまま main に残った実績がある。

扱うのはインラインリンク `[text](target)` のみ。参照リンク定義・HTML タグ・自動リンクは
リポジトリに 1 件も無いため対象外とする。画像記法は同じ形なので自然にカバーされる。

既知の限界: regex による行単位の近似であり Markdown パーサではない。記法の変種
(タイトル付きリンク等)、コード領域の変種 (HTML コメント・インデントコードブロック・
複数行にまたがるインラインコード等)、解決の癖 (クエリ文字列・macOS の Path.exists の
大文字小文字非区別等) は扱わない (例は代表であって網羅ではない)。スキームを文法で
判定する代償として、第 1 セグメントにコロンを含む相対パスは URL と解釈され検査されない
(fail-open)。閉じないまま EOF に達したフェンスは以降の行を黙って skip する (こちらは
誤検出ではなく検出漏れ側)。構造的な取りこぼしのクラスを踏んだときは、regex の逐次強化
(別の取りこぼしと引き換えになりやすい) ではなく extract_link_targets の中身を
CommonMark トークナイザへ差し替える。抽出はこの関数 1 つに隔離してある。
"""

from __future__ import annotations

import re
import urllib.parse
from pathlib import Path

from config_guard.git_run import run_git_checked
from config_guard.models import Finding

# インラインリンクのターゲット部分。画像記法 ![alt](target) も同じ形なので拾える
LINK_PATTERN = re.compile(r"\]\(([^)]+)\)")

# URL スキーム。既知スキームの列挙ではなく RFC 3986 の文法で判定する。列挙だと
# 未知のスキーム (vscode: 等) が相対パス扱いになり、踏むたびにソース編集が要る
EXTERNAL_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")

# コードフェンスの開始と終了。行頭のインデントを許す
# (home/.claude/skills/windows-vm-verification/SKILL.md に 3 スペースの例が実在する)。
# バッククォート数を捕捉するのは extract_link_targets が終了判定に使うため。
# ~~~ によるフェンスは扱わない。リポジトリに 0 件で、扱わない副作用は
# 「フェンス内が検査される」だけなので実害が出た時点で足せる
FENCE_PATTERN = re.compile(r"^\s*(`{3,})")

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
    if target.startswith("//"):
        # プロトコル相対 URL。スキームを省いた外部参照でありローカルには解決できない
        return None
    if target.startswith("#"):
        return None
    # アンカーを先に切り落としてからデコードする。逆順にすると %23 (ファイル名中の #) が
    # 裸の # になり、パスの一部が誤ってアンカーとして切り落とされる
    path_part = target.split("#", 1)[0]
    return urllib.parse.unquote(path_part)


def _tracked_markdown_files(repo_root: str) -> list[str]:
    """追跡下の .md を repo 相対パスで列挙する。

    git エラー (128 = git repo でない等) を「対象なし」と誤解して検査を素通りさせない
    (「リンクが無い」との取り違え防止) は run_git_checked の RuntimeError が担う。
    """
    stdout = run_git_checked(repo_root, "ls-files", "-z", "*.md")
    return [path for path in stdout.split("\0") if path]


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
            # walk_up が ../ で表現でき、テストが tmp_path に縛られない
            shown = resolved.relative_to(root, walk_up=True)
            findings.append(Finding(rel, target, f"リンク先が存在しません (解決先 {shown})"))
    return findings
