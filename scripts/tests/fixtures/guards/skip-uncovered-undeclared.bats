#!/usr/bin/env bats
# 宣言表に無いコマンドを skip_uncovered で skip しようとしたときの対照。
# 宣言の無い skip を通すと、assert-declared-skips.sh が突き合わせる相手を失う。

load ../../test_helper

@test "undeclared uncovered: rejected by the helper" {
    skip_uncovered definitely-not-declared || return 1
    false
}
