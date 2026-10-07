"""apm ガードの shim を解決する軽量ロジック。

強制層 (PreToolUse の apm-install-guard.py) がこのモジュールを Bash 呼び出しのたびに
import する。ここで `subprocess` や `dataclasses` を import するとそのコストが全 Bash
呼び出しに乗るため、import してよいのは `os` と `shutil` までに限る。プローブの判定ロジック
(ProbeResult や PROBES 登録簿) は guard_probes.py が持つ。そちらは SessionStart (セッションに
1 回) からしか呼ばれないので重い import を許容できる。強制層が guard_probes.py を import すると
診断層への依存が逆向きになり、診断層の import 失敗がガードを道連れにする。

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


def shim_exists() -> bool:
    """shim の実体が置かれているか。健全性ではなく手当ての出し分けにだけ使う。

    健全かどうかを決めるのは shim_resolves であって、この述語ではない (DEFAULT_SHIM_PATH の
    コメント参照)。置かれていても PATH に載っていなければ一度も横取りしないので、これを
    健全性の判定へ使うと守っていない状態が緑で通る。

    それでも存在を別に測るのは、沈黙の原因が 2 通りあって手当てが正反対になるためである。
    置かれていないなら配置のやり直しが要り、置かれているなら配置は正しくて起動元のシェルが
    古い。

    symlink は辿った先で見る。shim は symlink として配置されるので、辿れない symlink は
    配置済みではなく張り直しが要る側にあたる。
    """
    return os.path.exists(os.path.expanduser(shim_path()))


# apm ガードが横取りしていないときの手当て。原因が 2 通りあり、それぞれ正反対の作業になるので
# 分けて持つ。どちらを選ぶかは shim_exists が決める。
#
# leaf のここに置くのは、強制層 (apm-install-guard.py の deny) と診断層 (guard_probes.py) の
# 両方が使うためである。実際に apm を打った人が読むのは強制層の理由文なので、診断層だけを
# 直しても踏んだ人には届かない。
#
# 文面を定数へ出してあるのは、どちらが選ばれたかをテストが exact に pin するためである。
# 散文そのものの正しさはどの検査も見ないので、せめて分岐の選択だけは機械に見せる。
APM_REMEDY_MISSING_SHIM = (
    "shim が配置されていない。bootstrap.sh を実行し、そのあと Claude Code を起動し直す。"
)

# この原因には bootstrap.sh も Claude Code の再起動も効かない。それらを勧めると1往復を
# 空振りさせる (2026-08-31 に実測)。
APM_REMEDY_STALE_SHELL = (
    "shim は配置済みで、Claude Code の PATH に載っていないだけである。Claude Code は PATH を"
    "起動元のシェルから継承するので、Claude Code だけを起動し直しても直らない。shim を PATH へ"
    "足す行を読んだ新しいシェル (端末のタブを開き直すか exec zsh) から起動する。"
    "bootstrap.sh は要らない。"
)


def apm_remedy() -> str:
    """apm ガードが横取りしていない状態に対する手当てを 1 つ選ぶ。

    選択の規則を関数へ出すのは、強制層と診断層が同じ分岐を書くと片方だけが古びるためである。
    定数を共有しても、どちらを選ぶかを 2 箇所に書けば同じ二重管理が残る。
    """
    return APM_REMEDY_STALE_SHELL if shim_exists() else APM_REMEDY_MISSING_SHIM
