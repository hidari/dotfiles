"""TOML 設定ファイルの読み込みとバリデーション。

純粋関数のみで構成され、ファイル I/O は呼び出し元 (cli.py) の責務。
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from typing import Any, Literal, cast

ErrorBehavior = Literal["continue", "stop"]


class ConfigError(ValueError):
    """設定ファイルの形式・内容が不正なときに送出する。"""


@dataclass(frozen=True, slots=True)
class BackupPair:
    name: str
    source: str
    destination: str
    excludes: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Config:
    minimum_free_space_gb: int
    log_retention_days: int
    backup_pairs: tuple[BackupPair, ...]
    log_base_dir: str | None = None
    error_behavior: ErrorBehavior = "continue"
    additional_excludes: tuple[str, ...] = field(default_factory=tuple)


def load_config(data: bytes) -> Config:
    """TOML バイト列を読み込み、バリデート済みの Config を返す。"""
    try:
        raw = tomllib.loads(data.decode("utf-8"))
    except tomllib.TOMLDecodeError as err:
        raise ConfigError(f"TOML の解析に失敗しました: {err}") from err

    minimum_free_space_gb = _require_positive_int(raw, "minimum_free_space_gb")
    log_retention_days = _require_positive_int(raw, "log_retention_days")

    log_base_dir = _optional_str(raw, "log_base_dir")
    error_behavior = _parse_error_behavior(raw.get("error_behavior", "continue"))
    additional_excludes = _parse_string_list(raw, "additional_excludes")
    backup_pairs = _parse_backup_pairs(raw)

    return Config(
        minimum_free_space_gb=minimum_free_space_gb,
        log_retention_days=log_retention_days,
        log_base_dir=log_base_dir,
        error_behavior=error_behavior,
        additional_excludes=additional_excludes,
        backup_pairs=backup_pairs,
    )


def _require_positive_int(raw: dict[str, Any], key: str) -> int:
    if key not in raw:
        raise ConfigError(f"必須フィールド {key} が定義されていません")
    value = raw[key]
    if not isinstance(value, int) or isinstance(value, bool):
        raise ConfigError(f"{key} は整数である必要があります: 実際は {type(value).__name__}")
    if value < 0:
        raise ConfigError(f"{key} は 0 以上である必要があります: {value}")
    return value


def _optional_str(raw: dict[str, Any], key: str) -> str | None:
    if key not in raw:
        return None
    value = raw[key]
    if not isinstance(value, str):
        raise ConfigError(f"{key} は文字列である必要があります")
    return value


def _parse_error_behavior(value: Any) -> ErrorBehavior:
    if value not in ("continue", "stop"):
        raise ConfigError(
            f"error_behavior は 'continue' または 'stop' である必要があります: {value!r}"
        )
    return cast(ErrorBehavior, value)


def _parse_string_list(raw: dict[str, Any], key: str) -> tuple[str, ...]:
    value = raw.get(key, [])
    if not isinstance(value, list):
        raise ConfigError(f"{key} は配列である必要があります")
    for item in value:
        if not isinstance(item, str):
            raise ConfigError(f"{key} の要素は文字列である必要があります: {item!r}")
    return tuple(value)


def _parse_backup_pairs(raw: dict[str, Any]) -> tuple[BackupPair, ...]:
    pairs = raw.get("backup_pairs")
    if not pairs:
        raise ConfigError("backup_pairs が定義されていないか、空です")
    if not isinstance(pairs, list):
        raise ConfigError("backup_pairs は配列テーブルである必要があります")
    return tuple(_parse_backup_pair(entry, i) for i, entry in enumerate(pairs))


def _parse_backup_pair(entry: Any, index: int) -> BackupPair:
    if not isinstance(entry, dict):
        raise ConfigError(f"backup_pairs[{index}] はテーブルである必要があります")
    name = _require_str(entry, "name", index)
    source = _require_str(entry, "source", index)
    destination = _require_str(entry, "destination", index)
    excludes_raw = entry.get("excludes", [])
    if not isinstance(excludes_raw, list):
        raise ConfigError(f"backup_pairs[{index}].excludes は配列である必要があります")
    for item in excludes_raw:
        if not isinstance(item, str):
            raise ConfigError(f"backup_pairs[{index}].excludes の要素は文字列である必要があります")
    return BackupPair(
        name=name,
        source=source,
        destination=destination,
        excludes=tuple(excludes_raw),
    )


def _require_str(entry: dict[str, Any], key: str, index: int) -> str:
    if key not in entry:
        raise ConfigError(f"backup_pairs[{index}] に {key} が定義されていません")
    value = entry[key]
    if not isinstance(value, str):
        raise ConfigError(f"backup_pairs[{index}].{key} は文字列である必要があります")
    if value == "":
        raise ConfigError(f"backup_pairs[{index}].{key} は空文字列にできません")
    return value
