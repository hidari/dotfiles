#!/usr/bin/env bats
# =============================================================================
# .zshrc の補完ブロックが Homebrew の補完を compinit に拾わせるかのテスト
# =============================================================================
#
# compinit は呼ばれた時点の fpath だけを走査する。Homebrew が入れる補完
# (/opt/homebrew/share/zsh/site-functions) を fpath へ足すのが後段の brew shellenv だけだと、
# compinit はそれを見ないまま補完表を作り、brew / gh / op などの補完が黙って効かない。
#
# 補完ブロックだけを切り出し、起動ファイルを読まない zsh -f で評価する。HOME と ZDOTDIR を
# 一時ディレクトリへ向けるのは、手元の ~/.zcompdump を使い回す compinit -C 側へ分岐させず、
# 毎回 fpath を走査させるため。

bats_require_minimum_version 1.5.0

load test_helper

setup() {
    require_command_or_skip zsh || return 1

    COMPLETION_SLICE="$BATS_TEST_TMPDIR/completion.zsh"
    extract_zshrc_block '^# 補完$' "$COMPLETION_SLICE"
    ZDOT="$BATS_TEST_TMPDIR/zdot"
    mkdir -p "$ZDOT"
}

# 補完ブロックを評価してから、渡した zsh の式を評価して出力する。
#
# FPATH は外す。brew shellenv を読んだシェルから走らせると site-functions を含む FPATH を
# 継承し、ブロックが fpath へ足さなくても補完が登録されて緑のまま通る。
#
# ブロックが呼ぶ compinit は、insecure なものを黙って無視する compinit -i へ差し替える。
# fpath やその親に権限のゆるいディレクトリがあると、非対話の compinit は確認を出せずに
# 中断する (GitHub Actions のランナーで実際に起きた)。検査対象はブロックの書き方であって、
# 実行環境のディレクトリの権限ではない。先に定義した関数はブロックの autoload では
# 上書きされないので、ブロックが compinit を呼ばなければ差し替えも走らない。
eval_after_slice() {
    run --separate-stderr env -u FPATH HOME="$ZDOT" ZDOTDIR="$ZDOT" zsh -f -c "
        compinit() { unfunction compinit; autoload -Uz compinit; compinit -i \"\$@\"; }
        source '$COMPLETION_SLICE' || exit 9
        print -r -- $1"
}

# Homebrew の site-functions は macOS の開発機にしか無いので、タグで CI の実行対象から外す
# bats test_tags=uncovered
@test "completion block: compinit registers completions installed by Homebrew" {
    [ -f /opt/homebrew/share/zsh/site-functions/_brew ] \
        || skip_outside_ci "Homebrew の補完が見つからない" || return 1

    eval_after_slice '${_comps[brew]}'

    [ "$status" -eq 0 ]
    [ "$output" = "_brew" ]
}

@test "completion block: evaluating the slice initializes the completion system" {
    # 切り出しが空か compinit を呼ばない形だと、下の起動エラーの検査は何も評価しないまま
    # 緑になる。compdef は compinit を実際に呼んだときだけ定義されるので、それで確かめる
    eval_after_slice '${+functions[compdef]}'

    [ "$status" -eq 0 ]
    if [ "$output" != "1" ]; then
        echo "stderr: $stderr" >&2
        return 1
    fi
}

@test "completion block: a first shell without a compdump starts without errors" {
    # 新しいマシンの最初のシェルには ~/.zcompdump が無い。日付の比較が空の右辺で
    # 壊れると、起動のたびにエラーを出したまま compinit -C 側へ落ちる
    eval_after_slice '${+functions[compdef]}'

    [ "$status" -eq 0 ]
    if [ -n "$stderr" ]; then
        echo "stderr: $stderr" >&2
        return 1
    fi
}
