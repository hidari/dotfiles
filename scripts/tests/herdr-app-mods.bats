#!/usr/bin/env bats
# =============================================================================
# herdr-app の自作 mod のテスト
# =============================================================================
#
# このスクリプトが守る仕様は 2 つ。
#   1. pane-next と pane-prev の cycle.js は同じ内容を持つ。mod はフォルダの外を import
#      できないので 1 つを共有できず、片方だけ直すと巡回の向きによって挙動が変わる
#   2. 追跡下の mod はどれも herdr-app に読み込めて、1 度描画できる。mod の JavaScript の
#      構文エラーや import の解決失敗は、herdr-app に読ませるまでどの検査にも出ない
#
# keys.json の検査は config-guard の herdr_app_keys が持つ。

load test_helper

MODS_DIR="$REPO_ROOT/home/.config/herdr-app/mods"

@test "cycle.js: pane-next and pane-prev carry the same file" {
    run cmp "$MODS_DIR/pane-next/cycle.js" "$MODS_DIR/pane-prev/cycle.js"

    [ "$status" -eq 0 ]
}

# herdr-app は macOS の開発機にしか無いので、タグで CI の実行対象から外す
# bats test_tags=uncovered
@test "check: every tracked mod loads and renders in herdr-app" {
    require_command_or_skip herdr-app || return 1

    local checked=0 mod
    for mod in "$MODS_DIR"/*/; do
        run herdr-app check "$mod"
        [ "$status" -eq 0 ] || { echo "$mod: $output" >&2; return 1; }
        checked=$((checked + 1))
    done

    # glob が何も拾わないと 1 件も見ずに通るので、見た数が 0 でないことを確かめる
    [ "$checked" -gt 0 ]
}
