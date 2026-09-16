#!/usr/bin/env bash
# =============================================================================
# bats の TAP 出力に現れる skip を宣言と突き合わせる
#
# CI の bats job は scripts/tests/ を全件走らせるが、job が持たないコマンドのテストは
# skip でかわされ「1 件も検証していないのに緑」になる。その緑を証拠として使えるように、
# skip の集合そのものを検査対象にする。
#
# 「skip 0 件」を条件にはできない。どの job も供給しない依存 (macOS 専用コマンド等) に
# よる skip は正当に残るためで、その集合の canonical は test_helper.bash の
# UNCOVERED_DEPENDENCIES にある。件数だけを見ると宣言した skip が別の skip と
# 入れ替わっても同じ数になるので、両方向で突き合わせる。
#
#   宣言外の skip   マーカーを持たない skip、または表に無い依存の skip
#   dead な宣言     表にあるのに実際には skip されなかった依存
#
# 使い方:
#   assert-declared-skips.sh <tap-file>
#     <tap-file>  bats --formatter tap の出力を落としたファイル
#
# set -euo pipefail は main の内側に置く。top-level に置くと source したテストシェルへ
# errexit が漏れる (scripts/ci/download-and-verify.sh と同じ理由)。
# =============================================================================

# TAP 1 行から skip の理由を取り出す。skip 行でなければ非 0 を返す。
# テスト名自体が "# skip" を含む場合に備えて最後の出現から取る。
# 理由を持たない "# skip" だけの行は空文字を返す (マーカーが無いので宣言外へ倒れる)。
tap_skip_reason() {
    local line="$1"

    case "$line" in
        *"# skip"*) ;;
        *) return 1 ;;
    esac

    local reason="${line##*# skip }"
    if [ "$reason" = "$line" ]; then
        reason=""
    fi
    printf '%s' "$reason"
}

main() {
    set -euo pipefail

    local script_dir repo_root
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    repo_root="$(dirname "$(dirname "$script_dir")")"

    # 宣言表の canonical はテストヘルパ。値をこちらへ書き写すと drift するので source して読む。
    # shellcheck source=/dev/null
    source "${TEST_HELPER:-$repo_root/scripts/tests/test_helper.bash}"

    local tap="${1:-}"
    if [ -z "$tap" ]; then
        echo "usage: $(basename "${BASH_SOURCE[0]}") <tap-file>" >&2
        return 2
    fi
    if [ ! -s "$tap" ]; then
        echo "TAP 出力が空か存在しない: $tap" >&2
        return 1
    fi

    local undeclared=0 line reason dep
    local skipped_deps=""

    while IFS= read -r line; do
        reason="$(tap_skip_reason "$line")" || continue

        case "$reason" in
            "$UNCOVERED_SKIP_MARKER "*)
                dep="${reason#"$UNCOVERED_SKIP_MARKER" }"
                dep="${dep%%:*}"
                if ! uncovered_reason "$dep" > /dev/null; then
                    echo "宣言表に無い依存を指す skip: $dep" >&2
                    undeclared=$((undeclared + 1))
                    continue
                fi
                skipped_deps="$skipped_deps $dep"
                ;;
            *)
                echo "宣言されていない skip: $line" >&2
                undeclared=$((undeclared + 1))
                ;;
        esac
    done < "$tap"

    # 1 件も走っていない TAP は skip も 0 件なので、上の検査だけでは素通りする。
    # 赤いテストも「実行された」側に数える。ok だけで数えると全件赤の TAP が
    # 「1 件も実行されていない」という別の理由で落ちて原因を取り違える。
    local executed
    executed=$(grep -c -e '^ok ' -e '^not ok ' "$tap" || true)
    if [ "$executed" -eq 0 ]; then
        echo "TAP に実行されたテストが 1 件も無い: $tap" >&2
        return 1
    fi

    # 表が空なら dead な宣言はありえない。件数で先に分岐するのは、bash 3.2 が
    # set -u 下で空配列の [@] 展開を unbound variable にするため。表が空になるのは
    # 異常ではなく、全依存が CI へ入った状態を意味する。
    local missing=0 entry
    if [ "${#UNCOVERED_DEPENDENCIES[@]}" -gt 0 ]; then
        for entry in "${UNCOVERED_DEPENDENCIES[@]}"; do
            dep="${entry%%:*}"
            case " $skipped_deps " in
                *" $dep "*) ;;
                *)
                    echo "宣言したが skip されていない (dead な宣言): $dep" >&2
                    missing=$((missing + 1))
                    ;;
            esac
        done
    fi

    if [ "$undeclared" -gt 0 ] || [ "$missing" -gt 0 ]; then
        echo "skip の突き合わせに失敗: 宣言外 $undeclared 件 / dead な宣言 $missing 件" >&2
        return 1
    fi

    echo "skip の突き合わせに成功: 実行 $executed 件、宣言済みの skip のみ"
}

# 直接実行時のみ main を走らせ、source 時は関数だけ公開する
if [ "${BASH_SOURCE[0]}" = "${0}" ]; then
    main "$@"
fi
