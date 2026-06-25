"""config.load_config のテスト。

TOML の読み込み・バリデーション・デフォルト値適用を検証する。
副作用レイヤーは含まない（ファイル I/O は呼び出し元の責務）。
"""

from __future__ import annotations

import pytest

from backup_tool.config import BackupPair, Config, ConfigError, load_config


class TestLoadConfig:
    def test_loads_full_config(self) -> None:
        toml = """
minimum_free_space_gb = 100
log_retention_days = 90
log_base_dir = "/Volumes/Primary/.backup_logs"
error_behavior = "stop"
additional_excludes = ["*.tmp", "cache/"]

[[backup_pairs]]
name = "メインSSD"
source = "/Volumes/Primary"
destination = "/Volumes/Secondary"
excludes = ["node_modules"]
""".encode()
        config = load_config(toml)
        assert config == Config(
            minimum_free_space_gb=100,
            log_retention_days=90,
            log_base_dir="/Volumes/Primary/.backup_logs",
            error_behavior="stop",
            additional_excludes=("*.tmp", "cache/"),
            backup_pairs=(
                BackupPair(
                    name="メインSSD",
                    source="/Volumes/Primary",
                    destination="/Volumes/Secondary",
                    excludes=("node_modules",),
                ),
            ),
        )

    def test_applies_defaults(self) -> None:
        toml = b"""
minimum_free_space_gb = 50
log_retention_days = 30

[[backup_pairs]]
name = "test"
source = "/Volumes/A"
destination = "/Volumes/B"
"""
        config = load_config(toml)
        assert config.log_base_dir is None
        assert config.error_behavior == "continue"
        assert config.additional_excludes == ()
        assert config.backup_pairs[0].excludes == ()

    def test_handles_multiple_backup_pairs(self) -> None:
        toml = b"""
minimum_free_space_gb = 100
log_retention_days = 90

[[backup_pairs]]
name = "pair1"
source = "/Volumes/A"
destination = "/Volumes/B"

[[backup_pairs]]
name = "pair2"
source = "/Volumes/C"
destination = "/Volumes/D"
"""
        config = load_config(toml)
        assert len(config.backup_pairs) == 2
        assert config.backup_pairs[0].name == "pair1"
        assert config.backup_pairs[1].name == "pair2"


class TestValidation:
    def test_rejects_invalid_toml_syntax(self) -> None:
        with pytest.raises(ConfigError, match="TOML"):
            load_config(b"not = valid = toml")

    def test_requires_minimum_free_space_gb(self) -> None:
        toml = b"""
log_retention_days = 90
[[backup_pairs]]
name = "x"
source = "/Volumes/A"
destination = "/Volumes/B"
"""
        with pytest.raises(ConfigError, match="minimum_free_space_gb"):
            load_config(toml)

    def test_requires_log_retention_days(self) -> None:
        toml = b"""
minimum_free_space_gb = 100
[[backup_pairs]]
name = "x"
source = "/Volumes/A"
destination = "/Volumes/B"
"""
        with pytest.raises(ConfigError, match="log_retention_days"):
            load_config(toml)

    def test_requires_at_least_one_backup_pair(self) -> None:
        toml = b"""
minimum_free_space_gb = 100
log_retention_days = 90
backup_pairs = []
"""
        with pytest.raises(ConfigError, match="backup_pairs"):
            load_config(toml)

    def test_rejects_missing_backup_pair_field(self) -> None:
        toml = b"""
minimum_free_space_gb = 100
log_retention_days = 90
[[backup_pairs]]
name = "x"
source = "/Volumes/A"
"""
        with pytest.raises(ConfigError, match="destination"):
            load_config(toml)

    def test_rejects_invalid_error_behavior(self) -> None:
        toml = b"""
minimum_free_space_gb = 100
log_retention_days = 90
error_behavior = "panic"
[[backup_pairs]]
name = "x"
source = "/Volumes/A"
destination = "/Volumes/B"
"""
        with pytest.raises(ConfigError, match="error_behavior"):
            load_config(toml)

    def test_rejects_wrong_type_for_numeric_field(self) -> None:
        toml = b"""
minimum_free_space_gb = "100"
log_retention_days = 90
[[backup_pairs]]
name = "x"
source = "/Volumes/A"
destination = "/Volumes/B"
"""
        with pytest.raises(ConfigError, match="minimum_free_space_gb"):
            load_config(toml)

    def test_rejects_negative_minimum_free_space_gb(self) -> None:
        toml = b"""
minimum_free_space_gb = -1
log_retention_days = 90
[[backup_pairs]]
name = "x"
source = "/Volumes/A"
destination = "/Volumes/B"
"""
        with pytest.raises(ConfigError, match="minimum_free_space_gb"):
            load_config(toml)

    def test_rejects_empty_backup_pair_name(self) -> None:
        toml = b"""
minimum_free_space_gb = 100
log_retention_days = 90
[[backup_pairs]]
name = ""
source = "/Volumes/A"
destination = "/Volumes/B"
"""
        with pytest.raises(ConfigError, match="name"):
            load_config(toml)
