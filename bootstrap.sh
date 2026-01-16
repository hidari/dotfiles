#!/bin/bash
# =============================================================================
# dotfiles bootstrap script
# =============================================================================
set -euo pipefail

# =============================================================================
# 設定
# =============================================================================

# スクリプトのディレクトリを取得
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOTFILES_DIR="${DOTFILES_DIR:-$SCRIPT_DIR}"

# デフォルト設定
YES_MODE=false
FORCE_MODE=false
DRY_RUN=false
DOTFILES_ONLY=false
BACKUP_DIR="$HOME/.dotfiles_backup/$(date +%Y%m%d_%H%M%S)"

# シンボリックリンク定義（ソース|ターゲット）
SYMLINK_PAIRS=(
    "home/.Brewfile|.Brewfile"
    "home/.zshrc|.zshrc"
    "home/.gitconfig|.gitconfig"
    "home/.config/git/.gitignore_global|.config/git/.gitignore_global"
    "home/.claude/settings.json|.claude/settings.json"
    "home/.claude/CLAUDE.md|.claude/CLAUDE.md"
    "home/.claude/.mcp.json|.claude/.mcp.json"
    "scripts/backup.sh|.local/bin/backup.sh"
)

# =============================================================================
# ヘルパー関数
# =============================================================================

# ログ出力
log() {
    echo "[INFO] $*"
}

# 警告出力
warn() {
    echo "[WARN] $*" >&2
}

# エラー出力
error() {
    echo "[ERROR] $*" >&2
}

# ディレクトリを作成（冪等）
ensure_directory() {
    local dir="$1"

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] mkdir -p $dir"
        return 0
    fi

    if [ ! -d "$dir" ]; then
        mkdir -p "$dir"
        log "Created directory: $dir"
    fi
}

# ファイルをバックアップ
backup_file() {
    local file="$1"

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] backup $file"
        return 0
    fi

    if [ ! -d "$BACKUP_DIR" ]; then
        mkdir -p "$BACKUP_DIR"
    fi

    # ホームディレクトリからの相対パスを保持してバックアップ
    local relative_path="${file#$HOME/}"
    local backup_path="$BACKUP_DIR/$relative_path"
    local backup_dir
    backup_dir=$(dirname "$backup_path")

    mkdir -p "$backup_dir"
    mv "$file" "$backup_path"
    log "Backed up: $file -> $backup_path"
}

# シンボリックリンクを作成（冪等）
create_symlink() {
    local source="$1"
    local target="$2"

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] ln -sf $source $target"
        return 0
    fi

    # 既にリンクが存在し、正しい場所を指している場合はスキップ
    if [ -L "$target" ] && [ "$(readlink "$target")" = "$source" ]; then
        log "Already linked: $target"
        return 0
    fi

    # 間違ったシンボリックリンクの場合は削除して再作成
    if [ -L "$target" ]; then
        rm "$target"
    # 既存ファイル/ディレクトリの処理
    elif [ -e "$target" ]; then
        if [ "$FORCE_MODE" = true ]; then
            backup_file "$target"
        else
            error "Target exists: $target (use --force to overwrite)"
            return 1
        fi
    fi

    # 親ディレクトリを確保
    ensure_directory "$(dirname "$target")"

    ln -sf "$source" "$target"
    log "Linked: $target -> $source"
}

# ファイルをコピー（既存の場合はスキップ）
copy_if_not_exists() {
    local source="$1"
    local target="$2"

    if [ "$DRY_RUN" = true ]; then
        if [ -e "$target" ]; then
            echo "[DRY-RUN] skip copy (exists): $target"
        else
            echo "[DRY-RUN] cp $source $target"
        fi
        return 0
    fi

    if [ -e "$target" ]; then
        log "Skipped (exists): $target"
        return 0
    fi

    cp "$source" "$target"
    log "Copied: $source -> $target"
}

# skills ディレクトリをリンク
link_skills() {
    local source_dir="$1"
    local target_dir="$2"
    local error_count=0

    if [ ! -d "$source_dir" ]; then
        warn "Skills directory not found: $source_dir"
        return 0
    fi

    for skill in "$source_dir"/*/; do
        if [ -d "$skill" ]; then
            local skill_name
            skill_name=$(basename "$skill")
            if ! create_symlink "${skill%/}" "$target_dir/$skill_name"; then
                ((error_count++))
            fi
        fi
    done

    if [ "$error_count" -gt 0 ]; then
        warn "Failed to link $error_count skill(s)"
        return 1
    fi
}

# 使用方法を表示
usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTIONS]

Options:
  -y, --yes           Skip confirmation prompts
  -f, --force         Force overwrite existing files (with backup)
  -n, --dry-run       Show what would be done without making changes
  --dotfiles-only     Skip tool installation, only setup dotfiles
  -h, --help          Show this help message

Examples:
  $(basename "$0")                  # Interactive mode
  $(basename "$0") -y               # Non-interactive mode
  $(basename "$0") --dotfiles-only  # Only setup dotfiles
  $(basename "$0") -n               # Dry-run mode
EOF
}

# =============================================================================
# ツールインストール関数
# =============================================================================

install_homebrew() {
    log "Installing Homebrew..."
    if command -v brew &> /dev/null; then
        log "Homebrew is already installed. Skipping..."
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] Install Homebrew"
        return 0
    fi

    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
}

install_rust() {
    log "Installing Rust..."
    if command -v rustc &> /dev/null; then
        log "Rust is already installed. Skipping..."
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] Install Rust"
        return 0
    fi

    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
}

install_volta() {
    log "Installing Volta..."
    if command -v volta &> /dev/null; then
        log "Volta is already installed. Skipping..."
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] Install Volta"
        return 0
    fi

    curl https://get.volta.sh | bash
}

install_claude_code() {
    log "Installing Claude Code..."
    if command -v claude &> /dev/null; then
        log "Claude Code is already installed. Skipping..."
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] Install Claude Code"
        return 0
    fi

    curl -fsSL https://claude.ai/install.sh | bash
}

# =============================================================================
# dotfiles セットアップ関数
# =============================================================================

setup_dotfiles() {
    log "Setting up dotfiles..."

    # 必要なディレクトリを作成
    ensure_directory "$HOME/.claude/skills"
    ensure_directory "$HOME/.config/git"
    ensure_directory "$HOME/.local/bin"

    # シンボリックリンクを作成
    for pair in "${SYMLINK_PAIRS[@]}"; do
        local source="${pair%%|*}"
        local target="${pair##*|}"
        create_symlink "$DOTFILES_DIR/$source" "$HOME/$target"
    done

    # skills ディレクトリをリンク
    link_skills "$DOTFILES_DIR/home/.claude/skills" "$HOME/.claude/skills"

    # .gitconfig.private をコピー（既存の場合はスキップ）
    if [ -f "$DOTFILES_DIR/home/.gitconfig.private.example" ]; then
        copy_if_not_exists "$DOTFILES_DIR/home/.gitconfig.private.example" "$HOME/.gitconfig.private"
    fi

    log "Dotfiles setup complete!"
}

# =============================================================================
# メイン処理
# =============================================================================

main() {
    # 引数パース
    while [[ $# -gt 0 ]]; do
        case $1 in
            -y|--yes)
                YES_MODE=true
                shift
                ;;
            -f|--force)
                FORCE_MODE=true
                shift
                ;;
            -n|--dry-run)
                DRY_RUN=true
                shift
                ;;
            --dotfiles-only)
                DOTFILES_ONLY=true
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            *)
                error "Unknown option: $1"
                usage
                exit 1
                ;;
        esac
    done

    # 確認プロンプト
    if [ "$YES_MODE" = false ] && [ "$DRY_RUN" = false ]; then
        echo "This script will:"
        if [ "$DOTFILES_ONLY" = false ]; then
            echo "  - Install Homebrew, Rust, Volta, Claude Code"
        fi
        echo "  - Create symlinks for dotfiles"
        echo ""
        echo -n "Continue? (y/N): "
        read -r REPLY
        echo ""

        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            echo "Setup cancelled."
            exit 0
        fi
    fi

    # ツールインストール
    if [ "$DOTFILES_ONLY" = false ]; then
        install_homebrew
        install_rust
        install_volta
        install_claude_code
    fi

    # dotfiles セットアップ
    setup_dotfiles

    echo ""
    log "Bootstrap complete!"
    if [ "$DRY_RUN" = false ]; then
        echo "Run the following to update your PATH:"
        echo "  source ~/.zshrc"
    fi
}

# スクリプトとして実行された場合のみ main を実行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
