"""herdr_app_keys の仕様テスト。

keys.json の静的な検査 (JSON の構文とキーの重複) と、herdr-app の一覧に照らす検査
(アクションの解決と mod.open の宛先)、一覧の取得 (副作用) を検証する。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from config_guard import herdr_app_keys
from config_guard.herdr_app_keys import (
    KEYS_PATH,
    MODS_DIR,
    AppInventory,
    check_herdr_app_keys,
    read_app_inventory,
)
from tests.conftest import write_fake_binary

# 組み込みコマンドの一覧の一部。実物は `herdr-app commands` が返す
COMMANDS = frozenset({"tab.next", "pane.go", "mod.open", "layout.toggle", "terminal.copy"})


def _write_keys(repo: Path, text: str) -> None:
    path = repo / KEYS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_bindings(repo: Path, bindings: dict[str, dict[str, str]]) -> None:
    _write_keys(repo, json.dumps(bindings))


def _track_mod(repo: Path, name: str) -> None:
    (repo / MODS_DIR / name).mkdir(parents=True)


def _inventory(mods: frozenset[str] = frozenset()) -> AppInventory:
    return AppInventory(commands=COMMANDS, mods=mods)


# ---------------------------------------------------------------------------
# 静的な検査 (herdr-app が無くても走る)
# ---------------------------------------------------------------------------


def test_check_empty_when_no_keys_file(tmp_path: Path) -> None:
    assert check_herdr_app_keys(str(tmp_path), lambda: _inventory()) == []


def test_check_passes_on_valid_keys(tmp_path: Path) -> None:
    _track_mod(tmp_path, "unread")
    _write_bindings(
        tmp_path,
        {
            "global": {"cmd-u": "mod.open:unread", "alt-tab": "tab.next"},
            "terminal": {
                "cmd-c": "terminal.copy",
                "alt-left": "send:\u001bb",
                "ctrl-1": "terminal",
            },
        },
    )

    assert check_herdr_app_keys(str(tmp_path), lambda: _inventory()) == []


def test_check_reports_unparsable_json(tmp_path: Path) -> None:
    _write_keys(tmp_path, '{"global": {"cmd-u": "tab.next",}}')

    findings = check_herdr_app_keys(str(tmp_path))

    assert [(f.source, f.detail) for f in findings] == [(KEYS_PATH, "JSON")]


def test_check_reports_duplicate_key_within_a_section(tmp_path: Path) -> None:
    # JSON の重複キーは読み手が黙って後勝ちにするので、前の割り当てが消えたことに気づけない
    _write_keys(tmp_path, '{"global": {"cmd-u": "tab.next", "cmd-u": "pane.go:left"}}')

    findings = check_herdr_app_keys(str(tmp_path))

    assert [f.detail for f in findings] == ["global.cmd-u"]


def test_check_allows_same_key_in_different_sections(tmp_path: Path) -> None:
    # セクションが違えば別の割り当て (より具体的なセクションが勝つ) なので重複ではない
    _write_keys(tmp_path, '{"global": {"cmd-u": "tab.next"}, "terminal": {"cmd-u": "tab.next"}}')

    assert check_herdr_app_keys(str(tmp_path)) == []


def test_check_reports_duplicate_section(tmp_path: Path) -> None:
    _write_keys(tmp_path, '{"global": {"cmd-u": "tab.next"}, "global": {"cmd-d": "tab.next"}}')

    assert [f.detail for f in check_herdr_app_keys(str(tmp_path))] == ["global"]


@pytest.mark.parametrize(
    "text", ['["global"]', '{"global": ["cmd-u"]}', '{"global": {"cmd-u": 1}}']
)
def test_check_reports_unexpected_shape(tmp_path: Path, text: str) -> None:
    # 最上位はセクションのオブジェクト、各セクションはキーから文字列への対応でなければならない
    _write_keys(tmp_path, text)

    findings = check_herdr_app_keys(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].source == KEYS_PATH


# ---------------------------------------------------------------------------
# herdr-app の一覧に照らす検査
# ---------------------------------------------------------------------------


def test_check_skips_app_checks_without_reader(tmp_path: Path) -> None:
    _write_bindings(tmp_path, {"global": {"cmd-u": "no.such.command"}})

    assert check_herdr_app_keys(str(tmp_path)) == []


def test_check_skips_app_checks_when_app_is_absent(tmp_path: Path) -> None:
    _write_bindings(tmp_path, {"global": {"cmd-u": "no.such.command"}})

    assert check_herdr_app_keys(str(tmp_path), lambda: None) == []


def test_check_reports_unknown_action(tmp_path: Path) -> None:
    # herdr-app は未知のアクション名を keys.error にも status にも出さず、キーが黙って死ぬ
    _write_bindings(tmp_path, {"global": {"cmd-u": "tab.nxet"}})

    findings = check_herdr_app_keys(str(tmp_path), lambda: _inventory())

    assert [(f.source, f.detail) for f in findings] == [(KEYS_PATH, "global.cmd-u = tab.nxet")]


def test_check_reports_mod_command_form(tmp_path: Path) -> None:
    # `<mod>.<command>` の形は先頭が mod 名と一致すると typo でも妥当に見える (shipped の
    # pane mod があるので pane.nosuchcmd も通ってしまう)。使っていないので組み込みだけに絞る
    _track_mod(tmp_path, "pane")
    _write_bindings(tmp_path, {"global": {"cmd-u": "pane.nosuchcmd"}})

    findings = check_herdr_app_keys(str(tmp_path), lambda: _inventory(frozenset({"pane"})))

    assert [f.detail for f in findings] == ["global.cmd-u = pane.nosuchcmd"]


def test_check_reports_value_on_unknown_command_once(tmp_path: Path) -> None:
    # 値付きの形は値を除いたコマンド名で引く。値の側で二重に報告しない
    _write_bindings(tmp_path, {"global": {"cmd-u": "pane.og:left"}})

    assert len(check_herdr_app_keys(str(tmp_path), lambda: _inventory())) == 1


def test_check_reports_mod_open_to_missing_mod(tmp_path: Path) -> None:
    _write_bindings(tmp_path, {"global": {"cmd-u": "mod.open:unraed"}})

    findings = check_herdr_app_keys(str(tmp_path), lambda: _inventory())

    assert [f.detail for f in findings] == ["global.cmd-u = mod.open:unraed"]


def test_check_accepts_mod_open_to_live_mod(tmp_path: Path) -> None:
    # shipped の mod (picker など) は追跡下に無く、live の mods/ にだけある
    _write_bindings(tmp_path, {"global": {"cmd-p": "mod.open:picker"}})

    assert check_herdr_app_keys(str(tmp_path), lambda: _inventory(frozenset({"picker"}))) == []


def test_check_accepts_mod_open_to_tracked_mod(tmp_path: Path) -> None:
    # 追跡下の mod は bootstrap が配るまで live に無いことがある
    _track_mod(tmp_path, "unread")
    _write_bindings(tmp_path, {"global": {"cmd-u": "mod.open:unread"}})

    assert check_herdr_app_keys(str(tmp_path), lambda: _inventory()) == []


def test_check_reports_mod_open_without_name(tmp_path: Path) -> None:
    _write_bindings(tmp_path, {"global": {"cmd-u": "mod.open"}})

    assert len(check_herdr_app_keys(str(tmp_path), lambda: _inventory())) == 1


def test_check_reports_inventory_error(tmp_path: Path) -> None:
    # 一覧を解釈できないときは問題なしへ倒さず、検査できなかったことを告げる
    _write_bindings(tmp_path, {"global": {"cmd-u": "tab.next"}})

    def broken() -> AppInventory | None:
        raise herdr_app_keys.AppInventoryError("unexpected output")

    findings = check_herdr_app_keys(str(tmp_path), broken)

    assert [f.detail for f in findings] == ["herdr-app commands"]
    assert "unexpected output" in findings[0].message


def test_check_runs_static_checks_alongside_app_checks(tmp_path: Path) -> None:
    _write_keys(tmp_path, '{"global": {"cmd-u": "tab.nxet", "cmd-u": "tab.next"}}')

    details = {f.detail for f in check_herdr_app_keys(str(tmp_path), lambda: _inventory())}

    # 重複は後勝ちで読まれる側 (tab.next) を残すので、消えた側の typo は報告されない
    assert details == {"global.cmd-u"}


# ---------------------------------------------------------------------------
# read_app_inventory (副作用)
# ---------------------------------------------------------------------------


def _fake_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> Path:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    write_fake_binary(bin_dir, "herdr-app", body)
    monkeypatch.setattr(herdr_app_keys, "_SUBPROCESS_TIMEOUT_SECONDS", 120)
    monkeypatch.setenv("PATH", str(bin_dir))
    home = tmp_path / "app-home"
    (home / "mods" / "picker").mkdir(parents=True)
    (home / "mods" / "stray-file").parent.mkdir(exist_ok=True)
    (home / "mods" / "stray-file").write_text("", encoding="utf-8")
    monkeypatch.setenv("HERDR_APP_HOME", str(home))
    return home


def test_read_inventory_returns_none_without_app(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    assert read_app_inventory() is None


def test_read_inventory_lists_commands_and_live_mods(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _fake_app(tmp_path, monkeypatch, """printf '[{"name":"tab.next","args":[]}]'""")

    inventory = read_app_inventory()

    # mods/ 直下のディレクトリだけが mod で、ファイルは数えない
    assert inventory == AppInventory(commands=frozenset({"tab.next"}), mods=frozenset({"picker"}))


def test_read_inventory_without_mods_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    home = _fake_app(tmp_path, monkeypatch, """printf '[{"name":"tab.next"}]'""")
    shutil.rmtree(home / "mods")

    inventory = read_app_inventory()

    assert inventory is not None
    assert inventory.mods == frozenset()


@pytest.mark.parametrize(
    "body",
    [
        "printf 'not json'",
        "printf '{}'",
        # 空の一覧を受け入れると、照合が全アクションを未知として報告する
        "printf '[]'",
        'printf \'[{"about":"x"}]\'',
        # 出力が妥当でも rc が非 0 なら信用しない (後段の検査に吸収されないよう妥当な出力にする)
        'printf \'[{"name":"tab.next"}]\'\nexit 1',
    ],
)
def test_read_inventory_raises_on_uninterpretable_output(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, body: str
) -> None:
    _fake_app(tmp_path, monkeypatch, body)

    with pytest.raises(herdr_app_keys.AppInventoryError):
        read_app_inventory()


def test_read_inventory_returns_none_on_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sleep = shutil.which("sleep")
    assert sleep is not None
    _fake_app(tmp_path, monkeypatch, f"{sleep} 5")
    monkeypatch.setattr(herdr_app_keys, "_SUBPROCESS_TIMEOUT_SECONDS", 0.001)

    assert read_app_inventory() is None


requires_app = pytest.mark.skipif(shutil.which("herdr-app") is None, reason="herdr-app が無い")


@requires_app
def test_live_inventory_knows_builtin_commands() -> None:
    inventory = read_app_inventory()

    assert inventory is not None
    assert {"tab.next", "mod.open", "pane.go"} <= inventory.commands
