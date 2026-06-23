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
    "home/.claude/statusline-command.sh|.claude/statusline-command.sh"
    "home/.claude/CLAUDE.md|.claude/CLAUDE.md"
    "home/.claude/.mcp.json|.claude/.mcp.json"
    "home/.claude/skills|.claude/skills"
    "scripts/backup-tool/backup.sh|.local/bin/backup.sh"
    "scripts/util-tools/small-id-gen/small-id-gen.sh|.local/bin/small-id-gen"
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

    /bin/bash -c "$(curl --proto '=https' --tlsv1.2 -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
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

    curl --proto '=https' --tlsv1.2 -fsSL https://get.volta.sh | bash
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

    curl --proto '=https' --tlsv1.2 -fsSL https://claude.ai/install.sh | bash
}

# =============================================================================
# dotfiles セットアップ関数
# =============================================================================

setup_dotfiles() {
    log "Setting up dotfiles..."

    # 必要なディレクトリを作成
    ensure_directory "$HOME/.config/git"
    ensure_directory "$HOME/.local/bin"

    # シンボリックリンクを作成
    for pair in "${SYMLINK_PAIRS[@]}"; do
        local source="${pair%%|*}"
        local target="${pair##*|}"
        create_symlink "$DOTFILES_DIR/$source" "$HOME/$target"
    done

    # .gitconfig.private をコピー（既存の場合はスキップ）
    if [ -f "$DOTFILES_DIR/home/.gitconfig.private.example" ]; then
        copy_if_not_exists "$DOTFILES_DIR/home/.gitconfig.private.example" "$HOME/.gitconfig.private"
    fi

    log "Dotfiles setup complete!"
}

# =============================================================================
# Claude plugin セットアップ関数
# =============================================================================

# settings.json から marketplace / plugin のインストール対象を抽出する（純粋関数・副作用なし）
# 出力（タブ区切り、marketplace を先に出すことで install より前に登録される）:
#   marketplace<TAB><名前><TAB><source>  ... extraKnownMarketplaces の github(repo)/git(url)/directory(path)
#   plugin<TAB><id>                       ... enabledPlugins のうち値が true のもの
# inline(settings) ソースの marketplace は add 不要なので出力しない
claude_plugin_targets() {
    local settings_file="$1"

    # marketplace: source 種別ごとに add 引数（repo / url / path）を取り出す
    jq -r '
        .extraKnownMarketplaces // {} | to_entries[]
        | .key as $name
        | (.value.source.repo // .value.source.url // .value.source.path) as $arg
        | select($arg != null)
        | "marketplace\t\($name)\t\($arg)"
    ' "$settings_file"

    # plugin: enabled が true のものだけ
    jq -r '
        .enabledPlugins // {} | to_entries[]
        | select(.value == true)
        | "plugin\t\(.key)"
    ' "$settings_file"
}

# settings.json の宣言に従って marketplace を登録し plugin をインストールする
# - claude / jq が無ければ警告してスキップ（bootstrap 全体は止めない）
# - 既に登録済み / インストール済みのものはスキップ（冪等）
# - 個別の失敗は警告に留め best-effort で継続する（set -e 下なので明示的に分岐）
# - extraKnownMarketplaces に無い marketplace（claude-plugins-official 等の組み込み）は
#   claude が既知である前提で install する。未知なら install は best-effort で skip される
setup_claude_plugins() {
    local settings_file="${1:-$DOTFILES_DIR/home/.claude/settings.json}"
    log "Setting up Claude Code plugins..."

    if ! command -v claude &> /dev/null; then
        warn "claude not found; skipping Claude plugin setup"
        return 0
    fi
    if ! command -v jq &> /dev/null; then
        warn "jq not found; skipping Claude plugin setup"
        return 0
    fi
    if [ ! -f "$settings_file" ]; then
        warn "settings.json not found; skipping Claude plugin setup: $settings_file"
        return 0
    fi

    # 既存の marketplace 名 / plugin id を取得（冪等性チェック用。dry-run では不要）
    # --json スキーマは claude 2.1 系で確認済み: marketplace list は .name、plugin list は .id
    local existing_marketplaces="" existing_plugins=""
    if [ "$DRY_RUN" = false ]; then
        existing_marketplaces="$(claude plugin marketplace list --json 2>/dev/null | jq -r '.[].name' 2>/dev/null || true)"
        existing_plugins="$(claude plugin list --json 2>/dev/null | jq -r '.[].id' 2>/dev/null || true)"
    fi

    # claude_plugin_targets の各行を処理（marketplace は plugin より前に出力される）
    local kind name arg
    while IFS=$'\t' read -r kind name arg; do
        # 空行はスキップ（set -e 下で意図を明確にするため if 形式を使う）
        if [ -z "$kind" ]; then continue; fi
        case "$kind" in
            marketplace)
                # name=marketplace 名, arg=add に渡す source
                if [ "$DRY_RUN" = true ]; then
                    echo "[DRY-RUN] claude plugin marketplace add $arg --scope user"
                elif printf '%s\n' "$existing_marketplaces" | grep -qxF "$name"; then
                    log "Marketplace already registered: $name"
                elif claude plugin marketplace add "$arg" --scope user; then
                    log "Registered marketplace: $name ($arg)"
                else
                    warn "Failed to register marketplace (skipped): $name ($arg)"
                fi
                ;;
            plugin)
                # name=plugin id (<plugin>@<marketplace>)
                if [ "$DRY_RUN" = true ]; then
                    echo "[DRY-RUN] claude plugin install $name --scope user"
                elif printf '%s\n' "$existing_plugins" | grep -qxF "$name"; then
                    log "Plugin already installed: $name"
                elif claude plugin install "$name" --scope user; then
                    log "Installed plugin: $name"
                else
                    warn "Failed to install plugin (skipped): $name"
                fi
                ;;
        esac
    done < <(claude_plugin_targets "$settings_file")

    log "Claude plugin setup complete!"
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
            echo "  - Install Claude Code plugins declared in settings.json"
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

    # Claude plugin セットアップ（settings.json symlink 後・claude 導入後に実行する。
    # 先に実行すると claude が ~/.claude/settings.json を生成し setup_dotfiles の symlink と衝突するため）
    if [ "$DOTFILES_ONLY" = false ]; then
        setup_claude_plugins
    fi

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
