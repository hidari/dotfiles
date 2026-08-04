#!/usr/bin/env bats
# =============================================================================
# Raycast リファレンスモード切り替えのテスト
# =============================================================================
#
# このスクリプトが守る仕様は 7 つ。
#   1. トグルは 2 値。編集用プリセットにいるときだけ普段用へ戻り、それ以外
#      (普段用・第三のプリセット) からは編集用へ入る
#   2. 現在値が読めなかったら何も適用せず失敗する。空文字を「編集用ではない」と
#      解釈して編集用へ倒すと、UI 走査の失敗が意図しない切り替えに化ける
#   3. 適用後に実際の値を突き合わせ、要求と違えば失敗する。AppleScript の click は
#      成功を返しても実際には反映されないことがあり、click の戻り値だけでは信用できない
#   4. osascript が非ゼロで終わったらそこで止める
#   5. どの失敗経路でも System Settings を閉じる
#   6. 切り替え対象の 2 つは popup 識別リストの要素である。外れると popup が
#      永久に見つからない
#   7. source しても main を実行しない (テストや他スクリプトが GUI を開かないため)
#
# UI 操作そのもの (コールドスタートでの待機、メニュー展開) はここでは検証できない。
# GUI を持たない CI では原理的に踏めないため、live smoke に委ねる。

load test_helper

setup() {
    setup_test_home
    setup_fake_osascript
    load_raycast_toggle_functions
}

teardown() {
    teardown_test_home
}

# =============================================================================
# next_preset (純粋ロジック)
# =============================================================================

@test "next_preset: returns the everyday preset when the editing preset is active" {
    run next_preset "$EDITING_PRESET"

    [ "$status" -eq 0 ]
    [ "$output" = "$EVERYDAY_PRESET" ]
}

@test "next_preset: returns the editing preset when the everyday preset is active" {
    run next_preset "$EVERYDAY_PRESET"

    [ "$status" -eq 0 ]
    [ "$output" = "$EDITING_PRESET" ]
}

# 第三のプリセット (手動で別のものを選んでいた場合) からは編集用へ入る。
# 「編集したい」という利用者の意図に対して、まず編集用へ倒すのが最短。
@test "next_preset: returns the editing preset from any unrelated preset" {
    run next_preset "HDR Video (P3-ST 2084)"

    [ "$status" -eq 0 ]
    [ "$output" = "$EDITING_PRESET" ]
}

# =============================================================================
# プリセット定数
# =============================================================================

@test "presets: the editing and everyday presets are distinct and non-empty" {
    [ -n "$EDITING_PRESET" ]
    [ -n "$EVERYDAY_PRESET" ]
    [ "$EDITING_PRESET" != "$EVERYDAY_PRESET" ]
}

# popup の同定は「現在値が識別リストに含まれるか」だけが頼りなので、切り替え対象が
# リストから外れると popup が永久に見つからず、タイムアウトしてから
# 「コントロールが見つかりませんでした」という原因から遠いメッセージで落ちる。
@test "presets: both toggle targets are members of the identification list" {
    assert_array_contains "$EDITING_PRESET" "${PRESET_NAMES[@]}"
    assert_array_contains "$EVERYDAY_PRESET" "${PRESET_NAMES[@]}"
}

# =============================================================================
# 埋め込み AppleScript
# =============================================================================

# AppleScript の構文エラーは bash 側からは見えず、実行して初めて -2700 系の実行時
# エラーになる。予約語との衝突 (path / round など) は特に踏みやすい。
# 挙動は GUI 依存で検証できないが、コンパイルが通ることだけは GUI 抜きで確かめられる。
@test "applescript: the embedded block compiles" {
    command -v osacompile > /dev/null 2>&1 || skip "osacompile is unavailable"

    [ -n "$DISPLAY_APPLESCRIPT" ]
    printf '%s' "$DISPLAY_APPLESCRIPT" > "$TEST_HOME/embedded.applescript"

    run osacompile -o "$TEST_HOME/embedded.scpt" "$TEST_HOME/embedded.applescript"

    [ "$status" -eq 0 ]
}

# 識別リストの canonical は bash 側にあり、AppleScript へは引数で渡る。
# 渡し忘れると AppleScript 側のリストが空のままになり、どの popup とも一致しない。
@test "applescript: the identification list reaches osascript" {
    export FAKE_CURRENT_PRESET="$EVERYDAY_PRESET"

    run main

    [ "$status" -eq 0 ]

    local logged
    logged=$(cat "$FAKE_OSASCRIPT_LOG")

    # 先頭要素は presets= の直後に来る。リストの順序が保たれていることの確認を兼ねる。
    assert_contains "$logged" "presets=${PRESET_NAMES[0]}"

    local name
    for name in "${PRESET_NAMES[@]}"; do
        assert_contains "$logged" "$name"
    done
}

# =============================================================================
# source ガード
# =============================================================================

# setup で load_raycast_toggle_functions を通っているので、その時点で main が
# 走っていれば osascript の呼び出しが記録されている。ガードが外れるとテスト実行が
# System Settings を開き始めるため、ここは実害の予防線でもある。
@test "source guard: sourcing the script does not invoke osascript" {
    run cat "$FAKE_OSASCRIPT_LOG"

    [ "$status" -eq 0 ]
    [ "$output" = "" ]
}

# =============================================================================
# main (bash 側のオーケストレーション)
# =============================================================================

@test "main: applies the editing preset when the everyday preset is active" {
    export FAKE_CURRENT_PRESET="$EVERYDAY_PRESET"

    run main

    [ "$status" -eq 0 ]
    assert_contains "$(cat "$FAKE_OSASCRIPT_LOG")" "mode=apply preset=$EDITING_PRESET"
}

@test "main: applies the everyday preset when the editing preset is active" {
    export FAKE_CURRENT_PRESET="$EDITING_PRESET"

    run main

    [ "$status" -eq 0 ]
    assert_contains "$(cat "$FAKE_OSASCRIPT_LOG")" "mode=apply preset=$EVERYDAY_PRESET"
}

# 適用したプリセット名を利用者に返す。Raycast の HUD に出る唯一の手がかりなので、
# 何へ切り替わったかが分かる必要がある。上の 2 件と setup は同じだが、観測点が
# 「osascript に何を渡したか」と「利用者に何を見せたか」で別の仕様なので分けている。
@test "main: reports the preset it switched to" {
    export FAKE_CURRENT_PRESET="$EVERYDAY_PRESET"

    run main

    [ "$status" -eq 0 ]
    assert_contains "$output" "$EDITING_PRESET"
}

@test "main: fails without applying anything when the current preset cannot be read" {
    # FAKE_CURRENT_PRESET を設定しない = read が空文字を返す
    run main

    [ "$status" -ne 0 ]
    refute_contains "$(cat "$FAKE_OSASCRIPT_LOG")" "mode=apply"
}

# 後片付けの pin。失敗経路で close を落とすと System Settings が開いたまま残り、
# 「開くが何も起きない」という見え方になる。以下 4 件で全失敗経路を押さえる。
@test "main: closes System Settings when the current preset cannot be read" {
    run main

    [ "$status" -ne 0 ]
    assert_contains "$(cat "$FAKE_OSASCRIPT_LOG")" "mode=close"
}

@test "main: fails and closes System Settings when the applied preset does not match" {
    export FAKE_CURRENT_PRESET="$EVERYDAY_PRESET"
    export FAKE_APPLIED_PRESET="$EVERYDAY_PRESET"

    run main

    [ "$status" -ne 0 ]
    assert_contains "$(cat "$FAKE_OSASCRIPT_LOG")" "mode=close"
}

@test "main: fails and closes System Settings when reading exits non-zero" {
    export FAKE_CURRENT_PRESET="$EVERYDAY_PRESET"
    export FAKE_OSASCRIPT_FAIL="read"

    run main

    [ "$status" -ne 0 ]
    refute_contains "$(cat "$FAKE_OSASCRIPT_LOG")" "mode=apply"
    assert_contains "$(cat "$FAKE_OSASCRIPT_LOG")" "mode=close"
}

@test "main: fails and closes System Settings when applying exits non-zero" {
    export FAKE_CURRENT_PRESET="$EVERYDAY_PRESET"
    export FAKE_OSASCRIPT_FAIL="apply"

    run main

    [ "$status" -ne 0 ]
    assert_contains "$(cat "$FAKE_OSASCRIPT_LOG")" "mode=close"
}
