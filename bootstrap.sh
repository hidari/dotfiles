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
    "home/.config/mise/config.toml|.config/mise/config.toml"
    "home/.config/herdr/config.toml|.config/herdr/config.toml"
    "home/.config/herdr/scripts/herdr-unread|.config/herdr/scripts/herdr-unread"
    "home/.config/herdr/resources/herdr-cheatsheet.af|.config/herdr/resources/herdr-cheatsheet.af"
    "home/.config/herdr/resources/herdr-cheatsheet.png|.config/herdr/resources/herdr-cheatsheet.png"
    "home/.config/herdr/plugins/config/herdr-file-viewer/config.toml|.config/herdr/plugins/config/herdr-file-viewer/config.toml"
    "home/.config/nvim|.config/nvim"
    "home/.config/ghostty/config|.config/ghostty/config"
    "home/.config/raycast/scripts|.config/raycast/scripts"
    "home/.claude/settings.json|.claude/settings.json"
    "home/.claude/statusline-command.sh|.claude/statusline-command.sh"
    "home/.claude/CLAUDE.md|.claude/CLAUDE.md"
    "home/.claude/.mcp.json|.claude/.mcp.json"
    "home/.claude/hooks|.claude/hooks"
    # 2 アカウント運用 (CLAUDE_CONFIG_DIR=~/.claude-hamiltonian) 側へ同じ実体を張る。
    # hooks / statusline-command.sh / .mcp.json は張らない。前 2 つは settings.json が
    # $HOME/.claude/ 配下を絶対パスで参照して symlink 経由で解決されるため、
    # .mcp.json は Claude Code が読まないため (どちらも 2 本目は死んだ symlink になる)。
    "home/.claude/settings.json|.claude-hamiltonian/settings.json"
    "home/.claude/CLAUDE.md|.claude-hamiltonian/CLAUDE.md"
    "scripts/backup-tool/backup|.local/bin/backup"
    "scripts/util-tools/small-id-gen/small-id-gen.sh|.local/bin/small-id-gen"
)

# ホーム内で完結するシンボリックリンク定義（ソース|ターゲット、どちらも $HOME 相対）。
# SYMLINK_PAIRS と分けているのはパスの解決規則が違うからだけではない。あちらの source は
# git 管理下で必ず実在する（欠けていればバグ）のに対し、こちらの source は未追跡の
# ローカル状態で、無ければ作る。この差は共有ループへ per-entry の分岐を入れない限り
# 1 本の配列では表現できないため、記法だけを揃えても統合はできない。
HOME_SYMLINK_PAIRS=(
    # タスクリストはアカウントではなくプロジェクトに紐づく作業成果物なので、
    # どちらのアカウントから起動しても同じ実体を読み書きさせる。
    # 同時アクセスは tasks/<id>/.lock があることから処理系が扱う前提と判断した。
    # 実体を個人側に置くのは意図的な非対称。中立な置き場へ移す余地はあるが、
    # 既存タスクの移行を bootstrap が担わないため今は採らない。
    ".claude/tasks|.claude-hamiltonian/tasks"
)

# apm が deploy した成果物を source とするシンボリックリンク定義（ソース|ターゲット）。
# SYMLINK_PAIRS と分けているのは source の性質が違うため。あちらの source は git 管理下で
# 必ず実在する（欠けていればバグ）が、こちらは apm install が配置するまで存在しない。
# fresh clone や --dotfiles-only では実体が無いので、存在するときだけ張る。
# skills/ は root に SKILL.md を持つパッケージの verbatim コピー、agents/ と commands/ は
# .claude-plugin/ を持つパッケージのフラット分解で生まれる。
APM_SYMLINK_PAIRS=(
    "home/.claude/skills|.claude/skills"
    "home/.claude/agents|.claude/agents"
    "home/.claude/commands|.claude/commands"
    "home/.claude/skills|.claude-hamiltonian/skills"
    "home/.claude/agents|.claude-hamiltonian/agents"
    "home/.claude/commands|.claude-hamiltonian/commands"
    "home/.claude/skills/windows-vm-verification/winvm.py|.local/bin/winvm"
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
    local relative_path="${file#"$HOME"/}"
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

    # インストール直後は brew が現在のシェルの PATH に無いため、以降のステップ(install_mise 等)向けに読み込む
    eval "$(/opt/homebrew/bin/brew shellenv)"
}

# Brewfile が宣言する CLI ツール (pre-commit / gitleaks / shellcheck 等) を実体化する（冪等）。
# Brewfile は brew 依存の single source of truth。--file で repo の実体を直接読むため
# ~/.Brewfile symlink (setup_dotfiles が張る) の順序に依存しない。brew bundle は導入済みを skip する。
install_brew_packages() {
    log "Installing Brewfile packages..."

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] brew bundle --file=$DOTFILES_DIR/home/.Brewfile"
        return 0
    fi

    if ! command -v brew &> /dev/null; then
        warn "brew not found; skipping Brewfile packages"
        return 0
    fi

    brew bundle --file="$DOTFILES_DIR/home/.Brewfile"
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

install_mise() {
    log "Installing mise..."
    if command -v mise &> /dev/null; then
        log "mise is already installed. Skipping..."
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] Install mise"
        return 0
    fi

    brew install mise
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

install_apm() {
    log "Installing apm (Agent Package Manager)..."
    if command -v apm &> /dev/null; then
        log "apm is already installed. Skipping..."
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] Install apm"
        return 0
    fi

    # tap 修飾名 microsoft/apm/apm で入れると microsoft/apm tap を自動 tap して formula apm を導入する
    brew install microsoft/apm/apm
}

# mise が管理する pin ツール (config.toml の [tools] が一覧の真実源) を実体化する（冪等）。
# config.toml の symlink は setup_dotfiles が張るため、必ず setup_dotfiles の後に呼ぶこと。
install_mise_tools() {
    log "Installing mise-managed tools..."

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] mise install"
        return 0
    fi

    if ! command -v mise &> /dev/null; then
        warn "mise not found; skipping mise-managed tool installation"
        return 0
    fi

    # mise install は global config (~/.config/mise/config.toml) の pin を解決し、
    # 既にインストール済みのバージョンはスキップする冪等な操作。
    mise install
}

# apm install を阻む未コミットの変更を列挙する（1 行 1 パス。無ければ何も出さない）。
# apm install は deploy 先を rsync --delete 相当で書き換え、tracked file も黙って上書きし、
# パッケージに含まれないファイルを削除する。しかもログには (files unchanged) と出るため
# 差分に気づけない。ツリーが clean なら apm が何を壊しても git から戻せるので、目的は
# 破壊の防止ではなく復旧可能性の確保になる。この整理から検査範囲は deploy 先ではなく
# リポジトリ全体になる。
# apm.yml と apm.lock.yaml は apm install の入出力であり、これらだけが変更された状態は
# 正常な中間状態なので許可する。例外が無いと pin を更新するたびにガードが手順を止める。
# git リポジトリでなければ「git から戻す」前提そのものが無いので検査しない。
# パスは NUL 区切りで受け取る。空白や日本語を含むパスを空白分割すると分断され、落ちた分は
# 「エラー」ではなく「短い正常な結果」として返るため出力を見ても気づけない。
# 検査できなかったときは 1 を返す。git の失敗を空出力へ潰すと clean と区別できず、
# bootstrap が新規マシン（git が壊れやすい環境）で無防備に apm install を走らせる。

# パスが apm install の入出力なら真。これらだけが変更された状態は正常な中間状態であり、
# 例外が無いと pin を更新するたびにガードが手順を止める。
apm_io_path() {
    case "${1##*/}" in
        apm.yml | apm.lock.yaml) return 0 ;;
    esac
    return 1
}

apm_install_blockers() {
    local repo="$1"
    local entry status path from

    # リポジトリ外は検査対象外。この判定を先に置かないと、下の status 失敗検査が
    # 「リポジトリ外」を「検査できなかった」と取り違える。
    if ! git -C "$repo" rev-parse --show-toplevel > /dev/null 2>&1; then
        return 0
    fi
    # NUL 区切りの出力はコマンド置換では失われる（bash が NUL を捨てる）ためプロセス置換で
    # 読む。その形では git の exit code を受け取れないので、成否だけを別呼び出しで確かめる。
    if ! git -C "$repo" status --porcelain -z > /dev/null 2>&1; then
        return 1
    fi

    while IFS= read -r -d '' entry; do
        # porcelain の各エントリは "XY <path>" 形式。先頭 3 文字が状態フィールド
        status="${entry:0:2}"
        path="${entry:3}"
        from=""
        # rename と copy だけは "XY <to>\0<from>\0" の 2 チャンクで返る。from 側は状態
        # フィールドを持たないので、同じ規則で切ると実在しないパスになる。
        case "$status" in
            *R* | *C*) IFS= read -r -d '' from || from="" ;;
        esac
        # 1 つの記録が指すパスがすべて apm の入出力のときだけ許可する。移動先が apm.yml でも
        # 移動元が違えば、それは失われうる変更である。
        if apm_io_path "$path" && { [ -z "$from" ] || apm_io_path "$from"; }; then
            continue
        fi
        printf '%s\n' "$path"
    done < <(git -C "$repo" status --porcelain -z)
}

# apm.yml (home/) が宣言するスキルを apm.lock.yaml の pin 通りに実体化する（冪等）。
# apm は cwd の apm.yml/apm.lock.yaml を基準に home/.claude/skills へ展開するため、必ず home/ で実行する。
install_apm_skills() {
    log "Installing apm-managed skills..."

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] apm install --frozen (in $DOTFILES_DIR/home)"
        return 0
    fi

    if ! command -v apm &> /dev/null; then
        warn "apm not found; skipping apm-managed skill installation"
        return 0
    fi

    # 未コミットの変更がある状態で走らせると、apm の上書き・削除で復旧不能に失われる。
    # 他の install_* と違い warn + return 0 にしないのは、skip すると skill の供給が
    # 欠けたまま bootstrap が成功したように見えるため。
    local blockers
    if ! blockers="$(apm_install_blockers "$DOTFILES_DIR")"; then
        error "Failed to inspect the working tree; refusing to run apm install"
        return 1
    fi
    if [ -n "$blockers" ]; then
        error "Uncommitted changes found; refusing to run apm install"
        error "apm overwrites deploy targets and deletes files not in the package"
        printf '%s\n' "$blockers" >&2
        error "Commit or stash your work, then re-run bootstrap"
        return 1
    fi

    # --frozen は lockfile 不在/不整合時に install を拒否し、pin されたスキルの再現性を担保する。
    # サブシェルで cd し、呼び出し元の cwd を汚さない。
    ( cd "$DOTFILES_DIR/home" && apm install --frozen )
}

# =============================================================================
# dotfiles セットアップ関数
# =============================================================================

# ホーム内で完結するシンボリックリンクを作成する（冪等）。
# source 側が無いまま張るとリンク先の無い symlink が残り、参照した側が黙って失敗するため
# 先に実体を用意する。SYMLINK_PAIRS の source はリポジトリに実在する前提なのでこの手当ては要らない。
setup_home_symlinks() {
    local pair source target
    for pair in "${HOME_SYMLINK_PAIRS[@]}"; do
        source="$HOME/${pair%%|*}"
        target="$HOME/${pair##*|}"
        ensure_directory "$source"
        create_symlink "$source" "$target"
    done
}

# apm が deploy した成果物へのシンボリックリンクを作成する（冪等）。
# source が無いときは張らずに警告する。create_symlink の ln -sf は source の存在を見ないため
# リンク先の無い symlink を作れてしまい、参照した側が黙って失敗する。
# setup_home_symlinks と違って source を作らないのは、実体を用意できるのが apm だけだから。
# 空ディレクトリを先に作ると apm 未実行と実行済みが見分けられなくなる。
setup_apm_symlinks() {
    local pair source target
    for pair in "${APM_SYMLINK_PAIRS[@]}"; do
        source="$DOTFILES_DIR/${pair%%|*}"
        target="$HOME/${pair##*|}"
        if [ ! -e "$source" ]; then
            warn "apm source not found; skipping symlink: $source"
            continue
        fi
        create_symlink "$source" "$target"
    done
}

setup_dotfiles() {
    log "Setting up dotfiles..."

    # 必要なディレクトリを作成
    ensure_directory "$HOME/.config/git"
    ensure_directory "$HOME/.config/mise"
    ensure_directory "$HOME/.local/bin"

    # シンボリックリンクを作成
    local pair source target
    for pair in "${SYMLINK_PAIRS[@]}"; do
        source="$DOTFILES_DIR/${pair%%|*}"
        target="$HOME/${pair##*|}"
        create_symlink "$source" "$target"
    done

    # ホーム内で完結するリンクを作成
    setup_home_symlinks

    # .gitconfig.private をコピー（既存の場合はスキップ）
    if [ -f "$DOTFILES_DIR/home/.gitconfig.private.example" ]; then
        copy_if_not_exists "$DOTFILES_DIR/home/.gitconfig.private.example" "$HOME/.gitconfig.private"
    fi

    log "Dotfiles setup complete!"
}

# LaunchAgent plist をプレースホルダ置換してレンダリング（冪等）
render_launch_agent_plist() {
    local template="$1"
    local dest="$2"

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] render $template -> $dest"
        return 0
    fi

    ensure_directory "$(dirname "$dest")"
    sed -e "s|__DOTFILES_DIR__|$DOTFILES_DIR|g" -e "s|__HOME__|$HOME|g" "$template" > "$dest"
    log "Rendered LaunchAgent: $dest"
}

# node-security-notifier の LaunchAgent を導入（macOS のみ）
setup_launch_agent() {
    local label="com.hidari.node-security-notifier"
    local template="$DOTFILES_DIR/scripts/node-security-notifier/$label.plist"
    local dest="$HOME/Library/LaunchAgents/$label.plist"

    # DRY_RUN 時は render_launch_agent_plist 内部でガードされ副作用なし。以降の DRY_RUN 判定は launchctl のみを skip する
    render_launch_agent_plist "$template" "$dest"

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] launchctl reload $label"
        return 0
    fi

    if ! command -v launchctl &> /dev/null; then
        warn "launchctl not found; skipping LaunchAgent load"
        return 0
    fi

    local uid
    uid="$(id -u)"
    launchctl bootout "gui/$uid/$label" 2> /dev/null || true
    launchctl bootstrap "gui/$uid" "$dest"
    log "Loaded LaunchAgent: $label"
}

# このリポの pre-commit フックを実体化し commit-time の lint / leak guard を有効化する（冪等）。
# pre-commit は Brewfile 経由で導入済み前提。サブシェルで cd し呼び出し元の cwd を汚さない。
setup_precommit_hooks() {
    log "Installing pre-commit hooks..."

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] pre-commit install (in $DOTFILES_DIR)"
        return 0
    fi

    if ! command -v pre-commit &> /dev/null; then
        warn "pre-commit not found; skipping hook installation"
        return 0
    fi

    ( cd "$DOTFILES_DIR" && pre-commit install )
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
            echo "  - Install Homebrew, Rust, mise, Claude Code, apm"
            echo "  - Install Brewfile CLI tools (pre-commit, gitleaks, shellcheck, etc.)"
            echo "  - Install mise-managed tools"
            echo "  - Install apm-managed skills"
            echo "  - Install Claude Code plugins declared in settings.json"
            echo "  - Enable pre-commit git hooks in this repo"
            echo "  - Install a daily LaunchAgent (com.hidari.node-security-notifier) that polls the Node.js vulnerability feed"
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
        install_brew_packages
        install_rust
        install_mise
        install_claude_code
        install_apm
    fi

    # dotfiles セットアップ
    setup_dotfiles

    # mise の pin ツールと apm スキルを実体化する。
    # mise install は config.toml の symlink 後でなければならない（setup_dotfiles が張る）。
    # setup_apm_symlinks は install_apm_skills の後でなければならない。source は apm が
    # 配置する生成物で、先に張ろうとしても実体が無く全て skip されるため。
    # Claude plugin セットアップも settings.json symlink 後・claude 導入後に実行する
    # （先に実行すると claude が ~/.claude/settings.json を生成し setup_dotfiles の symlink と衝突するため）。
    if [ "$DOTFILES_ONLY" = false ]; then
        install_mise_tools
        install_apm_skills
        setup_apm_symlinks
        setup_claude_plugins
        # LaunchAgent と pre-commit フックはツール/サービス系のため --dotfiles-only では導入しない
        setup_launch_agent
        setup_precommit_hooks
    fi

    echo ""
    log "Bootstrap complete!"
    if [ "$DRY_RUN" = false ]; then
        echo "Run the following to update your PATH:"
        echo "  source ~/.zshrc"
        echo ""
        echo "Manual step: Raycast Script Commands cannot be auto-registered by bootstrap."
        echo "  Add this directory in Raycast Settings > Extensions > Script Commands:"
        echo "    ~/.config/raycast/scripts"
    fi
}

# スクリプトとして実行された場合のみ main を実行
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi
