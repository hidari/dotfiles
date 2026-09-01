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

@test "check reports a repo whose exclude lacks the second layer" {
    # symlink だけを見ていると、取り付けの 2 つの書き込みのうち 1 つしか検査しない。
    # 実測 (2026-09-02) では 21 リポ中 13 リポの exclude が手つかずの既定値のまま
    # symlink だけあり、--check は problems=0 を返していた。
    mkdir -p "$TARGET/.hidari"
    ln -sfn "$OPS" "$TARGET/.hidari/private-ops"
    : > "$TARGET/.git/info/exclude"
    printf 'repo\n' > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "partial: repo"
    assert_contains "$output" "listed=1 problems=1"
}

@test "check does not accept a global ignore as the second layer" {
    # 実効 (check-ignore) だけを見ると global の excludesfile で成立してしまい、
    # 二層目の欠落を検出できない。二層目を置いた理由が「global が効かないマシンでも
    # 守る」ことなので、実効が緑でも二層目がある証拠にはならない。
    mkdir -p "$TARGET/.hidari" "$TEST_HOME/.config/git"
    ln -sfn "$OPS" "$TARGET/.hidari/private-ops"
    : > "$TARGET/.git/info/exclude"
    printf '.hidari/\n.cache/\n' > "$TEST_HOME/.config/git/ignore"
    printf 'repo\n' > "$TEST_HOME/repos.txt"

    # 対照: global 側が実際に効いていること (効いていなければこのテストは何も測らない)
    git -C "$TARGET" check-ignore -q .hidari/private-ops

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -ne 0 ]
    assert_contains "$output" "partial: repo"
}

@test "check stays silent when both layers are in place" {
    # 取り付け直後は二層目も入っているので、partial を出さないこと。
    # これが無いと、常に partial を返す変異が上の 2 件だけで通る。
    "$WIRING" --ops "$OPS" "$TARGET"
    printf 'repo\n' > "$TEST_HOME/repos.txt"

    run "$WIRING" --check --ops "$OPS" --list "$TEST_HOME/repos.txt"

    [ "$status" -eq 0 ]
    assert_contains "$output" "ok: repo"
    refute_contains "$output" "partial"
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
