"""apm が deploy する vendored skill が全て gitignore されているか検査する。

apm.lock.yaml の deployed_files は「apm が .claude/skills 配下へ展開する再生成物」の
canonical な一覧。install-at-bootstrap では deploy 先を gitignore して bootstrap で再生成する
前提なので、deployed_files は全て home/.gitignore で ignore されねばならない。ignore が
per-skill 手書きのため skill 追加時に追記漏れが起きうる(漏れると vendored skill が tracked に
なり誤コミットされる)ので、lockfile を真実源に機械検査して二重管理の drift を検出する。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

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


def _is_ignored(repo_root: str, repo_rel_path: str) -> bool:
    proc = subprocess.run(
        ["git", "-C", repo_root, "check-ignore", "-q", repo_rel_path],
        capture_output=True,
        check=False,
    )
    # 0=ignored / 1=not ignored。それ以外(128 fatal: git repo でない等)を「not ignored」と
    # 誤解して findings を量産せず、明示的に失敗させる(git エラーと追記漏れを取り違えない)。
    if proc.returncode not in (0, 1):
        raise RuntimeError(
            f"git check-ignore が失敗しました (exit {proc.returncode}): {repo_rel_path}"
        )
    return proc.returncode == 0


def check_apm_deployed_files_ignored(repo_root: str) -> list[Finding]:
    """apm.lock.yaml の deployed_files が全て gitignore されているか検査する。

    lockfile が無い(apm 未使用)場合は検査対象なしで空を返す。
    """
    lockfile = Path(repo_root) / LOCKFILE_PATH
    if not lockfile.is_file():
        return []

    deployed = parse_deployed_files(lockfile.read_text(encoding="utf-8"))
    findings: list[Finding] = []
    for rel in deployed:
        # git は file のみ track するため、検査対象は leaf ファイルのみ。dir エントリ
        # (配下に別エントリを持つ placeholder) は apm の bookkeeping であって git-trackable な
        # 実体ではないので scope 外。加えて未展開 dir は trailing-slash パターンに
        # git check-ignore がマッチせず false-positive になる(非存在でもファイルパスは親
        # ディレクトリパターンに正しくマッチする)ため、いずれの観点でも leaf に絞る。
        if any(other.startswith(rel + "/") for other in deployed):
            continue
        # deployed_files は home/(apm.yml の位置)基準。repo root 基準に home/ を前置する。
        repo_rel = f"home/{rel}"
        if not _is_ignored(repo_root, repo_rel):
            findings.append(
                Finding(
                    LOCKFILE_PATH,
                    repo_rel,
                    "apm deploy 先が gitignore されていません (home/.gitignore に要追記)",
                )
            )
    return findings
