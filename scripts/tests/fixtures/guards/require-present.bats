#!/usr/bin/env bats
# test-helper-guards.bats と run-bats.bats が子プロセスとして渡す fixture。
# 実在するコマンドを require する。

load ../../test_helper

setup() {
    require_command_or_skip bats || return 1
}

@test "present: the test body runs" {
    true
}
