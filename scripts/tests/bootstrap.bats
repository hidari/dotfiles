#!/usr/bin/env bats
# =============================================================================
# bootstrap.sh テスト
# =============================================================================

load test_helper

# run --separate-stderr (stdout と stderr を分けて観測する) に必要。
# 宣言しないと bats が BW02 警告を出す。CI は v1.13.0 を pin している。
bats_require_minimum_version 1.5.0

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
    # "dry" / "Dry" 表記は存在しない。
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
# install_apm_packages tests (apm.yml が宣言する skill と plugin の実体化)
# =============================================================================

@test "install_apm_packages: dry-run shows apm install without executing" {
    DRY_RUN=true

    run install_apm_packages

    [ "$status" -eq 0 ]
    assert_contains "$output" "[DRY-RUN] apm install"
    # dry-run は早期 return するため apm 存在チェックまで進まない（early-return を担保する negative）
    refute_contains "$output" "apm not found"
}

@test "install_apm_packages: warns and skips when apm is not on PATH" {
    DRY_RUN=false
    local empty_dir="$TEST_HOME/empty-path"
    mkdir -p "$empty_dir"

    PATH="$empty_dir" run install_apm_packages

    [ "$status" -eq 0 ]
    assert_contains "$output" "apm not found"
}

@test "install_apm_packages: runs 'apm install --frozen' with cwd = DOTFILES_DIR/home" {
    DRY_RUN=false
    # apm を stub して呼び出し時の cwd と引数を記録し、実作業行 (cd home && apm install --frozen) を検証する。
    # 早期 return ガードだけでなく唯一の実作業行を通す（shell-out の cd 先・flag はユニットで担保する）。
    local rec
    setup_fake_apm
    rec="$APM_STUB_REC"
    DOTFILES_DIR="$TEST_HOME/dotfiles"
    mkdir -p "$DOTFILES_DIR/home"

    PATH="$FAKE_BIN:$PATH" run install_apm_packages

    [ "$status" -eq 0 ]
    # symlink 差を排すため両辺 pwd -P で比較する
    local expected_cwd
    expected_cwd="$(cd "$DOTFILES_DIR/home" && pwd -P)"
    [ "$(sed -n '1p' "$rec")" = "$expected_cwd" ]
    assert_contains "$(sed -n '2p' "$rec")" "install"
    assert_contains "$(sed -n '2p' "$rec")" "--frozen"
}

# =============================================================================
# apm install ガード tests (未コミット変更の列挙と、それを受けた中止)
# =============================================================================

# コミットを 1 つ持つテスト用リポジトリを作る。
# setup_test_repo はコミットを作らないが、status --porcelain の比較には
# 「追跡されている既存ファイル」が要るのでここで用意する。
init_committed_repo() {
    local repo="$1"
    setup_test_repo "$repo"
    echo hello > "$repo/a.txt"
    git -C "$repo" add a.txt
    git -C "$repo" commit -qm init
}

@test "apm_install_blockers: a clean tree yields no blockers" {
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"

    run apm_install_blockers "$repo"

    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "apm_install_blockers: a modified tracked file is a blocker" {
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"
    echo changed > "$repo/a.txt"

    run apm_install_blockers "$repo"

    [ "$status" -eq 0 ]
    assert_contains "$output" "a.txt"
}

@test "apm_install_blockers: an untracked file is a blocker" {
    # untracked は git から戻せないので、apm が deploy 先で消したときに復旧できない
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"
    echo new > "$repo/untracked.txt"

    run apm_install_blockers "$repo"

    [ "$status" -eq 0 ]
    assert_contains "$output" "untracked.txt"
}

@test "apm_install_blockers: the apm manifest and lockfile are allowed" {
    # apm install の入出力なので、これらだけが変更されている状態は正常な中間状態。
    # 例外が無いと pin 更新のたびにガードが自分の手順をブロックする
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"
    mkdir -p "$repo/home"
    echo "name: x" > "$repo/home/apm.yml"
    echo "v: 1" > "$repo/home/apm.lock.yaml"
    git -C "$repo" add home/apm.yml home/apm.lock.yaml
    git -C "$repo" commit -qm manifest
    echo "name: y" > "$repo/home/apm.yml"
    echo "v: 2" > "$repo/home/apm.lock.yaml"

    run apm_install_blockers "$repo"

    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "apm_install_blockers: a path with spaces stays a single entry" {
    # 空白で分割すると 1 件が 2 件に化け、落ちた分は「短い正常な結果」として返るので
    # 出力を見ても気づけない。NUL 区切りで受けていることを件数で確かめる
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"
    echo x > "$repo/has space.txt"

    run apm_install_blockers "$repo"

    [ "$status" -eq 0 ]
    assert_contains "$output" "has space.txt"
    [ "$(printf '%s\n' "$output" | grep -c .)" -eq 1 ]
}

@test "apm_install_blockers: a non-ASCII path stays a single entry" {
    # 日本語を含むパスも空白分割と同じ理由で分断されうる (git は既定でクォート表記にする)
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"
    echo x > "$repo/日本語ファイル.txt"

    run apm_install_blockers "$repo"

    [ "$status" -eq 0 ]
    [ "$(printf '%s\n' "$output" | grep -c .)" -eq 1 ]
    refute_contains "$output" '\\'
}

@test "apm_install_blockers: a directory that is not a git repo yields no blockers" {
    # git が無ければ「git から戻す」前提そのものが無いので、ガードの守備範囲外
    local plain="$TEST_HOME/plain"
    mkdir -p "$plain"

    run apm_install_blockers "$plain"

    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "apm_install_blockers: a rename is one blocker with an intact path" {
    # rename と copy だけ porcelain -z が "XY <to>\0<from>\0" の 2 チャンクを返す。
    # from 側は状態フィールドを持たないため、一律に 3 文字削ると実在しないパスが
    # 診断へ並び件数も水増しされる
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"
    git -C "$repo" mv a.txt renamed.txt

    run apm_install_blockers "$repo"

    [ "$status" -eq 0 ]
    [ "$output" = "renamed.txt" ]
}

@test "apm_install_blockers: a rename into the manifest still counts its source" {
    # 移動先が許可対象でも移動元が違えば、それは失われうる変更
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"
    mkdir -p "$repo/home"
    git -C "$repo" mv a.txt home/apm.yml

    run apm_install_blockers "$repo"

    [ "$status" -eq 0 ]
    [ "$output" = "home/apm.yml" ]
}

@test "apm_install_blockers: a git failure is not reported as a clean tree" {
    # status の失敗を空出力へ潰すと clean と区別できず、bootstrap が無防備に
    # apm install を走らせる。新規マシンは git が壊れやすい環境なので、
    # 「検査できなかった」は「検査対象外」と別に扱う
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"
    setup_failing_git_status

    PATH="$FAKE_BIN:$PATH" run apm_install_blockers "$repo"

    [ "$status" -eq 1 ]
}

@test "install_apm_packages: refuses to run when the tree is dirty" {
    DRY_RUN=false
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"
    mkdir -p "$repo/home"
    echo changed > "$repo/a.txt"

    # apm が呼ばれたら記録を残す stub。ガードが効いていれば記録は残らない
    setup_fake_apm
    DOTFILES_DIR="$repo"

    PATH="$FAKE_BIN:$PATH" run install_apm_packages

    [ "$status" -ne 0 ]
    assert_contains "$output" "a.txt"
    [ ! -e "$APM_STUB_REC" ]
}

@test "install_apm_packages: refuses to run when the tree cannot be inspected" {
    # apm_install_blockers が「検査できなかった」を返しても、呼び出し元が受けなければ
    # 空の blockers として通ってしまう。検査機構の取り付け側を見る
    DRY_RUN=false
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"
    mkdir -p "$repo/home"

    setup_fake_apm
    setup_failing_git_status
    DOTFILES_DIR="$repo"

    PATH="$FAKE_BIN:$PATH" run install_apm_packages

    [ "$status" -ne 0 ]
    [ ! -e "$APM_STUB_REC" ]
}

@test "install_apm_packages: runs when the tree is clean" {
    # 上の negative 対照。ガードが常に止めるだけの実装になっていないことを担保する
    DRY_RUN=false
    local repo="$TEST_HOME/repo"
    init_committed_repo "$repo"
    mkdir -p "$repo/home"

    setup_fake_apm
    DOTFILES_DIR="$repo"

    PATH="$FAKE_BIN:$PATH" run install_apm_packages

    [ "$status" -eq 0 ]
    [ -e "$APM_STUB_REC" ]
}

# =============================================================================
# claude_config_dirs / claude_extra_config_dirs tests (設定ディレクトリ一覧の読み込み)
# =============================================================================
#
# 一覧は追跡外の $HOME/.config/dotfiles/claude-config-dirs から読む。追加の
# ディレクトリ名を PUBLIC リポジトリへ書かないための外部化なので、テストは
# ダミー名 (.claude-alpha 等) だけを使う。実名をここへ書いてはならない。

# 設定ファイルをテスト用ホームへ書く (1 引数 1 行)。既定の読み先が $HOME 配下を
# 指すことも暗黙に検証される (TEST_HOME 以外を指すと読まれずテストが赤くなる)。
write_config_dirs_file() {
    mkdir -p "$TEST_HOME/.config/dotfiles"
    printf '%s\n' "$@" > "$TEST_HOME/.config/dotfiles/claude-config-dirs"
}

@test "claude_config_dirs: returns only the default when the config file is absent" {
    run claude_config_dirs

    [ "$status" -eq 0 ]
    [ "$output" = ".claude" ]
}

@test "claude_config_dirs: returns the default plus each configured dir in file order" {
    write_config_dirs_file '.claude-alpha' '.claude-beta'

    run claude_config_dirs

    [ "$status" -eq 0 ]
    [ "${#lines[@]}" -eq 3 ]
    [ "${lines[0]}" = ".claude" ]
    [ "${lines[1]}" = ".claude-alpha" ]
    [ "${lines[2]}" = ".claude-beta" ]
}

@test "claude_config_dirs: an empty config file yields only the default" {
    mkdir -p "$TEST_HOME/.config/dotfiles"
    : > "$TEST_HOME/.config/dotfiles/claude-config-dirs"

    run claude_config_dirs

    [ "$status" -eq 0 ]
    [ "$output" = ".claude" ]
}

@test "claude_config_dirs: reads a final line that lacks a trailing newline" {
    # 手で編集した設定ファイルは末尾改行を欠きやすい。read だけで回すと最終行が
    # 静かに落ち、そのディレクトリだけ配線されない
    mkdir -p "$TEST_HOME/.config/dotfiles"
    printf '.claude-alpha' > "$TEST_HOME/.config/dotfiles/claude-config-dirs"

    run claude_config_dirs

    [ "$status" -eq 0 ]
    [ "${#lines[@]}" -eq 2 ]
    [ "${lines[1]}" = ".claude-alpha" ]
}

@test "claude_config_dirs: skips comments and blank lines" {
    write_config_dirs_file '# comment line' '' '.claude-alpha'

    run claude_config_dirs

    [ "$status" -eq 0 ]
    [ "${#lines[@]}" -eq 2 ]
    [ "${lines[1]}" = ".claude-alpha" ]
}

@test "claude_config_dirs: rejects entries that are not plain dot-prefixed names" {
    # 行の内容はパス組み立てに流れるため、charset を通らない行は受け入れない
    # (../ による脱出やコマンド区切り文字の混入を防ぐ)。".." だけは charset を
    # 通りながら $HOME を脱出するため個別に落とす
    write_config_dirs_file '.claude-ok' '../escape' '.claude;rm -rf /' 'noleadingdot' '..'

    # 既定の run は stderr を $output へ併合する。warn が却下行を verbatim に出すため、
    # 併合したままでは「却下行が返り値に混ざっていない」ことを検査できない
    run --separate-stderr claude_config_dirs

    [ "$status" -eq 0 ]
    [ "${#lines[@]}" -eq 2 ]
    [ "${lines[0]}" = ".claude" ]
    [ "${lines[1]}" = ".claude-ok" ]
    # 却下したことが利用者へ届くことも検査する。黙って捨てると設定の typo に気づけない
    assert_contains "$stderr" "../escape"
    assert_contains "$stderr" ".claude;rm -rf /"
    assert_contains "$stderr" "noleadingdot"
}

@test "claude_config_dirs: skips the default if it is also listed (no duplicates)" {
    # 重複を返すと pair の生成は冪等でも、一覧の件数を数える利用側が静かに狂う
    write_config_dirs_file '.claude' '.claude-alpha'

    run claude_config_dirs

    [ "$status" -eq 0 ]
    [ "${#lines[@]}" -eq 2 ]
    [ "$(printf '%s\n' "$output" | grep -c '^\.claude$')" -eq 1 ]
}

@test "claude_extra_config_dirs: omits the default and yields nothing when unconfigured" {
    run claude_extra_config_dirs

    [ "$status" -eq 0 ]
    [ -z "$output" ]

    # 対照: 設定があれば追加分だけを返す (上の空が「読んでいない」ではないことの確認)
    write_config_dirs_file '.claude-alpha'
    run claude_extra_config_dirs
    [ "$status" -eq 0 ]
    [ "$output" = ".claude-alpha" ]
}

# =============================================================================
# claude_mirrored_target / claude_mirror_pairs tests (追加ディレクトリ向け pair の導出)
# =============================================================================

@test "claude_mirrored_target: mirrors .claude/ targets except the intentionally unmirrored set" {
    # 両方向を検証する (常に真/常に偽の実装を通さない)
    claude_mirrored_target ".claude/settings.json"
    claude_mirrored_target ".claude/some-new-shared-file"

    run claude_mirrored_target ".claude/hooks"
    [ "$status" -ne 0 ]
    run claude_mirrored_target ".claude/statusline-command.sh"
    [ "$status" -ne 0 ]
    run claude_mirrored_target ".claude/.mcp.json"
    [ "$status" -ne 0 ]
    # .claude/ 配下でない target は対象外
    run claude_mirrored_target ".local/bin/winvm"
    [ "$status" -ne 0 ]
}

@test "claude_mirror_pairs: rewrites the target prefix and preserves the source" {
    # source を元 pair から引き継ぐことが共有の規約 (実体が分かれた瞬間に
    # 2 つの設定ディレクトリの設定が静かに別物になる)。
    # 除外 target と .claude/ 配下でない target は出力に現れない
    run claude_mirror_pairs ".claude-alpha" \
        'home/.claude/a|.claude/a' \
        'home/.claude/hooks|.claude/hooks' \
        'scripts/x|.local/bin/x'

    [ "$status" -eq 0 ]
    [ "$output" = "home/.claude/a|.claude-alpha/a" ]
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
    load_pairs_array SYMLINK_PAIRS
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
    load_pairs_array SYMLINK_PAIRS
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

@test "SYMLINK_PAIRS: shared Claude config is mirrored into a configured extra dir" {
    # 共有ファイルを増やしたとき追加の設定ディレクトリ側の配線を忘れる drift を捕捉する。
    # 散文の注意書きではなくテストで縛る (CLAUDE.md の linter 委譲原則)。
    # mirror は配列に書かず claude_mirror_pairs が生成する (ディレクトリ名をリポジトリへ
    # 書かないため) ので、生成結果を allowlist の補集合と突き合わせる。
    load_pairs_array SYMLINK_PAIRS
    # 空配列 (slice 破綻) での vacuous pass を防ぐ negative guard
    [ "${#SYMLINK_PAIRS[@]}" -gt 0 ]

    # 意図的に 2 本目を張らない target の allowlist (canonical)。各行に理由を書く。
    local -a unmirrored=(
        ".claude/hooks"                  # settings.json が $HOME/.claude/hooks/ を絶対参照し symlink 経由で解決される
        ".claude/statusline-command.sh"  # settings.json が bash ~/.claude/... を絶対参照する
        ".claude/.mcp.json"              # Claude Code が ~/.claude/.mcp.json を読まない
    )

    # 期待値: .claude/ 配下の全 target から allowlist を除いた補集合が、同じ source の
    # まま .claude-alpha/ へ張り替えられる
    local pair source target allow skip expected=""
    for pair in "${SYMLINK_PAIRS[@]}"; do
        source="${pair%%|*}"
        target="${pair##*|}"
        case "$target" in
            .claude/*) ;;
            *) continue ;;
        esac
        skip=0
        for allow in "${unmirrored[@]}"; do
            if [ "$target" = "$allow" ]; then
                skip=1
                break
            fi
        done
        if [ "$skip" -eq 1 ]; then continue; fi
        expected="$expected$source|.claude-alpha/${target#.claude/}"$'\n'
    done
    # 補集合が空なら 1 件も検査していない (vacuous pass の防止)
    [ -n "$expected" ]

    # diff の exit status を verdict と診断の両方に使う。
    # < は生成漏れ (allowlist に無いのに張られない), > は phantom 生成 (allowlist の
    # target まで張る、または source の取り違え)。どちらの方向も FAIL する。
    if ! diff <(printf '%s' "$expected" | sort) <(claude_mirror_pairs ".claude-alpha" "${SYMLINK_PAIRS[@]}" | sort) >&2; then
        echo "追加ディレクトリ配線の drift 検出 (上記 diff: expected=allowlist の補集合 vs actual=生成された mirror)" >&2
        return 1
    fi
}

# =============================================================================
# APM_SYMLINK_PAIRS / setup_apm_symlinks tests
# =============================================================================
#
# SYMLINK_PAIRS とは source の性質が違うので独立に pin する。あちらの source は
# git 管理下で必ず実在するが、こちらは apm install が配置するまで存在しない。
# 配列を分けている理由は bootstrap.sh 側のコメントが持つ。

@test "APM_SYMLINK_PAIRS: every source is an apm deploy path" {
    load_pairs_array APM_SYMLINK_PAIRS
    # 空配列 (slice 破綻) での vacuous pass を防ぐ negative guard
    [ "${#APM_SYMLINK_PAIRS[@]}" -gt 0 ]

    local pair source
    for pair in "${APM_SYMLINK_PAIRS[@]}"; do
        source="${pair%%|*}"
        case "$source" in
            home/.claude/skills|home/.claude/agents|home/.claude/commands|home/.claude/skills/*) ;;
            *) echo "apm deploy パスではない source: $source" >&2; return 1 ;;
        esac
    done
}

@test "APM_SYMLINK_PAIRS: every source is gitignored" {
    # tracked な source をこの配列へ置くと、SYMLINK_PAIRS の「source は checkout に必ず
    # 実在する」不変条件の外で管理されることになり、どちらのテストにも捕まらなくなる。
    # 逆に apm 生成物が ignore されていなければ deploy のたびに tree が汚れる。
    #
    # 検査は実リポジトリではなく home/.gitignore だけを持つ scratch リポジトリで行う。
    # 末尾スラッシュ付きの ignore パターンはディレクトリにのみ一致し、git は実体の有無で
    # ディレクトリかを判定するため、source 自体を実リポジトリへ問い合わせると apm 配置済みの
    # ローカルでだけ緑になり fresh clone (CI) で赤くなる。実体の無い状態を再現したうえで
    # 配下のパスを問い合わせれば、どちらの環境でも同じ判定になる。
    load_pairs_array APM_SYMLINK_PAIRS
    [ "${#APM_SYMLINK_PAIRS[@]}" -gt 0 ]

    local probe="$TEST_HOME/gitignore-probe"
    mkdir -p "$probe/home"
    git -C "$probe" init -q
    cp "$REPO_ROOT/home/.gitignore" "$probe/home/.gitignore"

    local pair source checked=0
    for pair in "${APM_SYMLINK_PAIRS[@]}"; do
        source="${pair%%|*}"
        run git -C "$probe" check-ignore -q "$source/deployed-file"
        [ "$status" -eq 0 ] || { echo "gitignore されていない source: $source" >&2; return 1; }
        checked=$((checked + 1))
    done
    # 検査件数と対象件数の一致を確かめる (途中で数え漏らしていないこと)
    [ "$checked" -eq "${#APM_SYMLINK_PAIRS[@]}" ]

    # 対照。これが無いと check-ignore が常に 0 を返す壊れ方 (パターンの取り違えや
    # probe リポジトリの作成失敗) を「全件 ignore 済み」と読んでしまう
    run git -C "$probe" check-ignore -q "home/.claude/settings.json"
    [ "$status" -ne 0 ]
}

@test "SYMLINK_PAIRS: carries no apm-generated sources" {
    # apm 生成物は checkout に存在しないので、SYMLINK_PAIRS に置くと
    # 「all sources exist in repo」が fresh clone で構造的に赤くなる。
    # 配列の取り違えを、症状 (CI の赤) ではなく原因の側で捕まえる。
    load_pairs_array SYMLINK_PAIRS
    [ "${#SYMLINK_PAIRS[@]}" -gt 0 ]

    local pair source
    for pair in "${SYMLINK_PAIRS[@]}"; do
        source="${pair%%|*}"
        case "$source" in
            home/.claude/skills|home/.claude/skills/*|home/.claude/agents|home/.claude/commands)
                echo "apm 生成物は APM_SYMLINK_PAIRS へ移すこと: $source" >&2; return 1 ;;
        esac
    done
}

@test "APM_SYMLINK_PAIRS: shared Claude config is mirrored into a configured extra dir" {
    # apm 生成物も追加の設定ディレクトリで共有する。SYMLINK_PAIRS 側と同じ導出を使い、
    # allowlist は持たない (.claude/ 配下の全 target に mirror が要る)
    load_pairs_array APM_SYMLINK_PAIRS
    [ "${#APM_SYMLINK_PAIRS[@]}" -gt 0 ]

    local pair source target expected=""
    for pair in "${APM_SYMLINK_PAIRS[@]}"; do
        source="${pair%%|*}"
        target="${pair##*|}"
        case "$target" in
            .claude/*) ;;
            *) continue ;;
        esac
        expected="$expected$source|.claude-alpha/${target#.claude/}"$'\n'
    done
    # .claude/ 配下の target が 1 件も無ければ検査になっていない (vacuous pass の防止)
    [ -n "$expected" ]

    # 全 .claude/ target が同じ source のまま張り替えられること。winvm のような
    # .claude/ 配下でない target が紛れて張られないことも同じ diff が守る
    if ! diff <(printf '%s' "$expected" | sort) <(claude_mirror_pairs ".claude-alpha" "${APM_SYMLINK_PAIRS[@]}" | sort) >&2; then
        echo "追加ディレクトリ配線の drift 検出 (上記 diff: expected=.claude/ 配下の全 target vs actual=生成された mirror)" >&2
        return 1
    fi
}

@test "setup_apm_symlinks: skips pairs whose source does not exist" {
    # apm 未実行や --dotfiles-only では source が無い。create_symlink の ln -sf は
    # source の存在を見ないため、黙って壊れた symlink を張れてしまう
    DOTFILES_DIR="$TEST_HOME/repo"
    APM_SYMLINK_PAIRS=("home/.claude/agents|.claude/agents")

    run setup_apm_symlinks

    [ "$status" -eq 0 ]
    assert_contains "$output" "apm source not found"
    [ ! -L "$TEST_HOME/.claude/agents" ]
    [ ! -e "$TEST_HOME/.claude/agents" ]
}

@test "setup_apm_symlinks: links pairs whose source exists" {
    DOTFILES_DIR="$TEST_HOME/repo"
    APM_SYMLINK_PAIRS=("home/.claude/agents|.claude/agents")
    mkdir -p "$DOTFILES_DIR/home/.claude/agents"

    run setup_apm_symlinks

    [ "$status" -eq 0 ]
    [ -L "$TEST_HOME/.claude/agents" ]
    [ "$(readlink "$TEST_HOME/.claude/agents")" = "$DOTFILES_DIR/home/.claude/agents" ]
}

@test "setup_apm_symlinks: stays idempotent on a second run" {
    DOTFILES_DIR="$TEST_HOME/repo"
    APM_SYMLINK_PAIRS=("home/.claude/agents|.claude/agents")
    mkdir -p "$DOTFILES_DIR/home/.claude/agents"
    setup_apm_symlinks

    run setup_apm_symlinks

    [ "$status" -eq 0 ]
    [ -L "$TEST_HOME/.claude/agents" ]
    [ "$(readlink "$TEST_HOME/.claude/agents")" = "$DOTFILES_DIR/home/.claude/agents" ]
    # 入れ子 (.claude/agents/agents) が作られていないこと
    [ ! -e "$TEST_HOME/.claude/agents/agents" ]
}

@test "setup_apm_symlinks: dry-run mode does not create anything" {
    DOTFILES_DIR="$TEST_HOME/repo"
    APM_SYMLINK_PAIRS=("home/.claude/agents|.claude/agents")
    mkdir -p "$DOTFILES_DIR/home/.claude/agents"
    DRY_RUN=true

    run setup_apm_symlinks

    [ "$status" -eq 0 ]
    assert_contains "$output" "[DRY-RUN] ln -sf"
    [ ! -e "$TEST_HOME/.claude/agents" ]
}

@test "setup_apm_symlinks: links apm sources into each configured extra dir" {
    # 追加ディレクトリ向けの mirror は配列に書かず、この関数が生成して張る。
    # setup_dotfiles 側に置くと apm install より前・--dotfiles-only でも走り、
    # source が無い状態で張ってしまう (source 存在ガードはこの関数だけが持つ)
    DOTFILES_DIR="$TEST_HOME/repo"
    APM_SYMLINK_PAIRS=("home/.claude/agents|.claude/agents")
    mkdir -p "$DOTFILES_DIR/home/.claude/agents"
    write_config_dirs_file '.claude-alpha'

    run setup_apm_symlinks

    [ "$status" -eq 0 ]
    [ -L "$TEST_HOME/.claude-alpha/agents" ]
    [ "$(readlink "$TEST_HOME/.claude-alpha/agents")" = "$DOTFILES_DIR/home/.claude/agents" ]
    # 既定側も従来どおり張られる (mirror 生成が既定側の処理を置き換えていないこと)
    [ -L "$TEST_HOME/.claude/agents" ]
}

@test "setup_apm_symlinks: skips extra-dir mirrors whose source does not exist" {
    # apm 未実行では source が無い。既定側と同じ存在ガードが mirror にも効くこと
    DOTFILES_DIR="$TEST_HOME/repo"
    APM_SYMLINK_PAIRS=("home/.claude/agents|.claude/agents")
    write_config_dirs_file '.claude-alpha'

    run setup_apm_symlinks

    [ "$status" -eq 0 ]
    assert_contains "$output" "apm source not found"
    [ ! -L "$TEST_HOME/.claude-alpha/agents" ]
    [ ! -e "$TEST_HOME/.claude-alpha/agents" ]
}

# =============================================================================
# claude_home_symlink_pairs / setup_home_symlinks tests
# =============================================================================
#
# SYMLINK_PAIRS とは pair の出どころも処理も別なので、独立に pin する。
# 分かれている理由は bootstrap.sh 側のコメントが持つ。

@test "setup_home_symlinks: links the target to the source inside home" {
    mkdir -p "$TEST_HOME/.src/dir"

    run setup_home_symlinks ".src/dir|.dst/dir"

    [ "$status" -eq 0 ]
    [ -L "$TEST_HOME/.dst/dir" ]
    [ "$(readlink "$TEST_HOME/.dst/dir")" = "$TEST_HOME/.src/dir" ]
}

@test "setup_home_symlinks: creates the source instead of leaving a dangling link" {
    # source が無い状態で張ると、リンク先の無い symlink が残り
    # 参照した側が黙って失敗する。source を先に用意することで防ぐ
    [ ! -d "$TEST_HOME/.src/dir" ]

    run setup_home_symlinks ".src/dir|.dst/dir"

    [ "$status" -eq 0 ]
    [ -d "$TEST_HOME/.src/dir" ]
    # -e は symlink を辿るため、壊れたリンクなら偽になる
    [ -e "$TEST_HOME/.dst/dir" ]
}

@test "setup_home_symlinks: stays idempotent on a second run" {
    mkdir -p "$TEST_HOME/.src/dir"
    setup_home_symlinks ".src/dir|.dst/dir"

    run setup_home_symlinks ".src/dir|.dst/dir"

    [ "$status" -eq 0 ]
    [ -L "$TEST_HOME/.dst/dir" ]
    [ "$(readlink "$TEST_HOME/.dst/dir")" = "$TEST_HOME/.src/dir" ]
    # 入れ子 (.dst/dir/dir) が作られていないこと
    [ ! -e "$TEST_HOME/.dst/dir/dir" ]
}

@test "setup_home_symlinks: dry-run mode does not create anything" {
    DRY_RUN=true

    run setup_home_symlinks ".src/dir|.dst/dir"

    [ "$status" -eq 0 ]
    [ ! -e "$TEST_HOME/.dst/dir" ]
    # この関数は source 側も作るため、target だけ見ると副作用を半分見逃す
    [ ! -e "$TEST_HOME/.src/dir" ]
}

@test "setup_home_symlinks: does nothing when no pair is passed" {
    # 追加の設定ディレクトリが 1 件も無い経路。/bin/bash 3.2 + set -u では空配列の
    # "${arr[@]}" 展開が unbound variable で落ちるため、配列ではなく引数 ("$@" は
    # 空でも安全) で受ける形が仕様
    run setup_home_symlinks

    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "claude_home_symlink_pairs: shares the claude task list with each configured extra dir" {
    # 全ての設定ディレクトリが同じタスクリストを読み書きするための配線。
    # 参照先が分かれると同じ ID を指定しても進捗が 2 つに割れる
    write_config_dirs_file '.claude-alpha' '.claude-beta'

    run claude_home_symlink_pairs

    [ "$status" -eq 0 ]
    [ "${#lines[@]}" -eq 2 ]
    [ "${lines[0]}" = ".claude/tasks|.claude-alpha/tasks" ]
    [ "${lines[1]}" = ".claude/tasks|.claude-beta/tasks" ]
}

@test "claude_home_symlink_pairs: yields nothing when no extra dir is configured" {
    # 既定の .claude 単体では共有リンクは張らない (自分自身への共有になる)
    run claude_home_symlink_pairs

    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "claude_home_symlink_pairs: entries are home relative, not repo relative" {
    # リポジトリ相対の記法が混ざると $HOME/home/... のような実在しない場所を指す。
    # しかも source 側は ensure_directory が無条件に作るため、壊れたリンクという
    # 症状すら出ずに bogus なディレクトリが生えて終わる。
    # 取り違えたエントリは必ずリポジトリに実在するパスを名乗るので、それを直接見る
    # (SYMLINK_PAIRS の source が実在することは上のテストが pin している)
    write_config_dirs_file '.claude-alpha'

    local pair source target count=0
    while IFS= read -r pair; do
        source="${pair%%|*}"
        target="${pair##*|}"
        [ -n "$source" ]
        [ -n "$target" ]
        [ "$source" != "$target" ]
        [ ! -e "$REPO_ROOT/$source" ]
        [ ! -e "$REPO_ROOT/$target" ]
        count=$((count + 1))
    done < <(claude_home_symlink_pairs)
    # 生成が空なら 1 件も検査していない (vacuous pass の防止)
    [ "$count" -gt 0 ]
}

@test "load_pairs_array: fails loudly when the array is missing" {
    # 配列名が変わったのに黙って空を source すると、配列を検査するテストが
    # 「1 件も見ていないのに緑」になる
    run load_pairs_array NONEXISTENT_PAIRS

    [ "$status" -ne 0 ]
    assert_contains "$output" "array not found"
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

@test "main: dry-run wires the home-internal symlinks into the flow" {
    # 配列と関数が揃っていてもフローから呼ばれなければ何も起きない。
    # 個々の関数テストは緑のまま dead code になるため、結線そのものを pin する
    write_config_dirs_file '.claude-alpha'

    run bash "$BOOTSTRAP_SCRIPT" --dry-run --dotfiles-only

    [ "$status" -eq 0 ]
    assert_contains "$output" "[DRY-RUN] ln -sf $TEST_HOME/.claude/tasks $TEST_HOME/.claude-alpha/tasks"
}

@test "main: dry-run mirrors shared claude config into a configured extra dir" {
    # 設定ディレクトリ名は追跡外の claude-config-dirs から読む。mirror の生成が
    # setup_dotfiles に結線されていることを subprocess の full chain で pin する
    write_config_dirs_file '.claude-alpha'

    run bash "$BOOTSTRAP_SCRIPT" --dry-run --dotfiles-only

    [ "$status" -eq 0 ]
    assert_contains "$output" "[DRY-RUN] ln -sf $DOTFILES_DIR/home/.claude/settings.json $TEST_HOME/.claude-alpha/settings.json"
    assert_contains "$output" "[DRY-RUN] ln -sf $DOTFILES_DIR/home/.claude/CLAUDE.md $TEST_HOME/.claude-alpha/CLAUDE.md"
    # 意図的に 2 本目を張らない target (死んだ symlink になる) が生成されないこと
    refute_contains "$output" ".claude-alpha/hooks"
    refute_contains "$output" ".claude-alpha/statusline-command.sh"
    refute_contains "$output" ".claude-alpha/.mcp.json"
}

@test "main: dry-run creates no extra-dir links when the config file is absent" {
    # 設定ファイルが無い新規マシンでは既定の .claude だけが対象になる。
    # 追加ディレクトリが空でも exit 0 で完走することも同時に見る
    run bash "$BOOTSTRAP_SCRIPT" --dry-run --dotfiles-only

    [ "$status" -eq 0 ]
    refute_contains "$output" ".claude-alpha"
    # ホーム内共有リンク (tasks) も生成されない
    refute_contains "$output" "$TEST_HOME/.claude/tasks"
}

@test "main: dry-run wires the apm symlinks after the apm install step" {
    # 配列と関数が揃っていてもフローから呼ばれなければ何も起きない。
    # フィクスチャには apm 生成物が無いので skip の警告が出る。これが呼ばれた証拠になる
    # (fresh clone で apm 未実行のときに実機で起きる状態そのもの)。
    run bash "$BOOTSTRAP_SCRIPT" --dry-run

    [ "$status" -eq 0 ]
    assert_contains "$output" "apm source not found"
    # apm install の後に張ることを順序で pin する。先に張ると source が無く全て skip される
    assert_contains_in_order "$output" "[DRY-RUN] apm install --frozen" "apm source not found"
}

@test "main: --dotfiles-only dry-run skips the apm symlinks" {
    # apm 自体が走らない経路では symlink も張らない (dangling を作らないため)。
    # 上のテストの negative 対照で、警告の有無が gate の位置を示す
    run bash "$BOOTSTRAP_SCRIPT" --dry-run --dotfiles-only

    [ "$status" -eq 0 ]
    refute_contains "$output" "apm source not found"
    # gate の positive 対照 (vacuous な全 skip でないことを担保)
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
