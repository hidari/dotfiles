"""旧 backup.conf (Bash スクリプト) → backup.toml への変換。

Bash の source は任意コード実行になるため、安全のため簡易パーサで
KEY=VALUE / KEY=(...) 形式だけを抽出する。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from backup_tool.config import BackupPair, Config

_SCALAR = re.compile(r"^([A-Z_][A-Z0-9_]*)=(.*)$")
_ARRAY_OPEN = re.compile(r"^([A-Z_][A-Z0-9_]*)=\(\s*(.*)$")


class MigrationError(ValueError):
    """設定マイグレーション時のエラー。"""


def parse_bash_conf(text: str) -> Config:
    """Bash の backup.conf 形式を読み取り、Config に変換する。"""
    variables = _extract_variables(text)

    required = ("MINIMUM_FREE_SPACE_GB", "LOG_RETENTION_DAYS")
    missing = [key for key in required if key not in variables]
    if missing:
        raise MigrationError(f"必須項目が見つかりません: {', '.join(missing)}")

    pairs_raw = variables.get("BACKUP_PAIRS")
    if not isinstance(pairs_raw, list):
        raise MigrationError("BACKUP_PAIRS が配列として定義されていません")
    pairs = tuple(_parse_pair_string(entry) for entry in pairs_raw)

    additional = variables.get("ADDITIONAL_EXCLUDE", [])
    if not isinstance(additional, list):
        raise MigrationError("ADDITIONAL_EXCLUDE が配列として定義されていません")

    error_behavior_raw = variables.get("ERROR_BEHAVIOR", "continue")
    if error_behavior_raw not in ("continue", "stop"):
        raise MigrationError(
            f"ERROR_BEHAVIOR は 'continue' または 'stop' である必要があります: "
            f"{error_behavior_raw!r}"
        )

    log_base_dir = variables.get("LOG_BASE_DIR")
    if log_base_dir is not None and not isinstance(log_base_dir, str):
        raise MigrationError("LOG_BASE_DIR は文字列である必要があります")

    try:
        minimum_free_space_gb = int(str(variables["MINIMUM_FREE_SPACE_GB"]))
        log_retention_days = int(str(variables["LOG_RETENTION_DAYS"]))
    except ValueError as err:
        raise MigrationError(f"数値項目の解析に失敗しました: {err}") from err

    return Config(
        minimum_free_space_gb=minimum_free_space_gb,
        log_retention_days=log_retention_days,
        log_base_dir=log_base_dir if log_base_dir else None,
        error_behavior=error_behavior_raw,
        additional_excludes=tuple(additional),
        backup_pairs=pairs,
    )


def to_toml_string(config: Config) -> str:
    """Config を TOML 文字列にシリアライズする。"""
    lines: list[str] = [
        f"minimum_free_space_gb = {config.minimum_free_space_gb}",
        f"log_retention_days = {config.log_retention_days}",
    ]
    if config.log_base_dir is not None:
        lines.append(f"log_base_dir = {_toml_string(config.log_base_dir)}")
    lines.append(f'error_behavior = "{config.error_behavior}"')
    lines.append(f"additional_excludes = {_toml_string_array(config.additional_excludes)}")
    for pair in config.backup_pairs:
        lines.append("")
        lines.append("[[backup_pairs]]")
        lines.append(f"name = {_toml_string(pair.name)}")
        lines.append(f"source = {_toml_string(pair.source)}")
        lines.append(f"destination = {_toml_string(pair.destination)}")
        if pair.excludes:
            lines.append(f"excludes = {_toml_string_array(pair.excludes)}")
    return "\n".join(lines) + "\n"


def migrate_file(*, src: Path, dst: Path) -> None:
    """backup.conf を読み backup.toml を書き出し、旧ファイルを .bak に退避する。"""
    if not src.exists():
        raise MigrationError(f"{src} が見つかりません")
    if dst.exists():
        raise MigrationError(f"{dst} は既に存在します。上書きは行いません")

    config = parse_bash_conf(src.read_text(encoding="utf-8"))
    dst.write_text(to_toml_string(config), encoding="utf-8")
    src.rename(src.with_suffix(src.suffix + ".bak"))


def _extract_variables(text: str) -> dict[str, Any]:
    variables: dict[str, Any] = {}
    lines = text.splitlines()
    index = 0
    while index < len(lines):
        line = _strip_comment(lines[index]).strip()
        index += 1
        if not line:
            continue
        array_match = _ARRAY_OPEN.match(line)
        if array_match:
            name = array_match.group(1)
            after = array_match.group(2)
            items, index = _collect_array_items(after, lines, index)
            variables[name] = items
            continue
        scalar_match = _SCALAR.match(line)
        if scalar_match:
            name = scalar_match.group(1)
            raw_value = scalar_match.group(2).strip()
            variables[name] = _unquote(raw_value)
    return variables


def _collect_array_items(
    first_line_tail: str,
    lines: list[str],
    index: int,
) -> tuple[list[str], int]:
    items: list[str] = []
    buffer = first_line_tail.strip()

    def process_segment(segment: str) -> bool:
        """セグメントを items に追加。閉じカッコを検出したら True を返す。"""
        text = segment.strip()
        if text == "":
            return False
        if text == ")":
            return True
        if text.endswith(")"):
            inner = _strip_comment(text[:-1]).strip()
            if inner:
                items.append(_unquote(inner))
            return True
        items.append(_unquote(text))
        return False

    if buffer and process_segment(buffer):
        return items, index

    while index < len(lines):
        segment = _strip_comment(lines[index]).strip()
        index += 1
        if segment == "":
            continue
        if process_segment(segment):
            return items, index

    raise MigrationError("配列定義が閉じられていません")


def _strip_comment(line: str) -> str:
    in_single = False
    in_double = False
    for i, ch in enumerate(line):
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            return line[:i]
    return line


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def _parse_pair_string(value: str) -> BackupPair:
    parts = value.split("|")
    if len(parts) < 3:
        raise MigrationError(f"BACKUP_PAIRS のエントリが不正です: {value!r}")
    name = parts[0].strip()
    source = parts[1].strip()
    destination = parts[2].strip()
    excludes_field = parts[3] if len(parts) >= 4 else ""
    excludes = tuple(item.strip() for item in excludes_field.split(",") if item.strip())
    if not name or not source or not destination:
        raise MigrationError(f"BACKUP_PAIRS のエントリに空フィールドがあります: {value!r}")
    return BackupPair(name=name, source=source, destination=destination, excludes=excludes)


def _toml_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def _toml_string_array(values: tuple[str, ...]) -> str:
    if not values:
        return "[]"
    inner = ", ".join(_toml_string(v) for v in values)
    return f"[{inner}]"
