"""apm / tirith の shim とバイナリを解決する軽量ロジック。

強制層 (PreToolUse の apm-install-guard.py / tirith-check.py) がこのモジュールを
Bash 呼び出しのたびに import する。ここで `subprocess` や `dataclasses` を import すると
そのコストが全 Bash 呼び出しに乗るため、import してよいのは `os` と `shutil` までに
限る。プローブの判定ロジック (ProbeResult や PROBES 登録簿、実際に tirith を起動する
probe_tirith) は guard_probes.py が持つ。そちらは SessionStart (セッションに 1 回) からしか
呼ばれないので重い import を許容できる。強制層が guard_probes.py を import すると
診断層への依存が逆向きになり、診断層の import 失敗が両ガードを道連れにする。

tirith_child_env / tirith_check_argv をここへ置くのは、tirith-check.py 本体と
guard_probes.probe_tirith がどちらも同じ環境・同じ argv で tirith check を呼ぶ必要が
あるため (呼び方が違うとフックが通る経路とは別のものを測ることになる)。関数を共有すれば
片方だけ直して食い違う経路が構造的に無くなる。

フックからは sys.path[0] (スクリプトのディレクトリ) 経由で解決される。
"""

from __future__ import annotations

import os
import shutil

# 配布した shim の置き場。bootstrap.sh の SYMLINK_PAIRS が張る target と同じ値で、
# 一致は test_guard_probes.py の cross-pin テストが見る。
# 存在ではなく「PATH 上の apm がここへ解決されるか」を見る。ファイルがあっても PATH に
# 載っていなければ shim は一度も横取りしないので、存在検査は緑のまま守っていない状態を作る。
DEFAULT_SHIM_PATH = "~/.local/libexec/apm-guard/apm"

# tirith の子プロセスへ渡す環境から落とす接頭辞。tirith-check.py 本体と probe_tirith が
# 同じ規則を共有する (tirith_child_env 参照)。検査の基礎を外から動かせる変数を渡さないため。
_DROPPED_TIRITH_PREFIX = "TIRITH_"


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


def resolve_tirith_bin() -> str:
    """tirith バイナリのパスを解決する: TIRITH_BIN → PATH。

    どちらでも見つからなければ "tirith" を返す。呼び出し側の subprocess が
    FileNotFoundError を投げ、そこで不在を判定する。machine 固有パスを settings に
    焼かず実行時に解決するのは、この設定が全プロジェクトで共有されるためである。

    tirith は Homebrew 管理 (home/.Brewfile) で /opt/homebrew/bin へ入るため PATH で拾える。
    mise 管理だった頃の shim 探索段は、実体化経路が brew へ移った時点で到達しなくなった。
    """
    return os.environ.get("TIRITH_BIN") or shutil.which("tirith") or "tirith"


def tirith_child_env() -> dict[str, str]:
    """tirith の子プロセスへ渡す環境。TIRITH_ 接頭辞を落とし、integration だけ足す。

    tirith-check.py 本体と probe_tirith が個別に組み立てると、片方だけ直したときに
    無音で食い違う (どちらも「clean」と応答して見えるが、片方は検査を弱めた環境で
    呼んでいる、という形の drift)。ここへ 1 つだけ置いて両方から呼ぶ。
    """
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith(_DROPPED_TIRITH_PREFIX)
    }
    env["TIRITH_INTEGRATION"] = "claude-code"
    return env


def tirith_check_argv(tirith_bin: str, command: str) -> list[str]:
    """`tirith check` の argv を組み立てる。

    tirith-check.py 本体と probe_tirith が同じフラグ (--json --non-interactive --shell posix)
    で呼ぶことを保証する。フラグが 1 つでも違うとデーモンを経由するかどうかが変わり、
    プローブがフックの通る経路とは別のものを測ることになる。
    """
    return [tirith_bin, "check", "--json", "--non-interactive", "--shell", "posix", "--", command]
