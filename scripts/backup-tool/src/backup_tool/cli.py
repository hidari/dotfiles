"""コマンドラインエントリポイント。"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import NoReturn

from backup_tool.config import Config, ConfigError, load_config
from backup_tool.disk import DU_COMMAND
from backup_tool.logging_setup import LogFormat, configure_logging, rotate_old_logs
from backup_tool.rsync import RSYNC_COMMAND
from backup_tool.runner import ExitCode, run_backup

_DEFAULT_CONFIG_NAME = "backup.toml"
_LOG_DIR_NAME = ".backup_logs"
# 実行に要る外部コマンド。dry-run も rsync の --dry-run で動くので同じものが要る
_REQUIRED_COMMANDS: tuple[str, ...] = (DU_COMMAND, RSYNC_COMMAND)

logger = logging.getLogger("backup_tool")


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    parsed = parser.parse_args(argv)

    config_path = _resolve_config_path(parsed.config)
    if not config_path.is_file():
        print(_missing_config_message(config_path), file=sys.stderr)
        return int(ExitCode.NOT_STARTED)

    try:
        config = load_config(config_path.read_bytes())
    except ConfigError as err:
        print(f"設定ファイルが不正です: {err}", file=sys.stderr)
        return int(ExitCode.NOT_STARTED)

    # ログの準備と確認プロンプトより前に止め、始まらなかった実行の痕跡を残さない
    missing = _missing_commands()
    if missing:
        print(f"エラー: 必要なコマンドが見つかりません: {', '.join(missing)}", file=sys.stderr)
        return int(ExitCode.NOT_STARTED)

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
        return int(ExitCode.NOT_STARTED)

    exit_code = run_backup(config, dry_run=parsed.dry_run, logger=logger)
    logger.info("========== バックアップセッション終了 (exit=%d) ==========", int(exit_code))
    return int(exit_code)


class _ArgumentParser(argparse.ArgumentParser):
    """引数の誤りを argparse 既定の2ではなく、実行が始まらなかったことを示す終了コードで終える。

    2は「一部のペアが失敗」に割り当てているので、引数の誤りと区別できなくなる。
    """

    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(int(ExitCode.NOT_STARTED), f"{self.prog}: error: {message}\n")


def _missing_commands() -> list[str]:
    return [name for name in _REQUIRED_COMMANDS if shutil.which(name) is None]


def _build_parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
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
        f"backup.example.toml をコピーして {path.name} を作成してください"
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
