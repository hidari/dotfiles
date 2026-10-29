#!/usr/bin/env bats
# =============================================================================
# statusline-command.sh の使用率の色と handoff-sentinel のしきい値の同期
# =============================================================================
#
# 使用率の色は、handoff-sentinel フックが通知を出すしきい値に揃える。
#   - コンテキスト: フックの通知のしきい値から黄、CTX_RED_PCT から赤
#     (しきい値が CTX_RED_PCT 以上なら、赤の境界もしきい値まで上げる)
#   - 5h / 7d: フックの warn から黄、urgent から赤
#   - しきい値はフックの thresholds アクションから読む。値も環境変数の解釈もフックが持ち、
#     statusline は書き写さない
#   - 比べるのは丸める前の値 (フックと同じ)。表示だけを丸める
#   - しきい値を読めないときは、色を GRAY にして読めていないことを見せる
#
# 期待値のしきい値は、statusline を通さずにフックへ直接問い合わせて得る。

load test_helper

HOOK="$REPO_ROOT/home/.claude/hooks/handoff-sentinel.py"

setup() {
    setup_test_home
    unset CLAUDE_CONFIG_DIR
    export XDG_CACHE_HOME="$TEST_HOME/cache"
    # 開発機の環境変数でしきい値が動くと、期待値がテストごとに変わる
    unset HANDOFF_CONTEXT_THRESHOLD_PCT HANDOFF_RATELIMIT_WARN_PCT HANDOFF_RATELIMIT_URGENT_PCT
    # 色の定数とゲージをスクリプトから読み、期待値に literal を書き写さない
    load_statusline_functions
}

teardown() {
    teardown_test_home
}

# フックがいま効かせているしきい値を 1 つ返す
hook_threshold() {
    python3 "$HOOK" thresholds | jq -er ".$1"
}

# コンテキストの使用率 (と任意の rate_limits) を持つ stdin で statusline を実行する
run_with_usage() {
    local rate_limits="${2:-null}"
    run bash "$STATUSLINE_SCRIPT" <<< "$(jq -cn --argjson pct "$1" --argjson rl "$rate_limits" \
        '{model: {display_name: "Test"}, context_window: {used_percentage: $pct}, cwd: ""}
         + (if $rl == null then {} else {rate_limits: $rl} end)')"
    [ "$status" -eq 0 ]
}

# 1 行目のコンテキストの表示が、指定の色で始まること
assert_context_color() {
    local pct="$1" color="$2" shown
    run_with_usage "$pct"
    shown=$(printf '%.0f' "$pct")
    assert_contains "${lines[0]}" "${color}$(ctx_gauge "$shown") ${shown}%"
}

# 5h と 7d の行が、指定の色で始まること
assert_ratelimit_color() {
    local pct="$1" color="$2"
    run_with_usage 10 "$(rate_limits_json "$pct" "$pct")"
    assert_contains "${lines[1]}" "${color}5h  "
    assert_contains "${lines[2]}" "${color}7d  "
}

# =============================================================================
# コンテキスト
# =============================================================================

@test "context color: turns yellow at the hook's default threshold" {
    local t
    t=$(hook_threshold context_pct)

    assert_context_color "$((t - 1))" "$GREEN"
    assert_context_color "$t" "$YELLOW"
}

@test "context color: follows the threshold the hook reads from the environment" {
    export HANDOFF_CONTEXT_THRESHOLD_PCT=40

    assert_context_color 39 "$GREEN"
    assert_context_color 40 "$YELLOW"
    assert_context_color "$((CTX_RED_PCT - 1))" "$YELLOW"
    assert_context_color "$CTX_RED_PCT" "$RED"
}

@test "context color: leaves the parsing of the environment to the hook" {
    # int() は "+40" を 40 と読む。statusline が自前で解釈すると、ここで食い違う
    export HANDOFF_CONTEXT_THRESHOLD_PCT=+40

    assert_context_color 39 "$GREEN"
    assert_context_color 40 "$YELLOW"
}

@test "context color: raises red to the threshold when the threshold is above it" {
    export HANDOFF_CONTEXT_THRESHOLD_PCT=$((CTX_RED_PCT + 5))

    assert_context_color "$((CTX_RED_PCT + 4))" "$GREEN"
    assert_context_color "$((CTX_RED_PCT + 5))" "$RED"
}

@test "context color: compares the unrounded value" {
    export HANDOFF_CONTEXT_THRESHOLD_PCT=40

    # 39.5 は 40% と表示されるが、しきい値には届いていない
    assert_context_color 39.5 "$GREEN"
}

# =============================================================================
# 5h / 7d
# =============================================================================

@test "rate limit color: turns yellow at warn and red at urgent by default" {
    local warn urgent
    warn=$(hook_threshold ratelimit_warn_pct)
    urgent=$(hook_threshold ratelimit_urgent_pct)

    assert_ratelimit_color "$((warn - 1))" "$GREEN"
    assert_ratelimit_color "$warn" "$YELLOW"
    assert_ratelimit_color "$((urgent - 1))" "$YELLOW"
    assert_ratelimit_color "$urgent" "$RED"
}

@test "rate limit color: follows the thresholds the hook reads from the environment" {
    export HANDOFF_RATELIMIT_WARN_PCT=30 HANDOFF_RATELIMIT_URGENT_PCT=60

    assert_ratelimit_color 29 "$GREEN"
    assert_ratelimit_color 30 "$YELLOW"
    assert_ratelimit_color 59 "$YELLOW"
    assert_ratelimit_color 60 "$RED"
}

@test "rate limit color: compares the unrounded value like the hook does" {
    export HANDOFF_RATELIMIT_WARN_PCT=30 HANDOFF_RATELIMIT_URGENT_PCT=60

    # 29.5 は 30% と表示されるが、フックは warn に届いたと見なさない
    assert_ratelimit_color 29.5 "$GREEN"
}

# =============================================================================
# しきい値を読めないとき
# =============================================================================

# statusline をフックの無い場所へ写し、そこから実行する。第1引数はフックの中身 (省くと置かない)
use_isolated_statusline() {
    local dir="$TEST_HOME/isolated"
    mkdir -p "$dir"
    cp "$STATUSLINE_SCRIPT" "$dir/statusline-command.sh"
    if [ -n "${1:-}" ]; then
        mkdir -p "$dir/hooks"
        printf '%s\n' "$1" > "$dir/hooks/handoff-sentinel.py"
    fi
    STATUSLINE_SCRIPT="$dir/statusline-command.sh"
}

assert_all_gray() {
    run_with_usage 70 "$(rate_limits_json 70 70)"
    assert_contains "${lines[0]}" "${GRAY}$(ctx_gauge 70) 70%"
    assert_contains "${lines[1]}" "${GRAY}5h  "
    assert_contains "${lines[2]}" "${GRAY}7d  "
}

@test "thresholds unavailable: shows gray when the hook is missing" {
    use_isolated_statusline
    assert_all_gray
}

@test "thresholds unavailable: shows gray when the hook fails" {
    use_isolated_statusline 'import sys; sys.exit(1)'
    assert_all_gray
}

@test "thresholds unavailable: shows gray when the hook prints nothing" {
    use_isolated_statusline 'pass'
    assert_all_gray
}

@test "thresholds unavailable: shows gray when a key is missing" {
    use_isolated_statusline 'print("{\"context_pct\": 40, \"ratelimit_warn_pct\": 30}")'
    assert_all_gray
}

@test "thresholds unavailable: shows gray when a value is not a positive integer" {
    use_isolated_statusline 'print("{\"context_pct\": \"40\", \"ratelimit_warn_pct\": 30, \"ratelimit_urgent_pct\": 60}")'
    assert_all_gray
}

@test "thresholds available: the isolated copy reads a well-formed hook" {
    # 上の GRAY が「写した場所では何をしても GRAY になる」せいではないことの対照
    use_isolated_statusline 'print("{\"context_pct\": 40, \"ratelimit_warn_pct\": 30, \"ratelimit_urgent_pct\": 60}")'
    run_with_usage 70 "$(rate_limits_json 70 70)"
    assert_contains "${lines[0]}" "${YELLOW}$(ctx_gauge 70) 70%"
    assert_contains "${lines[1]}" "${RED}5h  "
}
