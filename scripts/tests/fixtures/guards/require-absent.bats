#!/usr/bin/env bats
# test-helper-guards.bats と run-bats.bats が子プロセスとして渡す fixture。
# 実在しないコマンドを require する。本体は走れば必ず赤くなる。

load ../../test_helper

setup() {
    require_command_or_skip definitely-not-installed-probe || return 1
}

@test "absent: guarded before the body" {
    false
}
