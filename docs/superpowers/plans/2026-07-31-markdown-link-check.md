# Markdown 相対リンク検査 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 追跡下の Markdown の相対リンクが実在するかを config-guard で機械検査し、pre-commit と CI で止める。

**Architecture:** `scripts/config-guard` に `markdown_links.py` を新設する。リンク文字列の抽出と分類を純粋関数に切り出し、ファイル走査と実在判定を `check_markdown_links(repo_root)` が担う。`cli.py` の `scan()` から既存 5 チェックと同じ形で呼び、pre-commit は既存の `config-guard-scan` hook の `files` に `.md` を足すだけで配線する。

**Tech Stack:** Python 3.12 / stdlib のみ (`re`, `urllib.parse`, `pathlib`, `os.path`) / pytest / ruff / mypy strict

## Global Constraints

- 新規の外部依存を追加しない。`scripts/config-guard/pyproject.toml` の `dependencies` は `[]` のまま
- Python は `>=3.12`
- ruff: `line-length = 100`、`select = ["E", "W", "F", "I", "B", "UP", "N", "SIM", "RUF"]`
- mypy: `strict = true`。全ての公開関数に型注釈を付ける
- コード内のコメントは日本語で書く
- テストは既存パターンに合わせる。例外検証は `pytest.raises` ではなく try/except/else、git 起動は `isolated_git_env()` 経由
- コミットメッセージは `.cache/commit-<slug>.txt` に Write ツールで書き `git commit -F` で渡す。Bash コマンド文字列に日本語を載せない
- 各タスクの最後に変異注入を行い、テストが確かに赤くなることを 1 箇所ずつ隔離して確認する

## File Structure

| ファイル | 責務 |
| --- | --- |
| `scripts/config-guard/src/config_guard/markdown_links.py` (新規) | リンク抽出・分類の純粋関数と、リポジトリ走査による実在判定 |
| `scripts/config-guard/tests/test_markdown_links.py` (新規) | 上記の仕様テスト |
| `scripts/config-guard/src/config_guard/cli.py` (変更) | `check_markdown_links` を `scan()` に配線し docstring を更新 |
| `scripts/config-guard/tests/test_cli.py` (変更) | 配線されていることを pin するテストを追加 |
| `.pre-commit-config.yaml` (変更) | `config-guard-scan` hook の `files` に `.*\.md$` を追加 |
| `scripts/config-guard/README.md` (変更) | 検査項目にリンク検査を追記 |

---

### Task 1: リンク抽出と分類の純粋関数

**Files:**
- Create: `scripts/config-guard/src/config_guard/markdown_links.py`
- Test: `scripts/config-guard/tests/test_markdown_links.py`

**Interfaces:**
- Consumes: なし
- Produces:
  - `extract_link_targets(text: str) -> list[str]`
  - `link_path_to_check(target: str) -> str | None`

`link_path_to_check` は「検査すべきパス部分（URL デコード済み）」を返し、検査不要なら `None` を返す。Task 2 がこの 2 つを使う。

- [ ] **Step 1: 失敗するテストを書く**

`scripts/config-guard/tests/test_markdown_links.py` を新規作成する。

```python
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
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_markdown_links.py -v`
Expected: FAIL。`ModuleNotFoundError: No module named 'config_guard.markdown_links'`

- [ ] **Step 3: 最小の実装を書く**

`scripts/config-guard/src/config_guard/markdown_links.py` を新規作成する。

```python
"""追跡下の Markdown の相対リンクが実在するかを検査する。

Issue を docs/issues/closed/ へ移すたびに、その Issue を指す相対リンクと、その Issue から
出ているリンクの両方が切れる。`../10_...` と `../closed/10_...` の書き分けが両端の
open / closed 状態に依存するためで、close する側とは別のファイルへ波及編集が要る。
実際 closed/9_.../issue.md のリンクは導入時点で壊れており main 上に残っていた。

扱うのはインラインリンク `[text](target)` のみ。参照リンク定義・HTML タグ・自動リンクは
リポジトリに 1 件も無いため対象外とする。画像記法は同じ形なので自然にカバーされる。
"""

from __future__ import annotations

import re
import urllib.parse

# インラインリンクのターゲット部分。画像記法 ![alt](target) も同じ形なので拾える
LINK_PATTERN = re.compile(r"\]\(([^)]+)\)")

# ネットワークを叩かないためスキップするスキーム
EXTERNAL_SCHEME = re.compile(r"^(?:https?|mailto|ftp):", re.IGNORECASE)


def extract_link_targets(text: str) -> list[str]:
    """Markdown 本文からインラインリンクのターゲット文字列を抽出する。"""
    return LINK_PATTERN.findall(text)


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
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_markdown_links.py -v`
Expected: PASS。10 件すべて。

- [ ] **Step 5: 変異注入で pin を確かめる**

1 箇所ずつ隔離して行う。各変異の前に `cp scripts/config-guard/src/config_guard/markdown_links.py .cache/mutation-backup.py` でバックアップを取り、確認後に戻す（`git checkout --` は未コミット編集を巻き戻すので使わない）。

| 変異 | 赤くなるべきテスト |
| --- | --- |
| `EXTERNAL_SCHEME.match(target)` の分岐を削除 | `test_external_urls_are_not_checked` |
| `re.IGNORECASE` を外す | `test_external_url_scheme_is_case_insensitive` |
| `target.startswith("#")` の分岐を削除 | `test_anchor_only_link_is_not_checked` |
| `urllib.parse.unquote(path_part)` を `path_part` に変える | `test_percent_encoding_is_decoded` |
| デコードとアンカー切り落としの順序を入れ替える | `test_encoded_hash_survives_anchor_stripping` |

各変異後に `uv run --directory scripts/config-guard pytest tests/test_markdown_links.py -v` を単独で実行し、期待したテストが FAIL することを確認する。緑のままなら dead pin なのでテストを強化する。

- [ ] **Step 6: lint と型検査を通す**

Run: `uv run --directory scripts/config-guard ruff check src tests`
Run: `uv run --directory scripts/config-guard ruff format --check src tests`
Run: `uv run --directory scripts/config-guard mypy src tests`
Expected: いずれもエラー 0 件。

- [ ] **Step 7: コミット**

`.cache/commit-link-pure.txt` に Write ツールでメッセージを書く。

```
feat: Markdown リンクの抽出と分類を実装する

インラインリンクのターゲット抽出と、検査対象かどうかの分類を純粋関数で実装する。
外部 URL とアンカーのみのリンクは検査せず、パス + アンカーはパス部分だけを返す。
URL エンコードはデコードする。ディレクトリ名の半角空白が %20 になるため。

アンカーの切り落としをデコードより先に行う。逆順にすると %23 (ファイル名に含まれる #)
がデコードで裸の # になり、パスの一部が誤ってアンカーとして切り落とされる。

Claude-Session: https://claude.ai/code/session_014wnSNLSZgXiSAn51Sa6b5N
```

```bash
git add scripts/config-guard/src/config_guard/markdown_links.py scripts/config-guard/tests/test_markdown_links.py
git commit -F .cache/commit-link-pure.txt
```

---

### Task 2: リポジトリ走査と実在判定

**Files:**
- Modify: `scripts/config-guard/src/config_guard/markdown_links.py`
- Test: `scripts/config-guard/tests/test_markdown_links.py`

**Interfaces:**
- Consumes: `extract_link_targets`, `link_path_to_check` (Task 1)
- Produces: `check_markdown_links(repo_root: str) -> list[Finding]`

`Finding` は `config_guard.models` の `@dataclass(frozen=True)` で、フィールドの並びは `(source, detail, message)`。本チェックでは `source` にリンク元の repo 相対パス、`detail` にリンク文字列そのもの、`message` に理由と解決先を入れる。

- [ ] **Step 1: 失敗するテストを書く**

`scripts/config-guard/tests/test_markdown_links.py` の末尾に追記する。ファイル冒頭の import も次の形に差し替える。

```python
from __future__ import annotations

import subprocess
from pathlib import Path

from config_guard.git_run import isolated_git_env
from config_guard.markdown_links import (
    check_markdown_links,
    extract_link_targets,
    link_path_to_check,
)
```

追記するテスト本体。

```python
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
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_markdown_links.py -v`
Expected: FAIL。`ImportError: cannot import name 'check_markdown_links'`

- [ ] **Step 3: 最小の実装を書く**

`markdown_links.py` の import 部を差し替え、末尾に追記する。

```python
from __future__ import annotations

import os.path
import re
import urllib.parse
from pathlib import Path

from config_guard.git_run import run_git
from config_guard.models import Finding
```

```python
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
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_markdown_links.py -v`
Expected: PASS。Task 1 の 10 件と Task 2 の 11 件で 21 件。

`tests` の値が 21 であることを目で確認する。0 件実行を件数で見抜けない罠があるため、期待するテスト名が出力に現れていることも確かめる。

- [ ] **Step 5: 変異注入で pin を確かめる**

1 箇所ずつ隔離して行う。

| 変異 | 赤くなるべきテスト |
| --- | --- |
| `if resolved.exists(): continue` を `if True: continue` に変える | `test_broken_relative_link_is_flagged` |
| `_tracked_markdown_files` の `returncode != 0` の分岐を削除 | `test_raises_on_git_error` |
| `run_git(...)` の引数 `"*.md"` を `"*"` に変える | 全ファイルを読もうとして既存テストが壊れる (バイナリで UnicodeDecodeError 等) |
| `Finding(rel, target, ...)` の第 1 引数を固定文字列に変える | `test_broken_relative_link_is_flagged` の `source` 検証 |

- [ ] **Step 6: lint と型検査を通す**

Run: `uv run --directory scripts/config-guard ruff check src tests`
Run: `uv run --directory scripts/config-guard ruff format --check src tests`
Run: `uv run --directory scripts/config-guard mypy src tests`
Expected: いずれもエラー 0 件。

- [ ] **Step 7: 実リポジトリで動かして 0 件を確認する**

Run: `uv run --directory scripts/config-guard python -c "from config_guard.markdown_links import check_markdown_links; print(check_markdown_links('$(git rev-parse --show-toplevel)'))"`
Expected: `[]`

現在のリポジトリには壊れたリンクが無いことを spec の調査で確定済みなので、ここで 1 件でも出たら実装かリンクのどちらかが誤っている。

- [ ] **Step 8: コミット**

`.cache/commit-link-scan.txt` に Write ツールでメッセージを書く。

```
feat: 追跡下の Markdown の相対リンクの実在を検査する

git ls-files で追跡下の .md を列挙し、各リンクを解決して実在を確かめる。
git の exit code が 0 以外なら例外を送出する。「リンクが無い」と
git エラーを取り違えて検査を素通りさせないため。

解決先はマシン依存の絶対パスではなく repo 相対で示す。
repo 外へ出るリンクも ../ で表現でき、テストが tmp_path に縛られない。

Claude-Session: https://claude.ai/code/session_014wnSNLSZgXiSAn51Sa6b5N
```

```bash
git add scripts/config-guard/src/config_guard/markdown_links.py scripts/config-guard/tests/test_markdown_links.py
git commit -F .cache/commit-link-scan.txt
```

---

### Task 2 追補: コード領域の除外と dead pin の解消

Task 2 完了時に 2 つの問題が判明したため追補する。

1 つ目。実リポジトリで走らせると 13 件を検出した。すべてこの機能の spec と plan 自身がリンク記法を例示している箇所で、plan の 12 件はコードフェンス内、spec の 1 件はインラインコード内。Task 3 で配線すると pre-commit と CI がこの 13 件で止まる。設計判断としてコード領域を除外することにした（spec の「判定ロジック」節を更新済み）。

2 つ目。Task 2 の変異注入 3 番目（`"*.md"` を `"*"` に変える）が dead pin だった。全テストが緑のまま通る。テストフィクスチャに非 `.md` の追跡ファイルが 1 つも無いため。実リポジトリではバイナリを読んで `UnicodeDecodeError` になる本物のリスクなので、テストで pin する。

**Files:**
- Modify: `scripts/config-guard/src/config_guard/markdown_links.py`
- Test: `scripts/config-guard/tests/test_markdown_links.py`

**Interfaces:**
- Consumes: なし（既存関数の挙動変更）
- Produces: `extract_link_targets(text: str) -> list[str]` のシグネチャは不変。コードフェンス内とインラインコード内を返さなくなる

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_markdown_links.py` の末尾に追記する。

```python
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
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_markdown_links.py -v`
Expected: 新規 6 件のうち 4 件が FAIL（`test_fenced_code_block_links_are_ignored` / `test_indented_fence_is_recognized` / `test_inline_code_links_are_ignored` / `test_non_markdown_files_are_not_scanned`）。残り 2 件（`test_link_after_fence_is_still_checked` / `test_link_outside_inline_code_on_same_line_is_checked`）は現状の実装でも通る。通る 2 件は「除外を入れすぎない」ための negative case なので、この時点で緑でも問題ない。

FAIL の件数と対象テスト名を目で確認する。`tests` の総数だけを見て判断しないこと。

- [ ] **Step 3: 実装を書く**

`markdown_links.py` の定数部に 2 つ追加する。

```python
# コードフェンスの開始と終了。行頭のインデントを許す
# (home/.claude/skills/windows-vm-verification/SKILL.md に 3 スペースの例が実在する)。
# ~~~ によるフェンスは扱わない。リポジトリに 0 件で、扱わない副作用は
# 「フェンス内が検査される」だけなので実害が出た時点で足せる
FENCE_PATTERN = re.compile(r"^\s*`{3,}")

# インラインコード。バッククォートのペアで囲まれた範囲
INLINE_CODE_PATTERN = re.compile(r"`[^`]*`")
```

`extract_link_targets` を次に差し替える。

```python
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
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_markdown_links.py -v`
Expected: PASS。既存 21 件 + 新規 6 件 = 27 件。Task 1 の純粋関数テスト 10 件が壊れていないことも確認する（これらはフェンスもインラインコードも含まないので影響しないはず）。

- [ ] **Step 5: 変異注入で pin を確かめる**

1 箇所ずつ隔離して行う。`cp` でバックアップを取ってから壊し、確認後に戻す。

| 変異 | 赤くなるべきテスト |
| --- | --- |
| `if FENCE_PATTERN.match(line):` の分岐ごと削除 | `test_fenced_code_block_links_are_ignored` |
| `FENCE_PATTERN` の `^\s*` を `^` に変える | `test_indented_fence_is_recognized` |
| `INLINE_CODE_PATTERN.sub("", line)` を `line` に変える | `test_inline_code_links_are_ignored` |
| フェンス行で `in_fence = not in_fence` を `in_fence = True` に変える | `test_link_after_fence_is_still_checked` |
| `run_git(...)` の `"*.md"` を `"*"` に変える | `test_non_markdown_files_are_not_scanned` |

最後の 1 つは Task 2 で dead pin だった箇所である。今回は必ず赤くなること、そして赤くなる理由が「`.txt` に書いたリンクが検出された」ことであるのを出力で確認する。

- [ ] **Step 6: 実リポジトリで 0 件を確認する**

Run: `uv run --directory scripts/config-guard python -c "from config_guard.markdown_links import check_markdown_links; import subprocess; root = subprocess.run(['git','rev-parse','--show-toplevel'],capture_output=True,text=True).stdout.strip(); [print(f.source, '|', f.detail) for f in check_markdown_links(root)]"`

Expected: 出力なし（0 件）。

13 件が 0 件になることがこの追補の目的である。1 件でも残るなら、その内訳を報告すること。

- [ ] **Step 7: lint と型検査を通す**

Run: `uv run --directory scripts/config-guard ruff check src tests`
Run: `uv run --directory scripts/config-guard ruff format --check src tests`
Run: `uv run --directory scripts/config-guard mypy src tests`
Expected: いずれもエラー 0 件。

- [ ] **Step 8: コミット**

`.cache/commit-link-fence.txt` に Write ツールでメッセージを書く。

```
fix: コードフェンスとインラインコード内のリンク例を検査対象から外す

実リポジトリで 13 件を検出した。すべてこの機能の spec と plan 自身が
リンク記法を例示している箇所で、plan の 12 件はコードフェンス内、
spec の 1 件はインラインコード内だった。一般的な Markdown リンクチェッカーも
コードブロックを検査対象から外す。

行頭のバッククォート 3 つ以上でフェンスの内外をトグルし、フェンス外の行からは
インラインコードを除去してから抽出する。フェンスの行頭インデントは許す。
SKILL.md に 3 スペースインデントのフェンスが実在するため。

あわせて Task 2 の変異注入で dead pin だった箇所を pin する。
git ls-files の glob を '*' に変えても全テストが緑のままだった。
フィクスチャに非 .md の追跡ファイルが無かったため。
.txt にリンクを書いても検出されないことを検証するテストを足した。

Claude-Session: https://claude.ai/code/session_014wnSNLSZgXiSAn51Sa6b5N
```

```bash
git add scripts/config-guard/src/config_guard/markdown_links.py scripts/config-guard/tests/test_markdown_links.py docs/superpowers/specs/2026-07-31-markdown-link-check-design.md docs/superpowers/plans/2026-07-31-markdown-link-check.md
git commit -F .cache/commit-link-fence.txt
```

---

### Task 3: 配線とドキュメント

**Files:**
- Modify: `scripts/config-guard/src/config_guard/cli.py`
- Modify: `scripts/config-guard/tests/test_cli.py`
- Modify: `.pre-commit-config.yaml:77`
- Modify: `scripts/config-guard/README.md`

**Interfaces:**
- Consumes: `check_markdown_links(repo_root: str) -> list[Finding]` (Task 2)
- Produces: なし（配線のみ）

- [ ] **Step 1: 配線が無いと失敗するテストを書く**

`scripts/config-guard/tests/test_cli.py` の末尾に追記する。

```python
def test_broken_markdown_link_is_detected(tmp_path: Path) -> None:
    # リンク検査が scan に配線されていること
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, GOOD_SETTINGS)
    doc = repo / "docs/a/index.md"
    doc.parent.mkdir(parents=True, exist_ok=True)
    doc.write_text("[先](../b/missing.md)\n", encoding="utf-8")
    _run(repo, "add", "-A")

    findings = scan(str(repo))

    assert any(f.detail == "../b/missing.md" for f in findings)
```

- [ ] **Step 2: テストが失敗することを確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_cli.py::test_broken_markdown_link_is_detected -v`
Expected: FAIL。`assert any(...)` が False。

このとき出力の `tests` が 1、`skipped` が 0 であることも確認する。pattern が 1 件も一致しないとファイル自身が 1 件の pass として計上され `tests 1 / pass 1 / fail 0` になるため、件数だけでは 0 件実行と区別できない。期待したテスト名が出力に現れているかで判断する。

- [ ] **Step 3: cli.py に配線する**

`scripts/config-guard/src/config_guard/cli.py` を変更する。

モジュール docstring を次に差し替える。

```python
"""リポジトリをスキャンして構造逸脱を検出する。

stale なツール名参照 / committed settings.json の不変条件 / apm.lock.yaml の
deployed_files が gitignore されているか(追記漏れ) / mise の global ツール pin が
exact か / herdr keybinding の方向整合と chord 重複 / 追跡下の Markdown の相対リンクが
実在するかを検査する。
"""
```

import を追加する（`from config_guard.herdr_keys import ...` の次の行、アルファベット順に従い `markdown_links` は `mise_pins` の前）。

```python
from config_guard.markdown_links import check_markdown_links
```

`scan()` の `herdr_keys` 呼び出しの後に追記する。

```python
    # 追跡下の Markdown の相対リンクが実在するか。Issue を closed/ へ移すと
    # 両端のリンクが切れるが、リンク元は変更されないため差分だけでは検出できない
    findings.extend(check_markdown_links(str(root)))
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_cli.py -v`
Expected: PASS。既存 4 件 + 新規 1 件 = 5 件。

- [ ] **Step 5: pre-commit の files パターンを更新する**

`.pre-commit-config.yaml` の `config-guard-scan` hook（77 行目付近）の `files` を変更する。

変更前:

```yaml
        files: ^(home/\.claude/skills/.*/SKILL\.md|home/\.claude/settings\.json|home/apm\.lock\.yaml|home/\.gitignore|home/\.config/herdr/config\.toml|scripts/config-guard/.*)$
```

変更後:

```yaml
        files: ^(home/\.claude/skills/.*/SKILL\.md|home/\.claude/settings\.json|home/apm\.lock\.yaml|home/\.gitignore|home/\.config/herdr/config\.toml|scripts/config-guard/.*|.*\.md)$
```

- [ ] **Step 6: hook の発火条件を実測する**

spec で未確認としていた 2 ケースを実測する。`.cache/` に作業用の一時ファイルを置き、確認後に元へ戻す。

1. `.md` を `git rm` して commit したとき hook が発火するか
2. `.md` を含むディレクトリを `git mv` して commit したとき hook が発火するか

判定の基準は、pre-commit の出力に出る `config-guard scan (リポジトリ設定の静的検査)` の行が `Skipped` かどうかである。`(no files to check)Skipped` なら発火していない。

まず戻り先を記録する。この後のダミーコミットは `git reset --hard` で取り消すが、`HEAD~3` のような相対指定は使わない。途中で 1 つでもコミットに失敗すると数がずれ、Task 1 と Task 2 の成果まで巻き戻すためである。

```bash
mkdir -p .cache/probe-hook
git rev-parse HEAD > .cache/probe-hook/base-sha.txt
cat .cache/probe-hook/base-sha.txt
```

出力された SHA が Task 2 完了時点のコミットであることを `git log --oneline -1` で照合してから先へ進む。

次に土台のコミットを作る。

```bash
mkdir -p docs/probe-move-src
printf '本文\n' > docs/probe-delete.md
printf '本文\n' > docs/probe-move-src/a.md
git add docs/probe-delete.md docs/probe-move-src/a.md
```

コミットメッセージは `.cache/commit-probe-base.txt` に Write ツールで書く（本文は `chore: hook 発火条件の実測用ダミー` の 1 行でよい）。

```bash
git commit -F .cache/commit-probe-base.txt > .cache/probe-hook/base.log 2>&1
```

ケース 1（削除のみ）。

```bash
git rm -q docs/probe-delete.md
git commit -F .cache/commit-probe-delete.txt > .cache/probe-hook/delete.log 2>&1
grep -c 'config-guard scan.*Skipped' .cache/probe-hook/delete.log
```

`grep -c` が `0` なら発火した、`1` なら Skipped で発火していない。

ケース 2（移動のみ）。

```bash
git mv docs/probe-move-src docs/probe-move-dst
git commit -F .cache/commit-probe-move.txt > .cache/probe-hook/move.log 2>&1
grep -c 'config-guard scan.*Skipped' .cache/probe-hook/move.log
```

実測後、記録した SHA へ戻してダミーコミットを取り消す。

```bash
git reset --hard "$(cat .cache/probe-hook/base-sha.txt)"
git log --oneline -1
git status --short
git ls-files -v | grep '^S'
```

`git log --oneline -1` が Task 2 完了時点のコミットを指していること、`git status --short` が空であること、そして `home/.claude/settings.json` の skip-worktree（`S`）が残っていることを必ず確認する。ダミーコミットは settings.json を触らないので blob は変わらず保たれるはずだが、消えていたら `git update-index --skip-worktree home/.claude/settings.json` で戻す。

記録するのは次の 2 点。

- 削除のみのコミットで hook が発火したか（Yes / No）
- 移動のみのコミットで hook が発火したか（Yes / No）

結果を spec の該当箇所（「ただし `files` の判定に使われる staged ファイル一覧に…」の段落）へ実測値として書き戻し、推測を断定に置き換える。発火しないケースが残るなら「CI 側の全体走査が backstop」と明記する。`always_run: true` へは変更しない。

- [ ] **Step 7: README を更新する**

`scripts/config-guard/README.md` の検査項目の箇条書き（3-7 行目）を次に差し替える。`mise` の項目は実装済みなのに README から漏れていた既存の drift なので、ボーイスカウトルールで併せて直す。

変更前:

```markdown
- skills の `allowed-tools` と committed `home/.claude/settings.json` の stale なツール名参照
- `home/apm.lock.yaml` の deployed_files が gitignore されているか（追記漏れ）
- `home/.config/herdr/config.toml` の keybinding（`previous_*` と `next_*` の方向整合、chord 重複、アクション名の綴り）
```

変更後:

```markdown
- skills の `allowed-tools` と committed `home/.claude/settings.json` の stale なツール名参照
- `home/apm.lock.yaml` の deployed_files が gitignore されているか（追記漏れ）
- `home/.config/mise/config.toml` の global ツール pin が exact か
- `home/.config/herdr/config.toml` の keybinding（`previous_*` と `next_*` の方向整合、chord 重複、アクション名の綴り）
- 追跡下の Markdown（`git ls-files '*.md'`）の相対リンクが実在するか（Issue を `closed/` へ移すと両端のリンクが切れる）
```

- [ ] **Step 8: 全チェックを通す**

Run: `uv run --directory scripts/config-guard ruff check src tests`
Run: `uv run --directory scripts/config-guard ruff format --check src tests`
Run: `uv run --directory scripts/config-guard mypy src tests`
Run: `uv run --directory scripts/config-guard pytest -q`
Run: `uv run --directory scripts/config-guard config-guard "$(git rev-parse --show-toplevel)"`

Expected: lint と型検査はエラー 0 件。pytest は既存 95 件 + 新規 28 件（markdown_links 27 件 + cli 1 件）= 123 件。config-guard は「問題は検出されませんでした」。

pytest の件数が期待どおりであることを確認する。減っていたらテストが収集されていない。

- [ ] **Step 9: コミット**

`.cache/commit-link-wiring.txt` に Write ツールでメッセージを書く。

```
feat: リンク検査を config-guard に配線し pre-commit を更新する

scan() から check_markdown_links を呼び、pre-commit の config-guard-scan hook の
files に .md を追加する。CI は既存の config-guard ジョブがリポジトリ全体を走査するため
変更不要。

リンク検査は変更されたファイルだけを見る形では機能しない。リンク先を消したとき
壊れるのはリンク元であり、そのファイルは変更されていないため。既存 hook は
pass_filenames: false で常に全体を走査するのでこの性質に合致する。

hook の発火条件 (削除のみ / 移動のみのコミット) を実測し spec に書き戻した。

Claude-Session: https://claude.ai/code/session_014wnSNLSZgXiSAn51Sa6b5N
```

```bash
git add scripts/config-guard/src/config_guard/cli.py scripts/config-guard/tests/test_cli.py .pre-commit-config.yaml scripts/config-guard/README.md docs/superpowers/specs/2026-07-31-markdown-link-check-design.md
git commit -F .cache/commit-link-wiring.txt
```

---

## 完了条件

- `uv run --directory scripts/config-guard pytest -q` が 123 件 pass
- `uv run --directory scripts/config-guard config-guard "$(git rev-parse --show-toplevel)"` が「問題は検出されませんでした」
- ruff / mypy がエラー 0 件
- 意図的に `.md` のリンクを壊すと pre-commit がコミットを止めることを 1 度実演する
- CI 10 checks が全て success
