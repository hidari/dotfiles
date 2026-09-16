#!/usr/bin/env bats
# =============================================================================
# CI ワークフローの配線を pin する
#
# 検査機構が正しくても、取り付けが外れれば CI は検証しないまま緑を返すか、
# push して初めて赤くなる。ここではその取り付けを開発機の時点で見る。
#
# 注意:
# - bats は @test 名を関数名へエンコードするため名前は ASCII に限る
#   (rules/bats-test-name-ascii-only.yml)
# =============================================================================

load test_helper

@test "the bats job runs the whole suite through the CI wrapper" {
    # 対象を個別ファイルへ絞っても、ラッパは skip 0 件として緑を返す
    assert_workflow_contains 'run: scripts/ci/run-bats.sh scripts/tests/'
}

@test "the wiring match ignores commented-out lines and trailing arguments" {
    # 行の一部で一致させると、コメントアウトした行や対象を絞った行でも上の pin が緑になる
    WORKFLOW_FILE="$BATS_TEST_TMPDIR/workflow.yml"
    printf '%s\n' \
        '      # run: scripts/ci/run-bats.sh scripts/tests/' \
        '        run: scripts/ci/run-bats.sh scripts/tests/nvim-markdown.bats' > "$WORKFLOW_FILE"
    run assert_workflow_contains 'run: scripts/ci/run-bats.sh scripts/tests/'
    [ "$status" -ne 0 ]

    # 対照: インデントだけが違う行には一致する
    printf '%s\n' '            run: scripts/ci/run-bats.sh scripts/tests/' > "$WORKFLOW_FILE"
    run assert_workflow_contains 'run: scripts/ci/run-bats.sh scripts/tests/'
    [ "$status" -eq 0 ]
}

@test "every run step runs under bash with pipefail or pwsh" {
    # shell を省いた step は bash -e で動き、パイプの前段の失敗が緑になる。
    # job の defaults.run は workflow の defaults.run を丸ごと置き換えるので、
    # 実効の shell は YAML の構造から step ごとに決める (決め方はプローブが持つ)
    require_command_or_skip uv || return 1

    run env WORKFLOW_FILE="$WORKFLOW_FILE" uv run --quiet --no-project --with pyyaml python3 \
        "$REPO_ROOT/scripts/tests/ci-shell-probe.py"
    [ "$status" -eq 0 ] || return 1

    # 0 件だと step を 1 つも見ないまま違反 0 になる
    refute_contains "$output" "RUN_STEP_COUNT=0"
    # 違反の一覧が空であること。run は末尾の改行を落とすので足してから行単位で見る
    assert_contains "$output"$'\n' $'\nRUN_STEP_WITHOUT_SHELL=\n'
}

@test "the shell probe lets job defaults replace workflow defaults as a whole" {
    # 上のテストの判定モデルを pin する。GitHub Actions は job に defaults.run があると
    # workflow 側の defaults.run を使わない (working-directory だけの job が bash -e で動いた)。
    # キーごとに混ぜるモデルだと、この job を bash と誤って通す
    require_command_or_skip uv || return 1

    local workflow="$BATS_TEST_TMPDIR/workflow.yml"
    cat > "$workflow" << 'EOF'
defaults:
  run:
    shell: bash
jobs:
  replaced:
    defaults:
      run:
        working-directory: sub
    steps:
      - name: without shell
        run: "true"
  inherited:
    steps:
      - name: from workflow
        run: "true"
      - name: explicit sh
        shell: sh
        run: "true"
EOF

    run env WORKFLOW_FILE="$workflow" uv run --quiet --no-project --with pyyaml python3 \
        "$REPO_ROOT/scripts/tests/ci-shell-probe.py"
    [ "$status" -eq 0 ] || return 1

    assert_contains "$output" "RUN_STEP_COUNT=3"
    assert_contains "$output"$'\n' $'\nRUN_STEP_WITHOUT_SHELL=replaced/without shell,inherited/explicit sh\n'
}

@test "every shell script under scripts/ci is executable in the index" {
    # workflow は shebang 経由で直接実行するので、実行ビットが落ちると Permission denied で
    # 止まる。テストは bash 経由で呼ぶため、この面はテストからは一切見えない。
    # 見るのは作業ツリーの属性ではなく index の mode で、CI が触るのは clone された側になる。
    # .ps1 を含めないのは pwsh が実行ビット無しでも走らせるため (run-pester.ps1 は 100644)
    local entries
    entries=$(git -C "$REPO_ROOT" ls-files -s 'scripts/ci/*.sh')
    [ -n "$entries" ]

    # 100755 以外の行が 1 行も無いこと (grep -v の rc=1)。落ちたときは該当行が出る
    run grep -v '^100755 ' <<< "$entries"
    [ "$status" -eq 1 ]
}
