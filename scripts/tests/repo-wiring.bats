#!/usr/bin/env bats
# =============================================================================
# repo-wiring (運用指示の取り付け) のテスト
# =============================================================================

load test_helper

bats_require_minimum_version 1.5.0

# 変異注入でコピーを読ませられるよう上書き可能にする。既定値は実ファイルなので
# 通常実行と CI の対象は変わらない (test_helper.bash の BOOTSTRAP_SCRIPT と同じ規約)。
WIRING="${WIRING:-$REPO_ROOT/scripts/repo-wiring/repo-wiring}"

setup() {
    setup_test_home
    TARGET="$TEST_HOME/repo"
    mkdir -p "$TARGET"
    git -C "$TARGET" init -q .
    OPS="$TEST_HOME/cloud/private-ops"
    mkdir -p "$OPS"
}

teardown() {
    teardown_test_home
}

@test "repo-wiring derives the ops path from the current repository" {
    # 導出が壊れても --ops を明示する他のテストは全部緑のままなので、省略する経路を
    # 正の側で pin する。ここだけが「導出した値が実際に使われる」ことを測る。
    "$WIRING" --ops "$OPS" "$TARGET"
    other="$TEST_HOME/other"
    mkdir -p "$other"
    git -C "$other" init -q .

    cd "$TARGET"
    run "$WIRING" "$other"

    [ "$status" -eq 0 ]
    [ "$(readlink "$other/.hidari/private-ops")" = "$OPS" ]
}

@test "repo-wiring refuses when the ops path cannot be derived" {
    # 導出元が無い場所で省略したとき、空の OPS のまま進まないこと。
    cd "$TEST_HOME"

    run "$WIRING" "$TARGET"

    [ "$status" -ne 0 ]
    assert_contains "$output" "--ops"
}

@test "check derives the ops path from the current repository" {
    "$WIRING" --ops "$OPS" "$TARGET"
    printf 'repo\n' > "$TEST_HOME/repos.txt"

    cd "$TARGET"
    run "$WIRING" --check --list "$TEST_HOME/repos.txt"

    [ "$status" -eq 0 ]
    assert_contains "$output" "ok: repo"
}

@test "repo-wiring creates the hidari directory and the symlink" {
    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    [ -d "$TARGET/.hidari" ]
    [ -L "$TARGET/.hidari/private-ops" ]
    [ -e "$TARGET/.hidari/private-ops" ]
}

@test "repo-wiring writes the exclude entry before creating the symlink" {
    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    grep -q '^\.hidari/$' "$TARGET/.git/info/exclude"
}

@test "repo-wiring is idempotent" {
    run "$WIRING" --ops "$OPS" "$TARGET"
    [ "$status" -eq 0 ]

    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    [ "$(grep -c '^\.hidari/$' "$TARGET/.git/info/exclude")" -eq 1 ]
}

@test "repo-wiring repairs a dangling symlink" {
    mkdir -p "$TARGET/.hidari"
    ln -s "$TEST_HOME/gone" "$TARGET/.hidari/private-ops"

    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    [ -e "$TARGET/.hidari/private-ops" ]
}

@test "repo-wiring refuses when the path is still not ignored" {
    # .gitignore で明示的に再包含すると exclude を書いても ignore されない。
    # スクリプト自身が ignore を用意しても穴が残る経路がこれで、fail-closed を測る。
    printf '!.hidari/\n' > "$TARGET/.gitignore"

    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -ne 0 ]
    [ ! -e "$TARGET/.hidari/private-ops" ]
}

@test "repo-wiring writes the cache exclude entry too" {
    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    grep -q '^\.cache/$' "$TARGET/.git/info/exclude"
}

@test "repo-wiring is idempotent for the cache exclude entry" {
    run "$WIRING" --ops "$OPS" "$TARGET"
    [ "$status" -eq 0 ]

    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    [ "$(grep -c '^\.cache/$' "$TARGET/.git/info/exclude")" -eq 1 ]
}

@test "repo-wiring keeps an existing pattern that lacks a trailing newline" {
    # 追記先が末尾改行を欠くと、追記行が最終行と融合して既存パターンを壊す。
    # 壊れた側は「ignore されていたものが ignore されなくなる」形で失われるので、
    # 利用者が意図して除外していたファイルが追跡の射程へ戻る。
    printf 'secrets.env' > "$TARGET/.git/info/exclude"

    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -eq 0 ]
    grep -q '^secrets\.env$' "$TARGET/.git/info/exclude"
    grep -q '^\.hidari/$' "$TARGET/.git/info/exclude"
}

@test "repo-wiring refuses when the cache path is still not ignored" {
    # .hidari/ 側は通り .cache/ 側だけが塞がれる状態を作る。両方を塞ぐと
    # どちらの guard で落ちたのか区別できない。
    printf '!.cache/\n' > "$TARGET/.gitignore"

    run "$WIRING" --ops "$OPS" "$TARGET"

    [ "$status" -ne 0 ]
    assert_contains "$output" ".cache/"
    [ ! -e "$TARGET/.hidari/private-ops" ]
}

@test "repo-wiring refuses when the ops directory does not exist" {
    run "$WIRING" --ops "$TEST_HOME/missing" "$TARGET"

    [ "$status" -ne 0 ]
}

@test "repo-wiring refuses when the target is not a git repository" {
    # 単に非 0 終了と .hidari 不在だけを見ると、この guard を外しても後段の
    # check-ignore が別経路で fail-closed するため区別できない (dead pin)。
    # このテスト固有の fail メッセージと、guard を通れば exclude を置くための
    # mkdir -p が作るはずの .git が無いことまで見て、この guard 自体を pin する。
    local not_a_repo="$TEST_HOME/not-a-repo"
    mkdir -p "$not_a_repo"

    run "$WIRING" --ops "$OPS" "$not_a_repo"

    [ "$status" -ne 0 ]
    assert_contains "$output" "git リポジトリではありません"
    [ ! -e "$not_a_repo/.git" ]
    [ ! -e "$not_a_repo/.hidari" ]
}

@test "check reports a repo listed but not wired" {
    printf 'repo\n' > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "repo"
    assert_contains "$output" "missing"
}

@test "check stays silent for a wired repo" {
    "$WIRING" --ops "$OPS" "$TARGET"
    printf 'repo\n' > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -eq 0 ]
    assert_contains "$output" "ok"
}

@test "check resolves a listed line against HOME" {
    # 相対形をそのまま渡すと現在位置基準で解決され、実行場所によって結果が変わる。
    # 一覧の基準が $HOME であることを、別の場所から実行して pin する。
    "$WIRING" --ops "$OPS" "$TARGET"
    printf 'repo\n' > "$TEST_HOME/repos.txt"
    mkdir -p "$TEST_HOME/elsewhere"

    cd "$TEST_HOME/elsewhere"
    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -eq 0 ]
    assert_contains "$output" "ok: repo"
}

@test "check never prints an absolute path" {
    # 出力を貼っても露出面を作らないことが一覧を相対形にした理由なので、
    # 解決先ではなく一覧の綴りを出していることを ok と vanished の両分岐で見る。
    "$WIRING" --ops "$OPS" "$TARGET"
    printf 'repo\ngone\n' > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "ok: repo"
    assert_contains "$output" "vanished: gone"
    refute_contains "$output" "$TEST_HOME"
}

@test "check reports a repo whose ignore is missing entirely" {
    # symlink だけを見ていると、取り付けの 2 つの書き込みのうち 1 つしか検査しない。
    # symlink はあるが exclude が空、という取りこぼしをここで pin する。
    mkdir -p "$TARGET/.hidari"
    ln -sfn "$OPS" "$TARGET/.hidari/private-ops"
    : > "$TARGET/.git/info/exclude"
    printf 'repo\n' > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "partial: repo"
    assert_contains "$output" "listed=1 problems=1"
}

@test "check does not accept a global ignore" {
    # 実効だけを見ると global の excludesfile で成立してしまい、マシンローカルの
    # 設定に依存した状態を健全と答える。出所まで見るのはこのため。
    mkdir -p "$TARGET/.hidari" "$TEST_HOME/.config/git"
    ln -sfn "$OPS" "$TARGET/.hidari/private-ops"
    : > "$TARGET/.git/info/exclude"
    printf '.hidari/\n.cache/\n' > "$TEST_HOME/.config/git/ignore"
    printf 'repo\n' > "$TEST_HOME/repos.txt"
    # global ignore の既定は $XDG_CONFIG_HOME/git/ignore で、未設定のときだけ
    # $HOME/.config/git/ignore へ落ちる。開発機は未設定だが CI では設定されており、
    # 明示しないと別の場所を見て global が効かない。効かないと本体のアサーションは
    # 「global を拒否したから」ではなく「global がそもそも無いから」通ってしまう。
    export XDG_CONFIG_HOME="$TEST_HOME/.config"

    # 対照: global 側が実際に効いていること (効いていなければこのテストは何も測らない)
    git -C "$TARGET" check-ignore -q .hidari/private-ops

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "partial: repo"
}

@test "check requires every wired pattern, not just the first" {
    # 一覧の全要素を見ていることを pin する。片方だけ置いた状態を作らないと、
    # ループを先頭要素へ落とす変異が全テスト緑のまま生存する (実測で確認した)。
    # 取り付け側の書き込みを測るテストは、この変異では壊れないので届かない。
    mkdir -p "$TARGET/.hidari"
    ln -sfn "$OPS" "$TARGET/.hidari/private-ops"
    printf '.hidari/\n' > "$TARGET/.git/info/exclude"
    printf 'repo\n' > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "partial: repo"
}

@test "check accepts a tracked gitignore as the source" {
    # 守りたいのは「マシンローカルの設定に依存しないこと」であって、exclude という
    # ファイルの存在ではない。追跡下の .gitignore で除外していればどのマシンでも効く。
    # 実測ではこの分岐に 14 リポが該当した。
    mkdir -p "$TARGET/.hidari"
    ln -sfn "$OPS" "$TARGET/.hidari/private-ops"
    : > "$TARGET/.git/info/exclude"
    printf '.hidari/\n.cache/\n' > "$TARGET/.gitignore"
    printf 'repo\n' > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -eq 0 ]
    assert_contains "$output" "ok: repo"
}

@test "check accepts spellings that git honours" {
    # git は末尾空白と CR を落としてからパターン化し、ルート固定やグロブも効かせる。
    # 綴りをバイト単位で照合すると、実際に効いている ignore を partial と誤報する。
    mkdir -p "$TARGET/.hidari"
    ln -sfn "$OPS" "$TARGET/.hidari/private-ops"
    printf '/.hidari/ \r\n.cache/*\n' > "$TARGET/.git/info/exclude"
    printf 'repo\n' > "$TEST_HOME/repos.txt"

    # 対照: この綴りで実際に ignore が効いていること
    git -C "$TARGET" check-ignore -q .hidari/private-ops

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -eq 0 ]
    assert_contains "$output" "ok: repo"
}

@test "check reports an ignore defeated by a later negation" {
    # exclude に書いてあっても後続の否定で無効化される。行の存在だけを見ると
    # ok と答えるが、実際には symlink が追跡の射程に出ている。
    mkdir -p "$TARGET/.hidari"
    ln -sfn "$OPS" "$TARGET/.hidari/private-ops"
    printf '.hidari/\n.cache/\n!.hidari/\n!.cache/\n' > "$TARGET/.git/info/exclude"
    printf 'repo\n' > "$TEST_HOME/repos.txt"

    # 対照: 実際に追跡の射程へ出ていること
    assert_contains "$(git -C "$TARGET" status --porcelain)" ".hidari/"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "partial: repo"
}

@test "check reports an ignore defeated by gitignore re-inclusion" {
    # .gitignore は exclude より優先される。取り付け時は fail-closed で拒むが、
    # 取り付けた後に置かれると --check だけが気づける位置にある。
    "$WIRING" --ops "$OPS" "$TARGET"
    printf '!.hidari/\n!.cache/\n' > "$TARGET/.gitignore"
    printf 'repo\n' > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "partial: repo"
}

@test "check always prints the population count" {
    printf 'repo\n' > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    # 0 件と見ていないを区別するため、問題の有無にかかわらず母数を出す
    assert_contains "$output" "listed=1"
}

@test "check rejects an absolute line instead of ignoring it" {
    # 一覧は $HOME からの相対パスで書く。絶対パスを黙って受けると、出力へ
    # ユーザー名が載る経路が復活する。
    printf '%s\n' "$TARGET" > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "rejected"
    # 却下した行も母数に数える。この行が無いと、加算を却下判定の後ろへ動かす
    # 変異が生存する (実測で確認済み)。
    assert_contains "$output" "listed=1"
}

@test "check skips comments and blank lines" {
    printf '# comment\n\nrepo\n' > "$TEST_HOME/repos.txt"
    "$WIRING" --ops "$OPS" "$TARGET"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -eq 0 ]
    assert_contains "$output" "listed=1"
}

@test "check reports a vanished repo" {
    printf 'gone\n' > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "vanished"
}

# --- 以下は既定値の分岐と取り付け判定 (-e の甘さ) を pin する。省略しないこと ---

@test "check falls back to the list inside the ops directory" {
    # --list を省略する唯一のテスト。これが無いと既定値の導出行を壊しても
    # 全テストが緑のままになる (毎回明示で上書きされる値は pin されない)。
    "$WIRING" --ops "$OPS" "$TARGET"
    printf 'repo\n' > "$OPS/repos.txt"

    run "$WIRING" --check --ops "$OPS"

    [ "$status" -eq 0 ]
    assert_contains "$output" "listed=1"
}

@test "check rejects a plain file standing in for the symlink" {
    # -e は通常ファイルでも真になるので、それだけでは取り付け済みと区別できない。
    mkdir -p "$TARGET/.hidari"
    : > "$TARGET/.hidari/private-ops"
    printf 'repo\n' > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "missing"
}

@test "check rejects a symlink pointing elsewhere" {
    # 解決先を見ないと、別の場所を指す symlink が取り付け済みとして通る。
    local other="$TEST_HOME/other-ops"
    mkdir -p "$TARGET/.hidari" "$other"
    ln -sfn "$other" "$TARGET/.hidari/private-ops"
    printf 'repo\n' > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "missing"
}
