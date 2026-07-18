"""mise_pins の仕様テスト。

exact 判定(pure)と、mise config を読む検査(実ファイル)を検証する。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.mise_pins import (
    MISE_CONFIG_PATH,
    check_mise_pins,
    is_exact_version,
)


def _write_config(repo_root: Path, body: str) -> None:
    path = repo_root / MISE_CONFIG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


# --- is_exact_version (pure) -------------------------------------------------


def test_is_exact_version_accepts_full_versions() -> None:
    # リポジトリで実際に使っている pin 形。ここが false になると正当な pin を弾く
    for spec in ("24.18.0", "10.32.1", "0.3.3", "1.56.0"):
        assert is_exact_version(spec), spec


def test_is_exact_version_accepts_prerelease() -> None:
    # prerelease を exact として認めないと、正当な pin を弾いて guard が邪魔になる
    assert is_exact_version("1.0.0-rc.1")


def test_is_exact_version_rejects_floating_specs() -> None:
    # 検出したい本体。どれか 1 つでも通ると drift が素通りする
    for spec in ("latest", "lts", "1", "1.56", "~1.2", "^1", ">=1.0", "1.x", ""):
        assert not is_exact_version(spec), spec


def test_is_exact_version_rejects_non_version_sources() -> None:
    # mise は ref:/path:/sub- 等も解釈する。これらは版が固定されないので exact ではない
    for spec in ("ref:main", "path:/opt/tool", "sub-1:latest", "prefix:1.2"):
        assert not is_exact_version(spec), spec


# --- check_mise_pins (実ファイル) --------------------------------------------


def test_check_mise_pins_flags_floating_pin(tmp_path: Path) -> None:
    _write_config(tmp_path, '[tools]\njust = "latest"\nnode = "24.18.0"\n')

    findings = check_mise_pins(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == 'just = "latest"'
    assert findings[0].source == MISE_CONFIG_PATH


def test_check_mise_pins_passes_all_exact(tmp_path: Path) -> None:
    # false positive 防止。exact だけの config を汚点扱いしない
    _write_config(tmp_path, '[tools]\nnode = "24.18.0"\npnpm = "10.32.1"\n')

    assert check_mise_pins(str(tmp_path)) == []


def test_check_mise_pins_flags_non_string_spec(tmp_path: Path) -> None:
    # 複数版指定やテーブル指定は「exact ではない」ではなく「判定できない」。
    # 素通りさせると false negative になるため明示的に検出する
    _write_config(tmp_path, '[tools]\nnode = ["24.18.0", "22.0.0"]\n')

    findings = check_mise_pins(str(tmp_path))

    assert len(findings) == 1
    assert "node" in findings[0].detail


def test_check_mise_pins_without_tools_table(tmp_path: Path) -> None:
    _write_config(tmp_path, "[settings]\nexperimental = true\n")

    assert check_mise_pins(str(tmp_path)) == []


def test_check_mise_pins_without_config_file(tmp_path: Path) -> None:
    # mise 未使用のリポジトリでも落ちない
    assert check_mise_pins(str(tmp_path)) == []


def test_repo_mise_config_pins_every_tool_exactly() -> None:
    # 実リポジトリの drift ガード。config.toml が宣言する「exact 指定で全マシンを
    # 完全再現する」規約を、コメントではなくここで機械的に担保する
    repo_root = Path(__file__).resolve().parents[3]
    assert (repo_root / MISE_CONFIG_PATH).is_file(), "mise config が想定パスに無い"

    assert check_mise_pins(str(repo_root)) == []
