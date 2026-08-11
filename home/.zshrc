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

# 開発版 (agentic-coding-tools の作業ツリー) のパッケージを --plugin-dir の並びとして
# 集める。既定の起動では skill は apm が配置したコピーを読むが、plugin は同名の
# marketplace 版が優先されるため実際には別経路から載る。経路の canonical は
# claude-plugins の CLAUDE.md にある供給経路の表。開発版は直しながら試すときだけ使う。
# 全アカウントのランチャが同じ並びを使うため構築をここへ閉じる。
# 戻り値では配列を運べないので、呼び出し側が local で宣言した配列へ書き込む。
function _claude_dev_plugin_args() {
  local repo="${AGENTIC_TOOLS_DIR:-$HOME/Develop/agentic-coding-tools}"
  if [ ! -d "$repo" ]; then
    echo "開発版のリポジトリが見つかりません: $repo" >&2
    return 1
  fi

  # 片側だけ欠けても find は残る側を返すので 0 件ガードを素通りし、半分の
  # パッケージで起動する。部分欠落は「短い正常な結果」として返るため、先に両方を検査する
  local base
  for base in "$repo/plugins" "$repo/skills"; do
    if [ ! -d "$base" ]; then
      echo "開発版のパッケージ置き場が見つかりません: $base" >&2
      return 1
    fi
  done

  # パッケージ名を列挙して固定すると増減で drift するため実体から拾う。plugin は
  # 深さ 1、skill はカテゴリを挟んで深さ 2 にあり、plugin 内部の skills/<name>/ は
  # plugin 経由で読まれる。-maxdepth 3 が内部 component を範囲外に落とす
  local -a args
  local skill_md
  while IFS= read -r -d '' skill_md; do
    args+=(--plugin-dir "${skill_md%/SKILL.md}")
  done < <(find "$repo/plugins" "$repo/skills" -maxdepth 3 -name SKILL.md -print0)

  # 0 件のまま起動すると既定の供給元で立ち上がる。開発版のつもりで古い挙動を観測する
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
  local -a _CLAUDE_DEV_PLUGIN_ARGS
  _claude_dev_plugin_args || return 1
  claude "${_CLAUDE_DEV_PLUGIN_ARGS[@]}" "$@"
}

# 追加の Claude 設定ディレクトリ一覧の置き場。1 行 1 ディレクトリ名 (ドット付き)。
# 追加アカウントのディレクトリ名をこの PUBLIC リポジトリへ書かないための外部化。
# bootstrap.sh の同名変数と同じ値でなければならないが、プロセスが別なので共有
# できない。両者が一致することはテスト (zshrc-claude.bats) が pin する。
CLAUDE_CONFIG_DIRS_FILE="${CLAUDE_CONFIG_DIRS_FILE:-$HOME/.config/dotfiles/claude-config-dirs}"

# 追加の設定ディレクトリが $HOME 直下に実在するかを調べる。グロブを裸で展開しない
# のは、zsh の nomatch が既定で有効で不一致のときエラーになるため (bats は bash で
# source し実シェルは zsh なので両方で成立する必要がある)。find は不一致でも exit 0
# を返すので出力の非空で判定する。既定の .claude はパターンに一致しない。
function _claude_extra_config_dir_exists() {
  [ -n "$(find "$HOME" -maxdepth 1 -type d -name '.claude-*' -print -quit 2>/dev/null)" ]
}

# 追加アカウントのランチャを設定ファイルから生成する。生成するのは「既定以外」
# だけで、既定の claude / claude-dev は CLAUDE_CONFIG_DIR を設定しない非対称を保つ
# ため静的定義のまま残す (理由は claude() のコメントを参照)。
# 1 ディレクトリにつき素のランチャ (<name>) と開発版の派生 (<name>-dev) の 2 関数を
# 対で作る。派生は素のランチャを名前で呼ぶので、片方だけ生成すると呼び先を失う。
# 行の検証は bootstrap.sh の claude_extra_config_dirs と同じ規約 (.claude- で始まる
# 英数字・ハイフン・ドット・アンダースコアのみ、末尾 -dev は派生名の予約として却下)。
# 名前空間を .claude- に閉じるのは、この行から作られるのがパスだけでなく関数名でも
# あるため。閉じないと .git のような行から関数 git が生えて外部コマンドを shadow する。
# 生成器は静的定義より後で走るので、衝突した名前は常に生成側が後勝ちする。
# ここでは行が eval に流れるため、検証を通らない行からは定義しない。黙って捨てると
# 設定の typo に気づけないので、却下行は verbatim で stderr へ知らせる。
# 両ファイルの文法が一致することは zshrc-claude.bats の parity テストが pin する。
function _claude_define_launchers() {
  local file="$CLAUDE_CONFIG_DIRS_FILE"
  if [ ! -f "$file" ]; then
    # 設定ファイルだけが無い状態は新規マシンや誤削除で起きる。無言でランチャが
    # 消えると command not found の原因がシェル設定側にあることに気づけないため
    # 知らせる。名前はリポジトリへ戻さないので、警告に具体的なディレクトリ名は
    # 載せない (テストが警告の期待値を持つため、載せると実名が追跡ファイルへ戻る)
    if _claude_extra_config_dir_exists; then
      echo "追加の設定ディレクトリがありますが claude-config-dirs が見つかりません: $file" >&2
    fi
    return 0
  fi

  local line name
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      '' | '#'* | '.claude') continue ;;
    esac
    if [ "$line" != "${line%-dev}" ] \
      || ! printf '%s' "$line" | grep -Eq '^\.claude-[A-Za-z0-9._-]+$'; then
      echo "設定ディレクトリ名として受け付けられない行を無視します: $line" >&2
      continue
    fi
    name="${line#.}"
    # アカウントを固定するのが存在理由なので、外から前置で CLAUDE_CONFIG_DIR が
    # 渡されていても自分のディレクトリを引数で名指しする。空文字のタスクリストを
    # 渡したときの挙動は未確認のため、導出できないときは変数ごと渡さず既定に任せる
    # (claude() と同じ)
    eval "
function ${name}() {
  local config_dir task_list
  config_dir=\"\$(_claude_config_dir \"\$HOME/${line}\")\" || return 1
  task_list=\"\${CLAUDE_CODE_TASK_LIST_ID:-\$(_claude_task_list_id)}\"
  _claude_task_list_notice \"\$config_dir\" \"\$task_list\"
  if [ -n \"\$task_list\" ]; then
    CLAUDE_CONFIG_DIR=\"\$config_dir\" CLAUDE_CODE_TASK_LIST_ID=\"\$task_list\" command claude \"\$@\"
  else
    CLAUDE_CONFIG_DIR=\"\$config_dir\" command claude \"\$@\"
  fi
}

function ${name}-dev() {
  local -a _CLAUDE_DEV_PLUGIN_ARGS
  _claude_dev_plugin_args || return 1
  ${name} \"\${_CLAUDE_DEV_PLUGIN_ARGS[@]}\" \"\$@\"
}
"
  done < "$file"
}

_claude_define_launchers

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
