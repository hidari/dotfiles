#!/usr/bin/env bats
# setup_file でコマンドが実在したときの対照。
# probe は setup_file で 1 回だけ回し、各テストはキャッシュを読む。

load ../../test_helper

setup_file() {
    require_command_for_file_setup bats || return 1

    if [ "$FILE_SETUP_READY" = "1" ]; then
        echo cached > "$BATS_FILE_TMPDIR/probe.txt"
    fi
}

setup() {
    file_setup_ready_or_skip || return 1
}

@test "file setup present: the first body reads the cache" {
    run cat "$BATS_FILE_TMPDIR/probe.txt"
    assert_contains "$output" "cached"
}

@test "file setup present: the second body reads the same cache" {
    run cat "$BATS_FILE_TMPDIR/probe.txt"
    assert_contains "$output" "cached"
}
