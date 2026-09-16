"""CI ワークフローの各 run step が実際に使う shell を YAML の構造として決め, 許可外の step を列挙する.

shell を持たない run step は GitHub Actions の既定 (bash -e) で動き, pipefail が付かない.
既定の決まり方は step の shell, job の defaults.run, workflow の defaults.run の順で,
job に defaults.run があると workflow 側の defaults.run は丸ごと使われない
(キーごとには混ざらない. working-directory だけを持つ job で bash -e になったのを CI の
ログで確認した).

判定はここで行い, 呼び出し側 (scripts/tests/ci-wiring.bats) は件数と一覧を照合するだけ.

実行: uv run --quiet --no-project --with pyyaml python3 <このファイル> <workflow のパス>
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

# bash は -eo pipefail で動く. pwsh はパイプの失敗の扱いが別なので対象外として通す.
ALLOWED_SHELLS = {"bash", "pwsh"}


def default_shell(owner: dict, fallback: object = None) -> object:
    """owner (workflow か job) の defaults.run が決める shell を返す.

    defaults.run が無いときだけ fallback を返す.
    """
    defaults = owner.get("defaults") or {}
    if "run" not in defaults:
        return fallback
    return (defaults["run"] or {}).get("shell")


def main() -> None:
    (workflow,) = sys.argv[1:]
    with Path(workflow).open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)

    workflow_shell = default_shell(data)
    count = 0
    offenders: list[str] = []
    for job_id, job in (data.get("jobs") or {}).items():
        inherited = default_shell(job, workflow_shell)
        for step in job.get("steps") or []:
            if "run" not in step:
                continue
            count += 1
            if step.get("shell", inherited) not in ALLOWED_SHELLS:
                offenders.append(f"{job_id}/{step.get('name', '?')}")

    print(f"RUN_STEP_COUNT={count}")
    print(f"RUN_STEP_DISALLOWED_SHELL={','.join(offenders)}")


if __name__ == "__main__":
    main()
