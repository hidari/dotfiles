#!/usr/bin/env bats
# setup_file でコマンドが不在だったときの対照。
# setup_file の中では skip を呼べないので、可否はフラグで運び setup() 側で skip する。
# ローカルなら全テストが skip され、CI ならファイル全体が赤くなる。

load ../../test_helper

setup_file() {
    require_command_for_file_setup nvim definitely-not-installed-probe || return 1

    if [ "$FILE_SETUP_READY" = "1" ]; then
        echo cached > "$BATS_FILE_TMPDIR/probe.txt"
    fi
}

setup() {
    file_setup_ready_or_skip || return 1
}

@test "file setup absent: the first body does not run" {
    false
}

@test "file setup absent: the second body does not run" {
    false
}
