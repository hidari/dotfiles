"""検査層が沈黙している状態を見る述語と、その登録簿。

PreToolUse の 2 つのガードは、どちらも自分が機能していない状態を検出できない。検出できて
いる箇所はあるが、射程が実態より狭い。この層はセッション頭で生存を測るためのものである。

述語をここへ集めるのは、同じ判定を 2 箇所へ書くと片方だけ直したときに沈黙して食い違う
ためである。それはこの層が扱っている欠陥そのものなので、canonical を 1 つにする。

print と sys.exit は持たない。副作用を持ち込むとこの層だけを直接テストできなくなる
(pretooluse.py と同じ規則)。subprocess は持つので純関数ではない。

shim / tirith バイナリの解決そのものは guard_resolve.py (leaf) が持つ。あちらは
PreToolUse (強制層) がホットパスで import するため軽量に保つ必要があり、こちらは
SessionStart (セッションに 1 回) からしか呼ばれないので subprocess / dataclasses を
import してよい。

フックからは sys.path[0] (スクリプトのディレクトリ) 経由で解決される。
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import Callable
from dataclasses import dataclass

import guard_resolve

# tirith の応答検査に流すコマンド。副作用が無く、検出されないことを実測で確かめたもの。
# 検出される文字列を選ぶと監査カウンタの blocked が呼び出しごとに 1 増え、tirith が
# 働いているかを判断する材料そのものを、この検査が壊す (実測)。
TIRITH_PROBE_COMMAND = "ls -la"

# 応答検査のタイムアウト (秒)。通常の応答は数十ミリ秒のオーダーだが、この値は
# 「応答しない」を判定するための上限であって通常経路の待ち時間ではない。
TIRITH_PROBE_TIMEOUT = 5.0


@dataclass(frozen=True)
class ProbeResult:
    """プローブ 1 件の結果。detail は沈黙しているときだけ意味を持つ。

    名前を持たないのは、登録簿が名前と関数の組で持つためである。プローブの呼び出し自体が
    例外で落ちたときにも名前が要るので、結果側ではなく登録簿側が名前を持つ。
    """

    healthy: bool
    detail: str = ""


def probe_apm() -> ProbeResult:
    """apm ガードの shim が実際に横取りする位置にあるか。

    フックが見る PATH を測っている。フックは Claude Code のプロセスから起動されるので、
    対話シェルの PATH に載っていても Claude Code の PATH に載っていなければ守っていない。
    Claude Code は起動時に PATH を snapshot するため、配置しただけでは反映されない。
    """
    if guard_resolve.shim_resolves():
        return ProbeResult(healthy=True)
    return ProbeResult(
        healthy=False,
        detail=(
            f"PATH 上の apm が {guard_resolve.shim_path()} へ解決されないため、apm ガードは"
            "横取りしていない。フックが自力で捕まえる形 (素の apm / 絶対パス / PATH の一時"
            "差し替え) は deny されるが、包み込みや変数間接や xargs の形は無音で素通りする。"
            "直すには bootstrap.sh を実行し、そのあと Claude Code を再起動する。"
            "PATH は起動時に snapshot されるので、シェルの再読み込みでは足りない。"
        ),
    )


def probe_tirith() -> ProbeResult:
    """tirith が解決し、clean なコマンドへ clean と応答するか。

    フックと同一のフラグと環境で呼ぶ (guard_resolve.tirith_child_env /
    tirith_check_argv)。呼び方が違うとデーモンを経由するかどうかが変わり、フックが通る
    経路とは別のものを測ることになる。

    「起動するが何も検出しない」状態はここでは覆わない。覆うには検出される文字列を流す
    陰性対照が要るが、それは監査カウンタの blocked を呼び出しごとに 1 増やし、tirith が
    働いているかを判断する材料そのものを壊す (実測)。
    """
    tirith_bin = guard_resolve.resolve_tirith_bin()

    try:
        result = subprocess.run(
            guard_resolve.tirith_check_argv(tirith_bin, TIRITH_PROBE_COMMAND),
            capture_output=True,
            text=True,
            timeout=TIRITH_PROBE_TIMEOUT,
            env=guard_resolve.tirith_child_env(),
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
