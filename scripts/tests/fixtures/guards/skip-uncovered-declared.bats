#!/usr/bin/env bats
# 宣言済みの未カバーコマンドを skip_uncovered で宣言したときの対照。
# skip の理由は宣言表から引くので、呼び出し側は理由を書かない (二重記述を作らない)。

load ../../test_helper

@test "declared uncovered: skipped with the marker" {
    skip_uncovered osacompile || return 1
    false
}
