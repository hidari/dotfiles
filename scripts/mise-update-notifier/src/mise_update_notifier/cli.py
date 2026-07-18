"""mise を呼んで pin と最新版を突き合わせ、報告本文とサマリを出す。

外界に触れるのはこの層だけ。判定と整形は versions / report の純粋関数が持つ。
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections.abc import Callable
from pathlib import Path

from mise_update_notifier.report import render_body
from mise_update_notifier.versions import (
    ToolStatus,
    compatible_spec,
    has_compatible_update,
    has_major_update,
    read_pins,
)

MiseLatest = Callable[[str], str]


def run_mise_latest(spec: str) -> str:
    """`mise latest <spec>` の出力を返す。

    stderr は捕捉せずジョブログへ流す。捕捉すると CalledProcessError が exit status しか
    語らず、ネットワーク断や rate limit で落ちたときに原因不明の赤になる。
    """
    proc = subprocess.run(
        ["mise", "latest", spec],
        stdout=subprocess.PIPE,
        text=True,
        check=True,
    )
    return proc.stdout.strip()


def collect_statuses(pins: dict[str, str], mise_latest: MiseLatest) -> list[ToolStatus]:
    """各 pin について互換範囲の最新と絶対的な最新を問い合わせる。

    mise は存在しないメジャーに対して exit 0 と空文字列を返すため、空は「更新なし」では
    なく問い合わせの失敗として扱う。
    """
    statuses: list[ToolStatus] = []
    for tool, pinned in pins.items():
        compatible_query = f"{tool}@{compatible_spec(pinned)}"
        absolute = _require_version(tool, mise_latest(tool))
        compatible = _require_version(compatible_query, mise_latest(compatible_query))
        statuses.append(
            ToolStatus(
                tool=tool,
                pinned=pinned,
                compatible_latest=compatible,
                absolute_latest=absolute,
            )
        )
    return statuses


def _display_path(config_path: Path) -> str:
    """報告本文に載せるパス。本文は公開先 (GitHub Issue) へ出るのでホームの絶対パスを晒さない。"""
    try:
        return str(config_path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return config_path.name


def _require_version(spec: str, result: str) -> str:
    if not result:
        raise RuntimeError(f"mise latest {spec} が版を返しませんでした (spec の導出を確認)")
    return result


def main(argv: list[str] | None = None, run_mise_latest: MiseLatest = run_mise_latest) -> int:
    parser = argparse.ArgumentParser(description="mise の exact pin に対する更新を報告する")
    parser.add_argument("--config", required=True, type=Path, help="mise config のパス")
    parser.add_argument("--body-out", required=True, type=Path, help="報告本文の出力先")
    args = parser.parse_args(argv)

    pins = read_pins(args.config)
    statuses = collect_statuses(pins, run_mise_latest)
    body = render_body(statuses, _display_path(args.config))
    args.body_out.write_text(body, encoding="utf-8")

    summary = {
        "has_updates": bool(body),
        "compatible": sum(1 for s in statuses if has_compatible_update(s)),
        "major": sum(1 for s in statuses if has_major_update(s)),
    }
    print(json.dumps(summary))
    return 0
