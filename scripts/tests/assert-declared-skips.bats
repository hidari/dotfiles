#!/usr/bin/env bats
# =============================================================================
# TAP 出力の skip 集合を宣言と突き合わせるガード (scripts/ci/assert-declared-skips.sh) の検証
#
# CI の bats job が緑であることを「全スイートを検証した」の証拠にするための最後の堰。
# 期待値の文字列は宣言表 (UNCOVERED_DEPENDENCIES) から組み立てる。ここへ理由を literal で
# 書き写すと、表を直したときテスト側だけが取り残される。
#
# 注意:
# - bats は @test 名を関数名へエンコードするため名前は ASCII に限る
#   (rules/bats-test-name-ascii-only.yml)
# =============================================================================

load test_helper

ASSERT_SCRIPT="$REPO_ROOT/scripts/ci/assert-declared-skips.sh"

setup() {
    TAP="$BATS_TEST_TMPDIR/out.tap"
}

# 宣言表の全エントリを発火させた skip 行を組み立てる。
# 1 つでも欠けるとガードは dead な宣言として落とすので、正常系の土台に要る。
all_declared_skip_lines() {
    local entry dep n=1
    for entry in "${UNCOVERED_DEPENDENCIES[@]}"; do
        dep="${entry%%:*}"
        printf 'ok %d guarded test for %s # skip %s %s: %s\n' \
            "$n" "$dep" "$UNCOVERED_SKIP_MARKER" "$dep" "${entry#*:}"
        n=$((n + 1))
    done
}

# 正常系の TAP を組み立てる。追加行があれば末尾へ足す。
write_tap() {
    {
        echo "ok 100 an ordinary test that ran"
        all_declared_skip_lines
        if [ "$#" -gt 0 ]; then
            printf '%s\n' "$@"
        fi
    } > "$TAP"
}

@test "accepts a TAP where every skip carries a declared marker" {
    write_tap

    run bash "$ASSERT_SCRIPT" "$TAP"

    [ "$status" -eq 0 ]
}

@test "rejects a skip that carries no marker" {
    # 生の skip がテストへ戻ってきた形。これを通すと「静かな全 skip」が復活する
    write_tap "ok 101 a test that quietly skipped # skip gitleaks is not installed"

    run bash "$ASSERT_SCRIPT" "$TAP"

    [ "$status" -ne 0 ]
    assert_contains "$output" "a test that quietly skipped"
}

@test "rejects a marked skip whose dependency is not in the table" {
    # マーカーだけ真似た skip を通さない。ヘルパ経由なら起こらないが、
    # 突き合わせの根拠がマーカーの有無だけになっていないことを示す
    write_tap "ok 102 forged # skip $UNCOVERED_SKIP_MARKER not-in-the-table: なにか"

    run bash "$ASSERT_SCRIPT" "$TAP"

    [ "$status" -ne 0 ]
    assert_contains "$output" "not-in-the-table"
}

@test "rejects a declared dependency that never skipped" {
    # 宣言だけが残って実際には skip されない状態 (dead な宣言)。
    # コマンドが CI へ入ったのに宣言を消し忘れた形がこれになる
    {
        echo "ok 1 an ordinary test that ran"
    } > "$TAP"

    run bash "$ASSERT_SCRIPT" "$TAP"

    [ "$status" -ne 0 ]
    assert_contains "$output" "${UNCOVERED_DEPENDENCIES[0]%%:*}"
}

@test "rejects a TAP that contains no executed test at all" {
    # bats がファイルを 1 件も見つけられなかったときの形。skip が 0 件なので
    # 「宣言外の skip は無い」を満たしてしまう
    printf '1..0\n' > "$TAP"

    run bash "$ASSERT_SCRIPT" "$TAP"

    [ "$status" -ne 0 ]
}

# 宣言表を空にしたヘルパを書き出す。表が空なのは異常ではなく、
# 全依存が CI へ入って未カバーが無くなった状態を意味する。
write_empty_table_helper() {
    local helper="$BATS_TEST_TMPDIR/empty-table.bash"
    {
        printf 'source "%s"\n' "$TEST_DIR/test_helper.bash"
        printf 'UNCOVERED_DEPENDENCIES=()\n'
    } > "$helper"
    printf '%s' "$helper"
}

@test "rejects a TAP with no executed test even when nothing is declared uncovered" {
    # 実行 0 件の検査が dead な宣言の検査に横取りされていないことを見る。
    # 表が空でないうちは skip 0 件が必ず dead な宣言としても落ちるので、
    # この分岐だけを壊しても赤くならない (変異注入で実際に生き残った)
    local helper
    helper=$(write_empty_table_helper)
    printf '1..0\n' > "$TAP"

    run env TEST_HELPER="$helper" bash "$ASSERT_SCRIPT" "$TAP"

    [ "$status" -ne 0 ]
    assert_contains "$output" "実行されたテストが 1 件も無い"
}

@test "reports a marked skip as undeclared when the table was emptied" {
    # 宣言を消したのに skip 側が残っている形。ここで初めて uncovered_reason が
    # 空の表を引く。ガードが無いと bash 3.2 の set -u が unbound variable で落とすので、
    # rc だけを見ると「正しく検出した」と読み違える。メッセージまで確かめる
    local helper
    helper=$(write_empty_table_helper)
    printf 'ok 1 leftover skip # skip %s osacompile: 宣言を消した後の残骸\n' \
        "$UNCOVERED_SKIP_MARKER" > "$TAP"

    run env TEST_HELPER="$helper" bash "$ASSERT_SCRIPT" "$TAP"

    [ "$status" -ne 0 ]
    assert_contains "$output" "宣言表に無い依存"
}

@test "accepts an empty uncovered table when tests did run" {
    # 上の対照。空の表で常に落ちる実装を「正しく落ちた」と読み違えないために要る。
    # bash 3.2 は set -u 下で空配列の [@] 展開を unbound variable にするので、
    # 件数ガードを外すとここが落ちる
    local helper
    helper=$(write_empty_table_helper)
    printf 'ok 1 an ordinary test that ran\n' > "$TAP"

    run env TEST_HELPER="$helper" bash "$ASSERT_SCRIPT" "$TAP"

    [ "$status" -eq 0 ]
}

@test "rejects an empty TAP file" {
    : > "$TAP"

    run bash "$ASSERT_SCRIPT" "$TAP"

    [ "$status" -ne 0 ]
}

@test "rejects a TAP path that does not exist" {
    run bash "$ASSERT_SCRIPT" "$BATS_TEST_TMPDIR/missing.tap"

    [ "$status" -ne 0 ]
}

@test "rejects being called without a TAP path" {
    run bash "$ASSERT_SCRIPT"

    [ "$status" -ne 0 ]
    assert_contains "$output" "usage"
}

@test "accepts the real suites once the uncovered dependencies are made absent" {
    # 合成 TAP は突き合わせ器そのものを測るが、宣言表が実態と噛み合っているかは測れない。
    # 未カバー依存を不在にした実スイートを端から端まで通し、宣言した 2 件がちょうど
    # skip されることを確認する。ローカルにはどちらも実在するので、差し替え可能にした
    # 入口 (OSACOMPILE_BIN / NEOTREE_HIGHLIGHTS) から不在を作る。
    # この 2 ファイルで UNCOVERED_DEPENDENCIES の全エントリを覆う
    local tap="$BATS_TEST_TMPDIR/real.tap"
    local rc=0

    env OSACOMPILE_BIN=definitely-not-installed NEOTREE_HIGHLIGHTS=/nonexistent \
        bats --formatter tap \
        "$TEST_DIR/raycast-reference-mode.bats" "$TEST_DIR/nvim-markdown.bats" \
        > "$tap" 2> /dev/null || rc=$?
    [ "$rc" -eq 0 ]

    run bash "$ASSERT_SCRIPT" "$tap"

    [ "$status" -eq 0 ]
}

@test "counts a failing test as executed so the count check does not mask failures" {
    # not ok も実行された 1 件。ここを ok だけで数えると、全件赤の TAP が
    # 「1 件も実行されていない」という別の理由で落ちて原因を取り違える
    {
        echo "not ok 1 something failed"
        all_declared_skip_lines
    } > "$TAP"

    run bash "$ASSERT_SCRIPT" "$TAP"

    [ "$status" -eq 0 ]
}
