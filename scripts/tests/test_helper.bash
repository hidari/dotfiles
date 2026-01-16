#!/bin/bash
# =============================================================================
# テスト用ヘルパー（backup.sh / bootstrap.sh 共通）
# =============================================================================

# テストディレクトリのパスを取得
TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(dirname "$TEST_DIR")"
REPO_ROOT="$(dirname "$SCRIPTS_DIR")"

# スクリプトのパス
BACKUP_SCRIPT="$SCRIPTS_DIR/backup.sh"
BOOTSTRAP_SCRIPT="$REPO_ROOT/bootstrap.sh"

# フィクスチャのパス
FIXTURES_DIR="$TEST_DIR/fixtures"
BOOTSTRAP_FIXTURES_DIR="$FIXTURES_DIR/bootstrap"

# =============================================================================
# 各テスト前の初期化
# =============================================================================

setup() {
    # グローバル変数をクリア
    unset BACKUP_PAIRS
    unset PAIR_NAME
    unset PAIR_SOURCE
    unset PAIR_DEST
    unset PAIR_EXCLUDES

    # テスト用の一時ファイル
    FILTERED_ERRORS_FILE=$(mktemp)
    export FILTERED_ERRORS_FILE

    # 必要な変数を設定
    LOG_FILE="/dev/null"
    DRY_RUN=true

    # backup.sh から関数を抽出して読み込む
    load_backup_functions
}

# 各テスト後の後処理
teardown() {
    # 一時ファイルを削除
    if [ -n "$FILTERED_ERRORS_FILE" ] && [ -f "$FILTERED_ERRORS_FILE" ]; then
        rm -f "$FILTERED_ERRORS_FILE"
    fi
}

# =============================================================================
# ヘルパー関数
# =============================================================================

# backup.sh から関数定義のみを読み込む
load_backup_functions() {
    local temp_func_file
    temp_func_file=$(mktemp)

    # 行番号を取得
    local func_start pairs_start main_start
    func_start=$(grep -n "^# 関数定義$" "$BACKUP_SCRIPT" | cut -d: -f1)
    pairs_start=$(grep -n "^# 複数ペア対応$" "$BACKUP_SCRIPT" | cut -d: -f1)
    main_start=$(grep -n "^# メイン処理$" "$BACKUP_SCRIPT" | cut -d: -f1)

    # 関数定義セクションを抽出（関数定義 から 複数ペア対応 の前まで）
    if [ -n "$func_start" ] && [ -n "$pairs_start" ]; then
        sed -n "$((func_start + 2)),$((pairs_start - 2))p" "$BACKUP_SCRIPT" > "$temp_func_file"
    fi

    # 複数ペア対応セクションを追加（複数ペア対応 から メイン処理 の前まで）
    if [ -n "$pairs_start" ] && [ -n "$main_start" ]; then
        sed -n "$((pairs_start + 2)),$((main_start - 2))p" "$BACKUP_SCRIPT" >> "$temp_func_file"
    fi

    # shellcheck source=/dev/null
    source "$temp_func_file"
    rm -f "$temp_func_file"
}

# =============================================================================
# bootstrap.sh テスト用ヘルパー
# =============================================================================

# テスト用の仮想ホームディレクトリを作成
setup_test_home() {
    TEST_HOME=$(mktemp -d)
    export HOME="$TEST_HOME"
    export DOTFILES_DIR="$BOOTSTRAP_FIXTURES_DIR"

    # 必要なディレクトリを作成
    mkdir -p "$TEST_HOME/.claude/skills"
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

    # 行番号を取得
    local func_start main_start
    func_start=$(grep -n "^# ヘルパー関数$" "$BOOTSTRAP_SCRIPT" | cut -d: -f1)
    main_start=$(grep -n "^# メイン処理$" "$BOOTSTRAP_SCRIPT" | cut -d: -f1)

    # ヘルパー関数セクションを抽出
    if [ -n "$func_start" ] && [ -n "$main_start" ]; then
        sed -n "$((func_start + 1)),$((main_start - 1))p" "$BOOTSTRAP_SCRIPT" > "$temp_func_file"
        # shellcheck source=/dev/null
        source "$temp_func_file"
    fi

    rm -f "$temp_func_file"
}
