"""ログ出力のセットアップとローテーション。

text / json 2 系列のフォーマッタと、旧 backup.sh:319-339 の
cleanup_old_logs 相当のロジックを提供する。
"""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

_LOG_PREFIX = "backup_"
_LOG_SUFFIX = ".log"
# logging.LogRecord の標準フィールド (extra と区別するため)
_STANDARD_ATTRS = frozenset(
    vars(logging.LogRecord("x", logging.INFO, "x", 0, "x", None, None)).keys()
) | {"message", "asctime"}


class LogFormat(StrEnum):
    TEXT = "text"
    JSON = "json"


class JsonFormatter(logging.Formatter):
    """1 行 1 オブジェクトの JSON ログを生成する。"""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = value
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(
    *,
    logger: logging.Logger,
    log_file: Path | None,
    log_format: LogFormat | str,
) -> None:
    """コンソール (+ ファイル) に出力する handler を logger に設定する。

    log_file=None の場合はファイルへの永続化を行わない (dry-run 向け)。
    """
    fmt = _coerce_format(log_format)
    logger.setLevel(logging.INFO)
    formatter = _build_formatter(fmt)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)


def rotate_old_logs(log_dir: Path, *, retention_days: int, now: float | None = None) -> int:
    """retention_days より古い backup_*.log を削除し、削除数を返す。"""
    if not log_dir.is_dir():
        return 0
    current = time.time() if now is None else now
    cutoff = current - retention_days * 86400
    deleted = 0
    for entry in log_dir.iterdir():
        if not entry.is_file():
            continue
        if not (entry.name.startswith(_LOG_PREFIX) and entry.name.endswith(_LOG_SUFFIX)):
            continue
        mtime = entry.stat().st_mtime
        if mtime < cutoff:
            entry.unlink()
            deleted += 1
    return deleted


def _coerce_format(value: LogFormat | str) -> LogFormat:
    if isinstance(value, LogFormat):
        return value
    try:
        return LogFormat(value)
    except ValueError as err:
        valid = tuple(f.value for f in LogFormat)
        raise ValueError(
            f"log_format は {valid} のいずれかである必要があります: {value!r}"
        ) from err


def _build_formatter(fmt: LogFormat) -> logging.Formatter:
    if fmt is LogFormat.JSON:
        return JsonFormatter()
    return logging.Formatter(
        fmt="[%(asctime)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
