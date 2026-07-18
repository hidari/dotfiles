"""pin と最新版の関係を扱う純粋ロジック。

mise の exact pin に対して素の `mise outdated` は構造的に盲目 (requested レンジが pin
そのものなので、レンジ内に新しい版が無い)。そのため更新の有無は「互換範囲の最新」と
「絶対的な最新」を別々に問い合わせて pin と比べる形で判定する。
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

# major.minor.patch と任意の prerelease / build metadata。exact pin ガード
# (config-guard の mise_pins) を通った版だけがここへ来る前提。
_VERSION_PATTERN = re.compile(
    r"(?P<major>\d+)\.(?P<minor>\d+)\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?"
)


@dataclass(frozen=True)
class ToolStatus:
    """1 ツールの pin と、2 通りの最新版。"""

    tool: str
    pinned: str
    compatible_latest: str
    absolute_latest: str


def compatible_spec(version: str) -> str:
    """破壊的変更を跨がない範囲を表す mise spec を返す。

    semver では 0.x の破壊的変更の軸は minor なので、0 系だけ major.minor を返す
    (0.3.3 の互換範囲に 0.4.0 を含めない)。
    """
    matched = _VERSION_PATTERN.fullmatch(version)
    if matched is None:
        raise ValueError(f"exact な version ではないため互換範囲を導出できません: {version!r}")
    major = matched.group("major")
    if major != "0":
        return major
    return f"0.{matched.group('minor')}"


def has_compatible_update(status: ToolStatus) -> bool:
    """互換範囲の中に、pin より新しい版があるか。"""
    return status.compatible_latest != status.pinned


def has_major_update(status: ToolStatus) -> bool:
    """互換範囲の外に、さらに新しい版があるか。"""
    return status.absolute_latest != status.compatible_latest


def read_pins(config_path: Path) -> dict[str, str]:
    """mise config の [tools] を宣言順の dict で返す。

    判定できない形 (list / table) は黙って捨てず失敗させる。捨てるとそのツールだけが
    監視対象から静かに外れ、更新を永久に見逃す。
    """
    with config_path.open("rb") as handle:
        config = tomllib.load(handle)

    tools = config.get("tools", {})
    if not isinstance(tools, dict):
        raise ValueError(f"[tools] がテーブルではありません: {tools!r}")

    pins: dict[str, str] = {}
    for tool, spec in tools.items():
        if not isinstance(spec, str):
            raise ValueError(f"version 指定が文字列ではありません: {tool} = {spec!r}")
        pins[tool] = spec
    return pins
