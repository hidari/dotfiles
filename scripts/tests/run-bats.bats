#!/usr/bin/env bats
# =============================================================================
# CI の bats job の入口 (scripts/ci/run-bats.sh) の失敗条件を pin する
#
# fixtures/guards/ の .bats を子プロセスとして渡し、終了コードで見る。
#
# 注意:
# - bats は @test 名を関数名へエンコードするため名前は ASCII に限る
#   (rules/bats-test-name-ascii-only.yml)
# - CI 変数は親から継承されるので、ローカル側の枝を見るテストは env CI= で明示的に空にする
# =============================================================================

load test_helper

RUN_BATS="$REPO_ROOT/scripts/ci/run-bats.sh"

# 第 1 引数は CI 変数の値、残りは渡す fixture のファイル名
run_wrapper() {
    local ci_value="$1"
    shift
    local fixtures=() name
    for name in "$@"; do
        fixtures+=("$FIXTURES_DIR/guards/$name")
    done
    run env CI="$ci_value" bash "$RUN_BATS" "${fixtures[@]}"
}

@test "run-bats: passes when every test runs and passes" {
    run_wrapper "" require-present.bats

    [ "$status" -eq 0 ]
}

@test "run-bats: fails when a test is skipped" {
    # bats 自体は skip を成功として rc=0 で終える
    run_wrapper "" require-absent.bats

    [ "$status" -ne 0 ]
    assert_contains "$output" "# skip definitely-not-installed-probe"
}

@test "run-bats: fails when bats fails while other tests pass" {
    # 通るテストを混ぜるのは、skip の検査と実行 0 件の検査に横取りされないようにするため。
    # この形で落とせるのは bats の終了コードだけで、tee の成功に飲み込まれると緑になる
    run_wrapper "true" require-present.bats require-absent.bats

    [ "$status" -ne 0 ]
    assert_contains "$output" $'\nnot ok 2 '
    refute_contains "$output" "# skip"
}

@test "run-bats: leaves uncovered tests out of the run" {
    # タグ付きの本体は false なので、走っていれば赤くなる
    run_wrapper "" require-present.bats uncovered-only.bats

    [ "$status" -eq 0 ]
    refute_contains "$output" "uncovered only"
}

@test "run-bats: fails when no test ran" {
    # skip も失敗も 0 件なので skip の検査を素通りする形。落とすのは bats 自体で、
    # ラッパは同じ検査を持たない。bats がこの挙動をやめたらここが赤くなる
    run_wrapper "" uncovered-only.bats

    [ "$status" -ne 0 ]
    assert_contains "$output" "Found no tests"
}
