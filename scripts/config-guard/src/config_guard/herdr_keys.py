"""herdr の keybinding 設定 (config.toml) の不変条件を検査する。

herdr の previous_* / next_* は対で使われ、chord の最終キーが向きを表す
(left/up/[/h/k = 前へ、right/down/]/j/l = 次へ)。この対応が逆転していても herdr は
警告なく起動するため、実際に指で押すまで誰も気づかない。実例として previous_workspace に
"ctrl+shift+alt+]" が、next_workspace に "ctrl+shift+alt+[" が割り当たっており、同じ
config 内の cycle_pane_* とは逆向きになっていた。

同一 chord を 2 つのアクションへ割り当てると herdr は片方を無効化する。修飾キーは集合として
解釈されるため、綴りの順が違うだけの chord は同じ chord であり、目視では衝突に気づけない。

この 2 つは TOML を読めば静的に判定できるので、herdr の無い CI でも検査する。

アクション名の綴り違い (`next_agentt`) は `herdr server reload-config` では警告されず、
その binding が黙って存在しないことになる。これは herdr 自身の `herdr config check` が
未知のキーとして報告するので、herdr があるときはそれに config を検証させる。herdr は
chord の重複も報告し、その判定は静的な正規化より正確なので、herdr が走ったときは静的な
重複検査を回さない (二重に報告しない)。向きの逆転は herdr が検証しないので常に回す。
"""

from __future__ import annotations

import os
import subprocess
import tomllib
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from config_guard.models import Finding

CONFIG_PATH = "home/.config/herdr/config.toml"

# `herdr config check` が問題なしのときの出力 (rc 0)
_CONFIG_CHECK_OK = "config: ok"
# `herdr config check` が問題を見つけたときの 1 行目 (rc 1)。2 行目以降が診断になる
_CONFIG_CHECK_ISSUES_HEADER = "config: issues found"
_CONFIG_CHECK_LABEL = "herdr config check"

# config のパスを受け取り `herdr config check` の結果を返す。herdr が無ければ None
ConfigChecker = Callable[[Path], subprocess.CompletedProcess[str] | None]

# parse_bindings が [[keys.command]] へ与える合成ラベルの接頭辞。アクション名ではない。
_COMMAND_LABEL_PREFIX = "keys.command["

# prefix は prefix モードの入口キー、indexed は 1..9 の一括割当、command は
# [[keys.command]] のテーブル配列。いずれも「アクション名 -> chord」の形をしていない。
_NON_ACTION_KEYS = frozenset({"prefix", "indexed", "command"})

# chord の最終キーが表す向き。修飾キー (ctrl/shift/alt/prefix) は向きを持たないため見ない。
# p/n/tab のように向きを持たないキーは判定対象外とし、false positive を出さない。
BACKWARD_KEYS = frozenset({"left", "up", "[", "h", "k"})
FORWARD_KEYS = frozenset({"right", "down", "]", "j", "l"})

# prefix モードの標識。修飾キーと違い先頭固定で、"shift+prefix+p" は herdr に拒否される。
_PREFIX_TOKEN = "prefix"

# herdr が chord を正規化するときの修飾キーの順。この順で綴らなくても herdr は同じ chord として
# 扱い、diagnostics ではこの順で報告する。cmd/super の位置は未確認なので後ろへ辞書順で回し、
# 正規化の決定性だけを担保する (順序を誤っても重複判定の結果は変わらない)。
_MODIFIER_ORDER = ("ctrl", "alt", "shift")

# アクション名に含まれる向きの語。cycle_pane_next / previous_workspace の双方に効く。
_BACKWARD = "previous"
_FORWARD = "next"

# `herdr config check` の待ち時間。実運用の herdr は検査済みなので即座に応答するが、
# テストが chmod +x したばかりの fake を起動すると macOS の初回検査で待たされ、混み合うと
# この値を超える (実測: 同一プロセス内で 8 秒 -> 10 秒超 -> 1.6 秒 -> 0.1 秒)。テスト側から
# 緩められるよう定数へ出してある。実運用側の値としては、pre-commit が毎回引くので短く保つ。
_SUBPROCESS_TIMEOUT_SECONDS = 10


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


def run_config_check(config: Path) -> subprocess.CompletedProcess[str] | None:
    """config を `herdr config check` で検証する。herdr が無い/起動できない/時間切れなら None。

    副作用をここへ隔離し、結果の解釈は呼び出し側が持つ (テストは hermetic に、
    herdr の無い CI ではこの検査だけが自動的に skip される)。
    """
    try:
        return subprocess.run(
            ["herdr", "config", "check"],
            capture_output=True,
            text=True,
            check=False,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            env=os.environ | {"HERDR_CONFIG_PATH": str(config)},
        )
    except (OSError, subprocess.SubprocessError):
        return None


def _config_check_findings(result: subprocess.CompletedProcess[str] | None) -> list[Finding]:
    """`herdr config check` の結果を Finding にする。想定外の形は問題なしへ倒さず報告する。"""
    if result is None:
        return []
    stdout = result.stdout.strip()
    if result.returncode == 0 and stdout == _CONFIG_CHECK_OK:
        return []

    header, _, diagnostics = stdout.partition("\n")
    lines = [line.strip() for line in diagnostics.splitlines() if line.strip()]
    if result.returncode == 1 and header == _CONFIG_CHECK_ISSUES_HEADER and lines:
        message = "herdr が config の問題を報告しました: " + " / ".join(lines)
    else:
        message = f"herdr config check の結果を解釈できません (rc={result.returncode}): " + (
            stdout or result.stderr.strip()
        )
    return [Finding(CONFIG_PATH, _CONFIG_CHECK_LABEL, message)]


def _parse_chord(chord: str) -> tuple[list[str], str]:
    """chord を (小文字の修飾キー列, 小文字の最終キー) へ分解する。空の chord は ([], "")。

    herdr は "+" 自体を plus と綴るので単純分割で足りる。複数文字のキー名は大文字小文字を
    区別しないが、1 文字の大文字キーは shift+小文字 と同じ chord になる (記号は shift の
    有無で別の chord のまま。0.9.5 で実測)。
    """
    tokens = [token for token in (part.strip() for part in chord.split("+")) if token]
    if not tokens:
        return [], ""

    raw_key = tokens[-1]
    modifiers = [token.lower() for token in tokens[:-1]]
    if len(raw_key) == 1 and raw_key.isupper():
        modifiers.append("shift")
    return modifiers, raw_key.lower()


def _final_key(chord: str) -> str:
    """chord の最終キーを取り出す。"""
    return _parse_chord(chord)[1]


def _normalize_chord(chord: str) -> str:
    """herdr が同一視する chord を 1 つの綴りへ畳む。

    修飾キーの並び順と綴りの大小だけが違う chord は herdr にとって同じ chord なので、
    重複検出は正規形をキーにしないと衝突を取りこぼす。
    """
    modifiers, key = _parse_chord(chord)
    if not key:
        return ""

    lead = []
    if modifiers[:1] == [_PREFIX_TOKEN]:
        lead, modifiers = [_PREFIX_TOKEN], modifiers[1:]

    known = [modifier for modifier in _MODIFIER_ORDER if modifier in modifiers]
    unknown = sorted(set(modifiers) - set(_MODIFIER_ORDER))
    return "+".join([*lead, *known, *unknown, key])


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

    綴りの揺れを吸収するため正規形でグルーピングし、報告には元の綴りを添える
    (どの行を直せばよいかが config を開かずに分かるように)。
    """
    owners: dict[str, list[Binding]] = defaultdict(list)
    for binding in bindings:
        owners[_normalize_chord(binding.chord)].append(binding)

    return [
        Finding(
            CONFIG_PATH,
            chord,
            "同一 chord が複数のアクションに割り当てられています: "
            + ", ".join(
                f"{owner.action} = {owner.chord}"
                for owner in sorted(owners_, key=lambda owner: (owner.action, owner.chord))
            ),
        )
        for chord, owners_ in owners.items()
        if len(owners_) > 1
    ]


def check_herdr_keys(repo_root: str, config_checker: ConfigChecker | None = None) -> list[Finding]:
    """herdr の config.toml を検査する。config が無い場合は検査対象なしで空を返す。

    config_checker が渡された場合のみ herdr 自身にも config を検証させる。config の有無は
    ここで先に確かめる (herdr は存在しないパスでも `config: ok` を返す)。
    """
    config = Path(repo_root) / CONFIG_PATH
    if not config.is_file():
        return []

    result = config_checker(config) if config_checker is not None else None
    herdr_findings = _config_check_findings(result)
    try:
        bindings = parse_bindings(config.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        # herdr が構文エラーを行と列つきで報告していればそれだけを返す。herdr が無いか
        # 受け入れた場合も、静的な検査が何も見ていないことは告げる
        return herdr_findings or [
            Finding(CONFIG_PATH, "TOML", f"config を TOML として読めません: {error}")
        ]

    findings = _check_directions(bindings)
    if result is None:
        findings += _check_duplicates(bindings)
    return findings + herdr_findings
