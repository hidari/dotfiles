#!/usr/bin/env bats
# =============================================================================
# apm ガード (PATH shim と共有判定層) のテスト
# =============================================================================

load test_helper

bats_require_minimum_version 1.5.0

SHIM_SOURCE="$REPO_ROOT/scripts/apm-guard/apm"

setup() {
    setup_test_home

    # shim を本番と同じ形 (symlink) で置く。実体をコピーで置くと、shim が自分の隣から
    # lib.sh を探す経路が symlink 越しでも通ることを確かめられない。
    GUARD_DIR="$TEST_HOME/guard"
    REAL_DIR="$TEST_HOME/real"
    mkdir -p "$GUARD_DIR" "$REAL_DIR"
    ln -sf "$SHIM_SOURCE" "$GUARD_DIR/apm"
    ln -sf "$APM_GUARD_LIB" "$GUARD_DIR/lib.sh"

    # 実物の代わり。起動されたことに加えて「shim を通ってきたか」を残す。
    # shim は委譲の直前に自分のディレクトリを PATH から外すので、ここから見た PATH に
    # guard が残っていれば shim を経由していない = テストの配線が壊れている。
    # 素の "起動された" だけを見ると、PATH の組み立てを間違えて shim が一度も走らない
    # 状態でも、委譲を期待するテストが全て緑になる (実際に一度そうなった)。
    cat > "$REAL_DIR/apm" <<'FAKE'
#!/bin/sh
case ":$PATH:" in
    *":$APM_GUARD_TEST_DIR:"*) printf 'BYPASSED_SHIM:%s\n' "$*" ;;
    *) printf 'REAL_APM_RAN:%s\n' "$*" ;;
esac
FAKE
    chmod +x "$REAL_DIR/apm"
}

# shim を PATH 先頭に置いて起動する。CPU 時間を縛るのは、PATH の除去が壊れたときの
# 失敗が「エラー」ではなく自分自身の再実行 = 無限再帰として現れるため。
run_shim() {
    local dir="$1"
    shift
    run bash -c '
        ulimit -t 10
        cd "$1" || exit 9
        shift
        PATH="$1:$2:/usr/bin:/bin"
        APM_GUARD_TEST_DIR="$1"
        export PATH APM_GUARD_TEST_DIR
        # 起動前に配線そのものを確かめる。ここが無いと、PATH の組み立てを間違えて
        # shim が一度も走らない状態でも、委譲を期待するテストが全て緑になる
        # (実際に一度そうなり、拒否を期待する 1 件だけが落ちた)。
        case ":$PATH:" in
            *":$APM_GUARD_TEST_DIR:"*) ;;
            *) echo "TEST_WIRING_BROKEN: guard dir is not on PATH" >&2; exit 98 ;;
        esac
        shift 2
        exec apm "$@"
    ' _ "$dir" "$GUARD_DIR" "$REAL_DIR" "$@"
}


# 実物が起動し、かつ shim を経由していたことを確認する。
# BYPASSED_SHIM は fake が「PATH に guard が残ったまま呼ばれた」と判定した印で、
# これが出るときはテストの配線が壊れていて、判定側は一度も走っていない。
assert_shim_delegated() {
    case "$1" in
        *BYPASSED_SHIM*)
            echo "shim を経由せず実物が直接呼ばれた: $1" >&2
            return 1
            ;;
    esac
}

# =============================================================================
# apm_is_readonly_invocation
# =============================================================================

@test "apm_is_readonly_invocation: a readonly subcommand is allowed" {
    . "$APM_GUARD_LIB"

    run apm_is_readonly_invocation view
    [ "$status" -eq 0 ]
}

@test "apm_is_readonly_invocation: a two-word readonly subcommand is allowed" {
    . "$APM_GUARD_LIB"

    run apm_is_readonly_invocation deps list
    [ "$status" -eq 0 ]
}

@test "apm_is_readonly_invocation: install is not readonly" {
    . "$APM_GUARD_LIB"

    run apm_is_readonly_invocation install
    [ "$status" -ne 0 ]
}

@test "apm_is_readonly_invocation: no subcommand only prints help" {
    # apm / apm --help / apm --version は help を出すだけなので検査対象外。
    # ここを偽にするとフラグだけの呼び出しが毎回止まり、ガードが手順の邪魔になる。
    . "$APM_GUARD_LIB"

    run apm_is_readonly_invocation --version
    [ "$status" -eq 0 ]
}

@test "apm_is_readonly_invocation: flags before the subcommand are skipped" {
    # フラグを位置引数として数えると install が第 2 語へずれ、書き込みが readonly に化ける
    . "$APM_GUARD_LIB"

    run apm_is_readonly_invocation --verbose install
    [ "$status" -ne 0 ]
}

# =============================================================================
# shim の判定
# =============================================================================

@test "apm shim: delegates to the real apm on a clean tree" {
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"

    run_shim "$repo" install

    [ "$status" -eq 0 ]
    assert_shim_delegated "$output"
    assert_contains "$output" "REAL_APM_RAN:install"
}

@test "apm shim: refuses on a dirty tree without running the real apm" {
    # ここが外れるとガードの主張 (dirty なら止まる) が静かに偽になる。実物が起動したか
    # どうかまで見るのは、拒否メッセージだけ出して委譲する形でも文言検査は通るため。
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"
    echo changed > "$repo/a.txt"

    run_shim "$repo" install

    [ "$status" -eq 1 ]
    assert_contains "$output" "refusing to run apm"
    assert_contains "$output" "a.txt"
    refute_contains "$output" "REAL_APM_RAN"
}

@test "apm shim: a readonly subcommand passes even on a dirty tree" {
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"
    echo changed > "$repo/a.txt"

    run_shim "$repo" view

    [ "$status" -eq 0 ]
    assert_shim_delegated "$output"
    assert_contains "$output" "REAL_APM_RAN:view"
}

@test "apm shim: the apm manifest alone is an allowed mid-state" {
    # pin を更新するたびにガードが手順を止めないための例外。落とすと apm.yml を書いた
    # 直後の apm install が必ず止まる。
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"
    echo x > "$repo/apm.yml"

    run_shim "$repo" install

    [ "$status" -eq 0 ]
    assert_shim_delegated "$output"
    assert_contains "$output" "REAL_APM_RAN:install"
}

@test "apm shim: outside a git repository there is nothing to protect" {
    # git から戻す前提そのものが無いので検査しない
    local plain="$TEST_HOME/plain"
    mkdir -p "$plain"

    run_shim "$plain" install

    [ "$status" -eq 0 ]
    assert_shim_delegated "$output"
    assert_contains "$output" "REAL_APM_RAN:install"
}

@test "apm shim: the disable environment variable bypasses the guard" {
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"
    echo changed > "$repo/a.txt"

    APM_INSTALL_GUARD_DISABLE=1 run_shim "$repo" install

    [ "$status" -eq 0 ]
    assert_shim_delegated "$output"
    assert_contains "$output" "REAL_APM_RAN:install"
}

@test "apm shim: does not re-exec itself when delegating" {
    # PATH から自分を外す処理が壊れると、失敗は「エラー」ではなく自分の再実行として
    # 現れる。ulimit -t が切るまで回り続けるので、status が 0 であることを見る。
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"

    run_shim "$repo" install

    [ "$status" -eq 0 ]
    assert_shim_delegated "$output"
    assert_contains "$output" "REAL_APM_RAN:install"
}

# =============================================================================
# 取り付け (配布経路と PATH への差し込み)
# =============================================================================

@test "apm shim: is distributed by SYMLINK_PAIRS" {
    # 配布経路から落ちると shim が配置されず、ガードは「静かに何もしない」状態になる
    load_pairs_array SYMLINK_PAIRS

    local pair found_shim=0 found_lib=0
    for pair in "${SYMLINK_PAIRS[@]}"; do
        case "$pair" in
            "scripts/apm-guard/apm|"*) found_shim=1 ;;
            "scripts/apm-guard/lib.sh|"*) found_lib=1 ;;
        esac
    done

    [ "$found_shim" -eq 1 ]
    [ "$found_lib" -eq 1 ]
}

@test "apm shim: the source is executable" {
    # 実行権限が落ちると PATH 解決から外れ、実物が直接呼ばれてガードが素通りする
    [ -x "$SHIM_SOURCE" ]
}

@test "apm shim: zshrc prepends the guard after mise activate" {
    # path 配列側へ書くと mise activate の再構成で実物より後ろへ落ちる (実測で 31 番目)。
    # 順序そのものが仕様なので行番号で pin する。
    local mise_line prepend_line
    mise_line="$(grep -n 'mise activate zsh' "$ZSHRC_FILE" | head -1 | cut -d: -f1)"
    prepend_line="$(grep -n 'libexec/apm-guard' "$ZSHRC_FILE" | head -1 | cut -d: -f1)"

    [ -n "$mise_line" ]
    [ -n "$prepend_line" ]
    [ "$prepend_line" -gt "$mise_line" ]
}

@test "apm shim: the zshrc PATH entry matches the SYMLINK_PAIRS target" {
    # 配置先と PATH に入れる先が別々に書かれているので、片方だけ直すと shim は
    # 置かれるのに PATH に載らない (またはその逆) という無音の失敗になる
    load_pairs_array SYMLINK_PAIRS

    local pair target dir=""
    for pair in "${SYMLINK_PAIRS[@]}"; do
        case "$pair" in
            "scripts/apm-guard/apm|"*)
                target="${pair#*|}"
                dir="${target%/*}"
                ;;
        esac
    done

    [ -n "$dir" ]
    run grep -F "\$HOME/$dir" "$ZSHRC_FILE"
    [ "$status" -eq 0 ]
}
