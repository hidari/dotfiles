#!/usr/bin/env bats
# =============================================================================
# .zshenv の禁止語ガード配線テスト
# =============================================================================
#
# 仕様とその根拠は home/.zshenv のコメントが canonical。ここは観測の作法だけを持つ。
#
# 観測は実際の zsh へ渡して行う。bash で source すると構文は通るのに、.zshenv が
# いつ読まれるか (非対話でも読まれるか) という検査したい面が丸ごと落ちる。
# 値の観測はさらに子プロセスを 1 枚挟む (理由は write_child_probe)。

load test_helper

# run --separate-stderr (stdout と stderr を分けて観測する) に必要。
bats_require_minimum_version 1.5.0

setup() {
    setup_test_home
    # 呼び出し元シェルの環境が漏れるとアサーションが偽陽性/偽陰性になるため落とす
    unset LEAK_GUARD_DENYLIST
    require_command_or_skip zsh || return 1
    # ライブ環境と同じ形にする (bootstrap が張る symlink 経由で読ませる)
    ln -s "$ZSHENV_FILE" "$TEST_HOME/.zshenv"
    write_child_probe

    # 中立な固定パス。テスト側でのこのパスの持ち場はここ 1 箇所で、fixture も期待値も
    # ここを通す。.zshenv 側は同じパスを自分で literal に持つので、ここが間違っていても
    # 両方が同時に間違って緑になることはない (fixture が別の場所へ張られ、export が
    # 起きないまま期待値と突き合わされるので落ちる)。
    NEUTRAL_PATH="$TEST_HOME/.config/leak-guard/denylist.gitignore"
}

teardown() {
    teardown_test_home
}

# 中立な固定パスへ symlink を張る。張り先は TEST_HOME 内に閉じる。
# 実物のリストのパスはこのリポジトリのどの追跡ファイルにも書かない。
link_denylist() {
    local dest="$1"
    mkdir -p "${NEUTRAL_PATH%/*}"
    ln -s "$dest" "$NEUTRAL_PATH"
}

# 実体を伴う symlink を張る。張り先は NEUTRAL_PATH。
link_live_denylist() {
    printf 'secret-word\n' > "$TEST_HOME/list.txt"
    link_denylist "$TEST_HOME/list.txt"
}

# 値を子プロセスから観測するためのプローブを置く。
# .zshenv を読んだシェル自身から観測してはいけない。そのシェルからは export を落として
# 代入だけにした形も同じ値に見えるため、実際の消費者 (pre-commit hook が起動する checker)
# へ届かない状態を緑で通してしまう。変異注入で実測済みで、この観測に変える前は
# export を外す変異が 9 件すべて緑のまま生存した。
write_child_probe() {
    CHILD_PROBE="$TEST_HOME/probe-env.sh"
    cat > "$CHILD_PROBE" << 'PROBE'
#!/bin/sh
printf '%s' "${LEAK_GUARD_DENYLIST-unset}"
PROBE
    chmod +x "$CHILD_PROBE"
}

# 非対話 zsh に .zshenv を読ませ、その子プロセスへ届いた値を観測する。
# 未設定と空文字を区別するため ${VAR-unset} を使う (空文字は checker が rc=2 で弾く side)。
# ZDOTDIR を落とすのは、環境に残っていると HOME より優先され .zshenv の置き場が
# 変わるため (落とさないと呼び出し元の設定でテストの対象ファイルが入れ替わる)。
# プローブは $0 経由で渡す。パスを文字列へ埋め込むと TEST_HOME に空白があるときに割れる。
observe_denylist_env() {
    run env -u ZDOTDIR zsh -c '"$0"' "$CHILD_PROBE"
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
    [ "$output" = "$NEUTRAL_PATH" ]
}

@test "zshenv: exports the neutral path when the symlink is broken" {
    link_denylist "$TEST_HOME/does-not-exist"

    observe_denylist_env

    [ "$status" -eq 0 ]
    # ここが -r / -e との分かれ目。壊れた symlink で export しないと、checker が
    # rc=2 で止まるはずの状況が rc=0 の skip に化ける
    [ "$output" = "$NEUTRAL_PATH" ]
}

@test "zshenv: leaves the variable unset when nothing is linked" {
    observe_denylist_env

    [ "$status" -eq 0 ]
    # 空文字ではなく未設定であること。空文字を export すると checker から見て
    # 「設定されているが指す先が無い」になり、リストを持たないマシンが赤くなる
    [ "$output" = "unset" ]
}

@test "zshenv: leaves the variable unset when the neutral path is a regular file" {
    # 中立パスは間接参照として設計されていて、実体を直接置く運用は無い。-L は symlink
    # だけを受けるので通常ファイルは通さない。ここを緩めて通常ファイルも受けると、
    # 壊れた symlink を不在から区別する性質まで一緒に失う (変異で実測: -L を -e / -r / -f
    # のいずれかへ替えても、-L と -f の or へ緩めても、このテストが赤くなる)
    mkdir -p "${NEUTRAL_PATH%/*}"
    printf 'secret-word\n' > "$NEUTRAL_PATH"

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
    # .zshenv が配られること自体が配線の要なので個別に pin する。
    load_pairs_array SYMLINK_PAIRS
    # 空配列 (slice 破綻) での vacuous pass を防ぐ negative guard
    [ "${#SYMLINK_PAIRS[@]}" -gt 0 ]

    assert_array_contains "home/.zshenv|.zshenv" "${SYMLINK_PAIRS[@]}"
}

@test "zshenv: contains no absolute path" {
    # リストの実体のパスは追跡下のどこにも書かない。これを語のリストではなく構造で見る。
    # このファイルのパスは設計上すべて $HOME 相対なので、絶対パスが 1 つでも現れたら
    # 意図しない場所を名指ししたことになる。
    #
    # 語のリスト (CloudStorage 等) にしない理由は 2 つ。リストに載せた語そのものが
    # PUBLIC リポジトリで実体の在り処を示唆すること、そして .gitleaks.toml の
    # macos-user-path ルールと重なる部分を二重管理にすることである。構造で見れば
    # /Volumes/ や /opt/ のような未知の形も同じ 1 つの検査で落ちる。
    #
    # 不在・空での vacuous pass を防ぐ negative guard。これが無いと、ファイルが
    # 無いときの grep の rc=2 を「一致なし」と読んで緑になる
    [ -s "$ZSHENV_FILE" ]

    # 行頭・空白・引用符・= ・( のいずれかに続く "/英字" を絶対パスの始まりとみなす。
    # 散文中の " / " は英字が続かないので誤検出しない (対照付きで実測)
    run grep -nE "(^|[[:space:]\"'=(])/[A-Za-z]" "$ZSHENV_FILE"

    # 1 (一致なし) を要求する。-ne 0 だと 2 (読めない等) も通してしまう
    [ "$status" -eq 1 ]
}
