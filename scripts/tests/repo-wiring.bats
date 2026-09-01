#!/usr/bin/env bats
# =============================================================================
# repo-wiring (運用指示の取り付け) のテスト
# =============================================================================

load test_helper

bats_require_minimum_version 1.5.0

# 変異注入でコピーを読ませられるよう上書き可能にする。既定値は実ファイルなので
# 通常実行と CI の対象は変わらない (test_helper.bash の BOOTSTRAP_SCRIPT と同じ規約)。
WIRING="${WIRING:-$REPO_ROOT/scripts/repo-wiring/repo-wiring}"

setup() {
    setup_test_home
    TARGET="$TEST_HOME/repo"
    mkdir -p "$TARGET"
    git -C "$TARGET" init -q .
    OPS="$TEST_HOME/cloud/private-ops"
    mkdir -p "$OPS"
}

teardown() {
    teardown_test_home
}

@test "repo-wiring requires the ops option" {
    # 非 0 終了だけを見ると、guard を外しても後段の -d "" が偽になって
    # fail() が exit 1 で落ちるため区別できない (dead pin)。
    # usage の終了コード 2 と、usage にしか出ない文字列の両方を見る。
    run "$WIRING" "$TARGET"

    [ "$status" -eq 2 ]
    assert_contains "$output" "--ops"
}

@test "check requires the ops option" {
    printf '%s\n' "$TARGET" > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --list "$TEST_HOME/repos.txt"

    [ "$status" -eq 2 ]
    assert_contains "$output" "--ops"
}

@test "repo-wiring creates the hidari directory and the symlink" {
    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    [ -d "$TARGET/.hidari" ]
    [ -L "$TARGET/.hidari/private-ops" ]
    [ -e "$TARGET/.hidari/private-ops" ]
}

@test "repo-wiring writes the exclude entry before creating the symlink" {
    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    grep -q '^\.hidari/$' "$TARGET/.git/info/exclude"
}

@test "repo-wiring is idempotent" {
    run "$WIRING" --ops "$OPS" "$TARGET"
    [ "$status" -eq 0 ]

    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    [ "$(grep -c '^\.hidari/$' "$TARGET/.git/info/exclude")" -eq 1 ]
}

@test "repo-wiring repairs a dangling symlink" {
    mkdir -p "$TARGET/.hidari"
    ln -s "$TEST_HOME/gone" "$TARGET/.hidari/private-ops"

    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    [ -e "$TARGET/.hidari/private-ops" ]
}

@test "repo-wiring refuses when the path is still not ignored" {
    # .gitignore で明示的に再包含すると exclude を書いても ignore されない。
    # スクリプト自身が ignore を用意しても穴が残る経路がこれで、fail-closed を測る。
    printf '!.hidari/\n' > "$TARGET/.gitignore"

    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -ne 0 ]
    [ ! -e "$TARGET/.hidari/private-ops" ]
}

@test "repo-wiring writes the cache exclude entry too" {
    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    grep -qx '\.cache/' "$TARGET/.git/info/exclude"
}

@test "repo-wiring is idempotent for the cache exclude entry" {
    run "$WIRING" --ops "$OPS" "$TARGET"
    [ "$status" -eq 0 ]

    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    [ "$(grep -c '^\.cache/$' "$TARGET/.git/info/exclude")" -eq 1 ]
}

@test "repo-wiring refuses when the cache path is still not ignored" {
    # .hidari/ 側は通り .cache/ 側だけが塞がれる状態を作る。両方を塞ぐと
    # どちらの guard で落ちたのか区別できない。
    printf '!.cache/\n' > "$TARGET/.gitignore"

    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -ne 0 ]
    assert_contains "$output" ".cache/"
    [ ! -e "$TARGET/.hidari/private-ops" ]
}

@test "repo-wiring refuses when the ops directory does not exist" {
    run "$WIRING" --ops "$TEST_HOME/missing" "$TARGET"

    [ "$status" -ne 0 ]
}

@test "repo-wiring refuses when the target is not a git repository" {
    # 単に非 0 終了と .hidari 不在だけを見ると、この guard を外しても後段の
    # check-ignore が別経路で fail-closed するため区別できない (dead pin)。
    # このテスト固有の fail メッセージと、guard を通れば作られるはずの
    # .git/info/exclude が作られていないことまで見て、この guard 自体を pin する。
    local not_a_repo="$TEST_HOME/not-a-repo"
    mkdir -p "$not_a_repo"

    run "$WIRING" --ops "$OPS" "$not_a_repo"

    [ "$status" -ne 0 ]
    assert_contains "$output" "git リポジトリではありません"
    [ ! -e "$not_a_repo/.git" ]
    [ ! -e "$not_a_repo/.hidari" ]
}

@test "check reports a repo listed but not wired" {
    printf '%s\n' "$TARGET" > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "$TARGET"
    assert_contains "$output" "missing"
}

@test "check stays silent for a wired repo" {
    "$WIRING" --ops "$OPS" "$TARGET"
    printf '%s\n' "$TARGET" > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -eq 0 ]
    assert_contains "$output" "ok"
}

@test "check always prints the population count" {
    printf '%s\n' "$TARGET" > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    # 0 件と見ていないを区別するため、問題の有無にかかわらず母数を出す
    assert_contains "$output" "listed=1"
}

@test "check rejects a malformed line instead of ignoring it" {
    printf 'relative/path\n' > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "rejected"
    # 却下した行も母数に数える。この行が無いと、加算を却下判定の後ろへ動かす
    # 変異が生存する (実測で確認済み)。
    assert_contains "$output" "listed=1"
}

@test "check skips comments and blank lines" {
    printf '# comment\n\n%s\n' "$TARGET" > "$TEST_HOME/repos.txt"
    "$WIRING" --ops "$OPS" "$TARGET"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -eq 0 ]
    assert_contains "$output" "listed=1"
}

@test "check reports a vanished repo" {
    printf '%s\n' "$TEST_HOME/gone" > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "vanished"
}

# --- 以下 3 件は既定値の分岐と取り付け判定 (-e の甘さ) を pin する。省略しないこと ---

@test "check falls back to the list inside the ops directory" {
    # --list を省略する唯一のテスト。これが無いと既定値の導出行を壊しても
    # 全テストが緑のままになる (毎回明示で上書きされる値は pin されない)。
    "$WIRING" --ops "$OPS" "$TARGET"
    printf '%s\n' "$TARGET" > "$OPS/repos.txt"

    run "$WIRING" --check --ops "$OPS"

    [ "$status" -eq 0 ]
    assert_contains "$output" "listed=1"
}

@test "check rejects a plain file standing in for the symlink" {
    # -e は通常ファイルでも真になるので、それだけでは取り付け済みと区別できない。
    mkdir -p "$TARGET/.hidari"
    : > "$TARGET/.hidari/private-ops"
    printf '%s\n' "$TARGET" > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "missing"
}

@test "check rejects a symlink pointing elsewhere" {
    # 解決先を見ないと、別の場所を指す symlink が取り付け済みとして通る。
    local other="$TEST_HOME/other-ops"
    mkdir -p "$TARGET/.hidari" "$other"
    ln -sfn "$other" "$TARGET/.hidari/private-ops"
    printf '%s\n' "$TARGET" > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "missing"
}
