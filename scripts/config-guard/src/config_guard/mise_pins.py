"""mise の global ツール pin が exact 指定であることを検査する。

home/.config/mise/config.toml は「exact 指定で全マシンを完全再現する」規約を持つが、
規約はコメントにしか書かれておらず何も強制していなかったため、`just = "latest"` が
素通りした実績がある。浮動 pin はマシンごとに解決版が変わり、config を symlink して
いても再現性が崩れる(しかも壊れるまで気づけない)ので、ここで機械的に弾く。

「exact とは何か」の canonical な定義はこのモジュールの EXACT_VERSION_PATTERN 一箇所に
置き、config.toml 側のコメントには literal を再掲しない(二重記述は drift する)。
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from config_guard.models import Finding

MISE_CONFIG_PATH = "home/.config/mise/config.toml"

# major.minor.patch と任意の prerelease のみを exact と見なす。部分指定 ("1", "1.56") は
# mise が「その系列の最新」に解決する浮動 pin なので弾く。
EXACT_VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$")


def is_exact_version(spec: str) -> bool:
    """version 指定が版を一意に固定するか判定する。"""
    return EXACT_VERSION_PATTERN.fullmatch(spec) is not None


def check_mise_pins(repo_root: str) -> list[Finding]:
    """mise config の [tools] が全て exact 指定か検査する。

    config が無い(mise 未使用)場合は検査対象なしで空を返す。
    """
    config_path = Path(repo_root) / MISE_CONFIG_PATH
    if not config_path.is_file():
        return []

    with config_path.open("rb") as handle:
        config = tomllib.load(handle)

    tools = config.get("tools", {})
    findings: list[Finding] = []
    for tool, spec in sorted(tools.items()):
        # 複数版指定 (list) やテーブル指定は「exact でない」ではなく「この guard では
        # 判定できない」形。素通りさせると false negative になるので明示的に検出する。
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
