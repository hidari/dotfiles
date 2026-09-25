# tgrep serve の寿命をセッションへ合わせる実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude Code のセッションが始まるときに tgrep serve を立て、最後のセッションが終わるときに止め、serve が無いときは検索が黙って古い答えを返さないようにする。

**Architecture:** hook 1 本 (`tgrep-serve.py`) が引数で契機を分ける。状態は `~/.cache/claude/tgrep-serve/` に root ごとの JSON で持ち、鍵は PID。判定ロジックは 1 つ (使っているセッションが他にいなければ止める) で、契機が SessionStart と SessionEnd の 2 つ。不在時の手当ては `.zshrc` のシェル関数ラッパーが持つ。

**Tech Stack:** Python 3 (標準ライブラリのみ)、zsh 関数、pytest、bats、tgrep 1.0.8

**Spec:** `docs/issues/ISSUE-102_tgrep serve の起動と停止をセッションの寿命へ合わせ、不在時の規範を決める/ISSUE-102-spec.md`

## Global Constraints

- hook 本体は `home/.claude/hooks/<kebab-case>.py`、mode 755、shebang `#!/usr/bin/env python3` 必須
- 共有モジュールは `home/.claude/hooks/<snake_case>.py`、mode 644、shebang 無し、`print` と `sys.exit` を持たない
- hook 本体は常に exit 0 に倒す。例外は `if __name__` ブロックの包括 except で握る
- JSON 出力は `ensure_ascii=False`
- `settings.json` に絶対パスを書かない。`$HOME` 形式を使う (`settings_invariants` が `/(Users|home)/[a-z_][a-z0-9._-]*` を弾く)
- mypy strict が通る型注釈を最初から付ける
- コード内コメントとシステム内部ログは日本語 (プロジェクトの CLAUDE.md)
- 日本語のテスト関数名を使うファイルは `scripts/claude-hooks/pyproject.toml` の `[tool.ruff.lint.per-file-ignores]` へ 1 行足す
- `.zshrc` の関数は bats が bash で source するので zsh 固有の modifier (`${dir:t}` 等) を使わない
- 定数の値 (資源上限・ハッシュ桁数) の canonical は実装に置く。この plan の値は実装時点のもの

---

## File Structure

| ファイル | 責務 |
| --- | --- |
| `home/.claude/hooks/tgrep_serve_state.py` | 参照カウントの読み書きと PID の生存判定。副作用は状態ファイルのみ |
| `home/.claude/hooks/tgrep-serve.py` | hook 本体。契機の分岐、serve の起動と停止、孤児の回収 |
| `home/.claude/settings.json` | SessionStart と SessionEnd への配線 |
| `home/.zshrc` | `tgrep` のラッパー関数 |
| `scripts/claude-hooks/tests/test_tgrep_serve.py` | 上 2 つの Python の仕様 |
| `scripts/tests/zshrc-tgrep.bats` | ラッパー関数の仕様 |
| `home/.claude/references/observation.md` | tgrep 節の一次実測 |

---

### Task 1: 参照カウントの状態モジュール

**Files:**
- Create: `home/.claude/hooks/tgrep_serve_state.py` (mode 644、shebang 無し)
- Create: `scripts/claude-hooks/tests/test_tgrep_serve.py`
- Modify: `scripts/claude-hooks/pyproject.toml` (per-file-ignores へ 1 行)

**Interfaces:**
- Consumes: なし
- Produces: `cache_root() -> Path` / `state_dir() -> Path` / `state_file(root: Path) -> Path` / `is_alive(pid: int) -> bool` / `live_pids(root: Path) -> list[int]` / `register(root: Path, pid: int) -> list[int]` / `unregister(root: Path, pid: int) -> list[int]` / `known_roots() -> list[Path]`

- [ ] **Step 1: 失敗するテストを書く**

`scripts/claude-hooks/tests/test_tgrep_serve.py` を作る。

```python
"""tgrep serve の寿命をセッションへ合わせる hook の仕様。

判定ロジックは in-process で呼び、起動形だけ最後に 1 件 subprocess で見る
(test_guard_health.py と同じ形)。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
import tgrep_serve_state as state


@pytest.fixture
def state_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """状態ファイルの置き場を使い捨てディレクトリへ向ける。"""
    target = tmp_path / "state"
    monkeypatch.setenv("TGREP_SERVE_STATE_DIR", str(target))
    return target


def test_状態ファイル名は_charset_を潰すと衝突する_2_つの_root_で別になる(state_dir: Path) -> None:
    # sanitize (非英数を _ へ潰す) を使うとこの 2 つは同じ名前へ落ちる
    a = state.state_file(Path("/tmp/a/b"))
    b = state.state_file(Path("/tmp/a_b"))
    assert a != b


def test_register_した_pid_が_live_pids_に現れる(state_dir: Path) -> None:
    root = Path("/tmp/repo-one")
    assert state.register(root, os.getpid()) == [os.getpid()]
    assert state.live_pids(root) == [os.getpid()]


def test_死んでいる_pid_は数えない(state_dir: Path) -> None:
    root = Path("/tmp/repo-two")
    state.register(root, os.getpid())
    # 実在しない PID を直接書き込む。記録はスナップショットなので信じて数えない
    path = state.state_file(root)
    path.write_text(
        json.dumps({"root": str(root), "pids": [os.getpid(), 2**22 - 1]}) + "\n",
        encoding="utf-8",
    )
    assert state.live_pids(root) == [os.getpid()]


def test_unregister_で_0_件になると状態ファイルごと消える(state_dir: Path) -> None:
    root = Path("/tmp/repo-three")
    state.register(root, os.getpid())
    assert state.unregister(root, os.getpid()) == []
    assert not state.state_file(root).exists()


def test_unregister_は他の生存_pid_を残す(state_dir: Path) -> None:
    root = Path("/tmp/repo-four")
    state.register(root, os.getpid())
    state.register(root, os.getppid())
    remaining = state.unregister(root, os.getpid())
    assert remaining == [os.getppid()]
    assert state.state_file(root).exists()


def test_known_roots_は記録された_root_を返す(state_dir: Path) -> None:
    state.register(Path("/tmp/repo-five"), os.getpid())
    state.register(Path("/tmp/repo-six"), os.getpid())
    assert sorted(state.known_roots()) == [Path("/tmp/repo-five"), Path("/tmp/repo-six")]


def test_壊れた状態ファイルは空として扱う(state_dir: Path) -> None:
    root = Path("/tmp/repo-seven")
    path = state.state_file(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{ not json", encoding="utf-8")
    assert state.live_pids(root) == []


def test_cache_root_は_XDG_CACHE_HOME_に従う(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg"))
    assert state.cache_root() == tmp_path / "xdg" / "claude"
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run --directory scripts/claude-hooks pytest tests/test_tgrep_serve.py -q`
Expected: `ModuleNotFoundError: No module named 'tgrep_serve_state'` で collection error。

- [ ] **Step 3: per-file-ignores へ 1 行足す**

`scripts/claude-hooks/pyproject.toml` の `[tool.ruff.lint.per-file-ignores]` へ次を足す。日本語のテスト関数名は N802 に当たる。

```toml
"tests/test_tgrep_serve.py" = ["N802"]
```

- [ ] **Step 4: 状態モジュールを書く**

`home/.claude/hooks/tgrep_serve_state.py` を作る。

```python
"""tgrep serve を使っているセッションを数えるための状態。

serve はディレクトリ単位で常駐し、停止手段はシグナルだけなので、誰が使っているかを
外から数える層が要る。Claude Code が書く sessions/<pid>.json は headless のセッションを
登録しないため、それを数えると走っている headless の足元で serve を止める。ここは自前で持つ。

print と sys.exit は持たない。副作用を持ち込むとこの層だけを直接テストできなくなる
(hook_git.py / guard_probes.py と同じ規則)。
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

# 状態ファイル名に使うハッシュの桁数。衝突を避けるのが目的なので短くしない。
DIGEST_CHARS = 16


def cache_root() -> Path:
    """このフックが使うキャッシュの根。handoff-sentinel の _cache_root と同じ規則。

    規則を 1 つに閉じないと、XDG_CACHE_HOME を設定したマシンで別の根へ落ちる。
    """
    cache_home = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache_home) / "claude"


def state_dir() -> Path:
    override = os.environ.get("TGREP_SERVE_STATE_DIR", "")
    if override:
        return Path(override)
    return cache_root() / "tgrep-serve"


def state_file(root: Path) -> Path:
    """root ごとの状態ファイル。名前はパスのハッシュにする。

    handoff-sentinel の _sanitize (非英数を _ へ潰す) は使わない。あちらの入力は
    session_id (UUID) なので衝突しないが、パスへ適用すると /a/b と /a_b が同じ名前へ落ちる。
    charset を通っていても警告は出ないので、2 つのリポジトリが同じ参照カウントを共有し、
    片方の SessionEnd がもう片方の serve を止めるまで気づけない。
    """
    digest = hashlib.sha256(str(root).encode("utf-8")).hexdigest()[:DIGEST_CHARS]
    return state_dir() / f"{digest}.json"


def is_alive(pid: int) -> bool:
    """PID が生きているか。プロセス起動を挟まない。

    PermissionError は「存在するが他ユーザーのもの」なので生存として扱う。PID の再利用で
    死んだ PID を生存と誤ることはありうるが、その向きの誤りは「止めない」側に落ちる。
    使用中のセッションの足元を払う向きより害が小さいので、再利用の検出は持たない。
    """
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _read(path: Path) -> dict[str, Any]:
    """状態ファイルを読む。壊れていれば空として扱う。"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write(path: Path, root: Path, pids: list[int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"root": str(root), "pids": sorted(set(pids))}
    path.write_text(json.dumps(payload, ensure_ascii=False) + "\n", encoding="utf-8")


def live_pids(root: Path) -> list[int]:
    """記録された PID のうち実際に生きているものだけを返す。

    記録は書いた時点のスナップショットなので、そのまま数えない。
    """
    recorded = _read(state_file(root)).get("pids")
    if not isinstance(recorded, list):
        return []
    return [p for p in recorded if isinstance(p, int) and is_alive(p)]


def register(root: Path, pid: int) -> list[int]:
    """pid を登録し、登録後の生存 PID を返す。"""
    pids = live_pids(root)
    if pid not in pids:
        pids.append(pid)
    _write(state_file(root), root, pids)
    return sorted(set(pids))


def unregister(root: Path, pid: int) -> list[int]:
    """pid を外し、残った生存 PID を返す。0 件なら状態ファイルごと消す。"""
    pids = [p for p in live_pids(root) if p != pid]
    path = state_file(root)
    if pids:
        _write(path, root, pids)
    else:
        path.unlink(missing_ok=True)
    return sorted(set(pids))


def known_roots() -> list[Path]:
    """状態ファイルが記録している root の一覧。孤児の回収に使う。

    ファイル名はハッシュなので名前から root は導けない。中身の root を読む。
    """
    try:
        entries = sorted(state_dir().glob("*.json"))
    except OSError:
        return []
    roots: list[Path] = []
    for entry in entries:
        recorded = _read(entry).get("root")
        if isinstance(recorded, str) and recorded:
            roots.append(Path(recorded))
    return roots
```

- [ ] **Step 5: テストが通ることを確かめる**

Run: `uv run --directory scripts/claude-hooks pytest tests/test_tgrep_serve.py -q -rf`
Expected: 8 passed。

- [ ] **Step 6: 変異注入で pin を確かめる**

`state_file` のハッシュを sanitize 相当へ一時的に変える。

```python
    # 変異: digest の代わりに非英数を潰した名前を使う
    import re
    return state_dir() / (re.sub(r"[^A-Za-z0-9_-]", "_", str(root)) + ".json")
```

Run: `uv run --directory scripts/claude-hooks pytest tests/test_tgrep_serve.py -q -rf`
Expected: `test_状態ファイル名は_charset_を潰すと衝突する_2_つの_root_で別になる` が FAIL。
変異を戻す (`git checkout` は使わない。未コミットの編集ごと失うため、手で戻す)。

- [ ] **Step 7: 型と lint を通す**

Run: `uv run --directory scripts/claude-hooks mypy . && uv run --directory scripts/claude-hooks ruff check . && uv run --directory scripts/claude-hooks ruff format --check .`
Expected: いずれも rc 0。

- [ ] **Step 8: コミット**

本文は日本語なので Write でファイルへ書いて `-F` で渡す (Bash コマンド文字列に日本語を載せると Tirith の confusable_text に当たる)。

```bash
git add home/.claude/hooks/tgrep_serve_state.py scripts/claude-hooks/tests/test_tgrep_serve.py scripts/claude-hooks/pyproject.toml
git commit -F .cache/commit-task1.txt
```

---

### Task 2: hook 本体の起動側

**Files:**
- Create: `home/.claude/hooks/tgrep-serve.py` (mode 755、shebang あり)
- Modify: `scripts/claude-hooks/tests/test_tgrep_serve.py`

**Interfaces:**
- Consumes: Task 1 の `tgrep_serve_state` 全関数、既存の `hook_git.rev_parse(cwd, *args) -> str | None`
- Produces: `tgrep_bin() -> str` / `serve_argv(root: Path) -> list[str]` / `serve_pid(root: Path) -> int | None` / `start_serve(root: Path) -> bool` / `resolve_root(payload: dict) -> Path | None` / `session_pid(argv: list[str]) -> int` / `handle_start(payload: dict, pid: int) -> None`

- [ ] **Step 1: 失敗するテストを書く**

`scripts/claude-hooks/tests/test_tgrep_serve.py` へ足す。冒頭の import に次を加える。

```python
import importlib.util
import subprocess
from types import ModuleType

from conftest import HOOKS_DIR, make_git_repo

HOOK = HOOKS_DIR / "tgrep-serve.py"


def _load_hook() -> ModuleType:
    """ハイフンを含むファイル名のフックをモジュールとして読む。"""
    spec = importlib.util.spec_from_file_location("tgrep_serve", HOOK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

テスト本体。

```python
def test_起動コマンドに_ignore_無視のフラグを渡さない() -> None:
    hook = _load_hook()
    argv = hook.serve_argv(Path("/tmp/repo"))
    # 「含まれない」ことが安全側の決定なので、部分一致ではなく集合として見る。
    # 部分一致だと変異でフラグを足しても赤くならない
    assert "--no-ignore" not in argv
    assert "--no-ignore-parent" not in argv
    assert "--no-ignore-vcs" not in argv
    assert "--hidden" not in argv


def test_起動コマンドに資源上限が渡る() -> None:
    hook = _load_hook()
    argv = hook.serve_argv(Path("/tmp/repo"))
    assert "--max-memory" in argv
    assert "--max-cpu" in argv
    assert argv[:3] == [hook.tgrep_bin(), "serve", "/tmp/repo"]


def test_serve_pid_は生きていない_pid_を_None_に落とす(tmp_path: Path) -> None:
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    (idx / "serve.json").write_text(json.dumps({"pid": 2**22 - 1, "port": 1}), encoding="utf-8")
    assert hook.serve_pid(tmp_path) is None


def test_serve_pid_は生きている_pid_を返す(tmp_path: Path) -> None:
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    (idx / "serve.json").write_text(
        json.dumps({"pid": os.getpid(), "port": 1}), encoding="utf-8"
    )
    assert hook.serve_pid(tmp_path) == os.getpid()


def test_serve_が動いていれば起動しない(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    (idx / "serve.json").write_text(
        json.dumps({"pid": os.getpid(), "port": 1}), encoding="utf-8"
    )
    launched: list[list[str]] = []
    monkeypatch.setattr(hook.subprocess, "Popen", lambda cmd, **kw: launched.append(cmd))
    assert hook.start_serve(tmp_path) is False
    assert launched == []


def test_起動は待たずに独立セッションで行う(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_hook()
    captured: dict[str, object] = {}

    def fake_popen(cmd: list[str], **kwargs: object) -> None:
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs

    monkeypatch.setattr(hook.subprocess, "Popen", fake_popen)
    assert hook.start_serve(tmp_path) is True
    kwargs = captured["kwargs"]
    assert isinstance(kwargs, dict)
    # detach の 3 点。1 つでも欠けるとセッション起動がブロックされるか出力が汚れる
    assert kwargs["start_new_session"] is True
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["stdout"] == subprocess.DEVNULL
    assert kwargs["stderr"] == subprocess.DEVNULL


def test_git_管理外では_root_を返さない(tmp_path: Path) -> None:
    hook = _load_hook()
    assert hook.resolve_root({"cwd": str(tmp_path)}) is None


def test_git_リポジトリなら_root_を返す(tmp_path: Path) -> None:
    hook = _load_hook()
    repo = make_git_repo(tmp_path / "repo")
    resolved = hook.resolve_root({"cwd": str(repo)})
    assert resolved is not None
    assert resolved.resolve() == repo.resolve()


def test_session_pid_は引数を優先し展開されなければ親へ落とす() -> None:
    hook = _load_hook()
    assert hook.session_pid(["tgrep-serve.py", "start", "4242"]) == 4242
    # シェルを経由せず $PPID が展開されなかった場合
    assert hook.session_pid(["tgrep-serve.py", "start", "$PPID"]) == os.getppid()
    assert hook.session_pid(["tgrep-serve.py", "start"]) == os.getppid()
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run --directory scripts/claude-hooks pytest tests/test_tgrep_serve.py -q -rf`
Expected: `_load_hook` が `FileNotFoundError` で落ちる。

- [ ] **Step 3: hook 本体を書く (起動側だけ)**

`home/.claude/hooks/tgrep-serve.py` を作る。

```python
#!/usr/bin/env python3
"""tgrep serve の寿命を Claude Code のセッションへ合わせる。

serve が無いと既定の検索は索引を直読みし、最後に保存された後の変更を持たない答えを
警告なしに返す。この経路は --stats が経路の語を出さないので最も気づきにくい。
serve をセッションの寿命に合わせて立てることで、この経路へ落ちる機会を減らす。

契機は引数で分ける (handoff-sentinel.py と同じ形)。判定のロジックは 1 つで、
「この root を使っているセッションが他にいなければ止める」を SessionEnd と
SessionStart の両方から呼ぶ。SIGKILL では SessionEnd が発火しないため、停止を
SessionEnd だけに賭けられない。

出力は持たない。SessionStart で文脈へ告げる形は ISSUE-83 と ISSUE-71 の決着に
先行されるので、この hook は副作用だけを持つ。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import hook_git
import tgrep_serve_state as state

# 初回索引構築の資源上限。既定は物理 RAM と論理コアの 50% で、ホスト環境を守る規範に対して
# 緩い。このリポジトリ (310 files) の実測では peak 36.9 MiB だったので 1 GB で足りる。
MAX_MEMORY_MB = "1024"
MAX_CPU_PERCENT = "25"


def tgrep_bin() -> str:
    """tgrep の実体。テストは偽バイナリを環境変数で差し込む。"""
    return os.environ.get("TGREP_BIN") or "tgrep"


def serve_argv(root: Path) -> list[str]:
    """serve の起動コマンド。

    ignore を無視するフラグは渡さない。渡すと .gitignore 配下 (.env 等) が索引に入り、
    認証の無い TCP の search から行の内容として読める。渡さないことが既定の状態なので、
    テストは argv 全体を見て「含まれない」ことを明示的に検査する。
    """
    return [
        tgrep_bin(),
        "serve",
        str(root),
        "--max-memory",
        MAX_MEMORY_MB,
        "--max-cpu",
        MAX_CPU_PERCENT,
    ]


def serve_pid(root: Path) -> int | None:
    """索引ディレクトリの serve.json が指す PID。生きていなければ None。

    SIGTERM / SIGKILL で止まった serve は serve.json を古いまま残すので、
    ファイルの存在だけでは判定できない。
    """
    try:
        data = json.loads((root / ".tgrep" / "serve.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    pid = data.get("pid")
    if not isinstance(pid, int) or not state.is_alive(pid):
        return None
    return pid


def start_serve(root: Path) -> bool:
    """serve を detach で起動する。起動したら True、既に動いていれば False。

    SessionStart の既定 timeout は 600 秒あり、同期で待つとセッション起動がそのまま止まる
    (78 秒ブロックさせると claude の wall が 79 秒になることを実測した)。
    stdio を継承させると hook の JSON 出力が汚れる (tirith-check.py と同じ 3 点)。
    """
    if serve_pid(root) is not None:
        return False
    try:
        subprocess.Popen(
            serve_argv(root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError:
        return False
    return True


def resolve_root(payload: dict[str, Any]) -> Path | None:
    """payload の cwd から git リポジトリの root を解決する。管理外なら None。

    hook_git.repo_root は管理外を cwd に落とすので使わない。ここでは「git 管理下か」の
    区別が要る。
    """
    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return None
    top = hook_git.rev_parse(cwd, "--show-toplevel")
    return Path(top) if top else None


def session_pid(argv: list[str]) -> int:
    """セッションの寿命を代表する PID。

    settings.json の command が $PPID を渡す。hook を起動したシェルの親、つまり claude 本体に
    あたる。シェルを経由せず展開されなかった場合は自分の親へ落とす。
    """
    if len(argv) > 2:
        try:
            return int(argv[2])
        except ValueError:
            pass
    return os.getppid()


def handle_start(payload: dict[str, Any], pid: int) -> None:
    root = resolve_root(payload)
    if root is None:
        return
    state.register(root, pid)
    start_serve(root)


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        if action != "start":
            return 0
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            return 0
        handle_start(payload, session_pid(sys.argv))
    except Exception:
        # fail-safe: 検索の速さのための機構なので、故障で作業を止めない
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: 実行権限を付ける**

```bash
chmod 755 home/.claude/hooks/tgrep-serve.py
chmod 644 home/.claude/hooks/tgrep_serve_state.py
```

`config-guard` の `check_hook_mode_shebang` は「mode 755 なら shebang 必須、shebang 無しなら mode 644 必須」を検査する。

- [ ] **Step 5: テストが通ることを確かめる**

Run: `uv run --directory scripts/claude-hooks pytest tests/test_tgrep_serve.py -q -rf`
Expected: 17 passed。

- [ ] **Step 6: 変異注入 (最も生存しやすい 1 件)**

`serve_argv` の戻り値へ `"--no-ignore"` を足す。

Run: `uv run --directory scripts/claude-hooks pytest tests/test_tgrep_serve.py -q -rf`
Expected: `test_起動コマンドに_ignore_無視のフラグを渡さない` が FAIL。緑のままならテストが
部分一致で見ている。集合として見る形へ直す。変異を手で戻す。

続けて `start_new_session=True` を落とす変異を入れ、`test_起動は待たずに独立セッションで行う`
が FAIL することを見る。戻す。

- [ ] **Step 7: 型と lint を通してコミット**

Run: `uv run --directory scripts/claude-hooks mypy . && uv run --directory scripts/claude-hooks ruff check . && uv run --directory scripts/claude-hooks ruff format --check .`

```bash
git add home/.claude/hooks/tgrep-serve.py scripts/claude-hooks/tests/test_tgrep_serve.py
git commit -F .cache/commit-task2.txt
```

---

### Task 3: hook 本体の停止側と孤児の回収

**Files:**
- Modify: `home/.claude/hooks/tgrep-serve.py`
- Modify: `scripts/claude-hooks/tests/test_tgrep_serve.py`

**Interfaces:**
- Consumes: Task 2 の `serve_pid` / `resolve_root` / `session_pid`
- Produces: `stop_serve(root: Path) -> bool` / `stop_if_unused(root: Path) -> bool` / `reap() -> list[Path]` / `handle_end(payload: dict, pid: int) -> None`

- [ ] **Step 1: 失敗するテストを書く**

```python
def test_停止は_SIGINT_を送る(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    hook = _load_hook()
    idx = tmp_path / ".tgrep"
    idx.mkdir()
    (idx / "serve.json").write_text(
        json.dumps({"pid": os.getpid(), "port": 1}), encoding="utf-8"
    )
    sent: list[tuple[int, int]] = []
    monkeypatch.setattr(hook.os, "kill", lambda pid, sig: sent.append((pid, sig)))
    assert hook.stop_serve(tmp_path) is True
    # SIGTERM は graceful handler を通らず serve.json を古いまま残す (実測)
    assert sent == [(os.getpid(), hook.signal.SIGINT)]


def test_生存セッションが残っていれば止めない(
    tmp_path: Path, state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    # git リポジトリにしないと resolve_root が手前で None を返し、狙った分岐へ届かない。
    # register する root も resolve_root が返すものに揃える (tmp_path と --show-toplevel は
    # symlink の解決で食い違いうる)
    repo = make_git_repo(tmp_path / "repo")
    root = hook.resolve_root({"cwd": str(repo)})
    assert root is not None
    state.register(root, os.getpid())
    state.register(root, os.getppid())
    stopped: list[Path] = []
    monkeypatch.setattr(hook, "stop_serve", lambda r: stopped.append(r) or True)
    hook.handle_end({"cwd": str(repo)}, os.getpid())
    assert stopped == []
    # 手前の検査を通過していることの対照。ここが空だと上の空も意味を持たない
    assert state.live_pids(root) == sorted({os.getppid()})


def test_最後の_1_人が抜けたら止める(
    tmp_path: Path, state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    repo = make_git_repo(tmp_path / "repo")
    root = hook.resolve_root({"cwd": str(repo)})
    assert root is not None
    state.register(root, os.getpid())
    stopped: list[Path] = []
    monkeypatch.setattr(hook, "stop_serve", lambda r: stopped.append(r) or True)
    hook.handle_end({"cwd": str(repo)}, os.getpid())
    assert stopped == [root]
    assert not state.state_file(root).exists()


def test_回収は生存_0_の_root_だけを止める(
    tmp_path: Path, state_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    hook = _load_hook()
    alive = tmp_path / "alive"
    dead = tmp_path / "dead"
    state.register(alive, os.getpid())
    # 実在しない PID だけが記録された root
    dead_file = state.state_file(dead)
    dead_file.parent.mkdir(parents=True, exist_ok=True)
    dead_file.write_text(
        json.dumps({"root": str(dead), "pids": [2**22 - 1]}) + "\n", encoding="utf-8"
    )
    stopped: list[Path] = []
    monkeypatch.setattr(hook, "stop_serve", lambda r: stopped.append(r) or True)
    assert hook.reap() == [dead]
    assert stopped == [dead]
    assert not dead_file.exists()
    assert state.state_file(alive).exists()
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `uv run --directory scripts/claude-hooks pytest tests/test_tgrep_serve.py -q -rf`
Expected: `AttributeError: module 'tgrep_serve' has no attribute 'stop_serve'`。

- [ ] **Step 3: 停止側を書く**

`home/.claude/hooks/tgrep-serve.py` の import に `import signal` を足し、次を加える。

```python
def stop_serve(root: Path) -> bool:
    """serve へ SIGINT を送る。送ったら True。

    SIGINT だけが graceful な経路で、shutting down を出して serve.json を消す。
    SIGTERM は graceful handler を通らず SIGKILL と同じ残り方をする (実測)。
    """
    pid = serve_pid(root)
    if pid is None:
        return False
    try:
        os.kill(pid, signal.SIGINT)
    except OSError:
        return False
    return True


def stop_if_unused(root: Path) -> bool:
    """この root を使っているセッションが無ければ serve を止め、状態ファイルを消す。

    止め損ねる害 (常駐 20 MB と認証の無い TCP) と、止めすぎる害 (使用中のセッションが
    索引直読みへ黙って落ちる) は釣り合わない。生存が確実に 0 のときだけ止める。
    """
    if state.live_pids(root):
        return False
    stop_serve(root)
    state.state_file(root).unlink(missing_ok=True)
    return True


def reap() -> list[Path]:
    """生存セッションが 0 の root をすべて止める。止めた root を返す。

    SIGKILL では SessionEnd が発火せず、hook が起こした子も孤児として残る (実測)。
    停止を SessionEnd だけに賭けられないので、SessionStart でも回収する。
    """
    return [root for root in state.known_roots() if stop_if_unused(root)]


def handle_end(payload: dict[str, Any], pid: int) -> None:
    root = resolve_root(payload)
    if root is None:
        return
    if not state.unregister(root, pid):
        stop_if_unused(root)
```

`handle_start` の先頭へ回収を足す。

```python
def handle_start(payload: dict[str, Any], pid: int) -> None:
    # 回収を先に行う。自分が使う root は登録前なので、この時点の生存 0 判定に自分は入らない。
    # 順序を逆にすると、自分が登録した直後に自分を数えて回収が空振りする
    reap()
    root = resolve_root(payload)
    if root is None:
        return
    state.register(root, pid)
    start_serve(root)
```

`main` の分岐を広げる。

```python
    HANDLERS = {"start": handle_start, "end": handle_end}
    handler = HANDLERS.get(action)
    if handler is None:
        return 0
    payload = json.loads(sys.stdin.read())
    if not isinstance(payload, dict):
        return 0
    handler(payload, session_pid(sys.argv))
```

- [ ] **Step 4: テストが通ることを確かめる**

Run: `uv run --directory scripts/claude-hooks pytest tests/test_tgrep_serve.py -q -rf`
Expected: 21 passed。

- [ ] **Step 5: 変異注入**

`stop_serve` の `signal.SIGINT` を `signal.SIGTERM` へ変える。
Expected: `test_停止は_SIGINT_を送る` が FAIL。戻す。

`stop_if_unused` の `if state.live_pids(root):` を `if False:` へ変える。
Expected: `test_生存セッションが残っていれば止めない` が FAIL。戻す。

- [ ] **Step 6: 起動形を subprocess で 1 件だけ pin する**

```python
def test_フックは_stdin_を読んで_exit_0_で終わる(tmp_path: Path) -> None:
    env = dict(os.environ)
    env["TGREP_SERVE_STATE_DIR"] = str(tmp_path / "state")
    env["TGREP_BIN"] = "/usr/bin/false"
    payload = json.dumps({"hook_event_name": "SessionStart", "cwd": str(tmp_path)})
    result = subprocess.run(
        [sys.executable, str(HOOK), "start", str(os.getpid())],
        input=payload,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout == ""
```

冒頭の import に `import sys` を足す。

- [ ] **Step 7: 型と lint を通してコミット**

---

### Task 4: settings.json への配線と headless での確認

**Files:**
- Modify: `home/.claude/settings.json:69-109` (SessionStart) と新設の SessionEnd

**Interfaces:**
- Consumes: Task 3 までの hook 本体
- Produces: なし (配線のみ)

このリポジトリの working tree は live な `~/.claude` の実体なので、配線した瞬間に現行マシンで
発火する。配線は最後に回し、headless の別プロセスで確かめてから入れる。

- [ ] **Step 1: 配線前に headless で確かめる**

使い捨ての設定ディレクトリを作り、そこへだけ配線して発火を見る。

```bash
mkdir -p .cache/tgrep-hook-verify/cfg .cache/tgrep-hook-verify/work
cd .cache/tgrep-hook-verify/work && git init -q && cd -
```

`.cache/tgrep-hook-verify/cfg/settings.json` を Write で作る。

```json
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/Develop/dotfiles/home/.claude/hooks/tgrep-serve.py\" start $PPID",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Run:
```bash
cd .cache/tgrep-hook-verify/work
TGREP_SERVE_STATE_DIR=$PWD/../state CLAUDE_CONFIG_DIR=$PWD/../cfg claude -p 'ok' > /dev/null
cat ../state/*.json
```

Expected: 状態ファイルが 1 件でき、`pids` に載った PID が `ps -p <pid>` で claude 本体として
見えること。`$PPID` がリテラルのまま渡っていれば `session_pid` のフォールバックが効くが、
その場合は claude ではなく hook のシェルが記録される。どちらが記録されたかを ps で確かめ、
claude でなければ settings.json の command の形を見直す。

- [ ] **Step 2: 使い捨てを片付ける**

```bash
rm -rf .cache/tgrep-hook-verify
```

- [ ] **Step 3: 本体へ配線する**

`home/.claude/settings.json` の `SessionStart` 配列の末尾へ足す。

```json
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/hooks/tgrep-serve.py\" start $PPID",
            "timeout": 10
          }
        ]
      }
```

`PostToolUse` の手前へ `SessionEnd` をキーごと新設する。`timeout` は必ず書く。SessionEnd の
既定は 1.5 秒で、兄弟 hook に長い timeout を書いても自分は延長されない (実測)。

```json
    "SessionEnd": [
      {
        "matcher": "*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/hooks/tgrep-serve.py\" end $PPID",
            "timeout": 10
          }
        ]
      }
    ],
```

- [ ] **Step 4: 配線の検査が効くことを変異で確かめる**

Run: `uv run --project scripts/config-guard config-guard .`
Expected: rc 0。

配線を外す変異: `settings.json` から `tgrep-serve.py` を含む 2 つのブロックを一時的に消す。
Run: `uv run --project scripts/config-guard config-guard .`
Expected: `hook_wiring` が `tgrep-serve.py` を未配線として報告する。戻す。

- [ ] **Step 5: 全スイートを回してコミット**

Run:
```bash
uv run --directory scripts/claude-hooks pytest -q -rf
uv run --directory scripts/config-guard pytest -q -rf
uv run --project scripts/config-guard config-guard .
```
Expected: claude-hooks は 264 + 22 = 286 passed、config-guard は 428 passed、scan は rc 0。

---

### Task 5: tgrep のラッパー関数

**Files:**
- Modify: `home/.zshrc` (Claude Code 起動関数の節の手前)
- Create: `scripts/tests/zshrc-tgrep.bats`

**Interfaces:**
- Consumes: なし
- Produces: シェル関数 `tgrep`

- [ ] **Step 1: 失敗するテストを書く**

`scripts/tests/zshrc-tgrep.bats` を作る。既存の `zshrc-claude.bats` と同じく `test_helper` を
load し、`setup_test_home` を使う。関数名は ASCII で書く (`ast-grep` の
`bats-test-name-ascii-only` ルールが日本語のテスト名を弾く)。

```bash
#!/usr/bin/env bats
# =============================================================================
# .zshrc の tgrep ラッパーのテスト
# =============================================================================
#
# ラッパーが守る仕様は以下の通り。
#   1. サブコマンド (serve/index/status/count-files/help) は素通しする。
#      ここに索引回避のフラグを足すと serve 自身が壊れる
#   2. 検索のとき、serve が生きていなければ --no-index を足して stderr に 1 行告げる
#   3. serve が生きていれば素通しする
#   4. 判定はプロセス起動を挟まない (serve.json と PID の生死だけを見る)

load test_helper

bats_require_minimum_version 1.5.0

setup() {
    setup_test_home
    FAKE_BIN="$TEST_HOME/bin"
    mkdir -p "$FAKE_BIN"
    # 渡された引数をそのまま記録する偽 tgrep
    cat > "$FAKE_BIN/tgrep" <<'EOF'
#!/bin/sh
printf '%s\n' "$@" > "$TGREP_ARGS_FILE"
exit 0
EOF
    chmod 755 "$FAKE_BIN/tgrep"
    PATH="$FAKE_BIN:$PATH"
    export TGREP_ARGS_FILE="$TEST_HOME/args.txt"
    REPO="$TEST_HOME/repo"
    mkdir -p "$REPO/.tgrep"
}

teardown() {
    teardown_test_home
}

# serve.json を書く。第 2 引数が live なら自分の PID (必ず生きている) を使う。
write_serve_json() {
    local pid="$2"
    [ "$pid" = "live" ] && pid=$$
    printf '{"pid":%s,"port":1}' "$pid" > "$1/.tgrep/serve.json"
}

@test "tgrep: passes serve subcommand through untouched" {
    load_zshrc_tgrep_function
    cd "$REPO" || return 1
    run tgrep serve .
    [ "$status" -eq 0 ]
    run cat "$TGREP_ARGS_FILE"
    [ "${lines[0]}" = "serve" ]
    ! grep -q -- "--no-index" "$TGREP_ARGS_FILE"
}

@test "tgrep: passes status subcommand through untouched" {
    load_zshrc_tgrep_function
    cd "$REPO" || return 1
    run tgrep status .
    ! grep -q -- "--no-index" "$TGREP_ARGS_FILE"
}

@test "tgrep: adds --no-index when no server is running" {
    load_zshrc_tgrep_function
    cd "$REPO" || return 1
    run --separate-stderr tgrep PATTERN
    grep -q -- "--no-index" "$TGREP_ARGS_FILE"
    [ -n "$stderr" ]
}

@test "tgrep: adds --no-index when serve.json points at a dead pid" {
    load_zshrc_tgrep_function
    write_serve_json "$REPO" 4194303
    cd "$REPO" || return 1
    run tgrep PATTERN
    grep -q -- "--no-index" "$TGREP_ARGS_FILE"
}

@test "tgrep: leaves the search untouched when the server is alive" {
    load_zshrc_tgrep_function
    write_serve_json "$REPO" live
    cd "$REPO" || return 1
    run --separate-stderr tgrep PATTERN
    ! grep -q -- "--no-index" "$TGREP_ARGS_FILE"
    [ -z "$stderr" ]
}
```

`scripts/tests/test_helper.bash` の `load_zshrc_claude_functions` の隣へ足す。
`load_marker_block` は開始マーカーから `ZSHRC_SECTION_END`
(`^########################################$`) までを切り出して source し、マーカーが
見つからなければ非 0 を返す。

```bash
# .zshrc の tgrep ラッパーを読み込む。
load_zshrc_tgrep_function() {
    load_marker_block "$ZSHRC_FILE" '^# tgrep$' "$ZSHRC_SECTION_END"
}
```

開始マーカーが `^# tgrep$` なので、`.zshrc` 側は `########################################` の
次の行をちょうど `# tgrep` にする (Step 3 のコードはその形になっている)。
マーカーが消えたときに黙って 0 件を source しないことは、既存の
`load_zshrc_claude_functions: fails loudly when the marker is missing` と同じ形の
テストを 1 件足して pin する。

```bash
@test "load_zshrc_tgrep_function: fails loudly when the marker is missing" {
    ZSHRC_FILE="$TEST_HOME/empty.zshrc"
    printf '%s\n' '# unrelated' > "$ZSHRC_FILE"
    run load_zshrc_tgrep_function
    [ "$status" -ne 0 ]
}
```

- [ ] **Step 2: テストが失敗することを確かめる**

Run: `bats scripts/tests/zshrc-tgrep.bats`
Expected: `load_zshrc_tgrep_function: command not found` で全件 FAIL。

- [ ] **Step 3: ラッパーを書く**

`home/.zshrc` の `########################################` で始まる Claude Code 起動の節の
手前へ足す。bats が bash で source するので zsh 固有の modifier は使わない。

```bash
########################################
# tgrep

# 常駐サーバーが無いとき、既定の tgrep は索引を直読みして最後に保存された後の変更を
# 持たない答えを返す。--stats は経路の語を出さないので、この落ち方は出力に現れない。
# ラッパーで索引を使わない経路へ落とし、落ちたことを stderr に残す。
# サブコマンドは素通しする。serve に索引回避のフラグを渡すと serve 自身が壊れる。
function tgrep() {
  case "$1" in
    serve|index|status|count-files|help|--help|-h|--version|"")
      command tgrep "$@"
      return
      ;;
  esac
  local root serve_json pid
  root="$(git rev-parse --show-toplevel 2>/dev/null)" || root="$(pwd -P)"
  serve_json="$root/.tgrep/serve.json"
  pid=""
  if [ -f "$serve_json" ]; then
    # serve.json は SIGTERM / SIGKILL で止まると古い pid を残すので、生死まで見る。
    # プロセス起動を挟まないよう、kill -0 で確かめる
    pid="$(sed -n 's/.*"pid":[[:space:]]*\([0-9][0-9]*\).*/\1/p' "$serve_json")"
    if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
      command tgrep "$@"
      return
    fi
  fi
  echo "tgrep: 常駐サーバーが無いため索引を使わずに検索します ($root)" >&2
  command tgrep --no-index "$@"
}
```

- [ ] **Step 4: テストが通ることを確かめる**

Run: `bats scripts/tests/zshrc-tgrep.bats`
Expected: 6 tests, 0 failures。

- [ ] **Step 5: 変異注入**

`case` から `serve|index` を落とす。
Expected: `passes serve subcommand through untouched` が FAIL。戻す。

`kill -0 "$pid"` を `true` へ変える。
Expected: `adds --no-index when serve.json points at a dead pid` が FAIL。戻す。

- [ ] **Step 6: 全 bats と shellcheck を回してコミット**

Run: `bats scripts/tests/` と `shellcheck -x -P SCRIPTDIR scripts/tests/zshrc-tgrep.bats`
Expected: 既存 362 + 新規 6 が ok、shellcheck は rc 0。

---

### Task 6: references/observation.md の tgrep 節を書き直す

**Files:**
- Modify: `home/.claude/references/observation.md:192-283`

**Interfaces:**
- Consumes: なし
- Produces: なし

- [ ] **Step 1: 既存の実測を版を確かめて取り直す**

節の冒頭が「2026-09-13 に dotfiles の常駐サーバーに対して実測した」と書いている。
上流 main の README は `--hidden` の扱いが 1.0.8 と違うと読めるので、既存の表の値を
1.0.8 で取り直す。取り直した値が変わっていれば差し替え、変わっていなければ日付だけ足す。

Run (経路の申告を確かめる例):
```bash
tgrep --stats -c ALWAYS_LOADED_BUDGET_BYTES . 2>&1 | tail -3
tgrep --stats --no-index -c ALWAYS_LOADED_BUDGET_BYTES . 2>&1 | tail -3
```

- [ ] **Step 2: 経路の表へ第 3 経路を足す**

現在の表は `(via server)` と `Brute-force` の 2 行しか持たない。索引直読み (常駐が無く索引が
あるとき) は経路の語を出さないので、行を足して「申告が無いこと自体が経路の徴である」と書く。

- [ ] **Step 3: 構築中の罠を足す**

索引構築中の serve は `(via server)` を申告しながら空の索引から答える。経路の申告では
見分けられず、判定には `tgrep status` の `Indexing:` が要る。
この節の既存の規範 (経路は `--stats` で判定する) の射程がここまでであることを書く。

- [ ] **Step 4: `-r` と `-E` の罠を足す**

`-r` は `--replace` で、grep 流に渡すと一致部分が黙って置き換わる (再帰は既定の動作なので
フラグ自体が要らない)。`-E` は `--encoding` で、`-E 'a|b'` は `unsupported encoding` で rc 2 になる。
前者は黙って通り後者はうるさく失敗するので、害の大きさが違うことも書く。
ISSUE-100 が `-r` の canonical の置き場を未決で持ち、この節を候補に挙げているので、
置いたことを ISSUE-100 側へ書き戻す (Task 7)。

- [ ] **Step 5: ラッパーの射程を書く**

ラッパーが届くのはシェル経由の `tgrep` 呼び出しだけで、Claude Code の Grep ツールや
他の経路には届かない。「ラッパーが何も言わなかった = 索引が正しい」とは読めないことを書く。

- [ ] **Step 6: 常時層の予算が動いていないことを確かめてコミット**

Run: `uv run --project scripts/config-guard config-guard .`
Expected: 「常時 27651B / 予算 27753B」が変わらないこと (references は常時層に入らない)。

---

### Task 7: Issue の更新と最終ゲート

**Files:**
- Modify: `docs/issues/ISSUE-102_.../issue.md`
- Modify: `docs/issues/ISSUE-100_.../issue.md`

- [ ] **Step 1: ISSUE-102 のタスクを実態へ合わせる**

「worktree で隔離した subagent での挙動を測る」は spec が未確認として残しているので、
測ったならチェックし、測っていなければ残す。実装で埋まったタスクだけをチェックする。

- [ ] **Step 2: ISSUE-100 の未決を 1 つ減らす**

`-r` の canonical を `references/observation.md` の tgrep 節へ置いたことを ISSUE-100 の
「決めること」の該当項目へ書き戻す。

- [ ] **Step 3: 上流への報告の Issue を起票する**

`dev-workflow:in-repo-issue` skill で起票する。起票の前に既存 Issue を検索して同じ論点が
無いことを確かめる (Phase A.0)。内容は spec の「上流への報告」節が持つ。

- [ ] **Step 4: 全スイートを回す**

Run:
```bash
bats scripts/tests/
uv run --directory scripts/backup-tool pytest -q -rf
uv run --directory scripts/config-guard pytest -q -rf
uv run --directory scripts/claude-hooks pytest -q -rf
uv run --project scripts/config-guard config-guard .
ast-grep test --skip-snapshot-tests
ast-grep scan --no-ignore hidden
( cd home && apm audit --ci )
```
Expected: すべて緑。baseline は bats 362 / backup-tool 82 / config-guard 428 / claude-hooks 264。

- [ ] **Step 5: マージ前ゲートを通す**

`dev-workflow:pre-merge-quality-gate` を起動する。
