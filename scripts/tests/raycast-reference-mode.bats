#!/usr/bin/env bats
# =============================================================================
# Raycast リファレンスモード切り替えのテスト
# =============================================================================
#
# このスクリプトが守る仕様は 5 つ。
#   1. トグルは 2 値。編集用プリセットにいるときだけ普段用へ戻り、それ以外
#      (普段用・第三のプリセット) からは編集用へ入る
#   2. 現在値が読めなかったら何も適用せず失敗する。空文字を「編集用ではない」と
#      解釈して編集用へ倒すと、UI 走査の失敗が意図しない切り替えに化ける
#   3. 適用後に実際の値を突き合わせ、要求と違えば失敗する。AppleScript の click は
#      成功を返しても実際には反映されないことがあり、click の戻り値だけでは信用できない
#   4. osascript が非ゼロで終わったらそこで止める
#   5. source しても main を実行しない (テストや他スクリプトが GUI を開かないため)
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

# 空文字は UI 走査の失敗を意味する。ここで編集用へ倒すと、読み取れなかっただけなのに
# 勝手にプリセットが変わる。失敗として扱う。
@test "next_preset: fails when the current preset is empty" {
    run next_preset ""

    [ "$status" -ne 0 ]
}

# =============================================================================
# プリセット定数
# =============================================================================

@test "presets: the editing and everyday presets are distinct and non-empty" {
    [ -n "$EDITING_PRESET" ]
    [ -n "$EVERYDAY_PRESET" ]
    [ "$EDITING_PRESET" != "$EVERYDAY_PRESET" ]
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
# 何へ切り替わったかが分かる必要がある。
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

# 失敗して System Settings が開きっぱなしになるのが元のバグの見え方だった。
# エラー時こそ後片付けを通す。
@test "main: closes System Settings when the current preset cannot be read" {
    run main

    [ "$status" -ne 0 ]
    assert_contains "$(cat "$FAKE_OSASCRIPT_LOG")" "mode=close"
}

# click が成功しても実際には反映されないケース。適用後の突き合わせが無いと
# 「成功した」と報告しながら何も変わっていない状態になる。
@test "main: fails when the applied preset does not match the requested one" {
    export FAKE_CURRENT_PRESET="$EVERYDAY_PRESET"
    export FAKE_APPLIED_PRESET="$EVERYDAY_PRESET"

    run main

    [ "$status" -ne 0 ]
}

@test "main: fails when reading the current preset exits non-zero" {
    export FAKE_CURRENT_PRESET="$EVERYDAY_PRESET"
    export FAKE_OSASCRIPT_FAIL="read"

    run main

    [ "$status" -ne 0 ]
    refute_contains "$(cat "$FAKE_OSASCRIPT_LOG")" "mode=apply"
}

@test "main: fails when applying the preset exits non-zero" {
    export FAKE_CURRENT_PRESET="$EVERYDAY_PRESET"
    export FAKE_OSASCRIPT_FAIL="apply"

    run main

    [ "$status" -ne 0 ]
}
