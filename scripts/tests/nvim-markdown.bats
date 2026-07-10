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
    # マーカーの検査が拡張クエリに支えられていることを示す
    # (拡張を外しても緑のままなら、その検査は何も守っていない)
    # markdown.lua はマーカーへ色を定義しないので MISSING_CAPTURES には現れない
    run probe_without_extends
    assert_contains "$output" "MARKER_CAPTURES=0"
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

@test "link punctuation is scoped to markdown_inline" {
    # @markup.link はリンクや画像のノード全体を捕捉する。記号 ( [ ] ( ) ! ) だけでなく
    # URL の範囲も含むが、URL には後方で宣言された @markup.link.url が後勝ちするため、
    # muted が最終的に乗るのは記号だけになる。
    # 素で定義すると lua など他の文法へ muted が漏れるため言語スコープへ逃がす。
    # 解決経路は highlighter.lua と同じ '@<capture>.<lang>' を使う
    run probe_with_extends
    assert_contains "$output" "LINK_SCOPED_IN_MARKDOWN=1"
    assert_contains "$output" "LINK_NO_BLEED_TO_LUA=1"
}

@test "heading markers inherit the color of their heading level" {
    # マーカーへ色を定義せず、@ 名前空間の階層フォールバックで見出し色を継承させる。
    # @markup.heading.N.marker が未定義なら @markup.heading.N へ落ちる。
    # この検査は名前解決だけで成立するのでクエリには依存しない。
    # 拡張クエリが正しいキャプチャ名を与えていることは MARKER_CAPTURES=6 が受け持つ
    run probe_with_extends
    assert_contains "$output" "MARKER_INHERITS_HEADING=1"
}

@test "neo-tree palette defines the groups that were measured as unreadable" {
    # gitignored と未追跡ファイルは名前そのものに色が乗る。
    # インデント線と薄字は NeoTreeDimText に由来する
    run probe_with_extends
    assert_contains "$output" "NeoTreeGitIgnored"
    assert_contains "$output" "NeoTreeDotfile"
    assert_contains "$output" "NeoTreeHiddenByName"
    assert_contains "$output" "NeoTreeGitUntracked"
    assert_contains "$output" "NeoTreeGitConflict"
    assert_contains "$output" "NeoTreeDimText"
    assert_contains "$output" "NeoTreeExpander"
    assert_contains "$output" "NeoTreeIndentMarker"
    assert_contains "$output" "NeoTreeMessage"
}

@test "neo-tree palette is actually applied" {
    # グループが空だと下のループが回らず NEOTREE_APPLIED=1 のまま通ってしまう。
    # 空でないことを先に固定して偽の緑を塞ぐ
    run probe_with_extends
    refute_contains "$output" "NEOTREE_GROUP_COUNT=0"
    assert_contains "$output" "NEOTREE_APPLIED=1"
}

@test "non-color attributes bold and italic are actually applied" {
    # NeoTreeGitUntracked と NeoTreeGitConflict は fg が同一で bold だけが両者を分ける。
    # 見出しも色相に頼らず bold を併用する。fg 比較だけでは守れないので属性まで突き合わせる。
    # 検査対象が 0 件だと空回りして緑になるため件数も固定する
    run probe_with_extends
    refute_contains "$output" "ATTRIBUTE_CHECK_COUNT=0"
    assert_contains "$output" "ATTRIBUTE_VIOLATION_COUNT=0"
}

@test "palette hex raises on an unknown token instead of returning nil" {
    # トークンを改名すると palette.hex.<旧名> が nil を返し、nvim_set_hl はそれを
    # fg 未指定と解釈して既定色へ黙って戻す。__index ガードで nil ではなく error にし、
    # ごく普通のリファクタで色が消えて全テスト緑になる事故を塞ぐ
    run probe_with_extends
    assert_contains "$output" "HEX_UNKNOWN_KEY_ERRORS=1"
}

@test "neo-tree highlight group names exist in the plugin source" {
    # グループ名は treesitter のキャプチャではないので、綴りを間違えても Neovim は黙る。
    # CI にはプラグインを入れないため、その場合は検査できない
    src="${NEOTREE_HIGHLIGHTS:-$HOME/.local/share/nvim/lazy/neo-tree.nvim/lua/neo-tree/ui/highlights.lua}"
    if [ ! -f "$src" ]; then
        skip "neo-tree is not installed"
    fi

    run probe_with_extends
    # 検査対象が空のまま緑になるのを防ぐ
    refute_contains "$output" "NEOTREE_GROUP_COUNT=0"

    groups=$(printf '%s\n' "$output" | sed -n 's/^NEOTREE_GROUPS=//p' | tr ',' '\n')
    source_text=$(cat "$src")
    for group in $groups; do
        assert_contains "$source_text" "\"$group\""
    done
}

@test "delta e helper is calibrated against known values" {
    # OKLab の L は 0 から 1 なので白と黒はちょうど 1.0 になる
    run probe_with_extends
    assert_contains "$output" "DELTA_E_SELFTEST_MAX=1.0000"
    assert_contains "$output" "DELTA_E_SELFTEST_MIN=0.0000"
}

@test "delta e is pinned by a chromatic known answer" {
    # 白黒較正は cube-root を固定点 1 と 0 でしか通さず、同色較正は 0 なので、
    # どちらも to_oklab の立方根指数を 1/3 から 1/2 や 1.0 へ変えても値が動かない。
    # 有彩ペアだけが OKLab の非線形性を通す。期待値は Ottosson の原典から Python で独立に導出したもので
    # probe の出力から作ってはならない (同語反復になり何も守らなくなる)
    run probe_with_extends
    assert_contains "$output" "DELTA_E_KNOWN_CHROMATIC=0.004930"
}

@test "palette: the distinguishability check detects two colors that look alike" {
    # 実際に同化していた組を sentinel に使う
    run probe_with_extends
    assert_contains "$output" "JND_DETECTOR_WORKS=1"
}

@test "palette: every pair of distinct colors is perceptibly different" {
    # 比べる組が 0 だと下のループが回らず違反 0 のまま通ってしまう
    run probe_with_extends
    refute_contains "$output" "PALETTE_JND_PAIR_COUNT=0"
    assert_contains "$output" "PALETTE_JND_VIOLATION_COUNT=0"
}

@test "opaque surfaces meet the contrast target against their own background" {
    # 面が 0 個だと上のループが回らず違反 0 のまま通ってしまう
    run probe_with_extends
    refute_contains "$output" "SURFACE_COUNT=0"
    assert_contains "$output" "SURFACE_VIOLATION_COUNT=0"
}

@test "lualine uses the same colors as the palette surfaces" {
    # 値の drift を塞ぐ。hex を書き戻すこと自体は ast-grep が塞ぐ
    run probe_with_extends
    assert_contains "$output" "LUALINE_MATCHES_PALETTE=1"
}
