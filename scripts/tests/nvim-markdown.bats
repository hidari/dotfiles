#!/usr/bin/env bats
# =============================================================================
# nvim の Markdown 配色の不変条件を headless で検証する
#
# 注意:
# - bats は @test 名を関数名へエンコードするため名前は ASCII に限る
#   (rules/bats-test-name-ascii-only.yml)
# - nvim --clean は user config を読まないので lazy.nvim が起動せず、プラグインの
#   clone もパーサのビルドも起きない。markdown / markdown_inline のパーサは本体同梱。
# - after/queries は rtp の独立したエントリとして足す必要がある (自動では入らない)。
# =============================================================================

load test_helper

NVIM_CONFIG_DIR="$REPO_ROOT/home/.config/nvim"
PROBE="$REPO_ROOT/scripts/tests/nvim-markdown-probe.lua"

# skip ガード自体を検証できるように、実行する nvim を差し替え可能にする。
# bats と nvim が同じディレクトリに入るため PATH から隠す方式は使えない。
NVIM_BIN="${NVIM_BIN:-nvim}"

setup() {
    if ! command -v "$NVIM_BIN" >/dev/null 2>&1; then
        # CI では Neovim の導入失敗を skip で隠さない。
        # 緑のまま何も検証していない状態が一番危ない
        if [ -n "${CI:-}" ]; then
            echo "nvim is required in CI but was not found" >&2
            return 1
        fi
        skip "nvim is not installed"
    fi
}

# 本番と同じ rtp 構成 (拡張クエリを含む) でプローブを走らせる
probe_with_extends() {
    "$NVIM_BIN" --clean --headless \
        --cmd "set rtp+=$NVIM_CONFIG_DIR" \
        --cmd "set rtp+=$NVIM_CONFIG_DIR/after" \
        -c "luafile $PROBE" -c 'qa!' 2>&1
}

# 拡張クエリを外して走らせる。検査が本当に効いていることを示す negative case 用
probe_without_extends() {
    "$NVIM_BIN" --clean --headless \
        --cmd "set rtp+=$NVIM_CONFIG_DIR" \
        -c "luafile $PROBE" -c 'qa!' 2>&1
}

@test "markdown palette: six heading levels are defined" {
    run probe_with_extends
    assert_contains "$output" "HEADING_LEVELS=6"
}

@test "markdown palette: heading levels have distinct foreground colors" {
    # 見出しが同色だと階層が読めない。これが元の不満そのもの
    run probe_with_extends
    assert_contains "$output" "HEADING_FG_DUPLICATES=0"
}

@test "markdown palette: every group exists as a treesitter capture" {
    # 存在しないグループへ色を定義しても Neovim は黙って無視するので静的に弾く
    run probe_with_extends
    assert_contains "$output" "MISSING_CAPTURES="
    refute_contains "$output" "MISSING_CAPTURES=@"
}

@test "extends query captures all six atx heading markers" {
    run probe_with_extends
    assert_contains "$output" "MARKER_CAPTURES=6"
}

@test "without the extends query the marker checks fail" {
    # 上の 2 つの検査が拡張クエリに支えられていることを示す
    # (拡張を外しても緑のままなら、その検査は何も守っていない)
    run probe_without_extends
    assert_contains "$output" "MARKER_CAPTURES=0"
    assert_contains "$output" "MISSING_CAPTURES=@markup.heading.marker"
}
