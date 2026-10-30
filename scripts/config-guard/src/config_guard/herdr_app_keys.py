"""herdr-app の keybinding 設定 (keys.json) の不変条件を検査する。

herdr-app は keys.json の不正な chord と未知のセクションを keys.error に書いて適用を止めるが、
存在しないアクション名は黙って受け入れる。keys.error にも `herdr-app status` にも出ず、そのキーを
押しても何も起きないので、指で押すまで誰も気づかない (2026-10-30 実測)。

アクションの形のうち `<mod>.<command>` は、先頭が mod 名と一致すると綴り違いでも妥当に見える
(shipped の pane mod があるので `pane.nosuchcmd` が通る)。このリポジトリはこの形を使わないので、
アクションは組み込みコマンドに解決するものだけを許す。`mod.open:<name>` は宛先の mod が
在るかまで見る。組み込みコマンドの一覧と shipped の mod は herdr-app が持つので、この 2 つは
herdr-app がある環境でだけ検査する (CI には無いので skip される)。

JSON の構文とキーの重複はファイルだけで判定できるので、どこでも検査する。同じセクションに
同じキーを 2 度書くと読み手は黙って後勝ちにするので、前の割り当てが消えたことに気づけない。
"""

from __future__ import annotations

import json
import os
import subprocess
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from config_guard.models import Finding

KEYS_PATH = "home/.config/herdr-app/keys.json"
MODS_DIR = "home/.config/herdr-app/mods"

# 組み込みコマンドを経由しない 2 つの形。send: は端末へ文字を送り、terminal はキーを
# 端末のプログラムへ渡す (どちらも `herdr-app commands` の一覧には現れない)
_SEND_PREFIX = "send:"
_TERMINAL_ACTION = "terminal"
_MOD_OPEN = "mod.open"
_INVENTORY_LABEL = "herdr-app commands"

# `herdr-app commands` の待ち時間。実物は窓が無くても即座に返すが、テストが chmod +x した
# ばかりの fake を起動すると macOS の初回検査で待たされうるので、テスト側から緩められるよう
# 定数へ出してある。pre-commit が毎回引くので実運用側の値は短く保つ。
_SUBPROCESS_TIMEOUT_SECONDS = 10


class AppInventoryError(Exception):
    """herdr-app は起動できたが、その一覧を解釈できなかった。"""


@dataclass(frozen=True)
class AppInventory:
    """herdr-app が知っている組み込みコマンドの名前と、live の mods/ にある mod の名前。"""

    commands: frozenset[str]
    mods: frozenset[str]


# 一覧を返す。herdr-app が無い/起動できない/時間切れなら None
InventoryReader = Callable[[], AppInventory | None]


class _Pairs(list[tuple[str, object]]):
    """object_pairs_hook で読んだ JSON オブジェクト。重複を残したまま (キー, 値) の列を持つ。

    素の list にすると JSON の配列と見分けられないので型を分ける。
    """


def _app_home() -> Path:
    """herdr-app のホーム。HERDR_APP_HOME が別のホームを選ぶ (herdr-app と同じ規則)。"""
    configured = os.environ.get("HERDR_APP_HOME")
    return Path(configured) if configured else Path.home() / ".config" / "herdr-app"


def _mod_names(mods_dir: Path) -> frozenset[str]:
    """mods/ 直下のディレクトリ名。mod はフォルダ単位なのでファイルは数えない。"""
    if not mods_dir.is_dir():
        return frozenset()
    return frozenset(entry.name for entry in mods_dir.iterdir() if entry.is_dir())


def _parse_commands(stdout: str) -> frozenset[str]:
    try:
        entries = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise AppInventoryError(f"JSON として読めません: {error}") from error
    if not isinstance(entries, list) or not entries:
        raise AppInventoryError("コマンドの配列ではありません")
    names = [entry.get("name") if isinstance(entry, dict) else None for entry in entries]
    if not all(isinstance(name, str) for name in names):
        raise AppInventoryError("name を持たない要素があります")
    return frozenset(name for name in names if isinstance(name, str))


def read_app_inventory() -> AppInventory | None:
    """`herdr-app commands` と live の mods/ から一覧を作る。

    副作用をここへ隔離し、照合は呼び出し側が持つ (テストは hermetic に、herdr-app の無い
    CI ではこの検査だけが自動的に skip される)。起動できたのに出力を解釈できないときは
    問題なしへ倒さず AppInventoryError を投げる。
    """
    try:
        result = subprocess.run(
            ["herdr-app", "commands"],
            capture_output=True,
            text=True,
            check=False,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        raise AppInventoryError(f"rc={result.returncode}: {result.stderr.strip()}")

    return AppInventory(
        commands=_parse_commands(result.stdout), mods=_mod_names(_app_home() / "mods")
    )


def _duplicates(pairs: _Pairs, prefix: str) -> list[Finding]:
    counts = Counter(key for key, _ in pairs)
    return [
        Finding(
            KEYS_PATH, f"{prefix}{key}", "同じキーが 2 度以上書かれ、前の値が黙って捨てられます"
        )
        for key, count in counts.items()
        if count > 1
    ]


def _parse_keys(text: str) -> tuple[dict[str, dict[str, str]], list[Finding]]:
    """keys.json を (セクション -> キー -> アクション, 形の問題) へ分解する。

    重複は後勝ちで畳み、読み手 (herdr-app) が実際に使う側を残す。
    """
    try:
        document = json.loads(text, object_pairs_hook=_Pairs)
    except json.JSONDecodeError as error:
        return {}, [Finding(KEYS_PATH, "JSON", f"keys.json を JSON として読めません: {error}")]
    if not isinstance(document, _Pairs):
        return {}, [Finding(KEYS_PATH, "JSON", "最上位がセクションのオブジェクトではありません")]

    findings = _duplicates(document, "")
    sections: dict[str, dict[str, str]] = {}
    for section, body in document:
        if not isinstance(body, _Pairs) or not all(isinstance(value, str) for _, value in body):
            findings.append(
                Finding(
                    KEYS_PATH, section, "セクションはキーから文字列への対応でなければなりません"
                )
            )
            continue
        findings.extend(_duplicates(body, f"{section}."))
        sections[section] = {key: str(value) for key, value in body}
    return sections, findings


def _action_problem(
    action: str, inventory: AppInventory, tracked_mods: frozenset[str]
) -> str | None:
    """アクションが解決しない理由。解決するなら None。"""
    if action == _TERMINAL_ACTION or action.startswith(_SEND_PREFIX):
        return None
    name, _, value = action.partition(":")
    if name not in inventory.commands:
        return f"{name} は herdr-app の組み込みコマンドではありません"
    if name == _MOD_OPEN and value not in tracked_mods | inventory.mods:
        return f"mod {value!r} が追跡下の {MODS_DIR} にも live の mods/ にもありません"
    return None


def check_herdr_app_keys(
    repo_root: str, inventory_reader: InventoryReader | None = None
) -> list[Finding]:
    """keys.json を検査する。keys.json が無い場合は検査対象なしで空を返す。

    inventory_reader が渡され、一覧が取れた場合だけアクションの解決を検査する。
    """
    root = Path(repo_root)
    keys = root / KEYS_PATH
    if not keys.is_file():
        return []

    sections, findings = _parse_keys(keys.read_text(encoding="utf-8"))
    if inventory_reader is None:
        return findings
    try:
        inventory = inventory_reader()
    except AppInventoryError as error:
        return [*findings, Finding(KEYS_PATH, _INVENTORY_LABEL, f"一覧を解釈できません: {error}")]
    if inventory is None:
        return findings

    tracked_mods = _mod_names(root / MODS_DIR)
    for section, bindings in sections.items():
        for key, action in bindings.items():
            problem = _action_problem(action, inventory, tracked_mods)
            if problem is not None:
                findings.append(Finding(KEYS_PATH, f"{section}.{key} = {action}", problem))
    return findings
