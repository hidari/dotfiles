# nvim カラーパレット再設計 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** nvim の Markdown ハイライトと neo-tree の配色を、ターミナル透過後の実効背景に対してコントラストが保証された色へ置き換え、その保証をテストで固定する。

**Architecture:** 色を `config/palette.lua` に単一の真実として集約し、`markdown.lua` と新設 `neotree.lua` がそこを参照する写像を返す。`appearance.lua` が 3 つのテーブルを合成して適用する。テストは palette を require してコントラスト比を実測し、tier の目標未達を検出する。写像ファイルへの hex ハードコードは ast-grep で構文レベルに禁止する。

**Tech Stack:** Neovim 0.12.3 (Lua), bats, ast-grep 0.44, pre-commit

## Global Constraints

- 設計の根拠は `docs/superpowers/specs/2026-07-10-nvim-contrast-palette-design.md` にある。基準背景と目標コントラストの値は `config/palette.lua` にのみ書き、散文やコメントに再掲しない。
- コード内のコメントは日本語で書く。
- ファイルの末尾は必ず 1 つの空行にする。
- bats の `@test` 名は ASCII のみ (`rules/bats-test-name-ascii-only.yml` が検査する)。
- bats のテスト本体で裸の `[[ ]]` を使わない (`rules/bats-no-bare-double-bracket.yml` が検査する)。アサーションは `test_helper.bash` の `assert_contains` / `refute_contains` を使う。
- 色の hex リテラルは `home/.config/nvim/lua/config/palette.lua` にのみ書く。この制約が及ぶ範囲は nvim の Lua (`home/.config/nvim/lua/**`) であり、ast-grep もその範囲だけを検査する。テストの probe (`scripts/tests/`) は検査ロジックの較正と negative case のために既知の色をリテラルで持つ。これは意図的な例外である。
- コミットメッセージ本文に全角の句読点や全角括弧を使わない。半角の区切りと改行で構造化する。メッセージはリポジトリ内の `tmp/commitmsg.txt` (gitignore 済み) に書き、`git commit -F tmp/commitmsg.txt` で渡す (argv を ASCII に保つため `-m` は使わない)。
- 各タスクの最後に `bats scripts/tests/` が全緑であることを確認してからコミットする。
- リポジトリのワーキングツリーは `~/.config/nvim` の symlink 実体である。ブランチを切り替えると live 設定が壊れるため、このブランチ上で作業を積む。

## 前提となる経緯

前回の PR #50 の final review で、同じ 2 ファイルに対して次の 2 点が記録されている。今回はどちらも回収する。

- 見出し 6 色に色相の意図を示すコメントが無く、H1 と H6 が近似した teal なのが意図か事故か読めない (今回 H6 の色相を振り直し、隣接色相差 30 度以上を確保する)
- hex リテラル `#8f9dcc` と `#6f7aa5` の共有は当時「per-file データ保持は妥当、結合は premature」と判断して見送った (今回は結合する。理由は結合そのものではなく、基準背景に対するコントラストを機械検査するには色と tier を一箇所に集める必要があるため。検査は palette の `colors` を走査するので、写像側に直接書かれた色は検査を素通りしてしまう)

---

### Task 1: palette.lua を新設し、コントラスト検査をテストへ組み込む

色トークンを一箇所へ集め、「全トークンが tier の目標コントラストを満たす」ことをテストで固定する。まず現行の色のまま palette を作って RED を出し、検査が本当に働くことを確認してから新色へ差し替える。

**Files:**
- Create: `home/.config/nvim/lua/config/palette.lua`
- Modify: `scripts/tests/nvim-markdown-probe.lua`
- Test: `scripts/tests/nvim-markdown.bats`

**Interfaces:**
- Produces: `require("config.palette")` が `reference_background` (string), `minimum_contrast` (tier 名から number への表), `colors` (token 名から `{ hex, tier }` への表), `hex` (token 名から string への表) を持つテーブルを返す。Task 2 と Task 3 は `palette.hex.<token>` だけを使う。

- [ ] **Step 1: 現行の色のまま palette.lua を作る**

この時点では色は変えない。tier だけを宣言する。現行色は目標を満たさないので、次のステップで RED になるのが正しい。

`home/.config/nvim/lua/config/palette.lua`:

```lua
-- 配色の色トークン。
--
-- reference_background は、ターミナルの背景を透過させた結果として文字の背後に
-- 実際に現れる色のうち、最も明るくなるケースを取っている。
--
-- 導出:
--   Ghostty のテーマ Mariana の背景 #343d46 を background-opacity 0.8 で背後のウィンドウと
--   合成する。背後が白いとき 0.8 * #343d46 + 0.2 * #ffffff となり、この値になる。
--   スクリーンショットの実測最頻色と一致することを確認済み。
--   背後が黒いときは #2a3138 まで暗くなるが、暗い方向はコントラストが上がるだけなので、
--   明るい方 (最悪ケース) を基準に取れば全ての状況で読める。
--
-- 前提: Ghostty の theme = Mariana と background-opacity = 0.8。
--       ~/.config/ghostty/config は dotfiles の symlink 管理下にないため、他のマシンでは再現されない。
--
-- 記号を暗くして後退させることはできない。実効背景は明るい方向にしか動かず、
-- 暗い前景は必ず背景に溶ける。後退は彩度を落として表現する。
--
-- 各色は tier を持ち、基準背景に対する WCAG コントラスト比の下限を宣言する。
-- 検査は scripts/tests/nvim-markdown-probe.lua が行う。

local M = {}

M.reference_background = "#5d646b"

-- tier ごとの最低コントラスト比。
-- 本文の前景 (Mariana の #d8dee9) が基準背景に対して 4.44:1 で、これが事実上の上限になる。
M.minimum_contrast = {
    text = 4.0, -- 読む前景
    accent = 3.5, -- 補助的に読む前景
    symbol = 3.0, -- 意図的に後退させる記号
    decoration = 2.0, -- 装飾
}

-- 複数のトークンが共有する色。hex を一箇所にまとめて drift を防ぐ。
local RECEDED = "#6f7aa5"
local LEAF_GREEN = "#98c379"

M.colors = {
    heading_1 = { hex = "#7fdfd0", tier = "text" },
    heading_2 = { hex = "#f0d399", tier = "text" },
    heading_3 = { hex = "#d8a0f0", tier = "text" },
    heading_4 = { hex = "#8ac6f7", tier = "text" },
    heading_5 = { hex = "#b5dd9b", tier = "text" },
    heading_6 = { hex = "#7fd4dd", tier = "text" },

    strong = { hex = "#dcdfe4", tier = "text" },

    muted = { hex = "#5c6370", tier = "symbol" },

    inline_code = { hex = "#e06c75", tier = "accent" },
    code_block = { hex = "#8f9dcc", tier = "accent" },
    list_marker = { hex = "#56b6c2", tier = "accent" },
    link_label = { hex = "#61afef", tier = "accent" },
    quote = { hex = LEAF_GREEN, tier = "accent" },
    checked = { hex = LEAF_GREEN, tier = "accent" },

    strikethrough = { hex = RECEDED, tier = "symbol" },
    unchecked = { hex = RECEDED, tier = "symbol" },

    line_number = { hex = "#53c9b8", tier = "accent" },
    cursor_line_number = { hex = "#e5c07b", tier = "accent" },

    dotfile = { hex = "#8f9dcc", tier = "symbol" },
    gitignored = { hex = RECEDED, tier = "symbol" },
    git_attention = { hex = "#ff8700", tier = "text" },
    indent_guide = { hex = "#4c4c4c", tier = "decoration" },
}

-- 写像側が使う平坦な表。colors から導出するので二重管理にならない。
M.hex = {}
for token, spec in pairs(M.colors) do
    M.hex[token] = spec.hex
end

return M
```

- [ ] **Step 2: probe に既存の変数名の衝突を解消する rename を入れる**

現行の probe は `local palette = require("config.markdown")` と命名しているが、これから本物の palette を require するため名前が衝突する。先に markdown 側をリネームする。

`scripts/tests/nvim-markdown-probe.lua` の先頭を次のように変える。

```lua
local markdown = require("config.markdown")
local palette = require("config.palette")
```

そのうえで、ファイル中の `palette` という参照を `markdown` へ置き換える。宣言 1 箇所のほかに参照が 3 箇所ある。

- 見出しループの `palette["@markup.heading." .. level]`
- MISSING_CAPTURES ループの `for group in pairs(palette) do`
- MUTED_FG を逆算している `palette["@conceal.markdown_inline"].fg`

置き換え後に `grep -n 'palette' scripts/tests/nvim-markdown-probe.lua` を実行し、残るのが `require("config.palette")` の宣言と、次のステップで足すコントラスト検査だけであることを確かめる。

- [ ] **Step 3: probe にコントラスト検査を追加する**

`scripts/tests/nvim-markdown-probe.lua` の末尾 (`AFTER_CS_H1_FG` を print している行の後) に追記する。

```lua

-- ---------------------------------------------------------------------------
-- パレットのコントラスト検査
--
-- 基準背景と tier ごとの目標値は config.palette が単一の真実として持つ。
-- ここでは WCAG 2.x の相対輝度を計算するだけで、期待値は持たない。
-- ---------------------------------------------------------------------------

-- sRGB のガンマを解いて線形化する
local function linearize(byte)
    local c = byte / 255
    if c <= 0.03928 then
        return c / 12.92
    end
    return ((c + 0.055) / 1.055) ^ 2.4
end

local function relative_luminance(hex)
    local r = linearize(tonumber(hex:sub(2, 3), 16))
    local g = linearize(tonumber(hex:sub(4, 5), 16))
    local b = linearize(tonumber(hex:sub(6, 7), 16))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
end

local function contrast_ratio(fg, bg)
    local lf, lb = relative_luminance(fg), relative_luminance(bg)
    local hi, lo = math.max(lf, lb), math.min(lf, lb)
    return (hi + 0.05) / (lo + 0.05)
end

-- 検査ロジック自体の較正。白と黒は 21:1、同色どうしは 1:1 になる。
-- ここが崩れていたら以降の判定は全て無意味なので先に固定する。
-- 同色の検査には基準背景を使う。値を書き写すと palette と drift する
print(string.format("CONTRAST_SELFTEST_MAX=%.2f", contrast_ratio("#ffffff", "#000000")))
print(string.format(
    "CONTRAST_SELFTEST_MIN=%.2f",
    contrast_ratio(palette.reference_background, palette.reference_background)
))

local violations = {}
for token, spec in pairs(palette.colors) do
    local target = palette.minimum_contrast[spec.tier]
    if target == nil then
        violations[#violations + 1] = token .. ":unknown-tier"
    else
        local ratio = contrast_ratio(spec.hex, palette.reference_background)
        if ratio < target then
            violations[#violations + 1] = string.format("%s:%.2f<%.2f", token, ratio, target)
        end
    end
end
table.sort(violations)
print("PALETTE_VIOLATIONS=" .. table.concat(violations, ","))
print("PALETTE_VIOLATION_COUNT=" .. #violations)

-- 検出器が働いていることを示す negative case。
-- 旧 MUTED (#5c6370) は基準背景の上で背景とほぼ同色になり symbol tier に届かない。
-- ここが 0 になったらコントラスト検査は何も守っていない
local sentinel_ratio = contrast_ratio("#5c6370", palette.reference_background)
print("VIOLATION_DETECTOR_WORKS=" .. ((sentinel_ratio < palette.minimum_contrast.symbol) and 1 or 0))
print(string.format("SENTINEL_RATIO=%.2f", sentinel_ratio))
```

- [ ] **Step 4: bats にテストを追加する**

`scripts/tests/nvim-markdown.bats` の末尾に追記する。

```bash

@test "contrast helper is calibrated against known values" {
    # 白と黒は 21:1、同色は 1:1。ここが崩れたら以降の判定は全て無意味
    run probe_with_extends
    assert_contains "$output" "CONTRAST_SELFTEST_MAX=21.00"
    assert_contains "$output" "CONTRAST_SELFTEST_MIN=1.00"
}

@test "palette: the contrast check detects a color below its tier" {
    # 検査が本当に効いていることを示す negative case。
    # 旧 MUTED は基準背景の上で 1.01:1 しかなく symbol tier を満たさない
    run probe_with_extends
    assert_contains "$output" "VIOLATION_DETECTOR_WORKS=1"
    assert_contains "$output" "SENTINEL_RATIO=1.01"
}

@test "palette: every token meets the contrast target of its tier" {
    # 基準背景の上で読めない色をパレットへ入れられないようにする
    run probe_with_extends
    assert_contains "$output" "PALETTE_VIOLATION_COUNT=0"
}
```

- [ ] **Step 5: テストを実行して RED を確認する**

Run: `bats scripts/tests/nvim-markdown.bats`

Expected:
- `contrast helper is calibrated against known values` が PASS
- `palette: the contrast check detects a color below its tier` が PASS
- `palette: every token meets the contrast target of its tier` が **FAIL**

FAIL の出力に `PALETTE_VIOLATION_COUNT=` が 0 以外の値で現れ、`PALETTE_VIOLATIONS=` に `muted:1.01<3.00` や `gitignored:1.43<3.00` が並ぶことを目視で確認する。これが確認できなければ検査は機能していない。

- [ ] **Step 6: palette.lua を新色へ差し替える**

`M.colors` とその上の共有色のローカル変数を、次の内容へ置き換える。他の部分は変えない。

```lua
-- 複数のトークンが共有する色。hex を一箇所にまとめて drift を防ぐ。
local RECEDED = "#aab6e4"
local LEAF_GREEN = "#a7d388"

M.colors = {
    -- 見出し: 階層を色相で分ける。OKLCh 色相環で隣接色相差 30 度以上を確保している
    heading_1 = { hex = "#83e4d4", tier = "text" },
    heading_2 = { hex = "#f0d399", tier = "text" },
    heading_3 = { hex = "#edc5ff", tier = "text" },
    heading_4 = { hex = "#aad9ff", tier = "text" },
    heading_5 = { hex = "#b6df9c", tier = "text" },
    heading_6 = { hex = "#8ee0f1", tier = "text" },

    strong = { hex = "#dcdfe4", tier = "text" },

    -- マークアップ記号とファイラの薄字。彩度を元の 30% まで落として後退させる
    muted = { hex = "#b5b8bc", tier = "symbol" },

    -- 赤は高輝度で sRGB のガマットが痩せる。text tier まで上げると淡いピンクになり
    -- コードであることの手がかりが失われるため accent tier に置いて赤みを残す
    inline_code = { hex = "#ffb2b4", tier = "accent" },
    code_block = { hex = "#b6c5f5", tier = "accent" },
    list_marker = { hex = "#75d4e1", tier = "accent" },
    link_label = { hex = "#90ccff", tier = "accent" },
    quote = { hex = LEAF_GREEN, tier = "accent" },
    checked = { hex = LEAF_GREEN, tier = "accent" },

    strikethrough = { hex = RECEDED, tier = "symbol" },
    unchecked = { hex = RECEDED, tier = "symbol" },

    line_number = { hex = "#64d9c7", tier = "accent" },
    cursor_line_number = { hex = "#e6c17b", tier = "accent" },

    -- ファイラ
    dotfile = { hex = "#a8b6e7", tier = "symbol" },
    gitignored = { hex = RECEDED, tier = "symbol" },
    -- git が注意を促す状態 (未追跡 / 衝突 / unstaged)。
    -- neo-tree は git status の色を filtered の色より後に上書きするため、
    -- この色はファイル名そのものに乗る。したがって読む前景として text tier に置く
    git_attention = { hex = "#ffc8a1", tier = "text" },
    -- ツリーのインデント線は装飾なので、見えるが目立たない位置に置く
    indent_guide = { hex = "#959594", tier = "decoration" },
}
```

- [ ] **Step 7: テストを実行して GREEN を確認する**

Run: `bats scripts/tests/`

Expected: 全テストが PASS。`not ok` が 1 件も出ないこと。

この時点では `markdown.lua` はまだ palette を参照していないので、実際の配色は変わっていない。`SCOPED_MUTED_APPLIED` などの既存テストは `markdown.lua` の旧色を見て緑のままである。

- [ ] **Step 8: コミットする**

```bash
mkdir -p tmp
cat > tmp/commitmsg.txt <<'EOF'
feat: nvim の色トークンを palette.lua へ集約しコントラストを検査する

- reference_background は Ghostty Mariana #343d46 を background-opacity 0.8 で
  背後の白いウィンドウと合成した最悪ケースの実効背景
- 各色に tier を持たせ 基準背景に対する WCAG コントラスト比の下限を宣言する
- probe が palette を require して全トークンの比を実測し 未達を列挙する
- 検出器が働くことを negative case で固定する
  旧 MUTED #5c6370 は 1.01:1 で symbol tier に届かない
- 白と黒が 21:1 同色が 1:1 になることで検査ロジック自体を較正する
- RED を確認してから新色へ差し替えた
EOF
git add home/.config/nvim/lua/config/palette.lua scripts/tests/nvim-markdown-probe.lua scripts/tests/nvim-markdown.bats
git commit -F tmp/commitmsg.txt
```

---

### Task 2: markdown.lua を palette 参照へ移し、リンク記号をスコープ付きで定義する

`markdown.lua` から hex を追い出し、`@markup.link.markdown_inline` を新たに定義する。このキャプチャが捕捉するのは URL ではなくリンクの記号 (`[` `]` `(` `)` `!`) である。

**Files:**
- Modify: `home/.config/nvim/lua/config/markdown.lua`
- Modify: `scripts/tests/nvim-markdown-probe.lua`
- Test: `scripts/tests/nvim-markdown.bats`

**Interfaces:**
- Consumes: `require("config.palette").hex` (Task 1 が提供)
- Produces: `require("config.markdown")` はハイライトグループ名から `nvim_set_hl` の引数テーブルへの表を返す (これは既存の契約であり変わらない)

- [ ] **Step 1: 描画と同じ経路で解決する検査を probe へ追加する**

Neovim の highlighter は `runtime/lua/vim/treesitter/highlighter.lua` で `'@' .. capture .. '.' .. lang` を組み立てて `nvim_get_hl_id_by_name` に渡す。既存の `GLOBAL_BLEED` はグループ名を直接引いているだけなので、描画と同じ経路に寄せて忠実にする。

`scripts/tests/nvim-markdown-probe.lua` の `GLOBAL_BLEED` を print している行の直後 (`SCOPED_MUTED_APPLIED` のループより前) に次を追記する。`MUTED_FG` はその時点で定義済みである。

```lua

-- highlighter (runtime/lua/vim/treesitter/highlighter.lua) が実際に使う解決経路。
-- キャプチャ名と言語から '@<capture>.<lang>' を組み立てて引く。
-- 定義が無ければ素の '@<capture>' へフォールバックする
local function resolved_fg(capture, lang)
    local id = vim.api.nvim_get_hl_id_by_name("@" .. capture .. "." .. lang)
    return vim.api.nvim_get_hl(0, { id = id, link = false }).fg
end

-- リンクの記号は markdown_inline でだけ muted になり、他言語へは漏れない
print("LINK_SCOPED_IN_MARKDOWN=" .. ((resolved_fg("markup.link", "markdown_inline") == MUTED_FG) and 1 or 0))
print("LINK_NO_BLEED_TO_LUA=" .. ((resolved_fg("markup.link", "lua") ~= MUTED_FG) and 1 or 0))
```

- [ ] **Step 2: bats にテストを追加する**

`scripts/tests/nvim-markdown.bats` の末尾に追記する。

```bash

@test "link punctuation is scoped to markdown_inline" {
    # @markup.link が捕捉するのは URL ではなくリンクの記号 ( [ ] ( ) ! ) である。
    # 素で定義すると lua など他の文法へ muted が漏れるため言語スコープへ逃がす。
    # 解決経路は highlighter.lua と同じ '@<capture>.<lang>' を使う
    run probe_with_extends
    assert_contains "$output" "LINK_SCOPED_IN_MARKDOWN=1"
    assert_contains "$output" "LINK_NO_BLEED_TO_LUA=1"
}
```

- [ ] **Step 3: テストを実行して RED を確認する**

Run: `bats scripts/tests/nvim-markdown.bats -f "link punctuation"`

Expected: FAIL。`LINK_SCOPED_IN_MARKDOWN=0` が出力される (まだ `@markup.link.markdown_inline` を定義していないため、解決結果が nil で MUTED_FG と一致しない)。

- [ ] **Step 4: markdown.lua を書き換える**

`home/.config/nvim/lua/config/markdown.lua` を全面的に置き換える。

```lua
-- Markdown の配色。
--
-- 副作用を持たず、ハイライトグループ名から nvim_set_hl の引数テーブルへの写像だけを返す。
-- 色は config.palette が単一の真実として持つ。
-- 適用は config.appearance の apply() が一手に引き受ける (colorscheme で消えるため再適用が要る)。
--
-- conceal 機能 (テキストを隠す conceallevel) は使わず、conceallevel は 0 のまま。
-- @conceal.markdown_inline は tree-sitter のキャプチャ名であり、記号を隠さず色を当てるためだけに使う。
-- 見出しは明度を上げて本文より目立たせ、階層は色相で分ける。色相だけに頼らないよう bold も併用する。
--
-- @markup.heading.marker は after/queries/markdown/highlights.scm が定義する拡張キャプチャで、
-- 既定のクエリには存在しない。
--
-- @punctuation.special / @conceal / @label / @markup.link は他の文法とも共有する汎用キャプチャ名なので、
-- 素で定義すると非 markdown のバッファへ色が漏れる。言語サフィックス付き
-- (@<capture>.markdown / @<capture>.markdown_inline) にすると tree-sitter highlighter が
-- その言語でだけ解決し (vim/treesitter/highlighter.lua の @<name>.<lang> 構築)、
-- 他言語では素の @<capture> にフォールバックするため漏れが止まる。
--
-- @markup.link が捕捉するのは URL ではなくリンクの記号 ( [ ] ( ) ! ) である。
-- 参照リンク [label][ref] の [ref] は @markup.link.label の後に @markup.link が評価されて
-- 後勝ちするため、[ref] 全体が muted になる (実測で確認済みの既知の挙動)。

local hex = require("config.palette").hex

return {
    -- 見出し: 階層を色相で分け、本文より明るくする
    ["@markup.heading.1"] = { fg = hex.heading_1, bold = true },
    ["@markup.heading.2"] = { fg = hex.heading_2, bold = true },
    ["@markup.heading.3"] = { fg = hex.heading_3, bold = true },
    ["@markup.heading.4"] = { fg = hex.heading_4, bold = true },
    ["@markup.heading.5"] = { fg = hex.heading_5, bold = true },
    ["@markup.heading.6"] = { fg = hex.heading_6, bold = true },

    -- 見出しの # 記号だけを引っ込める (拡張クエリ由来のキャプチャ)
    ["@markup.heading.marker"] = { fg = hex.muted },

    -- 引用の > 、表の | 、水平線の --- (markdown ブロック文法)
    ["@punctuation.special.markdown"] = { fg = hex.muted },

    -- リストマーカー ( - や 1. )
    ["@markup.list"] = { fg = hex.list_marker },

    -- インラインの記号 ( * ~ ` ) を引っ込める。markdown_inline の @conceal キャプチャ
    ["@conceal.markdown_inline"] = { fg = hex.muted },

    -- リンクの記号 ( [ ] ( ) ! ) を引っ込める
    ["@markup.link.markdown_inline"] = { fg = hex.muted },

    -- 強調
    ["@markup.strong"] = { fg = hex.strong, bold = true },
    ["@markup.italic"] = { italic = true },
    ["@markup.strikethrough"] = { fg = hex.strikethrough, strikethrough = true },

    -- コード: インラインは目立たせ、ブロックは注入された言語の色を邪魔しない
    ["@markup.raw"] = { fg = hex.inline_code },
    ["@markup.raw.block"] = { fg = hex.code_block },
    -- コードフェンスの言語ラベル (markdown ブロック文法)
    ["@label.markdown"] = { fg = hex.muted },

    -- 引用文
    ["@markup.quote"] = { fg = hex.quote, italic = true },

    -- リンク
    ["@markup.link.label"] = { fg = hex.link_label, underline = true },
    ["@markup.link.url"] = { fg = hex.muted, underline = true },

    -- チェックボックス
    ["@markup.list.checked"] = { fg = hex.checked },
    ["@markup.list.unchecked"] = { fg = hex.unchecked },
}
```

- [ ] **Step 5: probe の MUTED_FG の取得元を palette へ移す**

`markdown.lua` が palette を参照するようになったので、probe の逆算をやめて palette から直接取る。

変更前:

```lua
local MUTED_FG = tonumber(markdown["@conceal.markdown_inline"].fg:sub(2), 16)
```

変更後:

```lua
local MUTED_FG = tonumber(palette.hex.muted:sub(2), 16)
```

同じ箇所の直前にあるコメントも、逆算の説明ではなく palette 参照の説明へ書き換える。

```lua
-- 汎用キャプチャ名がグローバルへ muted を漏らしていないことを保証する。
-- markdown.lua は @<capture>.<lang> でスコープするので、他言語が共有する素の @<capture> は
-- muted を帯びてはならない。色は palette から直接取る
```

- [ ] **Step 6: probe の SCOPED_MUTED_APPLIED に新しいグループを足す**

`SCOPED_MUTED_APPLIED` のループのリストへ `"@markup.link.markdown_inline"` を追加する。

```lua
for _, name in ipairs({
    "@punctuation.special.markdown",
    "@conceal.markdown_inline",
    "@label.markdown",
    "@markup.link.markdown_inline",
}) do
```

同様に `GLOBAL_BLEED` のループのリストへ `"@markup.link"` を追加する。

```lua
for _, name in ipairs({ "@punctuation.special", "@conceal", "@label", "@markup.link" }) do
```

- [ ] **Step 7: テストを実行して GREEN を確認する**

Run: `bats scripts/tests/`

Expected: 全テストが PASS。特に次が緑であること。

- `link punctuation is scoped to markdown_inline`
- `scoped palette does not bleed muted into global capture groups`
- `markdown palette: every group exists as a treesitter capture`
- `palette: every token meets the contrast target of its tier`

`MISSING_CAPTURES` が空であることは、`@markup.link` が markdown_inline の実在キャプチャであることを保証している。

- [ ] **Step 8: コミットする**

```bash
mkdir -p tmp
cat > tmp/commitmsg.txt <<'EOF'
feat: markdown の配色を palette 参照へ移しリンク記号を後退させる

- markdown.lua から hex を追い出し config.palette の hex を参照する
- @markup.link.markdown_inline を新設する
  このキャプチャが捕捉するのは URL ではなくリンクの記号 ( [ ] ( ) ! ) で
  これまで色が未指定で本文色のまま前に出ていた
- 素で定義すると lua など他文法へ漏れることを実測したためスコープ付きにする
- 検査を highlighter.lua と同じ解決経路 ( '@<capture>.<lang>' を
  nvim_get_hl_id_by_name へ渡す ) に寄せて忠実にする
- 参照リンク [label][ref] の [ref] は @markup.link が後勝ちして
  全体が muted になる 既知の挙動として受容しコメントに残す
EOF
git add home/.config/nvim/lua/config/markdown.lua scripts/tests/nvim-markdown-probe.lua scripts/tests/nvim-markdown.bats
git commit -F tmp/commitmsg.txt
```

---

### Task 3: neotree.lua を新設し、appearance.lua を palette 参照へ移す

ファイラの配色を独立したモジュールへ切り出し、`appearance.lua` は base と `apply()` のオーケストレーションに専念させる。

**Files:**
- Create: `home/.config/nvim/lua/config/neotree.lua`
- Modify: `home/.config/nvim/lua/config/appearance.lua`
- Modify: `scripts/tests/nvim-markdown-probe.lua`
- Test: `scripts/tests/nvim-markdown.bats`

**Interfaces:**
- Consumes: `require("config.palette").hex` (Task 1 が提供)
- Produces: `require("config.neotree")` は NeoTree のハイライトグループ名から `nvim_set_hl` の引数テーブルへの表を返す。`require("config.appearance").apply()` は base と markdown と neotree の 3 つを適用する。

- [ ] **Step 1: 空の neotree.lua を作る**

RED を作るために、まずグループを何も定義しないモジュールを置く。

`home/.config/nvim/lua/config/neotree.lua`:

```lua
-- ファイラ (neo-tree) の配色。
--
-- プラグインの設定は plugins/neo-tree.lua が持つ。ここは配色だけを持ち、副作用は無い。
-- 色は config.palette が単一の真実として持ち、適用は config.appearance の apply() が行う。

return {}
```

この段階では `config.palette` を require しない。未使用のローカル変数は luals の警告になるため、Step 5 で中身を書くときに合わせて足す。

- [ ] **Step 2: probe に neo-tree の検査を追加する**

`scripts/tests/nvim-markdown-probe.lua` の `SCOPED_MUTED_APPLIED` を print している行の直後に追記する。この位置なら `highlight()` ヘルパーは定義済みで、まだ `colorscheme habamax` を読み込んでいない。

```lua

-- ---------------------------------------------------------------------------
-- ファイラの配色
--
-- NeoTree のグループ名は tree-sitter のキャプチャではないため、綴りを間違えても
-- Neovim は黙って無視する。ここではグループ名を出力し、実在の検査は bats が
-- neo-tree のソースに対して行う。
-- ---------------------------------------------------------------------------

local neotree = require("config.neotree")

local neotree_groups = {}
for name in pairs(neotree) do
    neotree_groups[#neotree_groups + 1] = name
end
table.sort(neotree_groups)
print("NEOTREE_GROUPS=" .. table.concat(neotree_groups, ","))
print("NEOTREE_GROUP_COUNT=" .. #neotree_groups)

-- 定義した色が実際に適用されていること。
-- link を張られている既定グループを上書きできているかもここで分かる
local neotree_applied = 1
for group, opts in pairs(neotree) do
    if opts.fg ~= nil then
        local want = tonumber(opts.fg:sub(2), 16)
        if highlight(group).fg ~= want then
            neotree_applied = 0
        end
    end
end
print("NEOTREE_APPLIED=" .. neotree_applied)
```

- [ ] **Step 3: bats にテストを追加する**

`scripts/tests/nvim-markdown.bats` の末尾に追記する。

```bash

@test "neo-tree palette defines the groups that were measured as unreadable" {
    # gitignored と未追跡ファイルは名前そのものに色が乗る。
    # インデント線と薄字は NeoTreeDimText に由来する
    run probe_with_extends
    assert_contains "$output" "NeoTreeGitIgnored"
    assert_contains "$output" "NeoTreeDotfile"
    assert_contains "$output" "NeoTreeHiddenByName"
    assert_contains "$output" "NeoTreeGitUntracked"
    assert_contains "$output" "NeoTreeGitConflict"
    assert_contains "$output" "NeoTreeDimText"
    assert_contains "$output" "NeoTreeExpander"
    assert_contains "$output" "NeoTreeIndentMarker"
    assert_contains "$output" "NeoTreeMessage"
}

@test "neo-tree palette is actually applied" {
    # グループが空だと下のループが回らず NEOTREE_APPLIED=1 のまま通ってしまう。
    # 空でないことを先に固定して偽の緑を塞ぐ
    run probe_with_extends
    refute_contains "$output" "NEOTREE_GROUP_COUNT=0"
    assert_contains "$output" "NEOTREE_APPLIED=1"
}

@test "neo-tree highlight group names exist in the plugin source" {
    # グループ名は treesitter のキャプチャではないので、綴りを間違えても Neovim は黙る。
    # CI にはプラグインを入れないため、その場合は検査できない
    src="${NEOTREE_HIGHLIGHTS:-$HOME/.local/share/nvim/lazy/neo-tree.nvim/lua/neo-tree/ui/highlights.lua}"
    if [ ! -f "$src" ]; then
        skip "neo-tree is not installed"
    fi

    run probe_with_extends
    # 検査対象が空のまま緑になるのを防ぐ
    refute_contains "$output" "NEOTREE_GROUP_COUNT=0"

    groups=$(printf '%s\n' "$output" | sed -n 's/^NEOTREE_GROUPS=//p' | tr ',' '\n')
    source_text=$(cat "$src")
    for group in $groups; do
        assert_contains "$source_text" "\"$group\""
    done
}
```

- [ ] **Step 4: テストを実行して RED を確認する**

Run: `bats scripts/tests/nvim-markdown.bats -f "neo-tree"`

Expected: 3 つとも **FAIL** する。

- `neo-tree palette defines the groups that were measured as unreadable` は `NEOTREE_GROUPS=` が空でどのグループ名も含まれないため落ちる
- `neo-tree palette is actually applied` は `NEOTREE_GROUP_COUNT=0` を弾くアサーションで落ちる (この行が無いとループが回らず常に緑になる偽の緑だった)
- `neo-tree highlight group names exist in the plugin source` も同じアサーションで落ちる

3 つとも落ちることを確認する。1 つでも緑なら、そのテストは何も守っていない。

- [ ] **Step 5: neotree.lua に配色を書く**

`home/.config/nvim/lua/config/neotree.lua` を次の内容に置き換える。

```lua
-- ファイラ (neo-tree) の配色。
--
-- プラグインの設定は plugins/neo-tree.lua が持つ。ここは配色だけを持ち、副作用は無い。
-- 色は config.palette が単一の真実として持ち、適用は config.appearance の apply() が行う。
--
-- neo-tree はファイル名の色を、まず filtered (dotfile / gitignored など) で決め、
-- そのあと git status の色で上書きする (lua/neo-tree/sources/common/components.lua の M.name)。
-- このため未追跡ファイルは名前そのものが git の色で描かれる。
--
-- NeoTreeIgnored と NeoTreeWindowsHidden は NeoTreeDotfile への link なので、
-- ここで定義しなくても修正が伝播する。
-- NeoTreeGitUnstaged は NeoTreeGitConflict への link なので同様に伝播する。
--
-- グループ名は tree-sitter のキャプチャではないため、綴りを間違えても Neovim は黙って無視する。
-- 実在は scripts/tests/nvim-markdown.bats が neo-tree のソースに対して検査する。

local hex = require("config.palette").hex

return {
    -- 隠されている項目。名前で隠す指定とドットファイルは同じ意味なので同色にする
    NeoTreeDotfile = { fg = hex.dotfile },
    NeoTreeHiddenByName = { fg = hex.dotfile },

    -- gitignore 対象。dotfile よりさらに後退させる
    NeoTreeGitIgnored = { fg = hex.gitignored },

    -- git が注意を促す状態。ファイル名そのものに乗るので読める明るさが要る。
    -- 色だけに頼らないよう neo-tree 既定の italic を保つ
    NeoTreeGitUntracked = { fg = hex.git_attention, italic = true },
    NeoTreeGitConflict = { fg = hex.git_attention, bold = true, italic = true },

    -- 薄字。(empty folder) などのメッセージと、展開マーカーは状態を伝えるので見える必要がある
    NeoTreeDimText = { fg = hex.muted },
    NeoTreeMessage = { fg = hex.muted, italic = true },
    NeoTreeExpander = { fg = hex.muted },

    -- インデント線は装飾なので、既定の link (NeoTreeDimText) を外して控えめに残す
    NeoTreeIndentMarker = { fg = hex.indent_guide },
}
```

- [ ] **Step 6: appearance.lua を書き換える**

`home/.config/nvim/lua/config/appearance.lua` を次の内容に置き換える。

```lua
-- エディタ全体のハイライト定義。
--
-- colorscheme を読み込むと nvim_set_hl の定義は hi clear で消える。
-- そこで起動時と ColorScheme のたびに同じ apply() を通して貼り直す。
-- (lazy.nvim の install.colorscheme はプラグイン導入時に colorscheme を読む)
--
-- 色は config.palette が単一の真実として持つ。
-- 各ファイルの責務は、ハイライトグループ名から nvim_set_hl の引数テーブルへの写像を返すことだけ。

local M = {}

local hex = require("config.palette").hex

-- 配色は副作用を持たない純粋テーブルとして各モジュールが持つ
local markdown = require("config.markdown")
local neotree = require("config.neotree")

local base = {
    -- ターミナルの背景をそのまま透過させる
    Normal = { bg = "NONE", ctermbg = "NONE" },
    NormalNC = { bg = "NONE", ctermbg = "NONE" },

    -- 行番号 (通常は teal、カーソル行は gold で太字)
    LineNr = { fg = hex.line_number, bg = "NONE" },
    CursorLineNr = { fg = hex.cursor_line_number, bg = "NONE", bold = true },
}

function M.apply()
    for _, groups in ipairs({ base, markdown, neotree }) do
        for group, opts in pairs(groups) do
            vim.api.nvim_set_hl(0, group, opts)
        end
    end
end

M.apply()

vim.api.nvim_create_autocmd("ColorScheme", {
    group = vim.api.nvim_create_augroup("dotfiles_appearance", { clear = true }),
    callback = M.apply,
})

return M
```

- [ ] **Step 7: テストを実行して GREEN を確認する**

Run: `bats scripts/tests/`

Expected: 全テストが PASS。特に次が緑であること。

- `neo-tree palette defines the groups that were measured as unreadable`
- `neo-tree palette is actually applied` (`NEOTREE_APPLIED=1`)
- `neo-tree highlight group names exist in the plugin source` (開発機では実行され、CI では skip)
- `highlights survive a colorscheme load`
- `appearance keeps the Normal background transparent`

`neo-tree highlight group names exist in the plugin source` が skip ではなく実行されていることを、bats の出力で確認する。skip されている場合は `NEOTREE_HIGHLIGHTS` 環境変数で neo-tree の highlights.lua のパスを指定して再実行し、実際に検査が通ることを一度は見ておく。

- [ ] **Step 8: コミットする**

```bash
mkdir -p tmp
cat > tmp/commitmsg.txt <<'EOF'
feat: ファイラの配色を neotree.lua へ切り出し基準を満たす色へ直す

- neo-tree は git status の色を filtered の色より後に上書きするため
  未追跡ファイルは名前そのものが 2.49:1 で描かれていた
- ツリーの薄灰は Comment ではなく NeoTreeDimText のハードコード値に由来する
  インデント線と展開マーカーと (empty folder) がここから来ている
- 展開マーカーは状態を伝えるので symbol tier まで上げ
  インデント線は装飾なので link を外して decoration tier に留める
- NeoTreeIgnored / NeoTreeWindowsHidden / NeoTreeGitUnstaged は
  link 経由で修正が伝播するため定義しない
- グループ名は treesitter キャプチャではなく綴りミスを Neovim が黙殺するため
  neo-tree のソースに対して実在を検査する
- appearance.lua は base と apply() のオーケストレーションに専念させる
EOF
git add home/.config/nvim/lua/config/neotree.lua home/.config/nvim/lua/config/appearance.lua scripts/tests/nvim-markdown-probe.lua scripts/tests/nvim-markdown.bats
git commit -F tmp/commitmsg.txt
```

---

### Task 4: hex リテラルのハードコードを ast-grep で禁止する

写像ファイルに色を直接書けないようにして、palette.lua が単一の真実であることを構文レベルで強制する。

**Files:**
- Create: `rules/nvim-lua-no-hex-literal.yml`
- Create: `rule-tests/nvim-lua-no-hex-literal-test.yml`
- Modify: `.pre-commit-config.yaml`

**Interfaces:**
- Consumes: なし
- Produces: なし (lint ルール)

- [ ] **Step 1: rule-tests を先に書く**

`rule-tests/nvim-lua-no-hex-literal-test.yml`:

```yaml
id: nvim-lua-no-hex-literal
valid:
  # palette を参照する正しい書き方
  - 'local hex = require("config.palette").hex'
  - 'return { X = { fg = hex.muted } }'
  # コメントの中の hex は文字列ノードではないので検出しない。
  # 実測値を根拠として書き残せることが重要
  - '-- 実測した実効背景は #5d646b である'
  # 色ではない文字列
  - 'local s = "NONE"'
  - 'local group = "@markup.heading.1"'
  # 数値リテラルの色 (nvim_set_hl は数値も受け付ける) は別問題なので対象外
  - 'local n = 0x5d646b'
invalid:
  - 'local MUTED = "#5c6370"'
  - 'return { X = { fg = "#aabbcc" } }'
  - 'local t = { bg = "#FFFFFF" }'
  - 'vim.api.nvim_set_hl(0, "LineNr", { fg = "#53c9b8" })'
```

- [ ] **Step 2: ast-grep test を実行して RED を確認する**

Run: `ast-grep test --skip-snapshot-tests`

Expected: FAIL。`nvim-lua-no-hex-literal` というルールが存在しないというエラーが出る。

- [ ] **Step 3: ルールを書く**

`severity` は必ず `error` にする。実測したところ `ast-grep scan` は `severity: error` の指摘があるとき exit 1 で終わるが、`severity: warning` では指摘があっても exit 0 で終わる。warning にすると pre-commit も CI も緑のまま素通りし、ルールは何も守らない。

`rules/nvim-lua-no-hex-literal.yml`:

```yaml
# 色の hex リテラルは config/palette.lua にのみ書く。
#
# 理由:
#   同じ色を複数のファイルに literal で書くと、片方だけを直して drift する。
#   基準背景に対するコントラストの検査 (scripts/tests/nvim-markdown.bats) は
#   palette.lua の colors を走査するので、写像側に直接書かれた色は検査を素通りする。
#
# kind: string に regex を掛けているのがこのルールの要点である。
#   grep だとコメントに書いた実測値まで誤検出するが、
#   ast-grep は文字列ノードだけを見るのでコメントは無視される。
#   実効背景の実測値を根拠としてコメントに残せることは重要なので、この区別が要る。
#
# 数値リテラル (0x5d646b) は対象外にしている。nvim_set_hl は数値も受け付けるが、
# 現状どこにも書かれておらず、書きたくなる動機も無い。必要になったら足す。
id: nvim-lua-no-hex-literal
language: lua
severity: error
message: 色の hex リテラルは config/palette.lua にのみ書く
note: |
  palette.lua の M.colors へトークンとして足し、ここでは require("config.palette").hex を参照する。
  tier を宣言しないとコントラスト検査を通らない。
files:
  - 'home/.config/nvim/lua/**/*.lua'
ignores:
  - 'home/.config/nvim/lua/config/palette.lua'
rule:
  kind: string
  regex: '#[0-9a-fA-F]{6}'
```

- [ ] **Step 4: ast-grep test を実行して GREEN を確認する**

Run: `ast-grep test --skip-snapshot-tests`

Expected: PASS。valid 6 件と invalid 4 件がすべて期待どおりに分類される。

- [ ] **Step 5: リポジトリ全体を scan して 0 件を確認する**

Run: `ast-grep scan`

Expected: `nvim-lua-no-hex-literal` の error が 0 件。既存の `bats-*` ルールも 0 件のまま。

もし error が出るなら、Task 2 と Task 3 で hex を追い出しきれていない。該当ファイルを直す。

exit code も直接確かめる。出力をパイプに繋ぐとパイプ先の exit code に化けるので繋がないこと。

```bash
ast-grep scan >/dev/null 2>&1
echo "exit=$?"
```

Expected: `exit=0`

- [ ] **Step 6: 変異注入でルールが効くことを確認する**

```bash
printf 'local x = "#123456"\n' >> home/.config/nvim/lua/config/markdown.lua
ast-grep scan
ast-grep scan >/dev/null 2>&1
echo "exit=$?"
```

Expected: `nvim-lua-no-hex-literal` の error が 1 件出て、`exit=1` になる。

確認したら元へ戻す。

```bash
git checkout home/.config/nvim/lua/config/markdown.lua
ast-grep scan >/dev/null 2>&1
echo "exit=$?"
```

Expected: `exit=0`

- [ ] **Step 7: pre-commit のトリガーへ Lua を足す**

`.pre-commit-config.yaml` の `ast-grep-scan` フックの `files` を変える。

変更前:

```yaml
        files: ^(.*\.bats|sgconfig\.yml|rules/.*)$
```

変更後:

```yaml
        files: ^(.*\.bats|.*\.lua|sgconfig\.yml|rules/.*)$
```

`ast-grep scan` は `pass_filenames: false` でリポジトリ全体を走るので、`files` は「いつ走らせるか」の条件でしかない。Lua を変更したときにも走るようにする。

- [ ] **Step 8: pre-commit が通ることを確認する**

Run: `pre-commit run --all-files`

Expected: `ast-grep scan` と `ast-grep test` が Passed。他のフックも Passed か Skipped。

- [ ] **Step 9: コミットする**

```bash
mkdir -p tmp
cat > tmp/commitmsg.txt <<'EOF'
ci: nvim の Lua に色の hex リテラルを書くことを ast-grep で禁止する

- palette.lua だけを ignore し 写像側へのハードコードを構文レベルで弾く
- kind: string に regex を掛けるのが要点
  grep だとコメントに書いた実測値まで誤検出するが
  ast-grep は文字列ノードだけを見るのでコメントは無視される
  実効背景の実測値を根拠としてコメントに残せることは重要なのでこの区別が要る
- rule-tests で valid 6 形と invalid 4 形を固定する
- 変異注入で確認済み
  markdown.lua に hex を 1 行足すと error が出て 戻すと 0 件に戻る
- pre-commit の ast-grep scan が Lua の変更でも走るよう files を広げる
EOF
git add rules/nvim-lua-no-hex-literal.yml rule-tests/nvim-lua-no-hex-literal-test.yml .pre-commit-config.yaml
git commit -F tmp/commitmsg.txt
```

---

### Task 5: ast-grep を CI に追加する

pre-commit だけでは `git commit --no-verify` で素通りし、`pre-commit install` を実行していないマシンでは一切走らない。dotfiles は複数マシンにクローンされる前提なのでこの穴は実在する。CI で守る。

このリポジトリは public であり、GitHub-hosted runner の実行時間は課金されない。実測でも `ast-grep scan` は 0.03 秒、`ast-grep test` は 0.00 秒で、ジョブ全体は runner 起動込みで 15 秒程度に収まる。

副次効果として、既存の `bats-no-bare-double-bracket` と `bats-test-name-ascii-only` も CI で守られるようになる。

**Files:**
- Create: `.github/actions/setup-ast-grep/action.yml`
- Modify: `.github/workflows/test.yml`

**Interfaces:**
- Consumes: `rules/` と `rule-tests/` と `sgconfig.yml` (Task 4 が提供)
- Produces: なし

- [ ] **Step 1: composite action を作る**

`setup-neovim` と同じ流儀にする。リリースタグ URL は tag の付け替えで中身が変わりうる mutable な参照なので、展開前に sha256 で検証する。

`.github/actions/setup-ast-grep/action.yml`:

```yaml
name: Setup ast-grep
description: ast-grep をバージョン pin した公式 zip から取得し PATH に追加するローカル composite action。pre-commit と同じ構文ルール (rules/) を CI でも走らせる。

runs:
  using: composite
  steps:
    - name: Install ast-grep
      shell: bash
      run: |
        ast_grep_version="0.44.1" # 開発機と揃える
        # リリースタグ URL は tag 付け替えで中身が変わりうる mutable な参照のため、
        # 展開前に固定済み sha256 で内容を検証する (setup-neovim と同じ意図)。
        # 再計算方法: curl で同じ URL を取得し `shasum -a 256 app-x86_64-unknown-linux-gnu.zip`
        # (macOS) または `sha256sum app-x86_64-unknown-linux-gnu.zip` (Linux) を実行する。
        expected_sha256="611f9e5e76f2611ecea1a35dd3468ceedf600641a11224b80341d79c6ee7b9dd"
        archive="$RUNNER_TEMP/ast-grep.zip"
        curl --proto '=https' --tlsv1.2 -fsSL -o "$archive" "https://github.com/ast-grep/ast-grep/releases/download/${ast_grep_version}/app-x86_64-unknown-linux-gnu.zip"
        echo "${expected_sha256}  ${archive}" | sha256sum -c -
        bin_dir="$RUNNER_TEMP/ast-grep-bin"
        mkdir -p "$bin_dir"
        unzip -q -o "$archive" -d "$bin_dir"
        # zip は実行権限を保持しないことがあるため明示的に付ける
        chmod +x "$bin_dir/ast-grep" "$bin_dir/sg"
        echo "$bin_dir" >> "$GITHUB_PATH"
```

- [ ] **Step 2: ジョブを追加する**

`.github/workflows/test.yml` の `bats` ジョブの直後に追加する。

```yaml
  ast-grep:
    name: ast-grep (syntax lint)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@9c091bb21b7c1c1d1991bb908d89e4e9dddfe3e0 # v7

      - name: Setup ast-grep
        uses: ./.github/actions/setup-ast-grep

      # rules/ の分類テスト。valid と invalid が期待どおりに分かれることを確かめる
      - name: Rule tests
        run: ast-grep test --skip-snapshot-tests

      # リポジトリ全体の走査。severity: error の指摘が 1 件でもあれば exit 1 になる
      # (severity: warning は指摘があっても exit 0 なので CI では守られない)
      - name: Scan repository
        run: ast-grep scan
```

- [ ] **Step 3: workflow の YAML が壊れていないことを確認する**

```bash
uv run --quiet --with pyyaml python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/test.yml')); yaml.safe_load(open('.github/actions/setup-ast-grep/action.yml')); print('yaml ok')"
```

Expected: `yaml ok`

- [ ] **Step 4: sha256 が正しいことを手元で確認する**

CI が落ちてから気づくのを避けるため、action.yml に書いた値と実際のアーカイブを照合する。

```bash
curl --proto '=https' --tlsv1.2 -fsSL -o /tmp/ast-grep.zip "https://github.com/ast-grep/ast-grep/releases/download/0.44.1/app-x86_64-unknown-linux-gnu.zip"
shasum -a 256 /tmp/ast-grep.zip
```

Expected: `611f9e5e76f2611ecea1a35dd3468ceedf600641a11224b80341d79c6ee7b9dd`

action.yml の `expected_sha256` と一致すること。

- [ ] **Step 5: コミットする**

```bash
mkdir -p tmp
cat > tmp/commitmsg.txt <<'EOF'
ci: ast-grep の構文ルールを CI でも走らせる

- pre-commit だけでは git commit --no-verify で素通りし
  pre-commit install していないマシンでは一切走らない
  dotfiles は複数マシンにクローンされる前提なのでこの穴は実在する
- setup-ast-grep composite action を setup-neovim と同じ流儀で追加する
  mutable なリリースタグ URL の中身を展開前に sha256 で検証する
  0.44.1 の zip をローカルで 2 回取得し一致を確認した値をハードコードする
- severity: error でないと scan は指摘があっても exit 0 で終わる
  warning のままだと CI は緑になりルールが何も守らない (実測で確認)
- 既存の bats-no-bare-double-bracket と bats-test-name-ascii-only も
  CI で守られるようになる
EOF
git add .github/actions/setup-ast-grep/action.yml .github/workflows/test.yml
git commit -F tmp/commitmsg.txt
```

---

### Task 6: 実環境で live smoke を行う

ユニットテストが緑でも、実際に描画されるかは別問題である。neo-tree は lazy load されるため、プラグインの `setup()` が後から走ったときに定義を上書きしないかを実機で確かめる必要がある。

**Files:**
- 変更なし (確認のみ)

**Interfaces:**
- Consumes: Task 1 から Task 5 の成果すべて

- [ ] **Step 1: 実 config で neo-tree を読み込ませ、色が残ることを確認する**

`--clean` ではなく実際の設定 (lazy.nvim 経由) で起動し、neo-tree の `setup()` が走ったあとの色を取る。

```bash
nvim --headless \
  -c 'Neotree show' \
  -c 'lua for _, g in ipairs({"NeoTreeGitIgnored","NeoTreeDotfile","NeoTreeGitUntracked","NeoTreeIndentMarker","NeoTreeExpander"}) do local hl = vim.api.nvim_get_hl(0, {name = g, link = false}); print(string.format("%s fg=%s", g, hl.fg and string.format("#%06x", hl.fg) or "nil")) end' \
  -c 'qa!' 2>&1
```

Expected: 5 グループすべてが palette の色を報告する。

- `NeoTreeGitIgnored fg=#aab6e4`
- `NeoTreeDotfile fg=#a8b6e7`
- `NeoTreeGitUntracked fg=#ffc8a1`
- `NeoTreeIndentMarker fg=#959594`
- `NeoTreeExpander fg=#b5b8bc`

`nil` や別の色が出たら、neo-tree の `create_highlight_group` が定義を上書きしている。その場合は `apply()` を neo-tree の setup 後にも走らせる必要があるので、`FileType neo-tree` の autocmd を追加して再度確認する。

- [ ] **Step 2: NeoTreeIndentMarker の link が外れていることを確認する**

```bash
nvim --headless \
  -c 'Neotree show' \
  -c 'lua print(vim.inspect(vim.api.nvim_get_hl(0, {name = "NeoTreeIndentMarker"})))' \
  -c 'qa!' 2>&1
```

Expected: `link` フィールドが無く、`fg` が直接入っている。`link = "NeoTreeDimText"` が残っていたら上書きできていない。

- [ ] **Step 3: 実際の端末で目視する**

次の 2 つを実際に開き、背後に白いウィンドウを置いた状態と黒いウィンドウを置いた状態の両方で確認する。

```bash
nvim README.md
```

確認項目:
- コードフェンス (```) の記号が背景に溶けず読める
- 表の `|` が読める
- リンクの URL が読める
- リンクの `[` `]` `(` `)` が本文より引っ込んで見える
- 打ち消し線が読める
- 見出し 1 から 6 の色が互いに区別できる
- インラインコードが赤みを保っている

```bash
nvim -c 'Neotree show'
```

確認項目:
- gitignore 対象のディレクトリ名 (`.hidari`, `.idea`, `.mypy_cache` など) が読める
- 未追跡ファイルの名前が読める
- インデント線が見えるが目立ちすぎない
- ドットファイルと gitignored の色が区別できる

- [ ] **Step 4: 参照リンクの既知の挙動を確認する**

一時ファイルに参照リンクを書き、`[ref]` 全体が muted になることを目視で確認する。これは spec に記録した既知の副作用であり、想定どおりであることを確かめる。

```bash
printf '[label][ref]\n\n[ref]: https://example.com\n' > /tmp/reflink.md
nvim /tmp/reflink.md
```

Expected: `[label]` の `label` はリンクラベル色、`[ref]` は全体が muted。

- [ ] **Step 5: 最終確認とプッシュ**

```bash
bats scripts/tests/
pre-commit run --all-files
git status --short
```

Expected: bats が全緑、pre-commit が全て Passed か Skipped、working tree がクリーン。

```bash
git push -u origin improve/nvim-contrast-palette
git ls-remote --heads origin improve/nvim-contrast-palette
git status -sb
```

`git ls-remote` でリモート ref の存在を、`git status -sb` で upstream tracking を直接確認する。push の出力をパイプに繋がないこと。

- [ ] **Step 6: CI の結論を専用クエリで確認する**

PR を作り、CI の結論を exit code ではなく専用クエリで直接確認する。

```bash
gh pr list --head improve/nvim-contrast-palette --base main
gh pr create --assignee @me --base main --fill
```

CI の結論は `gh run watch` の exit code ではなく、次で確認する。

```bash
run_id=$(gh run list --branch improve/nvim-contrast-palette --limit 1 --json databaseId --jq '.[0].databaseId')
gh run view "$run_id" --json conclusion,jobs --jq '{conclusion: .conclusion, jobs: [.jobs[] | {name: .name, conclusion: .conclusion}]}'
```

Expected: `conclusion` が `success`。`ast-grep (syntax lint)` ジョブと `bootstrap.sh (bats)` ジョブがともに `success`。

`ast-grep (syntax lint)` ジョブのログを実際に見て、`Scan repository` ステップが走っていることを確かめる。インストールに失敗して skip されていないことを目で確認する。

---

## 完了条件

- `bats scripts/tests/` が全緑 (skip は `neo-tree highlight group names exist in the plugin source` のみ許容し、開発機では実行されること)
- `pre-commit run --all-files` が全て Passed か Skipped
- `ast-grep scan` が exit 0
- CI の `ast-grep (syntax lint)` ジョブが success
- Task 6 の live smoke の全項目が目視で確認済み
- 色の hex が `home/.config/nvim/lua/config/palette.lua` 以外に存在しない
