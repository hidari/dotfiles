#!/usr/bin/env bats
# setup_file がガードを呼び忘れたときの対照。
# フラグ未設定を「準備済み」と読むと、キャッシュを作っていないのに全テストが走って
# しまう。未設定は skip 側へ倒れることを固定する。

load ../../test_helper

setup() {
    file_setup_ready_or_skip || return 1
}

@test "unguarded file setup: the body does not run" {
    false
}
