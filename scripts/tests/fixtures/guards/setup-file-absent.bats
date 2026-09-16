#!/usr/bin/env bats
# test-helper-guards.bats が子プロセスとして渡す fixture。
# setup_file で実在しないコマンドを require する。本体は走れば必ず赤くなる。

load ../../test_helper

setup_file() {
    require_command_or_skip definitely-not-installed-probe || return 1
}

@test "setup file absent: the first body does not run" {
    false
}

@test "setup file absent: the second body does not run" {
    false
}
