"""herdr の keybinding 設定 (config.toml) の不変条件を検査する。

herdr の previous_* / next_* は対で使われ、chord の最終キーが向きを表す
(left/up/[/h/k = 前へ、right/down/]/j/l = 次へ)。この対応が逆転していても herdr は
警告なく起動するため、実際に指で押すまで誰も気づかない。実例として previous_workspace に
"ctrl+shift+alt+]" が、next_workspace に "ctrl+shift+alt+[" が割り当たっており、同じ
config 内の cycle_pane_* とは逆向きになっていた。

同一 chord を 2 つのアクションへ割り当てた場合も、herdr は黙って片方だけを効かせる。

さらに herdr は未知のアクション名を検証しない。実測 (2026-07-09) では不正な chord は
`herdr server reload-config` が `status: partial` と diagnostics で報告するが、
`next_agentt = "prefix+shift+j"` のような綴り違いは `status: applied` / `diagnostics: []` で
受理され、その binding は警告なく存在しないことになる。正当なアクション名の一覧は
`herdr --default-config` が唯一の真実源なので、それを引けるときだけ照合する
(herdr が無い CI ではこの検査だけを skip する)。

いずれも TOML を読めば静的に判定できる。プロンプトでの注意喚起ではなく guard で機械検査する。
"""

from __future__ import annotations

import subprocess
import tomllib
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from config_guard.models import Finding

CONFIG_PATH = "home/.config/herdr/config.toml"

# `herdr --default-config` の [keys] テーブル。この見出しから次のテーブルまでが探索範囲。
_KEYS_TABLE_HEADER = "[keys]"

# parse_bindings が [[keys.command]] へ与える合成ラベルの接頭辞。アクション名ではない。
_COMMAND_LABEL_PREFIX = "keys.command["

# prefix は prefix モードの入口キー、indexed は 1..9 の一括割当、command は
# [[keys.command]] のテーブル配列。いずれも「アクション名 -> chord」の形をしていない。
_NON_ACTION_KEYS = frozenset({"prefix", "indexed", "command"})

# chord の最終キーが表す向き。修飾キー (ctrl/shift/alt/prefix) は向きを持たないため見ない。
# p/n/tab のように向きを持たないキーは判定対象外とし、false positive を出さない。
BACKWARD_KEYS = frozenset({"left", "up", "[", "h", "k"})
FORWARD_KEYS = frozenset({"right", "down", "]", "j", "l"})

# アクション名に含まれる向きの語。cycle_pane_next / previous_workspace の双方に効く。
_BACKWARD = "previous"
_FORWARD = "next"


@dataclass(frozen=True)
class Binding:
    """1 つのアクションに割り当てられた 1 つの chord。"""

    action: str
    chord: str


def _iter_chords(value: object) -> list[str]:
    """binding の値 (文字列 or 文字列配列) を chord のリストへ正規化する。"""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, str)]
    return []


def parse_bindings(config_text: str) -> list[Binding]:
    """config.toml の [keys] から (アクション, chord) の一覧を取り出す。

    未割り当てを表す "" は binding として数えない。[[keys.command]] には keys.command[i]
    という合成ラベルを与える (command のパス文字列をラベルにすると "next" 等を含むパスが
    方向判定へ紛れ込むため)。
    """
    keys = tomllib.loads(config_text).get("keys")
    if not isinstance(keys, dict):
        return []

    bindings: list[Binding] = []
    for action, value in keys.items():
        if action in _NON_ACTION_KEYS:
            continue
        bindings.extend(Binding(action, chord) for chord in _iter_chords(value) if chord)

    commands = keys.get("command")
    if isinstance(commands, list):
        for index, entry in enumerate(commands):
            if not isinstance(entry, dict):
                continue
            chord = entry.get("key")
            if isinstance(chord, str) and chord:
                bindings.append(Binding(f"{_COMMAND_LABEL_PREFIX}{index}]", chord))

    return bindings


def _uncomment(line: str) -> str:
    stripped = line.strip()
    return stripped[1:].strip() if stripped.startswith("#") else stripped


def known_action_names(default_config_text: str) -> set[str]:
    """`herdr --default-config` の [keys] ブロックから正当なアクション名を取り出す。

    既定値は全てコメントアウトされて出力されるため TOML パーサからは見えない。そこで
    コメントを外した行を 1 行ずつ tomllib に食わせ、TOML として成立する行だけを採用する。
    これにより `# type = "shell" runs detached in the background.` のような散文コメント
    (「名前 = 値」に見えるが値の後ろに散文が続き TOML として不正) を、自作の正規表現ではなく
    パーサ自身に排除させ、phantom entry の混入を防ぐ。
    """
    names: set[str] = set()
    in_keys_table = False
    for raw in default_config_text.splitlines():
        content = _uncomment(raw)
        if content == _KEYS_TABLE_HEADER:
            in_keys_table = True
            continue
        if not in_keys_table:
            continue
        # [keys.indexed] / [[keys.command]] などの下位テーブルはアクションの表ではない
        if content.startswith("["):
            break
        if "=" not in content:
            continue
        try:
            parsed = tomllib.loads(content)
        except tomllib.TOMLDecodeError:
            continue
        names.update(parsed.keys())
    return names - _NON_ACTION_KEYS


def read_default_config() -> str | None:
    """`herdr --default-config` を引く。herdr が無い/失敗した場合は None を返す。

    副作用をここへ隔離し、check_herdr_keys は渡されたテキストだけを見る (テストは hermetic に、
    herdr の無い CI ではアクション名検査だけが自動的に skip される)。
    """
    try:
        proc = subprocess.run(
            ["herdr", "--default-config"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def _final_key(chord: str) -> str:
    """chord の最終キーを取り出す。herdr は "+" 自体を plus と綴るので単純分割で足りる。"""
    return chord.split("+")[-1].strip().lower()


def _action_direction(action: str) -> str | None:
    if _BACKWARD in action:
        return _BACKWARD
    if _FORWARD in action:
        return _FORWARD
    return None


def _chord_direction(chord: str) -> str | None:
    key = _final_key(chord)
    if key in BACKWARD_KEYS:
        return _BACKWARD
    if key in FORWARD_KEYS:
        return _FORWARD
    return None


def _check_directions(bindings: list[Binding]) -> list[Finding]:
    """previous_* / next_* に逆向きのキーが割り当てられていないか検査する。"""
    findings: list[Finding] = []
    for binding in bindings:
        expected = _action_direction(binding.action)
        if expected is None:
            continue
        actual = _chord_direction(binding.chord)
        if actual is None or actual == expected:
            continue
        findings.append(
            Finding(
                CONFIG_PATH,
                f"{binding.action} = {binding.chord}",
                f"{expected} 方向のアクションに {actual} 方向のキーが割り当てられています "
                f"(最終キー: {_final_key(binding.chord)})",
            )
        )
    return findings


def _check_duplicates(bindings: list[Binding]) -> list[Finding]:
    """同一 chord が複数のアクションへ割り当てられていないか検査する。

    修飾キーの並び順は正規化しない (herdr 側の綴りに合わせる前提)。大文字小文字のみ吸収する。
    """
    owners: dict[str, list[str]] = defaultdict(list)
    for binding in bindings:
        owners[binding.chord.strip().lower()].append(binding.action)

    return [
        Finding(
            CONFIG_PATH,
            chord,
            f"同一 chord が複数のアクションに割り当てられています: {', '.join(sorted(actions))}",
        )
        for chord, actions in owners.items()
        if len(actions) > 1
    ]


def _check_unknown_actions(bindings: list[Binding], known: set[str]) -> list[Finding]:
    """herdr が認識しないアクション名が使われていないか検査する。"""
    findings: list[Finding] = []
    reported: set[str] = set()
    for binding in bindings:
        action = binding.action
        if action.startswith(_COMMAND_LABEL_PREFIX) or action in known or action in reported:
            continue
        reported.add(action)
        findings.append(
            Finding(
                CONFIG_PATH,
                action,
                "herdr が認識しないアクション名です "
                "(herdr は typo を警告せず受理し binding は無効化されます)",
            )
        )
    return findings


def check_herdr_keys(repo_root: str, default_config_text: str | None = None) -> list[Finding]:
    """herdr の config.toml を検査する。config が無い場合は検査対象なしで空を返す。

    default_config_text (`herdr --default-config` の出力) が渡された場合のみ、アクション名が
    herdr の知る名前かどうかも照合する。
    """
    config = Path(repo_root) / CONFIG_PATH
    if not config.is_file():
        return []

    bindings = parse_bindings(config.read_text(encoding="utf-8"))
    findings = _check_directions(bindings) + _check_duplicates(bindings)
    if default_config_text is not None:
        findings.extend(_check_unknown_actions(bindings, known_action_names(default_config_text)))
    return findings
