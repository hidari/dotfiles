#!/usr/bin/env bats
# 宣言済みだが実在しないコマンドを require したときの対照。
# 宣言キー (第 1 引数) と実際に探すコマンド (第 2 引数) を分ける形を使い、
# 「宣言は nvim のまま、探す先だけ不在にする」状況を作る。

load ../../test_helper

setup() {
    require_command_or_skip nvim definitely-not-installed-probe || return 1
}

@test "declared but absent: guarded before the body" {
    false
}
