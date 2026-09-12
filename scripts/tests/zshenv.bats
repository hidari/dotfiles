#!/usr/bin/env bats
# =============================================================================
# .zshenv の禁止語ガード配線テスト
# =============================================================================
#
# .zshenv が守る仕様は以下の通り。
#   1. 中立な固定パス ($HOME/.config/leak-guard/denylist.gitignore) に symlink が
#      張られているマシンでだけ LEAK_GUARD_DENYLIST を export する。リストの実体の
#      パスは追跡下のどこにも書かない (この PUBLIC リポジトリへ書けないため)
#   2. 判定は -L で行う。壊れた symlink は「不在」ではなく「人が意図して張った」側へ
#      入れ、checker の loud な失敗 (rc=2) へ届かせる。-r や -e にすると壊れた
#      symlink が不在と同じ扱いになり、loud な失敗が silent skip に化ける
#   3. 何も出力しない。.zshenv は scp / sftp / rsync over ssh の非対話セッションでも
#      読まれるため、出力するとプロトコルが壊れる
#
# 観測は実際の zsh へ渡して行う。bash で source すると構文は通るのに、.zshenv が
# いつ読まれるか (非対話でも読まれるか) という検査したい面が丸ごと落ちる。

load test_helper

# run --separate-stderr (stdout と stderr を分けて観測する) に必要。
bats_require_minimum_version 1.5.0

setup() {
    setup_test_home
    # 呼び出し元シェルの環境が漏れるとアサーションが偽陽性/偽陰性になるため落とす
    unset LEAK_GUARD_DENYLIST
    require_command_or_skip zsh
    # ライブ環境と同じ形にする (bootstrap が張る symlink 経由で読ませる)
    ln -s "$ZSHENV_FILE" "$TEST_HOME/.zshenv"
}

teardown() {
    teardown_test_home
}

# 中立な固定パスへ symlink を張る。張り先は TEST_HOME 内に閉じる。
# 実物のリストのパスはこのリポジトリのどの追跡ファイルにも書かない。
link_denylist() {
    local dest="$1"
    mkdir -p "$TEST_HOME/.config/leak-guard"
    ln -s "$dest" "$TEST_HOME/.config/leak-guard/denylist.gitignore"
}

# 実体を伴う symlink を張り、その中立側のパスを返す。
link_live_denylist() {
    printf 'secret-word\n' > "$TEST_HOME/list.txt"
    link_denylist "$TEST_HOME/list.txt"
}

# 中立な固定パス。期待値をテスト側で 1 箇所に閉じる。
neutral_path() {
    printf '%s' "$TEST_HOME/.config/leak-guard/denylist.gitignore"
}

# 非対話 zsh に .zshenv を読ませ、export された値を観測する。
# 未設定と空文字を区別するため ${VAR-unset} を使う。
# ZDOTDIR を落とすのは、環境に残っていると HOME より優先され .zshenv の置き場が
# 変わるため (落とさないと呼び出し元の設定でテストの対象ファイルが入れ替わる)。
observe_denylist_env() {
    run env -u ZDOTDIR zsh -c 'printf "%s" "${LEAK_GUARD_DENYLIST-unset}"'
}

# .zshenv 自身の出力を観測する。zsh には何も印字させないので、観測された
# 出力はすべて .zshenv 由来になる。
observe_zshenv_output() {
    run --separate-stderr env -u ZDOTDIR zsh -c true
}

# =============================================================================
# export の 3 状態
# =============================================================================

@test "zshenv: exports the neutral path when the symlink resolves" {
    link_live_denylist

    observe_denylist_env

    [ "$status" -eq 0 ]
    # 値は symlink の解決先ではなく中立側のパスそのもの。解決先を入れると
    # リストの実体パスが環境変数経由で外へ出る
    [ "$output" = "$(neutral_path)" ]
}

@test "zshenv: exports the neutral path when the symlink is broken" {
    link_denylist "$TEST_HOME/does-not-exist"

    observe_denylist_env

    [ "$status" -eq 0 ]
    # ここが -r / -e との分かれ目。壊れた symlink で export しないと、checker が
    # rc=2 で止まるはずの状況が rc=0 の skip に化ける
    [ "$output" = "$(neutral_path)" ]
}

@test "zshenv: leaves the variable unset when nothing is linked" {
    observe_denylist_env

    [ "$status" -eq 0 ]
    # 空文字ではなく未設定であること。空文字を export すると checker から見て
    # 「設定されているが指す先が無い」になり、リストを持たないマシンが赤くなる
    [ "$output" = "unset" ]
}

@test "zshenv: leaves the variable unset when the neutral path is a regular file" {
    # 実体を直接置く運用は採らない。採ると dotfiles 側に実体を置くことになり、
    # PUBLIC リポジトリへ持ち込む経路ができる
    mkdir -p "$TEST_HOME/.config/leak-guard"
    printf 'secret-word\n' > "$TEST_HOME/.config/leak-guard/denylist.gitignore"

    observe_denylist_env

    [ "$status" -eq 0 ]
    [ "$output" = "unset" ]
}

# =============================================================================
# 無出力
# =============================================================================

@test "zshenv: writes nothing when it exports" {
    link_live_denylist

    observe_zshenv_output

    [ "$status" -eq 0 ]
    [ -z "$output" ]
    [ -z "$stderr" ]
}

@test "zshenv: writes nothing when it skips" {
    observe_zshenv_output

    [ "$status" -eq 0 ]
    [ -z "$output" ]
    [ -z "$stderr" ]
}

@test "zshenv: writes nothing when the symlink is broken" {
    link_denylist "$TEST_HOME/does-not-exist"

    observe_zshenv_output

    [ "$status" -eq 0 ]
    [ -z "$output" ]
    [ -z "$stderr" ]
}

# =============================================================================
# 配線
# =============================================================================

@test "zshenv: SYMLINK_PAIRS carries the entry that puts it in place" {
    # home/ 配下の全ファイルが pair に覆われることは bootstrap.bats の reverse drift
    # テストが見ているが、あちらは unmanaged allowlist へ足しても緑になる。
    # .zshenv が配られること自体はこの Issue の要なので個別に pin する。
    load_pairs_array SYMLINK_PAIRS
    # 空配列 (slice 破綻) での vacuous pass を防ぐ negative guard
    [ "${#SYMLINK_PAIRS[@]}" -gt 0 ]

    assert_array_contains "home/.zshenv|.zshenv" "${SYMLINK_PAIRS[@]}"
}

@test "zshenv: does not name the denylist location" {
    # 実体のパスは追跡下のどこにも書かない。中立な固定パスだけを持つことを
    # 「$HOME 以外の絶対パスを含まない」という形で見る。
    # 不在・空での vacuous pass を防ぐ negative guard。これが無いと、ファイルが
    # 無いときの grep の rc=2 を「一致なし」と読んで緑になる
    [ -s "$ZSHENV_FILE" ]

    run grep -nE '(/Users/|/home/|CloudStorage|Drive)' "$ZSHENV_FILE"

    # 1 (一致なし) を要求する。-ne 0 だと 2 (読めない等) も通してしまう
    [ "$status" -eq 1 ]
}
