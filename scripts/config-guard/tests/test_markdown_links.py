"""markdown_links の仕様テスト。

リンク抽出と分類 (pure) と、リポジトリ走査による実在判定 (実 git repo) を検証する。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.markdown_links import (
    check_markdown_links,
    extract_link_targets,
    link_path_to_check,
)
from tests.conftest import init_repo, run_git, write_file


def test_extract_picks_up_inline_links() -> None:
    text = "見出し\n\n[説明](../a/issue.md) と [別](https://example.com/x) がある\n"
    assert extract_link_targets(text) == ["../a/issue.md", "https://example.com/x"]


def test_extract_picks_up_image_links() -> None:
    # 画像記法も同じ形なので拾える (現状リポジトリには無いが誤って落とさないことを pin)
    assert extract_link_targets("![alt](img/a.png)") == ["img/a.png"]


def test_extract_returns_empty_without_links() -> None:
    assert extract_link_targets("リンクを含まない本文\n") == []


def test_extract_ignores_fenced_code_block_links() -> None:
    # 設計ドキュメントがリンク記法を例示することがある。実リンクと誤読しない
    text = "本文\n\n```python\n# [説明](../b/missing.md) は例であって実リンクではない\n```\n"
    assert extract_link_targets(text) == []


def test_extract_recognizes_indented_fence() -> None:
    # 行頭がインデントされたフェンスも実在する (SKILL.md に 3 スペースの例がある)
    text = "1. 手順\n\n   ```\n   [説明](../b/missing.md)\n   ```\n"
    assert extract_link_targets(text) == []


def test_extract_ignores_inline_code_links() -> None:
    # 表の中で記法そのものを示す書き方を実リンクと誤読しない
    assert extract_link_targets("画像記法は `![alt](../b/missing.md)` と書く\n") == []


def test_extract_keeps_link_after_fence() -> None:
    # フェンスが閉じた後のリンクは抽出される (トグルが確かに閉じることを pin する)
    text = "```\nコード\n```\n\n[先](../b/missing.md)\n"
    assert extract_link_targets(text) == ["../b/missing.md"]


def test_extract_keeps_link_outside_inline_code_on_same_line() -> None:
    # インラインコードを除去しても、同じ行にある実リンクは残る
    text = "`![alt](target)` の形で書く。詳細は [先](../b/missing.md) を見よ\n"
    assert extract_link_targets(text) == ["../b/missing.md"]


def test_extract_excludes_link_inside_nested_fence() -> None:
    # CommonMark: 終了フェンスは開始フェンス以上の長さが要る。外側 4 本の中に内側 3 本の
    # フェンスが入れ子でも、開始の長さを記憶しなければ内側の 3 本で早期に閉じてしまい、
    # 「markdown について書く markdown」の例示コード中のリンクを実リンクと誤読する
    text = "````markdown\n内側の例:\n```\n[内側の例中のリンク](../inner.md)\n```\n````\n"
    assert extract_link_targets(text) == []


def test_extract_keeps_link_after_nested_fence() -> None:
    # ネストしたフェンスが閉じた後は通常どおり抽出される (除外しすぎない negative case)。
    # 内側の 3 本で誤って閉じると内側のリンクも漏れて 2 件になり、リスト全体の一致が崩れる
    text = (
        "````markdown\n内側の例:\n```\n[内側の例中のリンク](../inner.md)\n```\n````\n"
        "[外側のリンク](../outer.md)\n"
    )
    assert extract_link_targets(text) == ["../outer.md"]


def test_external_urls_are_not_checked() -> None:
    assert link_path_to_check("https://example.com/x") is None
    assert link_path_to_check("http://example.com/x") is None
    assert link_path_to_check("mailto:a@example.com") is None
    assert link_path_to_check("ftp://example.com/x") is None


def test_external_url_scheme_is_case_insensitive() -> None:
    assert link_path_to_check("HTTPS://example.com/x") is None


def test_unknown_scheme_is_not_checked() -> None:
    # スキームは既知の列挙ではなく RFC 3986 の文法で判定する。列挙に戻ると
    # 未知のスキームが相対パス扱いになり誤検出する
    assert link_path_to_check("vscode://file/a.py") is None
    assert link_path_to_check("obsidian://open?vault=x") is None
    assert link_path_to_check("file:///etc/hosts") is None


def test_protocol_relative_url_is_not_checked() -> None:
    # スキームを省いた外部参照。ローカルには解決できない
    assert link_path_to_check("//example.com/x") is None


def test_colon_in_later_segment_is_still_checked() -> None:
    # スキームの文法はコロンより前に / を許さない。第 2 セグメント以降のコロンは
    # パスの一部であり、fail-open になるのは第 1 セグメントのコロンだけ
    assert link_path_to_check("a/b:c.md") == "a/b:c.md"


def test_anchor_only_link_is_not_checked() -> None:
    assert link_path_to_check("#section") is None


def test_relative_path_is_returned_as_is() -> None:
    assert link_path_to_check("../a/issue.md") == "../a/issue.md"


def test_percent_encoding_is_decoded() -> None:
    # ディレクトリ名の半角空白が %20 でエンコードされる。デコードしないと解決に失敗する
    assert link_path_to_check("../13_%E4%BF%9D%E7%95%99%20%E7%B5%B1%E5%90%88/issue.md") == (
        "../13_保留 統合/issue.md"
    )


def test_anchor_is_stripped_before_decoding() -> None:
    # パス + アンカーはパス部分だけを返す
    assert link_path_to_check("a/b.md#section") == "a/b.md"


def test_encoded_hash_survives_anchor_stripping() -> None:
    # %23 は「ファイル名に含まれる #」であってアンカー区切りではない。
    # デコードを先に行うと裸の # になり、パスが誤って切り落とされる
    assert link_path_to_check("a/b%23c.md") == "a/b#c.md"


def _add_all(repo: Path) -> None:
    run_git(repo, "add", "-A")


def test_markdown_without_links_is_not_flagged(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_file(tmp_path, "docs/a/index.md", "リンクを含まない本文\n")
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []


def test_live_relative_link_is_not_flagged(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_file(tmp_path, "docs/a/index.md", "[先](../b/target.md)\n")
    write_file(tmp_path, "docs/b/target.md", "本文\n")
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []


def test_broken_relative_link_is_flagged(tmp_path: Path) -> None:
    init_repo(tmp_path)
    write_file(tmp_path, "docs/a/index.md", "[先](../b/missing.md)\n")
    _add_all(tmp_path)

    findings = check_markdown_links(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].source == "docs/a/index.md"
    assert findings[0].detail == "../b/missing.md"
    assert "docs/b/missing.md" in findings[0].message


def test_link_escaping_repo_is_reported_relative(tmp_path: Path) -> None:
    # repo 外へ解決されるリンクも repo 相対 (../ 始まり) で示す。docs/a/ から 3 段
    # 上がると repo の外に出る。walk_up の無い Path.relative_to は repo 外の解決先で
    # ValueError になり、指摘の代わりに scan 全体が落ちる
    init_repo(tmp_path)
    write_file(tmp_path, "docs/a/index.md", "[外](../../../escaped.md)\n")
    _add_all(tmp_path)

    findings = check_markdown_links(str(tmp_path))

    assert len(findings) == 1
    assert "解決先 ../escaped.md" in findings[0].message


def test_percent_encoded_link_with_anchor_resolves(tmp_path: Path) -> None:
    # strip / decode の各仕様は link_path_to_check の純粋テストが担う。ここでは解決が
    # link_path_to_check の返り値を使う配線を pin する。アンカー付き % エンコードにするのは
    # decode だけ・strip だけの部分的な迂回 (unquote や split の直書き) をどちらも
    # 「壊れている」と誤判定させて赤にするため
    init_repo(tmp_path)
    write_file(tmp_path, "docs/a/index.md", "[先](../b%20c/target.md#sec)\n")
    write_file(tmp_path, "docs/b c/target.md", "本文\n")
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []


def test_external_url_is_not_flagged(tmp_path: Path) -> None:
    # 外部/アンカーの分類仕様は link_path_to_check の純粋テストが担う。ここでは
    # link_path_to_check が None を返す分岐を check_markdown_links が skip する配線を pin する
    # (skip が消えると None の path 結合で TypeError になり、実リポジトリの scan が落ちる)
    init_repo(tmp_path)
    write_file(tmp_path, "docs/a/index.md", "[外](https://example.com/nope)\n")
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []


def test_path_with_anchor_flags_broken_path(tmp_path: Path) -> None:
    # Finding の detail は解決に使うパス部分ではなく、文書に書かれたままの target を保持する
    # (アンカーを含む形でしか区別できない仕様。修正時に文書中のリンクを検索できるようにする)
    init_repo(tmp_path)
    write_file(tmp_path, "docs/a/index.md", "[先](../b/missing.md#anchor)\n")
    _add_all(tmp_path)

    findings = check_markdown_links(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == "../b/missing.md#anchor"


def test_untracked_markdown_is_not_scanned(tmp_path: Path) -> None:
    # git add していないファイルは検査対象外。追跡下だけを見る仕様を pin する
    init_repo(tmp_path)
    write_file(tmp_path, "docs/a/tracked.md", "本文\n")
    _add_all(tmp_path)
    write_file(tmp_path, "docs/a/untracked.md", "[先](../b/missing.md)\n")

    assert check_markdown_links(str(tmp_path)) == []


def test_tracked_but_missing_from_worktree_markdown_is_skipped(tmp_path: Path) -> None:
    # git ls-files は index を列挙するが read は worktree を見るため、追跡下の .md を
    # rm しただけの状態 (commit 前の削除途中) では両者が食い違う。読めないファイルは
    # FileNotFoundError の生 traceback で落とさず skip する。削除途中のファイル自身の
    # リンクは検査対象として意味を持たず、そのファイルへ向かう他ファイルのリンク切れは
    # 通常どおり検出される (skip が検出漏れを生まないことを同時に pin する)
    init_repo(tmp_path)
    write_file(tmp_path, "docs/a/index.md", "[先](../b/target.md)\n")
    write_file(tmp_path, "docs/b/target.md", "[戻る](../a/index.md)\n")
    _add_all(tmp_path)
    (tmp_path / "docs/b/target.md").unlink()

    findings = check_markdown_links(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].source == "docs/a/index.md"
    assert findings[0].detail == "../b/target.md"


def test_directory_link_resolves(tmp_path: Path) -> None:
    # ディレクトリを指すリンクも実在すれば通る
    init_repo(tmp_path)
    write_file(tmp_path, "docs/a/index.md", "[先](../b)\n")
    write_file(tmp_path, "docs/b/target.md", "本文\n")
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []


def test_raises_on_git_error(tmp_path: Path) -> None:
    # git repo でないディレクトリでは git ls-files が 128 を返す。
    # 「リンクが 1 件も無い」と取り違えず明示的に失敗することを検証する (git init しない)
    try:
        check_markdown_links(str(tmp_path))
    except RuntimeError:
        pass
    else:
        raise AssertionError("git エラー時は RuntimeError が送出されるべき")


def test_code_region_exclusion_is_wired_into_check(tmp_path: Path) -> None:
    # フェンス / インラインコード除外の仕様そのものは extract_link_targets の純粋テストが
    # 担う。ここでは check_markdown_links が抽出を extract_link_targets に委ねている配線を
    # 1 本で pin する。生の LINK_PATTERN 走査に置き換わると例示リンク 2 件も検出され
    # findings が 3 件になる。除外しすぎて実リンクを落とさないことも同時に検証する
    init_repo(tmp_path)
    write_file(
        tmp_path,
        "docs/a/index.md",
        "```\n[フェンス内の例](../fenced.md)\n```\n"
        "`[インラインの例](../inline.md)` と [実リンク](../missing.md) を同じ行に書く\n",
    )
    _add_all(tmp_path)

    findings = check_markdown_links(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == "../missing.md"


def test_non_markdown_files_are_not_scanned(tmp_path: Path) -> None:
    # git ls-files の glob が '*.md' に絞られていること。'*' にすると全追跡ファイルを
    # 読もうとしてバイナリで壊れる。非 .md の追跡ファイルを置かないと glob を壊しても
    # 緑のままの dead pin になるため、.txt を置いて pin を生かしている
    init_repo(tmp_path)
    write_file(tmp_path, "docs/a/index.md", "本文\n")
    write_file(tmp_path, "docs/a/notes.txt", "[先](../b/missing.md)\n")
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []
