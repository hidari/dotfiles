#!/usr/bin/env bats
# =============================================================================
# 宣言表 CI_BATS_JOB_COMMANDS と CI ワークフローの実体を突き合わせる
#
# 宣言表は「CI の bats job が実行時に持つコマンド」の写しで、canonical は
# .github/workflows/test.yml の bats job にある。写しである以上 drift するので、
# 両方向で突き合わせる。
#
#   宣言 -> 実体  宣言した action / step が bats job に本当に配線されているか
#   実体 -> 宣言  bats job が使う action が宣言に載っているか
#
# 片方向だけだと、CI 側でツールの導入を消したときに「テストは CI で必須と思っているのに
# 実際は入っていない」状態が残り、そのテストは CI で赤くなるのではなく skip へ落ちる。
#
# 注意:
# - bats は @test 名を関数名へエンコードするため名前は ASCII に限る
#   (rules/bats-test-name-ascii-only.yml)
# =============================================================================

load test_helper

setup() {
    BLOCK=$(mktemp)
}

teardown() {
    if [ -n "${BLOCK:-}" ]; then
        rm -f "$BLOCK"
    fi
}

# 宣言表から kind が一致する source だけを標準出力へ並べる。
declared_sources_of_kind() {
    local want="$1"
    local entry rest
    for entry in "${CI_BATS_JOB_COMMANDS[@]}"; do
        rest="${entry#*:}"
        if [ "${rest%%:*}" = "$want" ]; then
            printf '%s\n' "${rest#*:}"
        fi
    done
}

@test "the job extractor yields the bats job and not its neighbours" {
    # 切り出しが空や全文に化けると、以降の突き合わせが一斉に素通りするか一斉に赤くなる。
    # どちらも「宣言と実体がずれている」という本来の失敗と区別できないので、
    # 切り出し器そのものを対照付きで先に固定する
    extract_workflow_job bats "$BLOCK"
    run cat "$BLOCK"

    assert_contains "$output" "Run Bats tests"
    # 隣接 job の step が混ざっていないこと (全文を返す壊れ方を捕まえる)
    refute_contains "$output" "Install Pester"
    refute_contains "$output" "Scan new commits for leaks"
}

@test "the job extractor fails loudly on a job that does not exist" {
    # 空を黙って返すと、宣言と実体の突き合わせが 1 件も走らないまま緑になる
    run extract_workflow_job definitely-not-a-job "$BLOCK"

    [ "$status" -ne 0 ]
    assert_contains "$output" "job block not found"
}

@test "every action-supplied command is wired into the bats job" {
    extract_workflow_job bats "$BLOCK"
    local block_text
    block_text=$(cat "$BLOCK")

    local source checked=0
    while read -r source; do
        [ -n "$source" ] || continue
        checked=$((checked + 1))

        # composite action の実体があること
        [ -f "$REPO_ROOT/.github/actions/$source/action.yml" ]
        # bats job がそれを使っていること
        assert_contains "$block_text" "uses: ./.github/actions/$source"
    done < <(declared_sources_of_kind action)

    # 1 件も回らないと空回りして緑になる
    [ "$checked" -gt 0 ]
}

@test "every step-supplied command has its step in the bats job" {
    extract_workflow_job bats "$BLOCK"
    local block_text
    block_text=$(cat "$BLOCK")

    local source checked=0
    while read -r source; do
        [ -n "$source" ] || continue
        checked=$((checked + 1))
        assert_contains "$block_text" "name: $source"
    done < <(declared_sources_of_kind step)

    [ "$checked" -gt 0 ]
}

@test "every action used by the bats job is declared" {
    # 逆向き。宣言から実体は追えても、workflow へ足した action が宣言に載らないと
    # 「CI は入れているのにテストは skip へ落ちる」形が残る
    extract_workflow_job bats "$BLOCK"

    local declared
    declared=$(declared_sources_of_kind action)
    [ -n "$declared" ]

    local used action checked=0
    used=$(sed -n 's|.*uses: \./\.github/actions/\([a-z0-9-]*\).*|\1|p' "$BLOCK")
    [ -n "$used" ]

    for action in $used; do
        checked=$((checked + 1))
        # shellcheck disable=SC2086
        assert_array_contains "$action" $declared
    done

    [ "$checked" -gt 0 ]
}

@test "runner-supplied commands carry the reason they are assumed present" {
    # runner 由来は突き合わせる相手が workflow に無い。理由の記述だけが根拠になるので、
    # 空のまま宣言へ足せないようにする
    local source checked=0
    while read -r source; do
        checked=$((checked + 1))
        [ -n "$source" ]
    done < <(declared_sources_of_kind runner)

    [ "$checked" -gt 0 ]
}

@test "the bats job runs the declared-skip guard over a TAP of the whole suite" {
    # 取り付けを外す変異への堰。突き合わせ器を作っても呼ばれなければ、
    # 宣言外の skip はそのまま緑で通る。3 つの条件が揃って初めて機構になる
    extract_workflow_job bats "$BLOCK"
    run cat "$BLOCK"

    # ガードが呼ばれること
    assert_contains "$output" "scripts/ci/assert-declared-skips.sh"
    # TAP でなければ skip 行が出ず、ガードは常に「skip 0 件」を見る
    assert_contains "$output" "--formatter tap"
    # pipefail が無いと bats の失敗を tee の成功が飲み込む
    assert_contains "$output" "set -o pipefail"
}

@test "every shell script under scripts/ci is executable in the index" {
    # workflow は shebang 経由で直接実行するので、実行ビットが落ちると Permission denied で
    # 止まる。テストは bash 経由で呼ぶため、この面はテストからは一切見えない。
    # 実際に assert-declared-skips.sh を 100644 のままコミットして踏んだ。
    # 見るのは作業ツリーの属性ではなく index の mode で、CI が触るのは clone された側になる。
    # .ps1 を含めないのは pwsh が実行ビット無しでも走らせるため (run-pester.ps1 は 100644)
    local checked=0 mode path
    while read -r mode _ _ path; do
        [ -n "$path" ] || continue
        checked=$((checked + 1))
        [ "$mode" = "100755" ]
    done < <(git -C "$REPO_ROOT" ls-files -s 'scripts/ci/*.sh')

    [ "$checked" -gt 0 ]
}

@test "the declared kinds are limited to the three the checks understand" {
    # 知らない kind を足すと、その行はどの検査にも拾われず宣言だけが増える。
    # 突き合わせの射程外が静かに広がるのを防ぐ
    local entry rest kind
    for entry in "${CI_BATS_JOB_COMMANDS[@]}"; do
        rest="${entry#*:}"
        kind="${rest%%:*}"
        assert_array_contains "$kind" action step runner
    done
}
