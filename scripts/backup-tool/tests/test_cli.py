"""cli モジュールの純粋ヘルパーに対するテスト。

I/O を伴う run_command / migrate_command 自体は実機・統合レベルで検証する。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from backup_tool.cli import (
    _default_base_dir,
    _missing_config_message,
    _prepare_log_file,
    _resolve_config_path,
    _resolve_log_dir,
    _should_prompt,
)
from backup_tool.logging_setup import LogFormat


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
    def test_includes_migrate_guidance(self, tmp_path: Path) -> None:
        message = _missing_config_message(tmp_path / "backup.toml")
        assert "backup migrate-config" in message
        assert "backup.example.toml" in message
