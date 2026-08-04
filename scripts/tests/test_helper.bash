#!/bin/bash
# =============================================================================
# bootstrap.sh テスト用ヘルパー
# =============================================================================

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(dirname "$TEST_DIR")"
REPO_ROOT="$(dirname "$SCRIPTS_DIR")"

# 変異注入でコピーを読ませられるよう上書き可能にする (下の 2 つと同じ理由)。
BOOTSTRAP_SCRIPT="${BOOTSTRAP_SCRIPT:-$REPO_ROOT/bootstrap.sh}"

# この 2 つは ~/.zshrc と ~/.claude/statusline-command.sh のライブ symlink 先そのもの。
# 変異注入で実ファイルを壊すと、その間に開いたシェルや statusLine の描画が壊れた版を踏む
# (特に claude 関数の再帰変異は実害が大きい)。コピーに対して変異を入れられるよう
# 上書き可能にしておく。既定値は実ファイルなので通常実行と CI の対象は変わらない。
STATUSLINE_SCRIPT="${STATUSLINE_SCRIPT:-$REPO_ROOT/home/.claude/statusline-command.sh}"
ZSHRC_FILE="${ZSHRC_FILE:-$REPO_ROOT/home/.zshrc}"

# Raycast のリファレンスモード切り替えスクリプト。上の 2 つと同じく変異注入で
# コピーを読ませられるよう上書き可能にする。
RAYCAST_TOGGLE_SCRIPT="${RAYCAST_TOGGLE_SCRIPT:-$REPO_ROOT/home/.config/raycast/scripts/toggle-reference-mode.sh}"

FIXTURES_DIR="$TEST_DIR/fixtures"
BOOTSTRAP_FIXTURES_DIR="$FIXTURES_DIR/bootstrap"

# =============================================================================
# bootstrap.sh テスト用ヘルパー
# =============================================================================

# テスト用の仮想ホームディレクトリを作成
setup_test_home() {
    TEST_HOME=$(mktemp -d)
    export HOME="$TEST_HOME"
    export DOTFILES_DIR="$BOOTSTRAP_FIXTURES_DIR"

    mkdir -p "$TEST_HOME/.claude"
    mkdir -p "$TEST_HOME/.config/git"
    mkdir -p "$TEST_HOME/.local/bin"
}

# テスト用の仮想ホームディレクトリを削除
teardown_test_home() {
    if [ -n "$TEST_HOME" ] && [ -d "$TEST_HOME" ]; then
        rm -rf "$TEST_HOME"
    fi
}

# bootstrap.sh からヘルパー関数を読み込む
load_bootstrap_functions() {
    local temp_func_file
    temp_func_file=$(mktemp)

    if [ ! -f "$BOOTSTRAP_SCRIPT" ]; then
        echo "Error: Bootstrap script not found: $BOOTSTRAP_SCRIPT" >&2
        return 1
    fi

    # 重複マーカーに対応するため head -1 を使用
    local func_start main_start
    func_start=$(grep -n "^# ヘルパー関数$" "$BOOTSTRAP_SCRIPT" | head -1 | cut -d: -f1)
    main_start=$(grep -n "^# メイン処理$" "$BOOTSTRAP_SCRIPT" | head -1 | cut -d: -f1)

    if [ -z "$func_start" ]; then
        echo "Error: '# ヘルパー関数' marker not found in $BOOTSTRAP_SCRIPT" >&2
        rm -f "$temp_func_file"
        return 1
    fi
    if [ -z "$main_start" ]; then
        echo "Error: '# メイン処理' marker not found in $BOOTSTRAP_SCRIPT" >&2
        rm -f "$temp_func_file"
        return 1
    fi

    sed -n "$((func_start + 1)),$((main_start - 1))p" "$BOOTSTRAP_SCRIPT" > "$temp_func_file"

    if [ ! -s "$temp_func_file" ]; then
        echo "Warning: No functions extracted from $BOOTSTRAP_SCRIPT" >&2
        rm -f "$temp_func_file"
        return 1
    fi

    # shellcheck source=/dev/null
    source "$temp_func_file"
    rm -f "$temp_func_file"
}

# 名前で指定した配列定義ブロックだけを切り出して source し、テストシェルに実配列を
# 定義する。load_bootstrap_functions と同じ marker-slice 方式。ブロックは純データ
# (set -euo pipefail 等の副作用を含まない) なので、whole-file source を避けている理由が
# ここにも当てはまる。実配列を source すればテキスト parse の脆さ
# (配列内コメントを phantom source と誤読する等) を避けられる。
# 配列名が変わったのに黙って空を source すると、その配列を検査するテストが
# 「1 件も見ていないのに緑」になるため、見つからない場合は失敗させる。
load_pairs_array() {
    local name="$1"
    local temp_pairs_file
    temp_pairs_file=$(mktemp)

    sed -n "/^${name}=(/,/^)/p" "$BOOTSTRAP_SCRIPT" > "$temp_pairs_file"

    if [ ! -s "$temp_pairs_file" ]; then
        echo "Error: array not found in $BOOTSTRAP_SCRIPT: $name" >&2
        rm -f "$temp_pairs_file"
        return 1
    fi

    # shellcheck source=/dev/null
    source "$temp_pairs_file"
    rm -f "$temp_pairs_file"
}

# 2 つのマーカー行に挟まれたブロックだけを切り出して source する汎用ローダー。
# load_bootstrap_functions と同じ marker-slice 方式で、whole-file source による副作用
# (set -euo pipefail / zsh 専用構文 / 実処理の実行) を避ける。
# マーカー欠落や空ブロックは黙って空を source せず失敗させる。静かに素通りすると
# 「1 件もアサーションが走っていないのに緑」という空虚なテストになるため。
load_marker_block() {
    local file="$1"
    local start_marker="$2"
    local end_marker="$3"

    if [ ! -f "$file" ]; then
        echo "Error: file not found: $file" >&2
        return 1
    fi

    local start_line
    start_line=$(grep -n "$start_marker" "$file" | head -1 | cut -d: -f1)
    if [ -z "$start_line" ]; then
        echo "Error: start marker not found in $file: $start_marker" >&2
        return 1
    fi

    # 終了マーカーは開始マーカーより後ろの最初の一致を採る。
    # tail で先頭を落としてから grep するため、得られる行番号は start_line からの相対値。
    local end_offset
    end_offset=$(tail -n "+$((start_line + 1))" "$file" | grep -n "$end_marker" | head -1 | cut -d: -f1)
    if [ -z "$end_offset" ]; then
        echo "Error: end marker not found in $file: $end_marker" >&2
        return 1
    fi
    local end_line=$((start_line + end_offset))

    local temp_file
    temp_file=$(mktemp)
    sed -n "$((start_line + 1)),$((end_line - 1))p" "$file" > "$temp_file"

    if [ ! -s "$temp_file" ]; then
        echo "Error: empty block extracted from $file" >&2
        rm -f "$temp_file"
        return 1
    fi

    # shellcheck source=/dev/null
    source "$temp_file"
    rm -f "$temp_file"
}

# statusline-command.sh のヘルパー関数ブロックを読み込む。
load_statusline_functions() {
    load_marker_block "$STATUSLINE_SCRIPT" '^# ヘルパー関数$' '^# メイン処理$'
}

# .zshrc の Claude Code 起動関数ブロックを読み込む。
# .zshrc 全体は zsh 専用構文 (typeset -U / mise activate zsh 等) を含み bash で
# source できないため、当該セクションだけを切り出す。
load_zshrc_claude_functions() {
    load_marker_block "$ZSHRC_FILE" '^# Claude Code 起動$' '^########################################$'
}

# Raycast のリファレンスモード切り替えスクリプトを読み込む。
# 上の 2 つと違い marker-slice を使わず丸ごと source できるのは、スクリプト末尾の
# BASH_SOURCE ガードが source 時の main 実行を抑えているため。marker 方式は
# 「ブロックの外に関数を置くと読み込まれない」制約を呼び込むので、新規スクリプトでは
# ガード方式を採る。ガードが生きていることは raycast-reference-mode.bats が pin する。
load_raycast_toggle_functions() {
    # shellcheck source=/dev/null
    source "$RAYCAST_TOGGLE_SCRIPT"
}

# toggle-reference-mode.sh に埋め込まれた AppleScript ブロックを取り出す。
# heredoc なので bash から source して取り出すことはできず、開始・終了マーカーで
# 切り出すしかない。切り出した中身はここでは一切解釈せず osacompile へ渡し、
# 構文の妥当性は AppleScript のパーサ自身に判定させる (bats 側に AppleScript の
# 文法を二重実装しないため)。
# マーカーが動いて空を切り出したまま緑になるのを防ぐため、空なら失敗させる。
extract_raycast_applescript() {
    local dest="$1"

    sed -n '/<<.APPLESCRIPT.$/,/^APPLESCRIPT$/p' "$RAYCAST_TOGGLE_SCRIPT" | sed '1d;$d' > "$dest"

    if [ ! -s "$dest" ]; then
        echo "Error: AppleScript block not found in $RAYCAST_TOGGLE_SCRIPT" >&2
        return 1
    fi
}

# 指定ディレクトリを cwd にして run を実行し、元の cwd へ戻す。
# cwd を戻さないと teardown_test_home が作業中のディレクトリごと削除し、後続テストが
# 存在しない cwd を引きずって git 探索の結果が揺れる。復元忘れを 1 件でも作らないよう
# ヘルパ側に閉じる。run と同じく status / output はグローバルに残る。
run_in_dir() {
    local dir="$1"
    shift
    local saved="$PWD"
    cd "$dir" || return 1
    run "$@"
    cd "$saved" || return 1
}

# テスト用の偽 claude バイナリを PATH 先頭に用意する
# - plugin list / marketplace list --json は環境変数で制御した JSON を返す
#   （FAKE_PLUGINS_JSON / FAKE_MARKETPLACES_JSON、既定は空配列）
# - marketplace add / install は引数を FAKE_CLAUDE_LOG に記録する
# - FAKE_INSTALL_FAIL に一致する plugin id の install は非ゼロ終了する（best-effort 検証用）
setup_fake_claude() {
    local fake_bin="$TEST_HOME/fakebin"
    mkdir -p "$fake_bin"
    export FAKE_CLAUDE_LOG="$TEST_HOME/claude_calls.log"
    : > "$FAKE_CLAUDE_LOG"

    cat > "$fake_bin/claude" <<'FAKE'
#!/usr/bin/env bash
if [ "$1" = "plugin" ]; then
    case "$2" in
        list)
            echo "${FAKE_PLUGINS_JSON:-[]}"
            exit 0
            ;;
        marketplace)
            case "$3" in
                list)
                    echo "${FAKE_MARKETPLACES_JSON:-[]}"
                    exit 0
                    ;;
                add)
                    echo "marketplace add $4" >> "$FAKE_CLAUDE_LOG"
                    exit 0
                    ;;
            esac
            ;;
        install)
            echo "install $3" >> "$FAKE_CLAUDE_LOG"
            if [ -n "${FAKE_INSTALL_FAIL:-}" ] && [ "$3" = "${FAKE_INSTALL_FAIL}" ]; then
                exit 1
            fi
            exit 0
            ;;
    esac
fi
exit 0
FAKE
    chmod +x "$fake_bin/claude"
    export PATH="$fake_bin:$PATH"
}

# 起動時の環境と引数だけを記録する偽 claude を PATH 先頭に用意する。
# 起動関数のテスト用。CLAUDE_CONFIG_DIR は「未設定」と「空文字」を区別して記録するため、
# 未設定時は行そのものを出さない (個人アカウントが変数に触れないことを pin するのに要る)。
setup_recording_claude() {
    local fake_bin="$TEST_HOME/fakebin"
    mkdir -p "$fake_bin"
    export RECORDED_LAUNCH="$TEST_HOME/claude_launch.log"
    : > "$RECORDED_LAUNCH"

    cat > "$fake_bin/claude" <<'FAKE'
#!/usr/bin/env bash
echo "LAUNCHED" >> "$RECORDED_LAUNCH"
if [ -n "${CLAUDE_CONFIG_DIR+set}" ]; then
    echo "CONFIG_DIR=$CLAUDE_CONFIG_DIR" >> "$RECORDED_LAUNCH"
fi
if [ -n "${CLAUDE_CODE_TASK_LIST_ID+set}" ]; then
    echo "TASK_LIST=$CLAUDE_CODE_TASK_LIST_ID" >> "$RECORDED_LAUNCH"
fi
echo "ARGV=$*" >> "$RECORDED_LAUNCH"
exit 0
FAKE
    chmod +x "$fake_bin/claude"
    export PATH="$fake_bin:$PATH"
}

# statusline-command.sh を実行するための偽 security / curl を PATH 先頭に用意する。
# security は要求された service 名を記録し、FAKE_KEYCHAIN_SERVICE に一致したときだけ
# トークンを返す。これで「どの service 名を引きに行ったか」と「不一致時に他の名前へ
# フォールバックしないか」の両方を観測できる。
setup_fake_keychain() {
    local fake_bin="$TEST_HOME/fakebin"
    mkdir -p "$fake_bin"
    export SECURITY_LOG="$TEST_HOME/security_calls.log"
    : > "$SECURITY_LOG"

    cat > "$fake_bin/security" <<'FAKE'
#!/usr/bin/env bash
service=""
while [ $# -gt 0 ]; do
    case "$1" in
        -s) service="$2"; shift 2 ;;
        *) shift ;;
    esac
done
echo "$service" >> "$SECURITY_LOG"
if [ "$service" = "${FAKE_KEYCHAIN_SERVICE:-}" ]; then
    echo "test-token"
    exit 0
fi
# 実物が item 不在時に返す exit code
exit 44
FAKE
    chmod +x "$fake_bin/security"

    cat > "$fake_bin/curl" <<'FAKE'
#!/usr/bin/env bash
cat <<'HEADERS'
HTTP/2 200
anthropic-ratelimit-unified-5h-utilization: 0.42
anthropic-ratelimit-unified-5h-reset: 1800000000
anthropic-ratelimit-unified-7d-utilization: 0.13
anthropic-ratelimit-unified-7d-reset: 1800000000
HEADERS
FAKE
    chmod +x "$fake_bin/curl"

    export PATH="$fake_bin:$PATH"
}

# テスト用の偽 osascript を PATH 先頭に用意する。
# リファレンスモード切り替えは実 GUI を操作するため、実物を呼ぶとテストが System
# Settings を開いてしまい CI でも回せない。呼び出し引数だけを記録して制御可能な値を
# 返す偽物に差し替え、bash 側のオーケストレーション (読む → 決める → 適用する →
# 突き合わせる) を GUI 抜きで検証する。UI 操作そのものの検証は live smoke に委ねる。
#
# 呼び出し形式は `osascript - <mode> <timeout> [preset]` を前提とする。
# 制御用の環境変数:
#   FAKE_CURRENT_PRESET  read が返す現在値 (未設定なら空 = 読み取り失敗の再現)
#   FAKE_APPLIED_PRESET  apply が返す適用後の値 (未設定なら要求値をそのまま返す)
#   FAKE_OSASCRIPT_FAIL  この mode の呼び出しを非ゼロ終了させる
setup_fake_osascript() {
    local fake_bin="$TEST_HOME/fakebin"
    mkdir -p "$fake_bin"
    export FAKE_OSASCRIPT_LOG="$TEST_HOME/osascript_calls.log"
    : > "$FAKE_OSASCRIPT_LOG"

    cat > "$fake_bin/osascript" <<'FAKE'
#!/usr/bin/env bash
# AppleScript 本体は stdin から渡るので読み捨てる。読まないと呼び出し側が
# SIGPIPE で落ち、偽物の存在自体がテスト結果を変えてしまう。
cat > /dev/null

mode="$2"
preset="${4:-}"
printf 'mode=%s preset=%s\n' "$mode" "$preset" >> "$FAKE_OSASCRIPT_LOG"

# 空同士の一致で無関係な呼び出しまで落とさないよう、指定があるときだけ比較する。
if [ -n "${FAKE_OSASCRIPT_FAIL:-}" ] && [ "${FAKE_OSASCRIPT_FAIL}" = "$mode" ]; then
    echo "fake osascript failure for mode=$mode" >&2
    exit 1
fi

case "$mode" in
    read) printf '%s' "${FAKE_CURRENT_PRESET-}" ;;
    apply) printf '%s' "${FAKE_APPLIED_PRESET-$preset}" ;;
esac
FAKE
    chmod +x "$fake_bin/osascript"

    export PATH="$fake_bin:$PATH"
}

# statusline-command.sh へ渡す stdin JSON を組み立てる。
# 引数を省くと cwd が空になり git 探索経路へ入らないため、アカウント分離の観測に絞れる。
statusline_input_json() {
    printf '{"model":{"display_name":"Test"},"context_window":{"used_percentage":10},"cwd":"%s"}' "${1:-}"
}

# statusline-command.sh をリポジトリ外の状況で実行する。
run_statusline() {
    run_statusline_in ""
}

# cwd を指定して statusline-command.sh を実行する (リポジトリ行の検証用)。
run_statusline_in() {
    run bash "$STATUSLINE_SCRIPT" <<< "$(statusline_input_json "$1")"
}

# statusline-command.sh の生の出力をファイルへ落とす。
# bats の $output は末尾改行を落とすため、「最終行に改行を付けない」規約は
# $lines の要素数では原理的に観測できない。改行の数で見る必要がある。
statusline_raw() {
    local dest="$1"
    bash "$STATUSLINE_SCRIPT" > "$dest" 2>/dev/null <<< "$(statusline_input_json "${2:-}")"
}

# ファイル内の改行の数を返す。行数ではなく改行数なので、
# 末尾に改行が無い N 行のファイルは N-1 を返す。
count_newlines() {
    wc -l < "$1" | tr -d ' '
}

# テスト用の git リポジトリを作る。コミットは作らないが
# branch --show-current は未出生ブランチ名を返すため表示検証には足りる。
setup_test_repo() {
    local dir="$1"
    mkdir -p "$dir"
    git -C "$dir" init -q
    git -C "$dir" config user.email "test@example.com"
    git -C "$dir" config user.name "test"
}

# =============================================================================
# アサーションヘルパー
# =============================================================================
#
# 裸の [[ ]] は bash 3.2 で偽でも ERR トラップを発火させずアサーションが空虚に緑になるため、
# 以降は単純コマンド (シェル関数呼び出し) で書く。詳細は rules/bats-no-bare-double-bracket.yml を参照。

# haystack が needle を部分文字列として含むことを確認する。
# 照合は case のクォート付きパターンで行う。needle をクォートせずに
# *$needle* と書くと [ ] を含む needle (例: [DRY-RUN]) が glob の文字クラスとして
# 解釈され、意図と違う 1 文字マッチになってしまうため、必ずクォートしてリテラル一致にする。
assert_contains() {
    local haystack="$1"
    local needle="$2"
    case "$haystack" in
        *"$needle"*) return 0 ;;
    esac
    echo "assert_contains: expected substring not found" >&2
    echo "  expected to contain: $needle" >&2
    echo "  actual: $haystack" >&2
    return 1
}

# haystack が needle を含まないことを確認する (assert_contains の否定形)。
refute_contains() {
    local haystack="$1"
    local needle="$2"
    case "$haystack" in
        *"$needle"*)
            echo "refute_contains: unexpected substring found" >&2
            echo "  expected NOT to contain: $needle" >&2
            echo "  actual: $haystack" >&2
            return 1
            ;;
    esac
    return 0
}

# haystack 内で needle_a の後に needle_b がこの順で現れることを確認する。
# 「両方含む」ではなく前後関係そのものが仕様であるケース専用
# (例: 1 件目の install 失敗後も 2 件目の install を試みる best-effort 継続の検証)。
# 単に両方含むかだけを見たいなら assert_contains を 2 回呼べばよい。
assert_contains_in_order() {
    local haystack="$1"
    local needle_a="$2"
    local needle_b="$3"
    case "$haystack" in
        *"$needle_a"*"$needle_b"*) return 0 ;;
    esac
    echo "assert_contains_in_order: expected order not found" >&2
    echo "  expected order: $needle_a -> $needle_b" >&2
    echo "  actual: $haystack" >&2
    return 1
}
