#!/usr/bin/env bats
# =============================================================================
# 件数の下限を見る assert_positive_count の契約を pin する
#
# プローブの出力する件数が 0 のとき、検査は何も見ないまま「違反 0」で緑になる。
# このヘルパーはその堰なので、通す形と弾く形の両方を固定する。
#
# 注意:
# - bats は @test 名を関数名へエンコードするため名前は ASCII に限る
#   (rules/bats-test-name-ascii-only.yml)
# =============================================================================

load test_helper

@test "assert_positive_count: accepts a line whose count is one or more" {
    assert_positive_count COUNT "VIOLATION=0" "COUNT=1"
    assert_positive_count COUNT "COUNT=10"
}

@test "assert_positive_count: rejects a zero count" {
    run assert_positive_count COUNT "COUNT=0"
    [ "$status" -eq 1 ]
}

@test "assert_positive_count: rejects output that lacks the line" {
    # refute_contains "COUNT=0" はこの形を通してしまう。プローブ側でキーを改名すると起きる
    run assert_positive_count COUNT "VIOLATION=0"
    [ "$status" -eq 1 ]
}

@test "assert_positive_count: matches the key and the count as a whole line" {
    run assert_positive_count COUNT "SUB_COUNT=1" "COUNT=1x"
    [ "$status" -eq 1 ]
}
