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

# =============================================================================
# render_launch_agent_plist tests
# =============================================================================

@test "render_launch_agent_plist: substitutes placeholders" {
    local template="$TEST_HOME/tmpl.plist"
    local dest="$TEST_HOME/Library/LaunchAgents/out.plist"
    printf '%s\n' '__DOTFILES_DIR__/scripts/run.sh __HOME__/log' > "$template"
    DOTFILES_DIR="/repo"

    run render_launch_agent_plist "$template" "$dest"

    [ "$status" -eq 0 ]
    [ -f "$dest" ]
    grep -q "/repo/scripts/run.sh" "$dest"
    grep -q "$TEST_HOME/log" "$dest"
    ! grep -q "__DOTFILES_DIR__" "$dest"
    ! grep -q "__HOME__" "$dest"
}

@test "render_launch_agent_plist: dry-run does not write" {
    local template="$TEST_HOME/tmpl.plist"
    local dest="$TEST_HOME/out.plist"
    printf '%s\n' 'x' > "$template"
    DRY_RUN=true

    run render_launch_agent_plist "$template" "$dest"

    [ "$status" -eq 0 ]
    [[ "$output" == *"[DRY-RUN]"* ]]
    [ ! -f "$dest" ]
}

# =============================================================================
# install_mise_tools tests
# =============================================================================

@test "install_mise_tools: dry-run shows mise install without executing" {
    DRY_RUN=true

    run install_mise_tools

    [ "$status" -eq 0 ]
    [[ "$output" == *"[DRY-RUN] mise install"* ]]
    # dry-run は早期 return するため mise 存在チェックまで進まない（early-return を担保する negative）
    [[ "$output" != *"mise not found"* ]]
}

@test "install_mise_tools: warns and skips when mise is not on PATH" {
    DRY_RUN=false
    local empty_dir="$TEST_HOME/empty-path"
    mkdir -p "$empty_dir"

    PATH="$empty_dir" run install_mise_tools

    [ "$status" -eq 0 ]
    [[ "$output" == *"mise not found"* ]]
}

# =============================================================================
# install_apm tests (apm CLI 本体の brew インストール)
# =============================================================================

@test "install_apm: skips when apm is already installed" {
    DRY_RUN=false
    # apm を PATH 上に stub して「導入済み」分岐を厳密に検証する
    local bin_dir="$TEST_HOME/fake-bin"
    mkdir -p "$bin_dir"
    printf '#!/bin/sh\nexit 0\n' > "$bin_dir/apm"
    chmod +x "$bin_dir/apm"

    PATH="$bin_dir:$PATH" run install_apm

    [ "$status" -eq 0 ]
    [[ "$output" == *"already installed"* ]]
}

@test "install_apm: dry-run shows install without executing" {
    DRY_RUN=true
    # apm 未導入状態を再現（PATH を空にして brew 到達前の dry-run 分岐を強制）
    local empty_dir="$TEST_HOME/empty-path"
    mkdir -p "$empty_dir"

    PATH="$empty_dir" run install_apm

    [ "$status" -eq 0 ]
    [[ "$output" == *"[DRY-RUN] Install apm"* ]]
    # dry-run で brew に到達していない（到達すれば空 PATH で command not found になる）
    [[ "$output" != *"already installed"* ]]
}

# =============================================================================
# install_apm_skills tests (apm.yml 宣言スキルの実体化)
# =============================================================================

@test "install_apm_skills: dry-run shows apm install without executing" {
    DRY_RUN=true

    run install_apm_skills

    [ "$status" -eq 0 ]
    [[ "$output" == *"[DRY-RUN] apm install"* ]]
    # dry-run は早期 return するため apm 存在チェックまで進まない（early-return を担保する negative）
    [[ "$output" != *"apm not found"* ]]
}

@test "install_apm_skills: warns and skips when apm is not on PATH" {
    DRY_RUN=false
    local empty_dir="$TEST_HOME/empty-path"
    mkdir -p "$empty_dir"

    PATH="$empty_dir" run install_apm_skills

    [ "$status" -eq 0 ]
    [[ "$output" == *"apm not found"* ]]
}

@test "install_apm_skills: runs 'apm install --frozen' with cwd = DOTFILES_DIR/home" {
    DRY_RUN=false
    # apm を stub して呼び出し時の cwd と引数を記録し、実作業行 (cd home && apm install --frozen) を検証する。
    # 早期 return ガードだけでなく唯一の実作業行を通す（shell-out の cd 先・flag はユニットで担保する）。
    local bin_dir="$TEST_HOME/fake-bin"
    local rec="$TEST_HOME/apm-invocation.txt"
    mkdir -p "$bin_dir"
    cat > "$bin_dir/apm" <<'STUB'
#!/bin/sh
pwd -P > "$APM_STUB_REC"
printf '%s\n' "$*" >> "$APM_STUB_REC"
STUB
    chmod +x "$bin_dir/apm"
    export APM_STUB_REC="$rec"
    DOTFILES_DIR="$TEST_HOME/dotfiles"
    mkdir -p "$DOTFILES_DIR/home"

    PATH="$bin_dir:$PATH" run install_apm_skills

    [ "$status" -eq 0 ]
    # symlink 差を排すため両辺 pwd -P で比較する
    local expected_cwd
    expected_cwd="$(cd "$DOTFILES_DIR/home" && pwd -P)"
    [ "$(sed -n '1p' "$rec")" = "$expected_cwd" ]
    [[ "$(sed -n '2p' "$rec")" == *"install"* ]]
    [[ "$(sed -n '2p' "$rec")" == *"--frozen"* ]]
}

# =============================================================================
# SYMLINK_PAIRS 整合性テスト
# =============================================================================

# "source|target" pair 列を受け取り、source (| の前) が REPO_ROOT に実在しない
# ものを echo する。分割は bootstrap.sh の setup_dotfiles と同じ ${pair%%|*} を
# 使い、区切り規約を単一の真実源に保つ。
missing_symlink_sources() {
    local pair source
    for pair in "$@"; do
        source="${pair%%|*}"
        [ -e "$REPO_ROOT/$source" ] || echo "$source"
    done
}

@test "SYMLINK_PAIRS: all sources exist in repo" {
    # source を欠いた pair は fresh マシンの bootstrap で create_symlink が
    # 存在しないファイルを指す壊れた symlink を張るため、ここで drift を捕捉する。
    # 実配列を source して回すことで、テキスト parse の脆さ (配列内コメントを
    # phantom source と誤読する等) を避ける。
    load_symlink_pairs
    # 空配列 (slice 破綻) での vacuous pass を防ぐ negative guard
    [ "${#SYMLINK_PAIRS[@]}" -gt 0 ]

    local missing
    missing="$(missing_symlink_sources "${SYMLINK_PAIRS[@]}")"
    [ -z "$missing" ] || { echo "repo に存在しない source:"; echo "$missing"; false; }
}

@test "missing_symlink_sources: passes existing and flags missing pairs" {
    # 実装が gaming していないことを担保するため両方向を検証する。
    local out
    out="$(missing_symlink_sources 'home/.zshrc|.zshrc' 'home/__does_not_exist__/x|.x')"
    # 実在する source は missing に含めない（false positive を防ぐ）
    [[ "$out" != *".zshrc"* ]]
    # 欠落 source は検出する（false negative を防ぐ）
    [[ "$out" == *"__does_not_exist__"* ]]
}
