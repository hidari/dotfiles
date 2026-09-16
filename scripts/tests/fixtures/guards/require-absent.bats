#!/usr/bin/env bats
# 実在しないコマンドを require したときの対照。本体は走れば必ず赤くなる。

load ../../test_helper

setup() {
    require_command_or_skip definitely-not-installed-probe || return 1
}

@test "absent: guarded before the body" {
    false
}
