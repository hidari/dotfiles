#!/usr/bin/env bats
# =============================================================================
# .zshrc の tgrep ラッパーのテスト
# =============================================================================
#
# ラッパーが守る仕様は以下の通り。
#   1. サブコマンド (serve/index/status/count-files/help) は素通しする。
#      ここに索引回避のフラグを足すと serve 自身が壊れる
#   2. 検索のとき、serve が生きていなければ --no-index を足して stderr に 1 行告げる
#      (素の tgrep も PATTERN 無しの subcommand 形 (search) も検索であり、
#      どちらも同じ扱いを受ける)
#   3. serve が生きていれば素通しする
#   4. 判定はプロセス起動を挟まない (serve.json と PID の生死だけを見る)

load test_helper

bats_require_minimum_version 1.5.0

setup() {
    setup_test_home
    FAKE_BIN="$TEST_HOME/bin"
    mkdir -p "$FAKE_BIN"
    # 渡された引数をそのまま記録する偽 tgrep
    cat > "$FAKE_BIN/tgrep" <<'EOF'
#!/bin/sh
printf '%s\n' "$@" > "$TGREP_ARGS_FILE"
exit 0
EOF
    chmod 755 "$FAKE_BIN/tgrep"
    PATH="$FAKE_BIN:$PATH"
    export TGREP_ARGS_FILE="$TEST_HOME/args.txt"
    REPO="$TEST_HOME/repo"
    mkdir -p "$REPO/.tgrep"
}

teardown() {
    teardown_test_home
}

# serve.json を書く。第 2 引数が live なら自分の PID (必ず生きている) を使う。
write_serve_json() {
    local pid="$2"
    [ "$pid" = "live" ] && pid=$$
    printf '{"pid":%s,"port":1}' "$pid" > "$1/.tgrep/serve.json"
}

@test "tgrep: passes serve subcommand through untouched" {
    load_zshrc_tgrep_function
    cd "$REPO" || return 1
    run tgrep serve .
    [ "$status" -eq 0 ]
    run cat "$TGREP_ARGS_FILE"
    [ "${lines[0]}" = "serve" ]
    run ! grep -q -- "--no-index" "$TGREP_ARGS_FILE"
}

@test "tgrep: passes status subcommand through untouched" {
    load_zshrc_tgrep_function
    cd "$REPO" || return 1
    run tgrep status .
    run ! grep -q -- "--no-index" "$TGREP_ARGS_FILE"
}

@test "tgrep: adds --no-index when no server is running" {
    load_zshrc_tgrep_function
    cd "$REPO" || return 1
    run --separate-stderr tgrep PATTERN
    grep -q -- "--no-index" "$TGREP_ARGS_FILE"
    [ -n "$stderr" ]
}

@test "tgrep: adds --no-index before the search subcommand when no server is running" {
    # search はパターン無しの検索であり、case の素通しリストへ足すと serve が生きて
    # いないときも索引回避されないまま検索してしまう。素の PATTERN 形だけでなく
    # search 形もこのテストで別に pin する
    load_zshrc_tgrep_function
    cd "$REPO" || return 1
    run --separate-stderr tgrep search PATTERN
    [ -n "$stderr" ]
    run cat "$TGREP_ARGS_FILE"
    [ "${lines[0]}" = "--no-index" ]
    [ "${lines[1]}" = "search" ]
    [ "${lines[2]}" = "PATTERN" ]
}

@test "tgrep: adds --no-index when serve.json points at a dead pid" {
    load_zshrc_tgrep_function
    write_serve_json "$REPO" 4194303
    cd "$REPO" || return 1
    run tgrep PATTERN
    grep -q -- "--no-index" "$TGREP_ARGS_FILE"
}

@test "tgrep: leaves the search untouched when the server is alive" {
    load_zshrc_tgrep_function
    write_serve_json "$REPO" live
    cd "$REPO" || return 1
    run --separate-stderr tgrep PATTERN
    [ -z "$stderr" ]
    run ! grep -q -- "--no-index" "$TGREP_ARGS_FILE"
}

@test "load_zshrc_tgrep_function: fails loudly when the marker is missing" {
    ZSHRC_FILE="$TEST_HOME/empty.zshrc"
    printf '%s\n' '# unrelated' > "$ZSHRC_FILE"
    run load_zshrc_tgrep_function
    [ "$status" -ne 0 ]
}
