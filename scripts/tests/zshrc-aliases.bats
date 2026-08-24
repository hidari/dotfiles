#!/usr/bin/env bats
# =============================================================================
# .zshrc のエイリアスが対話シェルに限定されているかのテスト
# =============================================================================
#
# エイリアスは対話シェルの利便機能だが、非対話シェル (エージェントの Bash ツール
# など) にも効くと出力の形が変わる。実測では `alias ls='ls -aG'` の -a が . と ..
# を数え、ファイル 2 個のディレクトリで `ls -1 | wc -l` が 4 を返した。エラーでは
# なくもっともらしい数字で返るため、出力を見ても気づけない。
#
# 検査は実際の zsh へ聞く。bats は bash で走るが `[[ -o interactive ]]` は zsh の
# オプション検査で、bash には interactive オプションが無い。bash へ source すると
# 構文は通るのに意味が変わり、検査が別物になる。
#
# zsh は `-f` で起動して起動ファイルを一切読ませない。実 .zshrc を読ませると
# mise / herdr / tirith まで走り、検査対象と無関係な理由で結果が揺れる。

load test_helper

setup() {
    ALIAS_SLICE="$BATS_TEST_TMPDIR/aliases.zsh"
    extract_zshrc_block '^# エイリアス$' "$ALIAS_SLICE"
}

# ブロックが宣言するエイリアス名を空白区切りで返す。名前をテスト側へ literal で
# 書くと、エイリアスを足したときに検査だけが古いリストを見たまま緑で通る。
alias_names_in_block() {
    grep -oE '^[[:space:]]*alias [A-Za-z0-9_-]+' "$ALIAS_SLICE" \
        | sed -E 's/.*alias //' \
        | tr '\n' ' '
}

@test "alias block: zsh is available for the shell-semantics tests" {
    # 不在だと下の 2 本が status 127 で落ち、原因が読み取りにくい失敗になる
    run command -v zsh
    [ "$status" -eq 0 ]
}

@test "alias block: the slice actually contains alias definitions" {
    # 切り出しが空だと下の 2 本が何も見ずに緑になる
    run grep -c '^[[:space:]]*alias ' "$ALIAS_SLICE"
    [ "$status" -eq 0 ]
    [ "$output" -ge 1 ]
}

@test "alias block: no alias from the block survives in a non-interactive shell" {
    # ブロックが宣言する名前を実ファイルから取り、その名前だけを引いて確かめる。
    # `alias` の出力が空であることでは判定できない。zsh は -f で起動しても
    # run-help / which-command の組み込みエイリアスを持つため常に非空になる
    local names
    names=$(alias_names_in_block)
    # 未定義のエイリアスを引くと zsh は 1 を返すので、ループ内では成否を落とす。
    # source の失敗だけは別の終了コードで残し、空の出力と取り違えないようにする
    run zsh -f -c "source '$ALIAS_SLICE' || exit 9; for n in $names; do alias \$n 2>/dev/null || true; done"
    [ "$status" -eq 0 ]
    [ -z "$output" ]
}

@test "alias block: ls stays aliased in an interactive shell" {
    # 対話側まで消すと利用者の利便を壊す。ガードは向きを持つ
    run zsh -f -i -c "source '$ALIAS_SLICE'; alias ls"
    [ "$status" -eq 0 ]
    assert_contains "$output" "ls -aG"
}
