# session-handoff Skill + handoff-sentinel Hook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** コンテキスト超過・ツール呼び出し破損・手動依頼の3経路で引き継ぎ書を `<リポルート>/tmp/handoff.md` に書き出し、新セッションの SessionStart で自動注入する user (マシン) スコープ機構を作る。

**Architecture:** 検知は単一 hook スクリプト `handoff-sentinel.py` (第1引数 `posttool` / `stop` / `session` で分岐、全経路 fail-safe exit 0)、手順は skill `session-handoff`、書式は同梱 `template.md` が canonical。テストは tirith-hook と同じ黒箱統合テスト (subprocess 起動、stdin JSON → stdout JSON / exit code の exact 検証、モック不使用)。

**Tech Stack:** Python 3.12+ (stdlib のみ)、uv + ruff + mypy strict + pytest (tirith-hook と同一構成)、pre-commit local hooks。

設計 spec: `docs/superpowers/specs/2026-07-03-session-handoff-design.md`

## Global Constraints

- しきい値等の canonical は `handoff-sentinel.py` の定数 (`DEFAULT_CONTEXT_WINDOW_TOKENS` = 200_000 / `DEFAULT_CONTEXT_THRESHOLD_PCT` = 50 / `DEFAULT_BROKEN_STREAK` = 5 / `DEFAULT_INJECT_MAX_BYTES` / `DEFAULT_TAIL_BYTES`)。環境変数 `HANDOFF_CONTEXT_WINDOW_TOKENS` / `HANDOFF_CONTEXT_THRESHOLD_PCT` / `HANDOFF_BROKEN_STREAK` / `HANDOFF_INJECT_MAX_BYTES` / `HANDOFF_TAIL_BYTES` / `HANDOFF_STATE_DIR` で上書き可。SKILL.md / template.md にこれらの値を再掲しない
- sentinel は全経路 fail-safe: 例外・不正入力・transcript 不在では何も出力せず exit 0。作業を止めない
- subagent では動かない: hook 入力に `agent_id` があれば即 exit 0。transcript 走査では `isSidechain` が真の entry を除外する
- 依存ゼロ (stdlib のみ)。dev 依存は pytest / ruff / mypy のみ
- 公開リポのため秘密・個人パス (`/Users/<name>`) を含めない。settings.json の hook command は `$HOME` ベースで書く (gitleaks が検査する)
- コード内コメントは日本語、ファイル末尾は空行1つ
- hook 本体は `home/.claude/hooks/handoff-sentinel.py` (symlink 都合)、テストハーネスは `scripts/handoff-sentinel/` (tirith-hook と同じ分離)
- `home/.claude/settings.json` は skip-worktree 運用。committed 版の編集は退避 → no-skip → 編集 → live 復元 → re-skip の手順を厳守 (Task 6)

---

## Phase 1: handoff-sentinel hook

### Task 1: テストハーネス scaffold + sentinel 骨格 + pre-commit 配線

**Files:**
- Create: `scripts/handoff-sentinel/pyproject.toml`
- Create: `home/.claude/hooks/handoff-sentinel.py`
- Create: `scripts/handoff-sentinel/tests/test_handoff_sentinel.py`
- Modify: `.pre-commit-config.yaml` (tirith-hook ブロックの直後に追記)
- Modify: `.gitignore` (tirith-hook ブロックの直後に追記)

**Interfaces:**
- Produces: `run_hook(action, hook_input, *, extra_env)` テストヘルパー (後続 Task の全テストが使う)、`main()` の dispatch 構造と `HANDLERS` dict (後続 Task が handler を追加する)

- [ ] **Step 1: pyproject.toml を作成**

`scripts/handoff-sentinel/pyproject.toml` (tirith-hook と同一構成、name / description のみ変更):

```toml
[project]
name = "handoff-sentinel"
version = "0.1.0"
description = "home/.claude/hooks/handoff-sentinel.py（Claude Code PostToolUse/Stop/SessionStart フック）の単体/統合テスト"
readme = "README.md"
requires-python = ">=3.12"
license = { text = "MIT" }
authors = [{ name = "Hidari" }]
dependencies = []

# 本体 (handoff-sentinel.py) は symlink 都合で home/.claude/hooks/ に置くため、
# このプロジェクトはインストール可能なパッケージを持たないテスト専用ハーネス。
[tool.uv]
package = false

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

[tool.pytest.ini_options]
addopts = "-ra --strict-markers --strict-config"
testpaths = ["tests"]
```

`scripts/handoff-sentinel/README.md` (1段落のみ):

```markdown
# handoff-sentinel

`home/.claude/hooks/handoff-sentinel.py` (Claude Code PostToolUse / Stop / SessionStart フック)
のテストハーネス。本体は symlink 都合で `home/.claude/hooks/` に置く。
仕様は `docs/superpowers/specs/2026-07-03-session-handoff-design.md` を参照。
```

- [ ] **Step 2: 骨格の失敗テストを書く**

`scripts/handoff-sentinel/tests/test_handoff_sentinel.py`:

```python
"""handoff-sentinel.py（Claude Code PostToolUse/Stop/SessionStart フック）の黒箱統合テスト。

フックを subprocess 起動し、stdin に hook JSON を、HANDOFF_* 環境変数にテスト用の
しきい値・state ディレクトリを与えて stdout (hook output JSON) と exit code を
exact 検証する。transcript は一時ファイルに JSONL で生成する（CLAUDE.md: モック回避）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
HOOK = REPO_ROOT / "home" / ".claude" / "hooks" / "handoff-sentinel.py"


def run_hook(
    action: str | None,
    hook_input: dict[str, object] | str | None,
    *,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """フックを subprocess 起動する。基底環境から HANDOFF_* を除去し extra_env のみ適用する。"""
    env = {k: v for k, v in os.environ.items() if not k.startswith("HANDOFF_")}
    if extra_env:
        env.update(extra_env)
    if isinstance(hook_input, dict):
        stdin = json.dumps(hook_input)
    else:
        stdin = hook_input or ""
    argv = [sys.executable, str(HOOK)]
    if action is not None:
        argv.append(action)
    return subprocess.run(
        argv, input=stdin, capture_output=True, text=True, env=env, timeout=10
    )


class TestFailSafeSkeleton:
    """骨格の fail-safe: どんな不正入力でも無出力 + exit 0 で作業を止めない。"""

    def test_未知のactionは無出力でexit0(self) -> None:
        result = run_hook("unknown-action", {"session_id": "s1"})
        assert result.returncode == 0
        assert result.stdout == ""

    def test_action無しは無出力でexit0(self) -> None:
        result = run_hook(None, {"session_id": "s1"})
        assert result.returncode == 0
        assert result.stdout == ""

    def test_非JSONのstdinは無出力でexit0(self) -> None:
        result = run_hook("posttool", "this is not json")
        assert result.returncode == 0
        assert result.stdout == ""

    def test_空stdinは無出力でexit0(self) -> None:
        result = run_hook("posttool", None)
        assert result.returncode == 0
        assert result.stdout == ""
```

- [ ] **Step 3: テストが失敗することを確認**

Run: `uv run --directory scripts/handoff-sentinel pytest -q`
Expected: FAIL (HOOK ファイル不在により FileNotFoundError)

- [ ] **Step 4: sentinel 骨格を実装**

`home/.claude/hooks/handoff-sentinel.py`:

```python
#!/usr/bin/env python3
"""Claude Code hook: セッション引き継ぎ検知器 (handoff-sentinel)。

第1引数で分岐する: posttool (コンテキスト使用率の監視) / stop (ツール呼び出し破損の
連続検知) / session (tmp/handoff.md の自動注入)。しきい値等の canonical はこのファイルの
定数であり、HANDOFF_* 環境変数で上書きできる。検知機構の故障で作業を止めないため、
全経路 fail-safe (無出力 + exit 0)。
仕様: docs/superpowers/specs/2026-07-03-session-handoff-design.md
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable
from typing import Any

# canonical な既定値。他ファイル (SKILL.md / template.md) はこれらの値を再掲しない。
DEFAULT_CONTEXT_WINDOW_TOKENS = 200_000
DEFAULT_CONTEXT_THRESHOLD_PCT = 50
DEFAULT_BROKEN_STREAK = 5
DEFAULT_INJECT_MAX_BYTES = 32_768
DEFAULT_TAIL_BYTES = 1_048_576

# handler は後続タスクで追加する
HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any] | None]] = {}


def main() -> int:
    try:
        action = sys.argv[1] if len(sys.argv) > 1 else ""
        handler = HANDLERS.get(action)
        if handler is None:
            return 0
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict) or payload.get("agent_id"):
            # subagent では動かない (spec: 共通ガード)
            return 0
        output = handler(payload)
        if output is not None:
            print(json.dumps(output, ensure_ascii=False))
    except Exception:
        # fail-safe: 検知器の故障で作業を止めない
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: テストが通ることを確認**

Run: `uv run --directory scripts/handoff-sentinel pytest -q`
Expected: PASS (4 passed)

- [ ] **Step 6: pre-commit と .gitignore に配線**

`.pre-commit-config.yaml` の `tirith-hook-pytest` エントリの直後 (gitleaks の前) に追記:

```yaml
      - id: handoff-sentinel-ruff-check
        name: handoff-sentinel ruff check
        language: system
        entry: uv run --directory scripts/handoff-sentinel ruff check --config pyproject.toml ../../home/.claude/hooks/handoff-sentinel.py tests
        pass_filenames: false
        files: ^(home/\.claude/hooks/handoff-sentinel\.py|scripts/handoff-sentinel/.*)$

      - id: handoff-sentinel-ruff-format
        name: handoff-sentinel ruff format --check
        language: system
        entry: uv run --directory scripts/handoff-sentinel ruff format --check --config pyproject.toml ../../home/.claude/hooks/handoff-sentinel.py tests
        pass_filenames: false
        files: ^(home/\.claude/hooks/handoff-sentinel\.py|scripts/handoff-sentinel/.*)$

      - id: handoff-sentinel-mypy
        name: handoff-sentinel mypy
        language: system
        entry: uv run --directory scripts/handoff-sentinel mypy --config-file pyproject.toml ../../home/.claude/hooks/handoff-sentinel.py tests
        pass_filenames: false
        files: ^(home/\.claude/hooks/handoff-sentinel\.py|scripts/handoff-sentinel/.*)$

      - id: handoff-sentinel-pytest
        name: handoff-sentinel pytest
        language: system
        entry: uv run --directory scripts/handoff-sentinel pytest -q
        pass_filenames: false
        files: ^(home/\.claude/hooks/handoff-sentinel\.py|scripts/handoff-sentinel/.*)$
```

`.gitignore` の tirith-hook ブロック (38行目付近) の直後に追記:

```
scripts/handoff-sentinel/.venv/
scripts/handoff-sentinel/**/__pycache__/
scripts/handoff-sentinel/.ruff_cache/
scripts/handoff-sentinel/.mypy_cache/
scripts/handoff-sentinel/.pytest_cache/
```

- [ ] **Step 7: lint / 型 / uv.lock を通す**

Run:
```bash
uv lock --directory scripts/handoff-sentinel
uv run --directory scripts/handoff-sentinel ruff check --config pyproject.toml ../../home/.claude/hooks/handoff-sentinel.py tests
uv run --directory scripts/handoff-sentinel ruff format --config pyproject.toml ../../home/.claude/hooks/handoff-sentinel.py tests
uv run --directory scripts/handoff-sentinel mypy --config-file pyproject.toml ../../home/.claude/hooks/handoff-sentinel.py tests
```
Expected: 全て成功 (ruff format は差分があれば自動整形するので再度 `--check` で確認)

- [ ] **Step 8: コミット**

```bash
git add scripts/handoff-sentinel home/.claude/hooks/handoff-sentinel.py .pre-commit-config.yaml .gitignore
git commit -m "feat(wip): handoff-sentinel hook の骨格とテストハーネスを追加"
```
Expected: pre-commit の handoff-sentinel 4 hooks が実行され全て Passed

### Task 2: posttool コンテキスト監視

**Files:**
- Modify: `home/.claude/hooks/handoff-sentinel.py`
- Modify: `scripts/handoff-sentinel/tests/test_handoff_sentinel.py`

**Interfaces:**
- Consumes: Task 1 の `run_hook` / `HANDLERS` / 定数
- Produces: `_env_int(name, default) -> int`、`_state_dir() -> Path`、`_notify_once(state_file) -> bool`、`_read_tail_entries(transcript_path) -> list[dict[str, Any]]` (Task 3 が再利用)、hook 出力 `{"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": "..."}}`

- [ ] **Step 1: 失敗テストを書く**

テストファイルに追記 (import に `from pathlib import Path` は既存。ヘルパーと posttool テストを追加):

```python
def assistant_usage(
    tokens: int, *, sidechain: bool = False
) -> dict[str, object]:
    """usage 合算が tokens になる assistant entry を作る (input に全量を寄せる)。"""
    entry: dict[str, object] = {
        "type": "assistant",
        "message": {
            "usage": {
                "input_tokens": tokens,
                "cache_read_input_tokens": 0,
                "cache_creation_input_tokens": 0,
            },
            "content": [],
        },
    }
    if sidechain:
        entry["isSidechain"] = True
    return entry


def write_transcript(path: Path, entries: list[dict[str, object]]) -> None:
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def base_env(tmp_path: Path) -> dict[str, str]:
    """テスト用の小さいしきい値: window=1000 tokens, 50% (= 500 tokens で発火)。"""
    return {
        "HANDOFF_STATE_DIR": str(tmp_path / "state"),
        "HANDOFF_CONTEXT_WINDOW_TOKENS": "1000",
        "HANDOFF_CONTEXT_THRESHOLD_PCT": "50",
        "HANDOFF_BROKEN_STREAK": "5",
    }


def posttool_input(tmp_path: Path, transcript: Path) -> dict[str, object]:
    return {
        "session_id": "sess-1",
        "transcript_path": str(transcript),
        "cwd": str(tmp_path),
        "hook_event_name": "PostToolUse",
    }


class TestPostToolContextWatch:
    """posttool: 最後の assistant usage 合算がしきい値以上のとき、1 回だけ通知する。"""

    def test_しきい値直下では発火しない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, [assistant_usage(499)])
        result = run_hook(
            "posttool", posttool_input(tmp_path, transcript), extra_env=base_env(tmp_path)
        )
        assert result.returncode == 0
        assert result.stdout == ""

    def test_しきい値ちょうどで発火しskill名を含む(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, [assistant_usage(500)])
        result = run_hook(
            "posttool", posttool_input(tmp_path, transcript), extra_env=base_env(tmp_path)
        )
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["hookEventName"] == "PostToolUse"
        assert "session-handoff" in output["hookSpecificOutput"]["additionalContext"]
        assert (tmp_path / "state" / "sess-1.notified").is_file()

    def test_usage3フィールドは合算される(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        entry = assistant_usage(0)
        message = entry["message"]
        assert isinstance(message, dict)
        message["usage"] = {
            "input_tokens": 100,
            "cache_read_input_tokens": 300,
            "cache_creation_input_tokens": 100,
        }
        write_transcript(transcript, [entry])
        result = run_hook(
            "posttool", posttool_input(tmp_path, transcript), extra_env=base_env(tmp_path)
        )
        assert result.stdout != ""  # 100+300+100=500 >= 500 で発火

    def test_通知済みセッションでは再発火しない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, [assistant_usage(999)])
        env = base_env(tmp_path)
        first = run_hook("posttool", posttool_input(tmp_path, transcript), extra_env=env)
        second = run_hook("posttool", posttool_input(tmp_path, transcript), extra_env=env)
        assert first.stdout != ""
        assert second.returncode == 0
        assert second.stdout == ""

    def test_sidechainのassistantは無視される(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(
            transcript,
            [assistant_usage(200), assistant_usage(9999, sidechain=True)],
        )
        result = run_hook(
            "posttool", posttool_input(tmp_path, transcript), extra_env=base_env(tmp_path)
        )
        assert result.stdout == ""  # 本編の 200 tokens のみで判定される

    def test_agent_id付きのsubagentでは発火しない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, [assistant_usage(999)])
        hook_input = posttool_input(tmp_path, transcript)
        hook_input["agent_id"] = "agent-x"
        result = run_hook("posttool", hook_input, extra_env=base_env(tmp_path))
        assert result.returncode == 0
        assert result.stdout == ""

    def test_transcript不在は無出力でexit0(self, tmp_path: Path) -> None:
        hook_input = posttool_input(tmp_path, tmp_path / "missing.jsonl")
        result = run_hook("posttool", hook_input, extra_env=base_env(tmp_path))
        assert result.returncode == 0
        assert result.stdout == ""

    def test_壊れたJSONL行は無視して判定する(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        valid = json.dumps(assistant_usage(999))
        transcript.write_text(f"{{broken json\n{valid}\n[1,2]\n", encoding="utf-8")
        result = run_hook(
            "posttool", posttool_input(tmp_path, transcript), extra_env=base_env(tmp_path)
        )
        assert result.stdout != ""  # 有効行のみで判定して発火

    def test_空のtranscriptは無出力でexit0(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        transcript.write_text("", encoding="utf-8")
        result = run_hook(
            "posttool", posttool_input(tmp_path, transcript), extra_env=base_env(tmp_path)
        )
        assert result.returncode == 0
        assert result.stdout == ""
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run --directory scripts/handoff-sentinel pytest -q`
Expected: FAIL (posttool が HANDLERS に無く全ケース無出力のため、発火系テストが FAIL)

- [ ] **Step 3: posttool handler を実装**

`handoff-sentinel.py` に追記。import へ `import os` と `from datetime import UTC, datetime` と `from pathlib import Path` を追加し、`HANDLERS` 定義の前に以下を挿入、`HANDLERS` を書き換える:

```python
def _env_int(name: str, default: int) -> int:
    """正の整数の環境変数を読む。未設定・不正・0 以下は default に落とす。"""
    try:
        value = int(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if value > 0 else default


def _state_dir() -> Path:
    override = os.environ.get("HANDOFF_STATE_DIR", "")
    if override:
        return Path(override)
    return Path.home() / ".cache" / "claude" / "handoff-sentinel"


def _notify_once(state_file: Path) -> bool:
    """state ファイルを新規作成できたら True (初回)。既存なら False (通知済み)。"""
    state_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(state_file, "x", encoding="utf-8") as fp:
            fp.write(datetime.now(UTC).isoformat() + "\n")
    except FileExistsError:
        return False
    return True


def _read_tail_entries(transcript_path: str) -> list[dict[str, Any]]:
    """transcript JSONL の末尾 (既定 DEFAULT_TAIL_BYTES) を読み、entry 一覧を返す。

    ツール実行ごとに走るため全量パースを避けてコストを一定に抑える。判定に必要なのは
    末尾近傍のみ (最後の usage / 破損 streak)。壊れた行と subagent の isSidechain な
    entry は捨てる。
    """
    tail_bytes = _env_int("HANDOFF_TAIL_BYTES", DEFAULT_TAIL_BYTES)
    size = os.path.getsize(transcript_path)
    with open(transcript_path, "rb") as fp:
        if size > tail_bytes:
            fp.seek(size - tail_bytes)
            fp.readline()  # seek で切れた部分行を捨てる
        data = fp.read()
    entries: list[dict[str, Any]] = []
    for line in data.decode("utf-8", errors="replace").splitlines():
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(entry, dict) and not entry.get("isSidechain"):
            entries.append(entry)
    return entries


def _context_tokens(entries: list[dict[str, Any]]) -> int:
    """最後の assistant メッセージの usage からコンテキスト占有量 (tokens) を推定する。"""
    for entry in reversed(entries):
        if entry.get("type") != "assistant":
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        usage = message.get("usage")
        if not isinstance(usage, dict):
            continue
        total = 0
        for key in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"):
            value = usage.get(key)
            if isinstance(value, int):
                total += value
        return total
    return 0


def handle_posttool(payload: dict[str, Any]) -> dict[str, Any] | None:
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")
    if not (isinstance(session_id, str) and session_id):
        return None
    if not (isinstance(transcript_path, str) and os.path.isfile(transcript_path)):
        return None
    window = _env_int("HANDOFF_CONTEXT_WINDOW_TOKENS", DEFAULT_CONTEXT_WINDOW_TOKENS)
    threshold_pct = _env_int("HANDOFF_CONTEXT_THRESHOLD_PCT", DEFAULT_CONTEXT_THRESHOLD_PCT)
    tokens = _context_tokens(_read_tail_entries(transcript_path))
    if tokens * 100 < window * threshold_pct:
        return None
    if not _notify_once(_state_dir() / f"{session_id}.notified"):
        return None
    context = (
        f"コンテキスト使用率がしきい値を超えた (推定 {tokens} tokens)。"
        "session-handoff スキルを発動して引き継ぎを tmp/handoff.md に書き出し、"
        "ユーザーにセッション切替 (/clear または新セッション) を促すこと。"
    )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": context,
        }
    }


HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any] | None]] = {
    "posttool": handle_posttool,
}
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run --directory scripts/handoff-sentinel pytest -q`
Expected: PASS (13 passed)

- [ ] **Step 5: lint / 型を通してコミット**

Run: Task 1 Step 7 と同じ ruff / mypy コマンド。全て成功したら:

```bash
git add home/.claude/hooks/handoff-sentinel.py scripts/handoff-sentinel/tests/test_handoff_sentinel.py
git commit -m "feat(wip): handoff-sentinel に posttool コンテキスト監視を追加"
```

### Task 3: stop 破損検知

**Files:**
- Modify: `home/.claude/hooks/handoff-sentinel.py`
- Modify: `scripts/handoff-sentinel/tests/test_handoff_sentinel.py`

**Interfaces:**
- Consumes: Task 2 の `_read_tail_entries` / `_notify_once` / `_env_int` / `_state_dir`
- Produces: hook 出力 `{"decision": "block", "reason": "..."}` (reason に `session-handoff` を含む)

- [ ] **Step 1: 失敗テストを書く**

テストファイルに追記。破損サンプルはユーザー実観測の漏れパターンをそのまま使う:

```python
LEAKED_TOOL_CALL = (
    "court\n"
    '<invoke name="Bash">\n'
    '<parameter name="command">echo ready</parameter>\n'
    "</invoke>"
)


def assistant_text(text: str, *, with_tool_use: bool = False) -> dict[str, object]:
    content: list[dict[str, object]] = [{"type": "text", "text": text}]
    if with_tool_use:
        content.append({"type": "tool_use", "id": "toolu_x", "name": "Bash", "input": {}})
    return {"type": "assistant", "message": {"content": content}}


def tool_result(*, is_error: bool) -> dict[str, object]:
    return {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_x",
                    "is_error": is_error,
                    "content": "",
                }
            ]
        },
    }


def stop_input(tmp_path: Path, transcript: Path) -> dict[str, object]:
    return {
        "session_id": "sess-1",
        "transcript_path": str(transcript),
        "cwd": str(tmp_path),
        "hook_event_name": "Stop",
        "stop_hook_active": False,
    }


class TestStopBrokenStreak:
    """stop: 末尾から連続する破損イベントが規定数に達したら 1 回だけ停止をブロックする。"""

    def leaks(self, n: int) -> list[dict[str, object]]:
        return [assistant_text(LEAKED_TOOL_CALL) for _ in range(n)]

    def test_破損5連続でblockしreasonにskill名を含む(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, [tool_result(is_error=False), *self.leaks(5)])
        result = run_hook("stop", stop_input(tmp_path, transcript), extra_env=base_env(tmp_path))
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["decision"] == "block"
        assert "session-handoff" in output["reason"]
        assert (tmp_path / "state" / "sess-1.blocked").is_file()

    def test_破損4連続では発火しない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, self.leaks(4))
        result = run_hook("stop", stop_input(tmp_path, transcript), extra_env=base_env(tmp_path))
        assert result.stdout == ""

    def test_正常なtool_resultでカウントがリセットされる(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(
            transcript, [*self.leaks(4), tool_result(is_error=False), *self.leaks(4)]
        )
        result = run_hook("stop", stop_input(tmp_path, transcript), extra_env=base_env(tmp_path))
        assert result.stdout == ""  # リセット後の 4 連続のみで判定

    def test_エラーtool_resultも破損イベントとして数える(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(
            transcript,
            [*self.leaks(2), tool_result(is_error=True), tool_result(is_error=True), *self.leaks(1)],
        )
        result = run_hook("stop", stop_input(tmp_path, transcript), extra_env=base_env(tmp_path))
        assert json.loads(result.stdout)["decision"] == "block"

    def test_正常なtool_use付きメッセージの断片は数えない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        entries = [assistant_text(LEAKED_TOOL_CALL, with_tool_use=True) for _ in range(5)]
        write_transcript(transcript, entries)
        result = run_hook("stop", stop_input(tmp_path, transcript), extra_env=base_env(tmp_path))
        assert result.stdout == ""

    def test_断片を含まない通常テキストは数えない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, [assistant_text("普通の応答です") for _ in range(5)])
        result = run_hook("stop", stop_input(tmp_path, transcript), extra_env=base_env(tmp_path))
        assert result.stdout == ""

    def test_stop_hook_activeのときはblockしない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, self.leaks(5))
        hook_input = stop_input(tmp_path, transcript)
        hook_input["stop_hook_active"] = True
        result = run_hook("stop", hook_input, extra_env=base_env(tmp_path))
        assert result.stdout == ""

    def test_block済みセッションでは再blockしない(self, tmp_path: Path) -> None:
        transcript = tmp_path / "t.jsonl"
        write_transcript(transcript, self.leaks(5))
        env = base_env(tmp_path)
        first = run_hook("stop", stop_input(tmp_path, transcript), extra_env=env)
        second = run_hook("stop", stop_input(tmp_path, transcript), extra_env=env)
        assert json.loads(first.stdout)["decision"] == "block"
        assert second.stdout == ""
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run --directory scripts/handoff-sentinel pytest -q`
Expected: FAIL (stop が HANDLERS に無いため block 系テストが FAIL)

- [ ] **Step 3: stop handler を実装**

`handoff-sentinel.py` に追記し、`HANDLERS` に `"stop": handle_stop` を追加:

```python
# 本文に漏れた tool-call 断片の目印 (破損イベントの判定に使う)
BROKEN_MARKERS = ("<invoke", "</invoke>", "<parameter", "antml")


def _classify(entry: dict[str, Any]) -> str:
    """entry を broken / reset / neutral に分類する。

    broken: 正常な tool_use を伴わない text への tool-call 断片の漏れ、
            または is_error な tool_result。
    reset: 正常に完了した tool_result (is_error が偽)。
    """
    message = entry.get("message")
    if not isinstance(message, dict):
        return "neutral"
    content = message.get("content")
    if not isinstance(content, list):
        return "neutral"
    if entry.get("type") == "assistant":
        has_tool_use = any(
            isinstance(block, dict) and block.get("type") == "tool_use" for block in content
        )
        if has_tool_use:
            # tool-call 記法を話題として扱う会話の誤検知ガード
            return "neutral"
        for block in content:
            if not (isinstance(block, dict) and block.get("type") == "text"):
                continue
            text = block.get("text")
            if isinstance(text, str) and any(marker in text for marker in BROKEN_MARKERS):
                return "broken"
        return "neutral"
    if entry.get("type") == "user":
        results = [
            block
            for block in content
            if isinstance(block, dict) and block.get("type") == "tool_result"
        ]
        if not results:
            return "neutral"
        if any(block.get("is_error") for block in results):
            return "broken"
        return "reset"
    return "neutral"


def _broken_streak(entries: list[dict[str, Any]]) -> int:
    """末尾から遡り、最新イベントで終わる破損イベントの連続数を数える。"""
    streak = 0
    for entry in reversed(entries):
        kind = _classify(entry)
        if kind == "broken":
            streak += 1
        elif kind == "reset":
            break
    return streak


def handle_stop(payload: dict[str, Any]) -> dict[str, Any] | None:
    if payload.get("stop_hook_active"):
        # block 由来の再入では判定しない (無限 block ループ防止の一段目)
        return None
    session_id = payload.get("session_id")
    transcript_path = payload.get("transcript_path")
    if not (isinstance(session_id, str) and session_id):
        return None
    if not (isinstance(transcript_path, str) and os.path.isfile(transcript_path)):
        return None
    streak_limit = _env_int("HANDOFF_BROKEN_STREAK", DEFAULT_BROKEN_STREAK)
    if _broken_streak(_read_tail_entries(transcript_path)) < streak_limit:
        return None
    if not _notify_once(_state_dir() / f"{session_id}.blocked"):
        # 1 セッション 1 回 (無限 block ループ防止の二段目)
        return None
    reason = (
        "ツール呼び出しの破損が連続して検知された。停止する前に session-handoff スキルを"
        "発動して引き継ぎを tmp/handoff.md に書き出し、ユーザーに Claude Code の再起動を"
        "促してから停止すること。"
    )
    return {"decision": "block", "reason": reason}
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run --directory scripts/handoff-sentinel pytest -q`
Expected: PASS (21 passed)

- [ ] **Step 5: lint / 型を通してコミット**

```bash
git add home/.claude/hooks/handoff-sentinel.py scripts/handoff-sentinel/tests/test_handoff_sentinel.py
git commit -m "feat(wip): handoff-sentinel に stop 破損検知を追加"
```

### Task 4: session 引き継ぎ注入

**Files:**
- Modify: `home/.claude/hooks/handoff-sentinel.py`
- Modify: `scripts/handoff-sentinel/tests/test_handoff_sentinel.py`

**Interfaces:**
- Consumes: Task 2 の `_env_int`
- Produces: hook 出力 `{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}}`、consumed リネーム `handoff-consumed-<UTC>.md`

- [ ] **Step 1: 失敗テストを書く**

テストファイルに追記 (import へ `import re` を追加):

```python
def session_input(cwd: Path) -> dict[str, object]:
    return {"session_id": "sess-1", "cwd": str(cwd), "hook_event_name": "SessionStart"}


class TestSessionStartInject:
    """session: tmp/handoff.md があれば注入して consumed へリネームする。"""

    def test_handoffを注入しconsumedへリネームする(self, tmp_path: Path) -> None:
        handoff_dir = tmp_path / "tmp"
        handoff_dir.mkdir()
        (handoff_dir / "handoff.md").write_text("# 引き継ぎ\n次は X をやる\n", encoding="utf-8")
        result = run_hook("session", session_input(tmp_path), extra_env=base_env(tmp_path))
        assert result.returncode == 0
        output = json.loads(result.stdout)
        assert output["hookSpecificOutput"]["hookEventName"] == "SessionStart"
        assert "次は X をやる" in output["hookSpecificOutput"]["additionalContext"]
        assert not (handoff_dir / "handoff.md").exists()
        consumed = [p.name for p in handoff_dir.iterdir()]
        assert len(consumed) == 1
        assert re.fullmatch(r"handoff-consumed-\d{8}T\d{6}Z\.md", consumed[0])

    def test_gitリポ内はサブディレクトリのcwdでもルートのhandoffを拾う(
        self, tmp_path: Path
    ) -> None:
        repo = tmp_path / "repo"
        sub = repo / "src"
        sub.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True, timeout=10)
        (repo / "tmp").mkdir()
        (repo / "tmp" / "handoff.md").write_text("root handoff\n", encoding="utf-8")
        result = run_hook("session", session_input(sub), extra_env=base_env(tmp_path))
        output = json.loads(result.stdout)
        assert "root handoff" in output["hookSpecificOutput"]["additionalContext"]

    def test_handoff不在は無出力でexit0(self, tmp_path: Path) -> None:
        result = run_hook("session", session_input(tmp_path), extra_env=base_env(tmp_path))
        assert result.returncode == 0
        assert result.stdout == ""

    def test_巨大なhandoffは先頭のみ注入し切り詰めを明記する(self, tmp_path: Path) -> None:
        handoff_dir = tmp_path / "tmp"
        handoff_dir.mkdir()
        (handoff_dir / "handoff.md").write_text("A" * 5000, encoding="utf-8")
        env = base_env(tmp_path) | {"HANDOFF_INJECT_MAX_BYTES": "100"}
        result = run_hook("session", session_input(tmp_path), extra_env=env)
        context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        assert "A" * 100 in context
        assert "A" * 101 not in context
        assert "先頭のみ注入" in context

    def test_agent_id付きのsubagentでは注入しない(self, tmp_path: Path) -> None:
        handoff_dir = tmp_path / "tmp"
        handoff_dir.mkdir()
        (handoff_dir / "handoff.md").write_text("x\n", encoding="utf-8")
        hook_input = session_input(tmp_path)
        hook_input["agent_id"] = "agent-x"
        result = run_hook("session", hook_input, extra_env=base_env(tmp_path))
        assert result.stdout == ""
        assert (handoff_dir / "handoff.md").exists()  # リネームもしない

    def test_リネーム失敗時は注入しない(self, tmp_path: Path) -> None:
        handoff_dir = tmp_path / "tmp"
        handoff_dir.mkdir()
        (handoff_dir / "handoff.md").write_text("x\n", encoding="utf-8")
        handoff_dir.chmod(0o555)  # ディレクトリ書き込み不可で rename を失敗させる
        try:
            result = run_hook("session", session_input(tmp_path), extra_env=base_env(tmp_path))
            assert result.returncode == 0
            assert result.stdout == ""  # 注入だけ成功して毎回再注入される重複を防ぐ
        finally:
            handoff_dir.chmod(0o755)
```

- [ ] **Step 2: テストが失敗することを確認**

Run: `uv run --directory scripts/handoff-sentinel pytest -q`
Expected: FAIL (session が HANDLERS に無いため注入系テストが FAIL)

- [ ] **Step 3: session handler を実装**

`handoff-sentinel.py` に追記し、`HANDLERS` に `"session": handle_session` を追加。
import へ `import subprocess` を追加:

```python
def _repo_root(cwd: str) -> Path:
    """cwd の git リポルートを返す。リポ外・git 不在は cwd に落とす。"""
    try:
        result = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return Path(cwd)
    top = result.stdout.strip()
    return Path(top) if result.returncode == 0 and top else Path(cwd)


def handle_session(payload: dict[str, Any]) -> dict[str, Any] | None:
    cwd = payload.get("cwd")
    if not (isinstance(cwd, str) and os.path.isdir(cwd)):
        return None
    handoff = _repo_root(cwd) / "tmp" / "handoff.md"
    if not handoff.is_file():
        return None
    max_bytes = _env_int("HANDOFF_INJECT_MAX_BYTES", DEFAULT_INJECT_MAX_BYTES)
    raw = handoff.read_bytes()
    text = raw[:max_bytes].decode("utf-8", errors="replace")
    if len(raw) > max_bytes:
        text += "\n\n(引き継ぎ書が大きいため先頭のみ注入した。全文は consumed リネーム先を読むこと)"
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    consumed = handoff.with_name(f"handoff-consumed-{stamp}.md")
    try:
        handoff.rename(consumed)
    except OSError:
        # リネームに失敗したら注入もしない (毎セッション再注入される重複より欠落を選ぶ)
        return None
    context = f"前セッションからの引き継ぎ (tmp/{consumed.name} として保存済み):\n\n{text}"
    return {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": context,
        }
    }
```

- [ ] **Step 4: テストが通ることを確認**

Run: `uv run --directory scripts/handoff-sentinel pytest -q`
Expected: PASS (27 passed)

- [ ] **Step 5: lint / 型を通してコミット**

```bash
git add home/.claude/hooks/handoff-sentinel.py scripts/handoff-sentinel/tests/test_handoff_sentinel.py
git commit -m "feat(wip): handoff-sentinel に SessionStart 引き継ぎ注入を追加"
```

## Phase 2: skill と配線

### Task 5: session-handoff skill + template

**Files:**
- Create: `home/.claude/skills/session-handoff/SKILL.md`
- Create: `home/.claude/skills/session-handoff/template.md`

**Interfaces:**
- Consumes: Task 2-3 の hook 通知文言 (「session-handoff スキルを発動して」)
- Produces: skill `session-handoff` (`/session-handoff` としても起動可)

- [ ] **Step 1: template.md を作成**

`home/.claude/skills/session-handoff/template.md`:

```markdown
# セッション引き継ぎ

<!-- 全セクション共通: コードや git 履歴から復元できない情報を優先する。
     diff・コミット履歴はリポが持っている。会話コンテキストにしかない判断・状態を凝縮する -->

## タスクと目的

<!-- いま何をなぜやっているか。ユーザーの依頼の要点。複数タスクがあれば全て -->

## 完了済み

<!-- 済んだこと。テスト・lint・ビルドの緑/赤など検証状態を必ず含める -->

## 未完と次の一手

<!-- 残作業と、再開後に最初に実行すべき具体的アクション (コマンドがあれば原文で) -->

## キー情報

<!-- ブランチ、PR 番号、重要ファイルパス、実行中プロセス、一時ファイルの場所 -->

## 決定事項とハマりどころ

<!-- 会話で決まったこと、却下した案とその理由、踏んだ罠と回避策 -->
```

- [ ] **Step 2: SKILL.md を作成**

`home/.claude/skills/session-handoff/SKILL.md`:

```markdown
---
name: session-handoff
description: セッションの作業状態を引き継ぎ書 <リポルート>/tmp/handoff.md に書き出し、新しいセッションへ引き継ぐ。発動経路は3つ。(1) hook からのコンテキスト超過通知を受けたとき (2) hook からのツール呼び出し破損通知を受けたとき (3) ユーザーが手動で依頼したとき (「引き継ぎ書いて」「handoff して」「セッション切り替えたい」等)。新セッション側の読み込みは SessionStart hook (handoff-sentinel) が自動で行うため、このスキルは書き出しと案内までが責務。
---

# Session Handoff

セッションの作業状態を引き継ぎ書に外部化する。書き出した handoff.md は
次のセッションの開始時に hook が自動注入するので、読み込み側の作業は不要。

## 手順

1. `git rev-parse --show-toplevel` でリポルートを解決する (リポ外なら cwd を使う)
2. `<ルート>/tmp/` を `mkdir -p` で確保する
3. このスキルと同じディレクトリの `template.md` を読み、各セクションを
   コメントのガイドに従って埋め、`<ルート>/tmp/handoff.md` に書き出す
   (既存の handoff.md があれば上書きする。最新の引き継ぎが常に正)
4. 発動経路に応じて締める:
   - コンテキスト超過通知: 「引き継ぎを書き出した。/clear するか新セッションを
     開いて再開して。開始時に自動で引き継がれる」と案内し、以後の作業を打ち切る
   - ツール呼び出し破損通知: 「引き継ぎを書き出した。Claude Code の再起動を推奨」
     と案内し、以後の作業を打ち切る
   - 手動依頼: 書き出した旨とファイルパスだけ報告する

## 書き方の要点

- 埋める内容の構造は template.md が canonical。セクションの追加・削除はしない
- しきい値などの検知条件は hook (handoff-sentinel.py) が canonical。ここには書かない
- 具体的で実行可能な「次の一手」を最優先で書く (再開後のセッションが最初に読む)
```

- [ ] **Step 3: 構造ガードを通してコミット**

Run: `pwd` を確認後:

```bash
git add home/.claude/skills/session-handoff
git commit -m "feat(wip): session-handoff skill と引き継ぎテンプレートを追加"
```

Expected: pre-commit の config-guard scan (SKILL.md 構造検査) を含め全て Passed。
FAIL した場合は config-guard の指摘に従い frontmatter / 構造を修正する。

- [ ] **Step 4: skill が認識されることを確認**

Run: `claude -p "/session-handoff の説明を1行で" 2>&1 | head -5`
Expected: skill の description に沿った説明が返る (認識されていれば OK。
返らない場合は `~/.claude/skills/session-handoff/SKILL.md` が symlink 経由で
見えているか `ls ~/.claude/skills/session-handoff/` で確認する)

### Task 6: settings.json 配線 (committed + live)

**Files:**
- Modify: `home/.claude/settings.json` (skip-worktree 運用。下記手順厳守)

**Interfaces:**
- Consumes: Task 1-4 の `handoff-sentinel.py` (posttool / stop / session)
- Produces: 全セッションで sentinel が有効になる配線

- [ ] **Step 1: live 版を退避し committed 版を展開**

```bash
cp home/.claude/settings.json /tmp/settings.live.json
git update-index --no-skip-worktree home/.claude/settings.json
git checkout -- home/.claude/settings.json
git diff --stat  # settings.json が差分なしであることを確認
```

- [ ] **Step 2: committed 版に配線を追加**

`home/.claude/settings.json` の `hooks` に以下を追加する (`$HOME` ベース。
PostToolUse / Stop キーが無ければ新設、SessionStart は既存配列に追記):

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/hooks/handoff-sentinel.py\" posttool",
            "timeout": 10
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/hooks/handoff-sentinel.py\" stop",
            "timeout": 10
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/hooks/handoff-sentinel.py\" session",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

注意: 上記は追加分のみの抜粋。既存の PreToolUse (tirith) や SessionStart (日付) の
エントリは残したままマージすること。`python3 -m json.tool home/.claude/settings.json`
で JSON 妥当性を確認する。

- [ ] **Step 3: committed 版をコミット**

```bash
git add home/.claude/settings.json
git commit -m "config: handoff-sentinel hook を settings.json に配線"
```
Expected: config-guard (settings.json 検査) と gitleaks が Passed

- [ ] **Step 4: live 版に同じ配線を適用して復元**

`/tmp/settings.live.json` (退避した live 版) に Step 2 と同一の 3 エントリを追加して
`home/.claude/settings.json` へ書き戻す。live 版には committed 版に無い項目
(marketplaces 等の `/Users` パス) が含まれるため、必ず退避版をベースにすること:

```bash
python3 - <<'PY'
import json

with open("/tmp/settings.live.json", encoding="utf-8") as fp:
    live = json.load(fp)
with open("home/.claude/settings.json", encoding="utf-8") as fp:
    committed = json.load(fp)

# committed 版に入れた handoff-sentinel 配線を live 版の hooks へ合流させる
hooks = live.setdefault("hooks", {})
for event in ("PostToolUse", "Stop", "SessionStart"):
    for entry in committed.get("hooks", {}).get(event, []):
        commands = [h.get("command", "") for h in entry.get("hooks", [])]
        if any("handoff-sentinel.py" in c for c in commands):
            hooks.setdefault(event, []).append(entry)

with open("home/.claude/settings.json", "w", encoding="utf-8") as fp:
    json.dump(live, fp, indent=2, ensure_ascii=False)
    fp.write("\n")
print("live 版へ配線を合流させた")
PY
git update-index --skip-worktree home/.claude/settings.json
git status --short  # settings.json が出ないことを確認 (skip-worktree 復帰)
```

- [ ] **Step 5: live 版の検証**

```bash
python3 -m json.tool home/.claude/settings.json > /dev/null && echo "JSON OK"
python3 -c "
import json
d = json.load(open('home/.claude/settings.json'))
h = d['hooks']
assert any('handoff-sentinel' in str(e) for e in h['PostToolUse']), 'PostToolUse 欠落'
assert any('handoff-sentinel' in str(e) for e in h['Stop']), 'Stop 欠落'
assert any('handoff-sentinel' in str(e) for e in h['SessionStart']), 'SessionStart 欠落'
assert 'tirith-check.py' in str(h.get('PreToolUse', [])), '既存 tirith 配線が消えている'
print('live 配線 OK')
"
```
Expected: `JSON OK` と `live 配線 OK`

## Phase 3: live smoke と仕上げ

### Task 7: live smoke 3種 + PR 作成

**Files:**
- なし (実機検証と PR 作成のみ)

**Interfaces:**
- Consumes: Task 1-6 の全成果物

- [ ] **Step 1: live smoke 1 — SessionStart 注入**

```bash
mkdir -p tmp
printf '# セッション引き継ぎ\n\n## タスクと目的\n\nsmoke-test-marker-12345 の確認\n' > tmp/handoff.md
claude -p "前セッションからの引き継ぎが注入されていれば、そこに含まれる marker 文字列をそのまま出力して。無ければ NONE と出力して"
ls tmp/
```
Expected: 出力に `smoke-test-marker-12345` が含まれ、`tmp/` に `handoff.md` が消えて
`handoff-consumed-*.md` が残る

- [ ] **Step 2: live smoke 2 — コンテキスト超過通知**

しきい値を極小にした環境でツールを 1 回使わせ、posttool 通知が届くことを確認する:

```bash
HANDOFF_CONTEXT_WINDOW_TOKENS=1000 claude -p "pwd を Bash で実行し、その後に受け取った system 通知に session-handoff への言及があれば YES、無ければ NO とだけ出力して"
```
Expected: `YES` (実行のたび session_id が変わるため state ファイルの掃除は不要)

- [ ] **Step 3: live smoke 3 — /session-handoff 手動起動**

```bash
rm -f tmp/handoff.md
claude -p "/session-handoff"
head -5 tmp/handoff.md
```
Expected: `tmp/handoff.md` が生成され、先頭に template.md 由来の
`# セッション引き継ぎ` 見出しがある

- [ ] **Step 4: 後始末と全体緑の確認**

```bash
rm -f tmp/handoff.md tmp/handoff-consumed-*.md
uv run --directory scripts/handoff-sentinel pytest -q
pre-commit run --all-files
```
Expected: pytest 全緑、pre-commit 全 Passed

- [ ] **Step 5: push と PR 作成**

```bash
git push -u origin feat/session-handoff-skill
git ls-remote --heads origin feat/session-handoff-skill
git status -sb
gh pr list --head feat/session-handoff-skill --base main
gh pr create --assignee @me --base main --fill
```
Expected: push 成功 (ls-remote に ref が出る)、PR が作成される。
マージ前には `dev-workflow:pre-merge-quality-gate` を通すこと (repo の MUST)。
