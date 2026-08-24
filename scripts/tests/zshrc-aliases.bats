#!/usr/bin/env bats
# =============================================================================
# .zshrc のエイリアスが対話シェルに限定されているかのテスト
# =============================================================================
#
# エイリアスが非対話シェルにも効くと何が壊れるかは、home/.zshrc のエイリアス
# ブロック冒頭が canonical。ここはその検査だけを持つ。
#
# 検査は実際の zsh へ聞く。bats は bash で走るが `[[ -o interactive ]]` は zsh の
# オプション検査で、bash には interactive オプションが無い。bash へ source すると
# 構文は通るのに意味が変わり、検査が別物になる。
#
# zsh は `-f` で起動して起動ファイルを一切読ませない。実 .zshrc を読ませると
# mise / herdr / tirith まで走り、検査対象と無関係な理由で結果が揺れる。

load test_helper

setup() {
    require_command_or_skip zsh || return 1

    ALIAS_SLICE="$BATS_TEST_TMPDIR/aliases.zsh"
    extract_zshrc_block '^# エイリアス$' "$ALIAS_SLICE"
}

# ブロックが宣言するエイリアス名を空白区切りで返す。名前をテスト側へ literal で
# 書くと、エイリアスを足したときに検査だけが古いリストを見たまま緑で通る。
# 空白へ畳むところまでが責務。戻り値は zsh へ渡すコマンド文字列の `for n in ...`
# へ埋め込まれるので、改行区切りのまま返すと語リストが 1 件目で終わる。
alias_names_in_block() {
    sed -nE 's/^[[:space:]]*alias ([A-Za-z0-9_-]+)=.*/\1/p' "$ALIAS_SLICE" \
        | tr '\n' ' '
}

@test "alias block: the slice holds every alias defined in the file" {
    # 切り出しが空だと下の 2 本が何も見ずに緑になる。さらに件数をファイル全体と
    # 突き合わせるのは、ブロック外に書いた alias がガードの外側に居るのに
    # ブロック限定の検査からは見えないため
    run grep -c '^[[:space:]]*alias ' "$ALIAS_SLICE"
    [ "$output" -ge 1 ]
    local in_block="$output"

    run grep -c '^[[:space:]]*alias ' "$ZSHRC_FILE"
    [ "$output" -eq "$in_block" ]
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
