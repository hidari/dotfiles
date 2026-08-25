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
CommonMark トークナイザへ差し替える。

リンク記法の regex はこのモジュールが canonical で、隣が import して使う。2 本あるのは
向きが違うため。LINK_PATTERN はターゲットを取り出す側で、リンクテキストの形を問わず
広く拾う (取りこぼすと検査が素通りするので広い方へ倒す)。strip_inline_links はリンクを
丸ごと落とす側で、こちらは落としすぎない形にしてある (落としすぎると本文が消える)。
2 本を 1 本へ寄せると、どちらかがもう片方の失敗方向を引き受けることになる。
"""

from __future__ import annotations

import re
import urllib.parse
from collections.abc import Iterator
from pathlib import Path

from config_guard.git_run import tracked_files
from config_guard.models import Finding

# 追跡下の Markdown を引く pathspec。git のパススペックは既定で * が / も跨ぐ
MARKDOWN_GLOB = "*.md"

# インラインリンクのターゲット部分。画像記法 ![alt](target) も同じ形なので拾える。
# リンクテキストの形を問わないので `[a[b]](x)` のような入れ子も拾う
LINK_PATTERN = re.compile(r"\]\(([^)]+)\)")

# リンクを丸ごと落とすための形。LINK_PATTERN と違いテキスト部の形を要求するので、
# 入れ子の角括弧を持つリンクは落とし残す。落とし残しても本文にリンクが残るだけで、
# 呼び出し側は「リンクの中の語を本文の語として読む」= 報告が増える側へ倒れる
_INLINE_LINK = re.compile(r"!?\[[^\]]*\]\([^)]+\)")

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


def strip_inline_links(line: str) -> str:
    """行からインラインリンクを丸ごと落とす。

    リンクの中の語を本文の語として読ませたくない呼び出し側のためのもの。落とし残しの
    向きは `_INLINE_LINK` のコメントが持つ。
    """
    return _INLINE_LINK.sub("", line)


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


def read_tracked_texts(repo_root: str, paths: list[str]) -> Iterator[tuple[str, str]]:
    """追跡パスの本文を (repo 相対パス, 本文) で返す。削除途中のファイルは飛ばす。

    git ls-files は index を列挙するが read は worktree を見る。追跡下の .md を rm した
    だけの状態 (commit 前の削除途中) では index にあって worktree に無く、読むと
    FileNotFoundError で落ちる。削除途中のファイル自身は検査対象として意味を持たないので
    skip する。そのファイルへ向かう他ファイルのリンク切れは、実在判定が worktree を見る
    ため通常どおり検出される。

    パス一覧を引数で受けるのは、呼び出し側が同じ一覧を別の用途にも使うため。ここで
    引き直すと 1 回の検査で git ls-files が複数回走る。
    """
    root = Path(repo_root).resolve()
    for rel in paths:
        source = root / rel
        if not source.is_file():
            continue
        yield rel, source.read_text(encoding="utf-8")


def check_markdown_links(repo_root: str) -> list[Finding]:
    """追跡下の Markdown の相対リンクが実在するか検査する。"""
    root = Path(repo_root).resolve()
    findings: list[Finding] = []
    for rel, text in read_tracked_texts(repo_root, tracked_files(repo_root, MARKDOWN_GLOB)):
        source = root / rel
        for target in extract_link_targets(text):
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
