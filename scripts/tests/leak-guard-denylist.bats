#!/usr/bin/env bats
# =============================================================================
# 禁止語リストの pre-commit 入口 (scripts/leak-guard/denylist-check.sh) のテスト
# =============================================================================
#
# 入口が持つのは「リストが届かない起動元で止める」ことと、checker への委譲だけ。
# 照合の仕様は checker の docstring が canonical なので、ここでは確かめない。
#
# 委譲の検査は使い捨てリポジトリへ偽の checker を置いて行う。置き場は本物と同じ
# 相対パスにするので、入口が checker を引く経路そのものを通る。
# 本物の checker を通す live のテストは apm の deploy 先を要るので uncovered にする
# (deploy 先は ignore されていて CI には無い)。
# 禁止語はテストの中で作る無害な語だけを使い、実物のリストは一度も読まない。

load test_helper

bats_require_minimum_version 1.5.0

LEAK_GUARD_HOOK="${LEAK_GUARD_HOOK:-$REPO_ROOT/scripts/leak-guard/denylist-check.sh}"

# 入口が引く checker の、リポジトリルートからの相対パス
CHECKER_REL="home/.claude/skills/dev-workflow/skills/commit-and-pr-message/scripts/check-leak-guard-denylist.py"

setup() {
    # 呼び出し元シェルの値が漏れると、未設定の枝を通したつもりで設定済みの枝を通す
    unset LEAK_GUARD_DENYLIST
    WORK="$(mktemp -d)"
    REPO="$WORK/repo"
    setup_test_repo "$REPO"
    # 本物のリポジトリと同じく deploy 先を追跡しない。checker 自身を走査対象へ入れないため
    printf 'home/.claude/skills/\n' > "$REPO/.gitignore"
    printf 'hello\n' > "$REPO/a.txt"
    git -C "$REPO" add -A
    CALLS="$WORK/calls"
}

teardown() {
    rm -rf "$WORK"
}

# 偽の checker。受けた引数を CALLS へ記録し、FAKE_RC で終わる
install_fake_checker() {
    local rc="$1"
    mkdir -p "$REPO/${CHECKER_REL%/*}"
    cat > "$REPO/$CHECKER_REL" <<EOF
import sys
with open("$CALLS", "a", encoding="utf-8") as f:
    f.write(" ".join(sys.argv[1:]) + "\n")
sys.exit($rc)
EOF
}

@test "stops with rc 2 when the denylist variable does not reach the hook" {
    install_fake_checker 0

    cd "$REPO"
    run --separate-stderr "$LEAK_GUARD_HOOK"

    [ "$status" -eq 2 ]
    # 抜け方を止めた場所で示す。hook id を変えたらここも変わる
    assert_contains "$stderr" "SKIP=leak-guard-denylist"
    # 止めたあとで checker を起動すると、checker の skip (rc 0) が上書きして通ってしまう
    [ ! -e "$CALLS" ]
}

@test "an empty value reaches the checker instead of being treated as unset" {
    # 空は checker が rc 2 で拒む値 (未設定とは別の枝)。入口が :+ で判定すると
    # 空を未設定と同じに扱い、checker の分岐表の1行を握りつぶす
    install_fake_checker 2
    export LEAK_GUARD_DENYLIST=""

    cd "$REPO"
    run "$LEAK_GUARD_HOOK"

    [ "$status" -eq 2 ]
    [ "$(cat "$CALLS")" = "--check" ]
}

@test "delegates to the checker with --check and passes each exit code through" {
    export LEAK_GUARD_DENYLIST="$WORK/list.txt"
    local rc
    for rc in 0 1 2; do
        rm -f "$CALLS"
        install_fake_checker "$rc"

        cd "$REPO"
        run "$LEAK_GUARD_HOOK"

        [ "$status" -eq "$rc" ]
        [ "$(cat "$CALLS")" = "--check" ]
    done
}

@test "resolves the checker from the repository root when started in a subdirectory" {
    install_fake_checker 0
    export LEAK_GUARD_DENYLIST="$WORK/list.txt"
    mkdir -p "$REPO/sub/dir"

    cd "$REPO/sub/dir"
    run "$LEAK_GUARD_HOOK"

    [ "$status" -eq 0 ]
    [ "$(cat "$CALLS")" = "--check" ]
}

@test "fails closed when the checker is not deployed" {
    # fresh clone のように apm の deploy 先が無い状態。止まらずに通ると検査が消えたことに
    # 誰も気づかない
    export LEAK_GUARD_DENYLIST="$WORK/list.txt"

    cd "$REPO"
    run "$LEAK_GUARD_HOOK"

    # python3 が対象を開けないときの rc。入口が存在しないとき (127) と区別する
    [ "$status" -eq 2 ]
}

# 本物の checker を通す。陽性の検体で止まり、陰性の側で通ることを両方見る。
# 禁止語は printf で組み立てる。
live_setup() {
    local real="$REPO_ROOT/$CHECKER_REL"
    [ -f "$real" ] || skip_outside_ci "checker が deploy されていない: $CHECKER_REL"
    mkdir -p "$REPO/${CHECKER_REL%/*}"
    cp "$real" "$REPO/$CHECKER_REL"
    WORD="$(printf '%s%s' "zebra" "quill")"
    printf '%s\n' "$WORD" > "$WORK/list.txt"
    export LEAK_GUARD_DENYLIST="$WORK/list.txt"
}

# bats test_tags=uncovered
@test "live: the real checker stops a staged file that contains a listed word" {
    live_setup
    printf 'note %s here\n' "$WORD" > "$REPO/b.txt"
    git -C "$REPO" add b.txt

    cd "$REPO"
    run --separate-stderr "$LEAK_GUARD_HOOK"

    [ "$status" -eq 1 ]
    # 語そのものは出力に出ない (座標だけを出す checker の約束が入口で壊れていない)
    refute_contains "$output$stderr" "$WORD"
}

# bats test_tags=uncovered
@test "live: the real checker passes and reports what it scanned when nothing is listed" {
    live_setup

    cd "$REPO"
    run --separate-stderr "$LEAK_GUARD_HOOK"

    [ "$status" -eq 0 ]
    # rc 0 だけでは「見て 0 件」と「見ていない」が区別できない。走査した件数まで pin する
    assert_contains "$output" "status=checked tracked=2 scanned=2 "
    assert_contains "$output" " findings=0"
}
