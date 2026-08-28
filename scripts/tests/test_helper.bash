#!/bin/bash
# =============================================================================
# bootstrap.sh テスト用ヘルパー
# =============================================================================

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPTS_DIR="$(dirname "$TEST_DIR")"
REPO_ROOT="$(dirname "$SCRIPTS_DIR")"

# 検査対象のスクリプト群。いずれも変異注入でコピーを読ませられるよう上書き可能に
# する。既定値は実ファイルなので通常実行と CI の対象は変わらない。
BOOTSTRAP_SCRIPT="${BOOTSTRAP_SCRIPT:-$REPO_ROOT/bootstrap.sh}"

# 次の 2 つは ~/.zshrc と ~/.claude/statusline-command.sh のライブ symlink 先そのもの。
# 変異注入で実ファイルを壊すと、その間に開いたシェルや statusLine の描画が壊れた版を踏む
# (特に claude 関数の再帰変異は実害が大きい)。上書き可能にしておく理由がここだけ重い。
STATUSLINE_SCRIPT="${STATUSLINE_SCRIPT:-$REPO_ROOT/home/.claude/statusline-command.sh}"
ZSHRC_FILE="${ZSHRC_FILE:-$REPO_ROOT/home/.zshrc}"

# apm ガードの判定を持つ共有シェル層。bootstrap.sh と PATH shim の両方が source する。
# bootstrap.sh はブロック切り出しで source されるため自分の位置から解決できず、
# ここが指す先が唯一の入口になる。export が要るのは bootstrap.bats が
# `run bash "$BOOTSTRAP_SCRIPT"` で別プロセスとして起動する経路のため。非 export の値は
# プロセス境界を越えず、変異注入で BOOTSTRAP_SCRIPT をコピーへ向けると相対解決の
# フォールバックも別ディレクトリを指すので、export を外すと変異注入だけが静かに壊れる。
APM_GUARD_LIB="${APM_GUARD_LIB:-$REPO_ROOT/scripts/apm-guard/lib.sh}"
export APM_GUARD_LIB

# .zshrc のセクション区切り。ブロック切り出しの終端マーカーとして複数の入口が使う
ZSHRC_SECTION_END='^########################################$'

# Raycast のリファレンスモード切り替えスクリプト。
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

# 外部コマンドの有無で分岐する。CI では skip で隠さず落とす。
# 緑のまま何も検証していない状態が一番危ないので、ローカルの利便とは非対称にする。
# 「CI なら必須」が成り立つのは、そのテストを走らせる job が導入するコマンドに限る。
# job が入れないコマンド (bats job にとっての gitleaks、Linux にとっての osacompile)
# へこの入口を使うと、正当な不在で CI が赤くなる。
require_command_or_skip() {
    local cmd="$1"

    if command -v "$cmd" >/dev/null 2>&1; then
        return 0
    fi
    if [ -n "${CI:-}" ]; then
        echo "$cmd is required in CI but was not found" >&2
        return 1
    fi
    skip "$cmd is not installed"
}

# bootstrap.sh からヘルパー関数を読み込む
load_bootstrap_functions() {
    load_marker_block "$BOOTSTRAP_SCRIPT" '^# ヘルパー関数$' '^# メイン処理$'
}

# 名前で指定した配列定義ブロックだけを切り出して source し、テストシェルに実配列を
# 定義する。load_marker_block と同じ marker-slice 方式。ブロックは純データ
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

# 2 つのマーカー行に挟まれたブロックを dest へ書き出す。
# 切り出しの規約 (開始マーカーの次行から、開始より後ろの最初の終了マーカーの前行まで) を
# ここに 1 つだけ置く。bash へ source する側と、別のシェルへ渡す側が別々に範囲を決めると、
# 片方だけが規約を変えたときに気づけない。
# マーカー欠落や空ブロックは黙って空を返さず失敗させる。静かに素通りすると
# 「1 件もアサーションが走っていないのに緑」という空虚なテストになるため。
extract_marker_block() {
    local file="$1"
    local start_marker="$2"
    local end_marker="$3"
    local dest="$4"

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

    # tail で先頭を落としてから grep するため、得られる行番号は start_line からの相対値。
    local end_offset
    end_offset=$(tail -n "+$((start_line + 1))" "$file" | grep -n "$end_marker" | head -1 | cut -d: -f1)
    if [ -z "$end_offset" ]; then
        echo "Error: end marker not found in $file: $end_marker" >&2
        return 1
    fi
    local end_line=$((start_line + end_offset))

    sed -n "$((start_line + 1)),$((end_line - 1))p" "$file" > "$dest"

    if [ ! -s "$dest" ]; then
        echo "Error: empty block extracted from $file" >&2
        return 1
    fi
}

# 2 つのマーカー行に挟まれたブロックだけを切り出して source する汎用ローダー。
# whole-file source による副作用 (set -euo pipefail / zsh 専用構文 / 実処理の実行) を避ける。
load_marker_block() {
    local temp_file
    temp_file=$(mktemp)

    if ! extract_marker_block "$1" "$2" "$3" "$temp_file"; then
        rm -f "$temp_file"
        return 1
    fi

    # shellcheck source=/dev/null
    source "$temp_file"
    rm -f "$temp_file"
}

# コミットを 1 つ持つテスト用リポジトリを作る。
# setup_test_repo はコミットを作らないが、status --porcelain の比較には
# 「追跡されている既存ファイル」が要るのでここで用意する。
init_committed_repo() {
    local repo="$1"
    setup_test_repo "$repo"
    echo hello > "$repo/a.txt"
    git -C "$repo" add a.txt
    git -C "$repo" commit -qm init
}

# statusline-command.sh のヘルパー関数ブロックを読み込む。
load_statusline_functions() {
    load_marker_block "$STATUSLINE_SCRIPT" '^# ヘルパー関数$' '^# メイン処理$'
}

# .zshrc の Claude Code 起動関数ブロックを読み込む。
# .zshrc 全体は zsh 専用構文 (typeset -U / mise activate zsh 等) を含み bash で
# source できないため、当該セクションだけを切り出す。
load_zshrc_claude_functions() {
    load_marker_block "$ZSHRC_FILE" '^# Claude Code 起動$' "$ZSHRC_SECTION_END"
}

# .zshrc のブロックを dest へ書き出す。bash へ source する上の 2 つと違い、
# zsh 専用の構文 (setopt / [[ -o ... ]] / print -rnD 等) を含むブロックを
# 実際の zsh へ渡して評価させるための入口。bash で解釈すると、構文は通るのに
# 意味が変わる形 (bash に interactive オプションが無い等) で検査が別物になる。
extract_zshrc_block() {
    local start_marker="$1"
    local dest="$2"
    extract_marker_block "$ZSHRC_FILE" "$start_marker" "$ZSHRC_SECTION_END" "$dest"
}

# Raycast のリファレンスモード切り替えスクリプトを読み込む。
# marker-slice 方式のローダーと違い丸ごと source できるのは、スクリプト末尾の
# BASH_SOURCE ガードが source 時の main 実行を抑えているため。marker 方式は
# 「ブロックの外に関数を置くと読み込まれない」制約を呼び込むので、新規スクリプトでは
# ガード方式を採る。ガードが生きていることは raycast-reference-mode.bats が pin する。
#
# AppleScript 本体もこの source で $DISPLAY_APPLESCRIPT として手に入る。ファイルを
# マーカーで切り出す必要が無いので、切り出し範囲が狭まって断片だけを検査していた、
# という失敗の形が起こらない。
load_raycast_toggle_functions() {
    # shellcheck source=/dev/null
    source "$RAYCAST_TOGGLE_SCRIPT"
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

# 偽バイナリの置き場を FAKE_BIN へ export する。値は返さない。
# コマンド置換で呼ぶとサブシェルになり export が親へ届かないため、変数で受け渡す。
# 届かない場合、stub 自体は作られるので「呼ばれた記録が無い」= ガードが効いた、という
# 偽の緑になりうる。
setup_fake_bin_dir() {
    export FAKE_BIN="$TEST_HOME/fakebin"
    mkdir -p "$FAKE_BIN"
}

# テスト用の偽 apm バイナリを FAKE_BIN へ用意する。
# 呼び出しの記録先は APM_STUB_REC で、1 行目に cwd (pwd -P)、2 行目に引数を書く。
# 呼ばれたかどうかだけを見るテストは記録ファイルの有無で判定できる。
setup_fake_apm() {
    setup_fake_bin_dir
    export APM_STUB_REC="$TEST_HOME/apm-invocation.txt"

    cat > "$FAKE_BIN/apm" << 'FAKE'
#!/bin/sh
pwd -P > "$APM_STUB_REC"
printf '%s\n' "$*" >> "$APM_STUB_REC"
FAKE
    chmod +x "$FAKE_BIN/apm"
}

# git status だけを失敗させる偽 git を FAKE_BIN へ用意する。
# それ以外のサブコマンドは実物へ委譲するので、リポジトリ判定はそのまま働く。
# 「検査できなかった」を「clean」と取り違えないことを見るために使う。
setup_failing_git_status() {
    setup_fake_bin_dir
    REAL_GIT="$(command -v git)"
    export REAL_GIT

    cat > "$FAKE_BIN/git" << 'FAKE'
#!/usr/bin/env bash
for arg in "$@"; do
    if [ "$arg" = "status" ]; then
        echo "fatal: simulated git failure" >&2
        exit 128
    fi
done
exec "$REAL_GIT" "$@"
FAKE
    chmod +x "$FAKE_BIN/git"
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
# 呼び出し形式は `osascript - <mode> <timeout> <preset> <presetList>` を前提とする。
# 引数は 4 つ固定で、read と close では preset が空文字になる。
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
preset="$4"
presets="$5"
printf 'mode=%s preset=%s presets=%s\n' "$mode" "$preset" "$presets" >> "$FAKE_OSASCRIPT_LOG"

if [ "${FAKE_OSASCRIPT_FAIL:-}" = "$mode" ]; then
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

# 配列が指定の要素を含むことを確認する。第 1 引数が探す値、残りが配列。
# 部分一致の assert_contains と違い要素単位で完全一致を見るので、
# 「別要素の一部にたまたま含まれている」を通さない。
assert_array_contains() {
    local needle="$1"
    shift

    local element
    for element in "$@"; do
        if [ "$element" = "$needle" ]; then
            return 0
        fi
    done

    echo "assert_array_contains: expected element not found" >&2
    echo "  expected: $needle" >&2
    echo "  actual: $*" >&2
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
