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
import signal
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


def handle_start(payload: dict[str, Any], pid: int) -> None:
    # 回収を先に行う。自分が使う root は登録前なので、この時点の生存 0 判定に自分は入らない。
    # 順序を逆にすると、自分が登録した直後に自分を数えて回収が空振りする
    reap()
    root = resolve_root(payload)
    if root is None:
        return
    state.register(root, pid)
    start_serve(root)


def handle_end(payload: dict[str, Any], pid: int) -> None:
    root = resolve_root(payload)
    if root is None:
        return
    if not state.unregister(root, pid):
        stop_if_unused(root)


# 契機 (action 引数) からハンドラへの分配。main() のローカル変数にすると ruff の N806
# (関数内ローカル変数は小文字) に触れるため、モジュール定数として持つ
HANDLERS = {"start": handle_start, "end": handle_end}


def main() -> int:
    action = sys.argv[1] if len(sys.argv) > 1 else ""
    try:
        handler = HANDLERS.get(action)
        if handler is None:
            return 0
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            return 0
        handler(payload, session_pid(sys.argv))
    except Exception:
        # fail-safe: 検索の速さのための機構なので、故障で作業を止めない
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
