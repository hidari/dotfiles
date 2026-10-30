#!/usr/bin/env bats
# =============================================================================
# ast-grep scan が隠しディレクトリ配下のファイルを見るかを検証する
#
# ast-grep test は仮想のスニペットに対して走るため、走査の側を通らない。
# 隠しディレクトリの扱いを確かめられるのはこのファイルだけである。
#
# 注意: @test 名は ASCII に限る (rules/bats-test-name-ascii-only.yml)
# =============================================================================

load test_helper

setup() {
    require_command_or_skip ast-grep || return 1

    # 本番のルールは使わない。本番のルールがパスを絞ると、走査の挙動とは無関係に結果が
    # 変わるためで、fixture の中に対象のパスを絞らないルールを置く
    FIXTURE="$BATS_TEST_TMPDIR/fixture"
    mkdir -p "$FIXTURE/rules" "$FIXTURE/home/.config/example"
    printf 'ruleDirs:\n  - rules\n' > "$FIXTURE/sgconfig.yml"
    printf 'id: hidden-probe\nlanguage: bash\nseverity: error\nrule:\n  pattern: hidden_probe_marker\n' \
        > "$FIXTURE/rules/hidden-probe.yml"
    printf 'hidden_probe_marker\n' > "$FIXTURE/home/.config/example/hidden.sh"
}

@test "with no-ignore hidden the scan visits and reports a file under a hidden directory" {
    run_in_dir "$FIXTURE" ast-grep scan --no-ignore hidden --inspect summary
    [ "$status" -eq 1 ] || return 1
    assert_contains "$output" "scannedFileCount=1"
    assert_contains "$output" "hidden.sh"
}

@test "without no-ignore hidden the scan silently visits nothing" {
    # なぜ --no-ignore hidden が要るのかを実行可能な事実として残す。違反が出ないことだけでは
    # 「見ていない」と「見たが一致しない」を区別できないので、走査した件数で見る。
    # ast-grep が既定で隠しディレクトリを飛ばさなくなったら、このテストが赤くなって教えてくれる
    run_in_dir "$FIXTURE" ast-grep scan --inspect summary
    [ "$status" -eq 0 ] || return 1
    assert_contains "$output" "scannedFileCount=0"
}

@test "every ast-grep scan invocation searches hidden directories" {
    # --no-ignore hidden が無いと、隠しディレクトリ配下 (home/.claude や home/.config) の
    # ファイルを 1 件も検査しないまま緑になる。走査の挙動は上のテストが守るが、呼び出し側の
    # 配線を守るのはここだけである。
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
