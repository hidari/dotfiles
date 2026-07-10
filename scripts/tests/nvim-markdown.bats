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

@test "appearance keeps the Normal background transparent" {
    # Normal の bg=NONE を壊すと端末背景の透過が失われる
    run probe_with_extends
    assert_contains "$output" "NORMAL_BG=nil"
}

@test "highlights survive a colorscheme load" {
    # colorscheme は hi clear を伴う。ColorScheme autocmd が無いと透過も配色も消える
    run probe_with_extends
    before=$(printf '%s\n' "$output" | sed -n 's/^H1_FG=//p')
    after=$(printf '%s\n' "$output" | sed -n 's/^AFTER_CS_H1_FG=//p')
    [ -n "$before" ]
    [ "$before" != "nil" ]
    [ "$before" = "$after" ]
    assert_contains "$output" "AFTER_CS_NORMAL_BG=nil"
}

@test "scoped palette does not bleed muted into global capture groups" {
    # @punctuation.special / @conceal / @label は他文法と共有する汎用キャプチャ名。
    # 素で定義すると非 markdown のバッファへ markdown の MUTED 灰色が漏れる。
    # 言語サフィックス付きへ逃がし、グローバル群が MUTED を帯びないことを保証する
    # (このブランチの核心)。同時にスコープした markdown 用グループには MUTED が乗っていること
    run probe_with_extends
    assert_contains "$output" "GLOBAL_BLEED=0"
    assert_contains "$output" "SCOPED_MUTED_APPLIED=1"
}

@test "conceal capture wins over strong at delimiter" {
    # **bold** の先頭 * 列は @markup.strong と @conceal の両方が捕捉する。
    # 同一優先度では後発キャプチャが勝つため、記号を暗くするには @conceal が
    # @markup.strong より後にイテレートされている必要がある (これがブランチの目玉挙動)
    run probe_with_extends
    assert_contains "$output" "CONCEAL_AFTER_STRONG=1"
}

@test "contrast helper is calibrated against known values" {
    # 白と黒は 21:1、同色は 1:1。ここが崩れたら以降の判定は全て無意味
    run probe_with_extends
    assert_contains "$output" "CONTRAST_SELFTEST_MAX=21.00"
    assert_contains "$output" "CONTRAST_SELFTEST_MIN=1.00"
}

@test "palette: the contrast check detects a color below its tier" {
    # 検査が本当に効いていることを示す negative case。
    # 旧 MUTED は基準背景の上で 1.01:1 しかなく symbol tier を満たさない
    run probe_with_extends
    assert_contains "$output" "VIOLATION_DETECTOR_WORKS=1"
    assert_contains "$output" "SENTINEL_RATIO=1.01"
}

@test "palette: every token meets the contrast target of its tier" {
    # 基準背景の上で読めない色をパレットへ入れられないようにする
    run probe_with_extends
    assert_contains "$output" "PALETTE_VIOLATION_COUNT=0"
}
