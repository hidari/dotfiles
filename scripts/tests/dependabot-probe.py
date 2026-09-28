"""Dependabot の github-actions の更新が, 外部 action を使う場所をすべて覆っているかを調べる.

外部 action を uses で使うのは, .github/workflows のワークフロー (Dependabot の directory では `/`) と,
.github/actions 配下の composite action である. どちらかが覆いから外れると, その場所の pin だけが
更新されずに黙って古くなる. run だけの composite は Dependabot が上げる対象を持たないので数えない.

照合は Dependabot の読み方に合わせる. directories の glob は `/` で区切った1段ごとに当て,
`**` だけが段をまたぐ. 単数形の directory は glob を解釈しないので完全一致で比べる.
他の package-ecosystem の覆いは数えない.

判定はここで行い, 呼び出し側 (scripts/tests/ci-wiring.bats) は件数と一覧を照合するだけ.
実行は scripts/tests/test_helper.bash の run_yaml_probe を通し, リポジトリのルートを渡す.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable
from fnmatch import fnmatchcase
from pathlib import Path

import yaml


def uses_external_action(steps: Iterable[object]) -> bool:
    # ./ はリポジトリ内の action, docker:// は Dependabot の github-actions の対象外
    return any(
        isinstance(step, dict)
        and isinstance(step.get("uses"), str)
        and not step["uses"].startswith(("./", "docker://"))
        for step in steps
    )


def load(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def action_dirs(root: Path) -> list[str]:
    jobs = [
        job
        for workflow in (root / ".github" / "workflows").glob("*.y*ml")
        for job in (load(workflow).get("jobs") or {}).values()
    ]
    steps = [step for job in jobs for step in job.get("steps") or []]
    # job の uses は再利用ワークフローの呼び出しで, これも Dependabot が上げる
    dirs = ["/"] if uses_external_action([*jobs, *steps]) else []
    composites = sorted((root / ".github" / "actions").rglob("action.y*ml"))
    return dirs + [
        f"/{path.parent.relative_to(root)}"
        for path in composites
        if uses_external_action((load(path).get("runs") or {}).get("steps") or [])
    ]


def segments(path: str) -> list[str]:
    return [part for part in path.split("/") if part]


def glob_matches(parts: list[str], pattern: list[str]) -> bool:
    if not pattern:
        return not parts
    if pattern[0] == "**":
        return any(glob_matches(parts[index:], pattern[1:]) for index in range(len(parts) + 1))
    return bool(parts) and fnmatchcase(parts[0], pattern[0]) and glob_matches(parts[1:], pattern[1:])


def main() -> None:
    (root_text,) = sys.argv[1:]
    root = Path(root_text)
    config = load(root / ".github" / "dependabot.yml")

    globs: list[list[str]] = []
    exact: list[list[str]] = []
    for update in config.get("updates") or []:
        if update.get("package-ecosystem") != "github-actions":
            continue
        globs += [segments(pattern) for pattern in update.get("directories") or []]
        if "directory" in update:
            exact.append(segments(update["directory"]))

    dirs = action_dirs(root)
    uncovered = [
        d
        for d in dirs
        if segments(d) not in exact and not any(glob_matches(segments(d), g) for g in globs)
    ]
    print(f"ACTION_DIR_COUNT={len(dirs)}")
    print(f"UNCOVERED_ACTION_DIRS={','.join(uncovered)}")


if __name__ == "__main__":
    main()
