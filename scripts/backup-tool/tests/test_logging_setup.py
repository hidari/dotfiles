"""logging_setup モジュールのテスト。

rotate_old_logs のロジックと JSON フォーマッタの挙動を検証する。
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

import pytest

from backup_tool.logging_setup import (
    JsonFormatter,
    LogFormat,
    configure_logging,
    rotate_old_logs,
)


class TestRotateOldLogs:
    def test_deletes_logs_older_than_retention(self, tmp_path: Path) -> None:
        old = tmp_path / "backup_20200101_000000.log"
        old.write_text("old")
        fresh = tmp_path / "backup_20260401_000000.log"
        fresh.write_text("new")

        now = time.time()
        old_mtime = now - 100 * 86400  # 100日前
        fresh_mtime = now - 1 * 86400  # 1日前
        os.utime(old, (old_mtime, old_mtime))
        os.utime(fresh, (fresh_mtime, fresh_mtime))

        deleted = rotate_old_logs(tmp_path, retention_days=90, now=now)

        assert deleted == 1
        assert not old.exists()
        assert fresh.exists()

    def test_ignores_non_backup_logs(self, tmp_path: Path) -> None:
        unrelated = tmp_path / "something.log"
        unrelated.write_text("x")
        os.utime(unrelated, (time.time() - 1000 * 86400, time.time() - 1000 * 86400))

        deleted = rotate_old_logs(tmp_path, retention_days=30, now=time.time())

        assert deleted == 0
        assert unrelated.exists()

    def test_returns_zero_when_directory_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "no-such-dir"
        assert rotate_old_logs(missing, retention_days=30, now=time.time()) == 0

    def test_keeps_files_at_exact_boundary(self, tmp_path: Path) -> None:
        target = tmp_path / "backup_20250101_000000.log"
        target.write_text("x")
        now = time.time()
        boundary_mtime = now - 30 * 86400
        os.utime(target, (boundary_mtime, boundary_mtime))

        deleted = rotate_old_logs(tmp_path, retention_days=30, now=now)

        assert deleted == 0
        assert target.exists()


class TestJsonFormatter:
    def test_emits_json_object(self) -> None:
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="backup_tool",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="hello %s",
            args=("world",),
            exc_info=None,
        )
        record.created = 1710000000.0

        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "hello world"
        assert parsed["logger"] == "backup_tool"
        assert "timestamp" in parsed

    def test_includes_extra_fields(self) -> None:
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="backup_tool",
            level=logging.INFO,
            pathname=__file__,
            lineno=1,
            msg="pair done",
            args=(),
            exc_info=None,
        )
        record.pair_name = "メインSSD"

        parsed = json.loads(formatter.format(record))
        assert parsed["pair_name"] == "メインSSD"


class TestConfigureLogging:
    def test_attaches_file_handler(self, tmp_path: Path) -> None:
        log_file = tmp_path / "backup.log"
        logger = logging.getLogger("test_backup_tool_file")
        logger.handlers.clear()

        configure_logging(
            logger=logger,
            log_file=log_file,
            log_format=LogFormat.TEXT,
        )

        logger.info("hello")
        for handler in logger.handlers:
            handler.flush()
        assert log_file.exists()
        assert "hello" in log_file.read_text()

    def test_json_format_emits_valid_json_per_line(self, tmp_path: Path) -> None:
        log_file = tmp_path / "backup.log"
        logger = logging.getLogger("test_backup_tool_json")
        logger.handlers.clear()

        configure_logging(
            logger=logger,
            log_file=log_file,
            log_format=LogFormat.JSON,
        )

        logger.info("hello")
        for handler in logger.handlers:
            handler.flush()

        lines = [line for line in log_file.read_text().splitlines() if line]
        assert lines, "ログ行が書き出されていません"
        for line in lines:
            parsed = json.loads(line)
            assert parsed["message"] == "hello"

    def test_rejects_unknown_log_format(self, tmp_path: Path) -> None:
        logger = logging.getLogger("test_backup_tool_bad")
        logger.handlers.clear()
        with pytest.raises(ValueError, match="log_format"):
            configure_logging(
                logger=logger,
                log_file=tmp_path / "backup.log",
                log_format="yaml",
            )

    def test_none_log_file_skips_file_handler(self) -> None:
        logger = logging.getLogger("test_backup_tool_nolog")
        logger.handlers.clear()

        configure_logging(logger=logger, log_file=None, log_format=LogFormat.TEXT)

        file_handlers = [h for h in logger.handlers if isinstance(h, logging.FileHandler)]
        assert file_handlers == []
        stream_handlers = [
            h
            for h in logger.handlers
            if isinstance(h, logging.StreamHandler) and not isinstance(h, logging.FileHandler)
        ]
        assert len(stream_handlers) == 1
