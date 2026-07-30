"""markdown_links の仕様テスト。

リンク抽出と分類 (pure) と、リポジトリ走査による実在判定 (実 git repo) を検証する。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from config_guard.git_run import isolated_git_env
from config_guard.markdown_links import (
    check_markdown_links,
    extract_link_targets,
    link_path_to_check,
)


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


def _init_repo(repo: Path) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "init", "-q"],
        check=True,
        capture_output=True,
        env=isolated_git_env(),
    )


def _write(repo: Path, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _add_all(repo: Path) -> None:
    subprocess.run(
        ["git", "-C", str(repo), "add", "-A"],
        check=True,
        capture_output=True,
        env=isolated_git_env(),
    )


def test_markdown_without_links_is_not_flagged(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write(tmp_path, "docs/a/index.md", "リンクを含まない本文\n")
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []


def test_live_relative_link_is_not_flagged(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write(tmp_path, "docs/a/index.md", "[先](../b/target.md)\n")
    _write(tmp_path, "docs/b/target.md", "本文\n")
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []


def test_broken_relative_link_is_flagged(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write(tmp_path, "docs/a/index.md", "[先](../b/missing.md)\n")
    _add_all(tmp_path)

    findings = check_markdown_links(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].source == "docs/a/index.md"
    assert findings[0].detail == "../b/missing.md"
    assert "docs/b/missing.md" in findings[0].message


def test_percent_encoded_link_resolves(tmp_path: Path) -> None:
    # デコードしないと「壊れている」と誤判定する (negative case)
    _init_repo(tmp_path)
    _write(tmp_path, "docs/a/index.md", "[先](../b%20c/target.md)\n")
    _write(tmp_path, "docs/b c/target.md", "本文\n")
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []


def test_external_url_is_not_flagged(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write(tmp_path, "docs/a/index.md", "[外](https://example.com/nope)\n")
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []


def test_anchor_only_link_is_not_flagged(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write(tmp_path, "docs/a/index.md", "[節へ](#section)\n")
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []


def test_path_with_anchor_checks_path_part_only(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    # パスが生きていればアンカーの実在は問わない
    _write(tmp_path, "docs/a/index.md", "[先](../b/target.md#nonexistent-anchor)\n")
    _write(tmp_path, "docs/b/target.md", "本文\n")
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []


def test_path_with_anchor_flags_broken_path(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write(tmp_path, "docs/a/index.md", "[先](../b/missing.md#anchor)\n")
    _add_all(tmp_path)

    findings = check_markdown_links(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == "../b/missing.md#anchor"


def test_untracked_markdown_is_not_scanned(tmp_path: Path) -> None:
    # git add していないファイルは検査対象外。追跡下だけを見る仕様を pin する
    _init_repo(tmp_path)
    _write(tmp_path, "docs/a/tracked.md", "本文\n")
    _add_all(tmp_path)
    _write(tmp_path, "docs/a/untracked.md", "[先](../b/missing.md)\n")

    assert check_markdown_links(str(tmp_path)) == []


def test_directory_link_resolves(tmp_path: Path) -> None:
    # ディレクトリを指すリンクも実在すれば通る
    _init_repo(tmp_path)
    _write(tmp_path, "docs/a/index.md", "[先](../b)\n")
    _write(tmp_path, "docs/b/target.md", "本文\n")
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


def test_fenced_code_block_links_are_ignored(tmp_path: Path) -> None:
    # 設計ドキュメントがリンク記法を例示することがある。実リンクと誤読しない
    _init_repo(tmp_path)
    _write(
        tmp_path,
        "docs/a/index.md",
        "本文\n\n```python\n# [説明](../b/missing.md) は例であって実リンクではない\n```\n",
    )
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []


def test_indented_fence_is_recognized(tmp_path: Path) -> None:
    # 行頭がインデントされたフェンスも実在する (SKILL.md に 3 スペースの例がある)
    _init_repo(tmp_path)
    _write(
        tmp_path,
        "docs/a/index.md",
        "1. 手順\n\n   ```\n   [説明](../b/missing.md)\n   ```\n",
    )
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []


def test_inline_code_links_are_ignored(tmp_path: Path) -> None:
    # 表の中で記法そのものを示す書き方を実リンクと誤読しない
    _init_repo(tmp_path)
    _write(tmp_path, "docs/a/index.md", "画像記法は `![alt](../b/missing.md)` と書く\n")
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []


def test_link_after_fence_is_still_checked(tmp_path: Path) -> None:
    # フェンスが閉じた後のリンクは検査される (トグルが確かに閉じることを pin する)
    _init_repo(tmp_path)
    _write(
        tmp_path,
        "docs/a/index.md",
        "```\nコード\n```\n\n[先](../b/missing.md)\n",
    )
    _add_all(tmp_path)

    findings = check_markdown_links(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == "../b/missing.md"


def test_link_outside_inline_code_on_same_line_is_checked(tmp_path: Path) -> None:
    # インラインコードを除去しても、同じ行にある実リンクは残る
    _init_repo(tmp_path)
    _write(
        tmp_path,
        "docs/a/index.md",
        "`![alt](target)` の形で書く。詳細は [先](../b/missing.md) を見よ\n",
    )
    _add_all(tmp_path)

    findings = check_markdown_links(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == "../b/missing.md"


def test_non_markdown_files_are_not_scanned(tmp_path: Path) -> None:
    # git ls-files の glob が '*.md' に絞られていること。'*' にすると全追跡ファイルを
    # 読もうとしてバイナリで壊れる。Task 2 の変異注入で dead pin だった箇所を pin する
    _init_repo(tmp_path)
    _write(tmp_path, "docs/a/index.md", "本文\n")
    _write(tmp_path, "docs/a/notes.txt", "[先](../b/missing.md)\n")
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []
