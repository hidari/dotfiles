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


# apm ガードが沈黙しているときの手当て。原因が 2 通りあり、それぞれ正反対の作業になるので
# 分けて持つ。文面を定数へ出してあるのは、どちらが選ばれたかをテストが exact に pin する
# ためである。散文の正しさ自体はどの検査も見ないので、せめて分岐の選択だけは機械に見せる。
APM_REMEDY_MISSING_SHIM = (
    "shim が配置されていない。bootstrap.sh を実行し、そのあと Claude Code を起動し直す。"
)

# 2026-08-31 に実際に踏んだ側。当時の文面は bootstrap.sh と Claude Code の再起動を勧めて
# おり、どちらもこの原因には効かないため 1 往復を空振りさせた。
APM_REMEDY_STALE_SHELL = (
    "shim は配置済みで、Claude Code の PATH に載っていないだけである。Claude Code は PATH を"
    "起動元のシェルから継承するので、Claude Code だけを起動し直しても直らない。shim を PATH へ"
    "足す行を読んだ新しいシェル (端末のタブを開き直すか exec zsh) から起動すること。"
    "bootstrap.sh は要らない。"
)


def probe_apm() -> ProbeResult:
    """apm ガードの shim が実際に横取りする位置にあるか。

    フックが見る PATH を測っている。フックは Claude Code のプロセスから起動されるので、
    対話シェルの PATH に載っていても Claude Code の PATH に載っていなければ守っていない。

    Claude Code は PATH を自分で作らず、起動元のシェルから継承する。shim を PATH へ足す行が
    入るより前から生きているシェルから起動すると載らず、Claude Code だけを起動し直しても
    継承元が同じなので直らない (2026-08-31 に ps で祖先を辿って実測)。
    """
    if guard_resolve.shim_resolves():
        return ProbeResult(healthy=True)
    remedy = APM_REMEDY_STALE_SHELL if guard_resolve.shim_exists() else APM_REMEDY_MISSING_SHIM
    return ProbeResult(
        healthy=False,
        detail=(
            f"PATH 上の apm が {guard_resolve.shim_path()} へ解決されないため、apm ガードは"
            "横取りしていない。フックが自力で捕まえる形 (素の apm / 絶対パス / PATH の一時"
            "差し替え) は deny されるが、包み込みや変数間接や xargs の形は無音で素通りする。"
            f"{remedy}"
        ),
    )


# tirith が PATH 上で解決しないときの手当て。原因は apm 側と同じく 2 通りある。入っていない
# 場合と、入っているのに PATH へ載っていない場合である。
#
# apm と違ってここでは区別しない。区別するには tirith の置き場を決め打つ必要があり、それは
# Homebrew が持つ事実の写しになって drift する。shim の置き場は bootstrap.sh が配置するので
# こちらが canonical を持てるが、tirith の置き場は持てない。
#
# 区別できないからこそ片方だけを勧めてはならない。2026-08-31 に PATH から /opt/homebrew/bin を
# 外して実測したところ、tirith は brew で入っているのに brew install tirith だけを勧めた。
TIRITH_REMEDY_UNRESOLVED = (
    "入っていないなら brew install tirith で戻る。入っているなら PATH に載っていないだけで、"
    "Claude Code を起動し直しても直らない。PATH を整えた新しいシェルから起動する。"
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
                "コマンドは検査されないまま通る。"
                f"{TIRITH_REMEDY_UNRESOLVED}"
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
