#!/bin/bash
# =============================================================================
# bootstrap.sh テスト用ヘルパー
# =============================================================================

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(dirname "$TEST_DIR")"
REPO_ROOT="$(dirname "$SCRIPTS_DIR")"

BOOTSTRAP_SCRIPT="$REPO_ROOT/bootstrap.sh"

FIXTURES_DIR="$TEST_DIR/fixtures"
BOOTSTRAP_FIXTURES_DIR="$FIXTURES_DIR/bootstrap"

# =============================================================================
# bootstrap.sh テスト用ヘルパー
# =============================================================================

# テスト用の仮想ホームディレクトリを作成
setup_test_home() {
    TEST_HOME=$(mktemp -d)
    export HOME="$TEST_HOME"
    export DOTFILES_DIR="$BOOTSTRAP_FIXTURES_DIR"

    mkdir -p "$TEST_HOME/.claude"
    mkdir -p "$TEST_HOME/.config/git"
    mkdir -p "$TEST_HOME/.local/bin"
}

# テスト用の仮想ホームディレクトリを削除
teardown_test_home() {
    if [ -n "$TEST_HOME" ] && [ -d "$TEST_HOME" ]; then
        rm -rf "$TEST_HOME"
    fi
}

# bootstrap.sh からヘルパー関数を読み込む
load_bootstrap_functions() {
    local temp_func_file
    temp_func_file=$(mktemp)

    if [ ! -f "$BOOTSTRAP_SCRIPT" ]; then
        echo "Error: Bootstrap script not found: $BOOTSTRAP_SCRIPT" >&2
        return 1
    fi

    # 重複マーカーに対応するため head -1 を使用
    local func_start main_start
    func_start=$(grep -n "^# ヘルパー関数$" "$BOOTSTRAP_SCRIPT" | head -1 | cut -d: -f1)
    main_start=$(grep -n "^# メイン処理$" "$BOOTSTRAP_SCRIPT" | head -1 | cut -d: -f1)

    if [ -z "$func_start" ]; then
        echo "Error: '# ヘルパー関数' marker not found in $BOOTSTRAP_SCRIPT" >&2
        rm -f "$temp_func_file"
        return 1
    fi
    if [ -z "$main_start" ]; then
        echo "Error: '# メイン処理' marker not found in $BOOTSTRAP_SCRIPT" >&2
        rm -f "$temp_func_file"
        return 1
    fi

    sed -n "$((func_start + 1)),$((main_start - 1))p" "$BOOTSTRAP_SCRIPT" > "$temp_func_file"

    if [ ! -s "$temp_func_file" ]; then
        echo "Warning: No functions extracted from $BOOTSTRAP_SCRIPT" >&2
        rm -f "$temp_func_file"
        return 1
    fi

    # shellcheck source=/dev/null
    source "$temp_func_file"
    rm -f "$temp_func_file"
}

# bootstrap.sh の SYMLINK_PAIRS 配列ブロックだけを切り出して source し、
# テストシェルに実配列を定義する。load_bootstrap_functions と同じ marker-slice 方式。
# ブロックは純データ (set -euo pipefail 等の副作用を含まない) なので、
# whole-file source を避けている理由がここにも当てはまる。実配列を source すれば
# テキスト parse の脆さ (配列内コメントを phantom source と誤読する等) を避けられる。
load_symlink_pairs() {
    local temp_pairs_file
    temp_pairs_file=$(mktemp)

    sed -n '/^SYMLINK_PAIRS=(/,/^)/p' "$BOOTSTRAP_SCRIPT" > "$temp_pairs_file"

    # shellcheck source=/dev/null
    source "$temp_pairs_file"
    rm -f "$temp_pairs_file"
}

# テスト用の偽 claude バイナリを PATH 先頭に用意する
# - plugin list / marketplace list --json は環境変数で制御した JSON を返す
#   （FAKE_PLUGINS_JSON / FAKE_MARKETPLACES_JSON、既定は空配列）
# - marketplace add / install は引数を FAKE_CLAUDE_LOG に記録する
# - FAKE_INSTALL_FAIL に一致する plugin id の install は非ゼロ終了する（best-effort 検証用）
setup_fake_claude() {
    local fake_bin="$TEST_HOME/fakebin"
    mkdir -p "$fake_bin"
    export FAKE_CLAUDE_LOG="$TEST_HOME/claude_calls.log"
    : > "$FAKE_CLAUDE_LOG"

    cat > "$fake_bin/claude" <<'FAKE'
#!/usr/bin/env bash
if [ "$1" = "plugin" ]; then
    case "$2" in
        list)
            echo "${FAKE_PLUGINS_JSON:-[]}"
            exit 0
            ;;
        marketplace)
            case "$3" in
                list)
                    echo "${FAKE_MARKETPLACES_JSON:-[]}"
                    exit 0
                    ;;
                add)
                    echo "marketplace add $4" >> "$FAKE_CLAUDE_LOG"
                    exit 0
                    ;;
            esac
            ;;
        install)
            echo "install $3" >> "$FAKE_CLAUDE_LOG"
            if [ -n "${FAKE_INSTALL_FAIL:-}" ] && [ "$3" = "${FAKE_INSTALL_FAIL}" ]; then
                exit 1
            fi
            exit 0
            ;;
    esac
fi
exit 0
FAKE
    chmod +x "$fake_bin/claude"
    export PATH="$fake_bin:$PATH"
}

# =============================================================================
# アサーションヘルパー
# =============================================================================
#
# bats の @test 本体は set -eE + trap ERR で走るが、macOS 標準の /bin/bash 3.2 は
# 「@test 本体の最終文ではない位置」の裸の [[ ]] が偽でも ERR トラップを発火させない
# (bash 5.3 は発火する)。ローカルの bats はこの bash 3.2 で、CI (ubuntu) は bash 5 で
# 走るため、[[ ]] のままだと「CI では落ちるがローカルでは素通りする」アサーションが
# 生まれる (実際に Task 1 の RED フェーズで嘘の緑が出た)。
# シェル関数呼び出しは単純コマンドなので、どちらの bash でも return 1 が確実に
# ERR を発火させる。以降のアサーションはこの形で書く。

# haystack が needle を部分文字列として含むことを確認する。
# 照合は case のクォート付きパターンで行う。needle をクォートせずに
# *$needle* と書くと [ ] を含む needle (例: [DRY-RUN]) が glob の文字クラスとして
# 解釈され、意図と違う 1 文字マッチになってしまうため、必ずクォートしてリテラル一致にする。
assert_contains() {
    local haystack="$1"
    local needle="$2"
    case "$haystack" in
        *"$needle"*) return 0 ;;
    esac
    echo "assert_contains: expected substring not found" >&2
    echo "  expected to contain: $needle" >&2
    echo "  actual: $haystack" >&2
    return 1
}

# haystack が needle を含まないことを確認する (assert_contains の否定形)。
refute_contains() {
    local haystack="$1"
    local needle="$2"
    case "$haystack" in
        *"$needle"*)
            echo "refute_contains: unexpected substring found" >&2
            echo "  expected NOT to contain: $needle" >&2
            echo "  actual: $haystack" >&2
            return 1
            ;;
    esac
    return 0
}

# haystack 内で needle_a の後に needle_b がこの順で現れることを確認する。
# 「両方含む」ではなく前後関係そのものが仕様であるケース専用
# (例: 1 件目の install 失敗後も 2 件目の install を試みる best-effort 継続の検証)。
# 単に両方含むかだけを見たいなら assert_contains を 2 回呼べばよい。
assert_contains_in_order() {
    local haystack="$1"
    local needle_a="$2"
    local needle_b="$3"
    case "$haystack" in
        *"$needle_a"*"$needle_b"*) return 0 ;;
    esac
    echo "assert_contains_in_order: expected order not found" >&2
    echo "  expected order: $needle_a -> $needle_b" >&2
    echo "  actual: $haystack" >&2
    return 1
}
