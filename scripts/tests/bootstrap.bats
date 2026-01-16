#!/usr/bin/env bats
# =============================================================================
# bootstrap.sh テスト
# =============================================================================

load test_helper

# =============================================================================
# セットアップ / ティアダウン
# =============================================================================

setup() {
    setup_test_home
    load_bootstrap_functions

    # デフォルト設定
    DRY_RUN=false
    FORCE_MODE=false
    BACKUP_DIR="$TEST_HOME/.dotfiles_backup"
}

teardown() {
    teardown_test_home
}

# =============================================================================
# ensure_directory tests
# =============================================================================

@test "ensure_directory: creates directory if not exists" {
    local test_dir="$TEST_HOME/new/nested/dir"
    [ ! -d "$test_dir" ]

    run ensure_directory "$test_dir"

    [ "$status" -eq 0 ]
    [ -d "$test_dir" ]
}

@test "ensure_directory: succeeds if directory already exists" {
    local test_dir="$TEST_HOME/.config/git"
    [ -d "$test_dir" ]

    run ensure_directory "$test_dir"

    [ "$status" -eq 0 ]
    [ -d "$test_dir" ]
}

# =============================================================================
# create_symlink tests
# =============================================================================

@test "create_symlink: creates symlink for new file" {
    local source="$BOOTSTRAP_FIXTURES_DIR/home/.zshrc"
    local target="$TEST_HOME/.zshrc"

    run create_symlink "$source" "$target"

    [ "$status" -eq 0 ]
    [ -L "$target" ]
    [ "$(readlink "$target")" = "$source" ]
}

@test "create_symlink: skips if symlink already exists and points to correct target" {
    local source="$BOOTSTRAP_FIXTURES_DIR/home/.zshrc"
    local target="$TEST_HOME/.zshrc"

    # 先にリンクを作成
    ln -s "$source" "$target"

    run create_symlink "$source" "$target"

    [ "$status" -eq 0 ]
    [[ "$output" == *"Already linked"* ]] || [[ "$output" == *"既にリンク"* ]]
}

@test "create_symlink: fails if target exists and not in force mode" {
    local source="$BOOTSTRAP_FIXTURES_DIR/home/.zshrc"
    local target="$TEST_HOME/.zshrc"

    # 既存ファイルを作成
    echo "existing content" > "$target"
    FORCE_MODE=false

    run create_symlink "$source" "$target"

    [ "$status" -ne 0 ]
    # 既存ファイルが残っている
    [ -f "$target" ]
    [ ! -L "$target" ]
}

@test "create_symlink: backs up and replaces in force mode" {
    local source="$BOOTSTRAP_FIXTURES_DIR/home/.zshrc"
    local target="$TEST_HOME/.zshrc"

    # 既存ファイルを作成
    echo "existing content" > "$target"
    FORCE_MODE=true

    run create_symlink "$source" "$target"

    [ "$status" -eq 0 ]
    [ -L "$target" ]
    # バックアップが作成されている
    [ -d "$BACKUP_DIR" ]
}

@test "create_symlink: replaces incorrect symlink" {
    local source="$BOOTSTRAP_FIXTURES_DIR/home/.zshrc"
    local target="$TEST_HOME/.zshrc"

    # 間違った場所を指すリンクを作成
    ln -s "/wrong/path" "$target"

    run create_symlink "$source" "$target"

    [ "$status" -eq 0 ]
    [ -L "$target" ]
    [ "$(readlink "$target")" = "$source" ]
}

# =============================================================================
# copy_if_not_exists tests
# =============================================================================

@test "copy_if_not_exists: copies file if target does not exist" {
    local source="$BOOTSTRAP_FIXTURES_DIR/home/.gitconfig.private.example"
    local target="$TEST_HOME/.gitconfig.private"

    run copy_if_not_exists "$source" "$target"

    [ "$status" -eq 0 ]
    [ -f "$target" ]
}

@test "copy_if_not_exists: does not overwrite existing file" {
    local source="$BOOTSTRAP_FIXTURES_DIR/home/.gitconfig.private.example"
    local target="$TEST_HOME/.gitconfig.private"

    # 既存ファイルを作成
    echo "custom content" > "$target"

    run copy_if_not_exists "$source" "$target"

    [ "$status" -eq 0 ]
    [ "$(cat "$target")" = "custom content" ]
}

# =============================================================================
# link_skills tests
# =============================================================================

@test "link_skills: links all skill directories" {
    local source_dir="$BOOTSTRAP_FIXTURES_DIR/home/.claude/skills"
    local target_dir="$TEST_HOME/.claude/skills"

    run link_skills "$source_dir" "$target_dir"

    [ "$status" -eq 0 ]
    [ -L "$target_dir/test-skill" ]
    [ "$(readlink "$target_dir/test-skill")" = "$source_dir/test-skill" ]
}

@test "link_skills: skips if skill already linked correctly" {
    local source_dir="$BOOTSTRAP_FIXTURES_DIR/home/.claude/skills"
    local target_dir="$TEST_HOME/.claude/skills"

    # 先にリンクを作成
    ln -s "$source_dir/test-skill" "$target_dir/test-skill"

    run link_skills "$source_dir" "$target_dir"

    [ "$status" -eq 0 ]
    [ -L "$target_dir/test-skill" ]
}

@test "link_skills: returns error count when symlink fails" {
    local source_dir="$BOOTSTRAP_FIXTURES_DIR/home/.claude/skills"
    local target_dir="$TEST_HOME/.claude/skills"

    # 既存ファイルを作成してリンク失敗を誘発
    echo "blocking file" > "$target_dir/test-skill"
    FORCE_MODE=false

    run link_skills "$source_dir" "$target_dir"

    [ "$status" -ne 0 ]
    [[ "$output" == *"Failed"* ]] || [[ "$output" == *"fail"* ]]
}

# =============================================================================
# dry-run mode tests
# =============================================================================

@test "create_symlink: dry-run mode shows action without executing" {
    local source="$BOOTSTRAP_FIXTURES_DIR/home/.zshrc"
    local target="$TEST_HOME/.zshrc"
    DRY_RUN=true

    run create_symlink "$source" "$target"

    [ "$status" -eq 0 ]
    [[ "$output" == *"[DRY-RUN]"* ]] || [[ "$output" == *"dry"* ]] || [[ "$output" == *"Dry"* ]]
    [ ! -L "$target" ]
}

# =============================================================================
# backup_file tests
# =============================================================================

@test "backup_file: preserves directory structure in backup" {
    # テスト用のファイルを作成
    mkdir -p "$TEST_HOME/.config/test"
    echo "test content" > "$TEST_HOME/.config/test/file.txt"

    run backup_file "$TEST_HOME/.config/test/file.txt"

    [ "$status" -eq 0 ]
    # バックアップがディレクトリ構造を保持しているか確認
    [ -f "$BACKUP_DIR/.config/test/file.txt" ]
    # 元のファイルは削除されている
    [ ! -f "$TEST_HOME/.config/test/file.txt" ]
}

@test "backup_file: dry-run mode shows action without executing" {
    mkdir -p "$TEST_HOME/.config"
    echo "test content" > "$TEST_HOME/.config/test.txt"
    DRY_RUN=true

    run backup_file "$TEST_HOME/.config/test.txt"

    [ "$status" -eq 0 ]
    [[ "$output" == *"[DRY-RUN]"* ]]
    # 元のファイルは残っている
    [ -f "$TEST_HOME/.config/test.txt" ]
}
