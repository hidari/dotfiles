"""versions の仕様テスト。互換範囲の導出と更新分類を検証する。"""

from __future__ import annotations

from pathlib import Path

import pytest

from mise_update_notifier.versions import (
    ToolStatus,
    compatible_spec,
    has_compatible_update,
    has_major_update,
    read_pins,
)

# --- compatible_spec ---------------------------------------------------------


def test_compatible_spec_uses_major_for_stable_versions() -> None:
    # 1.0.0 以降は major が破壊的変更の軸
    assert compatible_spec("1.56.0") == "1"
    assert compatible_spec("24.18.0") == "24"


def test_compatible_spec_uses_major_minor_for_zero_versions() -> None:
    # semver の 0.x は minor が破壊的変更の軸。0.3.3 の互換範囲に 0.4.0 を含めない
    assert compatible_spec("0.3.3") == "0.3"
    assert compatible_spec("0.0.5") == "0.0"


def test_compatible_spec_handles_multi_digit_components() -> None:
    # patch が 2 桁以上でも導出できること (1 桁しか見ない実装への退行を防ぐ)
    assert compatible_spec("24.18.10") == "24"
    assert compatible_spec("0.12.34") == "0.12"


def test_compatible_spec_ignores_prerelease_and_build_metadata() -> None:
    assert compatible_spec("1.0.0-rc.1") == "1"
    assert compatible_spec("21.0.8+9") == "21"


def test_compatible_spec_rejects_unparsable_version() -> None:
    # exact pin ガードを通った版しか来ない前提だが、黙って壊れた spec を作らない
    for spec in ("latest", "1", "1.2", ""):
        with pytest.raises(ValueError):
            compatible_spec(spec)


# --- 更新分類 ----------------------------------------------------------------


def _status(pinned: str, compatible: str, absolute: str) -> ToolStatus:
    return ToolStatus(
        tool="demo", pinned=pinned, compatible_latest=compatible, absolute_latest=absolute
    )


def test_has_compatible_update_when_same_range_moved_ahead() -> None:
    assert has_compatible_update(_status("10.32.1", "10.34.5", "11.13.1"))


def test_has_no_compatible_update_when_pinned_is_range_latest() -> None:
    assert not has_compatible_update(_status("24.18.0", "24.18.0", "26.5.0"))


def test_has_major_update_when_absolute_exceeds_compatible() -> None:
    assert has_major_update(_status("24.18.0", "24.18.0", "26.5.0"))


def test_has_no_major_update_when_absolute_equals_compatible() -> None:
    # 完全に最新な状態。どちらの区分にも現れてはいけない
    status = _status("1.56.0", "1.56.0", "1.56.0")
    assert not has_compatible_update(status)
    assert not has_major_update(status)


def test_major_update_is_independent_of_compatible_update() -> None:
    # pnpm 型: 同メジャーにも更新があり、かつメジャー越えも存在する
    status = _status("10.32.1", "10.34.5", "11.13.1")
    assert has_compatible_update(status)
    assert has_major_update(status)


# --- read_pins ---------------------------------------------------------------


def test_read_pins_extracts_tools_table(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text('[tools]\njust = "1.56.0"\nnode = "24.18.0"\n', encoding="utf-8")

    assert read_pins(config) == {"just": "1.56.0", "node": "24.18.0"}


def test_read_pins_preserves_declaration_order(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text('[tools]\nzig = "1.0.0"\najv = "2.0.0"\n', encoding="utf-8")

    assert list(read_pins(config)) == ["zig", "ajv"]


def test_read_pins_rejects_non_string_spec(tmp_path: Path) -> None:
    # 判定できない形を黙って捨てると、そのツールだけ監視から静かに外れる
    config = tmp_path / "config.toml"
    config.write_text('[tools]\nnode = ["24.18.0", "22.0.0"]\n', encoding="utf-8")

    with pytest.raises(ValueError, match="node"):
        read_pins(config)


def test_read_pins_without_tools_table(tmp_path: Path) -> None:
    config = tmp_path / "config.toml"
    config.write_text("[settings]\nexperimental = true\n", encoding="utf-8")

    assert read_pins(config) == {}
