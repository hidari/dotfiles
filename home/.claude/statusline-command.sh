#!/bin/bash
# Claude Code statusline script
# Line 1: account | Model | ◔◑◕● Context% | cost · duration
# Line 2: 5h rate limit progress bar
# Line 3: 7d rate limit progress bar
# Line 4: project [branch] | ± +added/-removed
# Line 5: prompt cache の残り時間 (warm) か、cold で次に払う再キャッシュ量
#
# 1〜3 行目は Claude が持つ状態 (アカウント・モデル・消費)、4 行目はリポジトリが持つ状態。
# キャッシュの行は Claude 側の状態だが、刻々と変わるので一番下に置く。
# 4 行目と 5 行目は出すものが無ければ行ごと省く (空行を出さない)。
#
# アカウント (CLAUDE_CONFIG_DIR) ごとにキャッシュを分ける。
# 分けないと片方のアカウントのレート制限がもう片方の statusLine に表示され、
# フックの発火判定も他方の値で行われる。

# =============================================================================
# ヘルパー関数
# =============================================================================

# ---------- ANSI Colors ----------
# テストが同じ値を source して期待値に使えるよう、ヘルパー関数と同じブロックに置く。
GREEN=$'\e[38;2;151;201;195m'
YELLOW=$'\e[38;2;229;192;123m'
RED=$'\e[38;2;224;108;117m'
GRAY=$'\e[38;2;74;88;92m'
# 2 段階の text color（One Dark 系パレットに整合）
TEXT=$'\e[38;2;220;223;228m'    # primary: model 名など主情報
SUB=$'\e[38;2;168;178;195m'     # secondary: cost / reset 時刻など補助情報
RESET=$'\e[0m'
PURPLE=$'\e[38;5;141m'
CYAN=$'\e[38;5;087m'
PINK=$'\e[38;5;213m'

# ---------- Color by percentage ----------
color_for_pct() {
  local pct="$1"
  if [ -z "$pct" ] || [ "$pct" = "null" ]; then
    printf '%s' "$GRAY"
    return
  fi
  local ipct
  ipct=$(printf "%.0f" "$pct" 2>/dev/null || echo "0")
  if [ "$ipct" -ge 80 ]; then
    printf '%s' "$RED"
  elif [ "$ipct" -ge 50 ]; then
    printf '%s' "$YELLOW"
  else
    printf '%s' "$GREEN"
  fi
}

# ---------- Progress bar (10 segments) ----------
progress_bar() {
  local pct="$1"
  local filled
  filled=$(awk -v p="$pct" 'BEGIN{printf "%d", int(p / 10 + 0.5)}' 2>/dev/null || echo 0)
  [ "$filled" -gt 10 ] 2>/dev/null && filled=10
  [ "$filled" -lt 0 ] 2>/dev/null && filled=0
  local bar=""
  for i in $(seq 1 10); do
    if [ "$i" -le "$filled" ]; then
      bar="${bar}▰"
    else
      bar="${bar}▱"
    fi
  done
  printf '%s' "$bar"
}

# ---------- Context gauge icon (pie chart) ----------
ctx_gauge() {
  local pct="$1"
  if [ "$pct" -ge 75 ] 2>/dev/null; then
    printf '%s' "●"
  elif [ "$pct" -ge 50 ] 2>/dev/null; then
    printf '%s' "◕"
  elif [ "$pct" -ge 25 ] 2>/dev/null; then
    printf '%s' "◑"
  else
    printf '%s' "◔"
  fi
}

# ---------- Format wall duration (ms -> "Xh Ym" / "Xm Ys" / "Zs") ----------
fmt_duration() {
  local ms="$1"
  [ -z "$ms" ] || [ "$ms" = "null" ] && ms=0
  local total_s=$((ms / 1000))
  local h=$((total_s / 3600))
  local m=$(((total_s % 3600) / 60))
  local s=$((total_s % 60))
  if [ "$h" -gt 0 ]; then
    printf '%dh%dm' "$h" "$m"
  elif [ "$m" -gt 0 ]; then
    printf '%dm%ds' "$m" "$s"
  else
    printf '%ds' "$s"
  fi
}

# ---------- アカウント識別 ----------
# CLAUDE_CONFIG_DIR ごとにキャッシュとアカウント情報の置き場が変わる。
# 既定ディレクトリだけが特別扱いされる点が全ての分岐の理由。

# 現在の設定ディレクトリ。未設定なら既定を返す。
account_config_dir() {
  printf '%s' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
}

# 既定の設定ディレクトリかどうか。この判定がキャッシュ名と .claude.json の置き場の
# 分岐条件になるため、定義を 1 箇所に閉じる。
is_default_config_dir() {
  [ "$1" = "$HOME/.claude" ]
}

# 設定ディレクトリを識別する短いタグ。既定は default、それ以外は絶対パスの sha256 先頭 8 桁。
# handoff-sentinel.py の _account_tag が同じ導出を持ち、ここが書いたキャッシュをあちらが読む。
# ずれるとフックが別のファイルを見て通知が無言で止まるので、両者を通した検体で pin してある。
account_tag() {
  local config_dir="$1"
  if is_default_config_dir "$config_dir"; then
    printf 'default'
    return
  fi
  printf '%s' "$config_dir" | shasum -a 256 | cut -c1-8
}

# アカウント情報を持つ .claude.json のパス。
# 既定ディレクトリのときだけ設定ディレクトリの中ではなく $HOME 直下に置かれる。
account_json_path() {
  local config_dir="$1"
  local base="$config_dir"
  if is_default_config_dir "$config_dir"; then
    base="$HOME"
  fi
  printf '%s/.claude.json' "$base"
}

# アカウントのメールアドレス。スクリプトに埋め込まず実データから読むことで、
# コミット対象ファイルに個人情報を置かずに済ませる。
# .claude.json は 100KB を超えるうえ statusLine は描画ごとに走るため、
# 結果をキャッシュし .claude.json が更新されたときだけ読み直す。
account_email() {
  local account_json="$1"
  local cache_file="$2"

  if [ -f "$cache_file" ] && [ -f "$account_json" ] && [ "$cache_file" -nt "$account_json" ]; then
    cat "$cache_file"
    return 0
  fi

  [ -f "$account_json" ] || return 1
  local email
  email=$(jq -r '.oauthAccount.emailAddress // empty' "$account_json" 2>/dev/null)
  [ -n "$email" ] || return 1

  printf '%s' "$email" > "$cache_file"
  printf '%s' "$email"
}

# ---------- Rate limits (Claude Code 本体が stdin で渡す値) ----------
# 自前でプローブを張らない: 推論リクエストなのでリミットを測るためにリミットを消費するうえ、
# 応答をキャッシュすると窓のリセットを跨いだとき失効した窓の使用率を出し続ける。
# 失効した窓は捨てる。本体は落として渡してくるが、キャッシュから読み直す経路
# (本体が値を渡さないとき) では過ぎた窓が残っている。残すとリセット直後に
# 前の窓の高い使用率を出し続ける。
load_rate_limits() {
  local data="$1"
  eval "$(printf '%s' "$data" | jq -r '
    def live(w): if (w.resets_at // 0) > now then w else {} end;
    live(.five_hour // {}) as $f |
    live(.seven_day // {}) as $s |
    "FIVE_HOUR_PCT=" + (($f.used_percentage // "") | tostring | @sh),
    "FIVE_HOUR_RESET=" + (($f.resets_at // "") | tostring | @sh),
    "SEVEN_DAY_PCT=" + (($s.used_percentage // "") | tostring | @sh),
    "SEVEN_DAY_RESET=" + (($s.resets_at // "") | tostring | @sh)
  ' 2>/dev/null)"
}

# ---------- Format reset time (from epoch seconds) ----------
format_epoch_time() {
  local epoch="$1"
  local format="$2"
  [ -z "$epoch" ] || [ "$epoch" = "0" ] && echo "" && return
  local result
  result=$(TZ="Asia/Tokyo" date -j -f "%s" "$epoch" "$format" 2>/dev/null || \
           TZ="Asia/Tokyo" date -d "@${epoch}" "$format" 2>/dev/null || echo "")
  echo "$result"
}

# ---------- Prompt cache (Claude Code 本体が stdin で渡す値) ----------
# warm のうちに次を送れば再キャッシュを払わずに済むので、残り時間と、cold で払う量を出す。
# 第 1 引数は prompt_cache の JSON、第 2 引数は現在時刻 (epoch 秒)。
# 手元の版に無いフィールドや null のフィールドは、その部分だけ飛ばす。
# cold の判定と丸めは jq に寄せ、シェルは並べるだけにする。
prompt_cache_line() {
  local pc_cold="" pc_remaining="" pc_ttl="" pc_hit="" pc_misses="" pc_recache_k="" pc_causes=""
  local assignments
  # warm が true でも期限に達していれば cold として扱う。本体は expires_at に達したときにも
  # statusline を再実行するが、その時点の warm はまだ true のことがある。
  # expires_at が null のときも cold になる。jq の順序では null がどの数よりも小さいので、
  # 期限の比較がそのまま真になる。
  assignments=$(printf '%s' "$1" | jq -r --argjson now "$2" '
    def ttl_seconds:
      if type == "string" and test("^[0-9]+[mh]$")
      then (.[:-1] | tonumber) * {"m": 60, "h": 3600}[.[-1:]]
      else null end;
    .expires_at as $exp |
    (.warm != true or $exp <= $now) as $cold |
    "pc_cold=" + ($cold | tostring),
    "pc_remaining=" + (if $cold then "" else ($exp - $now | floor | tostring) end | @sh),
    "pc_ttl=" + ((.ttl | ttl_seconds // "") | tostring | @sh),
    "pc_hit=" + (if .hit_ratio == null then "" else (.hit_ratio * 100 | round | tostring) end | @sh),
    "pc_misses=" + ((.misses // "") | tostring | @sh),
    "pc_recache_k=" + (if .recache_tokens_if_cold == null then ""
                       else (.recache_tokens_if_cold / 1000 | round | tostring) end | @sh),
    "pc_causes=" + ((.last_miss_cause.causes? // []) | map(tostring) | join(", ") | @sh)
  ' 2>/dev/null) || return 0
  eval "$assignments"

  local line
  if [ "$pc_cold" = "true" ]; then
    line="${RED}cache cold"
    [ -n "$pc_recache_k" ] && line+="  next message re-caches ${pc_recache_k}k tokens"
    [ -n "$pc_causes" ] && line+="  last miss: ${pc_causes}"
  else
    local color="$GREEN"
    [ "$pc_remaining" -le 600 ] && color="$YELLOW"
    # 切り上げる。切り捨てると最後の 1 分未満を 0 分と出す
    local mins=$(((pc_remaining + 59) / 60))
    if [ -n "$pc_ttl" ]; then
      line="${color}cache $(progress_bar $((pc_remaining * 100 / pc_ttl))) ${mins}/$((pc_ttl / 60))m"
    else
      line="${color}cache ${mins}m"
    fi
    local stats=""
    [ -n "$pc_hit" ] && stats="hit ${pc_hit}%"
    [ -n "$pc_misses" ] && stats+="${stats:+, }misses ${pc_misses}"
    [ -n "$stats" ] && line+="  ${stats}"
  fi
  printf '%s' "${line}${RESET}"
}

# =============================================================================
# メイン処理
# =============================================================================

input=$(cat)

# ---------- Parse stdin (single jq call) ----------
# jq 出力を eval で一括代入するため shellcheck は代入を追えない。
# ここで先に宣言して SC2154 (referenced but not assigned) の誤検出を防ぐ。
model_name="" used_pct="" cwd="" lines_added="" lines_removed="" cost_usd="" duration_ms="" rate_limits="" prompt_cache=""
FIVE_HOUR_PCT="" FIVE_HOUR_RESET="" SEVEN_DAY_PCT="" SEVEN_DAY_RESET=""
eval "$(echo "$input" | jq -r '
  "model_name=" + (.model.display_name // "Unknown" | @sh),
  "used_pct=" + (.context_window.used_percentage // 0 | tostring),
  "cwd=" + (.cwd // "" | @sh),
  "lines_added=" + (.cost.total_lines_added // 0 | tostring),
  "lines_removed=" + (.cost.total_lines_removed // 0 | tostring),
  "cost_usd=" + (.cost.total_cost_usd // 0 | tostring),
  "duration_ms=" + (.cost.total_duration_ms // 0 | tostring),
  "rate_limits=" + ((.rate_limits // {}) | tojson | @sh),
  "prompt_cache=" + ((.prompt_cache // {}) | tojson | @sh)
' 2>/dev/null)"

# ---------- Account ----------
CONFIG_DIR=$(account_config_dir)
ACCOUNT_TAG=$(account_tag "$CONFIG_DIR")
ACCOUNT_JSON=$(account_json_path "$CONFIG_DIR")

# 既定アカウントとそれ以外を色で分けるが、色だけに情報を持たせない。
# メールアドレスの文字列そのものが一次情報で、色は補助。
if [ "$ACCOUNT_TAG" = "default" ]; then
  ACCOUNT_COLOR="$CYAN"
else
  ACCOUNT_COLOR="$PINK"
fi

# ---------- Cache (アカウントごとに分離) ----------
# 共有すると 2 アカウントが同じファイルを潰し合い、片方の値でもう片方が表示・発火する。
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/claude"
mkdir -p "$CACHE_DIR" 2>/dev/null && chmod 700 "$CACHE_DIR" 2>/dev/null
RATE_LIMITS_CACHE="$CACHE_DIR/rate-limits-$ACCOUNT_TAG.json"
EMAIL_CACHE_FILE="$CACHE_DIR/account-email-$ACCOUNT_TAG.txt"

account_display=$(account_email "$ACCOUNT_JSON" "$EMAIL_CACHE_FILE" 2>/dev/null || true)

# ---------- Git info ----------
git_branch=""
git_staged=""
git_unstaged=""
project=""
if [ -n "$cwd" ] && [ -d "$cwd" ]; then
  # 作業ツリーの内外は --show-toplevel の成否で判定する。--is-inside-work-tree は
  # 答えを stdout の文字列で返すコマンドで、.git ディレクトリ内や bare リポジトリでは
  # "false" を出力しながら exit 0 を返すため、exit code では判定できない。
  # ここで取得したルートはそのまま project 名の導出に使うので rev-parse も 1 回で済む。
  # .zshrc の _claude_task_list_id とも述語が揃う。
  if project_root=$(git -C "$cwd" --no-optional-locks rev-parse --show-toplevel 2>/dev/null); then
    project=$(basename "$project_root")
    git_branch=$(git -C "$cwd" --no-optional-locks branch --show-current 2>/dev/null || echo "detached")
    if ! git -C "$cwd" --no-optional-locks diff --cached --quiet 2>/dev/null; then
      git_staged="!"
    fi
    if ! git -C "$cwd" --no-optional-locks diff --quiet 2>/dev/null; then
      git_unstaged="+"
    fi
  fi
fi

# ---------- Line stats from stdin ----------
git_stats=""
if [ "$lines_added" -gt 0 ] 2>/dev/null || [ "$lines_removed" -gt 0 ] 2>/dev/null; then
  git_stats="+${lines_added}/-${lines_removed}"
fi

# ---------- Load rate limits ----------
# 本体が値を渡してきたらキャッシュへ書く。handoff-sentinel フックはここを読む。
# 本体はフックへレートリミットを渡さないので、フックへの供給経路はこの 1 本しかない。
#
# 渡してこないとき (セッション開始直後・headless・非サブスク) はキャッシュを消さない。
# 消すと窓がまだ有効なあいだの既知値まで失う。失効の判定は load_rate_limits が行う。
if [ -n "$rate_limits" ] && [ "$rate_limits" != "{}" ]; then
  printf '%s' "$rate_limits" > "$RATE_LIMITS_CACHE"
fi

# 表示は手元の値ではなく必ず書いた先を読む。こうすると画面がフックの読むバイトの
# カナリアになり、書き込みが失敗したときに --% として目に見える。手元の値を表示すると
# 「画面は 96% なのにフックは何も読めていない」が成立し、それを知らせる面がどこにも無い。
if [ -f "$RATE_LIMITS_CACHE" ]; then
  load_rate_limits "$(cat "$RATE_LIMITS_CACHE")"
fi

five_reset_display=""
if [ -n "$FIVE_HOUR_RESET" ]; then
  five_reset_display="Resets at $(format_epoch_time "$FIVE_HOUR_RESET" "+%H:%M") (Asia/Tokyo)"
fi

seven_reset_display=""
if [ -n "$SEVEN_DAY_RESET" ]; then
  seven_reset_display="Resets at $(format_epoch_time "$SEVEN_DAY_RESET" "+%Y-%m-%d %H:%M") (Asia/Tokyo)"
fi

# ---------- Format context used% ----------
ctx_pct_int=0
if [ -n "$used_pct" ] && [ "$used_pct" != "null" ] && [ "$used_pct" != "0" ]; then
  ctx_pct_int=$(printf "%.0f" "$used_pct" 2>/dev/null || echo 0)
fi

# ---------- Line 1 ----------
SEP="${GRAY} │ ${RESET}"
ctx_color=$(color_for_pct "$ctx_pct_int")
ctx_icon=$(ctx_gauge "$ctx_pct_int")

line1=""
if [ -n "$account_display" ]; then
  line1="${ACCOUNT_COLOR}${account_display}${RESET}${SEP}"
fi
line1+="${TEXT}${model_name}${RESET}${SEP}${ctx_color}${ctx_icon} ${ctx_pct_int}%${RESET}"

# Session cost + wall duration（cost が 0 のうちは表示しない: 起動直後のノイズ抑制）
if [ -n "$cost_usd" ] && awk -v c="$cost_usd" 'BEGIN{exit !(c > 0)}'; then
  cost_fmt=$(printf '$%.2f' "$cost_usd")
  dur_fmt=$(fmt_duration "$duration_ms")
  line1+="${SEP}${SUB}${cost_fmt} · ${dur_fmt}${RESET}"
fi

# ---------- Line 2 (5h) ----------
line2=""
if [ -n "$FIVE_HOUR_PCT" ]; then
  c5=$(color_for_pct "$FIVE_HOUR_PCT")
  bar5=$(progress_bar "$FIVE_HOUR_PCT")
  pct5=$(printf "%3.0f%%" "$FIVE_HOUR_PCT")
  line2="${c5}5h  ${bar5}  ${pct5}${RESET}"
  [ -n "$five_reset_display" ] && line2+="  ${SUB}${five_reset_display}${RESET}"
else
  line2="${GRAY}5h  ▱▱▱▱▱▱▱▱▱▱   --%${RESET}"
fi

# ---------- Line 3 (7d) ----------
line3=""
if [ -n "$SEVEN_DAY_PCT" ]; then
  c7=$(color_for_pct "$SEVEN_DAY_PCT")
  bar7=$(progress_bar "$SEVEN_DAY_PCT")
  pct7=$(printf "%3.0f%%" "$SEVEN_DAY_PCT")
  line3="${c7}7d  ${bar7}  ${pct7}${RESET}"
  [ -n "$seven_reset_display" ] && line3+="  ${SUB}${seven_reset_display}${RESET}"
else
  line3="${GRAY}7d  ▱▱▱▱▱▱▱▱▱▱   --%${RESET}"
fi

# ---------- Line 4 (repository) ----------
# git リポジトリの外では空のまま。空文字なら行ごと出さず 3 行に畳む
# (空行を出すと画面に無意味な隙間が残る)。
line4=""
if [ -n "$git_branch" ]; then
  line4="${PURPLE}${project}${RESET} ${CYAN}${git_staged}${git_unstaged}[${git_branch}]${RESET}"
elif [ -n "$project" ]; then
  line4="${PURPLE}${project}${RESET}"
fi

if [ -n "$git_stats" ]; then
  [ -n "$line4" ] && line4+="${SEP}"
  line4+="${GREEN}± ${git_stats}${RESET}"
fi

# ---------- Line 5 (prompt cache) ----------
# 本体は最初の API 応答のあとから prompt_cache を渡す。それまでは行ごと出さない。
line5=""
if [ -n "$prompt_cache" ] && [ "$prompt_cache" != "{}" ]; then
  line5=$(prompt_cache_line "$prompt_cache" "${STATUSLINE_NOW:-$(date +%s)}")
fi

# ---------- Output ----------
# 空の行は省き、行のあいだにだけ改行を置く (最終行に改行を付けない)。
out=("$line1" "$line2" "$line3")
[ -n "$line4" ] && out+=("$line4")
[ -n "$line5" ] && out+=("$line5")
(IFS=$'\n'; printf '%s' "${out[*]}")
