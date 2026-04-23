"""runner モジュールの純粋ヘルパーに対するテスト。

_execute_pair / _verify_path / _verify_capacity は副作用が重いので
統合テストで扱い、ここでは終了コード集約と excludes 合成のみを検証する。
"""

from __future__ import annotations

from backup_tool.config import BackupPair, Config
from backup_tool.runner import ExitCode, _build_excludes, _determine_exit_code


def _make_config(*, additional: tuple[str, ...] = ()) -> Config:
    return Config(
        minimum_free_space_gb=100,
        log_retention_days=90,
        additional_excludes=additional,
        backup_pairs=(BackupPair(name="p", source="/Volumes/A", destination="/Volumes/B"),),
    )


class TestDetermineExitCode:
    def test_all_success(self) -> None:
        assert _determine_exit_code(fail=0, total=3) == ExitCode.SUCCESS

    def test_partial_success_counts_as_success(self) -> None:
        # rsync code 23 は「部分的成功」で fail には入らない
        assert _determine_exit_code(fail=0, total=2) == ExitCode.SUCCESS

    def test_partial_failure(self) -> None:
        assert _determine_exit_code(fail=1, total=2) == ExitCode.PARTIAL_FAILURE

    def test_total_failure(self) -> None:
        assert _determine_exit_code(fail=3, total=3) == ExitCode.TOTAL_FAILURE


class TestBuildExcludes:
    def test_merges_default_additional_and_pair_excludes(self) -> None:
        config = _make_config(additional=("custom_a",))
        pair = BackupPair(
            name="p",
            source="/Volumes/A",
            destination="/Volumes/B",
            excludes=("pair_specific",),
        )
        result = _build_excludes(config=config, pair=pair)
        # DEFAULT_EXCLUDES (.DS_Store など) + additional + pair 固有
        assert ".DS_Store" in result
        assert "custom_a" in result
        assert "pair_specific" in result

    def test_preserves_order_default_additional_pair(self) -> None:
        config = _make_config(additional=("custom",))
        pair = BackupPair(
            name="p",
            source="/Volumes/A",
            destination="/Volumes/B",
            excludes=("pair_only",),
        )
        result = list(_build_excludes(config=config, pair=pair))
        # custom は全デフォルト除外リストの後
        custom_idx = result.index("custom")
        ds_store_idx = result.index(".DS_Store")
        pair_only_idx = result.index("pair_only")
        assert ds_store_idx < custom_idx < pair_only_idx
