"""コマンドラインエントリポイント。

旧 backup.sh:702-732 のメイン処理を argparse ベースに書き直し、
run (デフォルト) と migrate-config の 2 サブコマンドを提供する。
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path

from backup_tool.config import Config, ConfigError, load_config
from backup_tool.logging_setup import LogFormat, configure_logging, rotate_old_logs
from backup_tool.migrate import MigrationError, migrate_file
from backup_tool.runner import ExitCode, run_backup

_DEFAULT_CONFIG_NAME = "backup.toml"
_LEGACY_CONFIG_NAME = "backup.conf"
_LOG_DIR_NAME = ".backup_logs"

logger = logging.getLogger("backup_tool")


def main(argv: Sequence[str] | None = None) -> int:
    args = list(argv) if argv is not None else sys.argv[1:]
    if args and args[0] == "migrate-config":
        return _migrate_command(args[1:])
    return _run_command(args)


def _run_command(args: list[str]) -> int:
    parser = _build_run_parser()
    parsed = parser.parse_args(args)

    config_path = _resolve_config_path(parsed.config)
    if not config_path.is_file():
        print(_missing_config_message(config_path), file=sys.stderr)
        return int(ExitCode.USER_ABORT)

    try:
        config = load_config(config_path.read_bytes())
    except ConfigError as err:
        print(f"設定ファイルが不正です: {err}", file=sys.stderr)
        return int(ExitCode.USER_ABORT)

    log_dir = _resolve_log_dir(config_path, config.log_base_dir)
    log_file = _prepare_log_file(log_dir, dry_run=parsed.dry_run)
    log_format = LogFormat(parsed.log_format)
    configure_logging(logger=logger, log_file=log_file, log_format=log_format)

    if not parsed.dry_run:
        rotate_old_logs(log_dir, retention_days=config.log_retention_days)

    if parsed.dry_run:
        logger.info("DRY-RUN モード: 実際のコピーは行いません")

    logger.info("========== バックアップセッション開始 ==========")
    _log_configuration(config, config_path=config_path)

    needs_prompt = _should_prompt(log_format=log_format, dry_run=parsed.dry_run)
    if needs_prompt and not _prompt_user_confirmation():
        logger.info("ユーザーの指示によりバックアップを中止しました")
        return int(ExitCode.USER_ABORT)

    exit_code = run_backup(config, dry_run=parsed.dry_run, logger=logger)
    logger.info("========== バックアップセッション終了 (exit=%d) ==========", int(exit_code))
    return int(exit_code)


def _migrate_command(args: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="backup migrate-config",
        description="旧 backup.conf を backup.toml に変換する",
    )
    parser.add_argument("--from", dest="src", type=Path, default=None, help="入力 backup.conf")
    parser.add_argument("--to", dest="dst", type=Path, default=None, help="出力 backup.toml")
    parsed = parser.parse_args(args)

    base_dir = _default_base_dir()
    src = parsed.src or base_dir / _LEGACY_CONFIG_NAME
    dst = parsed.dst or base_dir / _DEFAULT_CONFIG_NAME

    try:
        migrate_file(src=src, dst=dst)
    except MigrationError as err:
        print(f"マイグレーションに失敗しました: {err}", file=sys.stderr)
        return int(ExitCode.USER_ABORT)
    backup_path = src.with_suffix(src.suffix + ".bak")
    print(f"{src} を {dst} に変換しました。旧ファイルは {backup_path} に退避されています")
    return int(ExitCode.SUCCESS)


def _build_run_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="backup",
        description="macOS 向け rsync ベースのストレージバックアップ",
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        action="store_true",
        help="実際のコピーを行わず内容を確認",
    )
    parser.add_argument(
        "--log-format",
        choices=[f.value for f in LogFormat],
        default=LogFormat.TEXT.value,
        help="ログ出力フォーマット",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help=f"設定ファイルのパス (デフォルト: ./{_DEFAULT_CONFIG_NAME})",
    )
    return parser


def _resolve_config_path(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    return _default_base_dir() / _DEFAULT_CONFIG_NAME


def _default_base_dir() -> Path:
    """shebang ラッパーから BACKUP_TOOL_BASE_DIR が渡されていればそれを使う。"""
    env_dir = os.environ.get("BACKUP_TOOL_BASE_DIR")
    if env_dir:
        return Path(env_dir)
    return Path.cwd()


def _resolve_log_dir(config_path: Path, log_base_dir: str | None) -> Path:
    if log_base_dir:
        return Path(log_base_dir)
    return config_path.parent / _LOG_DIR_NAME


def _prepare_log_file(log_dir: Path, *, dry_run: bool) -> Path | None:
    if dry_run:
        return None
    log_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return log_dir / f"backup_{timestamp}.log"


def _missing_config_message(path: Path) -> str:
    return (
        "エラー: 設定ファイルが見つかりません\n"
        f"設定ファイル: {path}\n"
        "旧 backup.conf から移行する場合は 'backup migrate-config' を実行してください\n"
        f"新規の場合は backup.example.toml をコピーして {path.name} を作成してください"
    )


def _log_configuration(config: Config, *, config_path: Path) -> None:
    logger.info("設定ファイル: %s", config_path)
    logger.info("ペア数: %d", len(config.backup_pairs))
    logger.info("error_behavior: %s", config.error_behavior)
    for index, pair in enumerate(config.backup_pairs, start=1):
        logger.info(
            "[%d] %s: %s -> %s%s",
            index,
            pair.name,
            pair.source,
            pair.destination,
            f" (excludes: {', '.join(pair.excludes)})" if pair.excludes else "",
        )
    if config.additional_excludes:
        logger.info("追加の除外パターン: %s", ", ".join(config.additional_excludes))


def _should_prompt(*, log_format: LogFormat, dry_run: bool) -> bool:
    if dry_run:
        return False
    if log_format is LogFormat.JSON:
        return False
    return sys.stdin.isatty()


def _prompt_user_confirmation() -> bool:
    try:
        answer = input("上記の設定でバックアップを実行しますか? (y/n): ").strip().lower()
    except EOFError:
        return False
    return answer == "y"
