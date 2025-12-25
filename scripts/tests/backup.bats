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
