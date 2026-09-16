#!/usr/bin/env bats
# =============================================================================
# 不在コマンドのガード (require_command_or_skip / skip_uncovered) の契約を pin する
#
# この 2 つは「CI の緑がそのファイルを検証した証拠になる」ための堰なので、挙動そのものを
# 検査対象にする。skip は呼んだテスト自身を skip させてしまい同一プロセスでは観測できない
# ため、fixtures/guards/ の .bats を子プロセスとして起動し TAP 出力と終了コードで見る。
# bats はディレクトリを既定で再帰しないので fixtures 配下は本スイートに拾われない。
#
# 注意:
# - bats は @test 名を関数名へエンコードするため名前は ASCII に限る
#   (rules/bats-test-name-ascii-only.yml)
# - CI 変数は親から継承されるので、ローカル側の枝を見るテストは env CI= で明示的に空にする
# =============================================================================

load test_helper

GUARDS_DIR="$TEST_DIR/fixtures/guards"

# fixture を子 bats として TAP で走らせる。
run_guard_fixture() {
    local ci_value="$1"
    local fixture="$2"
    run env CI="$ci_value" bats --formatter tap "$GUARDS_DIR/$fixture"
}

@test "require_command_or_skip: a declared and present command runs the body" {
    run_guard_fixture "" require-declared-present.bats

    [ "$status" -eq 0 ]
    assert_contains "$output" "ok 1"
    refute_contains "$output" "# skip"
}

@test "require_command_or_skip: a declared but absent command skips outside CI" {
    run_guard_fixture "" require-declared-absent.bats

    # 本体は false なので、走っていれば必ず赤くなる。緑はガードが手前で止めた証拠
    [ "$status" -eq 0 ]
    assert_contains "$output" "# skip"
    assert_contains "$output" "definitely-not-installed-probe"
}

@test "require_command_or_skip: a declared but absent command fails in CI" {
    run_guard_fixture "true" require-declared-absent.bats

    [ "$status" -ne 0 ]
    assert_contains "$output" "CI では必須"
}

@test "require_command_or_skip: an undeclared command is rejected outside CI too" {
    # 宣言の射程を外れた使い方は環境によらず落とす。ローカルで素通りすると、
    # CI で初めて「正当な不在なのに赤い」形で露見する
    run_guard_fixture "" require-undeclared.bats

    [ "$status" -ne 0 ]
    assert_contains "$output" "CI_BATS_JOB_COMMANDS"
    assert_contains "$output" "skip_uncovered"
}

@test "skip_uncovered: a declared command skips with the marker and its reason" {
    run_guard_fixture "true" skip-uncovered-declared.bats

    # CI でも skip されることがこの入口の意味。本体の false に到達すれば赤くなる
    [ "$status" -eq 0 ]
    assert_contains "$output" "# skip $UNCOVERED_SKIP_MARKER osacompile:"
    assert_contains "$output" "macOS"
}

@test "skip_uncovered: an undeclared command is rejected" {
    run_guard_fixture "" skip-uncovered-undeclared.bats

    [ "$status" -ne 0 ]
    assert_contains "$output" "UNCOVERED_DEPENDENCIES"
}

@test "require_command_for_file_setup: a present command lets the bodies read the cache" {
    run_guard_fixture "" file-setup-present.bats

    [ "$status" -eq 0 ]
    refute_contains "$output" "# skip"
    assert_contains "$output" "ok 2"
}

@test "require_command_for_file_setup: an absent command skips the bodies outside CI" {
    # 本体は false なので、走っていれば赤くなる。緑はガードが手前で止めた証拠
    run_guard_fixture "" file-setup-absent.bats

    [ "$status" -eq 0 ]
    assert_contains "$output" "# skip"
    assert_contains "$output" "definitely-not-installed-probe"
}

@test "require_command_for_file_setup: an absent command fails the whole file in CI" {
    run_guard_fixture "true" file-setup-absent.bats

    [ "$status" -ne 0 ]
    assert_contains "$output" "CI では必須"
}

@test "file_setup_ready_or_skip: an unset flag skips instead of running the body" {
    # setup_file がガードを呼び忘れた形。未設定を準備済みと読むと、キャッシュを
    # 作っていないのに全テストが走って別の理由で赤くなり、原因を取り違える
    run_guard_fixture "" file-setup-unguarded.bats

    [ "$status" -eq 0 ]
    assert_contains "$output" "# skip"
}

@test "the declared tables are non-empty" {
    # 表が空だと require_command_or_skip が全件を拒み、skip_uncovered も全件を拒む。
    # どちらも「落ちる」側なので気づけはするが、表を空にした変更が
    # 「ガードが厳しくなっただけ」に見えるのを防ぐために件数を固定する
    [ "${#CI_BATS_JOB_COMMANDS[@]}" -gt 0 ]
    [ "${#UNCOVERED_DEPENDENCIES[@]}" -gt 0 ]
}

@test "every declared entry carries a non-empty command name" {
    # 区切り記法を崩したエントリは、照合が常に偽になって静かに全件を拒む側へ倒れる。
    # 空のキーを混ぜても表の件数は変わらないので、件数の検査では見えない
    local entry
    for entry in "${CI_BATS_JOB_COMMANDS[@]}"; do
        [ -n "${entry%%:*}" ]
        # kind と source まで揃っていること (2 つのコロンが要る)
        assert_contains "$entry" ":"
        local rest="${entry#*:}"
        assert_contains "$rest" ":"
    done

    for entry in "${UNCOVERED_DEPENDENCIES[@]}"; do
        [ -n "${entry%%:*}" ]
        [ -n "${entry#*:}" ]
    done
}
