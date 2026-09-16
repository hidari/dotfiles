#!/usr/bin/env bats
# 宣言済みかつ実在するコマンドを require したときの対照。
# このファイルは test-helper-guards.bats が子 bats として起動する fixture で、
# bats はディレクトリを既定で再帰しないため本スイート (bats scripts/tests/) には拾われない。

load ../../test_helper

setup() {
    require_command_or_skip bats || return 1
}

@test "declared and present: the test body runs" {
    true
}
