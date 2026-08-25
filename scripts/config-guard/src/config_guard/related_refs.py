"""`## 関連` 節の Issue 参照が識別子だけで書かれ、その識別子が実在するかの検査。

Issue をクローズすると `docs/issues/closed/` へ移り、パスの深さが 1 段変わる。相対リンクは
この深さに依存するので、移動のたびに両方向の書き換えが要る。リンクを張らなければ移動を
残したまま書き換えが 0 になる (設計は Issue 43 の spec が canonical)。

`markdown_links` との違いは見る対象。あちらはリンク先のパスを見て、こちらは識別子を見る。
リンクを外した後に残るのは識別子だけなので、あちらの検査は届かなくなる。

## 他リポジトリ参照

前置の無い識別子だけを自リポジトリで解決する。番号は両リポジトリで独立に採番されるので、
前置が無いまま解決すると、たまたま番号が一致する別 Issue へ静かに解決される。エラーに
ならないので出力を見ても気づけない。

前置はリポジトリ名で、既知のものを `FOREIGN_REPOS` が持つ。ここに無い名前は前置と
認めないので、未知のリポジトリを参照すると報告される側へ倒れる。「ハイフンを含む
トークンを前置とみなす」ような近似へ寄せ替えないこと。免除が広がっても結果は違反 0 件の
緑にしかならず、出力からは気づけない (どう外したかの実測は Issue 43 の spec)。

前置は識別子ごとに、同じ行の識別子より前へ書く。`<repo> 側:` のような段落見出しで
まとめて括る形は、見出しが行単位の走査から見えず配下の識別子が前置を失うため、
見出しの形そのものを報告する。

## 記法の canonical

識別子と Issue ディレクトリ名の記法は `dev-workflow:in-repo-issue` skill の
`scripts/issue-id.py` が canonical で、あちらは apm の deploy 先に在るため import できない。
再定義が取り残されると「違反 0 件」を返して沈黙するので、実ディレクトリ名を
`issue_number_of` に通す対照をテストへ置き、記法が変わったら赤くなるようにしてある。

## 既知の限界

- 節の走査は `prose_lines` を借りる。フェンス走査の実装を 3 つ目にしないため
  (Issue 39 が 2 実装を 1 つへ寄せる作業を持っている)
- 識別子の抽出は行単位の regex で Markdown パーサではない。`Issue 43 件` のような
  数量表現は識別子として読まれる。実在する番号なら無害で、実在しない番号のときだけ
  誤検出になる
- リンクの中の識別子は読まない。リンク自体を下の形式検査と `markdown_links` が見るのと、
  角括弧が `PR ` の直前判定を壊すため (`- relay PR [#588](...)` が実在する)
- 前置は同じ行のそれより後ろに在る識別子すべてに効く。他リポ前置の後ろへ自リポの識別子を
  書くと実在検査を素通りする。識別子ごとに前置を必須にする案を採らなかった理由は
  Issue 43 の spec が持つ (書き忘れの結果が誤解決の側へ倒れるため)
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from config_guard.git_run import tracked_files
from config_guard.instruction_refs import prose_lines
from config_guard.markdown_links import (
    LINK_PATTERN,
    link_path_to_check,
    read_tracked_texts,
    strip_inline_links,
)
from config_guard.models import Finding

ISSUE_ROOT = "docs/issues"
ISSUE_MARKDOWN_GLOB = f"{ISSUE_ROOT}/*.md"
CLOSED_DIR = "closed"
RELATED_HEADING = "## 関連"

# 他リポジトリの Issue を指すときに識別子へ前置する名前。ここに無い名前は前置と
# 認めず自リポジトリで解決するので、参照するリポジトリが増えたらここへ足す。
FOREIGN_REPOS: tuple[str, ...] = ("agentic-coding-tools",)

# Issue ディレクトリ名。接頭辞を optional にして旧記法と新記法の両方を受ける
# (canonical は issue-id.py の ANY_ISSUE_DIR。理由はモジュール docstring)。
_ISSUE_DIR = re.compile(r"^(?:ISSUE-)?([0-9]+)_")

# 見出し行。節の終わりは h1/h2 だけが決める。節の中の h3 以下で走査が止まると、
# 以降の識別子が黙って検査されなくなる
_HEADING = re.compile(r"^(#{1,6})\s")

# `<repo> 側:` の形。配下の識別子が前置を失う形なので、見出しそのものを報告する。
# リポジトリ名が既知かどうかは条件に入れない。未知の名前で括られた見出しこそ配下が
# 自リポジトリで解決される側なので、既知に限ると危ない方だけが報告されなくなる。
# 全角コロンはコードポイントで書く。字面で置くと半角と見分けが付かず、片方を落とす
# 変更が目視レビューを通り抜ける (落ちた側は違反 0 件の緑になるので出力にも出ない)
_SCOPE_HEADING = re.compile(r"^\S+\s*側[:\uff1a]\s*$")


# 使われている 4 つの記法をまとめて受ける。`Issue #N` は `#` の枝が
# 前置ごと消費するので、1 つの出現が 2 回数えられることはない。
# `#` の直前に英数字と `&` を許さないのは、HTML 実体参照と `owner/repo#N` を
# 識別子として読まないため
_IDENTIFIER = re.compile(r"(?:\bISSUE-|(?:\bIssue\s+)?(?<![0-9A-Za-z&])#|\bIssue\s+)([0-9]+)")

# GitHub の番号を指す前置。`PR ` と `owner/repo` の 2 つで、規約の canonical は
# issue-id.py (GITHUB_REF_ALLOWED_PREFIX と CROSS_REPO_REF)
_GITHUB_QUALIFIER = re.compile(r"(?:\bPR|[0-9A-Za-z._-]+/[0-9A-Za-z._-]+)\s*$")

# `## 関連` 節に残っているローカルリンクの本数。既存のリンクは一括変換しない
# (リンクテキストがディレクトリ名と一致していない実例が上流 ISSUE-24 の実測にあり、
# 機械変換すると不一致を識別子側へ持ち込む)。
# リンクを外したらここも減らす。減らし忘れは「baseline が実態と合っていない」で報告される。
# 増やす側は今のところ機械が止めない。同じコミットでリンクを 1 本足してここを 1 増やすと
# 実態と一致するので緑で通る (main と突き合わせるラチェットが無い)。単調非増加は
# レビューが守る約束であって検査が守っている状態ではない。埋めるのは Issue 47。
_LINK_BASELINE_ENTRIES: dict[str, int] = {
    "11_2 つのランチャの重複をどこまで共通化するか決める/issue.md": 1,
    "12_プロジェクト名の導出が .zshrc と statusline で二重実装されている/issue.md": 1,
    "17_Issue ディレクトリ配下の成果物ファイル名を config-guard で検査する/issue.md": 1,
    "18_closed 配下の Issue の status を config-guard で検査する/issue.md": 2,
    "26_Claude Code フックの共通基盤を集約する/issue.md": 2,
    "29_PUBLIC リポジトリに残る private リポジトリ名の露出を棚卸しする/issue.md": 2,
    "30_Markdown 内のシェルスニペットを構文検査する/issue.md": 2,
    "31_spec が参照する bootstrap.sh の関数名と行番号を実体に合わせる/issue.md": 1,
    "33_設定から外した Claude 設定ディレクトリの symlink が撤去されない/issue.md": 2,
    "34_cppath 関数のテストを追加する/issue.md": 1,
    "37_ツール取得の一時障害で CI が落ちるのを減らす/issue.md": 1,
    "38_ruff の per-file-ignores に残る dead な S101 を掃除する/issue.md": 1,
    "39_config-guard の Markdown フェンス走査を 1 実装へ寄せる/issue.md": 2,
    "40_skill バンドルの command と agent の二重登録を止める/issue.md": 2,
    "41_語の検査の近似を減らし免除の粒度を上げる/issue.md": 1,
    "42_リポジトリ固有の運用指示を外部ストレージから注入する仕組みを固める/issue.md": 3,
    "44_.zshrc が非対話シェルへ運ぶ設定をエイリアス以外にも絞る/issue.md": 1,
    "45_job が導入しないコマンドのテストが静かに全 skip する状態を解消する/issue.md": 2,
    "closed/10_タスクリスト ID を作業ディレクトリから自動導出する/issue.md": 1,
    "closed/13_保留にしたタスクリスト統合 3 本を適用する/issue.md": 1,
    "closed/15_docs の相対リンクを pre-commit で検査する/issue.md": 1,
    "closed/16_superpowers の成果物を Issue ディレクトリ配下へ寄せる/issue.md": 1,
    "closed/19_Windows 検証の基盤を VMware Fusion から Parallels へ移す/issue.md": 1,
    "closed/24_CLAUDE.md の MUST GLOBAL を族でまとめて読む単位を減らす/issue.md": 2,
    "closed/25_skill と plugin を新規 PUBLIC リポジトリへ集約し apm 配布へ移行する/issue.md": 8,
    "closed/32_symlink pair の列挙を張る側と数える側で共有する/issue.md": 2,
    "closed/35_CLAUDE.md の指示量と読む単位を減らす/issue.md": 2,
    "closed/36_CLAUDE.md を rules と skill へ分割し常時ロード量を減らす/issue.md": 6,
    "closed/7_Claude Code の 2 アカウント運用で設定を共有する/issue.md": 1,
    "closed/8_settings.json の live 専用パスを変数化して skip-worktree を解消する/issue.md": 2,
    "closed/9_2 アカウント間でタスクリストを共有する/issue.md": 1,
}

# 突き合わせと Finding の source はリポジトリ相対パスで扱う。上のキーが
# ISSUE_ROOT からの相対なのは、32 行に同じ接頭辞を書くとそこが 2 つ目の canonical に
# なるため (ISSUE_ROOT を変えたときに片方だけが残る)
LINK_BASELINE: dict[str, int] = {
    f"{ISSUE_ROOT}/{rel}": count for rel, count in _LINK_BASELINE_ENTRIES.items()
}


def issue_number_of(directory_name: str) -> str | None:
    """Issue ディレクトリ名から番号を返す。Issue ディレクトリでなければ None。"""
    match = _ISSUE_DIR.match(directory_name)
    return match.group(1) if match else None


def related_lines(text: str) -> list[str]:
    """`## 関連` 節の本文行を返す。見出し行・フェンス内・空行は含まない。

    空行を落とすのは、行の位置を使う呼び出し側が 1 つも無いため。返すと呼び出しごとに
    落とし直すことになり、落とし忘れた側だけが空行を数える。
    """
    lines: list[str] = []
    inside = False
    for line in prose_lines(text):
        heading = _HEADING.match(line)
        if heading:
            if len(heading.group(1)) <= 2:
                inside = line.strip() == RELATED_HEADING
            continue
        if inside and line.strip():
            lines.append(line)
    return lines


def local_link_targets(line: str) -> list[str]:
    """行に含まれるローカルリンクのターゲットを返す。外部 URL とアンカーは除く。

    リンク記法もローカル判定も `markdown_links` が canonical を持つ。数える側は
    取りこぼすと検査が素通りするので、リンクテキストの形を問わない広い方を使う。
    """
    return [target for target in LINK_PATTERN.findall(line) if link_path_to_check(target)]


def identifier_matches(line: str) -> list[tuple[str, str]]:
    """行から自リポジトリの Issue 識別子を (書かれた形, 番号) で返す。

    GitHub の番号 (`PR #N` / `owner/repo#N`) と、リポジトリ名を前置した他リポジトリ参照は
    除く。除外はいずれも識別子より前のテキストだけを見るので、同じ行の後続の識別子は
    通常どおり読まれる。
    """
    body = strip_inline_links(line)
    found: list[tuple[str, str]] = []
    for match in _IDENTIFIER.finditer(body):
        before = body[: match.start()]
        if _GITHUB_QUALIFIER.search(before):
            continue
        if any(repo in before for repo in FOREIGN_REPOS):
            continue
        found.append((match.group(0), match.group(1)))
    return found


def tracked_issue_markdown(repo_root: str) -> list[str]:
    """追跡下の Issue ドキュメントを repo 相対パスで返す。"""
    return tracked_files(repo_root, ISSUE_MARKDOWN_GLOB)


def issue_numbers(paths: list[str]) -> set[str]:
    """Issue ドキュメントのパス一覧から、実在する Issue 番号の集合を返す。

    パス一覧を引数で受けるのは、呼び出し側が同じ一覧を節の走査にも使うため。ここで
    引き直すと 1 回の検査で git ls-files が何度も走る。
    """
    numbers: set[str] = set()
    for rel in paths:
        # `closed/` の 1 段だけ剥がす。その先は剥がさない (Issue ディレクトリの下に
        # notes/ のようにもう 1 段持つ実例がある)
        rest = Path(rel).relative_to(ISSUE_ROOT).parts
        if rest and rest[0] == CLOSED_DIR:
            rest = rest[1:]
        if not rest:
            continue
        number = issue_number_of(rest[0])
        if number is not None:
            numbers.add(number)
    return numbers


def _sections(repo_root: str, paths: list[str]) -> Iterator[tuple[str, list[str]]]:
    """Issue ドキュメントの `## 関連` 節を (repo 相対パス, 本文行) で返す。"""
    for rel, text in read_tracked_texts(repo_root, paths):
        lines = related_lines(text)
        if lines:
            yield rel, lines


def _section_refs(lines: list[str]) -> tuple[list[str], list[tuple[str, str]], int]:
    """節を 1 度だけ走り (括りの見出し, 識別子, ローカルリンク本数) を返す。

    検査とサマリが別々に走ると、片方だけを直したときに出力と Finding が食い違う。
    """
    headings: list[str] = []
    identifiers: list[tuple[str, str]] = []
    links = 0
    for line in lines:
        if _SCOPE_HEADING.match(line.strip()):
            headings.append(line.strip())
            continue
        links += len(local_link_targets(line))
        identifiers.extend(identifier_matches(line))
    return headings, identifiers, links


_SCOPE_MESSAGE = (
    "リポジトリ名でまとめて括る見出しは、配下の識別子が前置を失う。行単位の走査から"
    "見出しは見えないので、番号が自リポジトリにも在ると別の Issue へ静かに解決される。"
    "見出しをやめ、識別子ごとに同じ行へ前置すること"
)

_MISSING_MESSAGE = (
    "この識別子に対応する Issue が docs/issues に無い。参照先が消えたか綴りが違う。"
    f"他リポジトリを指すならリポジトリ名を前置すること (既知: {', '.join(FOREIGN_REPOS)})"
)


def check_related_refs(
    repo_root: str,
    baseline: dict[str, int] | None = None,
) -> list[Finding]:
    """`## 関連` 節の識別子が実在するか、リンクが baseline を超えていないかを検査する。

    in-repo Issue を持たないリポジトリは対象外にする。`docs/issues` 配下の追跡ファイルが
    1 件も無いときは baseline の突き合わせも行わない (全件を「消えた」と報告してしまうため)。
    """
    allowed_links = LINK_BASELINE if baseline is None else baseline
    tracked = tracked_issue_markdown(repo_root)
    if not tracked:
        return []

    numbers = issue_numbers(tracked)
    findings: list[Finding] = []
    links_by_file: dict[str, int] = {}

    for rel, lines in _sections(repo_root, tracked):
        headings, identifiers, links = _section_refs(lines)
        findings.extend(Finding(rel, heading, _SCOPE_MESSAGE) for heading in headings)
        findings.extend(
            Finding(rel, written, _MISSING_MESSAGE)
            for written, number in identifiers
            if number not in numbers
        )
        links_by_file[rel] = links

    findings.extend(_check_link_baseline(links_by_file, allowed_links))
    return findings


def _check_link_baseline(
    links_by_file: dict[str, int],
    allowed: dict[str, int],
) -> list[Finding]:
    """リンク本数を baseline と突き合わせる。増えた側も減った側も報告する。

    減った側を黙って通すと baseline が実態より大きいまま残り、次の 1 本が無検査で入る。
    """
    findings: list[Finding] = []
    for rel, count in sorted(allowed.items()):
        if rel not in links_by_file:
            findings.append(
                Finding(
                    rel,
                    f"baseline {count}",
                    "baseline に記録があるが `## 関連` 節を持つ追跡ファイルとして見つからない。"
                    f"移動か削除で参照が消えたなら {__name__} の LINK_BASELINE から消すこと",
                )
            )
    for rel, count in sorted(links_by_file.items()):
        limit = allowed.get(rel, 0)
        if count > limit:
            findings.append(
                Finding(
                    rel,
                    f"{count} > {limit}",
                    "`## 関連` 節ではリンクを張らず識別子だけを書くこと。"
                    "リンクは Issue の移動で切れるが、識別子は切れない",
                )
            )
        elif count < limit:
            findings.append(
                Finding(
                    rel,
                    f"{count} < {limit}",
                    f"リンクが減ったので {__name__} の LINK_BASELINE も同じ値へ下げること。"
                    "残したままだと次の 1 本が無検査で入る",
                )
            )
    return findings


def related_refs_summary(repo_root: str) -> str:
    """走査した節の数と抽出した識別子の数を 1 行で返す。

    0 件で緑になる経路と、そもそも見ていないから 0 件の経路を区別できるようにする。
    """
    sections = identifiers = links = 0
    for _, lines in _sections(repo_root, tracked_issue_markdown(repo_root)):
        sections += 1
        _, found, count = _section_refs(lines)
        identifiers += len(found)
        links += count
    return f"関連 {sections} 節 / 識別子 {identifiers} 件 / 残リンク {links} 件"
