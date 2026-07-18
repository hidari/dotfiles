"""mise の global ツール pin が exact 指定であることを検査する。

home/.config/mise/config.toml は「exact 指定で全マシンを完全再現する」規約を持つが、
規約はコメントにしか書かれておらず何も強制していなかったため、`just = "latest"` が
素通りした実績がある。浮動 pin はマシンごとに解決版が変わり、config を symlink して
いても再現性が崩れる(しかも壊れるまで気づけない)ので、ここで機械的に弾く。

この guard は「exact であることの証明」ではなく「明らかな浮動形の排除」である。mise は
exact 一致しない spec を prefix 一致で最新版へ解決するため、`1.0.0-rc` のように
prerelease の途中までを書いた spec は形の上では版に見えるが実際は浮動する。文字列だけ
では実在するタグと prefix を区別できず、静的には閉じられない既知の限界。

version 形の canonical な定義は EXACT_VERSION_PATTERN 一箇所に置き、config.toml 側の
コメントには literal を再掲しない(二重記述は drift する)。
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from config_guard.models import Finding

MISE_CONFIG_PATH = "home/.config/mise/config.toml"

# semver の major.minor.patch と任意の prerelease / build metadata。部分指定 ("1", "1.56")
# は mise が「その系列の最新」に解決する浮動 pin なので弾く。build metadata (Java の
# "21.0.8+9" や zig の dev build) は版を一意に固定するので通す。
EXACT_VERSION_PATTERN = re.compile(r"\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?(\+[0-9A-Za-z.-]+)?")


def is_exact_version(spec: str) -> bool:
    """version 指定が版を一意に固定する形か判定する。"""
    return EXACT_VERSION_PATTERN.fullmatch(spec) is not None


def check_mise_pins(repo_root: str) -> list[Finding]:
    """mise config の [tools] が全て exact 指定か検査する。

    config が無い(mise 未使用)場合は検査対象なしで空を返す。判定できない形は素通り
    させず Finding にする(fail-closed。素通りは浮動 pin の見逃しに直結する)。
    """
    config_path = Path(repo_root) / MISE_CONFIG_PATH
    if not config_path.is_file():
        return []

    with config_path.open("rb") as handle:
        config = tomllib.load(handle)

    tools = config.get("tools", {})
    if not isinstance(tools, dict):
        return [
            Finding(
                MISE_CONFIG_PATH,
                f"tools = {tools!r}",
                "[tools] がテーブルではないため pin を検査できません",
            )
        ]

    findings: list[Finding] = []
    for tool, spec in tools.items():
        # 複数版指定 (list) やテーブル指定は「exact でない」ではなく「この guard では
        # 判定できない」形。浮動 pin と混同させないため message を分ける。
        if not isinstance(spec, str):
            findings.append(
                Finding(
                    MISE_CONFIG_PATH,
                    f"{tool} = {spec!r}",
                    "version 指定が文字列ではなく exact か判定できません",
                )
            )
            continue
        if not is_exact_version(spec):
            findings.append(
                Finding(
                    MISE_CONFIG_PATH,
                    f'{tool} = "{spec}"',
                    "浮動 pin です (マシン間で解決版がずれます。exact 指定にしてください)",
                )
            )
    return findings
