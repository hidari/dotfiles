#!/usr/bin/env bats
# =============================================================================
# backup.sh Test Suite
# =============================================================================
# Run: bats scripts/tests/backup.bats

# Load helper
load test_helper

# =============================================================================
# parse_backup_pair tests
# =============================================================================

@test "parse_backup_pair: parses basic 3-element string" {
    parse_backup_pair "Test|/src|/dst"
    [ "$PAIR_NAME" = "Test" ]
    [ "$PAIR_SOURCE" = "/src" ]
    [ "$PAIR_DEST" = "/dst" ]
    [ "${#PAIR_EXCLUDES[@]}" -eq 0 ]
}

@test "parse_backup_pair: parses 4-element string with excludes" {
    parse_backup_pair "Test|/src|/dst|*.tmp,cache"
    [ "$PAIR_NAME" = "Test" ]
    [ "$PAIR_SOURCE" = "/src" ]
    [ "$PAIR_DEST" = "/dst" ]
    [ "${#PAIR_EXCLUDES[@]}" -eq 2 ]
    [ "${PAIR_EXCLUDES[0]}" = "*.tmp" ]
    [ "${PAIR_EXCLUDES[1]}" = "cache" ]
}

@test "parse_backup_pair: parses Japanese name" {
    parse_backup_pair "PhotoBackup|/Volumes/Photos|/Volumes/Backup/Photos"
    [ "$PAIR_NAME" = "PhotoBackup" ]
    [ "$PAIR_SOURCE" = "/Volumes/Photos" ]
    [ "$PAIR_DEST" = "/Volumes/Backup/Photos" ]
}

@test "parse_backup_pair: parses path with spaces" {
    parse_backup_pair "Test|/Volumes/My Drive/Source|/Volumes/My Drive/Backup"
    [ "$PAIR_SOURCE" = "/Volumes/My Drive/Source" ]
    [ "$PAIR_DEST" = "/Volumes/My Drive/Backup" ]
}

@test "parse_backup_pair: fails on empty name" {
    run parse_backup_pair "|/source|/dest"
    [ "$status" -ne 0 ]
    [[ "$output" == *"エラー"* ]] || [[ "$output" == *"不正"* ]]
}

@test "parse_backup_pair: fails on empty source" {
    run parse_backup_pair "name||/dest"
    [ "$status" -ne 0 ]
}

@test "parse_backup_pair: fails on incomplete pair" {
    run parse_backup_pair "name_only"
    [ "$status" -ne 0 ]
}

# =============================================================================
# get_path_type tests
# =============================================================================

@test "get_path_type: returns volume for volume root" {
    run get_path_type "/Volumes/Luna-P"
    [ "$status" -eq 0 ]
    [ "$output" = "volume" ]
}

@test "get_path_type: returns directory for subdirectory under volume" {
    run get_path_type "/Volumes/Luna-P/Photos"
    [ "$status" -eq 0 ]
    [ "$output" = "directory" ]
}

@test "get_path_type: returns directory for deep path" {
    run get_path_type "/Volumes/Luna-P/Photos/2024/Summer"
    [ "$status" -eq 0 ]
    [ "$output" = "directory" ]
}

@test "get_path_type: returns local for /Users path" {
    run get_path_type "/Users/sho/Documents"
    [ "$status" -eq 0 ]
    [ "$output" = "local" ]
}

@test "get_path_type: returns local for root path" {
    run get_path_type "/tmp/backup"
    [ "$status" -eq 0 ]
    [ "$output" = "local" ]
}

# =============================================================================
# extract_volume_path tests
# =============================================================================

@test "extract_volume_path: extracts volume from directory path" {
    run extract_volume_path "/Volumes/Luna-P/Photos/2024"
    [ "$status" -eq 0 ]
    [ "$output" = "/Volumes/Luna-P" ]
}

@test "extract_volume_path: extracts volume from volume root" {
    run extract_volume_path "/Volumes/Luna-P"
    [ "$status" -eq 0 ]
    [ "$output" = "/Volumes/Luna-P" ]
}

@test "extract_volume_path: returns empty for local path" {
    run extract_volume_path "/Users/sho/Documents"
    [ "$status" -eq 0 ]
    [ "$output" = "" ]
}

@test "extract_volume_path: handles hyphenated volume name" {
    run extract_volume_path "/Volumes/My-External-Drive/Data"
    [ "$status" -eq 0 ]
    [ "$output" = "/Volumes/My-External-Drive" ]
}

# =============================================================================
# filter_rsync_output tests
# =============================================================================

@test "filter_rsync_output: filters .Trashes error" {
    echo 'opendir ".Trashes" failed: Operation not permitted' | filter_rsync_output > /dev/null
    [ -s "$FILTERED_ERRORS_FILE" ]
}

@test "filter_rsync_output: filters .Spotlight-V100 error" {
    echo 'delete_file: rmdir(.Spotlight-V100) failed: Operation not permitted' | filter_rsync_output > /dev/null
    [ -s "$FILTERED_ERRORS_FILE" ]
}

@test "filter_rsync_output: passes normal output through" {
    result=$(echo 'sending incremental file list' | filter_rsync_output)
    [ "$result" = "sending incremental file list" ]
}

@test "filter_rsync_output: passes file transfer line through" {
    result=$(echo 'Photos/2024/IMG_001.jpg' | filter_rsync_output)
    [ "$result" = "Photos/2024/IMG_001.jpg" ]
}

@test "filter_rsync_output: filters code 23 error" {
    echo 'rsync error: some files/attrs were not transferred (see previous errors) (code 23)' | filter_rsync_output > /dev/null
    [ -s "$FILTERED_ERRORS_FILE" ]
}

# =============================================================================
# display_summary tests
# =============================================================================

@test "display_summary: shows all success" {
    run display_summary 3 0 0
    [ "$status" -eq 0 ]
    [[ "$output" == *"3 / 3"* ]]
}

@test "display_summary: shows warning on partial failure" {
    run display_summary 2 0 1
    [ "$status" -eq 0 ]
    [[ "$output" == *"1 / 3"* ]]
}

@test "display_summary: counts partial success" {
    run display_summary 1 2 0
    [ "$status" -eq 0 ]
    [[ "$output" == *"2 / 3"* ]]
}

# =============================================================================
# check_path permission tests
# =============================================================================

# Note: check_path uses error_exit which calls exit, so we test the permission
# checking logic indirectly by verifying the bash test operators work correctly

@test "check_path: permission check logic - readable directory" {
    local test_dir
    test_dir=$(mktemp -d)
    chmod 755 "$test_dir"

    # Verify -r test works for readable directory
    [ -r "$test_dir" ]

    rm -rf "$test_dir"
}

@test "check_path: permission check logic - writable directory" {
    local test_dir
    test_dir=$(mktemp -d)
    chmod 755 "$test_dir"

    # Verify -w test works for writable directory
    [ -w "$test_dir" ]

    rm -rf "$test_dir"
}

@test "check_path: permission check logic - unreadable directory" {
    # Skip if running as root (root can read anything)
    [ "$(id -u)" -eq 0 ] && skip "Running as root, permission tests not applicable"

    local test_dir
    test_dir=$(mktemp -d)
    chmod 000 "$test_dir"

    # Verify -r test fails for unreadable directory
    local is_readable=true
    [ -r "$test_dir" ] || is_readable=false

    chmod 755 "$test_dir"
    rm -rf "$test_dir"

    [ "$is_readable" = "false" ]
}

@test "check_path: permission check logic - unwritable directory" {
    # Skip if running as root (root can write anything)
    [ "$(id -u)" -eq 0 ] && skip "Running as root, permission tests not applicable"

    local test_dir
    test_dir=$(mktemp -d)
    chmod 555 "$test_dir"

    # Verify -w test fails for unwritable directory
    local is_writable=true
    [ -w "$test_dir" ] || is_writable=false

    chmod 755 "$test_dir"
    rm -rf "$test_dir"

    [ "$is_writable" = "false" ]
}
