#!/usr/bin/env bats
# =============================================================================
# .zshrc の Claude Code 起動関数テスト
# =============================================================================
#
# 起動関数が守る仕様は 3 つ。
#   1. 個人アカウントは CLAUDE_CONFIG_DIR に触れない (Keychain の service 名の
#      導出条件が未確認のため、既定パスの明示指定という賭けをしない)
#   2. 仕事アカウントは config dir の存在を確認してから渡す (存在しない値は
#      Claude Code が黙って受け入れ、初期状態で起動してしまう)
#   3. タスクリスト ID はアカウントと直交する軸なので関数は持たず、未知の ID の
#      ときだけ知らせる (ブロックはしない)

load test_helper

setup() {
    setup_test_home
    # 呼び出し元シェルの環境が漏れるとアサーションが偽陽性/偽陰性になるため落とす
    unset CLAUDE_CONFIG_DIR
    unset CLAUDE_CODE_TASK_LIST_ID
}

teardown() {
    teardown_test_home
}

# =============================================================================
# _claude_task_list_notice
# =============================================================================

@test "_claude_task_list_notice: warns when the task list id is unknown" {
    load_zshrc_claude_functions

    CLAUDE_CODE_TASK_LIST_ID=nonexistent run _claude_task_list_notice "$TEST_HOME/.claude"

    # 新規作成は正当な操作なので、知らせるだけでブロックはしない
    [ "$status" -eq 0 ]
    assert_contains "$output" "新しいタスクリストを作成します: nonexistent"
}

@test "_claude_task_list_notice: stays silent when the task list already exists" {
    mkdir -p "$TEST_HOME/.claude/tasks/dotfiles"
    load_zshrc_claude_functions

    CLAUDE_CODE_TASK_LIST_ID=dotfiles run _claude_task_list_notice "$TEST_HOME/.claude"

    [ "$status" -eq 0 ]
    # 既知の ID で警告が出ると常時ノイズになり、本当の typo を見落とす
    [ -z "$output" ]
}

@test "_claude_task_list_notice: stays silent when no task list id is set" {
    load_zshrc_claude_functions

    run _claude_task_list_notice "$TEST_HOME/.claude"

    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "_claude_task_list_notice: distinguishes the config dir it inspects" {
    # タスクリストはアカウントごとに別なので、探索先が config dir 依存であることを pin する。
    # 個人側にだけ存在する ID を仕事側の config dir で問い合わせたら未知として扱う。
    mkdir -p "$TEST_HOME/.claude/tasks/dotfiles"
    mkdir -p "$TEST_HOME/.claude-hamiltonian"
    load_zshrc_claude_functions

    CLAUDE_CODE_TASK_LIST_ID=dotfiles run _claude_task_list_notice "$TEST_HOME/.claude-hamiltonian"

    [ "$status" -eq 0 ]
    assert_contains "$output" "新しいタスクリストを作成します: dotfiles"
}

# =============================================================================
# claude (個人アカウント)
# =============================================================================

@test "claude: launches without setting CLAUDE_CONFIG_DIR" {
    setup_recording_claude
    load_zshrc_claude_functions

    run claude

    [ "$status" -eq 0 ]
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    assert_contains "$recorded" "LAUNCHED"
    # 既定パスの明示指定は Keychain の service 名の導出を変えうるため、変数に触れないことが仕様
    refute_contains "$recorded" "CONFIG_DIR="
}

@test "claude: resolves to the real binary instead of recursing into itself" {
    setup_recording_claude
    load_zshrc_claude_functions

    run claude

    [ "$status" -eq 0 ]
    # command claude を使わないと関数が自分自身を呼び続ける。起動が 1 回だけであることで pin する
    local launches
    launches="$(grep -c '^LAUNCHED$' "$RECORDED_LAUNCH")"
    [ "$launches" -eq 1 ]
}

@test "claude: inspects the config dir handed in from outside" {
    # 前置で CLAUDE_CONFIG_DIR を渡すと起動先は別アカウントになるのに、確認先が
    # 個人側に固定されていると存在しない ID を既知と誤判定して黙る。
    # 「起動するアカウント」と「確認するアカウント」は一致していなければならない
    mkdir -p "$TEST_HOME/.claude/tasks/dotfiles"
    mkdir -p "$TEST_HOME/.claude-hamiltonian"
    setup_recording_claude
    load_zshrc_claude_functions

    CLAUDE_CONFIG_DIR="$TEST_HOME/.claude-hamiltonian" CLAUDE_CODE_TASK_LIST_ID=dotfiles run claude

    [ "$status" -eq 0 ]
    assert_contains "$output" "新しいタスクリストを作成します: dotfiles"
}

@test "claude: falls back to the default config dir when none is handed in" {
    # 上の裏返し。既定は個人側であり、外部指定が無いのに別の場所を見にいかないこと
    mkdir -p "$TEST_HOME/.claude/tasks/dotfiles"
    setup_recording_claude
    load_zshrc_claude_functions

    CLAUDE_CODE_TASK_LIST_ID=dotfiles run claude

    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "claude: forwards its arguments to the binary" {
    setup_recording_claude
    load_zshrc_claude_functions

    run claude --resume foo

    [ "$status" -eq 0 ]
    assert_contains "$(cat "$RECORDED_LAUNCH")" "ARGV=--resume foo"
}

# =============================================================================
# claude-hamiltonian (仕事アカウント)
# =============================================================================

@test "claude-hamiltonian: sets CLAUDE_CONFIG_DIR to the hamiltonian directory" {
    mkdir -p "$TEST_HOME/.claude-hamiltonian"
    setup_recording_claude
    load_zshrc_claude_functions

    run claude-hamiltonian

    [ "$status" -eq 0 ]
    assert_contains "$(cat "$RECORDED_LAUNCH")" "CONFIG_DIR=$TEST_HOME/.claude-hamiltonian"
}

@test "claude-hamiltonian: fails without launching when the config dir is missing" {
    # ディレクトリを作らない。Claude Code は存在しない値でも黙って初期状態で起動するため、
    # ここで止めないと未ログイン状態に落ちたことに /login を求められるまで気づけない
    setup_recording_claude
    load_zshrc_claude_functions

    run claude-hamiltonian

    [ "$status" -ne 0 ]
    assert_contains "$output" "設定ディレクトリが見つかりません"
    # 起動そのものを止めることが仕様。警告を出しつつ起動していたら無意味
    refute_contains "$(cat "$RECORDED_LAUNCH")" "LAUNCHED"
}

@test "claude-hamiltonian: passes the task list id through to the binary" {
    mkdir -p "$TEST_HOME/.claude-hamiltonian/tasks/dotfiles"
    setup_recording_claude
    load_zshrc_claude_functions

    # アカウント (関数) とタスクリスト (前置) が直交して合成できることを pin する
    CLAUDE_CODE_TASK_LIST_ID=dotfiles run claude-hamiltonian

    [ "$status" -eq 0 ]
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    assert_contains "$recorded" "CONFIG_DIR=$TEST_HOME/.claude-hamiltonian"
    assert_contains "$recorded" "TASK_LIST=dotfiles"
}

@test "claude-hamiltonian: warns about an unknown task list but still launches" {
    mkdir -p "$TEST_HOME/.claude-hamiltonian"
    setup_recording_claude
    load_zshrc_claude_functions

    CLAUDE_CODE_TASK_LIST_ID=typo run claude-hamiltonian

    [ "$status" -eq 0 ]
    assert_contains "$output" "新しいタスクリストを作成します: typo"
    assert_contains "$(cat "$RECORDED_LAUNCH")" "LAUNCHED"
}

# =============================================================================
# ローダー自身の健全性
# =============================================================================

@test "load_zshrc_claude_functions: fails loudly when the marker is missing" {
    # マーカーが消えたのに黙って空を source すると、以降の全テストが
    # 「関数が未定義なのにアサーションだけ通る」空虚な緑になる
    run load_marker_block "$ZSHRC_FILE" '^# nonexistent marker$' '^########################################$'

    [ "$status" -ne 0 ]
    assert_contains "$output" "start marker not found"
}
