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

# 補完ブロックを評価したあとの補完表から、コマンド名に対応する補完関数名を返す。
# FPATH は外す。brew shellenv を読んだシェルから走らせると site-functions を含む FPATH を
# 継承し、ブロックが fpath へ足さなくても補完が登録されて緑のまま通る
completion_for() {
    run --separate-stderr env -u FPATH HOME="$ZDOT" ZDOTDIR="$ZDOT" zsh -f -c "source '$COMPLETION_SLICE' || exit 9; print -r -- \${_comps[$1]}"
}

# Homebrew の site-functions は macOS の開発機にしか無いので、タグで CI の実行対象から外す
# bats test_tags=uncovered
@test "completion block: compinit registers completions installed by Homebrew" {
    [ -f /opt/homebrew/share/zsh/site-functions/_brew ] \
        || skip_outside_ci "Homebrew の補完が見つからない" || return 1

    completion_for brew

    [ "$status" -eq 0 ]
    [ "$output" = "_brew" ]
}

@test "completion block: a first shell without a compdump starts without errors" {
    # 新しいマシンの最初のシェルには ~/.zcompdump が無い。日付の比較が空の右辺で
    # 壊れると、起動のたびにエラーを出したまま compinit -C 側へ落ちる
    completion_for git

    [ "$status" -eq 0 ]
    [ -z "$stderr" ]
}

@test "completion block: the slice holds the compinit call" {
    # 切り出しが空だと上のテストが何も評価しないまま、補完表が空のせいで赤くなる。
    # 赤の理由を取り違えないよう、切り出し自体を先に確かめる
    run grep -c 'compinit' "$COMPLETION_SLICE"
    [ "$output" -ge 1 ]
}
