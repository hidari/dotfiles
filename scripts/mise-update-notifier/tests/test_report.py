"""report の仕様テスト。報告本文が危険度で分かれ、書き換え内容を提示することを検証する。"""

from __future__ import annotations

from mise_update_notifier.report import render_body
from mise_update_notifier.versions import ToolStatus

CONFIG_PATH = "home/.config/mise/config.toml"


def _status(tool: str, pinned: str, compatible: str, absolute: str) -> ToolStatus:
    return ToolStatus(
        tool=tool, pinned=pinned, compatible_latest=compatible, absolute_latest=absolute
    )


def test_compatible_update_lists_the_new_pin_line() -> None:
    # 「書き換えコマンド提示」の本体。config.toml へ貼れる形が出ていること
    body = render_body([_status("pnpm", "10.32.1", "10.34.5", "10.34.5")], CONFIG_PATH)

    assert 'pnpm = "10.34.5"' in body
    assert CONFIG_PATH in body
    assert "mise install" in body


def test_major_update_is_separated_from_compatible_update() -> None:
    statuses = [
        _status("pnpm", "10.32.1", "10.34.5", "11.13.1"),
        _status("node", "24.18.0", "24.18.0", "26.5.0"),
    ]

    body = render_body(statuses, CONFIG_PATH)
    compatible_section, major_section = body.split("## メジャー越え")

    # 同メジャー節には pnpm の 10.34.5 だけが載り、メジャー越えの版は混ざらない
    assert "10.34.5" in compatible_section
    assert "11.13.1" not in compatible_section
    # メジャー越え節には両方のメジャー跳躍が載る
    assert "26.5.0" in major_section
    assert "11.13.1" in major_section


def test_tool_without_any_update_is_not_listed() -> None:
    body = render_body([_status("just", "1.56.0", "1.56.0", "1.56.0")], CONFIG_PATH)

    assert "just" not in body


def test_section_is_omitted_when_empty() -> None:
    # メジャー越えが無いときに空の見出しだけ残さない
    body = render_body([_status("pnpm", "10.32.1", "10.34.5", "10.34.5")], CONFIG_PATH)

    assert "## メジャー越え" not in body
    assert "## 同メジャー" in body


def test_body_is_empty_when_nothing_to_report() -> None:
    assert render_body([_status("just", "1.56.0", "1.56.0", "1.56.0")], CONFIG_PATH) == ""


def test_major_only_update_omits_compatible_section() -> None:
    body = render_body([_status("node", "24.18.0", "24.18.0", "26.5.0")], CONFIG_PATH)

    assert "## 同メジャー" not in body
    assert "## メジャー越え" in body
    # メジャー越えは自動更新を勧めないので pin の書き換え行は出さない
    assert 'node = "26.5.0"' not in body
