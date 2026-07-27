#!/bin/bash
# Claude Code statusline script
# Line 1: account | Model | ◔◑◕● Context% | cost · duration
# Line 2: 5h rate limit progress bar
# Line 3: 7d rate limit progress bar
# Line 4: project [branch] | ± +added/-removed
#
# 行は情報の所有者で分ける。1〜3 行目は Claude が持つ状態 (アカウント・モデル・消費)、
# 4 行目はリポジトリが持つ状態。git リポジトリの外では 4 行目ごと省く (空行を出さない)。
#
# アカウント (CLAUDE_CONFIG_DIR) ごとに Keychain の service 名とキャッシュを分ける。
# 分けないと片方のアカウントのレート制限がもう片方の statusLine に表示される。

# =============================================================================
# ヘルパー関数
# =============================================================================

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
# CLAUDE_CONFIG_DIR ごとに Keychain の service 名・キャッシュ・アカウント情報の
# 置き場が変わる。既定ディレクトリだけが特別扱いされる点が全ての分岐の理由。

# 現在の設定ディレクトリ。未設定なら既定を返す。
account_config_dir() {
  printf '%s' "${CLAUDE_CONFIG_DIR:-$HOME/.claude}"
}

# 設定ディレクトリを識別する短いタグ。既定は default、それ以外は絶対パスの
# sha256 先頭 8 桁。Claude Code が Keychain の service 名へ付けるサフィックスと
# 同じ導出 (実測で確定)。キャッシュファイル名の分離にも使う。
account_tag() {
  local config_dir="$1"
  if [ "$config_dir" = "$HOME/.claude" ]; then
    printf 'default'
    return
  fi
  printf '%s' "$config_dir" | shasum -a 256 | cut -c1-8
}

# Keychain の service 名。既定ディレクトリのみサフィックス無し。
# 導出した item が存在しないときに無印へフォールバックしてはいけない。
# 他アカウントのトークンでプローブして別アカウントのレート制限を表示してしまう。
account_keychain_service() {
  local tag="$1"
  if [ "$tag" = "default" ]; then
    printf 'Claude Code-credentials'
    return
  fi
  printf 'Claude Code-credentials-%s' "$tag"
}

# アカウント情報を持つ .claude.json のパス。
# 既定ディレクトリのときだけ設定ディレクトリの中ではなく $HOME 直下に置かれる。
account_json_path() {
  local config_dir="$1"
  if [ "$config_dir" = "$HOME/.claude" ]; then
    printf '%s/.claude.json' "$HOME"
    return
  fi
  printf '%s/.claude.json' "$config_dir"
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

# ---------- Rate limit via Haiku probe ----------
fetch_usage() {
  local service="$1"
  local cache_file="$2"

  local token
  token=$(security find-generic-password -s "$service" -w 2>/dev/null || true)
  # item が無いのは「このアカウントの資格情報が取れない」という意味。
  # 他の service 名を試さずここで諦める (誤情報より無情報)。
  [ -z "$token" ] && return 1

  local access_token
  if echo "$token" | jq -e . >/dev/null 2>&1; then
    access_token=$(echo "$token" | jq -r '.claudeAiOauth.accessToken // empty' 2>/dev/null)
  else
    access_token="$token"
  fi
  [ -z "$access_token" ] && return 1

  # Tiny Haiku call (max_tokens=1) to get rate limit response headers
  # -si includes headers in output; -D- writes headers to stdout
  local full_response
  full_response=$(curl -sD- --max-time 8 -o /dev/null \
    -H "Authorization: Bearer ${access_token}" \
    -H "Content-Type: application/json" \
    -H "User-Agent: claude-code/${cc_version:-0.0.0}" \
    -H "anthropic-beta: oauth-2025-04-20" \
    -H "anthropic-version: 2023-06-01" \
    -d '{"model":"claude-haiku-4-5-20251001","max_tokens":1,"messages":[{"role":"user","content":"h"}]}' \
    "https://api.anthropic.com/v1/messages" 2>/dev/null || true)
  local headers="$full_response"
  [ -z "$headers" ] && return 1

  # Parse rate limit headers
  local h5_util h5_reset h7_util h7_reset
  h5_util=$(echo "$headers" | grep -i 'anthropic-ratelimit-unified-5h-utilization' | tr -d '\r' | awk '{print $2}')
  h5_reset=$(echo "$headers" | grep -i 'anthropic-ratelimit-unified-5h-reset' | tr -d '\r' | awk '{print $2}')
  h7_util=$(echo "$headers" | grep -i 'anthropic-ratelimit-unified-7d-utilization' | tr -d '\r' | awk '{print $2}')
  h7_reset=$(echo "$headers" | grep -i 'anthropic-ratelimit-unified-7d-reset' | tr -d '\r' | awk '{print $2}')

  [ -z "$h5_util" ] && return 1

  # Save to cache as JSON
  jq -n \
    --arg h5u "$h5_util" --arg h5r "$h5_reset" \
    --arg h7u "$h7_util" --arg h7r "$h7_reset" \
    '{five_hour_util: $h5u, five_hour_reset: $h5r, seven_day_util: $h7u, seven_day_reset: $h7r}' \
    > "$cache_file"
  return 0
}

load_usage() {
  local data="$1"
  eval "$(echo "$data" | jq -r '
    "FIVE_HOUR_UTIL=" + (.five_hour_util // "" | @sh),
    "FIVE_HOUR_RESET=" + (.five_hour_reset // "" | @sh),
    "SEVEN_DAY_UTIL=" + (.seven_day_util // "" | @sh),
    "SEVEN_DAY_RESET=" + (.seven_day_reset // "" | @sh)
  ' 2>/dev/null)"
}

# ---------- Convert utilization (0.0-1.0) to percentage ----------
to_pct() {
  local val="$1"
  if [ -z "$val" ] || [ "$val" = "null" ] || [ "$val" = "0" ]; then
    echo ""
    return
  fi
  awk -v v="$val" 'BEGIN{printf "%.0f", v * 100}' 2>/dev/null || echo ""
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

# =============================================================================
# メイン処理
# =============================================================================

input=$(cat)

# ---------- ANSI Colors ----------
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

# ---------- Parse stdin (single jq call) ----------
# jq 出力を eval で一括代入するため shellcheck は代入を追えない。
# ここで先に宣言して SC2154 (referenced but not assigned) の誤検出を防ぐ
# (usage 変数 FIVE_HOUR_UTIL 等も load_usage セクションで同様に別途宣言している)。
model_name="" used_pct="" cwd="" lines_added="" lines_removed="" cost_usd="" duration_ms="" cc_version=""
eval "$(echo "$input" | jq -r '
  "model_name=" + (.model.display_name // "Unknown" | @sh),
  "used_pct=" + (.context_window.used_percentage // 0 | tostring),
  "cwd=" + (.cwd // "" | @sh),
  "lines_added=" + (.cost.total_lines_added // 0 | tostring),
  "lines_removed=" + (.cost.total_lines_removed // 0 | tostring),
  "cost_usd=" + (.cost.total_cost_usd // 0 | tostring),
  "duration_ms=" + (.cost.total_duration_ms // 0 | tostring),
  "cc_version=" + (.version // "0.0.0" | @sh)
' 2>/dev/null)"

# ---------- Account ----------
CONFIG_DIR=$(account_config_dir)
ACCOUNT_TAG=$(account_tag "$CONFIG_DIR")
KEYCHAIN_SERVICE=$(account_keychain_service "$ACCOUNT_TAG")
ACCOUNT_JSON=$(account_json_path "$CONFIG_DIR")

# 既定アカウントとそれ以外を色で分けるが、色だけに情報を持たせない。
# メールアドレスの文字列そのものが一次情報で、色は補助。
if [ "$ACCOUNT_TAG" = "default" ]; then
  ACCOUNT_COLOR="$CYAN"
else
  ACCOUNT_COLOR="$PINK"
fi

# ---------- Cache (アカウントごとに分離) ----------
# 共有すると片方のアカウントの使用率がもう片方に TTL 分だけ表示される。
CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/claude"
mkdir -p "$CACHE_DIR" 2>/dev/null && chmod 700 "$CACHE_DIR" 2>/dev/null
CACHE_FILE="$CACHE_DIR/usage-cache-$ACCOUNT_TAG.json"
EMAIL_CACHE_FILE="$CACHE_DIR/account-email-$ACCOUNT_TAG.txt"
CACHE_TTL=360
FIVE_HOUR_UTIL=""
FIVE_HOUR_RESET=""
SEVEN_DAY_UTIL=""
SEVEN_DAY_RESET=""

account_display=$(account_email "$ACCOUNT_JSON" "$EMAIL_CACHE_FILE" 2>/dev/null || true)

# ---------- Git info ----------
git_branch=""
git_staged=""
git_unstaged=""
project=""
if [ -n "$cwd" ] && [ -d "$cwd" ]; then
  if git -C "$cwd" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    project=$(basename "$(git -C "$cwd" --no-optional-locks rev-parse --show-toplevel 2>/dev/null)")
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

# ---------- Load rate limit (cached CACHE_TTL seconds) ----------
USE_CACHE=false
if [ -f "$CACHE_FILE" ]; then
  cache_age=$(( $(date +%s) - $(stat -f '%m' "$CACHE_FILE" 2>/dev/null || echo 0) ))
  if [ "$cache_age" -lt "$CACHE_TTL" ]; then
    USE_CACHE=true
  fi
fi

if $USE_CACHE; then
  load_usage "$(cat "$CACHE_FILE")"
else
  # 失敗時に読み直すのは同じアカウントの古いキャッシュのみ。
  # CACHE_FILE がタグ付きなので他アカウントの値が混ざることはない。
  if fetch_usage "$KEYCHAIN_SERVICE" "$CACHE_FILE"; then
    load_usage "$(cat "$CACHE_FILE")"
  elif [ -f "$CACHE_FILE" ]; then
    load_usage "$(cat "$CACHE_FILE")"
  fi
fi

FIVE_HOUR_PCT=$(to_pct "$FIVE_HOUR_UTIL")
SEVEN_DAY_PCT=$(to_pct "$SEVEN_DAY_UTIL")

five_reset_display=""
if [ -n "$FIVE_HOUR_RESET" ] && [ "$FIVE_HOUR_RESET" != "0" ]; then
  five_reset_display="Resets at $(format_epoch_time "$FIVE_HOUR_RESET" "+%H:%M") (Asia/Tokyo)"
fi

seven_reset_display=""
if [ -n "$SEVEN_DAY_RESET" ] && [ "$SEVEN_DAY_RESET" != "0" ]; then
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
  pct5=$(printf "%3s%%" "$FIVE_HOUR_PCT")
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
  pct7=$(printf "%3s%%" "$SEVEN_DAY_PCT")
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

# ---------- Output ----------
# 最終行にだけ改行を付けない。4 行目の有無で最終行が変わるため分岐する。
printf '%s\n' "$line1"
printf '%s\n' "$line2"
if [ -n "$line4" ]; then
  printf '%s\n' "$line3"
  printf '%s' "$line4"
else
  printf '%s' "$line3"
fi
