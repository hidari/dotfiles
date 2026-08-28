"""検査層が沈黙している状態を見る述語と、その登録簿。

PreToolUse の 2 つのガードは、どちらも自分が機能していない状態を検出できない。検出できて
いる箇所はあるが、射程が実態より狭い。この層はセッション頭で生存を測るためのものである。

述語をここへ集めるのは、同じ判定を 2 箇所へ書くと片方だけ直したときに沈黙して食い違う
ためである。それはこの層が扱っている欠陥そのものなので、canonical を 1 つにする。

print と sys.exit は持たない。副作用を持ち込むとこの層だけを直接テストできなくなる
(pretooluse.py と同じ規則)。

フックからは sys.path[0] (スクリプトのディレクトリ) 経由で解決される。
"""

from __future__ import annotations

import os
import shutil
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
