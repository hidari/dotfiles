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

@test "every run step in test.yml runs under an allowed shell" {
    # 実効 shell の決め方と許可する shell は ci-shell-probe.py が持つ
    require_command_or_skip uv || return 1

    run_yaml_probe ci-shell-probe.py "$WORKFLOW_FILE"
    [ "$status" -eq 0 ] || return 1

    assert_positive_count RUN_STEP_COUNT "${lines[@]}"
    assert_array_contains "RUN_STEP_DISALLOWED_SHELL=" "${lines[@]}"
}

@test "the shell probe lets job defaults replace workflow defaults as a whole" {
    # 上のテストの判定モデルを pin する。キーごとに混ぜるモデルだと replaced の step を通してしまう
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

    run_yaml_probe ci-shell-probe.py "$workflow"
    [ "$status" -eq 0 ] || return 1

    assert_array_contains "RUN_STEP_COUNT=3" "${lines[@]}"
    assert_array_contains "RUN_STEP_DISALLOWED_SHELL=replaced/without shell,inherited/explicit sh" "${lines[@]}"
}

@test "every job in the workflows pins its runner image" {
    # 浮動ラベルの判定は ci-runner-probe.py が持つ
    require_command_or_skip uv || return 1

    run_yaml_probe ci-runner-probe.py "$REPO_ROOT/.github/workflows"
    [ "$status" -eq 0 ] || return 1

    assert_positive_count RUNNER_JOB_COUNT "${lines[@]}"
    assert_array_contains "RUNNER_FLOATING=" "${lines[@]}"
}

@test "the runner probe finds floating labels in string, list and group forms" {
    # 上のテストの判定を pin する。文字列だけを見る判定だと、配列や group 形の浮動ラベルを通してしまう。
    # GitHub は .yaml のワークフローも読むので、拡張子の両方を置く
    require_command_or_skip uv || return 1

    local workflows="$BATS_TEST_TMPDIR/workflows"
    mkdir -p "$workflows"
    cat > "$workflows/workflow.yml" << 'EOF'
jobs:
  pinned:
    runs-on: ubuntu-24.04
  floating:
    runs-on: ubuntu-latest
  listed:
    runs-on: [self-hosted, macos-latest-xlarge]
  called:
    uses: ./.github/workflows/reusable.yml
EOF
    cat > "$workflows/grouped.yaml" << 'EOF'
jobs:
  grouped:
    runs-on:
      group: runners
      labels: ubuntu-latest
EOF

    run_yaml_probe ci-runner-probe.py "$workflows"
    [ "$status" -eq 0 ] || return 1

    assert_array_contains "RUNNER_JOB_COUNT=4" "${lines[@]}"
    assert_array_contains "RUNNER_FLOATING=grouped.yaml/grouped,workflow.yml/floating,workflow.yml/listed" "${lines[@]}"
}

@test "dependabot updates every place that uses external actions" {
    # 覆う範囲の判定は dependabot-probe.py が持つ
    require_command_or_skip uv || return 1

    run_yaml_probe dependabot-probe.py "$REPO_ROOT"
    [ "$status" -eq 0 ] || return 1

    assert_positive_count ACTION_DIR_COUNT "${lines[@]}"
    assert_array_contains "UNCOVERED_ACTION_DIRS=" "${lines[@]}"
}

@test "the dependabot probe reports action directories left out of the config" {
    # 上のテストの判定を pin する。数えるのは外部 action を uses で使う場所だけで (e は run だけ)、
    # * は1段だけに一致し (c/d は actions/* の外)、単数形の directory は glob にならず、
    # 他の ecosystem の directories では覆ったことにならない。.yaml も GitHub は読む
    require_command_or_skip uv || return 1

    local root="$BATS_TEST_TMPDIR/repo"
    local actions="$root/.github/actions"
    mkdir -p "$root/.github/workflows" "$actions/a" "$actions/b" "$actions/c/d" "$actions/e"
    printf 'jobs: {x: {steps: [{uses: actions/checkout@v1}, {uses: ./.github/actions/a}]}}\n' \
        > "$root/.github/workflows/ci.yaml"
    local composite='runs: {using: composite, steps: [{uses: actions/cache@v1}]}'
    printf '%s\n' "$composite" > "$actions/a/action.yml"
    printf '%s\n' "$composite" > "$actions/b/action.yaml"
    printf '%s\n' "$composite" > "$actions/c/d/action.yml"
    printf 'runs: {using: composite, steps: [{run: "true", shell: bash}]}\n' > "$actions/e/action.yml"
    cat > "$root/.github/dependabot.yml" << 'EOF'
version: 2
updates:
  - package-ecosystem: github-actions
    directories:
      - /.github/actions/*
  - package-ecosystem: github-actions
    directory: /.github/actions/c/*
  - package-ecosystem: npm
    directories:
      - /
EOF

    run_yaml_probe dependabot-probe.py "$root"
    [ "$status" -eq 0 ] || return 1

    assert_array_contains "ACTION_DIR_COUNT=4" "${lines[@]}"
    assert_array_contains "UNCOVERED_ACTION_DIRS=/,/.github/actions/c/d" "${lines[@]}"
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
