#!/usr/bin/env bats
# =============================================================================
# statusline-command.sh のレートリミット表示とアカウント分離テスト
# =============================================================================
#
# レートリミットと 2 アカウント運用で statusLine が守る仕様は 3 つ。
#   1. レートリミットは Claude Code 本体が stdin で渡す値を使う (自前で API を叩かない)
#   2. 失効した窓は表示しない (リセット直後に前の窓の高い使用率を出さない)
#   3. キャッシュをアカウントごとに分ける
#      (共有すると片方の値がもう片方の表示とフックの発火判定へ混ざる)
#
# 3 番目のキャッシュは handoff-sentinel フックがレートリミットを読む供給経路でもある。
# 本体はフックへレートリミットを渡さないので、経路はこの 1 本しかない。

load test_helper

setup() {
    setup_test_home
    unset CLAUDE_CONFIG_DIR
    export XDG_CACHE_HOME="$TEST_HOME/cache"
}

teardown() {
    teardown_test_home
}

# 与えた config dir に対する期待タグ。プロダクトコードと同じ導出をテスト側に
# 書き写すのではなく、テストの意図 (sha256 先頭 8 桁) をここだけに置く。
expected_tag_for() {
    printf '%s' "$1" | shasum -a 256 | cut -c1-8
}

# =============================================================================
# account_config_dir
# =============================================================================

@test "account_config_dir: falls back to the default directory when unset" {
    load_statusline_functions

    run account_config_dir

    [ "$status" -eq 0 ]
    [ "$output" = "$TEST_HOME/.claude" ]
}

@test "account_config_dir: returns CLAUDE_CONFIG_DIR when it is set" {
    load_statusline_functions

    CLAUDE_CONFIG_DIR="$TEST_HOME/.claude-alpha" run account_config_dir

    [ "$status" -eq 0 ]
    [ "$output" = "$TEST_HOME/.claude-alpha" ]
}

# =============================================================================
# account_tag
# =============================================================================

@test "account_tag: returns default for the default config directory" {
    load_statusline_functions

    run account_tag "$TEST_HOME/.claude"

    [ "$status" -eq 0 ]
    [ "$output" = "default" ]
}

@test "account_tag: returns the sha256 prefix for a custom config directory" {
    load_statusline_functions
    local custom="$TEST_HOME/.claude-alpha"
    local expected
    expected="$(expected_tag_for "$custom")"

    run account_tag "$custom"

    [ "$status" -eq 0 ]
    # 存在チェックではなく exact 一致で見る。長さだけ合う別の導出を通さないため
    [ "$output" = "$expected" ]
    [ "${#output}" -eq 8 ]
}

@test "account_tag: yields different tags for two different config directories" {
    # キャッシュ分離の土台。ここが同じ値を返すと 2 アカウントが同じキャッシュを共有する
    load_statusline_functions

    run account_tag "$TEST_HOME/.claude-alpha"
    local first="$output"
    run account_tag "$TEST_HOME/.claude-other"
    local second="$output"

    [ -n "$first" ]
    [ -n "$second" ]
    [ "$first" != "$second" ]
}

# =============================================================================
# account_json_path
# =============================================================================

@test "account_json_path: points at HOME for the default account" {
    # 既定アカウントだけ .claude.json が設定ディレクトリの外に置かれる非対称がある
    load_statusline_functions

    run account_json_path "$TEST_HOME/.claude"

    [ "$status" -eq 0 ]
    [ "$output" = "$TEST_HOME/.claude.json" ]
}

@test "account_json_path: points inside the config dir for a custom account" {
    load_statusline_functions

    run account_json_path "$TEST_HOME/.claude-alpha"

    [ "$status" -eq 0 ]
    [ "$output" = "$TEST_HOME/.claude-alpha/.claude.json" ]
}

# =============================================================================
# account_email
# =============================================================================

@test "account_email: reads the address from the account json" {
    load_statusline_functions
    echo '{"oauthAccount":{"emailAddress":"someone@example.com"}}' > "$TEST_HOME/acc.json"

    run account_email "$TEST_HOME/acc.json" "$TEST_HOME/email-cache.txt"

    [ "$status" -eq 0 ]
    [ "$output" = "someone@example.com" ]
}

@test "account_email: fails when the account json is missing" {
    # 失敗時に空でも成功を返すと、表示側が「アカウント不明のまま緑」になる
    load_statusline_functions

    run account_email "$TEST_HOME/does-not-exist.json" "$TEST_HOME/email-cache.txt"

    [ "$status" -ne 0 ]
}

@test "account_email: refreshes the cache when the account json is newer" {
    load_statusline_functions
    local cache="$TEST_HOME/email-cache.txt"
    echo "stale@example.com" > "$cache"
    # キャッシュを過去へ倒して .claude.json の方が新しい状態を作る。
    # touch -t は POSIX で BSD/GNU 双方にあるが、相対指定の -A は BSD 専用で Linux では落ちる。
    touch -t 202001010000 "$cache"
    echo '{"oauthAccount":{"emailAddress":"fresh@example.com"}}' > "$TEST_HOME/acc.json"

    run account_email "$TEST_HOME/acc.json" "$cache"

    [ "$status" -eq 0 ]
    [ "$output" = "fresh@example.com" ]
}

@test "account_email: uses the cache when it is newer than the account json" {
    # 逆方向。statusLine は描画ごとに走るため、更新が無ければ 100KB 超の JSON を
    # 読み直さないことが仕様。両方向を見ないと「常に読み直す」実装を見逃す
    load_statusline_functions
    local cache="$TEST_HOME/email-cache.txt"
    echo '{"oauthAccount":{"emailAddress":"fresh@example.com"}}' > "$TEST_HOME/acc.json"
    touch -t 202001010000 "$TEST_HOME/acc.json"
    echo "cached@example.com" > "$cache"

    run account_email "$TEST_HOME/acc.json" "$cache"

    [ "$status" -eq 0 ]
    [ "$output" = "cached@example.com" ]
}

# =============================================================================
# レートリミット: 取得元と表示
# =============================================================================

@test "statusline: treats used_percentage as a 0-100 value" {
    # used_percentage は 0-100。0.0-1.0 と取り違えると 42% が 4200% になる。
    # スケールの取り違えは例外を出さずに成立するので、値そのものを exact に見る
    run_statusline "$(rate_limits_json 42 13)"

    [ "$status" -eq 0 ]
    assert_contains "${lines[1]}" "42%"
    assert_contains "${lines[2]}" "13%"
}

@test "statusline: does not show an expired window" {
    # 本体は失効窓を落として渡すが、キャッシュから読み直す経路では過ぎた窓が残る。
    # 残すとリセットで圧が下がった直後に前の窓の使用率を出し続ける
    local expired=1000000000  # 2001-09-09
    run_statusline "$(rate_limits_json 99 99 "$expired")"

    [ "$status" -eq 0 ]
    assert_contains "${lines[1]}" "--%"
    refute_contains "${lines[1]}" "99%"
}

@test "statusline: keeps the cached value when the body sends nothing" {
    # セッション開始直後・headless・非サブスクでは本体が渡さない。消すと窓が
    # まだ有効なあいだの既知値まで失う
    run_statusline "$(rate_limits_json 77 33)"
    [ "$status" -eq 0 ]

    run_statusline
    [ "$status" -eq 0 ]
    assert_contains "${lines[1]}" "77%"
    [ -f "$XDG_CACHE_HOME/claude/rate-limits-default.json" ]
}

@test "statusline: never runs an inference probe of its own" {
    # プローブは推論リクエストなので、リミットを測るためにリミットを消費する。
    # PATH 先頭の偽物が一度でも呼ばれたら、実装がまだ自前で取りに行っている
    setup_probe_watchdog

    run_statusline "$(rate_limits_json)"

    [ "$status" -eq 0 ]
    [ ! -s "$PROBE_LOG" ]
}

# =============================================================================
# レートリミット: フックへの供給
# =============================================================================

@test "statusline: writes the rate limit cache under an account specific name" {
    local custom="$TEST_HOME/.claude-alpha"
    mkdir -p "$custom"
    local tag
    tag="$(expected_tag_for "$custom")"
    export CLAUDE_CONFIG_DIR="$custom"

    run_statusline "$(rate_limits_json)"

    [ "$status" -eq 0 ]
    [ -f "$XDG_CACHE_HOME/claude/rate-limits-$tag.json" ]
}

@test "statusline: keeps the two accounts rate limit caches in separate files" {
    # 相互汚染バグの pin。共有ファイルへ戻すとここが落ちる
    local custom="$TEST_HOME/.claude-alpha"
    mkdir -p "$custom"
    local tag
    tag="$(expected_tag_for "$custom")"

    unset CLAUDE_CONFIG_DIR
    run_statusline "$(rate_limits_json)"
    [ "$status" -eq 0 ]

    export CLAUDE_CONFIG_DIR="$custom"
    run_statusline "$(rate_limits_json)"
    [ "$status" -eq 0 ]

    [ -f "$XDG_CACHE_HOME/claude/rate-limits-default.json" ]
    [ -f "$XDG_CACHE_HOME/claude/rate-limits-$tag.json" ]
}

# statusline が書いたキャッシュをフックが読んで発火するところまでを通す。
# パス導出は shell と Python の 2 実装なので、どちらかがずれるとフックは別のファイルを読み、
# レートリミットの通知が「エラーではなく無言」で来なくなる。片側だけのテストでは検出できない。
#
# 導出は既定アカウントとそれ以外で枝が分かれるので、両方を通す。片方だけだと、通した枝しか
# pin されない (既定枝を壊しても全テストが緑のままになることを変異注入で確認済み)。
assert_statusline_feeds_hook() {
    run_statusline "$(rate_limits_json 96 13)"
    [ "$status" -eq 0 ]

    local transcript="$TEST_HOME/t.jsonl"
    printf '{"type":"assistant","message":{"usage":{"input_tokens":1},"content":[]}}\n' > "$transcript"
    local hook_input
    hook_input="$(printf '{"session_id":"s1","transcript_path":"%s","cwd":"%s","hook_event_name":"PostToolUse"}' \
        "$transcript" "$TEST_HOME")"

    run env HANDOFF_STATE_DIR="$TEST_HOME/state" \
        python3 "$REPO_ROOT/home/.claude/hooks/handoff-sentinel.py" posttool <<< "$hook_input"

    [ "$status" -eq 0 ]
    assert_contains "$output" "session-handoff"
}

@test "statusline: writes where the handoff hook reads (custom account)" {
    local custom="$TEST_HOME/.claude-alpha"
    mkdir -p "$custom"
    export CLAUDE_CONFIG_DIR="$custom"

    assert_statusline_feeds_hook
}

@test "statusline: writes where the handoff hook reads (default account)" {
    # 単一アカウント運用で実際に通る枝。ハッシュ枝だけを pin していると、
    # 既定枝の導出が両言語でずれていても誰も気づけない
    unset CLAUDE_CONFIG_DIR

    assert_statusline_feeds_hook
}

# =============================================================================
# 表示まわり
# =============================================================================

@test "statusline: shows the account address on the first line" {
    local custom="$TEST_HOME/.claude-alpha"
    mkdir -p "$custom"
    echo '{"oauthAccount":{"emailAddress":"work@example.com"}}' > "$custom/.claude.json"
    export CLAUDE_CONFIG_DIR="$custom"

    run_statusline

    [ "$status" -eq 0 ]
    # 色だけに情報を持たせないため、アドレスの文字列そのものが出ていること
    assert_contains "$output" "work@example.com"
}

@test "statusline: emits color escapes rather than literal escape text" {
    run_statusline

    [ "$status" -eq 0 ]
    # \e[38;5;213m のような文字列がそのまま見えていたら色指定が壊れている
    refute_contains "$output" '\e['
}

# =============================================================================
# 行構成
# =============================================================================
#
# 1〜3 行目は Claude が持つ状態、4 行目はリポジトリが持つ状態。
# 情報の所有者で行を分けることが仕様なので、混ざっていないことまで検証する。

@test "statusline: collapses to three lines outside a repository" {
    # リポジトリ外で 4 行目を空のまま出すと、画面に無意味な空行が残る。
    # bats の $output は末尾改行を落とし $lines の要素数では区別が付かないため、
    # 生の出力の改行数で見る (3 行 + 末尾改行なし = 改行 2 個)。
    statusline_raw "$TEST_HOME/out.txt"

    [ "$(count_newlines "$TEST_HOME/out.txt")" -eq 2 ]
}

@test "statusline: emits four lines inside a repository without a trailing newline" {
    # 4 行 + 末尾改行なし = 改行 3 個。3 行目の改行落ちも余分な末尾改行も検出する
    setup_test_repo "$TEST_HOME/myrepo"

    statusline_raw "$TEST_HOME/out.txt" "$TEST_HOME/myrepo"

    [ "$(count_newlines "$TEST_HOME/out.txt")" -eq 3 ]
}

@test "statusline: puts the repository line last" {
    setup_test_repo "$TEST_HOME/myrepo"

    run_statusline_in "$TEST_HOME/myrepo"

    [ "$status" -eq 0 ]
    [ "${#lines[@]}" -eq 4 ]
    assert_contains "${lines[3]}" "myrepo"
}

# `git rev-parse --is-inside-work-tree` は答えを stdout の文字列で返すコマンドで、
# .git ディレクトリの中や bare リポジトリでは "false" を出力しながら exit 0 を返す。
# exit code だけで作業ツリーの内外を判定すると、この 2 経路で分岐へ入ってしまう。
# 分岐の中では --show-toplevel が exit 128 で落ちてプロジェクト名が空になる一方、
# branch --show-current は成功するため、4 行目が畳まれず「プロジェクト名だけが
# 空の行」が残る。作業ツリーの外という点ではリポジトリ外と同じなので 3 行に畳む。
@test "statusline: collapses to three lines inside a .git directory" {
    setup_test_repo "$TEST_HOME/myrepo"

    statusline_raw "$TEST_HOME/out.txt" "$TEST_HOME/myrepo/.git"

    [ "$(count_newlines "$TEST_HOME/out.txt")" -eq 2 ]
}

@test "statusline: collapses to three lines inside a bare repository" {
    git init -q --bare "$TEST_HOME/bare.git"

    statusline_raw "$TEST_HOME/out.txt" "$TEST_HOME/bare.git"

    [ "$(count_newlines "$TEST_HOME/out.txt")" -eq 2 ]
}

@test "statusline: keeps repository info out of the first line" {
    # 4 行目へ移したのに 1 行目にも残っている二重表示を防ぐ
    setup_test_repo "$TEST_HOME/myrepo"

    run_statusline_in "$TEST_HOME/myrepo"

    [ "$status" -eq 0 ]
    refute_contains "${lines[0]}" "myrepo"
}

@test "statusline: keeps the rate limit bars on the middle lines" {
    # リポジトリ行を足したときに 5h / 7d が押し出されていないこと
    setup_test_repo "$TEST_HOME/myrepo"

    run_statusline_in "$TEST_HOME/myrepo"

    [ "$status" -eq 0 ]
    assert_contains "${lines[1]}" "5h"
    assert_contains "${lines[2]}" "7d"
}

# =============================================================================
# ローダー自身の健全性
# =============================================================================

@test "load_statusline_functions: fails loudly when the marker is missing" {
    run load_marker_block "$STATUSLINE_SCRIPT" '^# nonexistent marker$' '^# メイン処理$'

    [ "$status" -ne 0 ]
    assert_contains "$output" "start marker not found"
}
