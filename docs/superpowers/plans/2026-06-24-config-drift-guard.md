# config drift guard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** skills の allowed-tools と committed settings.json の stale/不正なツール名参照、および committed settings.json の構造逸脱を CI と pre-commit で静的検出する Python ツール config-guard を作る。

**Architecture:** `scripts/config-guard/` を uv プロジェクトとして新設する（backup-tool と対称の ruff/mypy strict/pytest 構成）。ツール名検証は純粋関数 `validate_tool_token`（Hybrid: denylist + shape）に集約し、SKILL.md frontmatter と settings.json permissions の 2 経路から再利用する。settings.json は skip-worktree のため必ず git（staged→HEAD）から読み、working tree は読まない。

**Tech Stack:** Python 3.12+, uv, hatchling, ruff, mypy(strict), pytest。外部依存ゼロ（標準ライブラリの json / re / subprocess / glob / pathlib のみ）。

## Global Constraints

- requires-python は `>=3.12`、target-version `py312`（backup-tool に合わせる）。
- ランタイム依存はゼロに保つ（dependencies = []）。YAML パーサ等を足さず、frontmatter は標準ライブラリで抽出する。
- mypy は strict。bare な `dict` は禁止（`dict[str, Any]` 等を使う）。JSON 由来データは `Any` を明示的に使ってよいが、関数の戻り値で `Any` を露出しない。
- ruff の select / ignore は backup-tool と同一（RUF002/RUF003 は ignore）。tests には per-file-ignore `S101`。
- テストはモック禁止（git_source / cli は実際の一時 git リポジトリで検証する）。
- コード内コメントは日本語。config-guard の出力メッセージは内部ツールなので日本語。
- ファイル末尾は必ず 1 つの空行。
- ユーザー絶対パス（`/Users/<name>`）をコード・テスト・fixture に literal で書かない。プレースホルダは gitleaks allowlist 済みの `/Users/example` を使う。
- コミット末尾に `Claude-Session: https://claude.ai/code/session_01LfXRyn6J2VWYgQmVw2npso` を付ける。
- GitHub Actions の action は SHA pin（checkout `34e114876b0b11c390a56381ad16ebd13914f8d5 # v4`、setup-uv `d4b2f3b6ecc6e67c4457f6d3e41ec42d3d0fcb86 # v5`）。

### Task 1: uv プロジェクト scaffold と tool_refs（ツール名検証の純粋関数）

**Files:**
- Create: `scripts/config-guard/pyproject.toml`
- Create: `scripts/config-guard/src/config_guard/__init__.py`（空）
- Create: `scripts/config-guard/src/config_guard/tool_refs.py`
- Create: `scripts/config-guard/tests/__init__.py`（空）
- Create: `scripts/config-guard/tests/test_tool_refs.py`

**Interfaces:**
- Produces: `config_guard.tool_refs.validate_tool_token(token: str) -> str | None`（None=妥当、str=違反理由）。定数 `LEGACY_MCP_PREFIXES: tuple[str, ...]`、`KNOWN_BAD_NAMES: frozenset[str]`。

- [ ] **Step 1: pyproject.toml を作成する**

```toml
[project]
name = "config-guard"
version = "0.1.0"
description = "skills と committed settings.json の stale なツール名参照・構造逸脱を検出する静的ガード"
readme = "README.md"
requires-python = ">=3.12"
license = { text = "MIT" }
authors = [{ name = "Hidari" }]
dependencies = []

[project.scripts]
config-guard = "config_guard.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/config_guard"]

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

- [ ] **Step 2: README.md を作成する（hatchling が readme を要求するため最小限）**

`scripts/config-guard/README.md`:

```markdown
# config-guard

skills の `allowed-tools` と committed `home/.claude/settings.json` の stale な
ツール名参照・構造逸脱を静的検出するリポジトリ内ツール。

```bash
uv run config-guard /path/to/repo-root
```

検出が 1 件以上あれば非ゼロ終了する。CI（test.yml）と pre-commit から呼ばれる。
```

- [ ] **Step 3: 空の `__init__.py` を 2 つ作成する**

`src/config_guard/__init__.py` と `tests/__init__.py` をそれぞれ空ファイルで作成する。

- [ ] **Step 4: 失敗するテストを書く** (`tests/test_tool_refs.py`)

```python
"""tool_refs.validate_tool_token の仕様テスト。"""

from __future__ import annotations

from config_guard.tool_refs import validate_tool_token


class TestValidTokens:
    def test_builtin_bare(self) -> None:
        assert validate_tool_token("Read") is None

    def test_builtin_all_caps(self) -> None:
        # LS のような全大文字の実在ツール名も shape で通す
        assert validate_tool_token("LS") is None

    def test_builtin_with_specifier(self) -> None:
        assert validate_tool_token("Bash(git *)") is None

    def test_builtin_with_glob_specifier(self) -> None:
        assert validate_tool_token("Read(.hidari/**)") is None

    def test_mcp_plugin_form(self) -> None:
        token = "mcp__plugin_chrome-devtools-mcp_chrome-devtools__take_snapshot"
        assert validate_tool_token(token) is None

    def test_mcp_non_plugin_form(self) -> None:
        assert validate_tool_token("mcp__claude_ai_Gmail__authenticate") is None

    def test_notebook_read_is_valid(self) -> None:
        # NotebookRead は実在ツール名（allowlist 照合しないため shape で通る）
        assert validate_tool_token("NotebookRead") is None


class TestInvalidTokens:
    def test_legacy_un_prefixed_mcp(self) -> None:
        reason = validate_tool_token("mcp__chrome-devtools__navigate_page")
        assert reason is not None
        assert "legacy" in reason

    def test_legacy_claude_in_chrome(self) -> None:
        assert validate_tool_token("mcp__claude-in-chrome__open") is not None

    def test_known_bad_git(self) -> None:
        reason = validate_tool_token("Git")
        assert reason is not None
        assert "実在しない" in reason

    def test_known_typo_notebool_edit(self) -> None:
        reason = validate_tool_token("NoteboolEdit")
        assert reason is not None
        assert "実在しない" in reason

    def test_empty(self) -> None:
        assert validate_tool_token("") is not None

    def test_lowercase_garbage(self) -> None:
        reason = validate_tool_token("git")
        assert reason is not None
        assert "不正な形" in reason
```

- [ ] **Step 5: テストを実行して失敗を確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_tool_refs.py -q`
Expected: FAIL（`ModuleNotFoundError: config_guard.tool_refs` または import エラー）

- [ ] **Step 6: tool_refs.py を実装する**

```python
"""ツール名トークンの妥当性を判定する純粋関数。

Hybrid 方式: 既知の legacy/誤名を denylist で弾き、それ以外は形（shape）だけ
検証する。built-in 名の完全 allowlist 照合はしない（Claude Code のツール追加で
検証器が drift しないため）。
"""

from __future__ import annotations

import re

# plugin 化で legacy 化した un-prefixed MCP server。新たな移行時にここへ 1 行追加する。
LEGACY_MCP_PREFIXES: tuple[str, ...] = (
    "mcp__chrome-devtools__",
    "mcp__claude-in-chrome__",
)

# 既知の誤名・タイポ。実在しない bare ツール名。再混入防止のため列挙する。
KNOWN_BAD_NAMES: frozenset[str] = frozenset({"Git", "NoteboolEdit"})

# MCP ツール形: mcp__<server>__<tool>（plugin 形・非 plugin 形の双方を許容）
_MCP_SHAPE = re.compile(r"^mcp__[A-Za-z0-9_-]+__[A-Za-z0-9_]+$")

# built-in 形: 英大文字始まりのツール名ヘッド + 任意の (...) permission specifier
_BUILTIN_SHAPE = re.compile(r"^[A-Z][A-Za-z0-9]*(\(.*\))?$")


def validate_tool_token(token: str) -> str | None:
    """ツール名トークン 1 個を検証する。妥当なら None、問題があれば理由を返す。"""
    stripped = token.strip()
    if not stripped:
        return "空のツール名"
    for prefix in LEGACY_MCP_PREFIXES:
        if stripped.startswith(prefix):
            return f"legacy な未 prefix MCP ツール名（plugin 形へ移行済み）: {stripped}"
    if stripped in KNOWN_BAD_NAMES:
        return f"実在しないツール名: {stripped}"
    if _MCP_SHAPE.match(stripped) or _BUILTIN_SHAPE.match(stripped):
        return None
    return f"不正な形のツール名: {stripped}"
```

- [ ] **Step 7: テストを実行して通過を確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_tool_refs.py -q`
Expected: PASS（13 tests）

- [ ] **Step 8: lint / format / type を確認する**

Run:
```bash
uv run --directory scripts/config-guard ruff check src tests
uv run --directory scripts/config-guard ruff format src tests
uv run --directory scripts/config-guard mypy src tests
```
Expected: ruff PASS、format で整形、mypy `Success`

- [ ] **Step 9: commit**

```bash
git add scripts/config-guard/pyproject.toml scripts/config-guard/README.md \
  scripts/config-guard/uv.lock \
  scripts/config-guard/src/config_guard/__init__.py \
  scripts/config-guard/src/config_guard/tool_refs.py \
  scripts/config-guard/tests/__init__.py scripts/config-guard/tests/test_tool_refs.py
git commit -m "feat: config-guard の scaffold と tool_refs 検証器を追加

Claude-Session: https://claude.ai/code/session_01LfXRyn6J2VWYgQmVw2npso"
```
注意: `uv run` が初回に `.venv` と `uv.lock` を生成する。`.venv` / キャッシュ類はグローバル gitignore で除外される。`git status` で `uv.lock` のみが追跡対象になることを確認する。

### Task 2: models.Finding と extractors（トークン抽出）

**Files:**
- Create: `scripts/config-guard/src/config_guard/models.py`
- Create: `scripts/config-guard/src/config_guard/extractors.py`
- Create: `scripts/config-guard/tests/test_extractors.py`

**Interfaces:**
- Produces: `config_guard.models.Finding`（frozen dataclass: `source: str`, `detail: str`, `message: str`）。
- Produces: `config_guard.extractors.extract_skill_tokens(skill_md: str) -> list[str]`、`config_guard.extractors.extract_settings_permission_tokens(settings: dict[str, Any]) -> list[str]`。

- [ ] **Step 1: 失敗するテストを書く** (`tests/test_extractors.py`)

```python
"""extractors のトークン抽出仕様テスト。"""

from __future__ import annotations

from config_guard.extractors import (
    extract_settings_permission_tokens,
    extract_skill_tokens,
)

SKILL_WITH_TOOLS = """\
---
name: sample
description: サンプル
allowed-tools:
  - Read
  - Bash(git *)
  - mcp__plugin_chrome-devtools-mcp_chrome-devtools__take_snapshot
---

本文
"""

SKILL_NO_TOOLS = """\
---
name: sample
description: allowed-tools を持たない skill
---

本文
"""

SKILL_TOOLS_NOT_LAST = """\
---
name: sample
allowed-tools:
  - Read
  - Write
description: allowed-tools の後に別キーがある
---
"""


class TestExtractSkillTokens:
    def test_extracts_list(self) -> None:
        assert extract_skill_tokens(SKILL_WITH_TOOLS) == [
            "Read",
            "Bash(git *)",
            "mcp__plugin_chrome-devtools-mcp_chrome-devtools__take_snapshot",
        ]

    def test_empty_when_absent(self) -> None:
        assert extract_skill_tokens(SKILL_NO_TOOLS) == []

    def test_stops_at_next_key(self) -> None:
        assert extract_skill_tokens(SKILL_TOOLS_NOT_LAST) == ["Read", "Write"]

    def test_empty_when_no_frontmatter(self) -> None:
        assert extract_skill_tokens("# 本文だけ\n") == []


class TestExtractSettingsPermissionTokens:
    def test_collects_allow_deny_ask(self) -> None:
        settings = {
            "permissions": {
                "allow": ["Bash(cat:*)", "WebSearch"],
                "deny": ["NoteboolEdit"],
                "ask": ["Bash(git commit:*)"],
            }
        }
        assert extract_settings_permission_tokens(settings) == [
            "Bash(cat:*)",
            "WebSearch",
            "NoteboolEdit",
            "Bash(git commit:*)",
        ]

    def test_empty_when_no_permissions(self) -> None:
        assert extract_settings_permission_tokens({}) == []
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_extractors.py -q`
Expected: FAIL（import エラー）

- [ ] **Step 3: models.py を実装する**

```python
"""検出結果を表す値型。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    """1 件の検出。source は検出元、detail は該当トークン/キー、message は理由。"""

    source: str
    detail: str
    message: str
```

- [ ] **Step 4: extractors.py を実装する**

```python
"""検査対象からツール名トークンを抽出する。

SKILL.md は frontmatter の allowed-tools リスト（フラットなリスト）を標準ライブラリ
だけで抽出する（YAML パーサ依存を避ける）。settings.json は dict から permissions を
取り出す。
"""

from __future__ import annotations

import re
from typing import Any

_FRONTMATTER_DELIM = re.compile(r"^---\s*$")
_ALLOWED_TOOLS_KEY = re.compile(r"^allowed-tools\s*:")
_LIST_ITEM = re.compile(r"^\s*-\s+(.+?)\s*$")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def extract_skill_tokens(skill_md: str) -> list[str]:
    """SKILL.md の frontmatter から allowed-tools のツール名を抽出する。無ければ空。"""
    lines = skill_md.splitlines()
    delims = [i for i, ln in enumerate(lines) if _FRONTMATTER_DELIM.match(ln)]
    if len(delims) < 2:
        return []
    front = lines[delims[0] + 1 : delims[1]]
    tokens: list[str] = []
    in_block = False
    for ln in front:
        if _ALLOWED_TOOLS_KEY.match(ln):
            in_block = True
            continue
        if in_block:
            item = _LIST_ITEM.match(ln)
            if item:
                tokens.append(_unquote(item.group(1)))
            elif ln.strip() == "":
                continue
            else:
                break
    return tokens


def extract_settings_permission_tokens(settings: dict[str, Any]) -> list[str]:
    """settings.json の permissions.{allow,deny,ask} の全トークンを抽出する。"""
    perms = settings.get("permissions", {})
    tokens: list[str] = []
    if isinstance(perms, dict):
        for key in ("allow", "deny", "ask"):
            value = perms.get(key, [])
            if isinstance(value, list):
                tokens.extend(str(token) for token in value)
    return tokens
```

- [ ] **Step 5: テストを実行して通過を確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_extractors.py -q`
Expected: PASS（6 tests）

- [ ] **Step 6: lint / format / type を確認する**

Run:
```bash
uv run --directory scripts/config-guard ruff check src tests
uv run --directory scripts/config-guard ruff format src tests
uv run --directory scripts/config-guard mypy src tests
```
Expected: 全て PASS

- [ ] **Step 7: commit**

```bash
git add scripts/config-guard/src/config_guard/models.py \
  scripts/config-guard/src/config_guard/extractors.py \
  scripts/config-guard/tests/test_extractors.py
git commit -m "feat: config-guard に Finding 値型と token 抽出器を追加

Claude-Session: https://claude.ai/code/session_01LfXRyn6J2VWYgQmVw2npso"
```

### Task 3: git_source（committed settings.json を git から読む）

**Files:**
- Create: `scripts/config-guard/src/config_guard/git_source.py`
- Create: `scripts/config-guard/tests/test_git_source.py`

**Interfaces:**
- Produces: `config_guard.git_source.read_committed_settings(repo_root: str) -> dict[str, Any]`、定数 `SETTINGS_PATH = "home/.claude/settings.json"`。

- [ ] **Step 1: 失敗するテストを書く** (`tests/test_git_source.py`)

実際の一時 git リポジトリを使う（モック禁止）。staged / HEAD / working で内容を変え、staged 優先かつ working を読まないことを検証する。

```python
"""git_source の仕様テスト。working tree を読まないことを実 git リポで検証する。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from config_guard.git_source import SETTINGS_PATH, read_committed_settings


def _run(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _init_repo(repo: Path) -> None:
    _run(repo, "init", "-q")
    _run(repo, "config", "user.email", "test@example.com")
    _run(repo, "config", "user.name", "test")


def _write_settings(repo: Path, payload: dict[str, object]) -> None:
    path = repo / SETTINGS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_prefers_staged_over_head_and_ignores_working(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    # HEAD には head 版を commit
    _write_settings(tmp_path, {"marker": "head"})
    _run(tmp_path, "add", SETTINGS_PATH)
    _run(tmp_path, "commit", "-q", "-m", "head")
    # index には staged 版を stage
    _write_settings(tmp_path, {"marker": "staged"})
    _run(tmp_path, "add", SETTINGS_PATH)
    # working tree には working 版（stage しない）
    _write_settings(tmp_path, {"marker": "working"})

    result = read_committed_settings(str(tmp_path))
    assert result == {"marker": "staged"}


def test_falls_back_to_head_when_index_matches(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write_settings(tmp_path, {"marker": "head"})
    _run(tmp_path, "add", SETTINGS_PATH)
    _run(tmp_path, "commit", "-q", "-m", "head")
    # index は HEAD と同一、working だけ変更（stage しない）
    _write_settings(tmp_path, {"marker": "working"})

    result = read_committed_settings(str(tmp_path))
    assert result == {"marker": "head"}


def test_raises_when_absent(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    _write_settings(tmp_path, {"marker": "x"})
    _run(tmp_path, "add", "home")
    _run(tmp_path, "commit", "-q", "-m", "init")
    _run(tmp_path, "rm", "-q", SETTINGS_PATH)

    try:
        read_committed_settings(str(tmp_path))
    except RuntimeError:
        pass
    else:
        raise AssertionError("RuntimeError が送出されるべき")
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_git_source.py -q`
Expected: FAIL（import エラー）

- [ ] **Step 3: git_source.py を実装する**

```python
"""committed（staged を優先し HEAD にフォールバック）な settings.json を git から読む。

settings.json は skip-worktree のため working tree = live superset である。
working file を読むと個人トグルや /Users パスを誤検出するため、必ず git から読む。
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

SETTINGS_PATH = "home/.claude/settings.json"


def _git_show(repo_root: str, ref: str) -> str | None:
    proc = subprocess.run(
        ["git", "-C", repo_root, "show", ref],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def read_committed_settings(repo_root: str) -> dict[str, Any]:
    """staged → HEAD の順で settings.json を取得して JSON として返す。

    working tree は決して読まない。両方失敗したら RuntimeError。
    """
    for ref in (f":{SETTINGS_PATH}", f"HEAD:{SETTINGS_PATH}"):
        content = _git_show(repo_root, ref)
        if content is not None:
            parsed: dict[str, Any] = json.loads(content)
            return parsed
    raise RuntimeError(
        f"git から {SETTINGS_PATH} を取得できませんでした（staged/HEAD 双方失敗）"
    )
```

- [ ] **Step 4: テストを実行して通過を確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_git_source.py -q`
Expected: PASS（3 tests）

- [ ] **Step 5: lint / format / type を確認する**

Run:
```bash
uv run --directory scripts/config-guard ruff check src tests
uv run --directory scripts/config-guard ruff format src tests
uv run --directory scripts/config-guard mypy src tests
```
Expected: 全て PASS

- [ ] **Step 6: commit**

```bash
git add scripts/config-guard/src/config_guard/git_source.py \
  scripts/config-guard/tests/test_git_source.py
git commit -m "feat: config-guard に committed settings.json の git 読み取りを追加

Claude-Session: https://claude.ai/code/session_01LfXRyn6J2VWYgQmVw2npso"
```

### Task 4: settings_invariants（committed settings.json の構造不変条件）

**Files:**
- Create: `scripts/config-guard/src/config_guard/settings_invariants.py`
- Create: `scripts/config-guard/tests/test_settings_invariants.py`

**Interfaces:**
- Consumes: `Finding`（models）、`validate_tool_token`（tool_refs）、`extract_settings_permission_tokens`（extractors）。
- Produces: `config_guard.settings_invariants.check_settings_invariants(settings: dict[str, Any]) -> list[Finding]`。

- [ ] **Step 1: 失敗するテストを書く** (`tests/test_settings_invariants.py`)

```python
"""settings_invariants の仕様テスト。"""

from __future__ import annotations

from typing import Any

from config_guard.settings_invariants import check_settings_invariants

GOOD: dict[str, Any] = {
    "permissions": {
        "allow": ["Bash(cat:*)", "WebSearch"],
        "deny": ["NotebookRead"],
        "ask": ["Bash(git commit:*)"],
    },
    "extraKnownMarketplaces": {
        "superpowers-marketplace": {
            "source": {"source": "github", "repo": "obra/superpowers-marketplace"}
        }
    },
    "enabledPlugins": {
        "feature-dev@claude-plugins-official": True,
        "superpowers@superpowers-marketplace": True,
    },
}


class TestGood:
    def test_clean_settings_has_no_findings(self) -> None:
        assert check_settings_invariants(GOOD) == []


class TestInvariantViolations:
    def test_forbidden_key_enabled_mcp_servers(self) -> None:
        settings = {**GOOD, "enabledMcpjsonServers": ["chrome-devtools"]}
        findings = check_settings_invariants(settings)
        assert any(f.detail == "enabledMcpjsonServers" for f in findings)

    def test_user_absolute_path(self) -> None:
        settings = {
            **GOOD,
            "extraKnownMarketplaces": {
                "hidari-plugins": {
                    "source": {"source": "directory", "path": "/Users/example/x"}
                }
            },
        }
        findings = check_settings_invariants(settings)
        # ユーザーパス かつ directory marketplace の双方が検出される
        assert any("絶対パス" in f.message for f in findings)
        assert any("directory" in f.message for f in findings)

    def test_non_public_marketplace_plugin(self) -> None:
        settings = {
            **GOOD,
            "enabledPlugins": {"security@hidari-plugins": True},
        }
        findings = check_settings_invariants(settings)
        assert any("hidari-plugins" in f.detail for f in findings)

    def test_invalid_permission_tool_name(self) -> None:
        settings = {**GOOD, "permissions": {"deny": ["NoteboolEdit"]}}
        findings = check_settings_invariants(settings)
        assert any(f.detail == "NoteboolEdit" for f in findings)
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_settings_invariants.py -q`
Expected: FAIL（import エラー）

- [ ] **Step 3: settings_invariants.py を実装する**

```python
"""committed settings.json の構造不変条件を検証する。

セキュリティ・正当性に絞ったハードフェイルのみ。個人の好み（通知トグル等）は咎めない。
"""

from __future__ import annotations

import re
from typing import Any

from config_guard.extractors import extract_settings_permission_tokens
from config_guard.models import Finding
from config_guard.tool_refs import validate_tool_token

_SRC = "settings.json (committed)"

# committed に含めてはならないキー（PR #22 で消した dead config 等）
_FORBIDDEN_KEYS: tuple[str, ...] = ("enabledMcpjsonServers",)

# ユーザーのローカル絶対パス（gitleaks との多層防御）
_USER_PATH = re.compile(r"/(Users|home)/[a-z_][a-z0-9._-]*")

# committed に許可する公開 marketplace。ここに無い marketplace を参照する plugin は弾く。
_PUBLIC_MARKETPLACES: frozenset[str] = frozenset(
    {
        "claude-plugins-official",
        "superpowers-marketplace",
        "googlechrome",
        "chrome-devtools-plugins",
    }
)


def _iter_strings(obj: Any) -> list[str]:
    out: list[str] = []
    if isinstance(obj, str):
        out.append(obj)
    elif isinstance(obj, dict):
        for value in obj.values():
            out.extend(_iter_strings(value))
    elif isinstance(obj, list):
        for value in obj:
            out.extend(_iter_strings(value))
    return out


def check_settings_invariants(settings: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []

    # 1. 禁止キー
    for key in _FORBIDDEN_KEYS:
        if key in settings:
            findings.append(Finding(_SRC, key, f"committed に含めてはならないキー: {key}"))

    # 2. ユーザー絶対パス
    for text in _iter_strings(settings):
        if _USER_PATH.search(text):
            findings.append(Finding(_SRC, text, "ユーザーのローカル絶対パスを含む"))

    # 3. directory source の marketplace
    markets = settings.get("extraKnownMarketplaces", {})
    if isinstance(markets, dict):
        for name, spec in markets.items():
            source = spec.get("source", {}) if isinstance(spec, dict) else {}
            if isinstance(source, dict) and source.get("source") == "directory":
                findings.append(
                    Finding(_SRC, name, f"directory source の marketplace: {name}")
                )

    # 4. 非公開 marketplace を参照する plugin
    plugins = settings.get("enabledPlugins", {})
    if isinstance(plugins, dict):
        for plugin_key in plugins:
            if "@" in plugin_key:
                market = plugin_key.split("@", 1)[1]
                if market not in _PUBLIC_MARKETPLACES:
                    findings.append(
                        Finding(_SRC, plugin_key, f"非公開 marketplace を参照する plugin: {market}")
                    )

    # 5. permissions のツール名妥当性
    for token in extract_settings_permission_tokens(settings):
        reason = validate_tool_token(token)
        if reason is not None:
            findings.append(Finding(_SRC, token, reason))

    return findings
```

- [ ] **Step 4: テストを実行して通過を確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_settings_invariants.py -q`
Expected: PASS（5 tests）

- [ ] **Step 5: lint / format / type を確認する**

Run:
```bash
uv run --directory scripts/config-guard ruff check src tests
uv run --directory scripts/config-guard ruff format src tests
uv run --directory scripts/config-guard mypy src tests
```
Expected: 全て PASS

- [ ] **Step 6: commit**

```bash
git add scripts/config-guard/src/config_guard/settings_invariants.py \
  scripts/config-guard/tests/test_settings_invariants.py
git commit -m "feat: config-guard に committed settings.json 不変条件検証を追加

Claude-Session: https://claude.ai/code/session_01LfXRyn6J2VWYgQmVw2npso"
```

### Task 5: cli（リポジトリ全体のスキャンと終了コード）

**Files:**
- Create: `scripts/config-guard/src/config_guard/cli.py`
- Create: `scripts/config-guard/src/config_guard/__main__.py`
- Create: `scripts/config-guard/tests/test_cli.py`

**Interfaces:**
- Consumes: `Finding`、`validate_tool_token`、`extract_skill_tokens`、`read_committed_settings`、`check_settings_invariants`。
- Produces: `config_guard.cli.scan(repo_root: str) -> list[Finding]`、`config_guard.cli.main(argv: list[str] | None = None) -> int`、定数 `SKILLS_GLOB`。

- [ ] **Step 1: 失敗するテストを書く** (`tests/test_cli.py`)

実 git リポジトリを組み立て、good で空・bad で検出されることを検証する。

```python
"""cli.scan の統合テスト。実 git リポジトリで検証する。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from config_guard.cli import scan

GOOD_SETTINGS = {
    "permissions": {"allow": ["Bash(cat:*)"], "deny": ["NotebookRead"], "ask": []},
    "enabledPlugins": {"feature-dev@claude-plugins-official": True},
}

GOOD_SKILL = """\
---
name: good
allowed-tools:
  - Read
  - Bash(git *)
---
本文
"""

BAD_SKILL = """\
---
name: bad
allowed-tools:
  - Git
  - mcp__chrome-devtools__navigate_page
---
本文
"""


def _run(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)


def _make_repo(tmp_path: Path, skill_name: str, skill_body: str, settings: dict) -> Path:
    repo = tmp_path
    _run(repo, "init", "-q")
    _run(repo, "config", "user.email", "t@example.com")
    _run(repo, "config", "user.name", "t")
    settings_path = repo / "home/.claude/settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings), encoding="utf-8")
    skill_path = repo / f"home/.claude/skills/{skill_name}/SKILL.md"
    skill_path.parent.mkdir(parents=True, exist_ok=True)
    skill_path.write_text(skill_body, encoding="utf-8")
    _run(repo, "add", "-A")
    _run(repo, "commit", "-q", "-m", "init")
    return repo


def test_clean_repo_has_no_findings(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, GOOD_SETTINGS)
    assert scan(str(repo)) == []


def test_bad_skill_is_detected(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path, "bad", BAD_SKILL, GOOD_SETTINGS)
    findings = scan(str(repo))
    details = {f.detail for f in findings}
    assert "Git" in details
    assert "mcp__chrome-devtools__navigate_page" in details


def test_bad_settings_is_detected(tmp_path: Path) -> None:
    bad_settings = {**GOOD_SETTINGS, "enabledMcpjsonServers": ["x"]}
    repo = _make_repo(tmp_path, "good", GOOD_SKILL, bad_settings)
    findings = scan(str(repo))
    assert any(f.detail == "enabledMcpjsonServers" for f in findings)
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_cli.py -q`
Expected: FAIL（import エラー）

- [ ] **Step 3: cli.py を実装する**

```python
"""リポジトリをスキャンして stale なツール名参照と settings.json の逸脱を検出する。"""

from __future__ import annotations

import glob
import sys
from pathlib import Path

from config_guard.extractors import extract_skill_tokens
from config_guard.git_source import read_committed_settings
from config_guard.models import Finding
from config_guard.settings_invariants import check_settings_invariants
from config_guard.tool_refs import validate_tool_token

SKILLS_GLOB = "home/.claude/skills/*/SKILL.md"


def scan(repo_root: str) -> list[Finding]:
    """skills の allowed-tools と committed settings.json を検査する。"""
    root = Path(repo_root).resolve()
    findings: list[Finding] = []

    # skills の allowed-tools
    for skill_path in sorted(glob.glob(str(root / SKILLS_GLOB))):
        text = Path(skill_path).read_text(encoding="utf-8")
        rel = str(Path(skill_path).relative_to(root))
        for token in extract_skill_tokens(text):
            reason = validate_tool_token(token)
            if reason is not None:
                findings.append(Finding(rel, token, reason))

    # committed settings.json の不変条件（permissions のツール名検証を含む）
    settings = read_committed_settings(str(root))
    findings.extend(check_settings_invariants(settings))

    return findings


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    repo_root = args[0] if args else "."
    findings = scan(repo_root)
    if not findings:
        print("config-guard: 問題は検出されませんでした")
        return 0
    for finding in findings:
        print(f"config-guard: {finding.source}: {finding.message} [{finding.detail}]")
    print(f"config-guard: {len(findings)} 件の問題を検出しました")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: __main__.py を実装する**

```python
"""python -m config_guard のエントリ。"""

from __future__ import annotations

from config_guard.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 5: テストを実行して通過を確認する**

Run: `uv run --directory scripts/config-guard pytest tests/test_cli.py -q`
Expected: PASS（3 tests）

- [ ] **Step 6: 全テスト + lint / format / type を確認する**

Run:
```bash
uv run --directory scripts/config-guard ruff check src tests
uv run --directory scripts/config-guard ruff format src tests
uv run --directory scripts/config-guard mypy src tests
uv run --directory scripts/config-guard pytest -q
```
Expected: 全て PASS（合計 30 tests）

- [ ] **Step 7: commit**

```bash
git add scripts/config-guard/src/config_guard/cli.py \
  scripts/config-guard/src/config_guard/__main__.py \
  scripts/config-guard/tests/test_cli.py
git commit -m "feat: config-guard の CLI スキャナを追加

Claude-Session: https://claude.ai/code/session_01LfXRyn6J2VWYgQmVw2npso"
```

### Task 6: committed settings.json の NoteboolEdit タイポ修正

committed settings.json は skip-worktree のため、working file を触らず index の blob だけを差し替える。一時ファイルは 3 step で同一の決定的パスを使う（実行時はセッションのスクラッチパッド配下に置いてもよいが、3 step で同じパスを参照すること）。

**Files:**
- Modify（index blob のみ）: `home/.claude/settings.json`（deny の `NoteboolEdit` → `NotebookEdit`）

- [ ] **Step 1: committed blob を取得して差分対象を確認する**

```bash
cd ~/Develop/dotfiles
TMP_SETTINGS="${TMPDIR:-/tmp}/config-guard-settings.json"
git show HEAD:home/.claude/settings.json > "$TMP_SETTINGS"
grep -n 'NoteboolEdit' "$TMP_SETTINGS"
```
Expected: `NoteboolEdit` が deny 配列に 1 件ある。

- [ ] **Step 2: タイポだけを修正する（他は一切変更しない）**

`${TMPDIR:-/tmp}/config-guard-settings.json` の `"NoteboolEdit"` を `"NotebookEdit"` に置換する（Edit ツールで 1 箇所のみ）。`NotebookRead` は変更しない。

- [ ] **Step 3: 新 blob を object store へ登録し index を差し替える**

```bash
cd ~/Develop/dotfiles
TMP_SETTINGS="${TMPDIR:-/tmp}/config-guard-settings.json"
SHA=$(git hash-object -w "$TMP_SETTINGS")
git update-index --cacheinfo 100644,"$SHA",home/.claude/settings.json
```

- [ ] **Step 4: staged diff を検証する（NoteboolEdit→NotebookEdit のみであること）**

```bash
git diff --cached home/.claude/settings.json
```
Expected: 1 行の置換（`-      "NoteboolEdit",` / `+      "NotebookEdit",`）のみ。他の差分が出たら中止して調査する。

- [ ] **Step 5: commit して skip-worktree を再設定する**

```bash
git commit -m "fix: committed settings.json の deny の NoteboolEdit タイポを修正

実在しないツール名 NoteboolEdit を NotebookEdit に修正。config-guard が
検出する invalid ツール名であり、修正しないと CI が落ちる。working file は
skip-worktree のため触らず index blob のみ差し替えた。

Claude-Session: https://claude.ai/code/session_01LfXRyn6J2VWYgQmVw2npso"
git update-index --skip-worktree home/.claude/settings.json
```

- [ ] **Step 6: working file が無傷で skip-worktree が効いていることを確認する**

```bash
git ls-files -v home/.claude/settings.json   # 先頭が S なら skip-worktree 有効
git status -sb                                # settings.json が変更扱いされていないこと
```
Expected: 先頭フラグ `S`、status に settings.json が出ない。

- [ ] **Step 7: 実リポジトリで config-guard が緑になることを確認する**

```bash
uv run --directory scripts/config-guard config-guard .
echo "exit: $?"
```
Expected: `config-guard: 問題は検出されませんでした` / exit 0。
（注: cli は committed settings.json を git の index/HEAD から読むため、Step 5 commit 後は NotebookEdit 版が検査される。）

### Task 7: CI（test.yml）と pre-commit への配線

**Files:**
- Modify: `.github/workflows/test.yml`（config-guard job を追加）
- Modify: `.pre-commit-config.yaml`（config-guard の lint/test/scan フックを追加）

- [ ] **Step 1: test.yml に config-guard job を追加する**

`gitleaks` job の後（末尾）に以下を追加する。インデントは既存 job に合わせる。

```yaml
  config-guard:
    name: config-guard (python)
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: scripts/config-guard
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

      # リポジトリ全体に対して guard を実行する（cwd は scripts/config-guard、引数は repo root）
      - name: Run config-guard on repo
        run: uv run config-guard ../..
```

- [ ] **Step 2: pre-commit に config-guard フックを追加する**

`.pre-commit-config.yaml` の `gitleaks` フックの前（`repo: local` の hooks 配列内）に以下を追加する。

```yaml
      - id: config-guard-ruff-check
        name: config-guard ruff check
        language: system
        entry: uv run --directory scripts/config-guard ruff check src tests
        pass_filenames: false
        files: ^scripts/config-guard/(src|tests)/.*\.py$

      - id: config-guard-ruff-format
        name: config-guard ruff format --check
        language: system
        entry: uv run --directory scripts/config-guard ruff format --check src tests
        pass_filenames: false
        files: ^scripts/config-guard/(src|tests)/.*\.py$

      - id: config-guard-mypy
        name: config-guard mypy
        language: system
        entry: uv run --directory scripts/config-guard mypy src tests
        pass_filenames: false
        files: ^scripts/config-guard/(src|tests)/.*\.py$

      - id: config-guard-pytest
        name: config-guard pytest
        language: system
        entry: uv run --directory scripts/config-guard pytest -q
        pass_filenames: false
        files: ^scripts/config-guard/(src|tests)/.*\.py$

      - id: config-guard-scan
        name: config-guard scan (tool refs / settings invariants)
        language: system
        entry: bash -c 'uv run --directory scripts/config-guard config-guard "$(git rev-parse --show-toplevel)"'
        pass_filenames: false
        files: ^(home/\.claude/skills/.*/SKILL\.md|home/\.claude/settings\.json|scripts/config-guard/.*)$
```

- [ ] **Step 3: pre-commit フックをローカルで実行して確認する**

```bash
cd ~/Develop/dotfiles
pre-commit run config-guard-scan --all-files
pre-commit run config-guard-pytest --all-files
```
Expected: いずれも Passed。

- [ ] **Step 4: CI workflow の YAML 妥当性をローカル検証する（任意）**

```bash
python3 -c "import sys,yaml" 2>/dev/null && python3 -c "import yaml; yaml.safe_load(open('.github/workflows/test.yml'))" && echo "yaml ok" || echo "(pyyaml 無し: スキップ)"
```

- [ ] **Step 5: commit**

```bash
git add .github/workflows/test.yml .pre-commit-config.yaml
git commit -m "ci: config-guard を test.yml と pre-commit に追加

Claude-Session: https://claude.ai/code/session_01LfXRyn6J2VWYgQmVw2npso"
```

### Task 8: README に skip-worktree 契約を明記する

**Files:**
- Modify: `README.md`（新セクションを追加）
- Modify: `README.md` の Testing セクション（config-guard のテストコマンドを追記）

- [ ] **Step 1: skip-worktree 契約セクションを追加する**

`README.md` の Dotfiles テーブルの後（`Additionally, ...` の段落の後）に以下を追加する。

```markdown
## Claude Code 設定の管理 (skip-worktree 契約)

`home/.claude/settings.json` は `git update-index --skip-worktree` で管理しており、二重の状態を持つ。

- committed (HEAD): 公開して安全な curated subset。`/Users/<name>` パス・個人トグル・ローカル marketplace を含まない。
- working tree (`~/.claude/settings.json` の symlink 実体): 個人環境の live superset。

ローカル固有の設定を commit に混ぜないため、committed 側だけを編集するときは working file を触らず index の blob を差し替える。

```bash
# committed blob を取り出して編集し、index だけ差し替える
git show HEAD:home/.claude/settings.json > /tmp/settings.json
# /tmp/settings.json を編集
SHA=$(git hash-object -w /tmp/settings.json)
git update-index --cacheinfo 100644,"$SHA",home/.claude/settings.json
git diff --cached home/.claude/settings.json   # 差分検証
git commit -m "..."
git update-index --skip-worktree home/.claude/settings.json
```

committed 側は CI で 2 つの仕組みが守る。

- gitleaks: secret とユーザー名パス (`/Users/<name>`) の漏洩を検出する。
- config-guard: 構造 curation（禁止キー・directory marketplace・dead config・不正なツール名）を検出する。
```

- [ ] **Step 2: Testing セクションに config-guard を追記する**

`README.md` の Testing セクションの末尾コードブロックに以下を追記する。

```bash
# config-guard (Python / pytest)
uv run --directory scripts/config-guard pytest -q

# config-guard スキャン (skills + settings の stale 参照検出)
uv run --directory scripts/config-guard config-guard .
```

- [ ] **Step 3: gitleaks をローカルで確認する（README に /Users literal を入れていないこと）**

```bash
cd ~/Develop/dotfiles
git add README.md
gitleaks git --staged --redact --no-banner -c .gitleaks.toml && echo "gitleaks ok"
```
Expected: leaks found 0。（README には `/Users/<name>` プレースホルダのみで実ユーザー名を書かないこと。`/tmp/settings.json` の例も実ユーザー名を含まない。）

- [ ] **Step 4: commit**

```bash
git commit -m "docs: README に settings.json の skip-worktree 契約を明記

Claude-Session: https://claude.ai/code/session_01LfXRyn6J2VWYgQmVw2npso"
```

## 完了後の検証（全タスク後）

- [ ] `bats scripts/tests/` が緑。
- [ ] `uv run --directory scripts/config-guard pytest -q` が緑（30 tests）。
- [ ] `uv run --directory scripts/config-guard config-guard .` が exit 0。
- [ ] `pre-commit run --all-files` が全 Passed。
- [ ] PR を作成し（`gh pr create --assignee @me --base main --fill`）、本文に `Closes` で issue #1・#2 への相対パスリンクを記載する。
- [ ] pre-merge-quality-gate skill を通す。
- [ ] CI 結論を `gh pr view <n> --json statusCheckRollup` で直接確認する。

## Self-Review メモ（spec との対応）

- issue #1（stale 参照 CI ガード）: Task 1（validator）、Task 2（抽出）、Task 5（cli, skills + settings 両対応）、Task 7（CI/pre-commit）。
- issue #2（settings.json 二重管理）: Task 3（git-source 規約）、Task 4（committed 不変条件）、Task 6（NoteboolEdit 修正）、Task 8（README 契約）。
- Hybrid 検出ロジック: Task 1 の denylist + shape。allowlist 完全照合をしないため `LS`/`NotebookRead` を通すテストを含む。
- working file を読まない規約: Task 3 で staged/HEAD/working を変えた実 git リポで検証。
- 既知のトレードオフ（novel typo の見逃し / plugin 実在性の非検証）は spec に記載済みで本計画のスコープ外。
</content>
