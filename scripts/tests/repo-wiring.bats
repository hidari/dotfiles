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
