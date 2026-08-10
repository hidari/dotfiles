"""apm_pins の仕様テスト。

依存指定の分解 (pure)、apm.yml を読む検査、apm.lock.yaml との突き合わせを検証する。
"""

from __future__ import annotations

from pathlib import Path

import yaml

from config_guard.apm_pins import (
    APM_LOCK_PATH,
    APM_MANIFEST_PATH,
    check_apm_pins,
    load_lock_refs,
    parse_dependency,
)
from tests.conftest import REPO_ROOT

SHA = "d03931638f41a945e26e56407810d1adff872114"
OTHER_SHA = "8abbca2fc400c2ff4866248ba1ec9309b948812f"


def _write_manifest(repo_root: Path, deps: list[str]) -> None:
    path = repo_root / APM_MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "name: t\ndependencies:\n  apm:\n"
    for dep in deps:
        body += f"  - {dep}\n"
    body += "  mcp: []\n"
    path.write_text(body, encoding="utf-8")


def _write_lock(repo_root: Path, entries: list[tuple[str, str, str]]) -> None:
    """lock を書く。resolved_commit も書き、比較先が resolved_ref であることを pin する。"""
    path = repo_root / APM_LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "lockfile_version: '1'\ndependencies:\n"
    for repo, virtual_path, ref in entries:
        body += (
            f"- repo_url: {repo}\n"
            f"  virtual_path: {virtual_path}\n"
            f"  resolved_ref: {ref}\n"
            f"  resolved_commit: {OTHER_SHA}\n"
        )
    path.write_text(body, encoding="utf-8")


# -----------------------------------------------------------------------------
# parse_dependency (pure)
# -----------------------------------------------------------------------------


def test_parse_dependency_splits_github_shorthand() -> None:
    # 実際に使っている形。リポジトリは先頭 2 要素で、残りはリポジトリ内のパス
    assert parse_dependency("mizchi/skills/testing/playwright-cli#abc123") == (
        "github",
        "mizchi/skills",
        "testing/playwright-cli",
        "abc123",
    )


def test_parse_dependency_handles_repo_root_package() -> None:
    # パスを持たない形。2 要素ちょうどでも壊れないこと
    assert parse_dependency("owner/repo#v1.0.0") == ("github", "owner/repo", "", "v1.0.0")


def test_parse_dependency_reports_missing_ref_as_none() -> None:
    # ref 無しは「浮動」であって「解析不能」ではない。repo は取れる
    assert parse_dependency("mizchi/skills/tooling/herdr") == (
        "github",
        "mizchi/skills",
        "tooling/herdr",
        None,
    )


def test_parse_dependency_keeps_ref_containing_slash() -> None:
    # ブランチ名は slash を含みうる (feat/foo)。最初の # のみを区切りとする
    assert parse_dependency("owner/repo/path#feat/foo") == (
        "github",
        "owner/repo",
        "path",
        "feat/foo",
    )


def test_parse_dependency_treats_empty_ref_as_missing() -> None:
    # 末尾 # だけの形。空文字を ref として扱うと一致判定が空同士で通ってしまう
    assert parse_dependency("owner/repo/path#") == ("github", "owner/repo", "path", None)


def test_parse_dependency_classifies_a_non_github_host() -> None:
    # apm が受ける gitlab.com/org/repo 形。先頭 2 要素を repo とすると
    # gitlab.com/org が repo になり、別リポジトリを同じ群へ混ぜてしまう。
    # host を含む形は分類だけして検査対象から外す (lock の形を実測できていない)
    assert parse_dependency("gitlab.com/org/repo").kind == "hosted"
    assert parse_dependency("gitlab.com/org/repo/skills/x#abc").kind == "hosted"


def test_parse_dependency_classifies_a_local_path() -> None:
    # apm が受ける ./packages/my-skill 形。ref の概念が無いので浮動ではない
    for spec in ("./packages/my-skill", "../sibling/skill", "/abs/path/skill"):
        assert parse_dependency(spec).kind == "local", spec


def test_parse_dependency_rejects_specs_without_owner() -> None:
    # owner/repo の 2 要素に満たない形は分解できない。素通りさせず unknown にする
    for spec in ("skills#abc123", "#abc123", "", "justaname"):
        assert parse_dependency(spec).kind == "unknown", spec


# -----------------------------------------------------------------------------
# check_apm_pins: 形の検査
# -----------------------------------------------------------------------------


def test_check_apm_pins_flags_ref_mismatch_within_one_repo(tmp_path: Path) -> None:
    # 検出したい本体。1 行だけ更新し忘れた形
    _write_manifest(
        tmp_path,
        [f"owner/repo/a#{SHA}", f"owner/repo/b#{SHA}", f"owner/repo/c#{OTHER_SHA}"],
    )

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].source == APM_MANIFEST_PATH
    assert findings[0].detail == f"owner/repo: {SHA} (2), {OTHER_SHA} (1)"
    assert "一致しません" in findings[0].message


def test_check_apm_pins_passes_when_every_repo_is_consistent(tmp_path: Path) -> None:
    # false positive 防止。リポジトリが違えば ref が違うのは正常
    _write_manifest(
        tmp_path,
        [f"owner/one/a#{SHA}", f"owner/one/b#{SHA}", f"owner/two/c#{OTHER_SHA}"],
    )

    assert check_apm_pins(str(tmp_path)) == []


def test_check_apm_pins_flags_dependency_without_ref(tmp_path: Path) -> None:
    # ref 無しは既定ブランチへ浮動する。install した時期で中身が変わる
    _write_manifest(tmp_path, [f"owner/repo/a#{SHA}", "owner/other/b"])

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == "owner/other/b"
    assert "ref が指定されていません" in findings[0].message


def test_check_apm_pins_flags_a_branch_ref(tmp_path: Path) -> None:
    # README が宣言する不変条件は commit SHA pin。ブランチは付け替わるので
    # 「ref が在る」だけでは再現性を担保できない
    _write_manifest(tmp_path, ["owner/repo/a#main"])

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == "owner/repo/a#main"
    assert "commit SHA" in findings[0].message


def test_check_apm_pins_flags_a_tag_ref(tmp_path: Path) -> None:
    # tag も付け替え可能なので SHA ではない。README を緩める判断をするまでは弾く
    _write_manifest(tmp_path, ["owner/repo/a#v1.0.0"])

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].source == APM_MANIFEST_PATH
    assert findings[0].detail == "owner/repo/a#v1.0.0"
    assert "commit SHA" in findings[0].message


def test_check_apm_pins_rejects_a_short_or_uppercase_sha(tmp_path: Path) -> None:
    # 短縮 SHA は将来衝突しうる。大文字は lock の表記と突き合わなくなる。
    # 41 桁は fullmatch でなければ通ってしまう形 (先頭 40 桁が一致する)
    for ref in (SHA[:12], SHA.upper(), SHA + "0"):
        _write_manifest(tmp_path, [f"owner/repo/a#{ref}"])

        findings = check_apm_pins(str(tmp_path))

        assert len(findings) == 1, ref
        assert findings[0].source == APM_MANIFEST_PATH, ref
        assert findings[0].detail == f"owner/repo/a#{ref}", ref
        assert "commit SHA" in findings[0].message, ref


def test_check_apm_pins_skips_forms_it_cannot_cover(tmp_path: Path) -> None:
    # host 付きと local path は apm が受ける正規の形。偽陽性の赤を出さない。
    # always_run の pre-commit に配線されているので、偽陽性は全コミットを止める
    _write_manifest(tmp_path, ["gitlab.com/org/repo", "./packages/my-skill"])

    assert check_apm_pins(str(tmp_path)) == []


def test_check_apm_pins_skips_the_object_form(tmp_path: Path) -> None:
    # git:/path:/ref: のオブジェクト形も apm が受ける正規の形。dict を
    # 「文字列でない」として弾くと、正しい manifest に赤が出る
    path = tmp_path / APM_MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "name: t\ndependencies:\n  apm:\n"
        "  - git: git@gitlab.com:org/repo.git\n    path: skills/x\n    ref: main\n"
        "  mcp: []\n",
        encoding="utf-8",
    )

    assert check_apm_pins(str(tmp_path)) == []


def test_check_apm_pins_reports_an_unparsable_spec(tmp_path: Path) -> None:
    # どの正規形にも当てはまらない形は fail-closed で報告する
    _write_manifest(tmp_path, [f"justaname#{SHA}"])

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == f"justaname#{SHA}"
    assert "どの依存指定形にも当てはまらず" in findings[0].message


def test_check_apm_pins_reports_a_non_string_non_mapping_entry(tmp_path: Path) -> None:
    path = tmp_path / APM_MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("name: t\ndependencies:\n  apm:\n  - [1, 2]\n  mcp: []\n", encoding="utf-8")

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == "[1, 2]"
    assert "文字列でもマッピングでもなく" in findings[0].message


def test_check_apm_pins_reports_non_list_dependencies(tmp_path: Path) -> None:
    # valid な YAML だが apm が list でない形。crash させず Finding にする
    path = tmp_path / APM_MANIFEST_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("name: t\ndependencies:\n  apm: oops\n", encoding="utf-8")

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].source == APM_MANIFEST_PATH
    assert findings[0].detail == "apm: 'oops'"
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


def test_check_apm_pins_flags_manifest_ahead_of_lock(tmp_path: Path) -> None:
    # 宣言だけ更新して apm install を忘れた形。配置済みの実体は古いままだが
    # apm.yml だけ見ても気づけない
    _write_manifest(tmp_path, [f"owner/repo/a#{SHA}"])
    _write_lock(tmp_path, [("owner/repo", "a", OTHER_SHA)])

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].source == APM_LOCK_PATH
    assert findings[0].detail == f"owner/repo/a: apm.yml={SHA} lock={OTHER_SHA}"
    assert "配置済みの実体" in findings[0].message


def test_check_apm_pins_compares_against_resolved_ref_not_resolved_commit(
    tmp_path: Path,
) -> None:
    # _write_lock は resolved_commit に別の値を書く。実装が resolved_commit を
    # 見るように変わると、一致しているはずの組で赤くなる
    _write_manifest(tmp_path, [f"owner/repo/a#{SHA}"])
    _write_lock(tmp_path, [("owner/repo", "a", SHA)])

    assert check_apm_pins(str(tmp_path)) == []


def test_check_apm_pins_flags_dependency_absent_from_lock(tmp_path: Path) -> None:
    # 依存を足して install していない形。lock に無い = 配置されていない
    _write_manifest(tmp_path, [f"owner/repo/a#{SHA}", f"owner/repo/b#{SHA}"])
    _write_lock(tmp_path, [("owner/repo", "a", SHA)])

    findings = check_apm_pins(str(tmp_path))

    assert len(findings) == 1
    assert findings[0].detail == "owner/repo/b"
    assert "lock に対応する項目がありません" in findings[0].message


def test_check_apm_pins_covers_a_single_package_repo_through_the_lock(tmp_path: Path) -> None:
    # 一致検査は比較対象が要るので単独パッケージのリポジトリを覆えない。
    # lock との突き合わせがその範囲を埋めることを pin する
    _write_manifest(tmp_path, [f"owner/solo/a#{SHA}"])
    _write_lock(tmp_path, [("owner/solo", "a", OTHER_SHA)])

    assert [f.source for f in check_apm_pins(str(tmp_path))] == [APM_LOCK_PATH]


def test_check_apm_pins_skips_lock_comparison_when_lock_is_absent(tmp_path: Path) -> None:
    # lock を持たないリポジトリでも落ちない。突き合わせだけを飛ばす
    _write_manifest(tmp_path, [f"owner/repo/a#{SHA}", f"owner/repo/b#{OTHER_SHA}"])

    assert [f.source for f in check_apm_pins(str(tmp_path))] == [APM_MANIFEST_PATH]


def test_check_apm_pins_reports_an_unreadable_lock_instead_of_skipping(tmp_path: Path) -> None:
    # lock が在るのに形を認識できない場合、黙って突き合わせを飛ばすと
    # 「1 件も見ていない緑」になる。apm の版更新でキー名が変わる経路が実在する
    _write_manifest(tmp_path, [f"owner/repo/a#{SHA}"])
    path = tmp_path / APM_LOCK_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("lockfile_version: '1'\npackages: []\n", encoding="utf-8")

    findings = check_apm_pins(str(tmp_path))

    assert [f.source for f in findings] == [APM_LOCK_PATH]
    assert findings[0].detail == "dependencies"
    assert "突き合わせできません" in findings[0].message


# -----------------------------------------------------------------------------
# 実リポジトリのガードと、その対照
# -----------------------------------------------------------------------------


def _repo_manifest_entries() -> list[str]:
    manifest = yaml.safe_load((REPO_ROOT / APM_MANIFEST_PATH).read_text(encoding="utf-8"))
    entries = manifest["dependencies"]["apm"]
    assert isinstance(entries, list)
    return [str(entry) for entry in entries]


def test_repo_apm_manifest_and_lock_are_clean() -> None:
    # 実リポジトリの drift ガード。宣言どうしの整合と、宣言と実配置の整合を担保する
    assert (REPO_ROOT / APM_MANIFEST_PATH).is_file(), "apm.yml が想定パスに無い"
    assert (REPO_ROOT / APM_LOCK_PATH).is_file(), "apm.lock.yaml が想定パスに無い"

    assert check_apm_pins(str(REPO_ROOT)) == []


def test_repo_apm_manifest_has_a_shared_repo_group() -> None:
    # 群の一致検査が空振りでないことの対照。同一リポを指す行が 2 行以上無ければ
    # 一致検査は何も見ていないので、空の緑を健全と誤読することになる
    repos = [parse_dependency(dep).repo for dep in _repo_manifest_entries()]
    duplicated = {repo for repo in repos if repos.count(repo) > 1}

    assert duplicated, "同一リポを指す行が無く、一致検査が対象ゼロで緑になっている"


def test_repo_apm_lock_actually_covers_every_manifest_entry() -> None:
    # lock 突き合わせが空振りでないことの対照。群側と対になる。lock の形が変わると
    # 突き合わせが no-op になるので、実際に全件を突き合わせたことを数で確かめる
    lock_refs = load_lock_refs(REPO_ROOT / APM_LOCK_PATH)
    assert lock_refs is not None, "lock を読めておらず突き合わせが 0 件で緑になっている"

    entries = _repo_manifest_entries()
    keys = {(d.repo, d.path) for d in map(parse_dependency, entries)}

    assert keys <= set(lock_refs), "lock に無い manifest 項目がある"
    assert len(keys) == len(entries), "manifest に重複した (repo, path) がある"


def test_repo_apm_manifest_uses_only_the_covered_form() -> None:
    # この guard が覆うのは github shorthand だけ。host 付き / local path /
    # オブジェクト形を足すと黙って無検査になるため、足した時点で赤くして判断を促す
    kinds = {parse_dependency(dep).kind for dep in _repo_manifest_entries()}

    assert kinds == {"github"}, f"guard が覆わない依存指定形が入った: {kinds - {'github'}}"
