#!/usr/bin/env bats
# =============================================================================
# ast-grep のルールが「どのファイルを見るか」を検証する
#
# ast-grep test は仮想のスニペットに対して走るため files と ignores を通らない。
# 隠しディレクトリの扱いを確かめられるのはこのファイルだけである。
#
# 注意: @test 名は ASCII に限る (rules/bats-test-name-ascii-only.yml)
# =============================================================================

load test_helper

# 対象のパスを絞らないルール。隠しディレクトリ配下へ置いた fixture を見るかどうかが、
# ルールの glob ではなく走査の側だけで決まる
RULE="$REPO_ROOT/rules/bats-test-name-ascii-only.yml"

setup() {
    require_command_or_skip ast-grep || return 1

    # 実ルールをコピーするので、ルールの二重管理にならない。languageGlobs は sgconfig.yml と
    # 同じく .bats を bash として読ませる
    FIXTURE="$(mktemp -d)"
    mkdir -p "$FIXTURE/rules" "$FIXTURE/home/.config/example"
    cp "$RULE" "$FIXTURE/rules/"
    printf 'ruleDirs:\n  - rules\nlanguageGlobs:\n  bash:\n    - "*.bats"\n' > "$FIXTURE/sgconfig.yml"
    # マルチバイトの @test 名はこのファイル自身をルールに当てないよう、8 進のエスケープで作る
    printf '@test "\343\201\202" {\n    true\n}\n' > "$FIXTURE/home/.config/example/hidden.bats"
}

teardown() {
    if [ -n "${FIXTURE:-}" ]; then
        rm -rf "$FIXTURE"
    fi
}

@test "with no-ignore hidden the scan reports a violation under a hidden directory" {
    run bash -c "cd '$FIXTURE' && ast-grep scan --no-ignore hidden 2>&1"
    assert_contains "$output" "bats-test-name-ascii-only"
    assert_contains "$output" "hidden.bats"

    run bash -c "cd '$FIXTURE' && ast-grep scan --no-ignore hidden >/dev/null 2>&1"
    [ "$status" -eq 1 ] || return 1
}

@test "without no-ignore hidden the scan silently sees nothing" {
    # なぜ --no-ignore hidden が要るのかを実行可能な事実として残す。
    # ast-grep が既定で隠しディレクトリを飛ばさなくなったら、このテストが赤くなって教えてくれる
    run bash -c "cd '$FIXTURE' && ast-grep scan 2>&1"
    refute_contains "$output" "bats-test-name-ascii-only"

    run bash -c "cd '$FIXTURE' && ast-grep scan >/dev/null 2>&1"
    [ "$status" -eq 0 ] || return 1
}

@test "every ast-grep scan invocation searches hidden directories" {
    # --no-ignore hidden が無いと、隠しディレクトリ配下にルールの対象を足したとき 1 件も
    # 検査しないまま緑になる。走査の挙動は上のテストが守るが、呼び出し側の配線を守るのは
    # ここだけである。
    #
    # 配線は YAML を safe_load して構造として読む (規範は home/.claude/rules/testing-practices.md)。
    require_command_or_skip uv || return 1

    run_yaml_probe ast-grep-wiring-probe.py
    [ "$status" -eq 0 ] || return 1

    # 件数が 0 だと hook の id や step の run を改名したときに
    # 「見つからないから緑」になる。先に 0 を弾いて空回りを塞ぐ
    assert_positive_count PRECOMMIT_HOOK_COUNT "${lines[@]}"
    assert_positive_count WORKFLOW_STEP_COUNT "${lines[@]}"

    # 配線されたすべてがフラグを伴うこと
    assert_contains "$output" "PRECOMMIT_ENTRY_MISSING_FLAG=0"
    assert_contains "$output" "WORKFLOW_RUN_MISSING_FLAG=0"
}
