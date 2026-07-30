"""markdown_links の仕様テスト。

リンク抽出と分類 (pure) と、リポジトリ走査による実在判定 (実 git repo) を検証する。
"""

from __future__ import annotations

from config_guard.markdown_links import extract_link_targets, link_path_to_check


def test_extract_picks_up_inline_links() -> None:
    text = "見出し\n\n[説明](../a/issue.md) と [別](https://example.com/x) がある\n"
    assert extract_link_targets(text) == ["../a/issue.md", "https://example.com/x"]


def test_extract_picks_up_image_links() -> None:
    # 画像記法も同じ形なので拾える (現状リポジトリには無いが誤って落とさないことを pin)
    assert extract_link_targets("![alt](img/a.png)") == ["img/a.png"]


def test_extract_returns_empty_without_links() -> None:
    assert extract_link_targets("リンクを含まない本文\n") == []


def test_external_urls_are_not_checked() -> None:
    assert link_path_to_check("https://example.com/x") is None
    assert link_path_to_check("http://example.com/x") is None
    assert link_path_to_check("mailto:a@example.com") is None
    assert link_path_to_check("ftp://example.com/x") is None


def test_external_url_scheme_is_case_insensitive() -> None:
    assert link_path_to_check("HTTPS://example.com/x") is None


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
