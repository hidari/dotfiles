#!/usr/bin/env bats
# =============================================================================
# 前提の不在を扱うガード (require_command_or_skip / skip_outside_ci) の契約を pin する
#
# このガードは「CI の緑がそのファイルを検証した証拠になる」ための堰なので、挙動そのものを
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

@test "require_command_or_skip: a present command runs the body" {
    run_guard_fixture "" require-present.bats

    [ "$status" -eq 0 ]
    assert_contains "$output" "ok 1"
    refute_contains "$output" "# skip"
}

@test "require_command_or_skip: an absent command skips outside CI" {
    run_guard_fixture "" require-absent.bats

    # 本体は false なので、走っていれば必ず赤くなる。緑はガードが手前で止めた証拠
    [ "$status" -eq 0 ]
    assert_contains "$output" "# skip definitely-not-installed-probe"
}

@test "require_command_or_skip: an absent command fails in CI" {
    run_guard_fixture "true" require-absent.bats

    [ "$status" -ne 0 ]
    refute_contains "$output" "# skip"
    assert_contains "$output" "definitely-not-installed-probe が見つからない (CI では必須)"
}

@test "a guard in setup_file skips every test in the file outside CI" {
    # setup_file の skip はファイル内の全テストの skip として出る。
    # 1 件でも本体が走れば false で赤くなり、0 件実行なら bats が rc=1 を返す
    run_guard_fixture "" setup-file-absent.bats

    [ "$status" -eq 0 ]
    [ "$(printf '%s\n' "$output" | grep -c '^ok [0-9]* .* # skip ')" -eq 2 ]
}

@test "a guard in setup_file fails the whole file in CI" {
    run_guard_fixture "true" setup-file-absent.bats

    [ "$status" -ne 0 ]
    assert_contains "$output" "not ok 1 setup_file failed"
    assert_contains "$output" "CI では必須"
}
