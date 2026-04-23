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
