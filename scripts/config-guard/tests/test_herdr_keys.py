"""herdr_keys の仕様テスト。

binding パーサ(pure)と、方向整合 / chord 重複の検査(実ファイル)を検証する。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from config_guard.herdr_keys import (
    CONFIG_PATH,
    Binding,
    check_herdr_keys,
    known_action_names,
    parse_bindings,
    read_default_config,
)

# `herdr --default-config` の [keys] ブロックを模した抜粋。
# 既定値は全てコメントアウトされて出力される点と、`type = ...` の prose コメントが
# 「名前 = 値」の形をしている点(phantom entry の罠)を再現する。
DEFAULT_CONFIG_EXCERPT = """[theme]
name = "catppuccin"

[keys]
# Prefix key to enter prefix mode (default: "ctrl+b")
# prefix = "ctrl+b"

# Prefix-mode actions
# previous_agent = ""     # optional, unset by default
# next_agent = ""         # optional, unset by default
# previous_workspace = "" # optional, unset by default
# next_workspace = ""     # optional, unset by default
# zoom = "prefix+z"       # legacy alias: fullscreen
# new_tab = "prefix+c"
# close_pane = "prefix+x"
# previous_tab = "prefix+p"
# next_tab = "prefix+n"
# cycle_pane_next = "prefix+tab"
# cycle_pane_previous = "prefix+shift+tab"
# focus_pane_left = "prefix+h"
# focus_pane_down = "prefix+j"
# focus_pane_up = "prefix+k"
# focus_pane_right = "prefix+l"

# Custom commands use the same binding syntax.
# type = "shell" runs detached in the background.
# type = "pane" opens a temporary pane and closes it when the command exits.
# [[keys.command]]
# key = "prefix+alt+g"
# command = "lazygit"

# [keys.indexed]
# tabs = ""
"""

# 方向キーを持つ対と、方向を持たない対(p/n, tab)を混ぜた最小 config
SAMPLE_CONFIG = """[keys]
prefix = "ctrl+b"
previous_workspace = ["prefix+shift+left", "ctrl+shift+alt+["]
next_workspace = ["prefix+shift+right", "ctrl+shift+alt+]"]
previous_tab = ["prefix+p", "shift+alt+tab"]
next_tab = ["prefix+n", "alt+tab"]
previous_agent = "prefix+shift+k"
next_agent = "prefix+shift+j"
focus_pane_left = "prefix+h"
focus_pane_down = "prefix+j"

[[keys.command]]
key = "prefix+shift+u"
type = "shell"
command = "~/.config/herdr/scripts/herdr-unread"
"""


def _write_config(repo: Path, text: str) -> None:
    path = repo / CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# parse_bindings (pure)
# ---------------------------------------------------------------------------


def test_parse_bindings_reads_scalar_and_list_values() -> None:
    bindings = parse_bindings(SAMPLE_CONFIG)

    assert Binding("previous_agent", "prefix+shift+k") in bindings
    # 配列は要素ごとに 1 binding へ展開される
    assert Binding("previous_workspace", "prefix+shift+left") in bindings
    assert Binding("previous_workspace", "ctrl+shift+alt+[") in bindings


def test_parse_bindings_excludes_prefix_and_command_metadata() -> None:
    actions = {b.action for b in parse_bindings(SAMPLE_CONFIG)}

    # prefix はアクションではなく prefix モードの入口キー
    assert "prefix" not in actions
    # [[keys.command]] の type / command は chord ではない
    assert "type" not in actions
    assert "command" not in actions


def test_parse_bindings_labels_command_entries_by_index() -> None:
    bindings = parse_bindings(SAMPLE_CONFIG)

    assert Binding("keys.command[0]", "prefix+shift+u") in bindings


def test_parse_bindings_ignores_empty_binding() -> None:
    # 既定の未割り当て表現 "" は binding として数えない
    bindings = parse_bindings('[keys]\nnext_agent = ""\nprevious_agent = ["", "prefix+shift+k"]\n')

    assert bindings == [Binding("previous_agent", "prefix+shift+k")]


def test_parse_bindings_empty_when_no_keys_table() -> None:
    assert parse_bindings('[theme]\nname = "one-dark"\n') == []


# ---------------------------------------------------------------------------
# check_herdr_keys (方向整合)
# ---------------------------------------------------------------------------


def test_check_passes_on_consistent_config(tmp_path: Path) -> None:
    _write_config(tmp_path, SAMPLE_CONFIG)

    assert check_herdr_keys(str(tmp_path)) == []


def test_check_flags_reversed_workspace_chords(tmp_path: Path) -> None:
    # 実際に踏んだ取り違え: previous に "]"、next に "[" が割り当たっている
    _write_config(
        tmp_path,
        """[keys]
previous_workspace = ["prefix+shift+left", "ctrl+shift+alt+]"]
next_workspace = ["prefix+shift+right", "ctrl+shift+alt+["]
cycle_pane_next = ["prefix+tab", "ctrl+alt+]"]
cycle_pane_previous = ["prefix+shift+tab", "ctrl+alt+["]
""",
    )

    findings = check_herdr_keys(str(tmp_path))

    details = {f.detail for f in findings}
    assert details == {
        "previous_workspace = ctrl+shift+alt+]",
        "next_workspace = ctrl+shift+alt+[",
    }
    # 向きの正しい prefix+shift+left / right と、pane 側の [ ] は検出されない(negative)
    assert not any("cycle_pane" in d for d in details)
    assert not any("shift+left" in d or "shift+right" in d for d in details)
    assert all(f.source == CONFIG_PATH for f in findings)


def test_check_flags_reversed_agent_chords(tmp_path: Path) -> None:
    # j/k は vim 方向として扱う: k=上=previous, j=下=next。逆なら検出する
    _write_config(
        tmp_path,
        '[keys]\nprevious_agent = "prefix+shift+j"\nnext_agent = "prefix+shift+k"\n',
    )

    details = {f.detail for f in check_herdr_keys(str(tmp_path))}

    assert details == {
        "previous_agent = prefix+shift+j",
        "next_agent = prefix+shift+k",
    }


def test_check_ignores_non_directional_keys(tmp_path: Path) -> None:
    # p/n/tab は方向を表さないので、対の向きを判定しない(false positive を出さない)
    _write_config(
        tmp_path,
        '[keys]\nprevious_tab = ["prefix+p", "shift+alt+tab"]\n'
        'next_tab = ["prefix+n", "alt+tab"]\n',
    )

    assert check_herdr_keys(str(tmp_path)) == []


def test_check_ignores_actions_without_direction_in_name(tmp_path: Path) -> None:
    # focus_pane_left は previous/next の対ではないので h/k/j/l を方向として咎めない
    _write_config(
        tmp_path,
        '[keys]\nfocus_pane_left = "prefix+h"\nfocus_pane_down = "prefix+j"\n'
        'focus_pane_up = "prefix+k"\nfocus_pane_right = "prefix+l"\n',
    )

    assert check_herdr_keys(str(tmp_path)) == []


def test_check_direction_message_names_expected_then_actual(tmp_path: Path) -> None:
    # previous のアクションに next 方向のキー
    _write_config(tmp_path, '[keys]\nprevious_agent = "prefix+shift+j"\n')

    (finding,) = check_herdr_keys(str(tmp_path))

    assert finding.message == (
        "previous 方向のアクションに next 方向のキーが割り当てられています (最終キー: j)"
    )


def test_check_direction_message_is_not_symmetric(tmp_path: Path) -> None:
    # 逆向きの取り違え。expected と actual を入れ替えた実装は上のテストと同じ文面を出すため、
    # 両方向を固定して初めて swap を捕捉できる (是正の向きを逆に案内する回帰の防止)
    _write_config(tmp_path, '[keys]\nnext_agent = "prefix+shift+k"\n')

    (finding,) = check_herdr_keys(str(tmp_path))

    assert finding.message == (
        "next 方向のアクションに previous 方向のキーが割り当てられています (最終キー: k)"
    )


# ---------------------------------------------------------------------------
# check_herdr_keys (chord 重複)
# ---------------------------------------------------------------------------


def test_check_flags_duplicate_chord_across_actions(tmp_path: Path) -> None:
    _write_config(tmp_path, '[keys]\nnew_tab = "prefix+c"\nclose_pane = "prefix+c"\n')

    findings = check_herdr_keys(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == "prefix+c"
    # どのアクションが衝突しているかがメッセージから分かること
    assert "close_pane" in findings[0].message
    assert "new_tab" in findings[0].message


def test_check_flags_duplicate_chord_between_action_and_command(tmp_path: Path) -> None:
    _write_config(
        tmp_path,
        '[keys]\nnext_agent = "prefix+shift+u"\n\n[[keys.command]]\n'
        'key = "prefix+shift+u"\ntype = "shell"\ncommand = "echo hi"\n',
    )

    findings = check_herdr_keys(str(tmp_path))

    assert [f.detail for f in findings] == ["prefix+shift+u"]
    assert "keys.command[0]" in findings[0].message


def test_check_duplicate_detection_is_case_insensitive(tmp_path: Path) -> None:
    _write_config(tmp_path, '[keys]\nnew_tab = "prefix+C"\nclose_pane = "prefix+c"\n')

    assert [f.detail for f in check_herdr_keys(str(tmp_path))] == ["prefix+c"]


def test_check_allows_same_chord_listed_once_per_action(tmp_path: Path) -> None:
    # 1 アクションに複数 chord を割り当てるのは正常(重複ではない)
    _write_config(tmp_path, '[keys]\ncycle_pane_next = ["prefix+tab", "ctrl+alt+]"]\n')

    assert check_herdr_keys(str(tmp_path)) == []


def test_check_flags_duplicate_chord_across_modifier_orders(tmp_path: Path) -> None:
    # herdr は修飾キーを集合として解釈する。綴りの順が違うだけの chord は同じ chord。
    _write_config(
        tmp_path,
        '[keys]\nnext_agent = "ctrl+alt+shift+j"\nlast_pane = "alt+ctrl+shift+j"\n',
    )

    findings = check_herdr_keys(str(tmp_path))

    # 検出結果は herdr が diagnostics で示す正規順で報告する
    assert [f.detail for f in findings] == ["ctrl+alt+shift+j"]
    # どちらの綴りがどのアクションのものか、config を開かずに分かること
    assert findings[0].message == (
        "同一 chord が複数のアクションに割り当てられています: "
        "last_pane = alt+ctrl+shift+j, next_agent = ctrl+alt+shift+j"
    )


def test_check_normalizes_modifier_order_under_prefix(tmp_path: Path) -> None:
    # prefix 配下でも修飾キーは集合。prefix は先頭に残す
    _write_config(
        tmp_path,
        '[keys]\nrename_pane = "prefix+shift+ctrl+p"\nlast_pane = "prefix+ctrl+shift+p"\n',
    )

    assert [f.detail for f in check_herdr_keys(str(tmp_path))] == ["prefix+ctrl+shift+p"]


def test_check_allows_same_key_with_different_modifier_sets(tmp_path: Path) -> None:
    # 修飾キーの集合が違えば別の chord。正規化が過剰に畳まないこと(negative)
    _write_config(
        tmp_path,
        '[keys]\nnext_agent = "ctrl+alt+shift+j"\nfocus_pane_down = "ctrl+alt+j"\n',
    )

    assert check_herdr_keys(str(tmp_path)) == []


def test_check_treats_prefix_as_mode_marker_not_modifier(tmp_path: Path) -> None:
    # prefix は先頭固定のモード標識であり修飾キーではない。prefix+shift+p と shift+p は別 chord
    _write_config(tmp_path, '[keys]\nrename_pane = "prefix+shift+p"\nlast_pane = "shift+p"\n')

    assert check_herdr_keys(str(tmp_path)) == []


def test_check_empty_when_no_config(tmp_path: Path) -> None:
    assert check_herdr_keys(str(tmp_path)) == []


# ---------------------------------------------------------------------------
# known_action_names (pure)
# ---------------------------------------------------------------------------


def test_known_action_names_extracts_commented_defaults() -> None:
    names = known_action_names(DEFAULT_CONFIG_EXCERPT)

    assert {"previous_agent", "next_agent", "zoom", "focus_pane_left"} <= names


def test_known_action_names_rejects_prose_comment_lines() -> None:
    # `# type = "shell" runs detached in the background.` は「名前 = 値」に見えるが、値の
    # 後ろに散文が続くため TOML として不正。パーサに弾かせて phantom entry を防ぐ。
    assert "type" not in known_action_names(DEFAULT_CONFIG_EXCERPT)


def test_known_action_names_stops_at_sub_tables() -> None:
    names = known_action_names(DEFAULT_CONFIG_EXCERPT)

    # [[keys.command]] と [keys.indexed] の中身はアクション名ではない
    assert "key" not in names
    assert "command" not in names
    assert "tabs" not in names


def test_known_action_names_excludes_prefix() -> None:
    assert "prefix" not in known_action_names(DEFAULT_CONFIG_EXCERPT)


def test_known_action_names_ignores_other_tables() -> None:
    # [keys] より前にある [theme] の name を拾わない
    assert "name" not in known_action_names(DEFAULT_CONFIG_EXCERPT)


def test_known_action_names_empty_without_keys_table() -> None:
    assert known_action_names('[theme]\nname = "one-dark"\n') == set()


# ---------------------------------------------------------------------------
# check_herdr_keys (未知のアクション名)
# ---------------------------------------------------------------------------


def test_check_flags_unknown_action_name(tmp_path: Path) -> None:
    # herdr は綴り違いを diagnostics 無しで受理するため、guard 側で検出する
    _write_config(tmp_path, '[keys]\nnext_agentt = "prefix+shift+j"\n')

    findings = check_herdr_keys(str(tmp_path), default_config_text=DEFAULT_CONFIG_EXCERPT)

    assert [f.detail for f in findings] == ["next_agentt"]
    assert all(f.source == CONFIG_PATH for f in findings)


def test_check_accepts_known_action_names(tmp_path: Path) -> None:
    _write_config(tmp_path, SAMPLE_CONFIG)

    assert check_herdr_keys(str(tmp_path), default_config_text=DEFAULT_CONFIG_EXCERPT) == []


def test_check_does_not_flag_command_entries_as_unknown(tmp_path: Path) -> None:
    # keys.command[0] は parse_bindings が付ける合成ラベルであってアクション名ではない
    _write_config(
        tmp_path,
        '[[keys.command]]\nkey = "prefix+shift+u"\ntype = "shell"\ncommand = "echo hi"\n',
    )

    assert check_herdr_keys(str(tmp_path), default_config_text=DEFAULT_CONFIG_EXCERPT) == []


def test_check_reports_unknown_action_once_per_name(tmp_path: Path) -> None:
    _write_config(tmp_path, '[keys]\nbogus_action = ["prefix+a", "prefix+b"]\n')

    findings = check_herdr_keys(str(tmp_path), default_config_text=DEFAULT_CONFIG_EXCERPT)

    assert [f.detail for f in findings] == ["bogus_action"]


def test_check_skips_unknown_action_check_without_reference(tmp_path: Path) -> None:
    # 参照テキストを渡さなければアクション名は検証しない (herdr が無い CI での挙動)
    _write_config(tmp_path, '[keys]\nnext_agentt = "prefix+shift+j"\n')

    assert check_herdr_keys(str(tmp_path)) == []


# ---------------------------------------------------------------------------
# read_default_config (副作用の隔離)
# ---------------------------------------------------------------------------


def test_read_default_config_returns_none_without_herdr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # PATH から herdr を外すと None を返し、呼び出し側は検査を skip できる
    monkeypatch.setenv("PATH", str(tmp_path))

    assert read_default_config() is None


def test_read_default_config_returns_none_on_nonzero_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = tmp_path / "herdr"
    fake.write_text("#!/bin/sh\necho boom >&2\nexit 3\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))

    assert read_default_config() is None


def test_read_default_config_returns_stdout_on_success(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    fake = tmp_path / "herdr"
    fake.write_text("#!/bin/sh\nprintf '[keys]\\n# next_agent = \"\"\\n'\n", encoding="utf-8")
    fake.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))

    text = read_default_config()

    assert text is not None
    assert known_action_names(text) == {"next_agent"}
