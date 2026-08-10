##################################
# 環境変数

# 言語・文字コード
export LANG=ja_JP.UTF-8

# 履歴ファイルの保存先
export HISTFILE=${HOME}/.z_history

# メモリに保存される履歴の件数
export HISTSIZE=10000

# 履歴ファイルに保存される履歴の件数
export SAVEHIST=100000

# lsの色設定
export LSCOLORS=gxfxcxdxbxegedabagacad
export LS_COLORS='di=34:ln=35:so=32:pi=33:ex=31:bd=46;34:cd=43;34:su=41;30:sg=46;30:tw=42;30:ow=43;30'

# Homebrewの設定
export HOMEBREW_NO_ENV_HINTS=1

# Go言語の設定
export GOPATH="$HOME/.go"

# pnpmの設定
export PNPM_HOME="$HOME/Library/pnpm"

# Android開発の設定
export ANDROID_HOME="$HOME/Library/Android/sdk"

# path配列を使ってパスを通す
path=(
    /opt/homebrew/bin(N-/)
    $path
    $PNPM_HOME(N-/)
    $HOME/.bun/bin(N-/)
    $HOME/.cargo/bin(N-/)
    $HOME/.cargo/env(N-/)
    $HOME/.moon/bin(N-/)
    $HOME/.local/bin(N-/)
    $GOPATH/bin(N-/)
    $GOROOT/bin(N-/)
    /usr/local/bin(N-/)
    /opt/homebrew/opt/libpq/bin(N-/)
    $ANDROID_HOME/emulator(N-/)
    $ANDROID_HOME/platform-tools(N-/)
    $HOME/Library/Application Support/JetBrains/Toolbox/scripts(N-/)
)

##################################
# プロンプト設定

# 色を使用出来るようにする
autoload -Uz colors
colors

# プロンプトが表示されるたびにプロンプト文字列を評価、置換する
setopt prompt_subst

# gitのステータスを表示
autoload -Uz vcs_info
zstyle ':vcs_info:git:*' check-for-changes true
zstyle ':vcs_info:git:*' stagedstr "%F{magenta}!"
zstyle ':vcs_info:git:*' unstagedstr "%F{yellow}+"
zstyle ':vcs_info:*' formats "%F{087}%c%u[%b]%f"
zstyle ':vcs_info:*' actionformats '[%b|%a]'
precmd () { vcs_info }

# プロンプト表示
PROMPT='%F{141}[%D %*]%f %~ %F{087}$vcs_info_msg_0_%f
%F{081}❯%f '

########################################
# 補完

# 補完機能を有効にする
#for zsh-completions
fpath=(/usr/local/share/zsh-completions $fpath)

autoload -Uz compinit
if [ $(date +'%j') != $(stat -f '%Sm' -t '%j' ~/.zcompdump 2>/dev/null) ]; then
  compinit
else
  compinit -C
fi

zstyle ':completion:*' list-colors 'di=36' 'ln=35' 'so=32' 'ex=31' 'bd=46;34' 'cd=43;34'

# 補完で小文字でも大文字にマッチさせる
zstyle ':completion:*' matcher-list 'm:{a-z}={A-Z}'

# ../ の後は今いるディレクトリを補完しない
zstyle ':completion:*' ignore-parents parent pwd ..

# sudo の後ろでコマンド名を補完する
zstyle ':completion:*:sudo:*' command-path /usr/local/sbin /usr/local/bin \
                    /usr/sbin /usr/bin /sbin /bin /usr/X11R6/bin

# ps コマンドのプロセス名補完
zstyle ':completion:*:processes' command 'ps x -o pid,s,args'

########################################
# オプション

# 日本語ファイル名を表示可能にする
setopt print_eight_bit

# beep を無効にする
setopt no_beep

# フローコントロールを無効にする
setopt no_flow_control

# Ctrl+Dでzshを終了しない
setopt ignore_eof

# '#' 以降をコメントとして扱う
setopt interactive_comments

# ディレクトリ名だけでcdする
setopt auto_cd

# cd したら自動的にpushdする
setopt auto_pushd

# 重複したディレクトリを追加しない
setopt pushd_ignore_dups

# 同時に起動したzshの間でヒストリを共有する
setopt share_history

# 同じコマンドをヒストリに残さない
setopt hist_ignore_all_dups

# スペースから始まるコマンド行はヒストリに残さない
setopt hist_ignore_space

# ヒストリに保存するときに余分なスペースを削除する
setopt hist_reduce_blanks

# 重複を記録しない
setopt hist_ignore_dups

# 高機能なワイルドカード展開を使用する
setopt extended_glob

# globでメタ文字列が含まれるとファイル名と判断される問題の対処
setopt nonomatch

########################################
# エイリアス

# ファイル一覧を表示（隠しファイル含む、色付き）
alias ls='ls -aG'

# Git履歴を見やすく表示（直近15件、グラフ付き）
alias gitl='git log -15 --graph --date-order --decorate=short --date=iso --format="%C(yellow)%h%C(reset) %C(magenta)[%ad]%C(reset)%C(auto)%d%C(reset) %s %C(cyan)Author:%an%C(reset)"'

# UUIDを生成し、小文字に変換してクリップボードにコピー
alias uug='uuidgen | tr "[:upper:]" "[:lower:]" | tr -d "\n" | pbcopy && pbpaste'

# SL（Steam Locomotive）コマンドのオプション付き
alias sl='sl -Falc'

# ディスクの空き容量を確認
alias disk='diskutil info / | grep -E "Free|Available"'

# $PATHを見やすく表示
alias path='echo $PATH | tr ":" "\n" | nl'

# herdr の設定再読み込み
alias herdr-reload='herdr server reload-config'

########################################
# シェル関数

function port-proc() {
  lsof -ti :$1 | xargs ps -p
}

function kill-port() {
  if lsof -ti :$1 > /dev/null; then
    echo "Killing process(es) on port $1"
    lsof -ti :$1 | xargs kill
    echo "Still alive? Run: lsof -ti :$1 | xargs kill -9"
  else
    echo "No process found on port $1"
  fi
}

########################################
# Claude Code 起動

# タスクリスト ID が未知なら知らせる。Claude Code は未知の ID でも黙って新しいリストを
# 作るため、typo は「履歴が分裂している」形でしか後から気づけない。
# 新規作成そのものは正当な操作なのでブロックはしない。
# ID は呼び出し側が解決した値を受け取る。グローバルを直接読むと、導出した ID ではなく
# 前置の値を見てしまい判定がずれる。
function _claude_task_list_notice() {
  local config_dir="$1"
  local task_list_id="$2"
  [ -n "$task_list_id" ] || return 0
  [ -d "$config_dir/tasks/$task_list_id" ] && return 0
  echo "新しいタスクリストを作成します: $task_list_id" >&2
}

# 有効な設定ディレクトリを解決する。引数があればそれを、無ければ前置で渡された
# CLAUDE_CONFIG_DIR を、それも無ければ既定を使う。
# CLAUDE_CONFIG_DIR は存在しないディレクトリを指しても警告されず、その場所に初期状態の
# 設定ディレクトリを作って起動してしまうため、渡す前にここで止める。解決と検査を 1 箇所に
# 閉じることで、片方のランチャだけが検査するという非対称を作らない。
function _claude_config_dir() {
  local config_dir="${1:-${CLAUDE_CONFIG_DIR:-$HOME/.claude}}"
  if [ ! -d "$config_dir" ]; then
    echo "設定ディレクトリが見つかりません: $config_dir" >&2
    return 1
  fi
  printf '%s' "$config_dir"
}

# タスクリスト ID を作業ディレクトリから導出する。git リポジトリならルートの名前、
# そうでなければ cwd の名前。サブディレクトリでもルートに寄せるのは、同じプロジェクトの
# 進捗が割れないため。
# リポジトリ外では pwd -P で実体パスに寄せる。$PWD は symlink 経由で入ったときに
# リンク名を返すため、同じディレクトリなのに経路によって ID が割れる。git 側は
# --show-toplevel が常に実体パスを返すので、揃えないと 2 つの分岐が非対称になる。
# zsh の modifier (${dir:t}) は bats が bash で source すると壊れるので使わない。
function _claude_task_list_id() {
  local dir
  dir="$(git rev-parse --show-toplevel 2>/dev/null)" || dir="$(pwd -P)"
  printf '%s' "${dir##*/}"
}

# 個人アカウント。既定の設定ディレクトリを使うため CLAUDE_CONFIG_DIR は設定しない。
# 明示指定すると Keychain の service 名の導出が変わって再ログインを誘発しうる
# (既定はサフィックス無し、指定時は絶対パスの sha256 先頭 8 桁)。どちらの条件で
# 分岐しているかは未確認なので、未確認の前提に賭けず変数を設定しない。
# ただし外から前置で渡された値は読んで尊重する。確認先を決め打ちにすると、起動する
# アカウントとタスクリストを確認するアカウントがずれて警告が食い違う。
# command claude で関数自身の再帰を避ける。
function claude() {
  local config_dir task_list
  config_dir="$(_claude_config_dir)" || return 1
  task_list="${CLAUDE_CODE_TASK_LIST_ID:-$(_claude_task_list_id)}"
  _claude_task_list_notice "$config_dir" "$task_list"
  # 空文字を渡したときの挙動は未確認。導出できないときは変数ごと渡さず既定に任せる
  if [ -n "$task_list" ]; then
    CLAUDE_CODE_TASK_LIST_ID="$task_list" command claude "$@"
  else
    command claude "$@"
  fi
}

# 仕事アカウント。アカウントを固定するのが存在理由なので、外から前置で
# CLAUDE_CONFIG_DIR が渡されていても自分のディレクトリを引数で名指しする。
function claude-hamiltonian() {
  local config_dir task_list
  config_dir="$(_claude_config_dir "$HOME/.claude-hamiltonian")" || return 1
  task_list="${CLAUDE_CODE_TASK_LIST_ID:-$(_claude_task_list_id)}"
  _claude_task_list_notice "$config_dir" "$task_list"
  # 空文字を渡したときの挙動は未確認。導出できないときは変数ごと渡さず既定に任せる
  if [ -n "$task_list" ]; then
    CLAUDE_CONFIG_DIR="$config_dir" CLAUDE_CODE_TASK_LIST_ID="$task_list" command claude "$@"
  else
    CLAUDE_CONFIG_DIR="$config_dir" command claude "$@"
  fi
}

# 開発版 (agentic-coding-tools の作業ツリー) のパッケージを --plugin-dir の並びとして
# 集める。既定の起動は apm が配置した安定版 (apm.yml の hash 時点のコピー) を読むので、
# 直しながら試すときだけ使う。2 つのアカウントが同じ並びを使うため構築をここへ閉じる。
# 結果を配列で返さずグローバルへ置くのは、コマンド置換が NUL を運べず、改行区切りだと
# 空白や改行を含むパスで壊れるため。
function _claude_dev_plugin_args() {
  local repo="${AGENTIC_TOOLS_DIR:-$HOME/Develop/agentic-coding-tools}"
  if [ ! -d "$repo" ]; then
    echo "開発版のリポジトリが見つかりません: $repo" >&2
    return 1
  fi

  # パッケージ名を列挙して固定すると増減で drift するため実体から拾う。plugin は
  # 深さ 1、skill はカテゴリを挟んで深さ 2 にあり、plugin 内部の skills/<name>/ は
  # plugin 経由で読まれる。-maxdepth 3 が内部 component を範囲外に落とす
  local -a args
  local skill_md
  while IFS= read -r -d '' skill_md; do
    args+=(--plugin-dir "${skill_md%/SKILL.md}")
  done < <(find "$repo/plugins" "$repo/skills" -maxdepth 3 -name SKILL.md -print0 2>/dev/null)

  # 0 件のまま起動すると安定版で立ち上がる。開発版のつもりで古い挙動を観測する
  # ことになるため、静かに間違えるより止める
  if [ "${#args[@]}" -eq 0 ]; then
    echo "開発版のパッケージが見つかりません: $repo" >&2
    return 1
  fi

  _CLAUDE_DEV_PLUGIN_ARGS=("${args[@]}")
}

# 個人アカウントで開発版を読む。設定ディレクトリの検査とタスクリスト通知は
# claude 関数へ委ねる (command claude を直に呼ぶと両方を迂回する)。
function claude-dev() {
  _claude_dev_plugin_args || return 1
  claude "${_CLAUDE_DEV_PLUGIN_ARGS[@]}" "$@"
}

# 仕事アカウントで開発版を読む。アカウントの固定は claude-hamiltonian が持つ。
function claude-hamiltonian-dev() {
  _claude_dev_plugin_args || return 1
  claude-hamiltonian "${_CLAUDE_DEV_PLUGIN_ARGS[@]}" "$@"
}

########################################
# その他

# PATHの重複をなくすやつ
typeset -U PATH

# homebrewのやつ
eval "$(/opt/homebrew/bin/brew shellenv)"

# bun completions
[ -s "$HOME/.bun/_bun" ] && source "$HOME/.bun/_bun"

# miseのやつ
eval "$(mise activate zsh)"

# tirith (ターミナルのセキュリティツール)
# tirith は mise 提供のため mise activate より後に置く。未インストールのマシンで
# command not found を出さないよう、command -v で存在確認してから init する。
command -v tirith >/dev/null 2>&1 && eval "$(tirith init --shell zsh)"
