#!/usr/bin/env bats
# setup_file でコマンドが不在だったときの対照。
# ローカルなら全テストが skip され、CI ならファイル全体が赤くなる。本体は走れば必ず赤くなる。

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
