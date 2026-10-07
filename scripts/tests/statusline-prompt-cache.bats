#!/usr/bin/env bats
# =============================================================================
# statusline-command.sh のプロンプトキャッシュの行
# =============================================================================
#
# Claude Code 本体は statusLine の入力に prompt_cache を渡す。warm のうちに次を送れば
# 再キャッシュを払わずに済むので、残り時間と、cold になったときに払う量を最下行に出す。
#   - prompt_cache が無いあいだは行ごと出さない (空行も出さない)
#   - warm は緑、残り 600 秒以下は黄色、cold は赤
#   - warm が true でも expires_at が null か現在時刻以下なら cold として出す
#   - 手元の版に無いフィールドや null のフィールドは、その部分だけ飛ばす
#
# 現在時刻は STATUSLINE_NOW で固定する。実時刻に依存すると残り分数が揺れる。

load test_helper

NOW=2000000000

setup() {
    setup_test_home
    unset CLAUDE_CONFIG_DIR
    export XDG_CACHE_HOME="$TEST_HOME/cache"
    export STATUSLINE_NOW="$NOW"
    # 色の定数をスクリプトから読み、期待値に literal のエスケープを書き写さない
    load_statusline_functions
}

teardown() {
    teardown_test_home
}

# warm で 38 分残り (2280 秒 / 3600 秒) の基準形。第 1 引数の jq フィルタで 1 箇所ずつ崩す。
# フィルタの中では $now が現在時刻を指す。
prompt_cache_json() {
    jq -cn --argjson now "$NOW" "
        {warm: true, ttl: \"1h\", expires_at: (\$now + 2280), hit_ratio: 0.91, misses: 0,
         last_miss_cause: null, recache_tokens_if_cold: 82600}
        | ${1:-.}"
}

# statusline を prompt_cache 付きで実行し、最下行を CACHE_LINE に入れる。
# 行数はリポジトリの内外で変わるので、位置ではなく最後の要素で取る。
run_cache_line() {
    run_statusline_in "" "" "$1"
    [ "$status" -eq 0 ]
    CACHE_LINE="${lines[${#lines[@]}-1]}"
}

# =============================================================================
# 行の有無と位置
# =============================================================================

@test "prompt_cache: emits no cache line when the field is absent" {
    # $lines は末尾の空行を落とすので、空行を出していても要素数では見えない。改行数で見る
    statusline_raw "$TEST_HOME/out.txt"

    [ "$(count_newlines "$TEST_HOME/out.txt")" -eq 2 ]
    refute_contains "$(cat "$TEST_HOME/out.txt")" "cache"
}

@test "prompt_cache: emits no cache line when the field is null" {
    statusline_raw "$TEST_HOME/out.txt" "" "null"

    [ "$(count_newlines "$TEST_HOME/out.txt")" -eq 2 ]
    refute_contains "$(cat "$TEST_HOME/out.txt")" "cache"
}

@test "prompt_cache: appends the cache line last without a trailing newline" {
    statusline_raw "$TEST_HOME/out.txt" "" "$(prompt_cache_json)"

    [ "$(count_newlines "$TEST_HOME/out.txt")" -eq 3 ]
    assert_contains "$(tail -n 1 "$TEST_HOME/out.txt")" "cache"
}

@test "prompt_cache: puts the cache line below the repository line" {
    setup_test_repo "$TEST_HOME/myrepo"

    run_statusline_in "$TEST_HOME/myrepo" "" "$(prompt_cache_json)"

    [ "$status" -eq 0 ]
    [ "${#lines[@]}" -eq 5 ]
    assert_contains "${lines[3]}" "myrepo"
    assert_contains "${lines[4]}" "cache"
}

# =============================================================================
# warm
# =============================================================================

@test "prompt_cache: shows a green bar, remaining minutes, hit and misses while warm" {
    # バーの塗りは round(2280 / 3600 * 10) = 6
    run_cache_line "$(prompt_cache_json)"

    [ "$CACHE_LINE" = "${GREEN}cache ▰▰▰▰▰▰▱▱▱▱ 38/60m  hit 91%, misses 0${RESET}" ]
}

@test "prompt_cache: rounds the remaining minutes up" {
    # 2281 秒は 38 分と 1 秒。切り捨てると期限前に 38 と出し続ける
    run_cache_line "$(prompt_cache_json '.expires_at = $now + 2281')"

    assert_contains "$CACHE_LINE" " 39/60m"
}

@test "prompt_cache: turns yellow at exactly 600 seconds left" {
    run_cache_line "$(prompt_cache_json '.expires_at = $now + 600')"

    [ "$CACHE_LINE" = "${YELLOW}cache ▰▰▱▱▱▱▱▱▱▱ 10/60m  hit 91%, misses 0${RESET}" ]
}

@test "prompt_cache: stays green at 601 seconds left" {
    run_cache_line "$(prompt_cache_json '.expires_at = $now + 601')"

    [ "$CACHE_LINE" = "${GREEN}cache ▰▰▱▱▱▱▱▱▱▱ 11/60m  hit 91%, misses 0${RESET}" ]
}

@test "prompt_cache: uses the 5m ttl as the denominator" {
    # 5m の ttl は残りが常に 600 秒以下なので、warm の間ずっと黄色になる
    run_cache_line "$(prompt_cache_json '.ttl = "5m" | .expires_at = $now + 180')"

    [ "$CACHE_LINE" = "${YELLOW}cache ▰▰▰▰▰▰▱▱▱▱ 3/5m  hit 91%, misses 0${RESET}" ]
}

@test "prompt_cache: shows hit 0% rather than skipping a zero ratio" {
    # 0 は値であって欠損ではない。null と同じ扱いにすると最悪の状態が見えなくなる
    run_cache_line "$(prompt_cache_json '.hit_ratio = 0')"

    assert_contains "$CACHE_LINE" "  hit 0%, misses 0"
}

@test "prompt_cache: keeps the last miss cause off the warm line" {
    run_cache_line "$(prompt_cache_json '.last_miss_cause = {causes: ["tools_changed"]}')"

    refute_contains "$CACHE_LINE" "last miss"
}

# =============================================================================
# cold の判定
# =============================================================================
#
# 3 つの条件は独立に cold を作る。1 つのテストにまとめると、落とした条件が残りの条件に
# 隠れて緑のままになる。

@test "prompt_cache: is cold when warm is false" {
    run_cache_line "$(prompt_cache_json '.warm = false')"

    [ "$CACHE_LINE" = "${RED}cache cold  next message re-caches 83k tokens${RESET}" ]
}

@test "prompt_cache: is cold when warm but expires_at is null" {
    run_cache_line "$(prompt_cache_json '.expires_at = null')"

    [ "$CACHE_LINE" = "${RED}cache cold  next message re-caches 83k tokens${RESET}" ]
}

@test "prompt_cache: is cold when warm but expires_at has been reached" {
    # 本体は expires_at に達したときに statusline を再実行するが、その時点の warm は
    # まだ true のことがある。期限そのものを見ないと 0/60m の緑を出す
    run_cache_line "$(prompt_cache_json '.expires_at = $now')"

    [ "$CACHE_LINE" = "${RED}cache cold  next message re-caches 83k tokens${RESET}" ]
}

@test "prompt_cache: rounds the re-cache tokens to the nearest k" {
    run_cache_line "$(prompt_cache_json '.warm = false | .recache_tokens_if_cold = 82499')"
    assert_contains "$CACHE_LINE" "re-caches 82k tokens"

    run_cache_line "$(prompt_cache_json '.warm = false | .recache_tokens_if_cold = 82500')"
    assert_contains "$CACHE_LINE" "re-caches 83k tokens"
}

@test "prompt_cache: appends the last miss causes on the cold line" {
    run_cache_line "$(prompt_cache_json '.warm = false | .last_miss_cause = {causes: ["tools_changed", "ttl_expired_5m"]}')"

    [ "$CACHE_LINE" = "${RED}cache cold  next message re-caches 83k tokens  last miss: tools_changed, ttl_expired_5m${RESET}" ]
}

# =============================================================================
# 欠けたフィールド
# =============================================================================
#
# フィールドは版によって無いことがあり (last_miss_cause は v2.1.260 以降)、あっても null に
# なることがある。どちらもその部分だけを飛ばし、行の残りは出す。

@test "prompt_cache: skips hit when hit_ratio is null" {
    run_cache_line "$(prompt_cache_json '.hit_ratio = null')"

    [ "$CACHE_LINE" = "${GREEN}cache ▰▰▰▰▰▰▱▱▱▱ 38/60m  misses 0${RESET}" ]
}

@test "prompt_cache: skips hit when hit_ratio is absent" {
    run_cache_line "$(prompt_cache_json 'del(.hit_ratio)')"

    [ "$CACHE_LINE" = "${GREEN}cache ▰▰▰▰▰▰▱▱▱▱ 38/60m  misses 0${RESET}" ]
}

@test "prompt_cache: skips misses when it is absent" {
    run_cache_line "$(prompt_cache_json 'del(.misses)')"

    [ "$CACHE_LINE" = "${GREEN}cache ▰▰▰▰▰▰▱▱▱▱ 38/60m  hit 91%${RESET}" ]
}

@test "prompt_cache: ends at the remaining minutes when hit and misses are both missing" {
    run_cache_line "$(prompt_cache_json 'del(.hit_ratio) | .misses = null')"

    [ "$CACHE_LINE" = "${GREEN}cache ▰▰▰▰▰▰▱▱▱▱ 38/60m${RESET}" ]
}

@test "prompt_cache: skips the bar and the denominator when ttl is absent" {
    run_cache_line "$(prompt_cache_json 'del(.ttl)')"

    [ "$CACHE_LINE" = "${GREEN}cache 38m  hit 91%, misses 0${RESET}" ]
}

@test "prompt_cache: prints cause strings literally rather than evaluating them" {
    # 原因の文字列は eval を通る。クォートが抜けると入力がコマンドとして走る
    local marker="$TEST_HOME/evaluated"
    run_cache_line "$(prompt_cache_json ".warm = false | .last_miss_cause = {causes: [\"\$(touch $marker)\"]}")"

    [ ! -e "$marker" ]
    assert_contains "$CACHE_LINE" "last miss: \$(touch $marker)"
}

@test "prompt_cache: skips the bar and the denominator when ttl is zero" {
    # 分母が 0 だとバーの計算がゼロ除算で落ち、行ごと消える
    run_cache_line "$(prompt_cache_json '.ttl = "0m"')"

    [ "$CACHE_LINE" = "${GREEN}cache 38m  hit 91%, misses 0${RESET}" ]
}

@test "prompt_cache: skips the re-cache tokens when they are null" {
    # compaction の直後などに null になる
    run_cache_line "$(prompt_cache_json '.warm = false | .recache_tokens_if_cold = null')"

    [ "$CACHE_LINE" = "${RED}cache cold${RESET}" ]
}

@test "prompt_cache: skips the re-cache tokens when they are absent" {
    run_cache_line "$(prompt_cache_json '.warm = false | del(.recache_tokens_if_cold) | .last_miss_cause = {causes: ["tools_changed"]}')"

    [ "$CACHE_LINE" = "${RED}cache cold  last miss: tools_changed${RESET}" ]
}

@test "prompt_cache: skips the last miss when last_miss_cause is absent" {
    run_cache_line "$(prompt_cache_json '.warm = false | del(.last_miss_cause)')"

    [ "$CACHE_LINE" = "${RED}cache cold  next message re-caches 83k tokens${RESET}" ]
}
