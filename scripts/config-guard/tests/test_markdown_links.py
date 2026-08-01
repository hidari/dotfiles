"""markdown_links の仕様テスト。

リンク抽出と分類 (pure) と、リポジトリ走査による実在判定 (実 git repo) を検証する。
"""

from __future__ import annotations

import glob
import re
import subprocess
from pathlib import Path

from config_guard import cli
from config_guard.apm_gitignore import LOCKFILE_PATH
from config_guard.git_run import isolated_git_env
from config_guard.git_source import SETTINGS_PATH
from config_guard.herdr_keys import CONFIG_PATH as HERDR_CONFIG_PATH
from config_guard.markdown_links import (
    _tracked_markdown_files,
    check_markdown_links,
    extract_link_targets,
    link_path_to_check,
)
from config_guard.mise_pins import MISE_CONFIG_PATH


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


def test_tracked_but_missing_from_worktree_markdown_is_skipped(tmp_path: Path) -> None:
    # git ls-files は index を列挙するが read は worktree を見るため、追跡下の .md を
    # rm しただけの状態 (commit 前の削除途中) では両者が食い違う。読めないファイルは
    # FileNotFoundError の生 traceback で落とさず skip する。削除途中のファイル自身の
    # リンクは検査対象として意味を持たず、そのファイルへ向かう他ファイルのリンク切れは
    # 通常どおり検出される (skip が検出漏れを生まないことを同時に pin する)
    _init_repo(tmp_path)
    _write(tmp_path, "docs/a/index.md", "[先](../b/target.md)\n")
    _write(tmp_path, "docs/b/target.md", "[戻る](../a/index.md)\n")
    _add_all(tmp_path)
    (tmp_path / "docs/b/target.md").unlink()

    findings = check_markdown_links(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].source == "docs/a/index.md"
    assert findings[0].detail == "../b/target.md"


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


def test_nested_fence_excludes_inner_link(tmp_path: Path) -> None:
    # CommonMark: 終了フェンスは開始フェンス以上の長さが要る。外側 4 本の中に内側 3 本の
    # フェンスが入れ子でも、開始の長さを記憶しなければ内側の 3 本で早期に閉じてしまい、
    # 「markdown について書く markdown」の例示コード中のリンクを実リンクと誤読する
    _init_repo(tmp_path)
    _write(
        tmp_path,
        "docs/a/index.md",
        "````markdown\n内側の例:\n```\n[内側の例中のリンク](../inner.md)\n```\n````\n",
    )
    _add_all(tmp_path)

    assert check_markdown_links(str(tmp_path)) == []


def test_link_after_nested_fence_is_still_checked(tmp_path: Path) -> None:
    # ネストしたフェンスが閉じた後は通常どおり検査される (除外しすぎない negative case)。
    # 内側の 3 本で誤って閉じると外側のリンクの手前で内側のリンクも漏れて検出され、
    # findings が 2 件になり len(findings) == 1 が崩れる
    _init_repo(tmp_path)
    _write(
        tmp_path,
        "docs/a/index.md",
        "````markdown\n内側の例:\n```\n[内側の例中のリンク](../inner.md)\n```\n````\n"
        "[外側のリンク](../outer.md)\n",
    )
    _add_all(tmp_path)

    findings = check_markdown_links(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == "../outer.md"


# pre-commit の config-guard-scan hook の files は「いつ発火するか」を決める配線
# (設計ドキュメントの配線節)。ここから選択肢を落としたり狭めたりしても実行系テストは
# 1 つも落ちず、対応する検査だけが silent に発火しなくなるため、cross-file invariant と
# してここで pin する (test_git_run.py の hook 照合と同じ流儀)
_REPO_ROOT = Path(__file__).resolve().parents[3]
_PRECOMMIT_CONFIG_PATH = _REPO_ROOT / ".pre-commit-config.yaml"


def _scan_hook_block_lines() -> list[str]:
    """config-guard-scan hook ブロックの行 (strip 済み) を読み出す。

    apm_gitignore.parse_deployed_files と同じ stdlib のみの行パース (YAML lib 非使用)。
    hook 内で id: が先頭に来る前提に依存するが、誤読は必ず赤側に倒れる:
    ブロックを見つけられなければここで AssertionError になる (silent pass にはならない)。
    """
    lines: list[str] = []
    in_hook = False
    for line in _PRECOMMIT_CONFIG_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith("- id:"):
            in_hook = stripped == "- id: config-guard-scan"
            continue
        if in_hook:
            lines.append(stripped)
    if not lines:
        raise AssertionError("config-guard-scan hook ブロックが見つからない")
    return lines


def _scan_hook_files_pattern() -> str:
    """config-guard-scan hook の files 正規表現を hook 定義から読み出す。

    正規表現を literal でコピーすると定義と二重管理になり drift するため、必ず読み出す。
    誤読は必ず赤側に倒れる: files: を拾えなければここで AssertionError、引用符等の
    混入した値を返しても呼び出し側のパス照合が全滅して落ちる (silent pass にはならない)。
    """
    for stripped in _scan_hook_block_lines():
        if stripped.startswith("files:"):
            return stripped.removeprefix("files:").strip()
    raise AssertionError("config-guard-scan hook の files 定義が見つからない")


def _precommit_top_level_keys() -> set[str]:
    """.pre-commit-config.yaml のトップレベル (インデント無し) のキー名を読み出す。

    誤読は必ず赤側に倒れる: repos が取れなければここで AssertionError になる。
    """
    keys = {
        line.split(":", 1)[0]
        for line in _PRECOMMIT_CONFIG_PATH.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith((" ", "\t", "#")) and ":" in line
    }
    if "repos" not in keys:
        raise AssertionError("トップレベルの repos が見つからない")
    return keys


def test_precommit_scan_hook_has_no_narrowing_keys() -> None:
    # pre-commit (4.6.0 run.py で実測) は files と exclude の両方を search で適用するため、
    # hook に exclude: を 1 行足すだけで一部の .md 編集が発火しなくなるが、上下の files
    # 照合テストは files の正規表現しか読まないので緑のまま通る。types 系も同様に発火を
    # 狭める。今日の hook は files 以外の絞り込みキーを持たない前提で成立しているので、
    # その不在自体を pin する。将来正当に足したくなったら、このテストが「files 照合だけ
    # では覆えなくなった」ことを知らせるシグナルとして赤くなる
    narrowing_keys = ("exclude:", "types:", "types_or:", "exclude_types:")
    for stripped in _scan_hook_block_lines():
        for key in narrowing_keys:
            assert not stripped.startswith(key), f"config-guard-scan hook に {key} が足された"
    # 同じ狭窄は config レベルでも起きる。run.py は hook の files/exclude を適用する前に
    # トップレベルの files/exclude を全 hook へ適用するため、こちらに 1 行足しても
    # hook ブロックの照合はすべて緑のまま通る (実測済み)。両方の経路を 1 つの不変条件で覆う
    assert not {"files", "exclude"} & _precommit_top_level_keys()


def test_precommit_scan_hook_fires_on_any_markdown_file() -> None:
    # リンク検査は追跡下の全 .md を走査するので、hook もそのすべてで発火せねばならない。
    # 例示パス数本の照合では `docs/` 等への狭窄が緑のまま通るため、検査本体と同じ列挙
    # (_tracked_markdown_files) で実リポジトリを全数照合する。pre-commit と同じ search
    # 適用で振る舞いとして検証する
    pattern = re.compile(_scan_hook_files_pattern())
    tracked = _tracked_markdown_files(str(_REPO_ROOT))
    # 列挙 0 件だと下の照合が何も検証しない (vacuous pass) ので先に落とす
    assert tracked
    unmatched = [rel for rel in tracked if not pattern.search(rel)]
    assert unmatched == []
    # 無関係なファイルでは発火しない (files が絞り込みとして機能していることの negative case)
    assert not pattern.search("home/.zshrc")


def test_precommit_scan_hook_covers_all_config_guard_inputs() -> None:
    # scan() の各検査が読む入力ファイルの編集で hook が発火しなければ、その検査は
    # silent に dead になる。各モジュールの canonical なパス定数を import して照合し、
    # パスを literal で再掲しない (二重管理の drift 防止)
    pattern = re.compile(_scan_hook_files_pattern())
    assert pattern.search(SETTINGS_PATH)
    assert pattern.search(LOCKFILE_PATH)
    assert pattern.search(HERDR_CONFIG_PATH)
    assert pattern.search(MISE_CONFIG_PATH)
    # skills の allowed-tools 検査の入力は glob なので実パスへ展開して照合する。
    # 「SKILL.md 専用の選択肢は `.md` の選択肢が覆うため持たない」という hook 側の
    # 削除判断を、狭窄で壊れない不変条件としてここで文書化する
    skill_paths = glob.glob(cli.SKILLS_GLOB, root_dir=_REPO_ROOT)
    # 展開 0 件だと下の照合が何も検証しない (vacuous pass) ので先に落とす
    assert skill_paths
    for rel in skill_paths:
        assert pattern.search(rel)
    # config-guard 自身のコード変更でも再走が要る。パスは literal で書かず、import 済み
    # module の実体ファイルから repo 相対へ引き直す
    assert pattern.search(str(Path(cli.__file__).resolve().relative_to(_REPO_ROOT)))
    # home/.gitignore は定数化されていない (apm_gitignore は直接読まず git check-ignore
    # 経由で間接的に評価する) ため、ここだけ literal で照合する
    assert pattern.search("home/.gitignore")
