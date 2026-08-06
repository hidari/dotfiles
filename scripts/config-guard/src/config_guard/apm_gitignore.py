"""apm が deploy する成果物が全て gitignore されているか検査する。

apm.lock.yaml の deployed_files は「apm が展開する再生成物」の canonical な一覧。
install-at-bootstrap では deploy 先を gitignore して bootstrap で再生成する前提なので、
deployed_files は全て home/.gitignore で ignore されねばならない。

ignore はディレクトリ単位なのでパッケージ追加では追記が要らない。この検査が捕まえるのは
apm が新しい deploy root を作った場合で、そのとき成果物が tracked になり誤コミットされる。
lockfile を真実源に機械検査して、ignore 規則が deploy 先の実態から遅れることを検出する。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.git_run import run_git
from config_guard.models import Finding

LOCKFILE_PATH = "home/apm.lock.yaml"


def parse_deployed_files(lockfile_text: str) -> list[str]:
    """apm.lock.yaml から deployed_files のパス一覧を抽出する(stdlib のみ、YAML lib 非使用)。

    各 dependency の `deployed_files:` ブロック直下の `- <path>` 行を集める。ブロックは
    次の非リスト行(deployed_file_hashes: 等)で終わる。パスは home/ 基準の相対。
    """
    paths: list[str] = []
    in_block = False
    for line in lockfile_text.splitlines():
        stripped = line.strip()
        if stripped == "deployed_files:":
            in_block = True
            continue
        if in_block:
            if stripped.startswith("- "):
                paths.append(stripped[2:].strip())
            else:
                in_block = False
    return paths


def _ignored_paths(repo_root: str, repo_rel_paths: list[str]) -> set[str]:
    """渡したパスのうち ignore されているものの集合を返す。

    パス 1 件ごとにプロセスを起動すると deployed_files の件数分の fork/exec で検査時間を
    支配する(実測で config-guard 全体の過半)ため、`--stdin -z` で 1 プロセスに集約する。
    -z は入出力とも NUL 区切りで、出力には ignore されたパスだけが echo back される
    (0=1 件以上 ignored / 1=全て not ignored、と実験で確認済み)。
    """
    if not repo_rel_paths:
        # check-ignore は空入力でも exit 1 で正常終了するが、答えが自明なら起動しない
        return set()
    proc = run_git(repo_root, "check-ignore", "--stdin", "-z", stdin="\0".join(repo_rel_paths))
    # 0=1 件以上 ignored / 1=全て not ignored。それ以外(128 fatal: git repo でない等)を
    # 「not ignored」と誤解して findings を量産せず、明示的に失敗させる
    # (git エラーと追記漏れを取り違えない)。
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"git check-ignore が失敗しました (exit {proc.returncode})")
    return {path for path in proc.stdout.split("\0") if path}


def check_apm_deployed_files_ignored(repo_root: str) -> list[Finding]:
    """apm.lock.yaml の deployed_files が全て gitignore されているか検査する。

    lockfile が無い(apm 未使用)場合は検査対象なしで空を返す。
    """
    lockfile = Path(repo_root) / LOCKFILE_PATH
    if not lockfile.is_file():
        return []

    deployed = parse_deployed_files(lockfile.read_text(encoding="utf-8"))
    # git は file のみ track するため、検査対象は leaf ファイルのみ。dir エントリ
    # (配下に別エントリを持つ placeholder) は apm の bookkeeping であって git-trackable な
    # 実体ではないので scope 外。加えて未展開 dir は trailing-slash パターンに
    # git check-ignore がマッチせず false-positive になる(非存在でもファイルパスは親
    # ディレクトリパターンに正しくマッチする)ため、いずれの観点でも leaf に絞る。
    # deployed_files は home/(apm.yml の位置)基準。repo root 基準に home/ を前置する。
    leaves = [
        f"home/{rel}"
        for rel in deployed
        if not any(other.startswith(rel + "/") for other in deployed)
    ]
    ignored = _ignored_paths(repo_root, leaves)
    return [
        Finding(
            LOCKFILE_PATH,
            repo_rel,
            "apm deploy 先が gitignore されていません (home/.gitignore に要追記)",
        )
        for repo_rel in leaves
        if repo_rel not in ignored
    ]
