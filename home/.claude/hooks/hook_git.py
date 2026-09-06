"""フックから git の作業ツリーの根を解決する leaf。

同じ解決を 2 つのフックが要る。handoff-sentinel は状態ファイルの名前を作るために、
guard_probes はタスクリスト識別子の導出元を決めるために呼ぶ。同じ規則を 2 箇所へ書くと
片方だけ直したときに沈黙して食い違うので、canonical をここへ置く。

print と sys.exit は持たない。副作用を持ち込むとこの層だけを直接テストできなくなる
(pretooluse.py / guard_probes.py と同じ規則)。

subprocess をモジュール直下で import する。呼び出し側のうち handoff-sentinel は
ツール呼び出しごとに走る経路を持ち、そこがこのコストを払わないよう自分の関数の内側で
このモジュールを import する。ここで遅延させても、import する側が直下に置けば同じコストが
戻るので、遅延の位置は呼び出し側が決める。

フックからは sys.path[0] (スクリプトのディレクトリ) 経由で解決される。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

# 解決の上限 (秒)。「応答しない」を判定するための上限であって通常経路の待ち時間ではない。
RESOLVE_TIMEOUT = 5.0

# git の repo / worktree / index の位置を上書きする環境変数。git hook 経由の実行では git が
# これらを子へ渡すため、継承すると `git -C <cwd>` の repo 探索が hook 側の repo に上書きされる。
# repo の指定を -C に一本化するため、これらを除いた環境で git を起動する。
LOCATION_VARS = frozenset(
    {
        "GIT_DIR",
        "GIT_WORK_TREE",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_COMMON_DIR",
        "GIT_PREFIX",
        "GIT_NAMESPACE",
    }
)


def isolated_env() -> dict[str, str]:
    """ロケーション系 GIT_* を除いた環境変数を返す。

    落とすのを所在の指定だけに絞るのは、フック本体が本番環境で動くためである。GIT_ 接頭辞ごと
    落とすと認証やページャの設定まで剥がれ、本番とは別の条件で git を起動することになる。
    """
    return {k: v for k, v in os.environ.items() if k not in LOCATION_VARS}


def repo_root(cwd: str | Path) -> Path:
    """cwd の git リポルートを返す。リポ外・git 不在は cwd に落とす。

    symlink は解決しない。解決するかどうかは呼び出し側の都合で決まるので、必要な側が
    渡す前に解決する。ここで解決すると、この根から状態ファイルの名前を作っている側の
    既存ファイルが別名になって参照できなくなる。
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            timeout=RESOLVE_TIMEOUT,
            check=False,
            env=isolated_env(),
        )
    except (OSError, subprocess.TimeoutExpired):
        return Path(cwd)
    top = result.stdout.strip()
    return Path(top) if result.returncode == 0 and top else Path(cwd)
