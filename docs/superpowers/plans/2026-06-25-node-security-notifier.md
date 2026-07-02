# node-security-notifier Implementation Plan

> For agentic workers: REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

Goal: Node の脆弱性 RSS を日次監視し、新着セキュリティリリースを macOS 通知する Python ツールと、その launchd 自動実行を bootstrap で導入する。

Architecture: functional core + imperative shell。純粋関数の核（feed パース / diff / 通知組立）を fixture とデータで網羅テストし、薄い I/O 殻（HTTP 取得 / 状態書込 / osascript 実行）は依存注入でテスト可能にする。launchd plist はプレースホルダでコミットし bootstrap が実パスへ置換・冪等 load する。

Tech Stack: Python 3.12 標準ライブラリのみ（外部 pip 依存ゼロ）、uv + hatchling、ruff / mypy strict / pytest、bash（bootstrap・run.sh）、bats（bootstrap テスト）、launchd。

## Global Constraints

- requires-python >=3.12。`[project] dependencies = []`（標準ライブラリのみ。外部 pip 依存を足さない）
- 既存 scripts/config-guard と同一の lint/型/テスト設定（ruff line-length 100、select `["E","W","F","I","B","UP","N","SIM","RUF"]`、ignore `["RUF002","RUF003"]`、tests に S101 ignore、mypy strict、pytest `-ra --strict-markers --strict-config`）
- console script 名は `node-security-notifier`（`node_security_notifier.cli:main`）
- macOS 通知文（ユーザー向け＝外部）は英語。ツール内部ログは日本語（CLAUDE.md）
- コミットする plist に `/Users/<name>` 絶対パスを書かない。プレースホルダ `__DOTFILES_DIR__` / `__HOME__` を使い bootstrap が置換（gitleaks leak guard 回避）
- bootstrap に追加する関数は `# ヘルパー関数` 〜 `# メイン処理` マーカー間に置く（bats の `load_bootstrap_functions` が抽出する）。各関数は `DRY_RUN=true` で `[DRY-RUN] ...` を echo し副作用を出さない
- 各ファイル末尾は 1 つの空行で終える
- 全コミットメッセージ末尾に `Claude-Session: https://claude.ai/code/session_01XerMYnSkU8i3Ln1FgW5sxj` を付ける。本計画の各 commit ステップは subject のみ示すので、この footer を必ず付与する
- 作業ブランチは `feat/node-security-notifier`（既に作成済み・spec コミット済み）

## File Structure

新規 `scripts/node-security-notifier/`
- `pyproject.toml` パッケージ定義（config-guard と同型）
- `uv.lock` `uv sync` が生成（CI の `uv sync --frozen` 用）
- `README.md` 使い方
- `run.sh` launchd 用 wrapper（uv 解決 + ツール起動）
- `com.hidari.node-security-notifier.plist` launchd テンプレ（プレースホルダ）
- `src/node_security_notifier/`
  - `__init__.py`（空）
  - `__main__.py`（`python -m` 用）
  - `models.py` `FeedEntry`
  - `feed.py` `parse_feed`
  - `diff.py` `new_entries`
  - `state.py` `load_seen` / `save_seen`
  - `notify.py` `Notification` / `build_notifications` / `build_osascript_args` / `send_notification`
  - `fetch.py` `FEED_URL` / `fetch_feed`
  - `cli.py` `run` / `main`
- `tests/`
  - `__init__.py`（空）
  - `fixtures/sample_feed.xml`
  - `test_feed.py` / `test_diff.py` / `test_state.py` / `test_notify.py` / `test_cli.py`

既存ファイル変更
- `.github/workflows/test.yml` `node-security-notifier (python)` ジョブ追加
- `bootstrap.sh` `render_launch_agent_plist` / `setup_launch_agent` 追加 + `setup_dotfiles` から呼び出し
- `scripts/tests/bootstrap.bats` render 関数のテスト追加

---

### Task 1: パッケージ scaffold + FeedEntry + feed パース

Files:
- Create: `scripts/node-security-notifier/pyproject.toml`
- Create: `scripts/node-security-notifier/src/node_security_notifier/__init__.py`（空）
- Create: `scripts/node-security-notifier/src/node_security_notifier/__main__.py`
- Create: `scripts/node-security-notifier/src/node_security_notifier/models.py`
- Create: `scripts/node-security-notifier/src/node_security_notifier/feed.py`
- Create: `scripts/node-security-notifier/tests/__init__.py`（空）
- Create: `scripts/node-security-notifier/tests/fixtures/sample_feed.xml`
- Test: `scripts/node-security-notifier/tests/test_feed.py`

Interfaces:
- Produces: `FeedEntry(guid: str, title: str, link: str, pub_date: str)`（frozen dataclass）; `parse_feed(xml_bytes: bytes) -> list[FeedEntry]`（必須要素欠落 item はスキップ、出現順を保持、不正 XML は `xml.etree.ElementTree.ParseError` を送出）

- [ ] Step 1: pyproject.toml を作成

```toml
[project]
name = "node-security-notifier"
version = "0.1.0"
description = "Node の脆弱性 RSS を監視し新着セキュリティリリースを macOS 通知する"
readme = "README.md"
requires-python = ">=3.12"
license = { text = "MIT" }
authors = [{ name = "Hidari" }]
dependencies = []

[project.scripts]
node-security-notifier = "node_security_notifier.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/node_security_notifier"]

[dependency-groups]
dev = [
    "pytest>=8.3",
    "ruff>=0.8",
    "mypy>=1.13",
]

[tool.ruff]
line-length = 100
target-version = "py312"

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "UP", "N", "SIM", "RUF"]
ignore = ["RUF002", "RUF003"]

[tool.ruff.lint.per-file-ignores]
"tests/*" = ["S101"]

[tool.mypy]
strict = true
python_version = "3.12"
files = ["src", "tests"]
explicit_package_bases = true
mypy_path = "src"

[tool.pytest.ini_options]
addopts = "-ra --strict-markers --strict-config"
testpaths = ["tests"]
pythonpath = ["src"]
```

- [ ] Step 2: 空の `src/node_security_notifier/__init__.py` と `tests/__init__.py` を作成（各 1 空行）

- [ ] Step 3: 依存を同期して uv.lock を生成

Run: `cd scripts/node-security-notifier && uv sync`
Expected: `.venv` 作成、`uv.lock` 生成（成功終了）

- [ ] Step 4: fixture `tests/fixtures/sample_feed.xml` を作成

```xml
<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:atom="http://www.w3.org/2005/Atom" version="2.0">
  <channel>
    <title>Node.js Blog: Vulnerability Reports</title>
    <link>https://nodejs.org/en/blog/vulnerability</link>
    <atom:link href="https://nodejs.org/en/feed/vulnerability.xml" rel="self" type="application/rss+xml"/>
    <item>
      <title>June 2026 Security Releases</title>
      <link>https://nodejs.org/en/blog/vulnerability/june-2026-security-releases</link>
      <guid>https://nodejs.org/en/blog/vulnerability/june-2026-security-releases</guid>
      <pubDate>Thu, 18 Jun 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>March 2026 Security Releases</title>
      <link>https://nodejs.org/en/blog/vulnerability/march-2026-security-releases</link>
      <guid>https://nodejs.org/en/blog/vulnerability/march-2026-security-releases</guid>
      <pubDate>Tue, 10 Mar 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>欠落 item (guid 無し・スキップ対象)</title>
      <link>https://nodejs.org/en/blog/vulnerability/broken</link>
      <pubDate>Mon, 01 Jan 2024 00:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
```

- [ ] Step 5: feed パースの失敗テストを書く（`tests/test_feed.py`）

```python
"""feed パースの仕様テスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from node_security_notifier.feed import parse_feed

FIXTURE = Path(__file__).parent / "fixtures" / "sample_feed.xml"


class TestParseFeed:
    def test_parses_valid_items_in_order(self) -> None:
        entries = parse_feed(FIXTURE.read_bytes())
        assert [(e.guid, e.title) for e in entries] == [
            (
                "https://nodejs.org/en/blog/vulnerability/june-2026-security-releases",
                "June 2026 Security Releases",
            ),
            (
                "https://nodejs.org/en/blog/vulnerability/march-2026-security-releases",
                "March 2026 Security Releases",
            ),
        ]

    def test_skips_items_missing_required_fields(self) -> None:
        entries = parse_feed(FIXTURE.read_bytes())
        assert all(e.guid for e in entries)
        assert len(entries) == 2

    def test_raises_on_malformed_xml(self) -> None:
        import xml.etree.ElementTree as ET

        with pytest.raises(ET.ParseError):
            parse_feed(b"<rss><channel><item>")
```

- [ ] Step 6: テストが失敗することを確認

Run: `cd scripts/node-security-notifier && uv run pytest tests/test_feed.py -v`
Expected: FAIL（`ModuleNotFoundError: node_security_notifier.feed` 等）

- [ ] Step 7: `models.py` を実装

```python
"""フィードの 1 エントリを表す値型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FeedEntry:
    """Node 脆弱性フィードの 1 リリース。guid は安定 ID、link は advisory URL。"""

    guid: str
    title: str
    link: str
    pub_date: str
```

- [ ] Step 8: `feed.py` を実装

```python
"""Node 脆弱性 RSS (RSS 2.0) を FeedEntry のリストへパースする純粋関数。"""

from __future__ import annotations

import xml.etree.ElementTree as ET

from node_security_notifier.models import FeedEntry


def parse_feed(xml_bytes: bytes) -> list[FeedEntry]:
    """RSS バイト列を FeedEntry のリストへ変換する。出現順を保持する。

    必須要素 (title, link, guid, pubDate) が欠けた item はスキップする。
    不正な XML は xml.etree.ElementTree.ParseError を送出する。
    """
    root = ET.fromstring(xml_bytes)
    entries: list[FeedEntry] = []
    for item in root.findall("./channel/item"):
        guid = _text(item, "guid")
        title = _text(item, "title")
        link = _text(item, "link")
        pub_date = _text(item, "pubDate")
        if not (guid and title and link and pub_date):
            continue
        entries.append(FeedEntry(guid=guid, title=title, link=link, pub_date=pub_date))
    return entries


def _text(item: ET.Element, tag: str) -> str:
    el = item.find(tag)
    if el is None or el.text is None:
        return ""
    return el.text.strip()
```

- [ ] Step 9: `__main__.py` を実装

```python
"""python -m node_security_notifier のエントリポイント。"""

from __future__ import annotations

import sys

from node_security_notifier.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] Step 10: テストが通り、lint/型も緑であることを確認

Run: `cd scripts/node-security-notifier && uv run pytest tests/test_feed.py -v && uv run ruff check src tests && uv run ruff format --check src tests`
Expected: PASS（test 3 件成功、ruff エラーなし）。format 差分があれば `uv run ruff format src tests` で整形

注: この段階では `cli.py` 未実装のため `__main__.py` の import は mypy/実行で未解決になる。mypy は Task 5 完了後にまとめて緑化する。本ステップの確認は pytest と ruff のみ。

- [ ] Step 11: コミット（footer 必須）

```bash
cd ~/Develop/dotfiles
git add scripts/node-security-notifier/pyproject.toml scripts/node-security-notifier/uv.lock scripts/node-security-notifier/src scripts/node-security-notifier/tests
git commit -m "feat: node-security-notifier の feed パースを追加"
```

---

### Task 2: diff（新着抽出）

Files:
- Create: `scripts/node-security-notifier/src/node_security_notifier/diff.py`
- Test: `scripts/node-security-notifier/tests/test_diff.py`

Interfaces:
- Consumes: `FeedEntry`（Task 1）
- Produces: `new_entries(current: list[FeedEntry], seen: set[str]) -> list[FeedEntry]`（current のうち guid が seen に無いものを順序保持で返す）

- [ ] Step 1: 失敗テストを書く（`tests/test_diff.py`）

```python
"""diff（新着抽出）の仕様テスト。"""

from __future__ import annotations

from node_security_notifier.diff import new_entries
from node_security_notifier.models import FeedEntry

A = FeedEntry("g-a", "A", "https://x/a", "d")
B = FeedEntry("g-b", "B", "https://x/b", "d")
C = FeedEntry("g-c", "C", "https://x/c", "d")


class TestNewEntries:
    def test_returns_unseen_in_order(self) -> None:
        assert new_entries([A, B, C], {"g-b"}) == [A, C]

    def test_empty_when_all_seen(self) -> None:
        assert new_entries([A, B], {"g-a", "g-b"}) == []

    def test_all_when_seen_empty(self) -> None:
        assert new_entries([A, B], set()) == [A, B]
```

- [ ] Step 2: テストが失敗することを確認

Run: `cd scripts/node-security-notifier && uv run pytest tests/test_diff.py -v`
Expected: FAIL（`ModuleNotFoundError: node_security_notifier.diff`）

- [ ] Step 3: `diff.py` を実装

```python
"""既読集合に基づき新着エントリを抽出する純粋関数。"""

from __future__ import annotations

from node_security_notifier.models import FeedEntry


def new_entries(current: list[FeedEntry], seen: set[str]) -> list[FeedEntry]:
    """current のうち guid が seen に含まれないものを出現順で返す。"""
    return [entry for entry in current if entry.guid not in seen]
```

- [ ] Step 4: テストが通ることを確認

Run: `cd scripts/node-security-notifier && uv run pytest tests/test_diff.py -v`
Expected: PASS（3 件成功）

- [ ] Step 5: コミット（footer 必須）

```bash
cd ~/Develop/dotfiles
git add scripts/node-security-notifier/src/node_security_notifier/diff.py scripts/node-security-notifier/tests/test_diff.py
git commit -m "feat: node-security-notifier の新着抽出 diff を追加"
```

---

### Task 3: state（既読 GUID 集合の永続化）

Files:
- Create: `scripts/node-security-notifier/src/node_security_notifier/state.py`
- Test: `scripts/node-security-notifier/tests/test_state.py`

Interfaces:
- Produces: `load_seen(path: Path) -> set[str]`（欠落/破損/非リスト時は空集合）; `save_seen(path: Path, seen: set[str]) -> None`（親ディレクトリ自動作成、ソート済み JSON 配列で書込）

- [ ] Step 1: 失敗テストを書く（`tests/test_state.py`）

```python
"""state（既読集合の永続化）の仕様テスト。"""

from __future__ import annotations

from pathlib import Path

from node_security_notifier.state import load_seen, save_seen


class TestState:
    def test_round_trip(self, tmp_path: Path) -> None:
        path = tmp_path / "seen.json"
        save_seen(path, {"g-b", "g-a"})
        assert load_seen(path) == {"g-a", "g-b"}

    def test_load_missing_returns_empty(self, tmp_path: Path) -> None:
        assert load_seen(tmp_path / "absent.json") == set()

    def test_load_corrupt_returns_empty(self, tmp_path: Path) -> None:
        path = tmp_path / "seen.json"
        path.write_text("{ not json", encoding="utf-8")
        assert load_seen(path) == set()

    def test_save_creates_parent_dirs(self, tmp_path: Path) -> None:
        path = tmp_path / "nested" / "deep" / "seen.json"
        save_seen(path, {"g-a"})
        assert path.exists()
        assert load_seen(path) == {"g-a"}
```

- [ ] Step 2: テストが失敗することを確認

Run: `cd scripts/node-security-notifier && uv run pytest tests/test_state.py -v`
Expected: FAIL（`ModuleNotFoundError: node_security_notifier.state`）

- [ ] Step 3: `state.py` を実装

```python
"""既読 GUID 集合を JSON で永続化する。"""

from __future__ import annotations

import json
from pathlib import Path


def load_seen(path: Path) -> set[str]:
    """既読 GUID 集合を読む。欠落・破損・非リストの場合は空集合を返す。"""
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return set()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return set()
    if not isinstance(data, list):
        return set()
    return {str(item) for item in data}


def save_seen(path: Path, seen: set[str]) -> None:
    """既読 GUID 集合を JSON 配列で書き込む。親ディレクトリは自動作成する。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
```

- [ ] Step 4: テストが通ることを確認

Run: `cd scripts/node-security-notifier && uv run pytest tests/test_state.py -v`
Expected: PASS（4 件成功）

- [ ] Step 5: コミット（footer 必須）

```bash
cd ~/Develop/dotfiles
git add scripts/node-security-notifier/src/node_security_notifier/state.py scripts/node-security-notifier/tests/test_state.py
git commit -m "feat: node-security-notifier の既読集合 state を追加"
```

---

### Task 4: notify（通知組立 + osascript）

Files:
- Create: `scripts/node-security-notifier/src/node_security_notifier/notify.py`
- Test: `scripts/node-security-notifier/tests/test_notify.py`

Interfaces:
- Consumes: `FeedEntry`（Task 1）
- Produces:
  - `Notification(title: str, subtitle: str, body: str)`（frozen dataclass）
  - `build_notifications(entries: list[FeedEntry], max_individual: int) -> list[Notification]`（先頭 max_individual 件を個別化、超過があればサマリ 1 件を末尾に追加。entries 空なら空リスト）
  - `build_osascript_args(n: Notification) -> list[str]`（値を argv で渡す osascript コマンド配列。エスケープ不要）
  - `send_notification(n: Notification) -> None`（`subprocess.run(build_osascript_args(n), check=True)`）

- [ ] Step 1: 失敗テストを書く（`tests/test_notify.py`）

```python
"""notify（通知組立）の仕様テスト。"""

from __future__ import annotations

from node_security_notifier.models import FeedEntry
from node_security_notifier.notify import (
    Notification,
    build_notifications,
    build_osascript_args,
)

E1 = FeedEntry("g1", "June 2026 Security Releases", "https://x/1", "d")
E2 = FeedEntry("g2", "March 2026 Security Releases", "https://x/2", "d")
E3 = FeedEntry("g3", "Jan 2026 Security Releases", "https://x/3", "d")
E4 = FeedEntry("g4", "Dec 2025 Security Releases", "https://x/4", "d")


class TestBuildNotifications:
    def test_one_per_entry_within_limit(self) -> None:
        out = build_notifications([E1, E2], max_individual=3)
        assert len(out) == 2
        assert out[0] == Notification(
            title="Node.js Security Release",
            subtitle="June 2026 Security Releases",
            body="https://x/1",
        )

    def test_summary_appended_on_overflow(self) -> None:
        out = build_notifications([E1, E2, E3, E4], max_individual=3)
        assert len(out) == 4
        assert out[3] == Notification(
            title="Node.js Security Release",
            subtitle="1 more security release(s)",
            body="See nodejs.org/en/blog/vulnerability",
        )

    def test_empty_returns_empty(self) -> None:
        assert build_notifications([], max_individual=3) == []


class TestBuildOsascriptArgs:
    def test_passes_values_via_argv(self) -> None:
        n = Notification(title="T", subtitle="S", body="B")
        assert build_osascript_args(n) == [
            "osascript",
            "-e",
            "on run argv",
            "-e",
            "display notification (item 1 of argv) with title "
            "(item 2 of argv) subtitle (item 3 of argv)",
            "-e",
            "end run",
            "B",
            "T",
            "S",
        ]
```

- [ ] Step 2: テストが失敗することを確認

Run: `cd scripts/node-security-notifier && uv run pytest tests/test_notify.py -v`
Expected: FAIL（`ModuleNotFoundError: node_security_notifier.notify`）

- [ ] Step 3: `notify.py` を実装

```python
"""新着エントリから macOS 通知を組み立て osascript で送出する。

通知文はユーザー向け（外部）なので英語。値は osascript の argv で渡し、
AppleScript 文字列リテラルのエスケープを不要にする。
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass

from node_security_notifier.models import FeedEntry

_TITLE = "Node.js Security Release"
_VULN_PAGE = "See nodejs.org/en/blog/vulnerability"


@dataclass(frozen=True)
class Notification:
    """1 件の macOS 通知。title/subtitle/body はそのまま表示される。"""

    title: str
    subtitle: str
    body: str


def build_notifications(entries: list[FeedEntry], max_individual: int) -> list[Notification]:
    """先頭 max_individual 件を個別通知化し、超過分はサマリ 1 件にまとめる。"""
    notifications = [
        Notification(title=_TITLE, subtitle=entry.title, body=entry.link)
        for entry in entries[:max_individual]
    ]
    overflow = len(entries) - max_individual
    if overflow > 0:
        notifications.append(
            Notification(
                title=_TITLE,
                subtitle=f"{overflow} more security release(s)",
                body=_VULN_PAGE,
            )
        )
    return notifications


def build_osascript_args(n: Notification) -> list[str]:
    """値を argv で渡す osascript コマンド配列を組み立てる（エスケープ不要）。"""
    return [
        "osascript",
        "-e",
        "on run argv",
        "-e",
        "display notification (item 1 of argv) with title "
        "(item 2 of argv) subtitle (item 3 of argv)",
        "-e",
        "end run",
        n.body,
        n.title,
        n.subtitle,
    ]


def send_notification(n: Notification) -> None:
    """osascript で通知を送出する。失敗時は subprocess.CalledProcessError を送出。"""
    subprocess.run(build_osascript_args(n), check=True)
```

- [ ] Step 4: テストが通ることを確認

Run: `cd scripts/node-security-notifier && uv run pytest tests/test_notify.py -v`
Expected: PASS（4 件成功）

- [ ] Step 5: コミット（footer 必須）

```bash
cd ~/Develop/dotfiles
git add scripts/node-security-notifier/src/node_security_notifier/notify.py scripts/node-security-notifier/tests/test_notify.py
git commit -m "feat: node-security-notifier の通知組立を追加"
```

---

### Task 5: fetch + cli オーケストレーション

Files:
- Create: `scripts/node-security-notifier/src/node_security_notifier/fetch.py`
- Create: `scripts/node-security-notifier/src/node_security_notifier/cli.py`
- Test: `scripts/node-security-notifier/tests/test_cli.py`

Interfaces:
- Consumes: `parse_feed`, `new_entries`, `load_seen`/`save_seen`, `build_notifications`, `Notification`, `FeedEntry`
- Produces:
  - `FEED_URL: str`; `fetch_feed(url: str = FEED_URL, *, timeout: float = 30.0) -> bytes`
  - `run(*, fetcher: Callable[[], bytes], notifier: Callable[[Notification], None], state_path: Path, max_individual: int = 3) -> int`
  - `main(argv: list[str] | None = None) -> int`
  - 振る舞い: fetch 失敗(OSError)/パース失敗(ParseError)/空フィード は内部ログ + return 1（状態不変・通知なし）。`load_seen` が空（初回/破損）なら現状を seed し通知せず return 0。それ以外は新着を通知し `seen ∪ current` を保存して return 0。

- [ ] Step 1: 失敗テストを書く（`tests/test_cli.py`）

```python
"""cli オーケストレーションの仕様テスト（依存注入、モック不使用）。"""

from __future__ import annotations

from pathlib import Path

from node_security_notifier.cli import run
from node_security_notifier.notify import Notification
from node_security_notifier.state import load_seen, save_seen

FIXTURE = Path(__file__).parent / "fixtures" / "sample_feed.xml"
GUID_JUNE = "https://nodejs.org/en/blog/vulnerability/june-2026-security-releases"
GUID_MARCH = "https://nodejs.org/en/blog/vulnerability/march-2026-security-releases"


class Recorder:
    """通知を記録する test double（モックフレームワーク不使用）。"""

    def __init__(self) -> None:
        self.sent: list[Notification] = []

    def __call__(self, n: Notification) -> None:
        self.sent.append(n)


def _fetch_ok() -> bytes:
    return FIXTURE.read_bytes()


class TestRun:
    def test_first_run_seeds_without_notifying(self, tmp_path: Path) -> None:
        state = tmp_path / "seen.json"
        rec = Recorder()
        rc = run(fetcher=_fetch_ok, notifier=rec, state_path=state)
        assert rc == 0
        assert rec.sent == []
        assert load_seen(state) == {GUID_JUNE, GUID_MARCH}

    def test_notifies_only_new_entries(self, tmp_path: Path) -> None:
        state = tmp_path / "seen.json"
        save_seen(state, {GUID_MARCH})  # march は既読、june が新着
        rec = Recorder()
        rc = run(fetcher=_fetch_ok, notifier=rec, state_path=state)
        assert rc == 0
        assert [n.subtitle for n in rec.sent] == ["June 2026 Security Releases"]
        assert load_seen(state) == {GUID_JUNE, GUID_MARCH}

    def test_no_notification_when_all_seen(self, tmp_path: Path) -> None:
        state = tmp_path / "seen.json"
        save_seen(state, {GUID_JUNE, GUID_MARCH})
        rec = Recorder()
        rc = run(fetcher=_fetch_ok, notifier=rec, state_path=state)
        assert rc == 0
        assert rec.sent == []

    def test_network_failure_is_safe(self, tmp_path: Path) -> None:
        state = tmp_path / "seen.json"
        save_seen(state, {GUID_MARCH})

        def _fetch_fail() -> bytes:
            raise OSError("network down")

        rec = Recorder()
        rc = run(fetcher=_fetch_fail, notifier=rec, state_path=state)
        assert rc == 1
        assert rec.sent == []
        assert load_seen(state) == {GUID_MARCH}  # 状態は不変
```

- [ ] Step 2: テストが失敗することを確認

Run: `cd scripts/node-security-notifier && uv run pytest tests/test_cli.py -v`
Expected: FAIL（`ModuleNotFoundError: node_security_notifier.cli`）

- [ ] Step 3: `fetch.py` を実装

```python
"""Node 脆弱性 RSS を取得する薄い I/O 層。"""

from __future__ import annotations

import urllib.request

FEED_URL = "https://nodejs.org/en/feed/vulnerability.xml"


def fetch_feed(url: str = FEED_URL, *, timeout: float = 30.0) -> bytes:
    """フィード URL を取得し生バイト列を返す。失敗時は OSError 系を送出。"""
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        data: bytes = resp.read()
    return data
```

- [ ] Step 4: `cli.py` を実装

```python
"""取得 -> パース -> 差分 -> 通知 -> 保存 のオーケストレーション。"""

from __future__ import annotations

import logging
import xml.etree.ElementTree as ET
from collections.abc import Callable
from pathlib import Path

from node_security_notifier.diff import new_entries
from node_security_notifier.feed import parse_feed
from node_security_notifier.fetch import FEED_URL, fetch_feed
from node_security_notifier.notify import Notification, build_notifications, send_notification
from node_security_notifier.state import load_seen, save_seen

logger = logging.getLogger("node_security_notifier")

DEFAULT_STATE_PATH = Path.home() / ".local" / "state" / "node-security-notifier" / "seen.json"
MAX_INDIVIDUAL = 3


def run(
    *,
    fetcher: Callable[[], bytes],
    notifier: Callable[[Notification], None],
    state_path: Path,
    max_individual: int = MAX_INDIVIDUAL,
) -> int:
    """1 回分の取得〜通知を実行する。戻り値はプロセス終了コード。"""
    try:
        raw = fetcher()
    except OSError as exc:
        logger.error("フィード取得に失敗しました: %s", exc)
        return 1

    try:
        current = parse_feed(raw)
    except ET.ParseError as exc:
        logger.error("フィードのパースに失敗しました: %s", exc)
        return 1

    if not current:
        logger.error("フィードが空でした。状態は更新しません")
        return 1

    seen = load_seen(state_path)
    if not seen:
        save_seen(state_path, {e.guid for e in current})
        logger.info("初回実行のため現状を seed しました (%d 件)", len(current))
        return 0

    fresh = new_entries(current, seen)
    for notification in build_notifications(fresh, max_individual):
        notifier(notification)
    save_seen(state_path, seen | {e.guid for e in current})
    logger.info("新着 %d 件を処理しました", len(fresh))
    return 0


def main(argv: list[str] | None = None) -> int:
    """CLI エントリポイント。本番依存を結線して run を呼ぶ。"""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return run(
        fetcher=lambda: fetch_feed(FEED_URL),
        notifier=send_notification,
        state_path=DEFAULT_STATE_PATH,
    )
```

- [ ] Step 5: 全テスト + lint + 型を緑化

Run: `cd scripts/node-security-notifier && uv run pytest -v && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src tests`
Expected: PASS（全 test 成功、ruff 差分なし、mypy `Success`）。差分があれば `uv run ruff format src tests`

- [ ] Step 6: コミット（footer 必須）

```bash
cd ~/Develop/dotfiles
git add scripts/node-security-notifier/src/node_security_notifier/fetch.py scripts/node-security-notifier/src/node_security_notifier/cli.py scripts/node-security-notifier/tests/test_cli.py
git commit -m "feat: node-security-notifier の cli オーケストレーションを追加"
```

---

### Task 6: run.sh wrapper + README

Files:
- Create: `scripts/node-security-notifier/run.sh`
- Create: `scripts/node-security-notifier/README.md`

Interfaces:
- Produces: `run.sh`（launchd から絶対パスで起動され、uv を解決して `uv run node-security-notifier` を exec する）

- [ ] Step 1: `run.sh` を作成

```bash
#!/usr/bin/env bash
# node-security-notifier を launchd 環境から起動する薄い wrapper。
# launchd の最小 PATH でも uv を解決できるよう主要パスを補う。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

exec uv run --directory "$SCRIPT_DIR" node-security-notifier
```

- [ ] Step 2: 実行権限を付与

Run: `chmod +x scripts/node-security-notifier/run.sh`
Expected: 成功（`ls -l` で `x` が立つ）

- [ ] Step 3: `README.md` を作成

```markdown
# node-security-notifier

Node の脆弱性 RSS (`https://nodejs.org/en/feed/vulnerability.xml`) を日次で監視し、
新着セキュリティリリースを macOS 通知で知らせる。exact full-version で pin した node を
手動 bump する起点に使う。

## 実行

```bash
uv run node-security-notifier
```

初回実行は通知せず現状を seed する。以降は既読 GUID 集合と比較し、新着のみ通知する。
状態ファイルは `~/.local/state/node-security-notifier/seen.json`。

## 自動実行

bootstrap.sh が LaunchAgent (`com.hidari.node-security-notifier`) を導入し、日次 18:00 に
`run.sh` を起動する。ログは `~/.local/state/node-security-notifier/launchd.log`。
```

- [ ] Step 4: コミット（footer 必須）

```bash
cd ~/Develop/dotfiles
git add scripts/node-security-notifier/run.sh scripts/node-security-notifier/README.md
git commit -m "feat: node-security-notifier の run.sh と README を追加"
```

---

### Task 7: launchd plist + bootstrap 導入 + bats テスト

Files:
- Create: `scripts/node-security-notifier/com.hidari.node-security-notifier.plist`
- Modify: `bootstrap.sh`（`# ヘルパー関数` 〜 `# メイン処理` マーカー間に 2 関数追加、`setup_dotfiles` 末尾に呼び出し追加）
- Modify: `scripts/tests/bootstrap.bats`（render 関数テスト追加）

Interfaces:
- Consumes: `ensure_directory` / `log` / `warn`（bootstrap 既存）, `DRY_RUN` / `DOTFILES_DIR`
- Produces: `render_launch_agent_plist <template> <dest>`（プレースホルダ置換、DRY_RUN 対応、冪等）; `setup_launch_agent`（render + launchctl 冪等 load、launchctl 不在時はスキップ）

- [ ] Step 1: plist テンプレを作成（プレースホルダ）

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.hidari.node-security-notifier</string>
    <key>ProgramArguments</key>
    <array>
        <string>__DOTFILES_DIR__/scripts/node-security-notifier/run.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>18</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>__HOME__/.local/state/node-security-notifier/launchd.log</string>
    <key>StandardErrorPath</key>
    <string>__HOME__/.local/state/node-security-notifier/launchd.log</string>
</dict>
</plist>
```

- [ ] Step 2: bats の失敗テストを追加（`scripts/tests/bootstrap.bats` 末尾に追記）

```bash
# =============================================================================
# render_launch_agent_plist tests
# =============================================================================

@test "render_launch_agent_plist: substitutes placeholders" {
    local template="$TEST_HOME/tmpl.plist"
    local dest="$TEST_HOME/Library/LaunchAgents/out.plist"
    printf '%s\n' '__DOTFILES_DIR__/scripts/run.sh __HOME__/log' > "$template"
    DOTFILES_DIR="/repo"

    run render_launch_agent_plist "$template" "$dest"

    [ "$status" -eq 0 ]
    [ -f "$dest" ]
    grep -q "/repo/scripts/run.sh" "$dest"
    grep -q "$TEST_HOME/log" "$dest"
    ! grep -q "__DOTFILES_DIR__" "$dest"
    ! grep -q "__HOME__" "$dest"
}

@test "render_launch_agent_plist: dry-run does not write" {
    local template="$TEST_HOME/tmpl.plist"
    local dest="$TEST_HOME/out.plist"
    printf '%s\n' 'x' > "$template"
    DRY_RUN=true

    run render_launch_agent_plist "$template" "$dest"

    [ "$status" -eq 0 ]
    [[ "$output" == *"[DRY-RUN]"* ]]
    [ ! -f "$dest" ]
}
```

- [ ] Step 3: テストが失敗することを確認

Run: `bats scripts/tests/bootstrap.bats -f render_launch_agent_plist`
Expected: FAIL（`command not found: render_launch_agent_plist`）

- [ ] Step 4: bootstrap.sh に 2 関数を追加（`# メイン処理` マーカーの直前、`setup_dotfiles` 定義の後）

```bash
# LaunchAgent plist をプレースホルダ置換してレンダリング（冪等）
render_launch_agent_plist() {
    local template="$1"
    local dest="$2"

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] render $template -> $dest"
        return 0
    fi

    ensure_directory "$(dirname "$dest")"
    sed -e "s|__DOTFILES_DIR__|$DOTFILES_DIR|g" -e "s|__HOME__|$HOME|g" "$template" > "$dest"
    log "Rendered LaunchAgent: $dest"
}

# node-security-notifier の LaunchAgent を導入（macOS のみ）
setup_launch_agent() {
    local label="com.hidari.node-security-notifier"
    local template="$DOTFILES_DIR/scripts/node-security-notifier/$label.plist"
    local dest="$HOME/Library/LaunchAgents/$label.plist"

    render_launch_agent_plist "$template" "$dest"

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] launchctl reload $label"
        return 0
    fi

    if ! command -v launchctl &> /dev/null; then
        warn "launchctl not found; skipping LaunchAgent load"
        return 0
    fi

    local uid
    uid="$(id -u)"
    launchctl bootout "gui/$uid/$label" 2> /dev/null || true
    launchctl bootstrap "gui/$uid" "$dest"
    log "Loaded LaunchAgent: $label"
}
```

- [ ] Step 5: `setup_dotfiles` の末尾（`log "Dotfiles setup complete!"` の直前）に呼び出しを追加

```bash
    # node-security-notifier の LaunchAgent を導入
    setup_launch_agent

    log "Dotfiles setup complete!"
```

- [ ] Step 6: bats テストが通ることを確認

Run: `bats scripts/tests/bootstrap.bats`
Expected: PASS（既存 + 新規 render テストすべて成功）

- [ ] Step 7: dry-run で bootstrap 全体が壊れないことを確認

Run: `bash bootstrap.sh --dotfiles-only --dry-run`
Expected: `[DRY-RUN] render ...` と `[DRY-RUN] launchctl reload ...` を含み、エラーなく終了

- [ ] Step 8: コミット（footer 必須）

```bash
cd ~/Develop/dotfiles
git add scripts/node-security-notifier/com.hidari.node-security-notifier.plist bootstrap.sh scripts/tests/bootstrap.bats
git commit -m "feat: node-security-notifier の launchd 導入を bootstrap に追加"
```

---

### Task 8: CI ジョブ追加

Files:
- Modify: `.github/workflows/test.yml`（`config-guard` ジョブの後ろに新ジョブ追加）

Interfaces:
- Consumes: Task 1-5 の Python パッケージ（uv.lock 含む）

- [ ] Step 1: `test.yml` の末尾（`config-guard` ジョブ定義の後）に新ジョブを追加

```yaml
  node-security-notifier:
    name: node-security-notifier (python)
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: scripts/node-security-notifier
    steps:
      - uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4

      - name: Install uv
        uses: astral-sh/setup-uv@d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86 # v5
        with:
          enable-cache: true

      - name: Sync dependencies
        run: uv sync --frozen

      - name: Ruff check
        run: uv run ruff check src tests

      - name: Ruff format check
        run: uv run ruff format --check src tests

      - name: Mypy strict
        run: uv run mypy src tests

      - name: Pytest
        run: uv run pytest -q
```

- [ ] Step 2: ローカルで CI 相当を再現確認

Run: `cd scripts/node-security-notifier && uv sync --frozen && uv run ruff check src tests && uv run ruff format --check src tests && uv run mypy src tests && uv run pytest -q`
Expected: 全て成功（uv.lock が frozen で解決、ruff/mypy/pytest 緑）

- [ ] Step 3: コミット（footer 必須）

```bash
cd ~/Develop/dotfiles
git add .github/workflows/test.yml
git commit -m "ci: node-security-notifier のテストジョブを追加"
```

---

## 完了後の統合

全タスク完了後、`dev-workflow:pre-merge-quality-gate`（simplify / code-reviewer / boy-scout / e2e-impact）を通し、PR 作成 → CI 全緑 → squash マージ → ブランチ削除。マージ後にローカルで `bash bootstrap.sh --dotfiles-only` を実行して LaunchAgent を実機導入し、`launchctl print gui/$(id -u)/com.hidari.node-security-notifier` で登録を確認、`scripts/node-security-notifier/run.sh` を手動実行して seed が作られることを確認する。
