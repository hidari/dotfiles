"""tool_provisioning の仕様テスト。

要求の導出 (pre-commit の entry) / 供給の導出 (Brewfile と mise config) / 両者の
突き合わせを、それぞれ独立に検証する。実リポジトリに対する不変条件は末尾に置く。
"""

from __future__ import annotations

from pathlib import Path

from config_guard.mise_pins import MISE_CONFIG_PATH
from config_guard.tool_provisioning import (
    ALSO_REQUIRED,
    BREWFILE_PATH,
    NOT_PROVISIONED,
    PRECOMMIT_CONFIG_PATH,
    check_tool_provisioning,
    provided_commands,
    required_commands,
    uses_provisioning_manifests,
)
from tests.conftest import REPO_ROOT, write_file


def _precommit(*entries: str) -> str:
    hooks = "\n".join(
        f"      - id: hook-{index}\n"
        f"        name: hook {index}\n"
        f"        language: system\n"
        f"        entry: {entry}\n"
        for index, entry in enumerate(entries)
    )
    return f"repos:\n  - repo: local\n    hooks:\n{hooks}"


# -----------------------------------------------------------------------------
# required_commands: pre-commit の entry からの導出
# -----------------------------------------------------------------------------


def test_required_takes_the_first_token_of_entry(tmp_path: Path) -> None:
    write_file(tmp_path, PRECOMMIT_CONFIG_PATH, _precommit("ruff check src", "mypy src tests"))
    assert set(required_commands(str(tmp_path))) == {"ruff", "mypy"}


def test_required_reports_the_hook_id_as_origin(tmp_path: Path) -> None:
    # 報告に由来が無いと、どのフックのために足すのかが読み手に伝わらない
    write_file(tmp_path, PRECOMMIT_CONFIG_PATH, _precommit("ruff check src"))
    assert required_commands(str(tmp_path))["ruff"] == "hook-0"


def test_required_unwraps_the_shell_dash_c_body(tmp_path: Path) -> None:
    # ここを見ないと `bash -c '<tool> ...'` の形で要求が隠れる。実リポジトリでは
    # 本体の uv が他の entry からも入るため、この経路を壊しても結果が変わらない
    # (下流で吸収される)。独立に pin する
    write_file(tmp_path, PRECOMMIT_CONFIG_PATH, _precommit("bash -c 'hidden-tool --flag'"))
    assert set(required_commands(str(tmp_path))) == {"bash", "hidden-tool"}


def test_required_sees_commands_after_shell_operators(tmp_path: Path) -> None:
    # shlex.split は ; & | ( ) を区切らないので、素で使うと連結した 2 つ目以降が
    # コマンド位置として見えず、要求が静かに落ちる。今の .pre-commit-config.yaml に
    # 連結する entry は無いため実リポジトリでは差が出ない。独立に pin する
    write_file(
        tmp_path,
        PRECOMMIT_CONFIG_PATH,
        _precommit("first-tool a && second-tool b", "third-tool; fourth-tool", "fifth | sixth"),
    )
    assert set(required_commands(str(tmp_path))) == {
        "first-tool",
        "second-tool",
        "third-tool",
        "fourth-tool",
        "fifth",
        "sixth",
    }


def test_required_does_not_read_substitutions_as_commands(tmp_path: Path) -> None:
    # 演算子を独立トークンにすると `(` `)` も区切りになる。引数のクォートが効かないと
    # $(...) の中身をコマンド位置と誤読し、要求していないものを要求として報告する
    write_file(tmp_path, PRECOMMIT_CONFIG_PATH, _precommit('outer-tool "$(inner-tool --flag)"'))
    assert set(required_commands(str(tmp_path))) == {"outer-tool"}


def test_non_system_hooks_are_not_required(tmp_path: Path) -> None:
    # language: fail の entry は散文で、コマンドではない
    body = (
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: prose\n"
        "        name: prose\n"
        "        language: fail\n"
        "        entry: このファイルはここへ置く\n"
    )
    write_file(tmp_path, PRECOMMIT_CONFIG_PATH, body)
    assert required_commands(str(tmp_path)) == {}


def test_unterminated_quote_yields_no_requirement(tmp_path: Path) -> None:
    # 解釈できない形から要求をでっち上げると、存在しないコマンドを報告する
    write_file(tmp_path, PRECOMMIT_CONFIG_PATH, _precommit("bash -c 'unterminated"))
    assert required_commands(str(tmp_path)) == {}


def test_missing_precommit_config_yields_no_requirement(tmp_path: Path) -> None:
    assert required_commands(str(tmp_path)) == {}


# -----------------------------------------------------------------------------
# provided_commands: Brewfile と mise config からの導出
# -----------------------------------------------------------------------------


def test_both_brew_and_cask_lines_provide(tmp_path: Path) -> None:
    write_file(tmp_path, BREWFILE_PATH, 'brew "jq"\ncask "1password-cli"\n')
    assert provided_commands(str(tmp_path)) == {"jq", "1password-cli"}


def test_tap_qualified_names_are_reduced_to_the_command(tmp_path: Path) -> None:
    write_file(tmp_path, BREWFILE_PATH, 'brew "microsoft/apm/apm"\n')
    assert provided_commands(str(tmp_path)) == {"apm"}


def test_trailing_options_are_not_part_of_the_name(tmp_path: Path) -> None:
    write_file(tmp_path, BREWFILE_PATH, 'brew "yusukebe/tap/ax", trusted: true\n')
    assert provided_commands(str(tmp_path)) == {"ax"}


def test_commented_out_lines_do_not_provide(tmp_path: Path) -> None:
    # 行で読む以上、コメントの誤読 (phantom entry) がこのパーサ固有の壊れ方になる。
    # 供給側の phantom は「足したつもり」で検査を黙らせるので、要求側の漏れより悪い
    write_file(tmp_path, BREWFILE_PATH, '# brew "ghost"\n  # brew "ghost2"\nbrew "jq"\n')
    assert provided_commands(str(tmp_path)) == {"jq"}


def test_go_lines_do_not_provide(tmp_path: Path) -> None:
    # brew bundle がこの型を実体化するか未確認。数えると未検証の主張を検査が持つ
    write_file(tmp_path, BREWFILE_PATH, 'go "golang.org/x/tools/gopls"\nbrew "jq"\n')
    assert provided_commands(str(tmp_path)) == {"jq"}


def test_formula_names_map_to_their_commands(tmp_path: Path) -> None:
    # powershell は pwsh を、bats-core は bats を提供する。名前をそのまま使うと
    # 供給済みのものを「無い」と誤報する
    write_file(tmp_path, BREWFILE_PATH, 'brew "powershell"\nbrew "bats-core"\n')
    assert provided_commands(str(tmp_path)) == {"pwsh", "bats"}


def test_mise_tools_also_provide(tmp_path: Path) -> None:
    write_file(tmp_path, MISE_CONFIG_PATH, '[tools]\nnode = "24.18.0"\n')
    assert provided_commands(str(tmp_path)) == {"node"}


def test_mise_backend_prefix_is_reduced_to_the_command(tmp_path: Path) -> None:
    write_file(tmp_path, MISE_CONFIG_PATH, '[tools]\n"cargo:sqlx-cli" = "0.8.6"\n')
    assert provided_commands(str(tmp_path)) == {"sqlx-cli"}


# -----------------------------------------------------------------------------
# check_tool_provisioning: 突き合わせ
# -----------------------------------------------------------------------------

# ALSO_REQUIRED は entry に関係なく常に検査されるので、突き合わせの振る舞いを単独で
# 見るテストでは供給側にも置く。置かないと全ケースがその 3 件で赤くなり、何を見ている
# テストなのか区別できなくなる。ALSO_REQUIRED 自身の検査は専用のテストが持つ。
_ALSO_REQUIRED_FORMULAE = 'brew "tirith"\nbrew "bats-core"\nbrew "pre-commit"\n'


def _repo_with_required(root: Path, entry: str, brewfile: str) -> None:
    write_file(root, PRECOMMIT_CONFIG_PATH, _precommit(entry))
    write_file(root, BREWFILE_PATH, brewfile + _ALSO_REQUIRED_FORMULAE)


def test_unprovisioned_requirement_is_reported(tmp_path: Path) -> None:
    _repo_with_required(tmp_path, "orphan-tool check", 'brew "jq"\n')
    details = [f.detail for f in check_tool_provisioning(str(tmp_path))]
    assert "orphan-tool" in details


def test_provisioned_requirement_is_not_reported(tmp_path: Path) -> None:
    _repo_with_required(tmp_path, "jq --version", 'brew "jq"\n')
    assert [f.detail for f in check_tool_provisioning(str(tmp_path))] == []


def test_provisioning_from_mise_is_accepted(tmp_path: Path) -> None:
    # 供給経路は 2 つある。片方だけを見ると、もう片方にあるものを誤報する
    write_file(tmp_path, PRECOMMIT_CONFIG_PATH, _precommit("node --version"))
    write_file(tmp_path, BREWFILE_PATH, _ALSO_REQUIRED_FORMULAE)
    write_file(tmp_path, MISE_CONFIG_PATH, '[tools]\nnode = "24.18.0"\n')
    assert [f.detail for f in check_tool_provisioning(str(tmp_path))] == []


def test_os_provided_commands_are_not_required(tmp_path: Path) -> None:
    _repo_with_required(tmp_path, "bash -c 'jq --version'", 'brew "jq"\n')
    assert [f.detail for f in check_tool_provisioning(str(tmp_path))] == []


def test_pinned_extra_requirements_are_checked(tmp_path: Path) -> None:
    # pre-commit の entry には現れないが、欠けると検査層が無音になるもの。
    # 供給側に置かないリポジトリでは ALSO_REQUIRED の全件が報告されるはず
    write_file(tmp_path, PRECOMMIT_CONFIG_PATH, _precommit("jq --version"))
    write_file(tmp_path, BREWFILE_PATH, 'brew "jq"\n')
    reported = {f.detail.split(" ", 1)[0] for f in check_tool_provisioning(str(tmp_path))}
    assert reported == set(ALSO_REQUIRED)


def test_pinned_extra_findings_carry_their_reason(tmp_path: Path) -> None:
    # 理由が無いと、読み手が「要らないから消す」を選べてしまう
    write_file(tmp_path, PRECOMMIT_CONFIG_PATH, _precommit("jq --version"))
    write_file(tmp_path, BREWFILE_PATH, 'brew "jq"\n')
    for finding in check_tool_provisioning(str(tmp_path)):
        assert ALSO_REQUIRED[finding.detail.split(" ", 1)[0]] in finding.detail


def test_repo_without_provisioning_manifests_is_skipped(tmp_path: Path) -> None:
    # brew も mise も使わないリポジトリでこの供給モデルを要求すると誤報になる
    write_file(tmp_path, PRECOMMIT_CONFIG_PATH, _precommit("orphan-tool check"))
    assert check_tool_provisioning(str(tmp_path)) == []


# -----------------------------------------------------------------------------
# pin そのものの不変条件と実リポジトリ
# -----------------------------------------------------------------------------


def test_exemptions_and_extra_requirements_are_disjoint() -> None:
    # 同じ名前が両方にあると、要求しておきながら免除する矛盾になる
    assert not set(ALSO_REQUIRED) & set(NOT_PROVISIONED)


def test_silently_failing_extras_are_pinned_by_name() -> None:
    # ALSO_REQUIRED から名前が消えても、他のテストは期待値をこの dict 自身から導出して
    # いるため両辺が同時に縮んで緑のままになる (実測: tirith を消して 413 passed / rc 0)。
    # 欠けても実行時にエラーが出ない 3 つだけを literal で縛る。増やす分は自由。
    # とくに tirith は、不在時にフックが意図した fail-open へ倒れて検査そのものが
    # 無音になるので、この検査から外れると気づく手段が一つも残らない。
    assert {"tirith", "bats", "pre-commit"} <= set(ALSO_REQUIRED)


def test_real_repo_has_provisioning_manifests() -> None:
    # 対象判定の early return は宣言ファイルごと消したケースを見逃す。実リポジトリに
    # 対して存在を縛り、検査が丸ごと沈黙する形を塞ぐ
    assert uses_provisioning_manifests(str(REPO_ROOT))


def test_real_repo_has_requirements() -> None:
    # 0 件なら check は何も見ずに緑になる。下の回帰テストを vacuous にしない pin
    assert required_commands(str(REPO_ROOT))


def test_real_repo_has_provisions() -> None:
    assert provided_commands(str(REPO_ROOT))


def test_real_repo_provisions_every_requirement() -> None:
    findings = check_tool_provisioning(str(REPO_ROOT))
    assert findings == [], [f"{f.detail}: {f.message}" for f in findings]
