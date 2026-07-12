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
    # bootstrap.sh の該当分岐は log "Already linked: $target" ([INFO] 接頭辞) のみを
    # 出力し、日本語版のメッセージは存在しない (コメントに 既にリンク の語があるだけ)。
    # any-of で弱めていた元のアサーションを厳密な単一アサーションへ強化する。
    assert_contains "$output" "[INFO] Already linked: $target"
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
    # bootstrap.sh の該当分岐は echo "[DRY-RUN] ln -sf $source $target" しか出力せず、
    # "dry" / "Dry" 表記は存在しない。any-of で弱めていた元のアサーションを
    # 実際の出力全体に一致する厳密な単一アサーションへ強化する。
    assert_contains "$output" "[DRY-RUN] ln -sf $source $target"
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
    assert_contains "$output" "[DRY-RUN]"
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
    assert_contains "$output" "[DRY-RUN]"
    [ ! -f "$dest" ]
}

# =============================================================================
# install_mise_tools tests
# =============================================================================

@test "install_mise_tools: dry-run shows mise install without executing" {
    DRY_RUN=true

    run install_mise_tools

    [ "$status" -eq 0 ]
    assert_contains "$output" "[DRY-RUN] mise install"
    # dry-run は早期 return するため mise 存在チェックまで進まない（early-return を担保する negative）
    refute_contains "$output" "mise not found"
}

@test "install_mise_tools: warns and skips when mise is not on PATH" {
    DRY_RUN=false
    local empty_dir="$TEST_HOME/empty-path"
    mkdir -p "$empty_dir"

    PATH="$empty_dir" run install_mise_tools

    [ "$status" -eq 0 ]
    assert_contains "$output" "mise not found"
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
    assert_contains "$output" "already installed"
}

@test "install_apm: dry-run shows install without executing" {
    DRY_RUN=true
    # apm 未導入状態を再現（PATH を空にして brew 到達前の dry-run 分岐を強制）
    local empty_dir="$TEST_HOME/empty-path"
    mkdir -p "$empty_dir"

    PATH="$empty_dir" run install_apm

    [ "$status" -eq 0 ]
    assert_contains "$output" "[DRY-RUN] Install apm"
    # dry-run で brew に到達していない（到達すれば空 PATH で command not found になる）
    refute_contains "$output" "already installed"
}

# =============================================================================
# install_apm_skills tests (apm.yml 宣言スキルの実体化)
# =============================================================================

@test "install_apm_skills: dry-run shows apm install without executing" {
    DRY_RUN=true

    run install_apm_skills

    [ "$status" -eq 0 ]
    assert_contains "$output" "[DRY-RUN] apm install"
    # dry-run は早期 return するため apm 存在チェックまで進まない（early-return を担保する negative）
    refute_contains "$output" "apm not found"
}

@test "install_apm_skills: warns and skips when apm is not on PATH" {
    DRY_RUN=false
    local empty_dir="$TEST_HOME/empty-path"
    mkdir -p "$empty_dir"

    PATH="$empty_dir" run install_apm_skills

    [ "$status" -eq 0 ]
    assert_contains "$output" "apm not found"
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
    assert_contains "$(sed -n '2p' "$rec")" "install"
    assert_contains "$(sed -n '2p' "$rec")" "--frozen"
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

# file が sources のいずれかにカバーされるか判定する純粋関数。
# covered = file 自身が source (file pair)、または file が source の配下 (dir pair の transitive)。
# 末尾 "/" 境界により prefix 誤爆 (ghostty/config が ghostty/config-backup を誤カバー) を防ぐ。
symlink_target_covered() {
    local file="$1"
    shift
    local source
    for source in "$@"; do
        # file 自身 (file pair) か source/ 配下 (dir pair) を 1 パターンで判定する
        case "$file" in "$source"|"$source"/*) return 0 ;; esac
    done
    return 1
}

# 引数の pair 群 (SYMLINK_PAIRS) のうち, home/ 配下の tracked ファイルで
# どの pair source にもカバーされないものを列挙する。missing_symlink_sources と同じく
# pairs を明示 vararg で受け取り, 依存を呼び出し側に可視化する (global を暗黙参照しない)。
# git ls-files は tracked のみ返すため apm 生成物 (ignore 済み) は自動的に除外される。
uncovered_symlink_targets() {
    local -a sources=()
    local pair file
    for pair in "$@"; do
        sources+=("${pair%%|*}")
    done
    while IFS= read -r file; do
        symlink_target_covered "$file" "${sources[@]}" || echo "$file"
    done < <(git -C "$REPO_ROOT" ls-files 'home/')
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
    refute_contains "$out" ".zshrc"
    # 欠落 source は検出する（false negative を防ぐ）
    assert_contains "$out" "__does_not_exist__"
}

@test "symlink_target_covered: covers exact and dir-descendant, rejects uncovered and prefix collisions" {
    # 粒度混在の吸収を pin する。file pair は exact 一致、dir pair は配下 (transitive) でカバー。
    local -a srcs=("home/.config/nvim" "home/.config/ghostty/config")
    # 自身が source (file pair) → covered
    symlink_target_covered "home/.config/ghostty/config" "${srcs[@]}"
    # dir pair の配下 (transitive) → covered
    symlink_target_covered "home/.config/nvim/lua/init.lua" "${srcs[@]}"
    # どの source にも属さない → uncovered (false negative を防ぐ negative case)
    run symlink_target_covered "home/.config/herdr/resources/left-arrow.svg" "${srcs[@]}"
    [ "$status" -ne 0 ]
    # prefix 誤爆を防ぐ: config-backup は ghostty/config の配下ではない (末尾 / 境界)
    run symlink_target_covered "home/.config/ghostty/config-backup" "${srcs[@]}"
    [ "$status" -ne 0 ]
}

@test "SYMLINK_PAIRS: every managed home/ file is covered (reverse drift)" {
    # home/X は ~/X を mirror する規約で、home/ 配下は allowlist を除き全て symlink 対象。
    # 未カバー集合が allowlist と一致しない = 新 config の配線し忘れ (未カバー増) か
    # stale allowlist (pair 追加後の消し忘れ) を意味する drift。
    load_symlink_pairs
    # 空配列 (slice 破綻) での vacuous pass を防ぐ negative guard
    [ "${#SYMLINK_PAIRS[@]}" -gt 0 ]

    # home/ 配下だが意図的に symlink しないファイルの allowlist (canonical)。各行に理由を書く。
    local -a unmanaged=(
        "home/.gitignore"                              # home/ サブツリーの gitignore (apm 生成物を ignore)
        "home/.gitconfig.private.example"              # private gitconfig のテンプレ (copy_if_not_exists で配置, symlink 対象外)
        "home/apm.yml"                                 # apm install が bootstrap で読む manifest
        "home/apm.lock.yaml"                           # apm lockfile (deployed_files の真実源)
        "home/.config/herdr/resources/left-arrow.svg"  # cheatsheet .af のデザイン素材 (symlink 不要)
        "home/.config/herdr/resources/right-arrow.svg" # cheatsheet .af のデザイン素材 (symlink 不要)
    )

    local uncovered expected
    uncovered="$(uncovered_symlink_targets "${SYMLINK_PAIRS[@]}" | sort)"
    expected="$(printf '%s\n' "${unmanaged[@]}" | sort)"
    # diff の exit status を verdict と診断の両方に使う (二重比較を避ける)。
    # < は allowlist のみ (stale allowlist), > は未カバー (配線し忘れ)。どちらの方向も FAIL する。
    if ! diff <(echo "$expected") <(echo "$uncovered") >&2; then
        echo "reverse drift 検出 (上記 diff: expected=allowlist vs actual=uncovered)" >&2
        return 1
    fi
}

# =============================================================================
# install_brew_packages tests (Brewfile ツールの brew bundle)
# =============================================================================

@test "install_brew_packages: dry-run short-circuits before the brew guard (previews without brew)" {
    DRY_RUN=true
    local empty_dir="$TEST_HOME/empty-path"
    mkdir -p "$empty_dir"

    PATH="$empty_dir" run install_brew_packages

    [ "$status" -eq 0 ]
    assert_contains "$output" "[DRY-RUN] brew bundle"
    # brew 不在でも dry-run は [DRY-RUN] を出す = DRY_RUN 判定が command -v guard より前 (fresh machine の preview 保証)
    refute_contains "$output" "brew not found"
}

@test "install_brew_packages: warns and skips when brew is not on PATH" {
    DRY_RUN=false
    local empty_dir="$TEST_HOME/empty-path"
    mkdir -p "$empty_dir"

    PATH="$empty_dir" run install_brew_packages

    [ "$status" -eq 0 ]
    assert_contains "$output" "brew not found"
}

@test "install_brew_packages: runs 'brew bundle --file=DOTFILES_DIR/home/.Brewfile'" {
    DRY_RUN=false
    # brew を stub して argv を記録し、唯一の実作業行 (brew bundle --file=...) の引数構築を検証する。
    # 早期 return ガードだけでなく実作業行を通す (setup_precommit_hooks の stub テストと対称)。
    local bin_dir="$TEST_HOME/fake-bin"
    local rec="$TEST_HOME/brew-invocation.txt"
    mkdir -p "$bin_dir"
    cat > "$bin_dir/brew" <<'STUB'
#!/bin/sh
printf '%s\n' "$*" > "$BREW_STUB_REC"
STUB
    chmod +x "$bin_dir/brew"
    export BREW_STUB_REC="$rec"
    DOTFILES_DIR="$TEST_HOME/dotfiles"
    mkdir -p "$DOTFILES_DIR/home"

    PATH="$bin_dir:$PATH" run install_brew_packages

    [ "$status" -eq 0 ]
    assert_contains "$(cat "$rec")" "bundle"
    assert_contains "$(cat "$rec")" "--file=$DOTFILES_DIR/home/.Brewfile"
}

# =============================================================================
# setup_precommit_hooks tests (pre-commit フックの導入)
# =============================================================================

@test "setup_precommit_hooks: dry-run short-circuits before the pre-commit guard (previews without pre-commit)" {
    DRY_RUN=true
    local empty_dir="$TEST_HOME/empty-path"
    mkdir -p "$empty_dir"

    PATH="$empty_dir" run setup_precommit_hooks

    [ "$status" -eq 0 ]
    assert_contains "$output" "[DRY-RUN] pre-commit install"
    # pre-commit 不在でも dry-run は [DRY-RUN] を出す = DRY_RUN 判定が command -v guard より前 (fresh machine の preview 保証)
    refute_contains "$output" "pre-commit not found"
}

@test "setup_precommit_hooks: warns and skips when pre-commit is not on PATH" {
    DRY_RUN=false
    local empty_dir="$TEST_HOME/empty-path"
    mkdir -p "$empty_dir"

    PATH="$empty_dir" run setup_precommit_hooks

    [ "$status" -eq 0 ]
    assert_contains "$output" "pre-commit not found"
}

@test "setup_precommit_hooks: runs 'pre-commit install' with cwd = DOTFILES_DIR" {
    DRY_RUN=false
    # pre-commit を stub して cwd と引数を記録し、唯一の実作業行 (cd DOTFILES_DIR && pre-commit install) を検証する。
    # 早期 return ガードだけでなく実作業行を通す（shell-out の cd 先・引数をユニットで担保する）。
    local bin_dir="$TEST_HOME/fake-bin"
    local rec="$TEST_HOME/precommit-invocation.txt"
    mkdir -p "$bin_dir"
    cat > "$bin_dir/pre-commit" <<'STUB'
#!/bin/sh
pwd -P > "$PRECOMMIT_STUB_REC"
printf '%s\n' "$*" >> "$PRECOMMIT_STUB_REC"
STUB
    chmod +x "$bin_dir/pre-commit"
    export PRECOMMIT_STUB_REC="$rec"
    DOTFILES_DIR="$TEST_HOME/dotfiles"
    mkdir -p "$DOTFILES_DIR"

    PATH="$bin_dir:$PATH" run setup_precommit_hooks

    [ "$status" -eq 0 ]
    # symlink 差を排すため両辺 pwd -P で比較する
    local expected_cwd
    expected_cwd="$(cd "$DOTFILES_DIR" && pwd -P)"
    [ "$(sed -n '1p' "$rec")" = "$expected_cwd" ]
    assert_contains "$(sed -n '2p' "$rec")" "install"
}

# =============================================================================
# main() のツール/サービス gating テスト (--dotfiles-only の境界)
# =============================================================================
# gating は main() の配線 (どのブロックで呼ぶか) であり個別関数の unit では pin できない。
# dry-run で全体を subprocess 実行し、--dotfiles-only 有無でマーカーの有無を検証する。

@test "main: full dry-run installs Brewfile packages, pre-commit hooks, and the LaunchAgent" {
    run bash "$BOOTSTRAP_SCRIPT" --dry-run

    [ "$status" -eq 0 ]
    assert_contains "$output" "[DRY-RUN] brew bundle"
    assert_contains "$output" "[DRY-RUN] pre-commit install"
    assert_contains "$output" "com.hidari.node-security-notifier"
}

@test "main: --dotfiles-only dry-run skips Brewfile packages, pre-commit hooks, and the LaunchAgent" {
    run bash "$BOOTSTRAP_SCRIPT" --dry-run --dotfiles-only

    [ "$status" -eq 0 ]
    # ツール/サービス系は非 --dotfiles-only ブロックに gate されている
    refute_contains "$output" "[DRY-RUN] brew bundle"
    refute_contains "$output" "[DRY-RUN] pre-commit install"
    refute_contains "$output" "com.hidari.node-security-notifier"
    # dotfiles 本体 (symlink) は走る (gate の positive 対照。vacuous な全 skip でないことを担保)
    assert_contains "$output" "[DRY-RUN] ln -sf"
}

@test "main: confirm prompt discloses the LaunchAgent before install" {
    # 非 dry-run で prompt を表示させ n で cancel する。cancel は install ブロック (prompt の後) より
    # 前に exit 0 するため実インストールには到達しない。prompt が LaunchAgent 導入を開示することを pin する。
    run bash "$BOOTSTRAP_SCRIPT" <<< "n"

    [ "$status" -eq 0 ]
    assert_contains "$output" "Setup cancelled"
    assert_contains "$output" "com.hidari.node-security-notifier"
}
