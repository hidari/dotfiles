"""旧 backup.conf (Bash) → backup.toml 変換のテスト。"""

from __future__ import annotations

from pathlib import Path

import pytest

from backup_tool.config import BackupPair, Config, load_config
from backup_tool.migrate import MigrationError, migrate_file, parse_bash_conf, to_toml_string

SAMPLE_CONF = """
# コメント行
MINIMUM_FREE_SPACE_GB=100
LOG_RETENTION_DAYS=90
LOG_BASE_DIR="/Volumes/Primary/.backup_logs"
ERROR_BEHAVIOR="stop"

BACKUP_PAIRS=(
    "メインSSD|/Volumes/Primary|/Volumes/Secondary"
    "写真|/Volumes/Data/Photos|/Volumes/Backup/Photos|*.tmp,cache/"
)

ADDITIONAL_EXCLUDE=(
    "node_modules"
    ".venv"
)
"""


class TestParseBashConf:
    def test_parses_full_example(self) -> None:
        config = parse_bash_conf(SAMPLE_CONF)
        assert config == Config(
            minimum_free_space_gb=100,
            log_retention_days=90,
            log_base_dir="/Volumes/Primary/.backup_logs",
            error_behavior="stop",
            additional_excludes=("node_modules", ".venv"),
            backup_pairs=(
                BackupPair(
                    name="メインSSD",
                    source="/Volumes/Primary",
                    destination="/Volumes/Secondary",
                    excludes=(),
                ),
                BackupPair(
                    name="写真",
                    source="/Volumes/Data/Photos",
                    destination="/Volumes/Backup/Photos",
                    excludes=("*.tmp", "cache/"),
                ),
            ),
        )

    def test_handles_minimal_config(self) -> None:
        text = """
MINIMUM_FREE_SPACE_GB=50
LOG_RETENTION_DAYS=30
BACKUP_PAIRS=(
    "p|/Volumes/A|/Volumes/B"
)
"""
        config = parse_bash_conf(text)
        assert config.log_base_dir is None
        assert config.error_behavior == "continue"
        assert config.additional_excludes == ()
        assert len(config.backup_pairs) == 1

    def test_skips_comments_in_array(self) -> None:
        text = """
MINIMUM_FREE_SPACE_GB=100
LOG_RETENTION_DAYS=90
BACKUP_PAIRS=(
    # これはコメント
    "p|/Volumes/A|/Volumes/B"
)
"""
        config = parse_bash_conf(text)
        assert len(config.backup_pairs) == 1

    def test_raises_on_malformed_pair(self) -> None:
        text = """
MINIMUM_FREE_SPACE_GB=100
LOG_RETENTION_DAYS=90
BACKUP_PAIRS=(
    "名前だけで壊れてる"
)
"""
        with pytest.raises(MigrationError, match="BACKUP_PAIRS"):
            parse_bash_conf(text)

    def test_raises_when_required_missing(self) -> None:
        text = """
LOG_RETENTION_DAYS=90
BACKUP_PAIRS=(
    "p|/Volumes/A|/Volumes/B"
)
"""
        with pytest.raises(MigrationError, match="MINIMUM_FREE_SPACE_GB"):
            parse_bash_conf(text)


class TestToTomlString:
    def test_roundtrips_through_load_config(self) -> None:
        config = Config(
            minimum_free_space_gb=100,
            log_retention_days=90,
            log_base_dir="/Volumes/Primary/.backup_logs",
            error_behavior="stop",
            additional_excludes=("node_modules",),
            backup_pairs=(
                BackupPair(
                    name="メインSSD",
                    source="/Volumes/Primary",
                    destination="/Volumes/Secondary",
                    excludes=("*.tmp",),
                ),
            ),
        )
        toml_str = to_toml_string(config)
        # 生成された TOML を load_config でロードし直して同値性を確認
        assert load_config(toml_str.encode("utf-8")) == config

    def test_omits_log_base_dir_when_none(self) -> None:
        config = Config(
            minimum_free_space_gb=50,
            log_retention_days=30,
            backup_pairs=(BackupPair(name="p", source="/Volumes/A", destination="/Volumes/B"),),
        )
        toml_str = to_toml_string(config)
        assert "log_base_dir" not in toml_str


class TestMigrateFile:
    def test_creates_toml_and_backs_up_conf(self, tmp_path: Path) -> None:
        conf = tmp_path / "backup.conf"
        conf.write_text(SAMPLE_CONF)
        dst = tmp_path / "backup.toml"

        migrate_file(src=conf, dst=dst)

        assert dst.exists()
        backup = tmp_path / "backup.conf.bak"
        assert backup.exists()
        # 新旧ファイルとも存在 (旧 backup.conf はリネーム済み)
        assert not conf.exists()

    def test_refuses_to_overwrite_existing_toml(self, tmp_path: Path) -> None:
        conf = tmp_path / "backup.conf"
        conf.write_text(SAMPLE_CONF)
        dst = tmp_path / "backup.toml"
        dst.write_text("existing = true\n")

        with pytest.raises(MigrationError, match="既に存在"):
            migrate_file(src=conf, dst=dst)

    def test_errors_when_source_missing(self, tmp_path: Path) -> None:
        with pytest.raises(MigrationError, match="見つかりません"):
            migrate_file(src=tmp_path / "missing.conf", dst=tmp_path / "backup.toml")
