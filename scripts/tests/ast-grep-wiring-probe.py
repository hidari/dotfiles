"""ast-grep scan の配線を YAML の構造として観測し KEY=VALUE 形式で出力する.

判定は呼び出し側 (scripts/tests/ast-grep.bats) が行う.

regex での text-parse を避け, YAML を safe_load して言語自身に解釈させる
(グローバル CLAUDE.md の MUST: 設定のデータ構造を検証するときは定義を
source / import して言語自身に解釈させる).
regex 版は行頭錨が無く, コメントアウトした run 行を false pass し,
run: | のブロックスカラーを false fail していた.

実行: uv run --quiet --no-project --with pyyaml python3 <このファイル>
--no-project を必ず付ける (付けないと backup-tool の依存を sync しに行く).
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
PRECOMMIT = REPO_ROOT / ".pre-commit-config.yaml"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "test.yml"

SCAN = "ast-grep scan"
FLAG = "--no-ignore hidden"


def load(path: Path) -> object:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def check_precommit() -> None:
    """id が ast-grep-scan の hook を数え entry がフラグを持つか見る."""
    data = load(PRECOMMIT)
    entries: list[str] = []
    for repo in data.get("repos", []):
        for hook in repo.get("hooks", []):
            if hook.get("id") == "ast-grep-scan":
                entries.append(str(hook.get("entry", "")))
    missing = sum(1 for entry in entries if not (SCAN in entry and FLAG in entry))
    print(f"PRECOMMIT_HOOK_COUNT={len(entries)}")
    print(f"PRECOMMIT_ENTRY_MISSING_FLAG={1 if missing else 0}")


def check_workflow() -> None:
    """run に ast-grep scan を含む step を数え フラグを持つか見る."""
    data = load(WORKFLOW)
    runs: list[str] = []
    for job in data.get("jobs", {}).values():
        for step in job.get("steps", []):
            run = str(step.get("run", ""))
            if SCAN in run:
                runs.append(run)
    missing = sum(1 for run in runs if FLAG not in run)
    print(f"WORKFLOW_STEP_COUNT={len(runs)}")
    print(f"WORKFLOW_RUN_MISSING_FLAG={1 if missing else 0}")


def main() -> None:
    check_precommit()
    check_workflow()


if __name__ == "__main__":
    main()
