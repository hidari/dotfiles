#!/usr/bin/env bats
# =============================================================================
# .zshrc の Claude Code 起動関数テスト
# =============================================================================
#
# 起動関数が守る仕様は 3 つ。
#   1. 個人アカウントは CLAUDE_CONFIG_DIR を設定しない (Keychain の service 名の
#      導出条件が未確認のため、既定パスの明示指定という賭けをしない)。
#      外から渡された値は読んで尊重する
#   2. 仕事アカウントは config dir の存在を確認してから渡す (存在しない値は
#      Claude Code が黙って受け入れ、初期状態で起動してしまう)
#   3. タスクリスト ID はアカウントと直交する軸なので関数は持たず、未知の ID の
#      ときだけ知らせる (ブロックはしない)

load test_helper

# run --separate-stderr (stdout と stderr を分けて観測する) に必要。
# 宣言しないと bats が BW02 警告を出す。CI は v1.13.0 を pin している。
bats_require_minimum_version 1.5.0

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

    run _claude_task_list_notice "$TEST_HOME/.claude" nonexistent

    # 新規作成は正当な操作なので、知らせるだけでブロックはしない
    [ "$status" -eq 0 ]
    assert_contains "$output" "新しいタスクリストを作成します: nonexistent"
}

@test "_claude_task_list_notice: stays silent when the task list already exists" {
    mkdir -p "$TEST_HOME/.claude/tasks/dotfiles"
    load_zshrc_claude_functions

    run _claude_task_list_notice "$TEST_HOME/.claude" dotfiles

    [ "$status" -eq 0 ]
    # 既知の ID で警告が出ると常時ノイズになり、本当の typo を見落とす
    [ -z "$output" ]
}

@test "_claude_task_list_notice: stays silent when no task list id is given" {
    load_zshrc_claude_functions

    run _claude_task_list_notice "$TEST_HOME/.claude" ""

    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "_claude_task_list_notice: distinguishes the config dir it inspects" {
    # タスクリストはアカウントごとに別なので、探索先が config dir 依存であることを pin する。
    # 個人側にだけ存在する ID を仕事側の config dir で問い合わせたら未知として扱う。
    mkdir -p "$TEST_HOME/.claude/tasks/dotfiles"
    mkdir -p "$TEST_HOME/.claude-hamiltonian"
    load_zshrc_claude_functions

    run _claude_task_list_notice "$TEST_HOME/.claude-hamiltonian" dotfiles

    [ "$status" -eq 0 ]
    assert_contains "$output" "新しいタスクリストを作成します: dotfiles"
}

@test "_claude_task_list_notice: ignores the ambient environment variable" {
    # グローバル参照が残っていると、呼び出し側が渡した ID ではなく前置の値を見てしまう。
    # 導出した ID と手打ちの ID が食い違ったときに誤った判定をする
    mkdir -p "$TEST_HOME/.claude/tasks/derived"
    load_zshrc_claude_functions

    CLAUDE_CODE_TASK_LIST_ID=nonexistent run _claude_task_list_notice "$TEST_HOME/.claude" derived

    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

# =============================================================================
# _claude_config_dir
# =============================================================================
#
# 設定ディレクトリの解決と存在検査を 1 箇所に閉じる。存在検査が片方のランチャに
# しか無いと、外から渡された typo をもう片方が素通ししてしまう。

@test "_claude_config_dir: resolves to the default when nothing is given" {
    load_zshrc_claude_functions

    run _claude_config_dir

    [ "$status" -eq 0 ]
    [ "$output" = "$TEST_HOME/.claude" ]
}

@test "_claude_config_dir: resolves to the environment value when set" {
    mkdir -p "$TEST_HOME/.claude-hamiltonian"
    load_zshrc_claude_functions

    CLAUDE_CONFIG_DIR="$TEST_HOME/.claude-hamiltonian" run _claude_config_dir

    [ "$status" -eq 0 ]
    [ "$output" = "$TEST_HOME/.claude-hamiltonian" ]
}

@test "_claude_config_dir: prefers the explicit argument over the environment" {
    # アカウントを固定するランチャは、外から渡された値ではなく自分の値を使う
    mkdir -p "$TEST_HOME/.claude-hamiltonian"
    load_zshrc_claude_functions

    CLAUDE_CONFIG_DIR="$TEST_HOME/.claude" run _claude_config_dir "$TEST_HOME/.claude-hamiltonian"

    [ "$status" -eq 0 ]
    [ "$output" = "$TEST_HOME/.claude-hamiltonian" ]
}

@test "_claude_config_dir: fails when the resolved directory does not exist" {
    load_zshrc_claude_functions

    run --separate-stderr _claude_config_dir "$TEST_HOME/.claude-nonexistent"

    [ "$status" -ne 0 ]
    assert_contains "$stderr" "設定ディレクトリが見つかりません"
    # 解決結果を stdout へ流したまま失敗すると、呼び出し元が空でない値を掴んで起動しうる
    [ -z "$output" ]
}

# =============================================================================
# _claude_task_list_id
# =============================================================================
#
# ID を手で打つ限り typo は避けられない。作業ディレクトリから導出すれば
# 打ち間違えようがなく、指定を忘れることもない。

@test "_claude_task_list_id: derives from the git repository root" {
    setup_test_repo "$TEST_HOME/myrepo"
    load_zshrc_claude_functions

    run_in_dir "$TEST_HOME/myrepo" _claude_task_list_id

    [ "$status" -eq 0 ]
    [ "$output" = "myrepo" ]
}

@test "_claude_task_list_id: resolves to the root even from a subdirectory" {
    # サブディレクトリごとに別 ID になると、同じプロジェクトの進捗が割れる。
    # これが導出元を cwd ではなくリポジトリルートにしている理由
    setup_test_repo "$TEST_HOME/myrepo"
    mkdir -p "$TEST_HOME/myrepo/frontend/src"
    load_zshrc_claude_functions

    run_in_dir "$TEST_HOME/myrepo/frontend/src" _claude_task_list_id

    [ "$status" -eq 0 ]
    [ "$output" = "myrepo" ]
}

@test "_claude_task_list_id: falls back to the cwd name outside a repository" {
    mkdir -p "$TEST_HOME/plain-dir"
    load_zshrc_claude_functions

    run_in_dir "$TEST_HOME/plain-dir" _claude_task_list_id

    [ "$status" -eq 0 ]
    [ "$output" = "plain-dir" ]
}

@test "_claude_task_list_id: resolves symlinked directories to the same id" {
    # 同じ実ディレクトリへ 2 つの経路で入っても ID が一致すること。$PWD はリンク名を
    # 返すため、揃えないと同じ場所なのにタスクリストが 2 つに割れる。
    # git 側は --show-toplevel が常に実体パスを返すので、フォールバックだけ経路依存に
    # なる非対称を作らない
    mkdir -p "$TEST_HOME/real-dir"
    ln -s "$TEST_HOME/real-dir" "$TEST_HOME/link-dir"
    load_zshrc_claude_functions

    run_in_dir "$TEST_HOME/link-dir" _claude_task_list_id

    [ "$status" -eq 0 ]
    [ "$output" = "real-dir" ]
}

@test "_claude_task_list_id: yields nothing at the filesystem root" {
    # basename が空になる唯一の場所。空の ID を渡したときの Claude Code の挙動は
    # 未確認なので、呼び出し側が変数を設定しない判断をするための signal にする
    load_zshrc_claude_functions

    run_in_dir / _claude_task_list_id

    [ "$status" -eq 0 ]
    [ -z "$output" ]
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
    # 既定パスの明示指定は Keychain の service 名の導出を変えうるため、
    # 変数を子プロセスへ渡さないことが仕様
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

@test "claude: fails without launching when the config dir handed in is missing" {
    # 存在しない値は Claude Code が黙って受け入れ、その場所に初期状態の設定を作って
    # 起動する。前置の typo は /login を求められるまで気づけないため、ここで止める
    setup_recording_claude
    load_zshrc_claude_functions

    CLAUDE_CONFIG_DIR="$TEST_HOME/.claude-typo" run claude

    [ "$status" -ne 0 ]
    assert_contains "$output" "設定ディレクトリが見つかりません"
    refute_contains "$(cat "$RECORDED_LAUNCH")" "LAUNCHED"
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

@test "claude: passes the derived task list id to the binary" {
    setup_test_repo "$TEST_HOME/myrepo"
    setup_recording_claude
    load_zshrc_claude_functions

    run_in_dir "$TEST_HOME/myrepo" claude

    [ "$status" -eq 0 ]
    assert_contains "$(cat "$RECORDED_LAUNCH")" "TASK_LIST=myrepo"
}

@test "claude: lets an explicit task list id win over derivation" {
    # 導出は既定であって強制ではない。別のリストを指定して起動する余地を残す
    setup_test_repo "$TEST_HOME/myrepo"
    setup_recording_claude
    load_zshrc_claude_functions

    CLAUDE_CODE_TASK_LIST_ID=explicit run_in_dir "$TEST_HOME/myrepo" claude

    [ "$status" -eq 0 ]
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    assert_contains "$recorded" "TASK_LIST=explicit"
    refute_contains "$recorded" "TASK_LIST=myrepo"
}

@test "claude: leaves the variable unset when nothing can be derived" {
    # 空文字を渡したときの Claude Code の挙動は未確認。未確認の前提に賭けず、
    # 導出できないときは既定のセッション ID リストに任せる
    setup_recording_claude
    load_zshrc_claude_functions

    run_in_dir / claude

    [ "$status" -eq 0 ]
    refute_contains "$(cat "$RECORDED_LAUNCH")" "TASK_LIST="
}

@test "claude: warns about a derived task list that does not exist yet" {
    setup_test_repo "$TEST_HOME/myrepo"
    setup_recording_claude
    load_zshrc_claude_functions

    run_in_dir "$TEST_HOME/myrepo" claude

    [ "$status" -eq 0 ]
    assert_contains "$output" "新しいタスクリストを作成します: myrepo"
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

@test "claude-hamiltonian: pins its own account over an externally given config dir" {
    # アカウントを固定するのがこの関数の存在理由。前置に引きずられて個人側で
    # 起動したら、仕事用として呼んだ意味が消える
    mkdir -p "$TEST_HOME/.claude-hamiltonian"
    setup_recording_claude
    load_zshrc_claude_functions

    CLAUDE_CONFIG_DIR="$TEST_HOME/.claude" run claude-hamiltonian

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

@test "claude-hamiltonian: passes the derived task list id to the binary" {
    mkdir -p "$TEST_HOME/.claude-hamiltonian"
    setup_test_repo "$TEST_HOME/myrepo"
    setup_recording_claude
    load_zshrc_claude_functions

    run_in_dir "$TEST_HOME/myrepo" claude-hamiltonian

    [ "$status" -eq 0 ]
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    assert_contains "$recorded" "CONFIG_DIR=$TEST_HOME/.claude-hamiltonian"
    assert_contains "$recorded" "TASK_LIST=myrepo"
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
