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
from typing import Any, TypeGuard

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


def is_pid(value: object) -> TypeGuard[int]:
    """シグナルを送ってよい PID の形か。正の int だけを通す。

    kill(2) にとって 0 は自分のプロセスグループ、-1 は送れる全プロセスを指すので、
    そのまま is_alive (kill -0) へ渡すと生存として通り、その先の SIGINT がユーザーの
    全プロセスへ届く。serve.json はリポジトリの中にあって clone がそのまま持ち込めるため、
    ps による同一性確認とは別の層としてここで落とす。bool は int のサブクラスなので
    明示的に外す (True は 1 = launchd に化ける)。
    """
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


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
    return [p for p in recorded if is_pid(p) and is_alive(p)]


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
