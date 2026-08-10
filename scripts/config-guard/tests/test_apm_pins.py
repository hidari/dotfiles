"""apm_pins の仕様テスト。

依存指定の分解 (pure) と、apm.yml を読む検査 (実ファイル) を検証する。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.apm_pins import (
    APM_LOCK_PATH,
    APM_MANIFEST_PATH,
    check_apm_pins,
    parse_dependency,
)
from tests.conftest import REPO_ROOT


def _write_manifest(repo_root: Path, deps: list[str]) -> None:
    path = repo_root / APM_MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "name: t\ndependencies:\n  apm:\n"
    for dep in deps:
        body += f"  - {dep}\n"
    body += "  mcp: []\n"
    path.write_text(body, encoding="utf-8")


# -----------------------------------------------------------------------------
# parse_dependency (pure)
# -----------------------------------------------------------------------------


def test_parse_dependency_splits_repo_and_ref() -> None:
    # リポジトリは先頭 2 要素。残りはリポジトリ内のパスなので repo の同一判定には使わない
    assert parse_dependency("mizchi/skills/testing/playwright-cli#abc123") == (
        "mizchi/skills",
        "testing/playwright-cli",
        "abc123",
    )


def test_parse_dependency_handles_repo_root_package() -> None:
    # パスを持たない形。2 要素ちょうどでも壊れないこと
    assert parse_dependency("owner/repo#v1.0.0") == ("owner/repo", "", "v1.0.0")


def test_parse_dependency_reports_missing_ref_as_none() -> None:
    # ref 無しは「浮動」であって「解析不能」ではない。repo は取れる
    assert parse_dependency("mizchi/skills/tooling/herdr") == (
        "mizchi/skills",
        "tooling/herdr",
        None,
    )


def test_parse_dependency_rejects_specs_without_owner() -> None:
    # owner/repo の 2 要素に満たない形は repo を決められない。素通りさせず None を返す
    for spec in ("skills#abc123", "#abc123", ""):
        assert parse_dependency(spec) == (None, None, None), spec


def test_parse_dependency_keeps_ref_containing_slash() -> None:
    # ブランチ名は slash を含みうる (feat/foo)。ref 側で最初の # のみを区切りにする
    assert parse_dependency("owner/repo/path#feat/foo") == ("owner/repo", "path", "feat/foo")


def test_parse_dependency_treats_empty_ref_as_missing() -> None:
    # 末尾 # だけの形。空文字を ref として扱うと一致判定が空同士で通ってしまう
    assert parse_dependency("owner/repo/path#") == ("owner/repo", "path", None)


# -----------------------------------------------------------------------------
# check_apm_pins (実ファイル)
# -----------------------------------------------------------------------------


def test_check_apm_pins_flags_ref_mismatch_within_one_repo(tmp_path: Path) -> None:
    # 検出したい本体。1 行だけ更新し忘れた形
    _write_manifest(
        tmp_path,
        [
            "owner/repo/a#aaaaaaa",
            "owner/repo/b#aaaaaaa",
            "owner/repo/c#bbbbbbb",
        ],
    )

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].source == APM_MANIFEST_PATH
    assert findings[0].detail == "owner/repo: aaaaaaa (2), bbbbbbb (1)"
    assert "一致しません" in findings[0].message


def test_check_apm_pins_passes_when_every_repo_is_consistent(tmp_path: Path) -> None:
    # false positive 防止。リポジトリが違えば ref が違うのは正常
    _write_manifest(
        tmp_path,
        [
            "owner/one/a#aaaaaaa",
            "owner/one/b#aaaaaaa",
            "owner/two/c#bbbbbbb",
        ],
    )

    assert check_apm_pins(str(tmp_path)) == []


def test_check_apm_pins_flags_dependency_without_ref(tmp_path: Path) -> None:
    # ref 無しは既定ブランチへ浮動する。install した時期で中身が変わる
    _write_manifest(tmp_path, ["owner/repo/a#aaaaaaa", "owner/other/b"])

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == "owner/other/b"
    assert "ref が指定されていません" in findings[0].message
    assert "一致しません" not in findings[0].message


def test_check_apm_pins_does_not_double_report_unpinned_as_mismatch(tmp_path: Path) -> None:
    # ref 無しは浮動として 1 件だけ報告する。None を ref の一種として一致判定へ
    # 流すと、同じ行が「浮動」と「不一致」の 2 件になり原因が読み取りにくくなる
    _write_manifest(tmp_path, ["owner/repo/a#aaaaaaa", "owner/repo/b"])

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert "ref が指定されていません" in findings[0].message


def test_check_apm_pins_reports_unparsable_spec_as_undecidable(tmp_path: Path) -> None:
    # 「浮動」ではなく「判定できない」として報告する。混同すると原因を取り違える
    _write_manifest(tmp_path, ["justaname#aaaaaaa"])

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == "justaname#aaaaaaa"
    assert "判定できません" in findings[0].message
    assert "浮動" not in findings[0].message


def test_check_apm_pins_reports_non_string_entry(tmp_path: Path) -> None:
    path = tmp_path / APM_MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("name: t\ndependencies:\n  apm:\n  - {a: 1}\n  mcp: []\n", encoding="utf-8")

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert "判定できません" in findings[0].message


def test_check_apm_pins_reports_non_list_dependencies(tmp_path: Path) -> None:
    # valid な YAML だが apm が list でない形。crash させず Finding にする
    path = tmp_path / APM_MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("name: t\ndependencies:\n  apm: oops\n", encoding="utf-8")

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert "リストではない" in findings[0].message


def test_check_apm_pins_preserves_manifest_order(tmp_path: Path) -> None:
    # findings を apm.yml の行順で読めるようにする (並べ替えない)
    _write_manifest(tmp_path, ["owner/one/a", "owner/two/b"])

    findings = check_apm_pins(str(tmp_path))

    assert [f.detail for f in findings] == ["owner/one/a", "owner/two/b"]


def test_check_apm_pins_without_manifest(tmp_path: Path) -> None:
    # apm 未使用のリポジトリでも落ちない
    assert check_apm_pins(str(tmp_path)) == []


def test_check_apm_pins_without_apm_dependencies(tmp_path: Path) -> None:
    path = tmp_path / APM_MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("name: t\ndependencies:\n  mcp: []\n", encoding="utf-8")

    assert check_apm_pins(str(tmp_path)) == []


# -----------------------------------------------------------------------------
# apm.lock.yaml との突き合わせ
# -----------------------------------------------------------------------------


def _write_lock(repo_root: Path, entries: list[tuple[str, str, str]]) -> None:
    path = repo_root / APM_LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "lockfile_version: '1'\ndependencies:\n"
    for repo, virtual_path, ref in entries:
        body += f"- repo_url: {repo}\n  virtual_path: {virtual_path}\n  resolved_ref: {ref}\n"
    path.write_text(body, encoding="utf-8")


def test_check_apm_pins_flags_manifest_ahead_of_lock(tmp_path: Path) -> None:
    # 宣言だけ更新して apm install を忘れた形。install は走っていないので
    # 配置済みの実体は古いままだが、apm.yml だけ見ても気づけない
    _write_manifest(tmp_path, ["owner/repo/a#newnew"])
    _write_lock(tmp_path, [("owner/repo", "a", "oldold")])

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].source == APM_LOCK_PATH
    assert findings[0].detail == "owner/repo/a: apm.yml=newnew lock=oldold"
    assert "配置済みの実体" in findings[0].message


def test_check_apm_pins_passes_when_lock_agrees(tmp_path: Path) -> None:
    _write_manifest(tmp_path, ["owner/repo/a#same", "owner/repo/b#same"])
    _write_lock(tmp_path, [("owner/repo", "a", "same"), ("owner/repo", "b", "same")])

    assert check_apm_pins(str(tmp_path)) == []


def test_check_apm_pins_flags_dependency_absent_from_lock(tmp_path: Path) -> None:
    # 依存を足して install していない形。lock に無い = 配置されていない
    _write_manifest(tmp_path, ["owner/repo/a#same", "owner/repo/b#same"])
    _write_lock(tmp_path, [("owner/repo", "a", "same")])

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == "owner/repo/b"
    assert "lock に対応する項目がありません" in findings[0].message


def test_check_apm_pins_covers_a_single_package_repo_through_the_lock(tmp_path: Path) -> None:
    # 一致検査は比較対象が要るので単独パッケージのリポジトリを覆えない。
    # lock との突き合わせがその範囲を埋めることを pin する
    _write_manifest(tmp_path, ["owner/solo/a#newnew"])
    _write_lock(tmp_path, [("owner/solo", "a", "oldold")])

    findings = check_apm_pins(str(tmp_path))

    assert [f.source for f in findings] == [APM_LOCK_PATH]


def test_check_apm_pins_skips_lock_comparison_when_lock_is_absent(tmp_path: Path) -> None:
    # lock を持たないリポジトリでも落ちない。突き合わせだけを飛ばす
    _write_manifest(tmp_path, ["owner/repo/a#aaaaaaa", "owner/repo/b#bbbbbbb"])

    findings = check_apm_pins(str(tmp_path))

    assert [f.source for f in findings] == [APM_MANIFEST_PATH]


def test_repo_apm_lock_matches_the_manifest() -> None:
    # 実リポジトリの drift ガード。宣言と実配置がずれたまま commit されるのを止める
    assert (REPO_ROOT / APM_LOCK_PATH).is_file(), "apm.lock.yaml が想定パスに無い"

    assert [f for f in check_apm_pins(str(REPO_ROOT)) if f.source == APM_LOCK_PATH] == []


def test_repo_apm_manifest_pins_every_repo_consistently() -> None:
    # 実リポジトリの drift ガード。同一リポを指す行が複数あり、hash は literal で
    # 並ぶため、1 行の更新漏れは「そのパッケージだけ古い版が静かに配られる」形で壊れる
    assert (REPO_ROOT / APM_MANIFEST_PATH).is_file(), "apm.yml が想定パスに無い"

    assert check_apm_pins(str(REPO_ROOT)) == []


def test_repo_apm_manifest_actually_has_a_shared_repo_group() -> None:
    # 上のガードが空振りでないことの対照。同一リポを指す行が 2 行以上無ければ
    # 一致検査は何も見ていないので、空の緑を健全と誤読することになる
    import yaml

    manifest = yaml.safe_load((REPO_ROOT / APM_MANIFEST_PATH).read_text(encoding="utf-8"))
    repos = [parse_dependency(dep).repo for dep in manifest["dependencies"]["apm"]]
    duplicated = {repo for repo in repos if repos.count(repo) > 1}

    assert duplicated, "同一リポを指す行が無く、一致検査が対象ゼロで緑になっている"
