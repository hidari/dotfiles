"""cli モジュールのテスト。

純粋ヘルパーに加え、main を偽の du / rsync だけを置いた PATH で通して、
事前検査と終了コードを確かめる。
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from backup_tool.cli import (
    _default_base_dir,
    _missing_config_message,
    _prepare_log_file,
    _resolve_config_path,
    _resolve_log_dir,
    _should_prompt,
    main,
)
from backup_tool.logging_setup import LogFormat
from tests.conftest import count_lines, du_prints, install_rsync, rsync_calls_path

if TYPE_CHECKING:
    from tests.conftest import FakeCommand

_REQUIRED = ("du", "rsync")
_MISSING_PREFIX = "エラー: 必要なコマンドが見つかりません: "


@pytest.fixture(autouse=True)
def _reset_backup_tool_logger() -> Iterator[None]:
    """main が足した handler を外す。残すと閉じた capsys のストリームへ書き続ける。"""
    yield
    backup_logger = logging.getLogger("backup_tool")
    for handler in backup_logger.handlers[:]:
        handler.close()
        backup_logger.removeHandler(handler)


class TestResolveConfigPath:
    def test_uses_explicit_path_when_given(self, tmp_path: Path) -> None:
        explicit = tmp_path / "mine.toml"
        assert _resolve_config_path(explicit) == explicit

    def test_falls_back_to_base_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BACKUP_TOOL_BASE_DIR", str(tmp_path))
        assert _resolve_config_path(None) == tmp_path / "backup.toml"


class TestDefaultBaseDir:
    def test_uses_env_var_when_set(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BACKUP_TOOL_BASE_DIR", str(tmp_path))
        assert _default_base_dir() == tmp_path

    def test_falls_back_to_cwd_when_unset(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.delenv("BACKUP_TOOL_BASE_DIR", raising=False)
        monkeypatch.chdir(tmp_path)
        assert _default_base_dir() == tmp_path


class TestResolveLogDir:
    def test_uses_config_value_when_present(self, tmp_path: Path) -> None:
        config_path = tmp_path / "backup.toml"
        result = _resolve_log_dir(config_path, "/explicit/log/dir")
        assert result == Path("/explicit/log/dir")

    def test_falls_back_to_sibling_directory(self, tmp_path: Path) -> None:
        config_path = tmp_path / "backup.toml"
        assert _resolve_log_dir(config_path, None) == tmp_path / ".backup_logs"


class TestPrepareLogFile:
    def test_dry_run_returns_none(self, tmp_path: Path) -> None:
        assert _prepare_log_file(tmp_path, dry_run=True) is None

    def test_non_dry_run_creates_dir_and_returns_timestamped_file(self, tmp_path: Path) -> None:
        log_dir = tmp_path / "logs"
        result = _prepare_log_file(log_dir, dry_run=False)
        assert result is not None
        assert log_dir.is_dir()
        assert result.parent == log_dir
        assert result.name.startswith("backup_")
        assert result.name.endswith(".log")


class TestShouldPrompt:
    def test_dry_run_skips_prompt(self) -> None:
        assert _should_prompt(log_format=LogFormat.TEXT, dry_run=True) is False

    def test_json_format_skips_prompt(self) -> None:
        assert _should_prompt(log_format=LogFormat.JSON, dry_run=False) is False


class TestMissingConfigMessage:
    def test_guides_copying_the_example(self, tmp_path: Path) -> None:
        path = tmp_path / "backup.toml"
        message = _missing_config_message(path)
        assert f"設定ファイル: {path}" in message
        assert "backup.example.toml をコピーして backup.toml を作成してください" in message


def _write_config(tmp_path: Path) -> Path:
    """tmp_path 配下のローカルディレクトリ同士のペアを1つ持つ設定を書く。"""
    source = tmp_path / "src"
    destination = tmp_path / "dst"
    source.mkdir()
    destination.mkdir()
    config_path = tmp_path / "backup.toml"
    config_path.write_text(
        "minimum_free_space_gb = 1\n"
        "log_retention_days = 90\n"
        "[[backup_pairs]]\n"
        'name = "local"\n'
        f'source = "{source}"\n'
        f'destination = "{destination}"\n',
        encoding="utf-8",
    )
    return config_path


def _install_present(fake_command: FakeCommand, tmp_path: Path, *, missing: set[str]) -> Path:
    """missing 以外の必要なコマンドの偽物を置き、rsync の呼び出しを記録するファイルを返す。"""
    if "du" not in missing:
        fake_command("du", du_prints(1))
    if "rsync" not in missing:
        install_rsync(fake_command, tmp_path)
    return rsync_calls_path(tmp_path)


def _reported_missing(err: str) -> set[str]:
    lines = [line for line in err.splitlines() if line.startswith(_MISSING_PREFIX)]
    assert len(lines) == 1, err
    return set(lines[0].removeprefix(_MISSING_PREFIX).split(", "))


class TestMainPreflight:
    @pytest.mark.parametrize("missing", [{"du"}, {"rsync"}, {"du", "rsync"}])
    def test_reports_exactly_the_missing_commands(
        self,
        empty_path: None,
        fake_command: FakeCommand,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
        missing: set[str],
    ) -> None:
        calls = _install_present(fake_command, tmp_path, missing=missing)

        exit_code = main(["--dry-run", "--config", str(_write_config(tmp_path))])

        assert exit_code == 1
        err = capsys.readouterr().err
        assert _reported_missing(err) == missing
        for name in set(_REQUIRED) - missing:
            assert name not in err
        assert count_lines(calls) == 0

    def test_runs_the_backup_when_every_command_is_present(
        self,
        empty_path: None,
        fake_command: FakeCommand,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # 上の不在ケースの対照。偽物だけの PATH で main が最後まで通ることを確かめる
        calls = _install_present(fake_command, tmp_path, missing=set())

        exit_code = main(["--dry-run", "--config", str(_write_config(tmp_path))])

        assert exit_code == 0
        assert _MISSING_PREFIX not in capsys.readouterr().err
        assert count_lines(calls) == 1

    def test_stops_before_logging_setup_and_prompt(
        self,
        empty_path: None,
        fake_command: FakeCommand,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # dry-run ではログファイルもプロンプトも無く順序が見えないので、通常の実行で確かめる
        _install_present(fake_command, tmp_path, missing={"rsync"})
        monkeypatch.setattr(sys.stdin, "isatty", lambda: True)

        def refuse_prompt(_prompt: str = "") -> str:
            raise AssertionError("確認プロンプトに到達した")

        monkeypatch.setattr("builtins.input", refuse_prompt)
        config_path = _write_config(tmp_path)

        exit_code = main(["--config", str(config_path)])

        assert exit_code == 1
        assert _reported_missing(capsys.readouterr().err) == {"rsync"}
        assert not (config_path.parent / ".backup_logs").exists()


class TestMainUsageErrors:
    @pytest.mark.parametrize("argv", [["--no-such-option"], ["--log-format", "xml"]])
    def test_usage_error_exits_with_config_error_code(
        self, argv: list[str], capsys: pytest.CaptureFixture[str]
    ) -> None:
        # 2は「一部のペアが失敗」なので、引数の誤りは設定不備と同じ1にする
        with pytest.raises(SystemExit) as excinfo:
            main(argv)
        assert excinfo.value.code == 1
        assert "usage:" in capsys.readouterr().err

    def test_help_exits_zero(self, capsys: pytest.CaptureFixture[str]) -> None:
        with pytest.raises(SystemExit) as excinfo:
            main(["--help"])
        assert excinfo.value.code == 0
        assert "usage:" in capsys.readouterr().out
