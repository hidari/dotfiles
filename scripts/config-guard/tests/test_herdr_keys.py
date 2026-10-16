"""herdr_keys の仕様テスト。

binding パーサ(pure)と、方向整合 / chord 重複の検査(実ファイル)、`herdr config check` の
結果の解釈(pure)と起動(副作用)を検証する。
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from config_guard import herdr_keys
from config_guard.herdr_keys import (
    CONFIG_PATH,
    Binding,
    check_herdr_keys,
    parse_bindings,
    run_config_check,
)

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
# check_herdr_keys (`herdr config check` の結果の解釈)
# ---------------------------------------------------------------------------


def _checked(returncode: int, stdout: str) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["herdr", "config", "check"], returncode, stdout, "")


def test_check_reports_herdr_diagnostics(tmp_path: Path) -> None:
    _write_config(tmp_path, SAMPLE_CONFIG)
    result = _checked(
        1, "config: issues found\nunknown config key keys.next_agentt; ignoring key\n"
    )

    findings = check_herdr_keys(str(tmp_path), lambda _: result)

    assert [(f.source, f.detail) for f in findings] == [(CONFIG_PATH, "herdr config check")]
    assert "unknown config key keys.next_agentt; ignoring key" in findings[0].message


def test_check_keeps_every_line_of_multiline_diagnostics(tmp_path: Path) -> None:
    # TOML の構文エラーは複数行で報告される。1 行目だけ拾うと位置と理由が落ちる
    _write_config(tmp_path, SAMPLE_CONFIG)
    result = _checked(
        1,
        "config: issues found\nconfig parse error: TOML parse error at line 1, column 10\n"
        "invalid array\nexpected `]`\n; using defaults\n",
    )

    (finding,) = check_herdr_keys(str(tmp_path), lambda _: result)

    for line in ("line 1, column 10", "invalid array", "expected `]`", "using defaults"):
        assert line in finding.message


def test_check_passes_when_herdr_reports_ok(tmp_path: Path) -> None:
    _write_config(tmp_path, SAMPLE_CONFIG)

    assert check_herdr_keys(str(tmp_path), lambda _: _checked(0, "config: ok\n")) == []


@pytest.mark.parametrize(
    ("returncode", "stdout"),
    [
        (2, "herdr config commands:\n"),
        (1, "something else\n"),
        (1, ""),
        # 2 行目以降があっても、見出しが違えば診断として読まない
        (1, "unexpected header\nsome detail\n"),
    ],
)
def test_check_reports_uninterpretable_result(tmp_path: Path, returncode: int, stdout: str) -> None:
    # 想定外の形を「問題なし」へ倒すと、herdr の出力形式が変わった瞬間に検査が黙って止まる
    _write_config(tmp_path, SAMPLE_CONFIG)

    (finding,) = check_herdr_keys(str(tmp_path), lambda _: _checked(returncode, stdout))

    assert finding.detail == "herdr config check"
    assert f"rc={returncode}" in finding.message


def test_check_skips_herdr_when_checker_returns_none(tmp_path: Path) -> None:
    # herdr が無い CI では起動結果が None になり、静的な検査だけが走る
    _write_config(tmp_path, SAMPLE_CONFIG)

    assert check_herdr_keys(str(tmp_path), lambda _: None) == []


def test_check_passes_config_path_to_checker(tmp_path: Path) -> None:
    _write_config(tmp_path, SAMPLE_CONFIG)
    seen: list[Path] = []

    def checker(path: Path) -> subprocess.CompletedProcess[str]:
        seen.append(path)
        return _checked(0, "config: ok\n")

    check_herdr_keys(str(tmp_path), checker)

    assert seen == [tmp_path / CONFIG_PATH]


def test_check_does_not_run_herdr_without_config(tmp_path: Path) -> None:
    # herdr は存在しないパスを渡されても `config: ok` で rc 0 を返す (実測)。起動させると
    # 「config が無い」が「config に問題が無い」と区別できなくなる
    def checker(_: Path) -> subprocess.CompletedProcess[str]:
        raise AssertionError("config が無いのに herdr を起動した")

    assert check_herdr_keys(str(tmp_path), checker) == []


# ---------------------------------------------------------------------------
# run_config_check (副作用の隔離)
# ---------------------------------------------------------------------------


def _fake_herdr(directory: Path, body: str) -> None:
    fake = directory / "herdr"
    fake.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
    fake.chmod(0o755)


def test_run_config_check_returns_none_without_herdr(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PATH", str(tmp_path))

    assert run_config_check(tmp_path / "config.toml") is None


def test_run_config_check_points_herdr_at_the_given_config(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # 待ち時間を緩める理由は _SUBPROCESS_TIMEOUT_SECONDS の定義コメントを参照。
    # ここで測りたいのは引数と環境変数の受け渡しだけ
    monkeypatch.setattr(herdr_keys, "_SUBPROCESS_TIMEOUT_SECONDS", 120)
    _fake_herdr(tmp_path, 'printf "%s|%s" "$*" "$HERDR_CONFIG_PATH"; exit 1')
    monkeypatch.setenv("PATH", str(tmp_path))
    config = tmp_path / "config.toml"

    result = run_config_check(config)

    assert result is not None
    assert (result.returncode, result.stdout) == (1, f"config check|{config}")


def test_run_config_check_returns_none_on_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # timeout を None へ畳むことの仕様化と、_SUBPROCESS_TIMEOUT_SECONDS が subprocess へ
    # 渡っていることの pin を兼ねる。sleep を絶対パスで呼ぶのは、PATH を tmp_path だけへ
    # 絞ると PATH 経由では見つからず、sh が not found のまま即座に終わるため
    sleep = shutil.which("sleep")
    assert sleep is not None, "sleep が見つからない環境ではこのテストを構成できない"
    monkeypatch.setattr(herdr_keys, "_SUBPROCESS_TIMEOUT_SECONDS", 0.001)
    _fake_herdr(tmp_path, f"{sleep} 1\necho 'config: ok'")
    monkeypatch.setenv("PATH", str(tmp_path))

    assert run_config_check(tmp_path / "config.toml") is None


# ---------------------------------------------------------------------------
# 本物の herdr での live smoke (herdr が無い CI では skip)
# ---------------------------------------------------------------------------

requires_herdr = pytest.mark.skipif(shutil.which("herdr") is None, reason="herdr が無い")


@requires_herdr
def test_live_herdr_reports_misspelled_action(tmp_path: Path) -> None:
    _write_config(tmp_path, '[keys]\nnext_agentt = "prefix+shift+j"\n')

    (finding,) = check_herdr_keys(str(tmp_path), run_config_check)

    assert "unknown config key keys.next_agentt" in finding.message


@requires_herdr
def test_live_herdr_accepts_valid_config(tmp_path: Path) -> None:
    # 上のテストの対照。同じ経路で、正しい config では何も報告しない
    _write_config(tmp_path, '[keys]\nnext_agent = "prefix+shift+j"\n')

    assert check_herdr_keys(str(tmp_path), run_config_check) == []
