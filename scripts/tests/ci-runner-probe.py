"""CI ワークフローの各 job が使うランナーを YAML の構造として読み, 浮動ラベルを持つ job を列挙する.

`-latest` を含むラベル (ubuntu-latest や macos-latest-xlarge) は, GitHub がイメージを新しい版へ
移したときに中身が黙って変わる. ランナーは版を明示したラベルで指す.

runs-on は文字列・ラベルの配列・group / labels の3つの形から読む. 式 (`${{ }}`) で書いた runs-on は
値を解決しないので, matrix などで浮動ラベルを渡すと見逃す. runs-on を持たない job
(再利用ワークフローの呼び出し) は数えない.

判定はここで行い, 呼び出し側 (scripts/tests/ci-wiring.bats) は件数と一覧を照合するだけ.
実行は scripts/tests/test_helper.bash の run_yaml_probe を通し, ワークフローのディレクトリを渡す.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml


def labels_of(runs_on: object) -> list[str]:
    if isinstance(runs_on, dict):
        runs_on = runs_on.get("labels") or []
    if isinstance(runs_on, str):
        return [runs_on]
    return [str(label) for label in runs_on]


def main() -> None:
    (directory,) = sys.argv[1:]
    # GitHub は .yml と .yaml の両方をワークフローとして読む
    workflows = sorted([*Path(directory).glob("*.yml"), *Path(directory).glob("*.yaml")])

    count = 0
    floating: list[str] = []
    for path in workflows:
        with path.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        for job_id, job in (data.get("jobs") or {}).items():
            if "runs-on" not in job:
                continue
            count += 1
            if any("-latest" in label for label in labels_of(job["runs-on"])):
                floating.append(f"{path.name}/{job_id}")

    print(f"RUNNER_JOB_COUNT={count}")
    print(f"RUNNER_FLOATING={','.join(floating)}")


if __name__ == "__main__":
    main()
