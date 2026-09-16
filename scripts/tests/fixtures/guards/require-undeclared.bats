#!/usr/bin/env bats
# CI の bats job が供給しないコマンドを require したときの対照。
# この入口は「CI で不在なら落とす」を意味するので、供給されないコマンドへ使うと
# 正当な不在で CI が赤くなる。宣言の外はヘルパ側で落として気づかせる。

load ../../test_helper

setup() {
    require_command_or_skip osacompile || return 1
}

@test "undeclared command: rejected by the helper" {
    true
}
