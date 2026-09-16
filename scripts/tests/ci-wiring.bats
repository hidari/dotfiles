#!/usr/bin/env bats
# =============================================================================
# CI ワークフローの配線を pin する
#
# 検査機構が正しくても、取り付けが外れれば CI は何も検証しないまま緑を返す。
# ここではその取り付けのうち、外れても CI が赤くならない面だけを見る。
#
# 注意:
# - bats は @test 名を関数名へエンコードするため名前は ASCII に限る
#   (rules/bats-test-name-ascii-only.yml)
# =============================================================================

load test_helper

@test "the bats job runs the whole suite and fails on any skip" {
    # 3 行のどれが外れても、CI は赤くならずに検証の範囲だけが縮む。
    #   pipefail    無いと bats の失敗を tee の成功が飲み込む
    #   対象        scripts/tests/ を個別ファイルへ絞っても skip 0 件の検査は緑を返す
    #   skip の検査 無いと不在を skip で隠したテストが緑で通る
    local expected
    expected=$(
        cat << 'EOF'
set -o pipefail
bats --filter-tags '!uncovered' --formatter tap scripts/tests/ | tee "$RUNNER_TEMP/bats.tap"
if grep '# skip' "$RUNNER_TEMP/bats.tap"; then
echo "skip されたテストがある。CI では前提の不在を skip で隠さない" >&2
exit 1
fi
EOF
    )

    assert_workflow_contains "$expected"
}

@test "every shell script under scripts/ci is executable in the index" {
    # workflow は shebang 経由で直接実行するので、実行ビットが落ちると Permission denied で
    # 止まる。テストは bash 経由で呼ぶため、この面はテストからは一切見えない。
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
