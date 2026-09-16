#!/usr/bin/env bash
# =============================================================================
# CI の bats job の入口。bats を走らせ、次のどちらかに当たれば失敗させる。
#
#   bats 自体の失敗      パイプの後段 (tee) の成功に飲み込まれないよう pipefail で拾う。
#                        1 件も実行されないスイートも bats 自体が失敗として返す
#   skip が 1 件でもある CI では前提の不在を skip で隠さない (scripts/tests/test_helper.bash の
#                        skip_outside_ci が落とす) ので、ここで起きる skip は全部が異常
#
# どの job も供給できない依存 (macOS 専用コマンド等) のテストは、skip ではなく
# タグ uncovered で実行対象から外す。
#
# 使い方:
#   run-bats.sh <bats へ渡すパス>...
#   手元で CI と同じ条件にするときは CI=true を付けて呼ぶ。
# =============================================================================
set -euo pipefail

tap="$(mktemp)"
trap 'rm -f "$tap"' EXIT

bats --filter-tags '!uncovered' --formatter tap "$@" | tee "$tap"

# 該当行を出して、どのテストかを CI のログから追えるようにする
if grep '# skip' "$tap" >&2; then
    echo "skip されたテストがある" >&2
    exit 1
fi
