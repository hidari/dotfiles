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
