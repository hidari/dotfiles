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
    # 追加の Claude 設定ディレクトリ (2 アカウント運用) への mirror はここへ書かず、
    # claude_mirror_pairs が claude-config-dirs から生成する (名前をリポジトリへ書かないため)。
    "scripts/backup-tool/backup|.local/bin/backup"
    "scripts/util-tools/small-id-gen/small-id-gen.sh|.local/bin/small-id-gen"
)

# apm が deploy した成果物を source とするシンボリックリンク定義（ソース|ターゲット）。
# SYMLINK_PAIRS と分けているのは source の性質が違うため。あちらの source は git 管理下で
# 必ず実在する（欠けていればバグ）が、こちらは apm install が配置するまで存在しない。
# fresh clone や --dotfiles-only では実体が無いので、存在するときだけ張る。
# 3 ディレクトリそれぞれの由来は home/.gitignore のコメントが持つ。
# 追加の Claude 設定ディレクトリへの mirror はここへ書かず、claude_mirror_pairs が生成する。
APM_SYMLINK_PAIRS=(
    "home/.claude/skills|.claude/skills"
    "home/.claude/agents|.claude/agents"
    "home/.claude/commands|.claude/commands"
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

# Pester (PowerShell のテストフレームワーク) を導入する（冪等）。
#
# pwsh は Brewfile が入れるが Pester は同梱されないため別に要る。PSGallery から
# 取るので、gitleaks と同じく版を固定して開発機と CI を揃える。固定しないと
# 破壊的変更が入った版が黙って降ってきて、テストの赤が自分の変更由来か
# 判別できなくなる。
install_pester() {
    local pester_version="6.0.1" # CI (.github/workflows/test.yml の pester job) と揃える

    log "Installing Pester (PowerShell test framework)..."

    if ! command -v pwsh &> /dev/null; then
        warn "pwsh not found; skipping Pester installation"
        return 0
    fi

    if pwsh -NoProfile -Command "if (Get-Module -ListAvailable -Name Pester | Where-Object { \$_.Version -eq '$pester_version' }) { exit 0 } else { exit 1 }"; then
        log "Pester $pester_version is already installed. Skipping..."
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] Install Pester $pester_version"
        return 0
    fi

    pwsh -NoProfile -Command "Install-Module Pester -RequiredVersion '$pester_version' -Scope CurrentUser -Force -SkipPublisherCheck -Repository PSGallery"
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

# apm.yml (home/) が宣言する skill と plugin を apm.lock.yaml の pin 通りに実体化する（冪等）。
# apm は cwd の apm.yml/apm.lock.yaml を基準に展開先を決めるため、必ず home/ で実行する。
# 展開先は APM_SYMLINK_PAIRS の source と同じ 3 ディレクトリで、由来は home/.gitignore の
# コメントが持つ。
install_apm_packages() {
    log "Installing apm-managed skills and plugins..."

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] apm install --frozen (in $DOTFILES_DIR/home)"
        return 0
    fi

    if ! command -v apm &> /dev/null; then
        warn "apm not found; skipping apm-managed package installation"
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
# 追加の Claude 設定ディレクトリ
# =============================================================================

# 追加の Claude 設定ディレクトリ一覧の読み先。1 行 1 ディレクトリ名 (ドット付き)。
# ディレクトリ名をこの PUBLIC リポジトリへ書かないための外部化で、増えたら行を
# 足すだけでリポジトリ側の変更は要らない。
# この代入を設定変数の並び (冒頭) ではなくヘルパー関数マーカーより下へ置くのは、
# テストの load_bootstrap_functions がマーカー間だけを切り出して source するため。
CLAUDE_CONFIG_DIRS_FILE="${CLAUDE_CONFIG_DIRS_FILE:-$HOME/.config/dotfiles/claude-config-dirs}"

# 設定ファイルの 1 行を分類する。0 = 有効、1 = 無視 (空行・コメント・既定ディレクトリ)、
# 2 = 却下 (文法違反)。行を吐く側と警告する側が同じ述語を使うことで、文法が二重管理に
# ならない。文法の canonical はここ 1 箇所で、home/.zshrc 側との一致は parity テストが守る。
# 戻り値を読む側は set -e に注意すること。単独で呼ぶと 1 や 2 でスクリプトごと終了する。
claude_config_dir_line_kind() {
    case "$1" in
        '' | '#'* | '.claude') return 1 ;;
    esac
    if [ "$1" != "${1%-dev}" ] \
        || ! printf '%s' "$1" | grep -Eq '^\.claude-[A-Za-z0-9._-]+$'; then
        return 2
    fi
    return 0
}

# 追加の Claude 設定ディレクトリ (既定の .claude を除く) を 1 行 1 件で出力する。
# 各行は $HOME 直下のディレクトリ名そのものとして扱い、symlink の target へ無変換で使う
# (ドット無し記法にするとドットを再付与する第 2 の規約が生まれて drift する)。
#
# 受け入れるのは .claude- で始まる名前だけ。charset に "/" が無く先頭が .claude- に
# 固定されるので、行が $HOME の外や既存の意味を持つドットディレクトリ (.git 等) を
# 指すことはない (".." もこの文法を通らないので個別の分岐は要らない)。この前提は
# 「追加ディレクトリが実在するか」の検査が使う glob (.claude-*) が元から賭けていた
# もので、文法側へ昇格させて 2 つあった「追加ディレクトリとは何か」の定義を揃えた。
#
# 末尾が -dev の名前も落とす。.zshrc が 1 行につき <name> と <name>-dev を対で作る
# ため、-dev を許すと別の行の派生名と衝突して後勝ちで静かに上書きされる。bootstrap は
# 関数を作らないので単独では困らないが、片側だけが受理すると「mirror はあるがランチャ
# が無い」部分状態になるため同じ文法にする (一致は zshrc-claude.bats が pin する)。
claude_extra_config_dirs() {
    [ -f "$CLAUDE_CONFIG_DIRS_FILE" ] || return 0

    # 無視も却下もここでは黙って落とす。却下行の通知は
    # warn_invalid_claude_config_dir_lines が持ち main が 1 回だけ呼ぶ。
    # この関数はプロセス置換から何度も呼ばれるので、ここで警告すると同じ内容が並ぶ
    local line
    while IFS= read -r line || [ -n "$line" ]; do
        claude_config_dir_line_kind "$line" || continue
        printf '%s\n' "$line"
    done < "$CLAUDE_CONFIG_DIRS_FILE"
}

# 却下行を verbatim で stderr へ出す。黙って捨てると設定の typo に気づけない。
# main が 1 回だけ呼ぶ。判定は claude_config_dir_line_kind が canonical で、
# ここは通知だけを持つ。
# 戻り値の受け方に注意。set -e 下では述語を単独で呼ぶと 1 や 2 で即終了するため、
# || で受けて $? を読む
warn_invalid_claude_config_dir_lines() {
    [ -f "$CLAUDE_CONFIG_DIRS_FILE" ] || return 0

    local line kind
    while IFS= read -r line || [ -n "$line" ]; do
        kind=0
        claude_config_dir_line_kind "$line" || kind=$?
        if [ "$kind" -eq 2 ]; then
            warn "設定ディレクトリ名として受け付けられない行を無視します: $line"
        fi
    done < "$CLAUDE_CONFIG_DIRS_FILE"
    return 0
}

# 既定の .claude/ 向け target が追加の設定ディレクトリ側にも要るなら真。
# hooks / statusline-command.sh は settings.json が $HOME/.claude/ 配下を絶対パスで
# 参照して symlink 経由で解決されるため、.mcp.json は Claude Code が読まないため
# 張らない (いずれも 2 本目は死んだ symlink になる)。.claude/ 配下でない target は対象外。
claude_mirrored_target() {
    case "$1" in
        .claude/hooks | .claude/statusline-command.sh | .claude/.mcp.json) return 1 ;;
        .claude/*) return 0 ;;
    esac
    return 1
}

# 既定の .claude/ へ張る pair 列から、追加の設定ディレクトリ dir 向けの pair を導出して
# 1 行 1 pair で出力する。第 1 引数が dir、残りが "source|target" 形式の pair 列。
# source を元 pair から引き継ぐことで全ディレクトリが同じ実体を共有する
# (実体が分かれた瞬間に全設定ディレクトリの設定が静かに別物になる)。
# どの target を張るかの判定は claude_mirrored_target が持つ。
claude_mirror_pairs() {
    local dir="$1"
    shift

    local pair source target
    for pair in "$@"; do
        source="${pair%%|*}"
        target="${pair##*|}"
        if claude_mirrored_target "$target"; then
            printf '%s|%s/%s\n' "$source" "$dir" "${target#.claude/}"
        fi
    done
}

# ホーム内で完結する共有 pair (source|target、どちらも $HOME 相対) を追加の設定
# ディレクトリぶん生成して出力する。SYMLINK_PAIRS 由来の pair とはパスの解決規則が
# 違うだけでなく source の性質が違う。あちらの source は git 管理下で必ず実在する
# （欠けていればバグ）のに対し、こちらの source は未追跡のローカル状態で、無ければ
# setup_home_symlinks が作る。
# タスクリストはアカウントではなくプロジェクトに紐づく作業成果物なので、
# どの設定ディレクトリから起動しても同じ実体を読み書きさせる。
# 同時アクセスは tasks/<id>/.lock があることから処理系が扱う前提と判断した。
# 実体を既定側 (.claude/tasks) に置くのは意図的な非対称。中立な置き場へ移す余地は
# あるが、既存タスクの移行を bootstrap が担わないため今は採らない。
claude_home_symlink_pairs() {
    local dir
    while IFS= read -r dir; do
        printf '%s\n' ".claude/tasks|$dir/tasks"
    done < <(claude_extra_config_dirs)
}

# カテゴリ別に symlink pair (source|target) を 1 行 1 件で出力する単一の生成器。
# 張る側 (setup_dotfiles / setup_apm_symlinks) と数える側 (current_symlink_targets) が
# ここから取ることで、供給カテゴリを足したときの編集箇所が 1 関数へ閉じる。
# カテゴリの分け方の基準は source の性質。repo の source は git 管理下で必ず実在し、
# apm の source は apm install が配置するまで存在せず、home の source は未追跡の
# ローカル状態で無ければ張る側が作る。張る側がこの違いで分岐するため境界をここに合わせた。
# 未知のカテゴリで空を返さないのは、呼び出し側から「対象が 0 件」と区別が付かないため。
symlink_pairs_for() {
    local category="$1"
    local dir

    case "$category" in
        repo)
            printf '%s\n' "${SYMLINK_PAIRS[@]}"
            while IFS= read -r dir; do
                claude_mirror_pairs "$dir" "${SYMLINK_PAIRS[@]}"
            done < <(claude_extra_config_dirs)
            ;;
        apm)
            printf '%s\n' "${APM_SYMLINK_PAIRS[@]}"
            while IFS= read -r dir; do
                claude_mirror_pairs "$dir" "${APM_SYMLINK_PAIRS[@]}"
            done < <(claude_extra_config_dirs)
            ;;
        home)
            claude_home_symlink_pairs
            ;;
        all)
            symlink_pairs_for repo
            symlink_pairs_for apm
            symlink_pairs_for home
            ;;
        *)
            error "Unknown symlink pair category: $category"
            return 1
            ;;
    esac
}

# =============================================================================
# dotfiles セットアップ関数
# =============================================================================

# ホーム内で完結するシンボリックリンクを作成する（冪等）。pair は引数で受け取る。
# 配列を経由しないのは、追加の設定ディレクトリが 1 件も無いとき空になり、
# /bin/bash 3.2 + set -u では空配列の "${arr[@]}" 展開が unbound variable で落ちる
# ため ("$@" は空でも安全に展開できる)。
# source 側が無いまま張るとリンク先の無い symlink が残り、参照した側が黙って失敗するため
# 先に実体を用意する。SYMLINK_PAIRS の source はリポジトリに実在する前提なのでこの手当ては要らない。
setup_home_symlinks() {
    local pair source target
    for pair in "$@"; do
        source="$HOME/${pair%%|*}"
        target="$HOME/${pair##*|}"
        ensure_directory "$source"
        create_symlink "$source" "$target"
    done
}

# apm pair 1 件ぶんの symlink を張る。source が無いときは張らずに警告する。
# create_symlink の ln -sf は source の存在を見ないためリンク先の無い symlink を
# 作れてしまい、参照した側が黙って失敗する。
# setup_home_symlinks と違って source を作らないのは、実体を用意できるのが apm だけだから。
# 空ディレクトリを先に作ると apm 未実行と実行済みが見分けられなくなる。
create_apm_symlink() {
    local pair="$1"
    local source target
    source="$DOTFILES_DIR/${pair%%|*}"
    target="$HOME/${pair##*|}"

    if [ ! -e "$source" ]; then
        warn "apm source not found; skipping symlink: $source"
        return 0
    fi
    create_symlink "$source" "$target"
}

# apm が deploy した成果物へのシンボリックリンクを作成する（冪等）。
# pair は symlink_pairs_for apm から取る (追加の設定ディレクトリ向けの mirror を含む)。
# この張り付けを setup_dotfiles 側へ置かないのは、あちらが install_apm_packages より前かつ
# --dotfiles-only でも走るため。source 存在ガードを持つのはこの関数だけで、
# 先に張ると source が無い状態で symlink を張ってしまう。
setup_apm_symlinks() {
    local pair
    while IFS= read -r pair; do
        create_apm_symlink "$pair"
    done < <(symlink_pairs_for apm)
}

setup_dotfiles() {
    log "Setting up dotfiles..."

    # 必要なディレクトリを作成
    ensure_directory "$HOME/.config/git"
    ensure_directory "$HOME/.config/mise"
    ensure_directory "$HOME/.local/bin"

    # リポジトリを source とする symlink (追加設定ディレクトリ向けの mirror を含む)
    local pair source target
    while IFS= read -r pair; do
        source="$DOTFILES_DIR/${pair%%|*}"
        target="$HOME/${pair##*|}"
        create_symlink "$source" "$target"
    done < <(symlink_pairs_for repo)

    # ホーム内で完結する共有リンク。source が無ければ setup_home_symlinks が作る
    while IFS= read -r pair; do
        setup_home_symlinks "$pair"
    done < <(symlink_pairs_for home)

    # .gitconfig.private をコピー（既存の場合はスキップ）
    if [ -f "$DOTFILES_DIR/home/.gitconfig.private.example" ]; then
        copy_if_not_exists "$DOTFILES_DIR/home/.gitconfig.private.example" "$HOME/.gitconfig.private"
    fi

    log "Dotfiles setup complete!"
}

# bootstrap が管理する symlink の target ($HOME 相対) を 1 行 1 件で出力する。
# 供給は symlink_pairs_for all が持つ。集合を配列の直読みだけで組むと、追加の
# 設定ディレクトリ向けに生成される mirror pair とホーム内共有 pair が漏れ、
# 生きている追加ディレクトリ側のリンクを stale と誤認する。
current_symlink_targets() {
    local pair
    while IFS= read -r pair; do
        printf '%s\n' "${pair##*|}"
    done < <(symlink_pairs_for all)
}

# stdin の target ($HOME 相対) 列から、stale 検出で走査する親ディレクトリを
# 絶対パス・重複無しで出力する。target 自身ではなく親を返すのは、配列から消えた
# pair の残骸はもう集合に無く、位置は「今の target と同じディレクトリ」としか
# 推定できないため。$HOME 全体の再帰走査は巨大なツリー (Library 等) を歩くうえ
# 管理と無縁の場所まで候補に入れてしまうので採らない。
symlink_scan_dirs() {
    local target
    while IFS= read -r target; do
        case "$target" in
            # "$HOME/." のような "." 成分を作らない。走査結果のパスに "." が挟まると
            # $HOME 相対へ戻したとき target 集合と照合できず、生きたリンクを撤去する
            */*) printf '%s\n' "$HOME/${target%/*}" ;;
            *) printf '%s\n' "$HOME" ;;
        esac
    done | sort -u
}

# 配列から消えた pair の残骸 (stale symlink) を backup へ退避する（冪等）。
# bootstrap は過去に張った symlink の記録を持たないため、検出は「リンク先が
# $DOTFILES_DIR 配下 かつ 現在の target 集合に無い」に限定する (ユーザーが
# 手で張った無関係な symlink を殺さないため)。
# 判定は readlink が返すリテラルで行い、[ -e ] のような実体解決に依存する検査を
# 使わない。撤去対象は参照先が既に消えている dangling が典型で、実体解決だと
# まさに撤去すべきリンクが検査を素通りする。
prune_stale_symlinks() {
    # 設定ファイルが未作成のまま走らせると、追加ディレクトリぶんの target が集合から
    # 消える。ただし走査先も同じ集合から導出されるため配下のリンクは訪問すらされず、
    # 生きたリンクの誤撤去は構造的に起きない (symlink_scan_dirs のテストが pin する)。
    # それでも撤去そのものを止めるのは、設定を読めていない状態で「今の集合が正しい」
    # 前提の掃除を続けないため。走査の導出が将来変わったときの第 2 層でもある。
    # 存在検査はグロブを裸で展開せず find で行う (.zshrc の同じ検査と規約を揃える。
    # zsh は nomatch が既定で有効なため不一致の裸グロブがエラーになる)
    if [ ! -f "$CLAUDE_CONFIG_DIRS_FILE" ] \
        && [ -n "$(find "$HOME" -maxdepth 1 -type d -name '.claude-*' -print -quit 2> /dev/null)" ]; then
        warn "追加の設定ディレクトリがありますが設定ファイルが無いため stale symlink の撤去を skip します: $CLAUDE_CONFIG_DIRS_FILE"
        return 0
    fi

    local targets
    targets="$(current_symlink_targets)"

    local scan_dir link dest rel
    while IFS= read -r scan_dir; do
        [ -d "$scan_dir" ] || continue
        # パスは NUL 区切りで受け取る (空白や日本語を含むパスの分断を防ぐ)
        while IFS= read -r -d '' link; do
            dest="$(readlink "$link")" || continue
            case "$dest" in
                "$DOTFILES_DIR"/*) ;;
                *) continue ;;
            esac
            rel="${link#"$HOME"/}"
            if printf '%s\n' "$targets" | grep -qxF "$rel"; then
                continue
            fi
            backup_file "$link"
        done < <(find "$scan_dir" -maxdepth 1 -type l -print0 2> /dev/null)
    done < <(printf '%s\n' "$targets" | symlink_scan_dirs)
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
        install_pester
        install_rust
        install_mise
        install_claude_code
        install_apm
    fi

    # 設定ファイルの却下行をここで 1 回だけ知らせる。以降の読み取りは黙ってフィルタする
    warn_invalid_claude_config_dir_lines

    # dotfiles セットアップ
    setup_dotfiles

    # 配列から消えた pair の残骸を退避する。集合は pair の定義 (配列 + 生成) から
    # 組むので setup との順序に依存しないが、張り終えた状態を最後に整える意図で後置。
    # symlink 管理の一部なので --dotfiles-only でも走る
    prune_stale_symlinks

    # mise の pin ツールと apm スキルを実体化する。
    # mise install は config.toml の symlink 後でなければならない（setup_dotfiles が張る）。
    # setup_apm_symlinks は install_apm_packages の後でなければならない。source は apm が
    # 配置する生成物で、先に張ろうとしても実体が無く全て skip されるため。
    # Claude plugin セットアップも settings.json symlink 後・claude 導入後に実行する
    # （先に実行すると claude が ~/.claude/settings.json を生成し setup_dotfiles の symlink と衝突するため）。
    if [ "$DOTFILES_ONLY" = false ]; then
        install_mise_tools
        install_apm_packages
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
