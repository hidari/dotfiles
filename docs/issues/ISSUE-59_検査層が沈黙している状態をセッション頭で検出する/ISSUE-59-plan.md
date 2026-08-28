# 検査層の沈黙をセッション頭で検出する実装プラン

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** SessionStart フックが apm ガードと tirith の生存を測り、沈黙していればユーザーとモデルの両方へ 1 通で告げる。

**Architecture:** 述語を共有モジュール `guard_probes.py` へ集め、PreToolUse の 2 フックと新しい SessionStart フックが同じ述語を使う。フックは登録簿を回して結果を組み立てるだけで、判定のロジックを持たない。配線そのものは config-guard が 2 層 (名前での必須宣言と、導出による孤児検出) で pin する。

**Tech Stack:** Python 3.12 (標準ライブラリのみ)、pytest、uv、config-guard (同リポジトリ内)、pre-commit

**Spec:** `docs/issues/ISSUE-59_検査層が沈黙している状態をセッション頭で検出する/ISSUE-59-spec.md`

## Global Constraints

- フック本体とテストの Python は標準ライブラリのみ。`scripts/claude-hooks/pyproject.toml` は `dependencies = []` を宣言している
- ruff の `line-length` は 100、`target-version` は py312。mypy は `strict = true`
- コード内のコメントは日本語。ログとメッセージも日本語 (このリポジトリの CLAUDE.md が確定させている)
- 共有モジュールは実行ビットを持たない (mode 100644)。フック本体は持つ (mode 100755)。この差が孤児検出の判定基準になる
- フック本体は `home/.claude/hooks/` へ置く。テストは `scripts/claude-hooks/tests/` へ置く
- 日本語のテストメソッド名を使う場合は `pyproject.toml` の `[tool.ruff.lint.per-file-ignores]` へ `N802` を足す
- コミット本文は Write でファイルへ書き `git commit -F` で渡す。Bash コマンド文字列に日本語の散文を載せない
- 一時ファイルは `<repo>/.cache/` 配下へ置く。削除するときはコマンド文字列に `.cache/` を明示する

---

### Task 1: 共有プローブモジュールと apm プローブ

`shim_resolves` を `apm-install-guard.py` から共有モジュールへ移し、両方が同じ述語を使う状態にする。

**Files:**
- Create: `home/.claude/hooks/guard_probes.py` (mode 100644)
- Modify: `home/.claude/hooks/apm-install-guard.py` (`DEFAULT_SHIM_PATH` / `shim_path` / `shim_resolves` を削除し import へ差し替え)
- Create: `scripts/claude-hooks/tests/test_guard_probes.py`
- Modify: `scripts/claude-hooks/tests/test_apm_install_guard.py:720-729` (`test_shim_path_matches_the_distributed_target` を Task 1 の新テストへ移す)
- Modify: `scripts/claude-hooks/pyproject.toml` (`per-file-ignores` へ新テストを追加)

**Interfaces:**
- Consumes: なし (最初のタスク)
- Produces:
  - `guard_probes.ProbeResult` — `@dataclass(frozen=True)` で `healthy: bool` と `detail: str = ""`
  - `guard_probes.DEFAULT_SHIM_PATH: str`
  - `guard_probes.shim_path() -> str`
  - `guard_probes.shim_resolves() -> bool`
  - `guard_probes.probe_apm() -> ProbeResult`

- [ ] **Step 1: 失敗するテストを書く**

`scripts/claude-hooks/tests/test_guard_probes.py` を新規作成する。

```python
"""guard_probes の述語の仕様。

フック本体を subprocess 起動せず、共有層を直接 import して検査する。副作用 (print /
sys.exit) を持たない層なので、この形で仕様を読める。
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path

import guard_probes
import pytest
from conftest import REPO_ROOT

BOOTSTRAP = REPO_ROOT / "bootstrap.sh"


def test_shim_へ解決すれば健全(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shim = tmp_path / "libexec" / "apm"
    shim.parent.mkdir(parents=True)
    shim.write_text("#!/bin/sh\n", encoding="utf-8")
    shim.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "apm").symlink_to(shim)

    monkeypatch.setenv("PATH", str(bin_dir))
    monkeypatch.setenv("APM_INSTALL_GUARD_SHIM", str(shim))

    assert guard_probes.shim_resolves() is True
    assert guard_probes.probe_apm().healthy is True


def test_別の実体へ解決すれば沈黙(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shim = tmp_path / "libexec" / "apm"
    shim.parent.mkdir(parents=True)
    shim.write_text("#!/bin/sh\n", encoding="utf-8")
    other = tmp_path / "bin" / "apm"
    other.parent.mkdir(parents=True)
    other.write_text("#!/bin/sh\n", encoding="utf-8")
    other.chmod(0o755)

    monkeypatch.setenv("PATH", str(other.parent))
    monkeypatch.setenv("APM_INSTALL_GUARD_SHIM", str(shim))

    assert guard_probes.shim_resolves() is False
    result = guard_probes.probe_apm()
    assert result.healthy is False
    assert "bootstrap" in result.detail


def test_PATH_に_apm_が無ければ沈黙(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.setenv("APM_INSTALL_GUARD_SHIM", str(tmp_path / "nonexistent" / "apm"))

    assert guard_probes.shim_resolves() is False
    assert guard_probes.probe_apm().healthy is False


def test_shim_の置き場が配布先と一致する() -> None:
    """bootstrap.sh の SYMLINK_PAIRS を bash 自身に解釈させて読み、定数と突き合わせる。

    どちらか片方を直しても、もう片方が古いまま実配置と食い違う。文字列を写した検査では
    なく bash に解釈させるのは、配列の書式が変わったときに検査側が黙って空を返さないため。
    """
    script = f"source {shlex.quote(str(BOOTSTRAP))}; printf '%s\\n' \"${{SYMLINK_PAIRS[@]}}\""
    out = subprocess.run(
        ["bash", "-c", script], capture_output=True, text=True, check=True
    ).stdout
    pairs = [line for line in out.splitlines() if line]
    assert pairs, "SYMLINK_PAIRS を 1 件も読めていない"

    expected = guard_probes.DEFAULT_SHIM_PATH.removeprefix("~/")
    targets = [line.split("|", 1)[1] for line in pairs if "|" in line]
    assert expected in targets
```

- [ ] **Step 2: テストが落ちることを確認する**

Run: `uv run --directory scripts/claude-hooks pytest tests/test_guard_probes.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'guard_probes'`)

- [ ] **Step 3: 共有モジュールを書く**

`home/.claude/hooks/guard_probes.py` を新規作成する。

```python
"""検査層が沈黙している状態を見る述語と、その登録簿。

PreToolUse の 2 つのガードは、どちらも自分が機能していない状態を検出できない。検出できて
いる箇所はあるが、射程が実態より狭い。この層はセッション頭で生存を測るためのものである。

述語をここへ集めるのは、同じ判定を 2 箇所へ書くと片方だけ直したときに沈黙して食い違う
ためである。それはこの層が扱っている欠陥そのものなので、canonical を 1 つにする。

print と sys.exit は持たない。副作用を持ち込むとこの層だけを直接テストできなくなる
(pretooluse.py と同じ規則)。subprocess は持つので純関数ではない。

フックからは sys.path[0] (スクリプトのディレクトリ) 経由で解決される。
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

# 配布した shim の置き場。bootstrap.sh の SYMLINK_PAIRS が張る target と同じ値で、
# 一致は test_guard_probes.py の cross-pin テストが見る。
# 存在ではなく「PATH 上の apm がここへ解決されるか」を見る。ファイルがあっても PATH に
# 載っていなければ shim は一度も横取りしないので、存在検査は緑のまま守っていない状態を作る。
DEFAULT_SHIM_PATH = "~/.local/libexec/apm-guard/apm"

# tirith の応答検査に流すコマンド。副作用が無く、検出されないことを実測で確かめたもの。
# 検出される文字列を選ぶと監査カウンタの blocked が呼び出しごとに 1 増え、tirith が
# 働いているかを判断する材料そのものを、この検査が壊す (測定は ISSUE-59-spec.md)。
TIRITH_PROBE_COMMAND = "ls -la"

# 応答検査のタイムアウト (秒)。実測で 1 回あたり約 35 ミリ秒なので、この値は
# 「応答しない」を判定するための上限であって通常経路の待ち時間ではない。
TIRITH_PROBE_TIMEOUT = 5.0

# tirith の子プロセスへ渡す環境から落とす接頭辞。tirith-check.py と同じ規則で、
# 検査の基礎を外から動かせる変数を渡さないため。
_DROPPED_TIRITH_PREFIX = "TIRITH_"

# tirith が mise 経由で入っているときの shim。tirith-check.py と同じ探索順を保つ。
_MISE_TIRITH_SHIM = "~/.local/share/mise/shims/tirith"


@dataclass(frozen=True)
class ProbeResult:
    """プローブ 1 件の結果。detail は沈黙しているときだけ意味を持つ。

    名前を持たないのは、登録簿が名前と関数の組で持つためである。プローブの呼び出し自体が
    例外で落ちたときにも名前が要るので、結果側ではなく登録簿側が名前を持つ。
    """

    healthy: bool
    detail: str = ""


def shim_path() -> str:
    """検査する shim の置き場。テストで実在の shim を指すために上書きできる。

    無効化フラグ (APM_INSTALL_GUARD_DISABLE) と同じ接頭辞を使う。テストヘルパは基底環境から
    この接頭辞をまとめて落としてから必要なものだけ足すので、実行環境の設定がテストへ
    染み出さない。
    """
    return os.environ.get("APM_INSTALL_GUARD_SHIM") or DEFAULT_SHIM_PATH


def shim_resolves() -> bool:
    """PATH 上の apm が配布した shim へ解決されるか。

    パス文字列ではなく実体で比べる。shim は symlink として配置されるので、文字列比較では
    「解決先が symlink 自身か実体か」で結果が変わり、環境によって判定が揺れる。
    """
    resolved = shutil.which("apm")
    if resolved is None:
        return False
    try:
        return os.path.samefile(resolved, os.path.expanduser(shim_path()))
    except OSError:
        # どちらかが消えている / 辿れない。守れていないので偽を返す。
        return False


def probe_apm() -> ProbeResult:
    """apm ガードの shim が実際に横取りする位置にあるか。

    フックが見る PATH を測っている。フックは Claude Code のプロセスから起動されるので、
    対話シェルの PATH に載っていても Claude Code の PATH に載っていなければ守っていない。
    Claude Code は起動時に PATH を snapshot するため、配置しただけでは反映されない。
    """
    if shim_resolves():
        return ProbeResult(healthy=True)
    return ProbeResult(
        healthy=False,
        detail=(
            f"PATH 上の apm が {shim_path()} へ解決されないため、apm ガードは横取りしていない。"
            "フックが自力で捕まえる形 (素の apm / 絶対パス / PATH の一時差し替え) は deny "
            "されるが、包み込みや変数間接や xargs の形は無音で素通りする。"
            "直すには bootstrap.sh を実行し、そのあと Claude Code を再起動する。"
            "PATH は起動時に snapshot されるので、シェルの再読み込みでは足りない。"
        ),
    )
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run --directory scripts/claude-hooks pytest tests/test_guard_probes.py -q`
Expected: PASS (4 件)

- [ ] **Step 5: apm-install-guard.py を共有層へ寄せる**

`home/.claude/hooks/apm-install-guard.py` から `DEFAULT_SHIM_PATH` の定義ブロック、`shim_path`、`shim_resolves` を削除する。ファイル冒頭の `import pretooluse` の隣へ `import guard_probes` を足し、呼び出し箇所 (`if not shim_resolves():` と、その直後の deny 理由に埋め込まれている `shim_path()`) を `guard_probes.shim_resolves()` / `guard_probes.shim_path()` へ差し替える。

削除するブロックの直前にあるコメント (shim の置き場と cross-pin テストへの言及) も一緒に移す。コメントだけ残すと、指している定数が同じファイルに無い状態になる。

- [ ] **Step 6: cross-pin テストを移す**

`scripts/claude-hooks/tests/test_apm_install_guard.py` から `test_shim_path_matches_the_distributed_target` (720-729 行) と、そのためだけに使われている import (`shlex`、`BOOTSTRAP` 定数) を削除する。同名のテストは Step 1 で `test_guard_probes.py` へ日本語名で置いてあるので、内容の重複は残さない。

`BOOTSTRAP` 定数が他のテストからも使われている場合は残す。使われていなければ削除する。確認は次のコマンドで行う。

Run: `grep -n 'BOOTSTRAP\|shlex' scripts/claude-hooks/tests/test_apm_install_guard.py`
Expected: 残った参照が 0 件なら定数と import を削除、非 0 件なら残す

- [ ] **Step 7: per-file-ignores を足す**

`scripts/claude-hooks/pyproject.toml` の `[tool.ruff.lint.per-file-ignores]` へ 1 行足す。

```toml
"tests/test_guard_probes.py" = ["N802"]
```

- [ ] **Step 8: 実行ビットを落とす**

共有モジュールは孤児検出の対象外でなければならない。判定は mode なので、追跡下の mode を明示的に 100644 にする。

```bash
chmod 644 home/.claude/hooks/guard_probes.py
git add home/.claude/hooks/guard_probes.py
git ls-files -s home/.claude/hooks/guard_probes.py
```

Expected: 先頭が `100644`

- [ ] **Step 9: 全体を回して緑を確認する**

```bash
uv run --directory scripts/claude-hooks pytest -q
uv run --project scripts/config-guard config-guard .
```

Expected: pytest は既存 164 件に新規 4 件が加わって PASS、config-guard は問題なし

- [ ] **Step 10: コミット**

コミット本文を `.cache/commit-task1.txt` へ Write で書き、次で渡す。

```bash
git add home/.claude/hooks/guard_probes.py home/.claude/hooks/apm-install-guard.py scripts/claude-hooks/tests/test_guard_probes.py scripts/claude-hooks/tests/test_apm_install_guard.py scripts/claude-hooks/pyproject.toml
git commit -F .cache/commit-task1.txt
```

---

### Task 2: tirith プローブ

tirith のバイナリ解決を共有層へ移し、解決検査と応答検査の 2 段を持つプローブを足す。

**Files:**
- Modify: `home/.claude/hooks/guard_probes.py` (`resolve_tirith_bin` と `probe_tirith` と `PROBES` を追加)
- Modify: `home/.claude/hooks/tirith-check.py` (`_resolve_tirith_bin` を削除し import へ差し替え)
- Modify: `scripts/claude-hooks/tests/test_guard_probes.py` (tirith プローブのテストを追加)

**Interfaces:**
- Consumes: `guard_probes.ProbeResult` (Task 1)
- Produces:
  - `guard_probes.resolve_tirith_bin() -> str`
  - `guard_probes.probe_tirith() -> ProbeResult`
  - `guard_probes.PROBES: tuple[tuple[str, Callable[[], ProbeResult]], ...]`

- [ ] **Step 1: 失敗するテストを書く**

`scripts/claude-hooks/tests/test_guard_probes.py` の末尾へ足す。

```python
def _fake_tirith(path: Path, exit_code: int) -> Path:
    """指定の exit code を返す偽 tirith を作る。"""
    path.write_text(f"#!/bin/sh\nexit {exit_code}\n", encoding="utf-8")
    path.chmod(0o755)
    return path


def test_tirith_が_clean_へ応答すれば健全(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _fake_tirith(tmp_path / "tirith", 0)
    monkeypatch.setenv("TIRITH_BIN", str(fake))
    assert guard_probes.probe_tirith().healthy is True


def test_TIRITH_BIN_未設定で解決しなければ沈黙(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.delenv("TIRITH_BIN", raising=False)
    monkeypatch.setenv("PATH", str(empty))
    monkeypatch.setenv("HOME", str(tmp_path))

    result = guard_probes.probe_tirith()
    assert result.healthy is False
    assert "沈黙" in result.detail


def test_TIRITH_BIN_のパスが無ければ全_Bash_が止まると告げる(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TIRITH_BIN", str(tmp_path / "nonexistent" / "tirith"))

    result = guard_probes.probe_tirith()
    assert result.healthy is False
    assert "Bash" in result.detail


def test_clean_なコマンドに_clean_を返さなければ沈黙(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """応答はするが clean を clean と判定しない状態。フックは fail-closed に倒れる。"""
    fake = _fake_tirith(tmp_path / "tirith", 1)
    monkeypatch.setenv("TIRITH_BIN", str(fake))

    result = guard_probes.probe_tirith()
    assert result.healthy is False


def test_登録簿は名前と関数の組を持つ() -> None:
    """呼び出し自体が例外で落ちたときにも名前が要るので、名前は結果ではなく登録簿が持つ。"""
    names = [name for name, _ in guard_probes.PROBES]
    assert names == ["apm", "tirith"]
    for _, probe in guard_probes.PROBES:
        assert callable(probe)
```

- [ ] **Step 2: テストが落ちることを確認する**

Run: `uv run --directory scripts/claude-hooks pytest tests/test_guard_probes.py -q`
Expected: FAIL (`AttributeError: module 'guard_probes' has no attribute 'probe_tirith'`)

- [ ] **Step 3: 実装する**

`home/.claude/hooks/guard_probes.py` の末尾へ足す。

```python
def resolve_tirith_bin() -> str:
    """tirith バイナリのパスを解決する: TIRITH_BIN → PATH → mise shim (home 相対)。

    どれも無ければ "tirith" を返す。呼び出し側の subprocess が FileNotFoundError を投げ、
    そこで不在を判定する。machine 固有パスを settings に焼かず実行時に解決するのは、
    この設定が全プロジェクトで共有されるためである。
    """
    mise_shim = os.path.expanduser(_MISE_TIRITH_SHIM)
    return (
        os.environ.get("TIRITH_BIN")
        or shutil.which("tirith")
        or (mise_shim if os.path.exists(mise_shim) else None)
        or "tirith"
    )


def probe_tirith() -> ProbeResult:
    """tirith が解決し、clean なコマンドへ clean と応答するか。

    フックと同一のフラグと環境で呼ぶ。呼び方が違うとデーモンを経由するかどうかが変わり、
    フックが通る経路とは別のものを測ることになる。

    「起動するが何も検出しない」状態はここでは覆わない。覆うには検出される文字列を流す
    陰性対照が要るが、それは監査カウンタの blocked を呼び出しごとに 1 増やし、tirith が
    働いているかを判断する材料そのものを壊す (測定は ISSUE-59-spec.md)。
    """
    tirith_bin = resolve_tirith_bin()
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(_DROPPED_TIRITH_PREFIX)
    }
    env["TIRITH_INTEGRATION"] = "claude-code"

    try:
        result = subprocess.run(
            [
                tirith_bin,
                "check",
                "--json",
                "--non-interactive",
                "--shell",
                "posix",
                "--",
                TIRITH_PROBE_COMMAND,
            ],
            capture_output=True,
            text=True,
            timeout=TIRITH_PROBE_TIMEOUT,
            env=env,
        )
    except FileNotFoundError:
        if os.environ.get("TIRITH_BIN"):
            # 明示したパスが無い = 設定ミス。フックは fail-closed に倒れるので静かではないが、
            # 原因をここで名指しできる。
            return ProbeResult(
                healthy=False,
                detail=(
                    f"TIRITH_BIN={tirith_bin} が存在しないため、すべての Bash 呼び出しが "
                    "ブロックされる。パスを直すか TIRITH_BIN を解除する。"
                ),
            )
        return ProbeResult(
            healthy=False,
            detail=(
                f"{tirith_bin} が見つからないため、tirith の検査は沈黙している。"
                "コマンドは検査されないまま通る。mise で tirith を入れ直すと検査が戻る。"
            ),
        )
    except subprocess.TimeoutExpired:
        return ProbeResult(
            healthy=False,
            detail=(
                f"{tirith_bin} が {TIRITH_PROBE_TIMEOUT} 秒以内に応答しないため、"
                "すべての Bash 呼び出しがブロックされる。"
            ),
        )
    except OSError as exc:
        return ProbeResult(
            healthy=False,
            detail=f"{tirith_bin} を起動できない ({exc})。すべての Bash 呼び出しがブロックされる。",
        )

    if result.returncode != 0:
        return ProbeResult(
            healthy=False,
            detail=(
                f"{tirith_bin} が無害なコマンドを clean と判定しない (exit {result.returncode})。"
                "この状態ではすべての Bash 呼び出しがブロックされる。"
            ),
        )
    return ProbeResult(healthy=True)


# プローブの登録簿。名前を結果ではなくここが持つのは、プローブの呼び出し自体が例外で
# 落ちたときにも名前が要るためである。名前が無いと「検査できなかった」を報告できない。
PROBES: tuple[tuple[str, Callable[[], ProbeResult]], ...] = (
    ("apm", probe_apm),
    ("tirith", probe_tirith),
)
```

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run --directory scripts/claude-hooks pytest tests/test_guard_probes.py -q`
Expected: PASS (9 件)

- [ ] **Step 5: tirith-check.py を共有層へ寄せる**

`home/.claude/hooks/tirith-check.py` から `_resolve_tirith_bin` の定義 (docstring 含む) を削除し、`import pretooluse` の隣へ `import guard_probes` を足す。呼び出し箇所 (`_hook_event` の中と `main` の中) を `guard_probes.resolve_tirith_bin()` へ差し替える。

`shutil` の import が他で使われていなければ削除する。確認は次で行う。

Run: `grep -n 'shutil' home/.claude/hooks/tirith-check.py`
Expected: 残った参照が 0 件なら import を削除

- [ ] **Step 6: 既存の tirith テストが緑のままであることを確認する**

Run: `uv run --directory scripts/claude-hooks pytest tests/test_tirith_hook.py -q`
Expected: PASS (移設なので件数は変わらない)

- [ ] **Step 7: コミット**

コミット本文を `.cache/commit-task2.txt` へ Write で書いて渡す。

```bash
git add home/.claude/hooks/guard_probes.py home/.claude/hooks/tirith-check.py scripts/claude-hooks/tests/test_guard_probes.py
git commit -F .cache/commit-task2.txt
```

---

### Task 3: SessionStart フック

登録簿を回して、沈黙しているプローブがあれば 1 通にまとめて出す。

**Files:**
- Create: `home/.claude/hooks/guard-health.py` (mode 100755)
- Create: `scripts/claude-hooks/tests/test_guard_health.py`
- Modify: `scripts/claude-hooks/pyproject.toml` (`per-file-ignores` へ新テストを追加)

**Interfaces:**
- Consumes: `guard_probes.PROBES`、`guard_probes.ProbeResult` (Task 1 と Task 2)
- Produces: 実行可能なフック。健全なときは何も出さず、沈黙があれば次の形の JSON を 1 行出す

```json
{
  "systemMessage": "...",
  "hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "..."}
}
```

内部の関数も後続タスクの検体になる。

- `collect() -> list[tuple[str, guard_probes.ProbeResult]]` — 沈黙しているものだけを名前つきで返す
- `format_message(silent: list[tuple[str, guard_probes.ProbeResult]]) -> str`
- `emit(message: str) -> None`

- [ ] **Step 1: 失敗するテストを書く**

`scripts/claude-hooks/tests/test_guard_health.py` を新規作成する。

登録簿の差し替えは `PYTHONPATH` に偽モジュールを置く形では成立しない。Python は
スクリプトのディレクトリを `sys.path[0]` に置き、これが `PYTHONPATH` より先に解決される
ため、本物の `guard_probes` が常に勝つ。差し替えたつもりで実環境の健全性を見るテストに
なり、何も pin していないのに緑になる。フックを in-process にロードして
`guard_probes.PROBES` を差し替える。

```python
"""guard-health フックの仕様。

判定のロジックはフックを in-process にロードして検査する。フックはファイル名に
ハイフンを含み通常の import では解決できないので、既存のフックテストと同じく
importlib で読む。

起動形そのもの (subprocess として走り、exit 0 で、出力が空か妥当な JSON) は
最後に 1 件だけ subprocess で見る。この主張は実環境の健全性に依存しない。
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import guard_probes
import pytest
from conftest import HOOKS_DIR

HOOK = HOOKS_DIR / "guard-health.py"

SESSION_INPUT = json.dumps(
    {"hook_event_name": "SessionStart", "source": "startup", "session_id": "test"}
)


def _load_hook() -> ModuleType:
    """ハイフンを含むファイル名のフックをモジュールとして読む。"""
    spec = importlib.util.spec_from_file_location("guard_health", HOOK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _ok() -> guard_probes.ProbeResult:
    return guard_probes.ProbeResult(True)


def _silent(detail: str) -> guard_probes.ProbeResult:
    return guard_probes.ProbeResult(False, detail)


def test_全て健全なら沈黙は_0_件(monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_hook()
    monkeypatch.setattr(guard_probes, "PROBES", (("apm", _ok), ("tirith", _ok)))
    assert hook.collect() == []


def test_沈黙しているものだけを名前つきで返す(monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_hook()
    monkeypatch.setattr(
        guard_probes,
        "PROBES",
        (("apm", lambda: _silent("shim が横取りしていない")), ("tirith", _ok)),
    )
    silent = hook.collect()
    assert [name for name, _ in silent] == ["apm"]
    assert silent[0][1].detail == "shim が横取りしていない"


def test_プローブが落ちても他は走り落ちたことを報告する(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """検査できなかったことを健全へ潰さない。名前は登録簿が持つので落ちても分かる。"""
    hook = _load_hook()

    def boom() -> guard_probes.ProbeResult:
        raise RuntimeError("boom")

    monkeypatch.setattr(
        guard_probes,
        "PROBES",
        (("apm", boom), ("tirith", lambda: _silent("tirith が沈黙している"))),
    )
    silent = hook.collect()
    assert [name for name, _ in silent] == ["apm", "tirith"]
    assert "boom" in silent[0][1].detail


def test_文面は名前と件数と_detail_を持つ() -> None:
    hook = _load_hook()
    message = hook.format_message(
        [("apm", _silent("shim が横取りしていない")), ("tirith", _silent("解決しない"))]
    )
    assert "2 件" in message
    assert "[apm]" in message
    assert "[tirith]" in message
    assert "shim が横取りしていない" in message


def test_沈黙を両方の経路へ載せる(capsys: pytest.CaptureFixture[str]) -> None:
    """systemMessage はユーザーの UI へ、additionalContext はモデルの文脈へ届く。

    片方だけでは届かない相手が出る。両方に同じ文面を載せることを pin する。
    """
    hook = _load_hook()
    hook.emit("テスト文面")
    payload = json.loads(capsys.readouterr().out)
    assert payload["systemMessage"] == "テスト文面"
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert payload["hookSpecificOutput"]["additionalContext"] == "テスト文面"


def test_起動形が壊れていない() -> None:
    """実際の起動形で走り、exit 0 で、出力が空か妥当な JSON であること。

    実環境のガードが健全かどうかには依存しない主張にしてある。健全性まで見ると、
    テストの意味が実行環境で変わる。
    """
    proc = subprocess.run(
        [sys.executable, str(HOOK)],
        input=SESSION_INPUT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    if proc.stdout.strip():
        payload = json.loads(proc.stdout)
        assert "systemMessage" in payload
        assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
```

- [ ] **Step 2: テストが落ちることを確認する**

Run: `uv run --directory scripts/claude-hooks pytest tests/test_guard_health.py -q`
Expected: FAIL (フックが存在しないので `_load_hook` が `FileNotFoundError`)

- [ ] **Step 3: フックを書く**

`home/.claude/hooks/guard-health.py` を新規作成する。

```python
#!/usr/bin/env python3
"""SessionStart で検査層の生存を測り、沈黙していれば 1 通で告げる。

SessionStart はセッションを止められない (exit 2 でも続行し stderr が出るだけ) ので、
この層は告げるだけである。強制は PreToolUse 側の責務のまま変わらない。

告げ先を 2 つ持つのは、届く相手が違うためである。systemMessage はトップレベルの
フィールドでユーザーの UI へ出る。additionalContext は hookSpecificOutput の中で
モデルの文脈へ入る。両方へ同じ文面を載せて、ユーザーとモデルの双方が同じものを見る。

健全なときは何も出さない。毎セッションの出力はノイズになるためである。この選択で
「健全」と「この検査自体が走らなかった」は実行時には区別できなくなるが、その区別は
配線を静的に pin する層 (config-guard) が持つ。実行時は黙り、配線は叫ぶ。

matcher は settings.json 側で全開始理由を覆う。compact でも発火するので、長時間走る
セッションでは再告知が自動的に起きる。再告知の機構をここへ書かずに済む。
"""

from __future__ import annotations

import json
import sys

import guard_probes

_HOOK_EVENT_NAME = "SessionStart"


def collect() -> list[tuple[str, guard_probes.ProbeResult]]:
    """登録簿を回して、沈黙しているものだけを名前つきで返す。

    1 件が例外を投げても他は走らせる。落ちたプローブは沈黙として報告する。検査できな
    かったことを健全へ潰すと、この層自身が沈黙する側へ回る。
    """
    silent: list[tuple[str, guard_probes.ProbeResult]] = []
    for name, probe in guard_probes.PROBES:
        try:
            result = probe()
        except Exception as exc:  # noqa: BLE001 - プローブの失敗はすべて沈黙として扱う
            silent.append(
                (name, guard_probes.ProbeResult(False, f"プローブ自身が失敗した: {exc}"))
            )
            continue
        if not result.healthy:
            silent.append((name, result))
    return silent


def format_message(silent: list[tuple[str, guard_probes.ProbeResult]]) -> str:
    """沈黙しているプローブを 1 通の文面にまとめる。"""
    head = f"検査層の健全性: {len(silent)} 件が沈黙している"
    body = "\n".join(f"[{name}] {result.detail}" for name, result in silent)
    return f"{head}\n\n{body}"


def emit(message: str) -> None:
    """ユーザーの UI とモデルの文脈の両方へ同じ文面を載せる。

    systemMessage だけだとモデルが知らないまま作業を続け、additionalContext だけだと
    ユーザーの端末が静かなままになる。直せるのはユーザーだけなので両方へ載せる。
    """
    print(
        json.dumps(
            {
                "systemMessage": message,
                "hookSpecificOutput": {
                    "hookEventName": _HOOK_EVENT_NAME,
                    "additionalContext": message,
                },
            },
            ensure_ascii=False,
        )
    )


def main() -> int:
    # 入力は使わないが読む。読まないと書き手が EPIPE を受けうる。
    try:
        sys.stdin.read()
    except OSError:
        pass

    silent = collect()
    if not silent:
        return 0
    emit(format_message(silent))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001 - 落ちたことを黙って隠さない
        # この層が落ちたこと自体を告げる。stderr へ倒すとモデルの文脈へ入らない。
        emit(f"検査層の健全性チェック自体が失敗した: {exc}")
        sys.exit(0)
```

- [ ] **Step 4: 実行ビットを立てる**

```bash
chmod 755 home/.claude/hooks/guard-health.py
git add home/.claude/hooks/guard-health.py
git ls-files -s home/.claude/hooks/guard-health.py
```

Expected: 先頭が `100755`

- [ ] **Step 5: テストが通ることを確認する**

Run: `uv run --directory scripts/claude-hooks pytest tests/test_guard_health.py -q`
Expected: PASS (6 件)

- [ ] **Step 6: per-file-ignores を足す**

`scripts/claude-hooks/pyproject.toml` の `[tool.ruff.lint.per-file-ignores]` へ 1 行足す。

```toml
"tests/test_guard_health.py" = ["N802"]
```

- [ ] **Step 7: lint と型検査を通す**

```bash
uv run --directory scripts/claude-hooks ruff check .
uv run --directory scripts/claude-hooks ruff format --check .
uv run --directory scripts/claude-hooks mypy .
```

Expected: すべて問題なし。`_load_hook` が返すのは動的にロードしたモジュールなので、
mypy が属性を追えず `Any` として扱う。strict でも `ModuleType` からの属性アクセスは
許されるが、警告が出る場合はテストファイル側で対処する (実装側の型を緩めない)。

- [ ] **Step 8: コミット**

コミット本文を `.cache/commit-task3.txt` へ Write で書いて渡す。

```bash
git add home/.claude/hooks/guard-health.py scripts/claude-hooks/tests/test_guard_health.py scripts/claude-hooks/pyproject.toml
git commit -F .cache/commit-task3.txt
```

---

### Task 4: 配線と必須フック検査のイベント軸への一般化

settings.json へ登録し、config-guard の必須フック検査を PreToolUse 固定から外す。

**Files:**
- Modify: `scripts/config-guard/tests/conftest.py` (定数とヘルパを 1 つずつ追加)
- Modify: `scripts/config-guard/src/config_guard/settings_invariants.py:30` および 6 番の検査
- Modify: `scripts/config-guard/tests/test_settings_invariants.py` (GOOD フィクスチャの更新と新規テスト)
- Modify: `home/.claude/settings.json` (SessionStart グループを 1 つ追加)

**Interfaces:**
- Consumes: Task 3 が作った `guard-health.py`
- Produces:
  - `config_guard.settings_invariants._REQUIRED_HOOKS: dict[str, tuple[str, ...]]`
  - `tests.conftest.GUARD_HEALTH_HOOK_COMMAND: str`
  - `tests.conftest.session_start(*groups: dict[str, Any]) -> dict[str, Any]`

- [ ] **Step 1: テストヘルパを足す**

`scripts/config-guard/tests/conftest.py` へ定数 1 つとヘルパ 1 つを足す。定数は既存の
`TIRITH_HOOK_COMMAND` / `APM_GUARD_HOOK_COMMAND` の隣へ置く。

```python
GUARD_HEALTH_HOOK_COMMAND = 'python3 "$HOME/.claude/hooks/guard-health.py"'


def session_start(*groups: dict[str, Any]) -> dict[str, Any]:
    """hooks セクションの SessionStart 部分を作る。

    matcher の既定を持たせないのは、SessionStart の matcher が開始理由を見るためである。
    hook_group の既定 (Bash) はツール名なので、呼び出し側が matcher を明示する。
    """
    return {"SessionStart": list(groups)}
```

定数は `settings_invariants` の `_REQUIRED_HOOKS` から生成しないこと。生成すると clean
フィクスチャが常に検査を満たし、pin が自己参照で空虚になる。同じ理由は既存の 2 定数の
コメントが持っている。

- [ ] **Step 2: 失敗するテストを書く**

`scripts/config-guard/tests/test_settings_invariants.py` の import へ `GUARD_HEALTH_HOOK_COMMAND`
と `session_start` を足し、末尾へ次を足す。

```python
def _settings_with_hooks(hooks: dict[str, Any]) -> dict[str, Any]:
    """必須の除外だけを満たした最小 settings に、渡された hooks を載せる。"""
    return {
        "claudeMdExcludes": ["**/home/.claude/CLAUDE.md"],
        "hooks": hooks,
    }


def _pretooluse_group() -> dict[str, Any]:
    """PreToolUse の必須フックを 1 グループにまとめたもの。"""
    return hook_group(TIRITH_HOOK_COMMAND, APM_GUARD_HOOK_COMMAND)


def _guard_health_group(matcher: str = "*") -> dict[str, Any]:
    """SessionStart の必須フックを 1 グループにまとめたもの。"""
    return hook_group(GUARD_HEALTH_HOOK_COMMAND, matcher=matcher)


def test_SessionStart_の必須フックが無ければ検出する() -> None:
    settings = _settings_with_hooks(pretooluse(_pretooluse_group()))
    findings = check_settings_invariants(settings)
    assert any("guard-health.py" in f.detail for f in findings)


def test_SessionStart_に配線されていれば検出しない() -> None:
    settings = _settings_with_hooks(
        {**pretooluse(_pretooluse_group()), **session_start(_guard_health_group())}
    )
    findings = check_settings_invariants(settings)
    assert not any("guard-health.py" in f.detail for f in findings)


def test_開始理由を絞った_matcher_は配線として数えない() -> None:
    """SessionStart の matcher は開始理由を見る。startup だけでは compact で発火しない。"""
    settings = _settings_with_hooks(
        {
            **pretooluse(_pretooluse_group()),
            **session_start(_guard_health_group(matcher="startup")),
        }
    )
    findings = check_settings_invariants(settings)
    assert any("guard-health.py" in f.detail for f in findings)


def test_ツール名の_matcher_を_SessionStart_の配線として数えない() -> None:
    """PreToolUse の述語を使い回すと Bash が全一致して配線済みに見える。"""
    settings = _settings_with_hooks(
        {
            **pretooluse(_pretooluse_group()),
            **session_start(_guard_health_group(matcher="Bash")),
        }
    )
    findings = check_settings_invariants(settings)
    assert any("guard-health.py" in f.detail for f in findings)


def test_PreToolUse_の必須フックは引き続き検出される() -> None:
    """イベント軸へ一般化しても既存の検査が緩まないことを見る。"""
    settings = _settings_with_hooks(
        {
            **pretooluse(hook_group(TIRITH_HOOK_COMMAND)),
            **session_start(_guard_health_group()),
        }
    )
    findings = check_settings_invariants(settings)
    assert any("apm-install-guard.py" in f.detail for f in findings)
```

- [ ] **Step 3: テストが落ちることを確認する**

Run: `uv run --project scripts/config-guard pytest tests/test_settings_invariants.py -q`
Expected: FAIL。`guard-health.py` をまだ要求していないので 1 件目と 3 件目と 4 件目が落ちる

- [ ] **Step 4: 実装する**

`scripts/config-guard/src/config_guard/settings_invariants.py:30` の `_REQUIRED_PRETOOLUSE_HOOKS`
を次へ差し替える。既存のコメント (取り付けを不変条件にする理由) はそのまま残し、名前で
宣言する理由を足す。

```python
# 必ず配線されていなければならないフック（本体のファイル名で照合する）。
# フック本体が存在しても settings.json から外れれば何も守らないため、取り付け自体を
# 不変条件にする。これが無いと検査機構の 3 種変異のうち「取り付けを外す」をテストで
# 捕まえられない（実際この検査を足すまで、tirith-check.py の配線を外しても全テストが緑だった）。
#
# 名前で宣言するのは、存在するファイルの集合から必須集合を導くと、本体を消せば要求も
# 消えて緑になるためである。それは検査が必要な状況でだけ検査が動かない自己敗北にあたる。
# 配線漏れの検出は逆向きなので導出でよく、hook_wiring が持つ。
_REQUIRED_HOOKS: dict[str, tuple[str, ...]] = {
    "PreToolUse": ("tirith-check.py", "apm-install-guard.py"),
    "SessionStart": ("guard-health.py",),
}
```

`_matcher_covers_guarded_tool` の下へ次を足す。

```python
def _matcher_covers_all_sources(matcher: Any) -> bool:
    """SessionStart のグループが全開始理由を覆うか。

    SessionStart の matcher はツール名ではなく開始理由 (startup / resume / clear /
    compact / fork) を見る。PreToolUse の述語を使い回すと、ツール名を書いたグループが
    全一致して配線済みに見える。

    全理由に一致する書き方 (省略・空文字・"*") だけを配線として数える。個々の理由を
    列挙する形は数えない。理由の一覧を literal で持つと、Claude Code が理由を増やした
    ときに検査側だけが古くなるためである。この向きの誤りは「動いている配線を咎める」
    可視で安価な失敗で済み、逆向きに緩めると発火しない配線を配線済みと読む。
    """
    return matcher is None or matcher in ("", "*")


# イベントごとの matcher 述語。matcher の意味がイベントで違うので、1 つの述語を
# 使い回さない。使い回すと SessionStart にツール名を書いた配線が全一致で通る。
_MATCHER_PREDICATES: dict[str, Callable[[Any], bool]] = {
    "PreToolUse": _matcher_covers_guarded_tool,
    "SessionStart": _matcher_covers_all_sources,
}
```

`_pretooluse_commands` をイベント引数付きへ一般化して `_wired_commands` へ改名する。

```python
def _wired_commands(settings: dict[str, Any], event: str) -> list[str]:
    """hooks[event] で、そのイベントの述語を満たすグループの command 文字列を集める。

    グループを分けるか 1 グループに複数要素を置くかは配線の自由度なので、両方を平らに集める。
    述語を満たさないグループは数えない。本体が残っていても起動しないので、
    それは配線を外したのと同じである。
    """
    covers = _MATCHER_PREDICATES[event]
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return []
    groups = hooks.get(event)
    if not isinstance(groups, list):
        return []

    commands: list[str] = []
    for group in groups:
        if not isinstance(group, dict):
            continue
        if not covers(group.get("matcher")):
            continue
        entries = group.get("hooks")
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            command = entry.get("command")
            if isinstance(command, str):
                commands.append(command)
    return commands
```

`check_settings_invariants` の 6 番を次へ差し替える。

```python
    # 6. 必須フックが各イベントへ配線されているか
    for event, scripts in _REQUIRED_HOOKS.items():
        commands = _wired_commands(settings, event)
        for script in scripts:
            if not any(script in command for command in commands):
                findings.append(
                    Finding(_SRC, script, f"{event} に必須フックが配線されていません: {script}")
                )
```

冒頭の import へ `Callable` を足す。

```python
from collections.abc import Callable
```

- [ ] **Step 5: 既存の GOOD フィクスチャを更新する**

`scripts/config-guard/tests/test_settings_invariants.py` の `GOOD` は `hooks` に PreToolUse
しか持たないため、この変更で `test_clean_settings_has_no_findings` が落ちる。SessionStart の
配線を足す。

```python
    # 必須フックの配線。欠けていると他の検査のテストにも findings が混ざるため、
    # 「狙った検査だけが落とす」最小の差分を保つ意味でも clean な形をここに置く。
    # SessionStart の matcher は開始理由を見るので "*" を明示する
    "hooks": {
        **pretooluse(hook_group(TIRITH_HOOK_COMMAND), hook_group(APM_GUARD_HOOK_COMMAND)),
        **session_start(hook_group(GUARD_HEALTH_HOOK_COMMAND, matcher="*")),
    },
```

このフィクスチャの更新が要ること自体が、必須宣言が効いている証拠である。落ちなければ
新しい要求が pin されていない。

- [ ] **Step 6: settings.json へ配線する**

`home/.claude/settings.json` の `hooks.SessionStart` 配列へ、既存の 3 グループと同じ形で
1 つ足す。

```json
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/hooks/guard-health.py\"",
            "timeout": 10
          }
        ]
      }
```

- [ ] **Step 7: テストが通ることを確認する**

```bash
uv run --project scripts/config-guard pytest -q
uv run --project scripts/config-guard config-guard .
```

Expected: pytest は既存に新規 5 件が加わって PASS、config-guard は問題なし

- [ ] **Step 8: コミット**

コミット本文を `.cache/commit-task4.txt` へ Write で書いて渡す。

```bash
git add home/.claude/settings.json scripts/config-guard/src/config_guard/settings_invariants.py scripts/config-guard/tests/test_settings_invariants.py scripts/config-guard/tests/conftest.py
git commit -F .cache/commit-task4.txt
```

---

### Task 5: 孤児検出

フック本体が settings.json のどこにも現れないものを検出する。

**Files:**
- Create: `scripts/config-guard/src/config_guard/hook_wiring.py`
- Modify: `scripts/config-guard/src/config_guard/cli.py` (import と `scan()` への追加、モジュール docstring の検査項目一覧)
- Create: `scripts/config-guard/tests/test_hook_wiring.py`

**Interfaces:**
- Consumes: `config_guard.git_run.run_git_checked`、`config_guard.models.Finding`、`tests.conftest` の git ヘルパ
- Produces: `check_hook_wiring(repo_root: str) -> list[Finding]`

- [ ] **Step 1: 失敗するテストを書く**

`scripts/config-guard/tests/test_hook_wiring.py` を新規作成する。git の起動は必ず
`tests.conftest` のヘルパを通すこと。各テストファイルが `subprocess.run` を手書きすると
ロケーション系 `GIT_*` の隔離を忘れる穴が開く (同 conftest の docstring が持つ理由)。

```python
"""hook_wiring の仕様。

使い捨てリポジトリを作り、実行ビットと settings.json の組み合わせを変えて検査する。
本体リポジトリを対象にすると、実装の変更ではなく本体の状態でテストの意味が変わる。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config_guard.hook_wiring import check_hook_wiring
from tests.conftest import init_repo, run_git, write_file

_WIRED: dict[str, Any] = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Bash",
                "hooks": [{"type": "command", "command": 'python3 "$HOME/.claude/hooks/a.py"'}],
            }
        ]
    }
}


def _repo(tmp_path: Path, hooks: dict[str, int], settings: dict[str, Any]) -> Path:
    """フックと settings.json を持つ使い捨てリポジトリを作って commit する。

    hooks は「ファイル名 -> mode」。mode は 0o755 か 0o644 を渡す。
    """
    root = tmp_path / "repo"
    root.mkdir()
    init_repo(root)
    write_file(root, "home/.claude/settings.json", json.dumps(settings, ensure_ascii=False))
    for name, mode in hooks.items():
        path = write_file(root, f"home/.claude/hooks/{name}", "#!/usr/bin/env python3\n")
        path.chmod(mode)
    run_git(root, "add", "-A")
    run_git(root, "commit", "-qm", "init")
    return root


def test_配線されたフックは孤児にしない(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"a.py": 0o755}, _WIRED)
    assert check_hook_wiring(str(root)) == []


def test_どこにも現れないフックを孤児として検出する(tmp_path: Path) -> None:
    root = _repo(tmp_path, {"a.py": 0o755, "orphan.py": 0o755}, _WIRED)
    findings = check_hook_wiring(str(root))
    assert [f.detail for f in findings] == ["orphan.py"]


def test_実行ビットの無いファイルは共有モジュールとして除く(tmp_path: Path) -> None:
    """共有モジュールは配線されないのが正しい。実行ビットが本体と分けている。"""
    root = _repo(tmp_path, {"a.py": 0o755, "shared.py": 0o644}, _WIRED)
    assert check_hook_wiring(str(root)) == []


def test_どのイベントに現れてもよい(tmp_path: Path) -> None:
    """どのイベントへ配線するのが正しいかは名前で宣言する層の担当で、ここは所在だけを見る。"""
    settings: dict[str, Any] = {
        "hooks": {
            "SessionStart": [
                {
                    "matcher": "*",
                    "hooks": [
                        {"type": "command", "command": 'python3 "$HOME/.claude/hooks/a.py"'}
                    ],
                }
            ]
        }
    }
    root = _repo(tmp_path, {"a.py": 0o755}, settings)
    assert check_hook_wiring(str(root)) == []


def test_settings_json_が読めなければ検査できないと告げる(tmp_path: Path) -> None:
    """読めないことを「孤児なし」へ潰さない。"""
    root = _repo(tmp_path, {"a.py": 0o755}, _WIRED)
    (root / "home" / ".claude" / "settings.json").write_text("{ broken", encoding="utf-8")
    findings = check_hook_wiring(str(root))
    assert len(findings) == 1
    assert "settings.json" in findings[0].detail
```

- [ ] **Step 2: テストが落ちることを確認する**

Run: `uv run --project scripts/config-guard pytest tests/test_hook_wiring.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'config_guard.hook_wiring'`)

- [ ] **Step 3: 実装する**

`scripts/config-guard/src/config_guard/hook_wiring.py` を新規作成する。

```python
"""フック本体が settings.json のどこかへ配線されているかの検査。

必須であることの宣言は settings_invariants が名前で持つ。こちらは逆向きで、
「本体があるのにどこにも現れない」を導出で拾う。導出でよいのは、ファイルが消えても
要求が消えないためである (要求は名前で宣言する層が別に持っている)。

フック本体と共有モジュールの区別に実行ビットを使う。追跡下の mode は本体が 100755、
共有モジュールが 100644 で既に分かれており、新しい規約を作らずに済む。実行ビットを
落とすと検出から外れるので、その形は変異注入で確認する。

配線されているかはコマンド文字列に basename が現れるかで見る。イベントも matcher も
問わない。どのイベントへ配線するのが正しいかは名前で宣言する層の担当で、ここは
「どこにも無い」だけを見る。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config_guard.git_run import run_git_checked
from config_guard.models import Finding

_SRC = "home/.claude/hooks"

# フック本体の追跡下 mode。共有モジュールは 100644 なのでここに一致しない。
_EXECUTABLE_MODE = "100755"

# 走査する pathspec。
_HOOKS_PATHSPEC = "home/.claude/hooks"

# 配線の宣言を読む先。
_SETTINGS_PATH = "home/.claude/settings.json"


def _executable_hooks(repo_root: str) -> list[str]:
    """追跡下のフック本体の basename を返す。

    NUL 区切りで受けるのは、改行区切りだと非 ASCII のパスがクォートされて件数が
    静かに落ちるためである (git ls-files の既定の挙動)。
    """
    stdout = run_git_checked(repo_root, "ls-files", "-s", "-z", _HOOKS_PATHSPEC)
    names: list[str] = []
    for record in stdout.split("\0"):
        if not record or "\t" not in record:
            continue
        meta, path = record.split("\t", 1)
        fields = meta.split()
        if not fields or fields[0] != _EXECUTABLE_MODE:
            continue
        names.append(Path(path).name)
    return names


def _iter_strings(obj: Any) -> list[str]:
    """オブジェクトを再帰的に走査してすべての文字列を返す。"""
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


def check_hook_wiring(repo_root: str) -> list[Finding]:
    """フック本体で settings.json に一度も現れないものを Finding で返す。"""
    settings_file = Path(repo_root) / _SETTINGS_PATH
    if not settings_file.exists():
        return []
    try:
        settings = json.loads(settings_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        # 読めないことを「孤児なし」へ潰さない。settings.json の構造は
        # settings_invariants が別途見るので、ここは検査できなかったことだけを告げる。
        return [Finding(_SRC, _SETTINGS_PATH, "settings.json を読めないため配線を検査できません")]

    wired = _iter_strings(settings)
    findings: list[Finding] = []
    for name in sorted(_executable_hooks(repo_root)):
        if not any(name in text for text in wired):
            findings.append(
                Finding(
                    _SRC, name, f"フック本体が settings.json のどこにも配線されていません: {name}"
                )
            )
    return findings
```

`_iter_strings` は `settings_invariants` にも同名の関数がある。片方が settings.json の
dict を、もう片方が同じ dict を走査するので、共有せず各モジュールが持つ形にしてある。
これを共有層へ寄せるかは Issue 26 の「共通基盤の集約」の領分なので、この PR では触らない。

- [ ] **Step 4: テストが通ることを確認する**

Run: `uv run --project scripts/config-guard pytest tests/test_hook_wiring.py -q`
Expected: PASS (5 件)

- [ ] **Step 5: cli へ載せる**

`scripts/config-guard/src/config_guard/cli.py` の import 群へ足す (アルファベット順の位置へ)。

```python
from config_guard.hook_wiring import check_hook_wiring
```

`scan()` の `check_settings_invariants` の直後へ足す。

```python
    # フック本体が settings.json のどこにも配線されていないもの (孤児) を検出する。
    # 必須の宣言は settings_invariants が名前で持ち、こちらは導出で漏れを拾う。
    # 新しいフックを足して配線を忘れると、本体はあるのに一度も起動しない状態になる
    findings.extend(check_hook_wiring(str(root)))
```

モジュール docstring の検査項目一覧へ 1 句足す。

- [ ] **Step 6: scan への取り付けを pin する**

`scripts/config-guard/tests/test_cli.py` へ、`scan()` の結果に孤児検出が含まれることを
見るテストを足す。取り付けを外す変異が既存のテストでは捕まらないためである。既存の
テストが使っている使い捨てリポジトリの組み立て方に合わせること。

```python
def test_scan_は孤児検出を含む(tmp_path: Path) -> None:
    """cli への取り付けを外すと本体スキャンから孤児検出が消える。単体テストは通り続ける。"""
    root = tmp_path / "repo"
    root.mkdir()
    init_repo(root)
    write_file(root, "home/.claude/settings.json", "{}")
    path = write_file(root, "home/.claude/hooks/orphan.py", "#!/usr/bin/env python3\n")
    path.chmod(0o755)
    run_git(root, "add", "-A")
    run_git(root, "commit", "-qm", "init")

    findings = scan(str(root))
    assert any("orphan.py" in f.detail for f in findings)
```

- [ ] **Step 7: 本体リポジトリで孤児が 0 件であることを確認する**

Run: `uv run --project scripts/config-guard config-guard .`
Expected: 問題なし (Task 4 で `guard-health.py` を配線済みのため)

孤児が 0 件であることは「検査が働いた」ことの証拠にならない。働いたことは Step 6 の
テストと、Task 6 の取り付け変異が持つ。

- [ ] **Step 8: コミット**

コミット本文を `.cache/commit-task5.txt` へ Write で書いて渡す。

```bash
git add scripts/config-guard/src/config_guard/hook_wiring.py scripts/config-guard/src/config_guard/cli.py scripts/config-guard/tests/test_hook_wiring.py scripts/config-guard/tests/test_cli.py
git commit -F .cache/commit-task5.txt
```

---

### Task 6: 変異注入と射程の穴の記録

pin が実際に効いていることを確かめ、この層が覆わない範囲を数える。

**Files:**
- Modify: `docs/issues/ISSUE-59_検査層が沈黙している状態をセッション頭で検出する/issue.md` (タスクのチェックと、射程の表を追加)

**Interfaces:**
- Consumes: Task 1 から Task 5 の成果すべて
- Produces: なし (記録のみ)

- [ ] **Step 1: 変異を 1 件ずつ適用して赤を確認する**

各変異は 1 件だけ適用し、対応するものが赤くなることを確認してから元へ戻す。まとめて適用
すると、どの変異が何を赤くしたかが分からなくなる。

「赤くなるはずのもの」には単体テストと本体スキャンの 2 種がある。実ファイル
(`settings.json` や `cli.py`) を変える変異は、自前の dict を組む単体テストには届かない。
届かないことを「変異が捕まらない」と読むと、取り付けの pin が無いのに有ると錯覚する。

| # | 種別 | 変異 | 赤くなるはずのもの |
| --- | --- | --- | --- |
| 1 | 検査対象 | `guard_probes.shim_resolves` の `samefile` を文字列比較 (`==`) へ変える | `test_shim_へ解決すれば健全` (symlink 経由で偽になる) |
| 2 | 検査対象 | `probe_tirith` の `result.returncode != 0` を `False` へ変える | `test_clean_なコマンドに_clean_を返さなければ沈黙` |
| 3 | 検査対象 | `probe_tirith` の FileNotFoundError 分岐で `TIRITH_BIN` の有無を見ずに常に沈黙の文面を返す | `test_TIRITH_BIN_のパスが無ければ全_Bash_が止まると告げる` |
| 4 | 検査対象 | `guard_probes.DEFAULT_SHIM_PATH` を別のパスへ変える | `test_shim_の置き場が配布先と一致する` (bootstrap.sh との cross-pin) |
| 5 | 検査機構 | `guard-health.py` の `collect` から try/except を外す | `test_プローブが落ちても他は走り落ちたことを報告する` |
| 6 | 検査機構 | `guard-health.py` の `emit` から `systemMessage` を落とす | `test_沈黙を両方の経路へ載せる` |
| 7 | 検査機構 | `guard-health.py` の `emit` から `hookSpecificOutput` を落とす | 同上 |
| 8 | 検査機構 | `_matcher_covers_all_sources` を `_matcher_covers_guarded_tool` の別名にする | `test_ツール名の_matcher_を_SessionStart_の配線として数えない` |
| 9 | 検査機構 | `hook_wiring._EXECUTABLE_MODE` を `100644` へ変える | `test_実行ビットの無いファイルは共有モジュールとして除く` |
| 10 | 検査機構 | `_REQUIRED_HOOKS` から SessionStart のエントリを削除する | `test_SessionStart_の必須フックが無ければ検出する` |
| 11 | 検査機構 | `_REQUIRED_HOOKS` の PreToolUse から `apm-install-guard.py` を削除する | `test_PreToolUse_の必須フックは引き続き検出される` (イベント軸への一般化で既存の検査が緩んでいないか) |
| 12 | 取り付け | 実ファイル `home/.claude/settings.json` から `guard-health.py` のグループを削除する | 本体スキャン (`config-guard .`) が必須フック欠落と孤児の 2 件を出す。単体テストは自前の dict を組むので届かない |
| 13 | 取り付け | `cli.scan()` から `check_hook_wiring` の呼び出しを削除する | `test_scan_は孤児検出を含む` (Task 5 Step 6 で足したもの) |
| 14 | 取り付け | `guard-health.py` の実行ビットを落とす (`chmod 644`) | 何も赤くならない。これは既知の穴で、射程の表へ記録する |

変異 14 は赤くならないことが期待値である。実行ビットを落とすと孤児検出の母集団から静かに
外れるので、配線を消さなくても検査から消える。塞ぐには mode ではない判定基準が要り、
それは新しい規約を作ることになる。この PR では塞がず、穴として数えて記録する。

- [ ] **Step 2: 変異が下流で吸収されていないことを確かめる**

赤くなった各件について、その変異のせいで赤いことを確認する。過去に、変異が狙った分岐へ
届いていたのに検体が後段で同じ出力へ収束して観測できなかった例がある。赤くならなかった
変異は、変異が悪いのではなく検体の選び方が悪い可能性を先に疑う。

変異 14 のように「赤くならないことが期待値」のものは、期待どおりであることを確認する。
期待していない緑と、期待した緑を、記録の上で混ぜない。

- [ ] **Step 3: 射程の穴を数えて Issue へ記録する**

`issue.md` へ次の表を足す。実装した層が覆うものと覆わないものを、数えた形で残す。

| 対象 | 覆う | 覆わない |
| --- | --- | --- |
| apm の shim が PATH 上に居ない | はい | |
| apm の shim を迂回する形そのもの | | はい。この層は状態を告げるだけ |
| tirith のバイナリが解決しない | はい | |
| tirith が応答しない / clean を clean と言わない | はい | |
| tirith が応答するが何も検出しない | | はい。陰性対照が監査統計を壊すため |
| フック本体が settings.json から外れた | はい (config-guard の 2 層) | |
| フック本体の実行ビットが落ちた | | はい。孤児検出の母集団から静かに外れる (変異 14 で確認) |
| `home/.claude/hooks/` 以外の検査層 | | はい。登録簿は 2 件で始める |
| この層自身が settings.json から外れた | はい (必須宣言) | |
| この層自身が例外で落ちた | はい (文面として告げる) | |

- [ ] **Step 4: issue.md のタスクをチェックする**

`issue.md` の `## タスク` のうち、この PR で完了したものを `[x]` にする。

「コマンド単位の暫定告知 (tirith-check.py の fail-open 経路) を、この層ができたら畳む」は
残す。畳むと tirith 不在時にコマンド単位の文脈が消えるので、この層が実運用で効くことを
確かめてから決める。残す判断の理由も本文へ書く。

- [ ] **Step 5: コミット**

コミット本文を `.cache/commit-task6.txt` へ Write で書いて渡す。

```bash
git add "docs/issues/ISSUE-59_検査層が沈黙している状態をセッション頭で検出する/issue.md"
git commit -F .cache/commit-task6.txt
```

---

### Task 7: live smoke と PR

実環境で 1 度通す。純粋ロジックのテストが緑でも、subprocess とフックの配線がランタイムで
壊れていないことは別に確かめる必要がある。

**Files:**
- なし (検証とコミット済み成果物の公開)

**Interfaces:**
- Consumes: Task 1 から Task 6 のすべて
- Produces: なし

- [ ] **Step 1: フックを手で起動して出力を見る**

```bash
echo '{"hook_event_name":"SessionStart","source":"startup","session_id":"smoke"}' \
  | python3 home/.claude/hooks/guard-health.py
```

Expected: 現在のセッションでは apm の shim が Claude Code の PATH に載っていないため、
`systemMessage` と `hookSpecificOutput.additionalContext` の両方を持つ JSON が 1 行出る。
tirith 側は健全なので文面に現れない。

この期待は「配置したあとも Claude Code を再起動するまで沈黙を報告し続ける」という
spec の記述と一致する。誤報ではない。

- [ ] **Step 2: 全検査を通す**

```bash
bats scripts/tests/
uv run --directory scripts/claude-hooks pytest -q
uv run --project scripts/config-guard config-guard .
pre-commit run --all-files
```

Expected: すべて緑。件数を控えて、緑ではなく件数で確認する

- [ ] **Step 3: push して PR を作る**

`dev-workflow:pre-merge-quality-gate` を通してから `gh pr create` する。PR 本文は
`.cache/pr-issue59.md` へ Write で書き `--body-file` で渡す。

```bash
git push -u origin feat/detect-silent-guards
```

- [ ] **Step 4: 実セッションでの発火を確認する**

ユーザーが Claude Code を再起動したあと、新しいセッションの頭で systemMessage が
実際に表示されるかを確認する。再起動は PATH の snapshot を更新するためにも必要なので、
この確認と目的が重なる。

再起動後は apm プローブが健全になるはずなので、**沈黙の報告が出ないこと**が期待値になる。
沈黙を実際に表示させたい場合は、`~/.local/libexec/apm-guard/apm` を一時的に退避してから
新しいセッションを開き、確認後に戻す。

この確認だけはユーザーの操作が要る。エージェントは代行できない。
