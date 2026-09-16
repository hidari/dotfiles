"""CI ワークフローの各 run step が実際に使う shell を YAML の構造として観測する.

判定は呼び出し側 (scripts/tests/ci-wiring.bats) が行う.

shell を持たない run step は GitHub Actions の既定 (bash -e) で動き, pipefail が付かない.
既定の決まり方は step の shell, job の defaults.run, workflow の defaults.run の順で,
job に defaults.run があると workflow 側の defaults.run は丸ごと使われない
(キーごとには混ざらない. working-directory だけを持つ job で bash -e になったのを CI の
ログで確認した).

実行: uv run --quiet --no-project --with pyyaml python3 <このファイル>
"""

from __future__ import annotations

import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = Path(os.environ.get("WORKFLOW_FILE", REPO_ROOT / ".github" / "workflows" / "test.yml"))

# bash は -eo pipefail で動く. pwsh はパイプの失敗の扱いが別なので対象外として通す.
ALLOWED_SHELLS = {"bash", "pwsh"}


def run_defaults_shell(owner: dict) -> tuple[bool, object]:
    """owner (workflow か job) が defaults.run を持つかと, その shell を返す."""
    defaults = owner.get("defaults") or {}
    if "run" not in defaults:
        return False, None
    return True, (defaults.get("run") or {}).get("shell")


def main() -> None:
    with WORKFLOW.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    _, workflow_shell = run_defaults_shell(data)
    count = 0
    offenders: list[str] = []
    for job_id, job in (data.get("jobs") or {}).items():
        job_has_run_defaults, job_shell = run_defaults_shell(job)
        inherited = job_shell if job_has_run_defaults else workflow_shell
        for step in job.get("steps") or []:
            if "run" not in step:
                continue
            count += 1
            shell = step.get("shell", inherited)
            if shell not in ALLOWED_SHELLS:
                offenders.append(f"{job_id}/{step.get('name', '?')}")

    print(f"RUN_STEP_COUNT={count}")
    print(f"RUN_STEP_WITHOUT_SHELL={','.join(offenders)}")


if __name__ == "__main__":
    main()
