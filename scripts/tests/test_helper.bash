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
