##################################
# 環境変数

# 言語・文字コード
export LANG=ja_JP.UTF-8

# 履歴ファイルの保存先
export HISTFILE=${HOME}/.zhistory

# メモリに保存される履歴の件数
export HISTSIZE=10000

# 履歴ファイルに保存される履歴の件数
export SAVEHIST=100000

# pyenvの環境
export PYENV_ROOT="$HOME/.pyenv"

# lsの色設定
export LSCOLORS=gxfxcxdxbxegedabagacad
export LS_COLORS='di=34:ln=35:so=32:pi=33:ex=31:bd=46;34:cd=43;34:su=41;30:sg=46;30:tw=42;30:ow=43;30'

# Go言語の設定
export GOPATH="$HOME/.go"

# path配列を使ってパスを通す
path=(
    $path
    $PYENV_ROOT/bin(N-/)
    /usr/local/bin(N-/)
    ./node_modules/.bin(N-/)
    $GOPATH/bin(N-/)
    $HOME/.nodenv/shims(N-/)
)

##################################
# プロンプト

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
compinit

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

alias ls='ls -aG'
alias yarnx='yarn run -s'
alias gitl='git log -15 --graph --date-order --decorate=short --date=iso --format="%C(yellow)%h%C(reset) %C(magenta)[%ad]%C(reset)%C(auto)%d%C(reset) %s %C(cyan)Author:%an%C(reset)"'
alias uug='uuidgen | tr "[:upper:]" "[:lower:]" | tr -d "\n"'

########################################
# その他

# pyenv
eval "$(pyenv init -)"

# nodenv
eval "$(nodenv init -)"

# direnv
#eval "$(direnv hook zsh)"

# PATHの重複をなくすやつ
typeset -U PATH
