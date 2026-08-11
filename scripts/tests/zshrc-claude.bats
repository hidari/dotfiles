#!/usr/bin/env bats
# =============================================================================
# .zshrc の Claude Code 起動関数テスト
# =============================================================================
#
# 起動関数が守る仕様は以下の通り。
#   1. 個人アカウントは CLAUDE_CONFIG_DIR を設定しない (Keychain の service 名の
#      導出条件が未確認のため、既定パスの明示指定という賭けをしない)。
#      外から渡された値は読んで尊重する
#   2. 追加アカウントのランチャは追跡外の設定ファイル (claude-config-dirs) から
#      生成する。ディレクトリ名をこの PUBLIC リポジトリへ書かないための外部化で、
#      テストはダミー名 (.claude-alpha 等) だけを使う
#   3. 追加アカウントのランチャは config dir の存在を確認してから渡す (存在しない
#      値は Claude Code が黙って受け入れ、初期状態で起動してしまう)
#   4. タスクリスト ID は作業ディレクトリから導出する (git リポジトリならルート、
#      無ければ cwd の名前)。前置の明示指定はこの導出に優先し、何も導出できない
#      ときは変数ごと渡さず既定のセッション ID リストに任せる
#   5. 未知のタスクリスト ID は新規作成として通し、知らせるだけでブロックはしない
#      (_claude_task_list_notice() が導出済みの ID を引数で受け取る専用関数であり、
#      ランチャと通知が別々に ID を判定して食い違うことを防ぐ)

load test_helper

# run --separate-stderr (stdout と stderr を分けて観測する) に必要。
# 宣言しないと bats が BW02 警告を出す。CI は v1.13.0 を pin している。
bats_require_minimum_version 1.5.0

setup() {
    setup_test_home
    # 呼び出し元シェルの環境が漏れるとアサーションが偽陽性/偽陰性になるため落とす
    unset CLAUDE_CONFIG_DIR
    unset CLAUDE_CODE_TASK_LIST_ID
    unset CLAUDE_CONFIG_DIRS_FILE
}

teardown() {
    teardown_test_home
}

# 追加アカウントの設定ファイルを書く。引数 1 つが 1 行になる。
# パスの規約 (追跡外・$HOME/.config/dotfiles/claude-config-dirs) は
# bootstrap.sh / .zshrc の CLAUDE_CONFIG_DIRS_FILE と同じで、一致は
# 下の drift テストが pin する。
write_config_dirs_file() {
    mkdir -p "$TEST_HOME/.config/dotfiles"
    printf '%s\n' "$@" > "$TEST_HOME/.config/dotfiles/claude-config-dirs"
}

# 追加アカウントを丸ごと用意する (設定ファイル + 実ディレクトリ)。
# 名前はダミーの .claude-alpha。実名は追跡外の設定ファイルにのみ存在し、
# この PUBLIC リポジトリの追跡ファイルへは書かない。
setup_extra_account() {
    write_config_dirs_file '.claude-alpha'
    mkdir -p "$TEST_HOME/.claude-alpha"
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
    # 既定側にだけ存在する ID を追加アカウント側の config dir で問い合わせたら未知として扱う。
    mkdir -p "$TEST_HOME/.claude/tasks/dotfiles"
    mkdir -p "$TEST_HOME/.claude-alpha"
    load_zshrc_claude_functions

    run _claude_task_list_notice "$TEST_HOME/.claude-alpha" dotfiles

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
    mkdir -p "$TEST_HOME/.claude-alpha"
    load_zshrc_claude_functions

    CLAUDE_CONFIG_DIR="$TEST_HOME/.claude-alpha" run _claude_config_dir

    [ "$status" -eq 0 ]
    [ "$output" = "$TEST_HOME/.claude-alpha" ]
}

@test "_claude_config_dir: prefers the explicit argument over the environment" {
    # アカウントを固定するランチャは、外から渡された値ではなく自分の値を使う
    mkdir -p "$TEST_HOME/.claude-alpha"
    load_zshrc_claude_functions

    CLAUDE_CONFIG_DIR="$TEST_HOME/.claude" run _claude_config_dir "$TEST_HOME/.claude-alpha"

    [ "$status" -eq 0 ]
    [ "$output" = "$TEST_HOME/.claude-alpha" ]
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
    mkdir -p "$TEST_HOME/.claude-alpha"
    setup_recording_claude
    load_zshrc_claude_functions

    CLAUDE_CONFIG_DIR="$TEST_HOME/.claude-alpha" CLAUDE_CODE_TASK_LIST_ID=dotfiles run claude

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
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    # 変数を渡さないだけでなく、起動そのものが行われたことも確かめる。
    # ここを確かめないと else 分岐の起動を削除しても検出できない
    assert_contains "$recorded" "LAUNCHED"
    refute_contains "$recorded" "TASK_LIST="
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
# _claude_define_launchers (追加アカウントのランチャ生成)
# =============================================================================
#
# 追加アカウントのランチャは静的定義ではなく、追跡外の設定ファイル (1 行 1 ディレク
# トリ名・ドット付き) から生成する。ディレクトリ名をこの PUBLIC リポジトリへ書かない
# ための外部化。生成器はマーカーブロックの source 時に 1 度呼ばれるため、テストは
# load_zshrc_claude_functions の後に明示の呼び直しをしない (呼び直すと、ブロック末尾
# の取り付けを外す退行が全テスト緑のまま通る)。警告の観測だけは出力を分離するため
# run で呼び直す。

@test "_claude_define_launchers: defines a launcher for each configured dir at source time" {
    setup_extra_account
    load_zshrc_claude_functions

    run type claude-alpha

    [ "$status" -eq 0 ]
}

@test "_claude_define_launchers: defines the dev variant alongside the base launcher" {
    # 派生は素のランチャを名前で呼ぶため、片方だけ生成すると呼び先を失う
    setup_extra_account
    load_zshrc_claude_functions

    run type claude-alpha-dev

    [ "$status" -eq 0 ]
}

@test "_claude_define_launchers: defines launchers for every configured dir, not just the first" {
    write_config_dirs_file '.claude-alpha' '.claude-beta'
    load_zshrc_claude_functions

    run type claude-beta
    [ "$status" -eq 0 ]
    run type claude-beta-dev
    [ "$status" -eq 0 ]
    # 2 件目の処理が 1 件目を消していないことも確かめる
    run type claude-alpha
    [ "$status" -eq 0 ]
}

@test "_claude_define_launchers: defines nothing when the config file is absent" {
    load_zshrc_claude_functions

    run type claude-alpha

    [ "$status" -ne 0 ]
}

@test "_claude_define_launchers: rejects lines that are not plain dot-prefixed names" {
    # 行は eval に流れて関数定義になるため、charset を通らない行からは定義しない。
    # 黙って捨てると設定の typo に気づけないので、却下行は verbatim の警告で知らせる。
    # 却下対象は 3 種 (パス脱出・コマンド区切りの混入・ドット無しの素の名前) で、
    # 選別条件が独立にあるため 1 種類では 1 条件しか pin できない
    write_config_dirs_file '.claude-ok' '../escape' '.claude;echo injected' 'alpha'
    load_zshrc_claude_functions

    run --separate-stderr _claude_define_launchers

    [ "$status" -eq 0 ]
    assert_contains "$stderr" "無視します: ../escape"
    assert_contains "$stderr" "無視します: .claude;echo injected"
    assert_contains "$stderr" "無視します: alpha"
    # 検証を全部通った行だけが関数になる
    run type claude-ok
    [ "$status" -eq 0 ]
    run type escape
    [ "$status" -ne 0 ]
    run type alpha
    [ "$status" -ne 0 ]
}

@test "_claude_define_launchers: rejects the bare parent-directory line" {
    # ".." は唯一 charset を通りながら $HOME を脱出する値なので個別に却下する。
    # 規約は bootstrap.sh の claude_extra_config_dirs と同じ
    write_config_dirs_file '..' '.claude-ok'
    load_zshrc_claude_functions

    run --separate-stderr _claude_define_launchers

    [ "$status" -eq 0 ]
    assert_contains "$stderr" "無視します: .."
    # 却下が後続の行を巻き込んでいないこと
    run type claude-ok
    [ "$status" -eq 0 ]
}

@test "_claude_define_launchers: skips comments and blank lines silently" {
    # コメントと空行は整理用の正当な行なので、却下の警告を出さない。
    # 警告が出ると常時ノイズになり、本物の却下を見落とす
    write_config_dirs_file '# comment' '' '.claude-alpha'
    load_zshrc_claude_functions

    run --separate-stderr _claude_define_launchers

    [ "$status" -eq 0 ]
    [ -z "$stderr" ]
    run type claude-alpha
    [ "$status" -eq 0 ]
}

@test "_claude_define_launchers: does not replace the static default launcher" {
    # 設定ファイルに既定の .claude が書かれていても claude を生成し直さない。
    # 生成版は CLAUDE_CONFIG_DIR を設定するため、置き換わると既定アカウントの
    # 非対称 (変数を渡さない) が静かに消える
    setup_recording_claude
    write_config_dirs_file '.claude' '.claude-alpha'
    load_zshrc_claude_functions

    run claude

    [ "$status" -eq 0 ]
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    assert_contains "$recorded" "LAUNCHED"
    refute_contains "$recorded" "CONFIG_DIR="
}

@test "_claude_define_launchers: warns when extra config dirs exist but the config file is absent" {
    # 設定ファイルだけが無い状態は新規マシンや誤削除で起きる。現行の .zshrc は単体で
    # 自足していたので、無言で消えると command not found の原因がシェル設定側にある
    # ことに気づけない
    mkdir -p "$TEST_HOME/.claude-alpha"
    load_zshrc_claude_functions

    run --separate-stderr _claude_define_launchers

    [ "$status" -eq 0 ]
    assert_contains "$stderr" "claude-config-dirs"
    # 警告文が名前を含むと、テストの期待値経由で実名がリポジトリへ戻る。
    # 警告はファイルパスだけを載せ、見つけたディレクトリ名は載せない
    refute_contains "$stderr" ".claude-alpha"
}

@test "_claude_define_launchers: stays silent when neither the config file nor extra dirs exist" {
    # 追加アカウントを使わないマシンで毎シェル警告が出るとノイズになり、
    # 本物の警告を見落とす。上の警告テストの対照 (正常なら空になる側)
    load_zshrc_claude_functions

    run --separate-stderr _claude_define_launchers

    [ "$status" -eq 0 ]
    [ -z "$stderr" ]
    [ -z "$output" ]
}

@test "_claude_define_launchers: agrees with bootstrap.sh on where the config dir list lives" {
    # 同じパスを 2 ファイルに書かざるを得ない (プロセスが別で共有できない) ため、
    # 値そのものを突き合わせて drift を検出する。片方だけ変えると赤くなる
    local from_bootstrap from_zshrc
    unset CLAUDE_CONFIG_DIRS_FILE
    load_bootstrap_functions
    from_bootstrap="$CLAUDE_CONFIG_DIRS_FILE"

    unset CLAUDE_CONFIG_DIRS_FILE
    load_zshrc_claude_functions
    from_zshrc="$CLAUDE_CONFIG_DIRS_FILE"

    [ -n "$from_bootstrap" ]
    [ "$from_bootstrap" = "$from_zshrc" ]
}

# =============================================================================
# claude-alpha (生成された追加アカウントのランチャ)
# =============================================================================
#
# 生成に移っても、静的定義だった頃の呼び出し時の契約 (アカウント固定・存在検査・
# タスクリスト導出) が保存されることを、ダミー名 .claude-alpha のランチャで pin する。

@test "claude-alpha: sets CLAUDE_CONFIG_DIR to its own directory" {
    setup_extra_account
    setup_recording_claude
    load_zshrc_claude_functions

    run claude-alpha

    [ "$status" -eq 0 ]
    assert_contains "$(cat "$RECORDED_LAUNCH")" "CONFIG_DIR=$TEST_HOME/.claude-alpha"
}

@test "claude-alpha: pins its own account over an externally given config dir" {
    # アカウントを固定するのがこのランチャの存在理由。前置に引きずられて既定側で
    # 起動したら、追加アカウント用として呼んだ意味が消える
    setup_extra_account
    setup_recording_claude
    load_zshrc_claude_functions

    CLAUDE_CONFIG_DIR="$TEST_HOME/.claude" run claude-alpha

    [ "$status" -eq 0 ]
    assert_contains "$(cat "$RECORDED_LAUNCH")" "CONFIG_DIR=$TEST_HOME/.claude-alpha"
}

@test "claude-alpha: fails without launching when the config dir is missing" {
    # 設定ファイルに行があってもディレクトリが無ければ起動を止める。生成は
    # ディレクトリの実在を条件にしない (後から作られうる) ので、検査は呼び出し時に
    # 行う。不在のまま起動すると初期状態の設定が作られる
    write_config_dirs_file '.claude-alpha'
    setup_recording_claude
    load_zshrc_claude_functions

    run claude-alpha

    [ "$status" -ne 0 ]
    assert_contains "$output" "設定ディレクトリが見つかりません"
    # 起動そのものを止めることが仕様。警告を出しつつ起動していたら無意味
    refute_contains "$(cat "$RECORDED_LAUNCH")" "LAUNCHED"
}

@test "claude-alpha: passes the task list id through to the binary" {
    setup_extra_account
    mkdir -p "$TEST_HOME/.claude-alpha/tasks/explicit"
    setup_test_repo "$TEST_HOME/myrepo"
    setup_recording_claude
    load_zshrc_claude_functions

    # アカウント (関数) とタスクリスト (前置) が直交して合成できることを pin する。
    # 前置値は導出値と衝突しない名前にする
    CLAUDE_CODE_TASK_LIST_ID=explicit run_in_dir "$TEST_HOME/myrepo" claude-alpha

    [ "$status" -eq 0 ]
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    assert_contains "$recorded" "CONFIG_DIR=$TEST_HOME/.claude-alpha"
    assert_contains "$recorded" "TASK_LIST=explicit"
    refute_contains "$recorded" "TASK_LIST=myrepo"
}

@test "claude-alpha: passes the derived task list id to the binary" {
    setup_extra_account
    setup_test_repo "$TEST_HOME/myrepo"
    setup_recording_claude
    load_zshrc_claude_functions

    run_in_dir "$TEST_HOME/myrepo" claude-alpha

    [ "$status" -eq 0 ]
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    assert_contains "$recorded" "CONFIG_DIR=$TEST_HOME/.claude-alpha"
    assert_contains "$recorded" "TASK_LIST=myrepo"
}

@test "claude-alpha: leaves the variable unset when nothing can be derived" {
    # 空ガードはランチャごとに複製される。生成側を pin しないと、生成テンプレート
    # だけが空ガードを落とす退行が緑で通る
    setup_extra_account
    setup_recording_claude
    load_zshrc_claude_functions

    run_in_dir / claude-alpha

    [ "$status" -eq 0 ]
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    # 変数を渡さないだけでなく、起動そのものが行われたことも確かめる。
    # ここを確かめないと else 分岐の起動を削除しても検出できない
    assert_contains "$recorded" "LAUNCHED"
    refute_contains "$recorded" "TASK_LIST="
}

@test "claude-alpha: warns about an unknown task list but still launches" {
    setup_extra_account
    setup_recording_claude
    load_zshrc_claude_functions

    CLAUDE_CODE_TASK_LIST_ID=typo run claude-alpha

    [ "$status" -eq 0 ]
    assert_contains "$output" "新しいタスクリストを作成します: typo"
    assert_contains "$(cat "$RECORDED_LAUNCH")" "LAUNCHED"
}

# =============================================================================
# claude-dev / claude-alpha-dev (開発版の skill と plugin を読む)
# =============================================================================
#
# 既定の claude は skill を apm が配置したコピーから読むが、plugin は同名の marketplace
# 版が優先されるため別経路から載る (経路の canonical は claude-plugins の CLAUDE.md)。
# agentic-coding-tools を直しながら試すときだけ開発版 (作業ツリーの実体) を読む。
# パッケージ一覧は列挙せず実体から拾うため、増減しても追随する。
#
# アカウント (既定 / 追加) と版 (安定 / 開発) は直交する 2 軸。既定側の 2 つは静的
# 定義、追加側の 2 つは設定ファイルから生成される。収集とガードは共通ヘルパーに
# 1 つだけ置くが、テストは両ランチャで重複して pin する。片方だけを pin すると、
# もう片方はヘルパーの呼び出しを外しても緑のままになり、追加アカウント側だけが
# 退行できてしまう。

# 開発版リポジトリの最小構成。plugin (深さ 1) と skill (カテゴリを挟んで深さ 2) の
# 両方を置き、拾ってはいけないものを 3 種類混ぜる。3 種類あるのは選別条件が 3 つ
# (探索根 / 深さ / ファイル名) 独立にあり、1 種類では 1 条件しか pin できないため
setup_dev_packages() {
    local root="$TEST_HOME/agentic"
    mkdir -p "$root/plugins/dev-workflow/skills/git-branch-switcher"
    : > "$root/plugins/dev-workflow/SKILL.md"
    : > "$root/plugins/dev-workflow/skills/git-branch-switcher/SKILL.md"
    mkdir -p "$root/skills/tooling/herdr"
    : > "$root/skills/tooling/herdr/SKILL.md"
    mkdir -p "$root/plugins/no-skill-here"
    # ファイル名の条件。実体には README.md や agents/*.md が並ぶので、SKILL.md 以外を
    # 拾う退行が入ると不正なパスが --plugin-dir へ混ざる
    mkdir -p "$root/plugins/readme-only"
    : > "$root/plugins/readme-only/README.md"
    mkdir -p "$root/plugins/dev-workflow/agents"
    : > "$root/plugins/dev-workflow/agents/reviewer.md"
    # 探索根の条件。起点を repo 直下へ広げると .git まで渡してしまう
    mkdir -p "$root/.git"
    : > "$root/.git/SKILL.md"
}

@test "claude-dev: passes --plugin-dir for both plugin and skill packages" {
    # plugin と skill は階層の深さが違う。片方だけ拾う実装だと、もう片方は
    # 安定版のまま静かに残り、直したはずの変更が反映されない
    setup_dev_packages
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/agentic" run claude-dev

    [ "$status" -eq 0 ]
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    assert_contains "$recorded" "--plugin-dir $TEST_HOME/agentic/plugins/dev-workflow"
    assert_contains "$recorded" "--plugin-dir $TEST_HOME/agentic/skills/tooling/herdr"
    # 含む一致は「余計な尾ひれ」を原理的に検出できない。SKILL.md の除去を落とすと
    # 渡るのはディレクトリではなくファイルになるが、上の 2 行はその prefix なので緑になる
    refute_contains "$recorded" "/SKILL.md"
    # 件数を数えないと、無関係な要素を足す退行が含む一致を素通りする
    local plugin_dir_count
    plugin_dir_count="$(grep -o -- '--plugin-dir' "$RECORDED_LAUNCH" | wc -l | tr -d ' ')"
    [ "$plugin_dir_count" -eq 2 ]
}

@test "claude-dev: excludes directories without SKILL.md" {
    # SKILL.md の有無で判定しないと作りかけのディレクトリまで渡してしまう。
    # ファイル名の条件も併せて pin する。ディレクトリの空・非空だけを見ていると
    # -name を緩める退行が緑のまま通り、README.md の側まで拾ってしまう
    setup_dev_packages
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/agentic" run claude-dev

    [ "$status" -eq 0 ]
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    refute_contains "$recorded" "no-skill-here"
    refute_contains "$recorded" "readme-only"
    refute_contains "$recorded" "dev-workflow/agents"
}

@test "claude-dev: searches only under plugins and skills" {
    # 探索根を repo 直下へ広げると .git のような管理用ディレクトリまで渡す。
    # SKILL.md を置いた .git は、深さとファイル名の条件では落とせない
    setup_dev_packages
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/agentic" run claude-dev

    [ "$status" -eq 0 ]
    refute_contains "$(cat "$RECORDED_LAUNCH")" "/.git"
}

@test "claude-dev: excludes component skills nested inside a plugin" {
    # plugin 内部の skills/<name>/ は plugin 経由で読まれる。個別にも渡すと
    # 同じ skill が 2 経路で載る
    setup_dev_packages
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/agentic" run claude-dev

    [ "$status" -eq 0 ]
    refute_contains "$(cat "$RECORDED_LAUNCH")" "git-branch-switcher"
}

@test "claude-dev: fails without launching when the repository is missing" {
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/nonexistent" run claude-dev

    [ "$status" -ne 0 ]
    assert_contains "$output" "開発版のリポジトリが見つかりません"
    refute_contains "$(cat "$RECORDED_LAUNCH")" "LAUNCHED"
}

@test "claude-dev: fails without launching when no package is found" {
    # 0 件のまま起動すると安定版で立ち上がる。開発版を見ているつもりで古い挙動を
    # 観測することになるので、静かに間違えるより止める
    # 置き場は両方あるが中身が無い形にする。手前の探索根チェックで落ちると
    # 0 件ガードを壊しても緑のままになり、狙った検査を pin できない
    mkdir -p "$TEST_HOME/empty-repo/plugins" "$TEST_HOME/empty-repo/skills"
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/empty-repo" run claude-dev

    [ "$status" -ne 0 ]
    assert_contains "$output" "開発版のパッケージが見つかりません"
    refute_contains "$(cat "$RECORDED_LAUNCH")" "LAUNCHED"
}

@test "claude-dev: fails without launching when one of the package roots is missing" {
    # 0 件ガードは全滅しか見ない。片側が欠けると find は残る側だけを返し、
    # 半分のパッケージを載せて rc=0 で起動する。部分欠落はエラーではなく
    # 「短い正常な結果」として返るので、件数を見ているだけでは気づけない
    mkdir -p "$TEST_HOME/half-repo/plugins/dev-workflow"
    : > "$TEST_HOME/half-repo/plugins/dev-workflow/SKILL.md"
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/half-repo" run claude-dev

    [ "$status" -ne 0 ]
    assert_contains "$output" "開発版のパッケージ置き場が見つかりません: $TEST_HOME/half-repo/skills"
    refute_contains "$(cat "$RECORDED_LAUNCH")" "LAUNCHED"
}

@test "claude-dev: falls back to the default repository path when none is handed in" {
    # 他のテストは AGENTIC_TOOLS_DIR を明示するため、既定パスだけが無検証で残る。
    # 実運用で踏むのは常に既定パスの側
    setup_recording_claude
    load_zshrc_claude_functions

    run claude-dev

    [ "$status" -ne 0 ]
    assert_contains "$output" "開発版のリポジトリが見つかりません: $HOME/Develop/agentic-coding-tools"
    refute_contains "$(cat "$RECORDED_LAUNCH")" "LAUNCHED"
}

@test "claude-dev: does not leak the plugin dir array into the caller" {
    # ヘルパーは呼び出し側が local で宣言した配列へ書き込む。ランチャ側の宣言が
    # 落ちると対話シェルへ残り続ける。run はサブシェルなので観測できず、
    # 直に呼んでから同じシェルで確かめる
    setup_dev_packages
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/agentic" claude-dev

    [ "${#_CLAUDE_DEV_PLUGIN_ARGS[@]}" -eq 0 ]
}

@test "claude-dev: derives the task list id through the claude function" {
    # 設定ディレクトリの検査だけでは委譲を pin できない。検査を手元へ写して
    # command claude を直に呼ぶ形にしても緑のままになり、タスクリスト通知だけが
    # 静かに落ちる。claude 関数だけが持つ導出を観測して委譲そのものを pin する
    setup_test_repo "$TEST_HOME/myrepo"
    setup_dev_packages
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/agentic" run_in_dir "$TEST_HOME/myrepo" claude-dev

    [ "$status" -eq 0 ]
    assert_contains "$(cat "$RECORDED_LAUNCH")" "TASK_LIST=myrepo"
}

@test "claude-dev: forwards its arguments to the binary" {
    setup_dev_packages
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/agentic" run claude-dev --resume foo

    [ "$status" -eq 0 ]
    assert_contains "$(cat "$RECORDED_LAUNCH")" "--resume foo"
}

@test "claude-dev: goes through the claude function so the config dir is checked" {
    # command claude を直に呼ぶと設定ディレクトリの検査とタスクリスト通知を迂回する。
    # 存在しない前置で止まることで、claude 関数を経由していることを pin する
    setup_dev_packages
    setup_recording_claude
    load_zshrc_claude_functions

    CLAUDE_CONFIG_DIR="$TEST_HOME/.claude-typo" AGENTIC_TOOLS_DIR="$TEST_HOME/agentic" run claude-dev

    [ "$status" -ne 0 ]
    assert_contains "$output" "設定ディレクトリが見つかりません"
    refute_contains "$(cat "$RECORDED_LAUNCH")" "LAUNCHED"
}

@test "claude-alpha-dev: pins the extra account and passes the dev plugin dirs" {
    # アカウント (関数) と版 (安定 / 開発) が直交して合成できることを pin する。
    # 開発版を追加アカウントで使いたい場面があるため、既定側だけの機能にしない
    setup_extra_account
    setup_dev_packages
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/agentic" run claude-alpha-dev

    [ "$status" -eq 0 ]
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    assert_contains "$recorded" "CONFIG_DIR=$TEST_HOME/.claude-alpha"
    assert_contains "$recorded" "--plugin-dir $TEST_HOME/agentic/plugins/dev-workflow"
    assert_contains "$recorded" "--plugin-dir $TEST_HOME/agentic/skills/tooling/herdr"
}

@test "claude-alpha-dev: pins its own account over an externally given config dir" {
    # 素のランチャと同じ規約。前置に引きずられて既定側で起動したら、
    # 追加アカウント用として呼んだ意味が消える
    setup_extra_account
    setup_dev_packages
    setup_recording_claude
    load_zshrc_claude_functions

    CLAUDE_CONFIG_DIR="$TEST_HOME/.claude" AGENTIC_TOOLS_DIR="$TEST_HOME/agentic" run claude-alpha-dev

    [ "$status" -eq 0 ]
    assert_contains "$(cat "$RECORDED_LAUNCH")" "CONFIG_DIR=$TEST_HOME/.claude-alpha"
}

@test "claude-alpha-dev: fails without launching when the repository is missing" {
    # ガードの実体は共通ヘルパーにあるが、生成テンプレート側が呼び出しを落とす
    # 配線ミスは、生成されたランチャを pin しないと検出できない
    setup_extra_account
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/nonexistent" run claude-alpha-dev

    [ "$status" -ne 0 ]
    assert_contains "$output" "開発版のリポジトリが見つかりません"
    refute_contains "$(cat "$RECORDED_LAUNCH")" "LAUNCHED"
}

@test "claude-alpha-dev: fails without launching when no package is found" {
    setup_extra_account
    # 置き場は両方あるが中身が無い形にする。手前の探索根チェックで落ちると
    # 0 件ガードを壊しても緑のままになり、狙った検査を pin できない
    mkdir -p "$TEST_HOME/empty-repo/plugins" "$TEST_HOME/empty-repo/skills"
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/empty-repo" run claude-alpha-dev

    [ "$status" -ne 0 ]
    assert_contains "$output" "開発版のパッケージが見つかりません"
    refute_contains "$(cat "$RECORDED_LAUNCH")" "LAUNCHED"
}

@test "claude-alpha-dev: forwards its arguments to the binary" {
    # 既定側にしか転送のテストが無いと、生成テンプレートだけ "$@" を落とす退行が緑で通る
    setup_extra_account
    setup_dev_packages
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/agentic" run claude-alpha-dev --resume foo

    [ "$status" -eq 0 ]
    assert_contains "$(cat "$RECORDED_LAUNCH")" "--resume foo"
}

@test "claude-alpha-dev: fails without launching when its own config dir is missing" {
    # 素のランチャを経由せずアカウント固定だけを手元へ写すと、追加アカウント側の
    # 設定ディレクトリ検査が落ちる。不在のまま起動すると初期状態の設定が作られる
    write_config_dirs_file '.claude-alpha'
    setup_dev_packages
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/agentic" run claude-alpha-dev

    [ "$status" -ne 0 ]
    assert_contains "$output" "設定ディレクトリが見つかりません"
    refute_contains "$(cat "$RECORDED_LAUNCH")" "LAUNCHED"
}

@test "claude-alpha-dev: derives the task list id through the generated base launcher" {
    # 既定側と同じ理由で委譲そのものを pin する。ガードは共通ヘルパーにあるが、
    # 委譲先は関数ごとに別々なので片方だけでは配線ミスを検出できない
    setup_extra_account
    setup_test_repo "$TEST_HOME/myrepo"
    setup_dev_packages
    setup_recording_claude
    load_zshrc_claude_functions

    AGENTIC_TOOLS_DIR="$TEST_HOME/agentic" run_in_dir "$TEST_HOME/myrepo" claude-alpha-dev

    [ "$status" -eq 0 ]
    local recorded
    recorded="$(cat "$RECORDED_LAUNCH")"
    assert_contains "$recorded" "TASK_LIST=myrepo"
    assert_contains "$recorded" "CONFIG_DIR=$TEST_HOME/.claude-alpha"
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
