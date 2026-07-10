#!/usr/bin/env bats
# =============================================================================
# ast-grep のルールが「どのファイルを見るか」を検証する
#
# ast-grep test は仮想のスニペットに対して走るため files と ignores を通らない。
# glob と隠しディレクトリの扱いを確かめられるのはこのファイルだけである。
#
# 注意: @test 名は ASCII に限る (rules/bats-test-name-ascii-only.yml)
# =============================================================================

load test_helper

RULE="$REPO_ROOT/rules/nvim-lua-no-hex-literal.yml"

setup() {
    if ! command -v ast-grep >/dev/null 2>&1; then
        if [ -n "${CI:-}" ]; then
            echo "ast-grep is required in CI but was not found" >&2
            return 1
        fi
        skip "ast-grep is not installed"
    fi

    # 本番と同じ相対パスを持つ fixture を作る。
    # 実ルールをコピーするので、ルールの二重管理にならない
    FIXTURE="$(mktemp -d)"
    mkdir -p "$FIXTURE/rules" \
        "$FIXTURE/home/.config/nvim/lua/config" \
        "$FIXTURE/home/.config/nvim/lua/plugins"
    cp "$RULE" "$FIXTURE/rules/"
    printf 'ruleDirs:\n  - rules\n' > "$FIXTURE/sgconfig.yml"
}

teardown() {
    if [ -n "${FIXTURE:-}" ]; then
        rm -rf "$FIXTURE"
    fi
}

scan() {
    (cd "$FIXTURE" && ast-grep scan --no-ignore hidden 2>&1)
}

scan_exit() {
    (cd "$FIXTURE" && ast-grep scan --no-ignore hidden >/dev/null 2>&1)
}

@test "the rule catches a hex literal under the hidden nvim config path" {
    printf 'return { X = { fg = "#123456" } }\n' > "$FIXTURE/home/.config/nvim/lua/config/markdown.lua"

    run scan
    assert_contains "$output" "nvim-lua-no-hex-literal"
    assert_contains "$output" "markdown.lua"

    run scan_exit
    [ "$status" -eq 1 ] || return 1
}

@test "the rule catches a hex literal under the nvim plugins path" {
    # 写像ファイルは config/ だけでなく plugins/ 配下にもある (lualine.lua は
    # palette.surfaces を参照する hex 禁止対象)。glob を lua/config/ へ狭めると
    # plugins/ 全体が黙って検査対象から外れるため、その広さをここで固定する
    printf 'return { X = { fg = "#654321" } }\n' > "$FIXTURE/home/.config/nvim/lua/plugins/lualine.lua"

    run scan
    assert_contains "$output" "nvim-lua-no-hex-literal"
    assert_contains "$output" "lualine.lua"

    run scan_exit
    [ "$status" -eq 1 ] || return 1
}

@test "the rule exempts palette lua" {
    printf 'return { X = { fg = "#123456" } }\n' > "$FIXTURE/home/.config/nvim/lua/config/palette.lua"

    run scan
    refute_contains "$output" "nvim-lua-no-hex-literal"

    run scan_exit
    [ "$status" -eq 0 ] || return 1
}

@test "a comment holding a hex value is not a violation" {
    printf -- '-- コメントの中の hex #123abc は検出しない\nreturn { X = { fg = hex.muted } }\n' \
        > "$FIXTURE/home/.config/nvim/lua/config/markdown.lua"

    run scan
    refute_contains "$output" "nvim-lua-no-hex-literal"

    run scan_exit
    [ "$status" -eq 0 ] || return 1
}

@test "without no-ignore hidden the scan silently sees nothing" {
    # なぜ --no-ignore hidden が要るのかを実行可能な事実として残す。
    # ast-grep が既定で隠しディレクトリを飛ばさなくなったら、このテストが赤くなって教えてくれる
    printf 'return { X = { fg = "#123456" } }\n' > "$FIXTURE/home/.config/nvim/lua/config/markdown.lua"

    run bash -c "cd '$FIXTURE' && ast-grep scan 2>&1"
    refute_contains "$output" "nvim-lua-no-hex-literal"

    run bash -c "cd '$FIXTURE' && ast-grep scan >/dev/null 2>&1"
    [ "$status" -eq 0 ] || return 1
}

@test "every ast-grep scan invocation searches hidden directories" {
    # --no-ignore hidden が無いと nvim の Lua を 1 件も検査しないまま緑になる。
    # ルールの検出力は上のテストが守るが、呼び出し側の配線を守るのはここだけである。
    #
    # 実行行だけを見るため entry: と run: で錨を打つ。
    # そうしないと pre-commit の name: ast-grep scan (...) という表示名まで拾って常に赤くなる
    pre_commit="$REPO_ROOT/.pre-commit-config.yaml"
    workflow="$REPO_ROOT/.github/workflows/test.yml"
    invocation='(entry|run):[[:space:]]*ast-grep scan'

    # 呼び出しが 0 件だと下の検査が空回りして緑になる。
    # pre-commit と CI がそれぞれ 1 回以上呼んでいることを先に固定する
    pre_commit_calls=$(grep -cE "$invocation" "$pre_commit" || true)
    workflow_calls=$(grep -cE "$invocation" "$workflow" || true)
    [ "$pre_commit_calls" -ge 1 ] || return 1
    [ "$workflow_calls" -ge 1 ] || return 1

    # そのすべてがフラグを伴うこと
    missing=$(grep -hE "$invocation" "$pre_commit" "$workflow" | grep -cv -- '--no-ignore hidden' || true)
    [ "$missing" = "0" ] || return 1
}
