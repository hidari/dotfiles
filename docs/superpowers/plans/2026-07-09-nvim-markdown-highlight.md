# Neovim Markdown ハイライト強化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** conceal も行全体背景も使わず、色だけで Markdown の要素を描き分ける。

**Architecture:** 配色を副作用のない純粋テーブル (`config.markdown`) に切り出し、適用を `config.appearance` の `apply()` に一本化する。`apply()` は起動時と `ColorScheme` のたびに呼ばれる。見出しマーカー `#` は既定のクエリに独立キャプチャが無いため、`after/queries/markdown/highlights.scm` の `;; extends` で `@markup.heading.marker` を追加する。

**Tech Stack:** Neovim 0.12.3 組み込み treesitter、`nvim_set_hl`、bats、GitHub Actions composite action

設計は `docs/superpowers/specs/2026-07-09-nvim-markdown-highlight-design.md` (commit d29d3fe)。

## Global Constraints

- Neovim は開発機の v0.12.3 に合わせる。CI も同じバージョンを pin する。
- nvim プラグインを追加しない。`nvim_set_hl` と treesitter クエリ拡張だけで完結させる。
- `conceallevel` を変更しない。既定の `0` のまま運用する。
- `Normal` の `bg = "NONE"` による端末背景の透過を壊さない。
- bats の `@test` 名は ASCII のみ。日本語の説明はテスト本文のコメントに書く (`rules/bats-test-name-ascii-only.yml`)。
- コード内のコメントは日本語で書く。
- ファイルの末尾は空行 1 つにする。
- コミットメッセージ本文に全角の句読点と全角括弧を使わない。日本語メッセージは `git commit -F <file>` で渡す (`-m` は tirith が弾く)。
- 作業ブランチは `feature/nvim-markdown-highlight`。リポジトリの作業ツリーが `~/.config` の live symlink の実体なので、他ブランチへ `git checkout` しない。

---

### Task 1: Markdown 配色テーブルと拡張クエリ

**Files:**
- Create: `home/.config/nvim/lua/config/markdown.lua`
- Create: `home/.config/nvim/after/queries/markdown/highlights.scm`
- Test: `scripts/tests/nvim-markdown-probe.lua`
- Test: `scripts/tests/nvim-markdown.bats`

**Interfaces:**
- Consumes: なし
- Produces:
  - `require("config.markdown")` はハイライトグループ名 (`string`) から `nvim_set_hl` の第 3 引数テーブルへの写像を返す。副作用なし。
  - `scripts/tests/nvim-markdown-probe.lua` は `HEADING_LEVELS=<int>` / `HEADING_FG_DUPLICATES=<int>` / `MISSING_CAPTURES=<カンマ区切り>` / `MARKER_CAPTURES=<int>` を標準出力へ 1 行ずつ出す。
  - `scripts/tests/nvim-markdown.bats` は bash 関数 `probe_with_extends` と `probe_without_extends` を持つ。

- [ ] **Step 1: プローブを書く**

`scripts/tests/nvim-markdown-probe.lua` を作成する。

```lua
-- nvim の Markdown 配色の不変条件を headless で観測し KEY=VALUE 形式で出力する。
-- 判定は呼び出し側 (scripts/tests/nvim-markdown.bats) が行う。
--
-- nvim --clean で起動される前提。user config を読まないので lazy.nvim は動かず、
-- markdown / markdown_inline のパーサは Neovim 本体同梱のものが使われる。

local palette = require("config.markdown")

-- 見出し 1..6 の fg が互いに異なること。同色だと階層が読めない
local levels, duplicates, seen = 0, 0, {}
for level = 1, 6 do
    local group = palette["@markup.heading." .. level]
    if group and group.fg then
        levels = levels + 1
        if seen[group.fg] then
            duplicates = duplicates + 1
        end
        seen[group.fg] = true
    end
end
print("HEADING_LEVELS=" .. levels)
print("HEADING_FG_DUPLICATES=" .. duplicates)

-- 定義したグループ名が実際のキャプチャ集合に含まれること。
-- 含まれないグループへ色を定義しても Neovim はエラーを出さず黙って無視する。
-- 強調やリンクは markdown_inline 由来なので両方の和集合をとる。
local captures = {}
for _, lang in ipairs({ "markdown", "markdown_inline" }) do
    local query = vim.treesitter.query.get(lang, "highlights")
    if query then
        for _, name in ipairs(query.captures) do
            captures["@" .. name] = true
        end
    end
end
local missing = {}
for group in pairs(palette) do
    if not captures[group] then
        missing[#missing + 1] = group
    end
end
table.sort(missing)
print("MISSING_CAPTURES=" .. table.concat(missing, ","))

-- 拡張クエリが 6 段階すべての見出しマーカーを捕捉すること
local buffer = vim.api.nvim_create_buf(false, true)
vim.api.nvim_buf_set_lines(buffer, 0, -1, false, {
    "# h1", "## h2", "### h3", "#### h4", "##### h5", "###### h6",
})
local tree = vim.treesitter.get_parser(buffer, "markdown"):parse(true)[1]
local query = vim.treesitter.query.get("markdown", "highlights")
local markers = 0
for id in query:iter_captures(tree:root(), buffer, 0, -1) do
    if query.captures[id] == "markup.heading.marker" then
        markers = markers + 1
    end
end
print("MARKER_CAPTURES=" .. markers)
```

- [ ] **Step 2: 失敗するテストを書く**

`scripts/tests/nvim-markdown.bats` を作成する。

```bash
#!/usr/bin/env bats
# =============================================================================
# nvim の Markdown 配色の不変条件を headless で検証する
#
# 注意:
# - bats は @test 名を関数名へエンコードするため名前は ASCII に限る
#   (rules/bats-test-name-ascii-only.yml)
# - nvim --clean は user config を読まないので lazy.nvim が起動せず、プラグインの
#   clone もパーサのビルドも起きない。markdown / markdown_inline のパーサは本体同梱。
# - after/queries は rtp の独立したエントリとして足す必要がある (自動では入らない)。
# =============================================================================

load test_helper

NVIM_CONFIG_DIR="$REPO_ROOT/home/.config/nvim"
PROBE="$REPO_ROOT/scripts/tests/nvim-markdown-probe.lua"

# skip ガード自体を検証できるように、実行する nvim を差し替え可能にする。
# bats と nvim が同じディレクトリに入るため PATH から隠す方式は使えない。
NVIM_BIN="${NVIM_BIN:-nvim}"

setup() {
    if ! command -v "$NVIM_BIN" >/dev/null 2>&1; then
        # CI では Neovim の導入失敗を skip で隠さない。
        # 緑のまま何も検証していない状態が一番危ない
        if [ -n "${CI:-}" ]; then
            echo "nvim is required in CI but was not found" >&2
            return 1
        fi
        skip "nvim is not installed"
    fi
}

# 本番と同じ rtp 構成 (拡張クエリを含む) でプローブを走らせる
probe_with_extends() {
    "$NVIM_BIN" --clean --headless \
        --cmd "set rtp+=$NVIM_CONFIG_DIR" \
        --cmd "set rtp+=$NVIM_CONFIG_DIR/after" \
        -c "luafile $PROBE" -c 'qa!' 2>&1
}

# 拡張クエリを外して走らせる。検査が本当に効いていることを示す negative case 用
probe_without_extends() {
    "$NVIM_BIN" --clean --headless \
        --cmd "set rtp+=$NVIM_CONFIG_DIR" \
        -c "luafile $PROBE" -c 'qa!' 2>&1
}

@test "markdown palette: six heading levels are defined" {
    run probe_with_extends
    [[ "$output" == *"HEADING_LEVELS=6"* ]]
}

@test "markdown palette: heading levels have distinct foreground colors" {
    # 見出しが同色だと階層が読めない。これが元の不満そのもの
    run probe_with_extends
    [[ "$output" == *"HEADING_FG_DUPLICATES=0"* ]]
}

@test "markdown palette: every group exists as a treesitter capture" {
    # 存在しないグループへ色を定義しても Neovim は黙って無視するので静的に弾く
    run probe_with_extends
    [[ "$output" == *"MISSING_CAPTURES="* ]]
    [[ "$output" != *"MISSING_CAPTURES=@"* ]]
}

@test "extends query captures all six atx heading markers" {
    run probe_with_extends
    [[ "$output" == *"MARKER_CAPTURES=6"* ]]
}

@test "without the extends query the marker checks fail" {
    # 上の 2 つの検査が拡張クエリに支えられていることを示す
    # (拡張を外しても緑のままなら、その検査は何も守っていない)
    run probe_without_extends
    [[ "$output" == *"MARKER_CAPTURES=0"* ]]
    [[ "$output" == *"MISSING_CAPTURES=@markup.heading.marker"* ]]
}
```

- [ ] **Step 3: テストを走らせて落ちることを確認する**

Run: `bats scripts/tests/nvim-markdown.bats`

Expected: 5 件すべて失敗。`config.markdown` が存在しないため `module 'config.markdown' not found` が出る。

- [ ] **Step 4: 配色テーブルを書く**

`home/.config/nvim/lua/config/markdown.lua` を作成する。

```lua
-- Markdown の配色。
--
-- 副作用を持たず、ハイライトグループ名から nvim_set_hl の引数テーブルへの写像だけを返す。
-- 適用は config.appearance の apply() が一手に引き受ける (colorscheme で消えるため再適用が要る)。
--
-- conceal は使わない。記号を隠す代わりに MUTED で暗くして視覚的に後退させる。
-- 見出しは明度を上げて本文より目立たせ、階層は色相で分ける。
--
-- @markup.heading.marker は after/queries/markdown/highlights.scm が定義する拡張キャプチャで、
-- 既定のクエリには存在しない。

-- マークアップ記号に使う色。本文より暗くして視覚的に後退させる
local MUTED = "#5c6370"

return {
    -- 見出し: 階層を色相で分け、本文より明るくする
    ["@markup.heading.1"] = { fg = "#7fdfd0", bold = true },
    ["@markup.heading.2"] = { fg = "#f0d399", bold = true },
    ["@markup.heading.3"] = { fg = "#d8a0f0", bold = true },
    ["@markup.heading.4"] = { fg = "#8ac6f7", bold = true },
    ["@markup.heading.5"] = { fg = "#b5dd9b", bold = true },
    ["@markup.heading.6"] = { fg = "#7fd4dd", bold = true },

    -- 見出しの # 記号だけを引っ込める (拡張クエリ由来のキャプチャ)
    ["@markup.heading.marker"] = { fg = MUTED },

    -- 引用の > 、表の | 、水平線の ---
    ["@punctuation.special"] = { fg = MUTED },

    -- リストマーカー ( - や 1. )
    ["@markup.list"] = { fg = "#56b6c2" },

    -- 強調
    ["@markup.strong"] = { fg = "#dcdfe4", bold = true },
    ["@markup.italic"] = { italic = true },
    ["@markup.strikethrough"] = { fg = "#6f7aa5", strikethrough = true },

    -- コード: インラインは目立たせ、ブロックは注入された言語の色を邪魔しない
    ["@markup.raw"] = { fg = "#e06c75" },
    ["@markup.raw.block"] = { fg = "#8f9dcc" },
    ["@label"] = { fg = MUTED },

    -- 引用文
    ["@markup.quote"] = { fg = "#98c379", italic = true },

    -- リンク
    ["@markup.link.label"] = { fg = "#61afef", underline = true },
    ["@markup.link.url"] = { fg = MUTED, underline = true },

    -- チェックボックス
    ["@markup.list.checked"] = { fg = "#98c379" },
    ["@markup.list.unchecked"] = { fg = "#6f7aa5" },
}
```

- [ ] **Step 5: 拡張クエリを書く**

`home/.config/nvim/after/queries/markdown/highlights.scm` を作成する。1 行目の `;; extends` は既定クエリを置き換えず追記するための指示なので、必ず先頭に置く。

```scheme
;; extends

; 見出しマーカー (# ## ...) を見出し本体と別グループへ分け、色を分けられるようにする。
; 既定クエリの @markup.heading.N は "# H1" の行全体を覆っており、マーカー単独のキャプチャが無い。
; 拡張クエリのキャプチャは既定より後に評価されるため、範囲が重なったときに後勝ちする。
(atx_h1_marker) @markup.heading.marker
(atx_h2_marker) @markup.heading.marker
(atx_h3_marker) @markup.heading.marker
(atx_h4_marker) @markup.heading.marker
(atx_h5_marker) @markup.heading.marker
(atx_h6_marker) @markup.heading.marker
```

- [ ] **Step 6: テストを走らせて通ることを確認する**

Run: `bats scripts/tests/nvim-markdown.bats`

Expected: `5 tests, 0 failures`

- [ ] **Step 7: 変異注入で「見出しが同色」を検出できることを確認する**

`home/.config/nvim/lua/config/markdown.lua` の `@markup.heading.2` の `fg` を一時的に `"#7fdfd0"` (H1 と同じ) に書き換える。

Run: `bats scripts/tests/nvim-markdown.bats`

Expected: `markdown palette: heading levels have distinct foreground colors` が失敗する。

確認できたら `"#f0d399"` に戻し、再度 `bats scripts/tests/nvim-markdown.bats` で `5 tests, 0 failures` に戻ることを確認する。

- [ ] **Step 8: 変異注入で「存在しないグループ」を検出できることを確認する**

`home/.config/nvim/lua/config/markdown.lua` の `return {` の直後に一時的に次の 1 行を足す。

```lua
    ["@does.not.exist"] = { fg = "#ff0000" },
```

Run: `bats scripts/tests/nvim-markdown.bats`

Expected: `markdown palette: every group exists as a treesitter capture` が失敗し、出力に `MISSING_CAPTURES=@does.not.exist` が現れる。

確認できたらその 1 行を削除し、再度 `bats scripts/tests/nvim-markdown.bats` で `5 tests, 0 failures` に戻ることを確認する。

- [ ] **Step 9: コミットする**

```bash
cat > tmp/commitmsg.txt <<'EOF'
feat: nvim の Markdown 配色を追加し treesitter クエリを拡張する

- config.markdown を新設し、副作用のない純粋テーブルとして配色を持つ
  - 見出しは階層を色相で分け、本文より明るくする
  - マークアップ記号は本文より暗くして視覚的に後退させる (conceal は使わない)
- after/queries/markdown/highlights.scm で atx_h1_marker..atx_h6_marker を捕捉する
  - 既定クエリの @markup.heading.N は行全体を覆いマーカー単独のキャプチャが無い
  - 拡張クエリのキャプチャは既定より後に評価されるため後勝ちする
- scripts/tests/nvim-markdown.bats で headless 検証する
  - nvim --clean は lazy.nvim を通さず、markdown パーサは Neovim 本体同梱
  - 拡張クエリを外すと検査が落ちることまでテストで固定する
  - 変異注入 (見出しを同色にする / 存在しないグループを足す) で赤を確認済み
EOF
git add home/.config/nvim/lua/config/markdown.lua \
        home/.config/nvim/after/queries/markdown/highlights.scm \
        scripts/tests/nvim-markdown-probe.lua \
        scripts/tests/nvim-markdown.bats
git commit -F tmp/commitmsg.txt
```

---

### Task 2: 適用の一本化と colorscheme 耐性

**Files:**
- Modify: `home/.config/nvim/lua/config/appearance.lua` (全面書き換え)
- Modify: `scripts/tests/nvim-markdown-probe.lua` (末尾に追記)
- Modify: `scripts/tests/nvim-markdown.bats` (末尾に追記)

**Interfaces:**
- Consumes: `require("config.markdown")` (Task 1)
- Produces: `require("config.appearance")` は `{ apply = fun() }` を返す。`require` した時点で `apply()` が 1 回走り、`ColorScheme` autocmd が登録される。プローブは `NORMAL_BG` / `H1_FG` / `AFTER_CS_NORMAL_BG` / `AFTER_CS_H1_FG` を追加で出力する。

- [ ] **Step 1: プローブに適用側の観測を追記する**

`scripts/tests/nvim-markdown-probe.lua` の末尾に追記する。

```lua

-- ここから適用側の観測。config.appearance は require した時点で apply() を 1 回走らせ、
-- ColorScheme autocmd を登録する。
require("config.appearance")

local function highlight(name)
    return vim.api.nvim_get_hl(0, { name = name, link = false })
end

print("NORMAL_BG=" .. tostring(highlight("Normal").bg))
print("H1_FG=" .. tostring(highlight("@markup.heading.1").fg))

-- colorscheme の読み込みは hi clear を伴うため、autocmd が無いと定義が消える
vim.cmd("colorscheme habamax")
print("AFTER_CS_NORMAL_BG=" .. tostring(highlight("Normal").bg))
print("AFTER_CS_H1_FG=" .. tostring(highlight("@markup.heading.1").fg))
```

- [ ] **Step 2: 失敗するテストを追記する**

`scripts/tests/nvim-markdown.bats` の末尾に追記する。

```bash

@test "appearance keeps the Normal background transparent" {
    # Normal の bg=NONE を壊すと端末背景の透過が失われる
    run probe_with_extends
    [[ "$output" == *"NORMAL_BG=nil"* ]]
}

@test "highlights survive a colorscheme load" {
    # colorscheme は hi clear を伴う。ColorScheme autocmd が無いと透過も配色も消える
    run probe_with_extends
    before=$(printf '%s\n' "$output" | sed -n 's/^H1_FG=//p')
    after=$(printf '%s\n' "$output" | sed -n 's/^AFTER_CS_H1_FG=//p')
    [ -n "$before" ]
    [ "$before" != "nil" ]
    [ "$before" = "$after" ]
    [[ "$output" == *"AFTER_CS_NORMAL_BG=nil"* ]]
}
```

- [ ] **Step 3: テストを走らせて落ちることを確認する**

Run: `bats scripts/tests/nvim-markdown.bats`

Expected: `appearance keeps the Normal background transparent` は通る (現在の `appearance.lua` も `Normal` を `NONE` にしている)。`highlights survive a colorscheme load` が失敗する。`H1_FG` は現在の既定配色の値になり、`AFTER_CS_H1_FG` は `habamax` の値に変わるため一致しない。

- [ ] **Step 4: appearance.lua を書き換える**

`home/.config/nvim/lua/config/appearance.lua` の内容を次で置き換える。

```lua
-- エディタ全体のハイライト定義。
--
-- colorscheme を読み込むと nvim_set_hl の定義は hi clear で消える。
-- そこで起動時と ColorScheme のたびに同じ apply() を通して貼り直す。
-- (lazy.nvim の install.colorscheme はプラグイン導入時に colorscheme を読む)

local M = {}

-- markdown の配色は副作用を持たない純粋テーブルとして config.markdown が持つ
local markdown = require("config.markdown")

local base = {
    -- ターミナルの背景をそのまま透過させる
    Normal = { bg = "NONE", ctermbg = "NONE" },
    NormalNC = { bg = "NONE", ctermbg = "NONE" },

    -- 行番号（通常は teal、カーソル行は gold で太字）
    LineNr = { fg = "#53c9b8", bg = "NONE" },
    CursorLineNr = { fg = "#e5c07b", bg = "NONE", bold = true },

    -- neo-treeの隠しファイル/gitignore対象が灰色すぎて見えない対策
    NeoTreeDotfile = { fg = "#8f9dcc" },       -- ドットファイル（読みやすい青みグレー）
    NeoTreeHiddenByName = { fg = "#8f9dcc" },  -- 名前で隠される項目も同色
    NeoTreeGitIgnored = { fg = "#6f7aa5" },    -- gitignore対象は少し暗めで区別
}

function M.apply()
    for group, opts in pairs(base) do
        vim.api.nvim_set_hl(0, group, opts)
    end
    for group, opts in pairs(markdown) do
        vim.api.nvim_set_hl(0, group, opts)
    end
end

M.apply()

vim.api.nvim_create_autocmd("ColorScheme", {
    group = vim.api.nvim_create_augroup("dotfiles_appearance", { clear = true }),
    callback = M.apply,
})

return M
```

`init.lua` は変更しない。`require("config.appearance")` が読み込み時に `apply()` を呼び、autocmd を登録する。

- [ ] **Step 5: テストを走らせて通ることを確認する**

Run: `bats scripts/tests/nvim-markdown.bats`

Expected: `7 tests, 0 failures`

- [ ] **Step 6: 変異注入で colorscheme 耐性の欠落を検出できることを確認する**

`home/.config/nvim/lua/config/appearance.lua` の `vim.api.nvim_create_autocmd(...)` のブロック全体を一時的にコメントアウトする。

Run: `bats scripts/tests/nvim-markdown.bats`

Expected: `highlights survive a colorscheme load` が失敗する。

確認できたらコメントを外し、再度 `bats scripts/tests/nvim-markdown.bats` で `7 tests, 0 failures` に戻ることを確認する。

- [ ] **Step 7: 実機の nvim で起動エラーが無いことを確認する**

Run: `nvim --headless -c 'lua print(vim.g.colors_name)' -c 'qa!'`

Expected: `nil` とだけ出力され、エラーが出ない。

- [ ] **Step 8: コミットする**

```bash
cat > tmp/commitmsg.txt <<'EOF'
feat: ハイライト適用を apply() に一本化し colorscheme 耐性を持たせる

colorscheme の読み込みは hi clear を伴い、nvim_set_hl の定義を消す。
実測で Normal.bg が nil (透過) から不透明へ変わることを確認した。
lazy.nvim の install.colorscheme はプラグイン導入時に colorscheme を読むため、
既存の透過設定と LineNr の色も同じ脆さを持っていた。

- appearance.lua に apply() を置き、base と config.markdown をまとめて適用する
- ColorScheme autocmd から同じ apply() を呼び、消えた定義を貼り直す
- 透過と配色が colorscheme 読込後も生き残ることをテストで固定する
  - autocmd をコメントアウトすると赤になることを変異注入で確認済み
- LineNr のコメントが実際の色 (teal) と食い違っていたので直す
EOF
git add home/.config/nvim/lua/config/appearance.lua \
        scripts/tests/nvim-markdown-probe.lua \
        scripts/tests/nvim-markdown.bats
git commit -F tmp/commitmsg.txt
```

---

### Task 3: 実端末での確認と `@conceal` の判断

**Files:**
- Modify: `home/.config/nvim/lua/config/markdown.lua` (`@conceal` を足すか否か)

**Interfaces:**
- Consumes: Task 1 の `config.markdown`、Task 2 の `config.appearance`
- Produces: なし (配色テーブルに 1 行増えるかもしれない)

headless では描画が走らず `vim.inspect_pos` が空を返すため、ここだけは実端末で確認する。

- [ ] **Step 1: 確認用の Markdown を用意する**

`tmp/` は gitignore されている。Markdown のコードフェンスを heredoc へ入れるため、外側のフェンスはバッククォート 4 つにしてある。

````bash
cat > tmp/probe.md <<'EOF'
# H1
## H2
### H3

**bold** *italic* ~~strike~~ `inline code`

> 引用文

- リスト
- [ ] 未完了
- [x] 完了

[リンク](https://example.com)

```lua
local x = 1
```
EOF
````

- [ ] **Step 2: 実端末で開き termguicolors を確認する**

Run: `nvim tmp/probe.md` を Ghostty で開き、`:lua print(vim.o.termguicolors)` を実行する。

Expected: `true`。`false` の場合は 24bit color が有効になっておらず、hex 指定の色が反映されない。その場合は `vim.opt.termguicolors = true` を `options.lua` に足し、Task 2 のテストに影響しないことを確認してからコミットする。

- [ ] **Step 3: 見出しの階層が色で区別できることを目視する**

Expected: `# H1` `## H2` `### H3` が異なる色で表示され、行頭の `#` `##` `###` は本文より暗い。

- [ ] **Step 4: `@conceal` が `**` を暗くできるか確認する**

`vim.inspect_pos` で `**bold**` の最初のアスタリスク (5 行目、桁 0) に当たるハイライトを列挙する。

Run: `:lua print(vim.inspect(vim.tbl_map(function(t) return t.hl_group end, vim.inspect_pos(0, 4, 0).treesitter)))`

Expected: `@markup.strong` と `@conceal` の両方が並ぶ。後に現れるほうが優先される。

- [ ] **Step 5: 判断して反映する**

`@conceal` が `@markup.strong` の後に現れる場合、`home/.config/nvim/lua/config/markdown.lua` の `-- 強調` ブロックの直前に次の 1 行を足す。

```lua
    -- インラインの記号 ( * ~ ` ) を引っ込める。markdown_inline の @conceal キャプチャ
    ["@conceal"] = { fg = MUTED },
```

`@conceal` が先に現れる (優先されない) 場合は何も足さない。

Run: `bats scripts/tests/nvim-markdown.bats`

Expected: `7 tests, 0 failures`。`@conceal` は `markdown_inline` のキャプチャなので `MISSING_CAPTURES` には入らない。

- [ ] **Step 6: コミットする**

`@conceal` を足した場合のみコミットする。足さなかった場合はこの Step を飛ばし、spec の「実装時に確認する項目」に結果を追記して Task 4 へ進む。

```bash
cat > tmp/commitmsg.txt <<'EOF'
feat: インラインのマークアップ記号を暗くする

markdown_inline の @conceal キャプチャは * ~ ` の記号に当たる。
実端末で @markup.strong より後に評価されることを確認したため、
conceal を使わずに記号だけを引っ込められる。
EOF
git add home/.config/nvim/lua/config/markdown.lua
git commit -F tmp/commitmsg.txt
```

---

### Task 4: CI で Neovim を pin してテストを回す

**Files:**
- Create: `.github/actions/setup-neovim/action.yml`
- Modify: `.github/workflows/test.yml` (`bats` ジョブ)

**Interfaces:**
- Consumes: `scripts/tests/nvim-markdown.bats` (Task 1, Task 2)
- Produces: なし

CI の `bats` ジョブは `bats scripts/tests/` でディレクトリごと実行するため、テストファイルの登録は不要。Neovim を PATH に置くだけでよい。

- [ ] **Step 1: composite action を作る**

`.github/actions/setup-neovim/action.yml` を作成する。`setup-bats` と同じく tarball をバージョン pin して展開する。

```yaml
name: Setup Neovim
description: Neovim をバージョン pin した公式 tarball から取得し PATH に追加するローカル composite action。markdown パーサは本体同梱のため tree-sitter CLI も C コンパイラも不要。

runs:
  using: composite
  steps:
    - name: Install Neovim
      shell: bash
      run: |
        nvim_version="v0.12.3" # 開発機と揃える
        curl --proto '=https' --tlsv1.2 -fsSL "https://github.com/neovim/neovim/releases/download/${nvim_version}/nvim-linux-x86_64.tar.gz" | tar -xz -C "$RUNNER_TEMP"
        echo "$RUNNER_TEMP/nvim-linux-x86_64/bin" >> "$GITHUB_PATH"
```

- [ ] **Step 2: bats ジョブに Neovim のセットアップを足す**

`.github/workflows/test.yml` の `bats` ジョブの `Setup Bats` ステップの直後に足す。

```yaml
      - name: Setup Neovim
        uses: ./.github/actions/setup-neovim
```

変更後の `bats` ジョブは次の形になる。

```yaml
  bats:
    name: bootstrap.sh (bats)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7

      - name: Setup Bats
        uses: ./.github/actions/setup-bats

      - name: Setup Neovim
        uses: ./.github/actions/setup-neovim

      - name: Run Bats tests
        run: bats scripts/tests/
```

- [ ] **Step 3: tarball の展開先が正しいことをローカルで確認する**

Run: `curl --proto '=https' --tlsv1.2 -fsSL "https://github.com/neovim/neovim/releases/download/v0.12.3/nvim-linux-x86_64.tar.gz" | tar -tz | head -2`

Expected:

```
nvim-linux-x86_64/bin/
nvim-linux-x86_64/bin/nvim
```

- [ ] **Step 4: テスト全体がローカルで通ることを確認する**

Run: `bats scripts/tests/`

Expected: すべて pass。`nvim-markdown.bats` の 7 件を含む。

- [ ] **Step 5: skip ガードが CI で効かないことを確認する**

`bats` と `nvim` は同じディレクトリ (`/opt/homebrew/bin`) に入るため、PATH から nvim だけを隠すことはできない。`NVIM_BIN` を存在しない名前に差し替えて検証する。

Run: `NVIM_BIN=nvim-not-installed bats scripts/tests/nvim-markdown.bats`

Expected: 7 件すべて `skipped (nvim is not installed)`。ローカルで nvim が無い環境では skip される。

Run: `CI=true NVIM_BIN=nvim-not-installed bats scripts/tests/nvim-markdown.bats`

Expected: 7 件すべて失敗し、`nvim is required in CI but was not found` が出力される。CI で Neovim の導入に失敗したとき、テストが黙って skip されて緑になることを防ぐ。

- [ ] **Step 6: コミットする**

```bash
cat > tmp/commitmsg.txt <<'EOF'
ci: bats ジョブで Neovim を pin して Markdown 配色テストを回す

markdown / markdown_inline のパーサは Neovim 本体に同梱されているため、
CI には Neovim を 1 つ入れるだけでよい。tree-sitter CLI も C コンパイラも不要。
テストは nvim --clean で起動し lazy.nvim を通さないのでプラグインの clone も起きない。

- setup-neovim composite action を setup-bats と同じ流儀で追加する
- バージョンは開発機に合わせて v0.12.3 を pin する
- bats ジョブは scripts/tests/ をディレクトリごと実行するため登録は不要
EOF
git add .github/actions/setup-neovim/action.yml .github/workflows/test.yml
git commit -F tmp/commitmsg.txt
```

---

## 完了後

`dev-workflow:pre-merge-quality-gate` を通してから PR を作る。PR #48 のブランチから分岐しているため、base は `feature/herdr-agent-cycle-keys` を指定するか、#48 のマージ後に `main` へ rebase する。
