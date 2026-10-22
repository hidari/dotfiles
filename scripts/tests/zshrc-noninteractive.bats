#!/usr/bin/env bats
# =============================================================================
# .zshrc が対話専用のもの (プロンプト・オプション・claude のランチャ) を非対話シェルへ運ばないかのテスト
# =============================================================================
#
# 非対話へ運ぶと何が壊れるかは、home/.zshrc の各ガードの冒頭が canonical。ここは
# その検査だけを持つ。エイリアスの検査は zshrc-aliases.bats が持つ。
#
# 検査は実際の zsh へ聞く。理由と -f で起動する理由は zshrc-aliases.bats の冒頭と同じ。

load test_helper

setup() {
    require_command_or_skip zsh || return 1

    PROMPT_SLICE="$BATS_TEST_TMPDIR/prompt.zsh"
    OPTION_SLICE="$BATS_TEST_TMPDIR/options.zsh"
    LAUNCHER_SLICE="$BATS_TEST_TMPDIR/launchers.zsh"
    LAUNCHER_GUARD_SLICE="$BATS_TEST_TMPDIR/launcher-guard.zsh"
    extract_zshrc_block '^# プロンプト設定$' "$PROMPT_SLICE"
    extract_zshrc_block '^# オプション$' "$OPTION_SLICE"
    extract_zshrc_block '^# Claude Code 起動$' "$LAUNCHER_SLICE"
    extract_zshrc_block '^# 非対話シェルへ運ばないランチャ$' "$LAUNCHER_GUARD_SLICE"

    # ランチャの生成器が読む設定を一時ディレクトリへ閉じる。追加アカウントの行を1つ
    # 置くのは、生成された関数まで外れることを確かめるため
    export HOME="$BATS_TEST_TMPDIR/home"
    mkdir -p "$HOME/.claude" "$HOME/.claude-alpha"
    export CLAUDE_CONFIG_DIRS_FILE="$BATS_TEST_TMPDIR/claude-config-dirs"
    printf '.claude-alpha\n' > "$CLAUDE_CONFIG_DIRS_FILE"
}

# 切り出しが宣言するオプション名を、zsh の `setopt` が出力する形 (小文字、_ なし) に
# 揃えて空白区切りで返す。名前をテスト側へ literal で書くと、オプションを足したときに
# 検査だけが古いリストを見たまま緑で通る
option_names_in_slices() {
    sed -nE 's/^[[:space:]]*setopt ([A-Za-z_]+).*/\1/p' "$PROMPT_SLICE" "$OPTION_SLICE" \
        | tr -d '_' | tr '[:upper:]' '[:lower:]' | tr '\n' ' '
}

@test "option guard: the guarded slices hold every setopt in the file" {
    # 切り出しが空だと下の検査が何も見ずに緑になる。件数をファイル全体と突き合わせる
    # のは、ガードの外に書いた setopt がスライス限定の検査から見えないため
    run grep -c '^[[:space:]]*setopt ' "$PROMPT_SLICE" "$OPTION_SLICE"
    local in_slices
    in_slices=$(printf '%s\n' "$output" | awk -F: '{s += $NF} END {print s}')
    [ "$in_slices" -ge 2 ]

    run grep -c '^[[:space:]]*setopt ' "$ZSHRC_FILE"
    [ "$output" -eq "$in_slices" ]
}

@test "option guard: no option from the slices takes effect in a non-interactive shell" {
    local names
    names=$(option_names_in_slices)
    [ -n "$names" ]
    # 有効なオプションの一覧を出し、宣言した名前が1つも載らないことを見る。source の
    # 失敗だけは別の終了コードで残し、空の一覧と取り違えないようにする
    run zsh -f -c "source '$PROMPT_SLICE' || exit 9; source '$OPTION_SLICE' || exit 9; setopt"
    [ "$status" -eq 0 ]
    local name
    for name in $names; do
        if printf '%s\n' "$output" | grep -qx "$name"; then
            echo "非対話で有効: $name" >&2
            return 1
        fi
    done
}

@test "option guard: every option from the slices stays on in an interactive shell" {
    # 対話側まで消すと利用者の利便を壊す。ガードは向きを持つ
    local names
    names=$(option_names_in_slices)
    [ -n "$names" ]
    run zsh -f -i -c "source '$PROMPT_SLICE'; source '$OPTION_SLICE'; setopt"
    [ "$status" -eq 0 ]
    local name
    for name in $names; do
        if ! printf '%s\n' "$output" | grep -qx "$name"; then
            echo "対話で無効: $name" >&2
            return 1
        fi
    done
}

@test "launcher guard: no claude launcher is a function in a non-interactive shell" {
    # 補助関数 (_ 始まり) はスナップショットに運ばれないので、非対話に残ったランチャは
    # 呼ぶと落ちる。生成されたアカウント分も含めて関数として残らないことを見る
    run zsh -f -c "source '$LAUNCHER_SLICE' || exit 9; source '$LAUNCHER_GUARD_SLICE' || exit 9; whence -w claude claude-dev claude-alpha claude-alpha-dev"
    [ "$status" -ne 9 ]
    if printf '%s\n' "$output" | grep -q ': function$'; then
        echo "$output" >&2
        return 1
    fi
}

@test "launcher guard: the helpers outside the launchers stay functions in a non-interactive shell" {
    # 関数は非対話へ運ぶ裁定なので、外すのはランチャに限る。外す範囲を広げると
    # ランチャ以外の関数まで消える
    run zsh -f -c "source '$LAUNCHER_SLICE' || exit 9; source '$LAUNCHER_GUARD_SLICE' || exit 9; whence -w _claude_config_dir _claude_task_list_id _claude_dev_plugin_args"
    [ "$status" -eq 0 ]
    assert_contains "$output" "_claude_config_dir: function"
    assert_contains "$output" "_claude_task_list_id: function"
    assert_contains "$output" "_claude_dev_plugin_args: function"
}

@test "launcher guard: the launchers stay functions in an interactive shell" {
    run zsh -f -i -c "source '$LAUNCHER_SLICE'; source '$LAUNCHER_GUARD_SLICE'; whence -w claude claude-dev claude-alpha claude-alpha-dev"
    [ "$status" -eq 0 ]
    assert_contains "$output" "claude: function"
    assert_contains "$output" "claude-dev: function"
    assert_contains "$output" "claude-alpha: function"
    assert_contains "$output" "claude-alpha-dev: function"
}
