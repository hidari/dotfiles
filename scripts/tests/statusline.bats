#!/usr/bin/env bats
# =============================================================================
# statusline-command.sh のアカウント分離テスト
# =============================================================================
#
# 2 アカウント運用で statusLine が守る仕様は 3 つ。
#   1. Keychain の service 名を config dir から導出する (既定は無印、それ以外は
#      絶対パスの sha256 先頭 8 桁。実測で確定した Claude Code の規則)
#   2. 導出した item が無くても他の service 名へフォールバックしない
#      (他アカウントのトークンで引くと別アカウントのレート制限を表示してしまう)
#   3. 使用率キャッシュをアカウントごとに分ける
#      (共有すると片方の値がもう片方に TTL 分だけ表示される)

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

    CLAUDE_CONFIG_DIR="$TEST_HOME/.claude-hamiltonian" run account_config_dir

    [ "$status" -eq 0 ]
    [ "$output" = "$TEST_HOME/.claude-hamiltonian" ]
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
    local custom="$TEST_HOME/.claude-hamiltonian"
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

    run account_tag "$TEST_HOME/.claude-hamiltonian"
    local first="$output"
    run account_tag "$TEST_HOME/.claude-other"
    local second="$output"

    [ -n "$first" ]
    [ -n "$second" ]
    [ "$first" != "$second" ]
}

# =============================================================================
# account_keychain_service
# =============================================================================

@test "account_keychain_service: has no suffix for the default account" {
    load_statusline_functions

    run account_keychain_service "default"

    [ "$status" -eq 0 ]
    [ "$output" = "Claude Code-credentials" ]
}

@test "account_keychain_service: appends the tag for a custom account" {
    load_statusline_functions

    run account_keychain_service "2a4c0d76"

    [ "$status" -eq 0 ]
    [ "$output" = "Claude Code-credentials-2a4c0d76" ]
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

    run account_json_path "$TEST_HOME/.claude-hamiltonian"

    [ "$status" -eq 0 ]
    [ "$output" = "$TEST_HOME/.claude-hamiltonian/.claude.json" ]
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
# 統合: スクリプト全体の挙動
# =============================================================================

@test "statusline: asks the keychain for the derived service name of a custom account" {
    local custom="$TEST_HOME/.claude-hamiltonian"
    mkdir -p "$custom"
    echo '{"oauthAccount":{"emailAddress":"work@example.com"}}' > "$custom/.claude.json"
    local tag
    tag="$(expected_tag_for "$custom")"
    setup_fake_keychain
    export FAKE_KEYCHAIN_SERVICE="Claude Code-credentials-$tag"
    export CLAUDE_CONFIG_DIR="$custom"

    run_statusline

    [ "$status" -eq 0 ]
    assert_contains "$(cat "$SECURITY_LOG")" "Claude Code-credentials-$tag"
}

@test "statusline: never falls back to another account's keychain item" {
    # 導出した item が無い状況を作る。ここで無印を試しに行くと個人アカウントの
    # トークンで引いてしまい、仕事アカウントの statusLine に個人側の値が出る
    local custom="$TEST_HOME/.claude-hamiltonian"
    mkdir -p "$custom"
    setup_fake_keychain
    export FAKE_KEYCHAIN_SERVICE="no-such-service"
    export CLAUDE_CONFIG_DIR="$custom"

    run_statusline

    [ "$status" -eq 0 ]
    # 無印の service 名を「行として」一度も引いていないこと。
    # 部分一致だとサフィックス付きの名前が巻き込まれるため -x で行全体一致にする
    local bare_count
    bare_count="$(grep -cx 'Claude Code-credentials' "$SECURITY_LOG" || true)"
    [ "$bare_count" -eq 0 ]
    # 資格情報が取れないので数値は出さず未取得表示に落ちる
    assert_contains "$output" "--%"
}

@test "statusline: writes the usage cache under an account specific name" {
    local custom="$TEST_HOME/.claude-hamiltonian"
    mkdir -p "$custom"
    local tag
    tag="$(expected_tag_for "$custom")"
    setup_fake_keychain
    export FAKE_KEYCHAIN_SERVICE="Claude Code-credentials-$tag"
    export CLAUDE_CONFIG_DIR="$custom"

    run_statusline

    [ "$status" -eq 0 ]
    [ -f "$XDG_CACHE_HOME/claude/usage-cache-$tag.json" ]
}

@test "statusline: keeps the two accounts usage caches in separate files" {
    # 相互汚染バグの pin。共有ファイルへ戻すとここが落ちる
    local custom="$TEST_HOME/.claude-hamiltonian"
    mkdir -p "$custom"
    local tag
    tag="$(expected_tag_for "$custom")"
    setup_fake_keychain

    # 個人アカウントとして 1 回
    export FAKE_KEYCHAIN_SERVICE="Claude Code-credentials"
    unset CLAUDE_CONFIG_DIR
    run_statusline
    [ "$status" -eq 0 ]

    # 仕事アカウントとして 1 回
    export FAKE_KEYCHAIN_SERVICE="Claude Code-credentials-$tag"
    export CLAUDE_CONFIG_DIR="$custom"
    run_statusline
    [ "$status" -eq 0 ]

    [ -f "$XDG_CACHE_HOME/claude/usage-cache-default.json" ]
    [ -f "$XDG_CACHE_HOME/claude/usage-cache-$tag.json" ]
}

@test "statusline: shows the account address on the first line" {
    local custom="$TEST_HOME/.claude-hamiltonian"
    mkdir -p "$custom"
    echo '{"oauthAccount":{"emailAddress":"work@example.com"}}' > "$custom/.claude.json"
    setup_fake_keychain
    export CLAUDE_CONFIG_DIR="$custom"

    run_statusline

    [ "$status" -eq 0 ]
    # 色だけに情報を持たせないため、アドレスの文字列そのものが出ていること
    assert_contains "$output" "work@example.com"
}

@test "statusline: emits color escapes rather than literal escape text" {
    setup_fake_keychain

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
    setup_fake_keychain

    statusline_raw "$TEST_HOME/out.txt"

    [ "$(count_newlines "$TEST_HOME/out.txt")" -eq 2 ]
}

@test "statusline: emits four lines inside a repository without a trailing newline" {
    # 4 行 + 末尾改行なし = 改行 3 個。3 行目の改行落ちも余分な末尾改行も検出する
    setup_fake_keychain
    setup_test_repo "$TEST_HOME/myrepo"

    statusline_raw "$TEST_HOME/out.txt" "$TEST_HOME/myrepo"

    [ "$(count_newlines "$TEST_HOME/out.txt")" -eq 3 ]
}

@test "statusline: puts the repository line last" {
    setup_fake_keychain
    setup_test_repo "$TEST_HOME/myrepo"

    run_statusline_in "$TEST_HOME/myrepo"

    [ "$status" -eq 0 ]
    [ "${#lines[@]}" -eq 4 ]
    assert_contains "${lines[3]}" "myrepo"
}

@test "statusline: keeps repository info out of the first line" {
    # 4 行目へ移したのに 1 行目にも残っている二重表示を防ぐ
    setup_fake_keychain
    setup_test_repo "$TEST_HOME/myrepo"

    run_statusline_in "$TEST_HOME/myrepo"

    [ "$status" -eq 0 ]
    refute_contains "${lines[0]}" "myrepo"
}

@test "statusline: keeps the rate limit bars on the middle lines" {
    # リポジトリ行を足したときに 5h / 7d が押し出されていないこと
    setup_fake_keychain
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
