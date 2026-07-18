"""cli の仕様テスト。mise 呼び出しは注入した fake で置き換え、実行順と失敗検出を検証する。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mise_update_notifier.cli import collect_statuses, main
from mise_update_notifier.versions import ToolStatus


class FakeMise:
    """spec -> 返す version の対応表。呼ばれた spec を順に記録する。"""

    def __init__(self, table: dict[str, str]) -> None:
        self.table = table
        self.calls: list[str] = []

    def __call__(self, spec: str) -> str:
        self.calls.append(spec)
        return self.table[spec]


def test_collect_statuses_queries_absolute_and_compatible_specs() -> None:
    mise = FakeMise({"pnpm": "11.13.1", "pnpm@10": "10.34.5"})

    statuses = collect_statuses({"pnpm": "10.32.1"}, mise)

    assert statuses == [
        ToolStatus(
            tool="pnpm", pinned="10.32.1", compatible_latest="10.34.5", absolute_latest="11.13.1"
        )
    ]
    assert sorted(mise.calls) == ["pnpm", "pnpm@10"]


def test_collect_statuses_derives_zero_version_range_from_minor() -> None:
    # 0.x は minor が破壊的変更の軸。tirith@0 ではなく tirith@0.3 を問い合わせる
    mise = FakeMise({"tirith": "0.4.0", "tirith@0.3": "0.3.3"})

    collect_statuses({"tirith": "0.3.3"}, mise)

    assert "tirith@0.3" in mise.calls
    assert "tirith@0" not in mise.calls


def test_collect_statuses_rejects_empty_result() -> None:
    # mise は存在しないメジャーに exit 0 + 空文字列を返す。空を「更新なし」と読むと
    # 導出を誤った瞬間に嘘をつき続けるので、必ず失敗させる
    mise = FakeMise({"pnpm": "11.13.1", "pnpm@10": ""})

    with pytest.raises(RuntimeError, match="pnpm@10"):
        collect_statuses({"pnpm": "10.32.1"}, mise)


def test_main_writes_body_and_reports_updates(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "config.toml"
    config.write_text('[tools]\npnpm = "10.32.1"\n', encoding="utf-8")
    body_out = tmp_path / "body.md"
    mise = FakeMise({"pnpm": "11.13.1", "pnpm@10": "10.34.5"})

    exit_code = main(["--config", str(config), "--body-out", str(body_out)], run_mise_latest=mise)

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary == {"has_updates": True, "compatible": 1, "major": 1}
    assert 'pnpm = "10.34.5"' in body_out.read_text(encoding="utf-8")


def test_main_reports_no_updates_and_writes_empty_body(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    config = tmp_path / "config.toml"
    config.write_text('[tools]\njust = "1.56.0"\n', encoding="utf-8")
    body_out = tmp_path / "body.md"
    mise = FakeMise({"just": "1.56.0", "just@1": "1.56.0"})

    exit_code = main(["--config", str(config), "--body-out", str(body_out)], run_mise_latest=mise)

    assert exit_code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary == {"has_updates": False, "compatible": 0, "major": 0}
    assert body_out.read_text(encoding="utf-8") == ""


def test_main_fails_loudly_when_mise_returns_empty(tmp_path: Path) -> None:
    # 失敗を exit 0 + 「更新なし」に化けさせない (Issue が黙って閉じるのを防ぐ)
    config = tmp_path / "config.toml"
    config.write_text('[tools]\npnpm = "10.32.1"\n', encoding="utf-8")
    mise = FakeMise({"pnpm": "11.13.1", "pnpm@10": ""})

    with pytest.raises(RuntimeError):
        main(
            ["--config", str(config), "--body-out", str(tmp_path / "body.md")],
            run_mise_latest=mise,
        )


def test_main_renders_config_path_relative_to_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 本文は GitHub Issue に載る。絶対パスのまま出すとユーザー名が公開先へ漏れる
    config = tmp_path / "home" / "config.toml"
    config.parent.mkdir()
    config.write_text('[tools]\npnpm = "10.32.1"\n', encoding="utf-8")
    body_out = tmp_path / "body.md"
    mise = FakeMise({"pnpm": "11.13.1", "pnpm@10": "10.34.5"})
    monkeypatch.chdir(tmp_path)

    main(["--config", str(config), "--body-out", str(body_out)], run_mise_latest=mise)

    body = body_out.read_text(encoding="utf-8")
    assert "home/config.toml" in body
    assert str(tmp_path) not in body
