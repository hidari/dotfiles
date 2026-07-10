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

### Task 2b: 見出しマーカーを見出しと同色にする

Hidari の判断により追加したタスク。見出しの `#` を灰色ではなく、見出し文字列と同じ色にする。

要点は色を定義しないことである。Neovim の `@` 名前空間は `@markup.heading.1.marker` を `@markup.heading.1` へ階層フォールバックする。つまりキャプチャ名にレベルを含めれば、色を一行も書かずに見出し色を継承する。現在の `@markup.heading.marker` がレベルを持たず `@markup.heading` (既定の `Title`) にしか落ちないのが、マーカーが見出しと別色になっていた理由である。

あわせて Task 2 のレビューで指摘された `@markup.link` のコメントの不正確さを直す。`@markup.link` は URL (`link_destination`) も構造的に捕捉している。URL に muted が乗らないのは、クエリの後方で宣言された `@markup.link.url` が同じ範囲を捕捉して後勝ちするからであって、`@markup.link` が URL を除外しているからではない。現在のコメントは「捕捉する範囲」と「最終的に解決される色」を混同している。

**Files:**
- Modify: `home/.config/nvim/after/queries/markdown/highlights.scm`
- Modify: `home/.config/nvim/lua/config/markdown.lua`
- Modify: `scripts/tests/nvim-markdown-probe.lua`
- Test: `scripts/tests/nvim-markdown.bats`

**Interfaces:**
- Consumes: `require("config.palette").hex.heading_1` から `heading_6` (Task 1 が提供)
- Produces: `markdown.lua` は `@markup.heading.marker` を定義しなくなる。`palette.hex.muted` は他の記号 (`` ` `` `~` `*` `|` `>` `---`、コードフェンスの言語名、リンク URL、リンクの記号) 専用になる

**2 つのテストの役割の違い (実測で確定済み)**

このタスクには性質の異なる 2 つの検査がある。混同しないこと。

- `MARKER_CAPTURES=6` は「拡張クエリが `@markup.heading.N.marker` というキャプチャ名を与えている」ことを検査する。カウント条件を新しい名前に変えるとクエリ変更前は 0 になるので、**これが RED を作る**。
- `MARKER_INHERITS_HEADING=1` は「マーカーのグループが見出しの色に解決される」ことを検査する。これは名前解決だけで成立するため、**クエリを変える前から 1 になる** (controller が 6 レベルすべてで実測済み)。したがって TDD の RED は作らない。このテストが守っているのは「誰かがマーカーへ色を明示定義して継承を壊すこと」であり、それは Step 8 の変異注入で確かめる。

両方が揃って初めて「`#` が見出しと同じ色で描かれる」が保証される。片方だけでは足りない。クエリが旧名のままだとマーカーは `@markup.heading` (既定の `Title`) に落ち、見出し色にならない。

- [ ] **Step 1: probe を書き換える**

まず、マーカー計数ループの条件をレベル別キャプチャ名に変える。

変更前:

```lua
    if query.captures[id] == "markup.heading.marker" then
```

変更後:

```lua
    if query.captures[id]:match("^markup%.heading%.%d%.marker$") then
```

次に、`LINK_NO_BLEED_TO_LUA` を print している行の直後へ継承の検査を追記する。この位置なら `resolved_fg` と `palette` は定義済みである。

```lua

-- 見出しマーカーには色を定義しない。@markup.heading.N.marker という名前が
-- @ 名前空間の階層フォールバックで @markup.heading.N へ落ちるため、見出しと同色になる。
-- この検査は名前解決だけで成立するのでクエリの有無には依存しない。
-- 守っているのは、誰かがマーカーへ色を明示定義して継承を壊すことである
local marker_inherits = 1
for level = 1, 6 do
    local want = tonumber(palette.hex["heading_" .. level]:sub(2), 16)
    if resolved_fg("markup.heading." .. level .. ".marker", "markdown") ~= want then
        marker_inherits = 0
    end
end
print("MARKER_INHERITS_HEADING=" .. marker_inherits)
```

- [ ] **Step 2: bats にテストを追加する**

`scripts/tests/nvim-markdown.bats` の末尾に追記する。

```bash

@test "heading markers inherit the color of their heading level" {
    # マーカーへ色を定義せず、@ 名前空間の階層フォールバックで見出し色を継承させる。
    # @markup.heading.N.marker が未定義なら @markup.heading.N へ落ちる。
    # この検査は名前解決だけで成立するのでクエリには依存しない。
    # 拡張クエリが正しいキャプチャ名を与えていることは MARKER_CAPTURES=6 が受け持つ
    run probe_with_extends
    assert_contains "$output" "MARKER_INHERITS_HEADING=1"
}
```

- [ ] **Step 3: テストを実行して RED を確認する**

Run: `bats scripts/tests/nvim-markdown.bats`

Expected:
- `extends query captures all six atx heading markers` が **FAIL**。出力に `MARKER_CAPTURES=0` が現れる。拡張クエリがまだ旧いキャプチャ名 `@markup.heading.marker` を使っているため、新しい名前では 1 つも数えられない。
- `heading markers inherit the color of their heading level` は **PASS**。継承は名前解決だけで成立するため、クエリを変える前から緑である。これは想定どおりであり、異常ではない。
- `without the extends query the marker checks fail` も **FAIL**。`MARKER_CAPTURES=0` は満たすが `MISSING_CAPTURES=@markup.heading.marker` はまだ満たす。Step 6 で直す。

`MARKER_CAPTURES=0` を自分の目で確認すること。確認できなければ検査は機能していない。

- [ ] **Step 4: 拡張クエリのキャプチャ名をレベル別にする**

`home/.config/nvim/after/queries/markdown/highlights.scm` を次の内容に置き換える。

```scheme
;; extends

; 見出しマーカー (# ## ...) をレベルごとのキャプチャへ分ける。
; 既定クエリの @markup.heading.N は "# H1" の行全体 (改行まで) を覆っており、
; マーカー単独のキャプチャが無い。
; 拡張クエリのキャプチャは既定より後に評価されるため、範囲が重なったときに後勝ちする。
;
; キャプチャ名にレベルを含めるのが要点である。@markup.heading.N.marker は
; @ 名前空間の階層フォールバックで @markup.heading.N へ落ちるため、
; 色を一切定義しなくてもマーカーが見出しと同色になる。
; レベルを含まない @markup.heading.marker は @markup.heading (既定の Title) にしか落ちない。
;
; キャプチャ名がレベルごとに異なるため、交替リストにはまとめられない。
(atx_h1_marker) @markup.heading.1.marker
(atx_h2_marker) @markup.heading.2.marker
(atx_h3_marker) @markup.heading.3.marker
(atx_h4_marker) @markup.heading.4.marker
(atx_h5_marker) @markup.heading.5.marker
(atx_h6_marker) @markup.heading.6.marker
```

- [ ] **Step 5: markdown.lua から marker のエントリを消し、コメントを直す**

まず、ヘッダーコメントの次の 2 行を削除する。

```lua
-- @markup.heading.marker は after/queries/markdown/highlights.scm が定義する拡張キャプチャで、
-- 既定のクエリには存在しない。
```

そのかわりに、同じ位置へ次を書く。

```lua
-- 見出しマーカー (#) には色を定義しない。after/queries/markdown/highlights.scm が
-- @markup.heading.N.marker というレベル入りのキャプチャ名を与えており、
-- @ 名前空間の階層フォールバックで @markup.heading.N を継承するため、見出しと同色になる。
```

次に、`@markup.link` を説明している 3 行を次のように書き換える。

変更前:

```lua
-- @markup.link が捕捉するのは URL ではなくリンクの記号 ( [ ] ( ) ! ) である。
-- 参照リンク [label][ref] の [ref] は @markup.link.label の後に @markup.link が評価されて
-- 後勝ちするため、[ref] 全体が muted になる (実測で確認済みの既知の挙動)。
```

変更後:

```lua
-- @markup.link はリンクや画像のノード全体を捕捉する。記号 ( [ ] ( ) ! ) だけでなく
-- URL の範囲も含む。それでも URL に muted が乗らないのは、クエリの後方で宣言された
-- @markup.link.url が同じ範囲を捕捉して後勝ちするためであり、@markup.link が URL を
-- 構造的に除外しているわけではない。結果として muted が最終的に乗るのは記号だけになる。
-- 同じ理由で、参照リンク [label][ref] の [ref] は @markup.link.label の後に
-- @markup.link が評価されて後勝ちするため、[ref] 全体が muted になる (実測で確認済み)。
```

最後に、次のエントリとその直前のコメントを削除する。

```lua
    -- 見出しの # 記号だけを引っ込める (拡張クエリ由来のキャプチャ)
    ["@markup.heading.marker"] = { fg = hex.muted },
```

- [ ] **Step 6: bats の negative case から MISSING_CAPTURES の行を消す**

`markdown.lua` が `@markup.heading.marker` を定義しなくなったので、拡張クエリを外したときに `MISSING_CAPTURES` へ現れなくなる。`MARKER_CAPTURES=0` が拡張クエリの negative case を担う。

変更前:

```bash
@test "without the extends query the marker checks fail" {
    # 上の 2 つの検査が拡張クエリに支えられていることを示す
    # (拡張を外しても緑のままなら、その検査は何も守っていない)
    run probe_without_extends
    assert_contains "$output" "MARKER_CAPTURES=0"
    assert_contains "$output" "MISSING_CAPTURES=@markup.heading.marker"
}
```

変更後:

```bash
@test "without the extends query the marker checks fail" {
    # マーカーの検査が拡張クエリに支えられていることを示す
    # (拡張を外しても緑のままなら、その検査は何も守っていない)
    # markdown.lua はマーカーへ色を定義しないので MISSING_CAPTURES には現れない
    run probe_without_extends
    assert_contains "$output" "MARKER_CAPTURES=0"
}
```

- [ ] **Step 7: テストを実行して GREEN を確認する**

Run: `bats scripts/tests/`

Expected: 全テストが PASS。特に次が緑であること。

- `heading markers inherit the color of their heading level` (`MARKER_INHERITS_HEADING=1`)
- `extends query captures all six atx heading markers` (`MARKER_CAPTURES=6`)
- `without the extends query the marker checks fail` (`MARKER_CAPTURES=0`)
- `markdown palette: every group exists as a treesitter capture` (`MISSING_CAPTURES=` が空)
- `palette: every token meets the contrast target of its tier`

- [ ] **Step 8: 変異注入で 2 つのテストが別々の失敗モードを捕まえることを確かめる**

このタスクの検査は 2 本立てなので、それぞれ独立に効くことを示す。

変異注入 a (継承を明示定義で壊す)。`markdown.lua` の `return {` の直後に次の 1 行を一時的に足す。

```lua
    ["@markup.heading.1.marker"] = { fg = hex.muted },
```

Run: `bats scripts/tests/nvim-markdown.bats`

Expected: `heading markers inherit the color of their heading level` が FAIL (`MARKER_INHERITS_HEADING=0`)。`extends query captures all six atx heading markers` は緑のまま。

元へ戻す。

```bash
git checkout home/.config/nvim/lua/config/markdown.lua
```

変異注入 b (クエリのキャプチャ名を旧名へ戻す)。`highlights.scm` の 6 行を `@markup.heading.marker` へ書き換える。

Run: `bats scripts/tests/nvim-markdown.bats`

Expected: `extends query captures all six atx heading markers` が FAIL (`MARKER_CAPTURES=0`)。`heading markers inherit the color of their heading level` は緑のまま (継承は名前解決だけで成立するため)。

この 2 つが別々に落ちることが、2 本のテストが別々の失敗モードを見ている証拠である。

元へ戻して全緑を確認する。

```bash
git checkout home/.config/nvim/after/queries/markdown/highlights.scm
bats scripts/tests/
```

Expected: 全緑

- [ ] **Step 9: コミットする**

```bash
mkdir -p tmp
cat > tmp/commitmsg.txt <<'EOF'
improve: 見出しマーカーを見出しと同色にする

- 拡張クエリのキャプチャ名を @markup.heading.N.marker へ変える
  名前にレベルを含めると @ 名前空間の階層フォールバックが
  @markup.heading.N へ落とすため 色を一行も定義せずに見出し色を継承する
- レベルを持たない @markup.heading.marker は @markup.heading (Title) にしか
  落ちないため これまでマーカーだけ別色になっていた
- markdown.lua から marker のエントリを削除する
  muted は他の記号 ( ` ~ * | > --- ) とリンク URL 専用になる
- 継承が崩れると検出できるよう probe が 6 レベルすべての解決結果を照合する
  変異注入で確認済み: マーカーへ色を明示定義すると赤になる
- @markup.link のコメントを実測に合わせて訂正する
  @markup.link は URL の範囲も構造的に捕捉しており
  URL に muted が乗らないのは後方の @markup.link.url が後勝ちするためである
EOF
git add home/.config/nvim/after/queries/markdown/highlights.scm home/.config/nvim/lua/config/markdown.lua scripts/tests/nvim-markdown-probe.lua scripts/tests/nvim-markdown.bats
git commit -F tmp/commitmsg.txt
```

`git add` はファイルを明示指定すること。`git add .` や `git add -A` を使ってはならない (作業ツリーに Hidari が編集中の `.af` ファイルがある)。

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

### Task 3b: gitignored を dotfile と区別できる彩度まで下げ、知覚距離を機械検査する

コントラスト検査は各色が tier の下限を超えるかしか見ない。下限に張り付いた色どうしが同化しても緑のまま通る。この穴を塞ぐ。

**Files:**
- Modify: `home/.config/nvim/lua/config/palette.lua`
- Modify: `scripts/tests/nvim-markdown-probe.lua`
- Test: `scripts/tests/nvim-markdown.bats`

**Interfaces:**
- Consumes: `palette.colors` と `palette.reference_background` (Task 1 が提供)、probe の `linearize` (Task 1 が提供)
- Produces: `palette.minimum_delta_e`。probe が `DELTA_E_SELFTEST_MAX` / `DELTA_E_SELFTEST_MIN` / `PALETTE_DISTINCT_HEX_COUNT` / `PALETTE_JND_PAIR_COUNT` / `PALETTE_JND_VIOLATIONS` / `PALETTE_JND_VIOLATION_COUNT` / `JND_DETECTOR_WORKS` を出力する

**controller が実測済みの事実 (再検証は不要):**

- `dotfile` (`#a8b6e7`) と `RECEDED` (`#aab6e4`) はどちらも symbol tier の下限に張り付き (3.005:1 と 3.012:1)、OKLCh の色相も 272.2 度と 273.4 度でほぼ同じ。OKLab の色差は 0.0049 で、知覚閾値 (JND) 0.02 の 4 分の 1 しかない
- `RECEDED` を `#b1b7cf` にすると輝度を保ったまま彩度だけが下がる。コントラストは 3.012:1 (margin +0.012) を維持し、`dotfile` との色差は 0.0371、`muted` との色差は 0.0286 になる。どちらも JND を超える
- 彩度をこれ以上落とすと `muted` (`#b5b8bc`) と同化する。`#b3b8c9` は muted との色差が 0.0187 で JND を割る
- 修正後の palette は相異なる hex が 19 個、組が 171 通りで、JND を割る組は 0 になる。最小は `strikethrough` と `muted` の 0.0286
- OKLab の色差は白と黒でちょうど 1.0 になる (L が 0 から 1 に収まるため)。同色どうしは 0.0
- probe の既存 `linearize` は WCAG の閾値 0.03928 を使う。sRGB 規格 (OKLab の前提) は 0.04045 だが、8bit 入力では 10/255 = 0.0392 が両方の閾値を下回り、11/255 = 0.0431 が両方を上回るため、0 から 255 のどの値でも分岐が変わらない。よって `linearize` をそのまま使い回してよい
- 上記の Lua 実装は controller が Python の参照実装と突き合わせ、小数 6 桁まで一致することを確認済み

- [ ] **Step 1: palette に閾値を足す (色はまだ変えない)**

`home/.config/nvim/lua/config/palette.lua` の `M.minimum_contrast` テーブルの直後に追記する。

```lua

-- 知覚可能な最小の色差 (OKLab のユークリッド距離)。
-- これを下回る 2 色は人間には同じ色に見える。
-- 彩度で後退させた色どうしが tier の下限に張り付いて同化するのを防ぐ。
M.minimum_delta_e = 0.02
```

- [ ] **Step 2: probe に色差の検査を追加する**

`scripts/tests/nvim-markdown-probe.lua` の末尾 (`SENTINEL_RATIO` を print している行の直後) に追記する。

```lua

-- ---------------------------------------------------------------------------
-- パレットの区別可能性の検査
--
-- コントラスト検査は各色が tier の下限を超えるかしか見ない。
-- 下限に張り付いた色どうしが同化しても検出できないため、色差を別に測る。
--
-- OKLab は知覚的におおむね均等な色空間で、L は 0 から 1 に収まる。
-- 2 色のユークリッド距離が知覚閾値 (JND) を下回ると人間には同じ色に見える。
--
-- 意図的に同色のトークンは palette の中で同じリテラルを共有する。
-- したがって相異なる hex どうしだけを比べれば、区別すべき色だけが対象になる。
--
-- linearize は WCAG の閾値 0.03928 を使う。sRGB 規格は 0.04045 だが、
-- 8bit 入力では 10/255 = 0.0392 が両方を下回り 11/255 = 0.0431 が両方を上回るため、
-- 0 から 255 のどの値でも分岐は変わらない。よってここで使い回せる。
-- ---------------------------------------------------------------------------

local function to_oklab(hex)
    local r = linearize(tonumber(hex:sub(2, 3), 16))
    local g = linearize(tonumber(hex:sub(4, 5), 16))
    local b = linearize(tonumber(hex:sub(6, 7), 16))

    local l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    local m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    local s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b

    local l_, m_, s_ = l ^ (1 / 3), m ^ (1 / 3), s ^ (1 / 3)

    return 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
end

local function delta_e(hex_a, hex_b)
    local la, aa, ba = to_oklab(hex_a)
    local lb, ab, bb = to_oklab(hex_b)
    return math.sqrt((la - lb) ^ 2 + (aa - ab) ^ 2 + (ba - bb) ^ 2)
end

-- 検査ロジック自体の較正。OKLab の L は 0 から 1 なので白と黒はちょうど 1.0、
-- 同色どうしは 0.0 になる。ここが崩れたら以降の判定は全て無意味なので先に固定する
print(string.format("DELTA_E_SELFTEST_MAX=%.4f", delta_e("#ffffff", "#000000")))
print(string.format(
    "DELTA_E_SELFTEST_MIN=%.4f",
    delta_e(palette.reference_background, palette.reference_background)
))

-- 相異なる hex ごとに代表トークンを 1 つ選ぶ。辞書順で最小を取れば出力が安定する
local representative = {}
for token, spec in pairs(palette.colors) do
    if representative[spec.hex] == nil or token < representative[spec.hex] then
        representative[spec.hex] = token
    end
end

local distinct = {}
for hex in pairs(representative) do
    distinct[#distinct + 1] = hex
end
table.sort(distinct)
print("PALETTE_DISTINCT_HEX_COUNT=" .. #distinct)
print("PALETTE_JND_PAIR_COUNT=" .. (#distinct * (#distinct - 1) / 2))

local jnd_violations = {}
for i = 1, #distinct do
    for j = i + 1, #distinct do
        local distance = delta_e(distinct[i], distinct[j])
        if distance < palette.minimum_delta_e then
            jnd_violations[#jnd_violations + 1] = string.format(
                "%s|%s:%.4f",
                representative[distinct[i]],
                representative[distinct[j]],
                distance
            )
        end
    end
end
table.sort(jnd_violations)
print("PALETTE_JND_VIOLATIONS=" .. table.concat(jnd_violations, ","))
print("PALETTE_JND_VIOLATION_COUNT=" .. #jnd_violations)

-- 検出器が働いていることを示す negative case。
-- 旧 RECEDED (#aab6e4) は dotfile (#a8b6e7) と色差 0.0049 で同化していた。
-- ここが 0 になったら区別可能性の検査は何も守っていない
print("JND_DETECTOR_WORKS=" .. ((delta_e("#a8b6e7", "#aab6e4") < palette.minimum_delta_e) and 1 or 0))
```

- [ ] **Step 3: bats にテストを追加する**

`scripts/tests/nvim-markdown.bats` の末尾に追記する。

```bash

@test "delta e helper is calibrated against known values" {
    # OKLab の L は 0 から 1 なので白と黒はちょうど 1.0 になる
    run probe_with_extends
    assert_contains "$output" "DELTA_E_SELFTEST_MAX=1.0000"
    assert_contains "$output" "DELTA_E_SELFTEST_MIN=0.0000"
}

@test "palette: the distinguishability check detects two colors that look alike" {
    # 実際に同化していた組を sentinel に使う
    run probe_with_extends
    assert_contains "$output" "JND_DETECTOR_WORKS=1"
}

@test "palette: every pair of distinct colors is perceptibly different" {
    # 比べる組が 0 だと下のループが回らず違反 0 のまま通ってしまう
    run probe_with_extends
    refute_contains "$output" "PALETTE_JND_PAIR_COUNT=0"
    assert_contains "$output" "PALETTE_JND_VIOLATION_COUNT=0"
}
```

- [ ] **Step 4: テストを実行して RED を確認する**

Run: `bats scripts/tests/nvim-markdown.bats -f "delta e|distinguishability|perceptibly"`

Expected: `palette: every pair of distinct colors is perceptibly different` だけが FAIL する。

出力に `PALETTE_JND_VIOLATION_COUNT=1` と `PALETTE_JND_VIOLATIONS=dotfile|gitignored:0.0049` が現れることを確認する。較正テストと sentinel テストは緑である (これらは色を直しても緑のままなので、赤を作るのは違反カウントの側だけである)。

- [ ] **Step 5: palette の RECEDED を直す**

`home/.config/nvim/lua/config/palette.lua` の `RECEDED` を書き換える。

```lua
-- 後退した記号とファイル名。彩度をほぼ捨てて dotfile の青みから離す。
-- 輝度は symbol tier の下限を満たす位置に保つ
local RECEDED = "#b1b7cf"
```

- [ ] **Step 6: テストを実行して GREEN を確認する**

Run: `bats scripts/tests/`

Expected: 全テストが PASS。特に `palette: every token meets the contrast target of its tier` が緑のままであること (`RECEDED` は 3.012:1 で symbol tier の 3.0 を満たす)。

- [ ] **Step 7: コミットする**

変異注入より先にコミットする。`git checkout <file>` は「HEAD の状態へ戻す」であって「変異注入の直前へ戻す」ではないため、
未コミットの実装が残っていると変異と一緒に巻き戻る。コミットを済ませておけばそれが復元点になる。

```bash
mkdir -p tmp
cat > tmp/commitmsg.txt <<'EOF'
improve: gitignored を dotfile と見分けられる彩度まで下げ 色差を機械検査する

- コントラスト検査は各色が tier の下限を超えるかしか見ないため
  下限に張り付いた 2 色が同化しても緑のまま通っていた
- dotfile と RECEDED は OKLab の色差が 0.0049 で
  知覚閾値 0.02 の 4 分の 1 しか離れていなかった
- RECEDED の彩度を落として色差を 0.0371 まで開く
  輝度は変えないのでコントラストは 3.01:1 を維持する
- 相異なる hex が互いに知覚可能な距離を持つことを probe が総当たりで検査する
  意図的に同色のトークンは同じリテラルを共有するため対象にならない
EOF
git add home/.config/nvim/lua/config/palette.lua scripts/tests/nvim-markdown-probe.lua scripts/tests/nvim-markdown.bats
git commit -F tmp/commitmsg.txt
```

- [ ] **Step 8: 変異注入で 3 つのテストが別々の失敗モードを捕まえることを確かめる**

コミット済みなので `git checkout <file>` で安全に戻せる。各変異のあと必ず戻して全緑を確認する。

変異注入 a (色を同化した状態へ戻す)。`palette.lua` の `RECEDED` を `"#aab6e4"` に戻す。

Expected: `palette: every pair of distinct colors is perceptibly different` だけが FAIL。較正と sentinel は緑のまま。

変異注入 b (閾値を無効化する)。`palette.lua` の `M.minimum_delta_e` を `0` にする。

Expected: `palette: the distinguishability check detects two colors that look alike` だけが FAIL (`JND_DETECTOR_WORKS=0`)。違反カウントは 0 のまま緑。

変異注入 c (色差の計算を壊す)。probe の `to_oklab` の `0.7936177850` を `0.5` にする。

Expected: `delta e helper is calibrated against known values` だけが FAIL。区別可能性の 2 本は緑のまま。
係数を壊しても色差の値がたまたま閾値を超え続けるため、数式の正しさを守っているのは較正テストだけである。

---

### Task 3c: lualine の配色を palette の surfaces へ移す

自前の背景色を持つ面を palette の管理下に入れ、hex リテラルを nvim の Lua から一掃する。

**Files:**
- Modify: `home/.config/nvim/lua/config/palette.lua`
- Modify: `home/.config/nvim/lua/plugins/lualine.lua`
- Modify: `scripts/tests/nvim-markdown-probe.lua`
- Test: `scripts/tests/nvim-markdown.bats`

**Interfaces:**
- Consumes: probe の `contrast_ratio` (Task 1 が提供)
- Produces: `palette.surfaces` と `palette.surface_minimum_contrast`。probe が `SURFACE_COUNT` / `SURFACE_VIOLATIONS` / `SURFACE_VIOLATION_COUNT` / `LUALINE_MATCHES_PALETTE` を出力する

**controller が実測済みの事実 (再検証は不要):**

- `plugins/lualine.lua` の `buffers_color` だけが hex リテラルを持つ。他は `theme = "auto"` で colorscheme から取る
- Ghostty 1.3.1 の `background-opacity-cells` は既定 `false`。ドキュメントに「`background-opacity` is only applied to the window background. If a cell has an explicit background color set ... that background color will be fully opaque」とある。よって lualine の bg は不透明に描かれる
- 実測: active は `#282c34` on `#53c9b8` で 6.94:1、inactive は `#abb2bf` on `#21252b` で 7.22:1。どちらも WCAG AA の 4.5:1 を満たす
- 基準背景に対して測ると active の fg は 2.33:1、inactive の fg は 2.81:1 で、どの tier も満たさない。だから `colors` ではなく `surfaces` に置く
- probe の headless nvim から `require("plugins.lualine")` が引けることを controller が実測済み。再帰探索で `buffers_color` に到達できる
- 値は据え置く。色を Mariana 系へ揃え直すかどうかは別の議論であり、このタスクの範囲外

- [ ] **Step 1: probe に不透明な面の検査を追加する (RED を作る)**

`scripts/tests/nvim-markdown-probe.lua` の末尾に追記する。

```lua

-- ---------------------------------------------------------------------------
-- 不透明な面の配色の検査
--
-- ステータスラインのように自前の背景色を持つ面は、透過したターミナル背景の上には無い。
-- Ghostty の background-opacity はウィンドウ背景にだけ掛かり、
-- 明示的な背景色を持つセルは不透明に描かれる (background-opacity-cells が既定の false のとき)。
-- したがって前景色は reference_background ではなく自前の bg に対して評価する。
-- ---------------------------------------------------------------------------

local surface_violations = {}
local surface_count = 0
for name, surface in pairs(palette.surfaces) do
    surface_count = surface_count + 1
    local ratio = contrast_ratio(surface.fg, surface.bg)
    if ratio < palette.surface_minimum_contrast then
        surface_violations[#surface_violations + 1] = string.format(
            "%s:%.2f<%.2f",
            name,
            ratio,
            palette.surface_minimum_contrast
        )
    end
end
table.sort(surface_violations)
print("SURFACE_COUNT=" .. surface_count)
print("SURFACE_VIOLATIONS=" .. table.concat(surface_violations, ","))
print("SURFACE_VIOLATION_COUNT=" .. #surface_violations)

-- lualine の spec の入れ子から指定キーを再帰的に探す。
-- 添字を決め打ちにすると spec の並べ替えで壊れるため、キー名で辿る
local function find_key(node, key)
    if type(node) ~= "table" then
        return nil
    end
    if node[key] ~= nil then
        return node[key]
    end
    for _, child in pairs(node) do
        local found = find_key(child, key)
        if found ~= nil then
            return found
        end
    end
    return nil
end

-- lualine が palette と同じ値を使っていること (drift ガード)。
-- palette を参照していること自体は ast-grep の nvim-lua-no-hex-literal が構文レベルで保証する。
-- ここは値の一致だけを見る
local buffers_color = find_key(require("plugins.lualine"), "buffers_color")
local lualine_matches = 0
if buffers_color ~= nil then
    local active = palette.surfaces.statusline_buffer_active
    local inactive = palette.surfaces.statusline_buffer_inactive
    if
        buffers_color.active.fg == active.fg
        and buffers_color.active.bg == active.bg
        and buffers_color.inactive.fg == inactive.fg
        and buffers_color.inactive.bg == inactive.bg
    then
        lualine_matches = 1
    end
end
print("LUALINE_MATCHES_PALETTE=" .. lualine_matches)
```

- [ ] **Step 2: bats にテストを追加する**

`scripts/tests/nvim-markdown.bats` の末尾に追記する。

```bash

@test "opaque surfaces meet the contrast target against their own background" {
    # 面が 0 個だと上のループが回らず違反 0 のまま通ってしまう
    run probe_with_extends
    refute_contains "$output" "SURFACE_COUNT=0"
    assert_contains "$output" "SURFACE_VIOLATION_COUNT=0"
}

@test "lualine uses the same colors as the palette surfaces" {
    # 値の drift を塞ぐ。hex を書き戻すこと自体は ast-grep が塞ぐ
    run probe_with_extends
    assert_contains "$output" "LUALINE_MATCHES_PALETTE=1"
}
```

- [ ] **Step 3: テストを実行して RED を確認する**

Run: `bats scripts/tests/nvim-markdown.bats -f "opaque surfaces|lualine"`

Expected: 2 つとも FAIL する。`palette.surfaces` がまだ存在せず、probe が nil を添字参照して落ちるため。

- [ ] **Step 4: palette に surfaces を足す**

`home/.config/nvim/lua/config/palette.lua` の `M.hex` の導出より前 (`M.colors` テーブルの直後) に追記する。

```lua

-- 不透明な面の配色。
--
-- ステータスラインのように自前の背景色を持つ面は、透過したターミナル背景の上には無い。
-- Ghostty の background-opacity はウィンドウ背景にだけ掛かり、
-- 明示的な背景色を持つセルは不透明に描かれる (background-opacity-cells が既定の false のとき)。
-- したがって reference_background ではなく自前の bg に対して評価し、
-- 不透明である以上、WCAG AA (通常テキスト) の基準を課せる。
M.surface_minimum_contrast = 4.5

M.surfaces = {
    -- ステータスラインのバッファ一覧。アクティブなものを teal の帯で強調する
    statusline_buffer_active = { fg = "#282c34", bg = "#53c9b8" },
    statusline_buffer_inactive = { fg = "#abb2bf", bg = "#21252b" },
}
```

- [ ] **Step 5: lualine を palette 参照へ移す**

`home/.config/nvim/lua/plugins/lualine.lua` の先頭に require を足し、`buffers_color` を書き換える。太字の指定は色ではないので lualine 側に残す。

```lua
local surfaces = require("config.palette").surfaces

return {
```

```lua
                        -- アクティブなバッファをtealでくっきり強調（追従が見えるように）
                        buffers_color = {
                            active = {
                                fg = surfaces.statusline_buffer_active.fg,
                                bg = surfaces.statusline_buffer_active.bg,
                                gui = "bold",
                            },
                            inactive = {
                                fg = surfaces.statusline_buffer_inactive.fg,
                                bg = surfaces.statusline_buffer_inactive.bg,
                            },
                        },
```

- [ ] **Step 6: テストを実行して GREEN を確認する**

Run: `bats scripts/tests/`

Expected: 全テストが PASS。`SURFACE_VIOLATION_COUNT=0` と `LUALINE_MATCHES_PALETTE=1` が出力に現れる。

`grep -rnE '"#[0-9a-fA-F]{6}"' home/.config/nvim/lua --include='*.lua' | grep -v 'lua/config/palette.lua'` が何も返さないことも確認する。Task 4 の ast-grep ルールはこの状態を前提に着地する。

- [ ] **Step 7: コミットする**

変異注入より先にコミットする。`git checkout <file>` は「HEAD の状態へ戻す」であって「変異注入の直前へ戻す」ではないため、
未コミットの実装が残っていると変異と一緒に巻き戻る。コミットを済ませておけばそれが復元点になる。

```bash
mkdir -p tmp
cat > tmp/commitmsg.txt <<'EOF'
refactor: lualine の配色を palette の surfaces へ移す

- ステータスラインは自前の背景色を持つため 透過した基準背景の上には無い
  Ghostty の background-opacity はウィンドウ背景にだけ掛かる
- したがって tier ではなく 自前の bg に対する WCAG AA 4.5:1 で評価する
- この 4 色はこれまで誰も検査していなかった
  palette へ移したことで初めて機械検査が付く
- background-opacity-cells を有効にすると前提が崩れるが
  前提を palette に書いたのでそのときはテストが赤くなる
- これで nvim の Lua から hex リテラルが palette.lua だけになる
EOF
git add home/.config/nvim/lua/config/palette.lua home/.config/nvim/lua/plugins/lualine.lua scripts/tests/nvim-markdown-probe.lua scripts/tests/nvim-markdown.bats
git commit -F tmp/commitmsg.txt
```

- [ ] **Step 8: 変異注入で 2 つのテストが別々の失敗モードを捕まえることを確かめる**

コミット済みなので `git checkout <file>` で安全に戻せる。各変異のあと必ず戻して全緑を確認する。

変異注入 a (面のコントラストを壊す)。`palette.lua` の `statusline_buffer_inactive` の `fg` を `"#3a3f45"` にする。

Expected: `opaque surfaces meet the contrast target against their own background` だけが FAIL。`lualine uses the same colors as the palette surfaces` は緑のまま (lualine は palette を参照しているので一緒に動く)。

変異注入 b (lualine に値を書き戻す)。`lualine.lua` の inactive の `fg` を `"#abb2bf"` というリテラルに戻したうえで、`palette.lua` の同じ値を `"#a9b0bd"` に変える。

Expected: `lualine uses the same colors as the palette surfaces` だけが FAIL (`LUALINE_MATCHES_PALETTE=0`)。面のコントラストは緑のまま。

---

### Task 4: hex リテラルのハードコードを ast-grep で禁止する

写像ファイルに色を直接書けないようにして、palette.lua が単一の真実であることを構文レベルで強制する。

**Files:**
- Create: `rules/nvim-lua-no-hex-literal.yml`
- Create: `rule-tests/nvim-lua-no-hex-literal-test.yml`
- Create: `scripts/tests/ast-grep.bats`
- Modify: `.pre-commit-config.yaml`

**Interfaces:**
- Consumes: なし
- Produces: なし (lint ルール)

**controller が実測済みの事実 (再検証は不要):**

- ast-grep 0.44.1。`kind: string` + regex は Lua の文字列リテラルだけを捕捉し、コメント内の hex は無視する
- `severity: error` は指摘があると exit 1、`severity: warning` は exit 0。warning では pre-commit も CI も素通りする
- `ast-grep scan` は既定で隠しディレクトリを走査しない。`home/.config/` はドットで始まるため、`--no-ignore hidden` が無いと nvim の Lua を 1 件も検査せず 0 件・exit 0 で終わる
- `--no-ignore hidden` を足しても既存の 2 ルールに新たな違反は出ず、scan は 0.04 秒で終わる
- `ast-grep test` は仮想スニペットに対して走るため `files` と `ignores` を通らない。glob の検査には fixture が要る
- fixture のルートに `sgconfig.yml` と `rules/` を置き、`home/.config/nvim/lua/config/` を掘れば実ルールがそのまま効く (controller が実証済み)
- `home/.config/nvim/init.lua` は `lua/**` の外なので glob の対象外。現状 hex を持たない

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
  - '-- コメントの中の hex #123abc は検出しない'
  # 色ではない文字列
  - 'local s = "NONE"'
  - 'local group = "@markup.heading.1"'
  # 数値リテラルの色 (nvim_set_hl は数値も受け付ける) は別問題なので対象外
  - 'local n = 0xaabbcc'
invalid:
  - 'local MUTED = "#5c6370"'
  - 'return { X = { fg = "#aabbcc" } }'
  - 'local t = { bg = "#FFFFFF" }'
  - 'vim.api.nvim_set_hl(0, "LineNr", { fg = "#0f1e2d" })'
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
# 数値リテラル (0xaabbcc の形) は対象外にしている。nvim_set_hl は数値も受け付けるが、
# 現状どこにも書かれておらず、書きたくなる動機も無い。必要になったら足す。
#
# 既知のトレードオフ: regex は文字列ノードのテキスト全体に掛かるため、
#   色ではない文字列に含まれる #rrggbb も検出する (例: "https://example.com/#a1b2c3")。
#   現状そのような文字列は無く、出たときに ignores か constraints を足せばよい。
#
# 注意: ast-grep scan は既定で隠しディレクトリを走査しない。
#   nvim の設定は home/.config/ 配下 (ドットで始まる) にあるため、
#   --no-ignore hidden を付けないと 1 件も検査されず exit 0 で素通りする。
#   pre-commit と CI の両方でこのフラグを付けている。
#   ast-grep test は仮想のスニペットに対して走るため files と ignores を通らない。
#   したがってこの glob を検査できるのは scripts/tests/ast-grep.bats の fixture だけである。
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

`ast-grep scan` は既定で隠しディレクトリを走査しない。nvim の設定は `home/.config/` 配下にあるため、素の `ast-grep scan` は 1 件も検査せず必ず 0 件で終わる。これは「違反が無い」ではなく「何も見ていない」状態であり、完璧な偽の緑である。`--no-ignore hidden` を必ず付ける。

Run: `ast-grep scan --no-ignore hidden`

Expected: `nvim-lua-no-hex-literal` の error が 0 件。既存の `bats-*` ルールも 0 件のまま。

もし error が出るなら、Task 2 / Task 3 / Task 3c のいずれかで hex を追い出しきれていない。
`plugins/lualine.lua` は Task 3c が `palette.surfaces` へ移し済みである。該当ファイルを直す。

exit code も直接確かめる。出力をパイプに繋ぐとパイプ先の exit code に化けるので繋がないこと。

```bash
ast-grep scan --no-ignore hidden >/dev/null 2>&1
echo "exit=$?"
```

Expected: `exit=0`

- [ ] **Step 6: glob と隠しディレクトリを bats で検査する**

`ast-grep test` は仮想のスニペットに対して走るため、`files` と `ignores` の glob を一度も通らない。したがってルールの「どのファイルを見るか」の層はルールテストでは検査できない。fixture のディレクトリツリーを作り、リポジトリの実ルールをそこへコピーして検査する。ルールをテスト側に書き写すと二重管理になるため、必ず実ファイルをコピーする。

`scripts/tests/ast-grep.bats` を新設する。

```bash
#!/usr/bin/env bats
# =============================================================================
# ast-grep のルールが「どのファイルを見るか」を検証する
#
# ast-grep test は仮想のスニペットに対して走るため files と ignores を通らない。
# glob と隠しディレクトリの扱いを確かめられるのはこのファイルだけである。
#
# 注意: @test 名は ASCII に限る (rules/bats-test-name-ascii-only.yml)
# =============================================================================

load test_helper

RULE="$REPO_ROOT/rules/nvim-lua-no-hex-literal.yml"

setup() {
    if ! command -v ast-grep >/dev/null 2>&1; then
        if [ -n "${CI:-}" ]; then
            echo "ast-grep is required in CI but was not found" >&2
            return 1
        fi
        skip "ast-grep is not installed"
    fi

    # 本番と同じ相対パスを持つ fixture を作る。
    # 実ルールをコピーするので、ルールの二重管理にならない
    FIXTURE="$(mktemp -d)"
    mkdir -p "$FIXTURE/rules" "$FIXTURE/home/.config/nvim/lua/config"
    cp "$RULE" "$FIXTURE/rules/"
    printf 'ruleDirs:\n  - rules\n' > "$FIXTURE/sgconfig.yml"
}

teardown() {
    if [ -n "${FIXTURE:-}" ]; then
        rm -rf "$FIXTURE"
    fi
}

scan() {
    (cd "$FIXTURE" && ast-grep scan --no-ignore hidden 2>&1)
}

scan_exit() {
    (cd "$FIXTURE" && ast-grep scan --no-ignore hidden >/dev/null 2>&1)
}

@test "the rule catches a hex literal under the hidden nvim config path" {
    printf 'return { X = { fg = "#123456" } }\n' > "$FIXTURE/home/.config/nvim/lua/config/markdown.lua"

    run scan
    assert_contains "$output" "nvim-lua-no-hex-literal"
    assert_contains "$output" "markdown.lua"

    run scan_exit
    [ "$status" -eq 1 ] || return 1
}

@test "the rule exempts palette lua" {
    printf 'return { X = { fg = "#123456" } }\n' > "$FIXTURE/home/.config/nvim/lua/config/palette.lua"

    run scan
    refute_contains "$output" "nvim-lua-no-hex-literal"

    run scan_exit
    [ "$status" -eq 0 ] || return 1
}

@test "a comment holding a hex value is not a violation" {
    printf -- '-- コメントの中の hex #123abc は検出しない\nreturn { X = { fg = hex.muted } }\n' \
        > "$FIXTURE/home/.config/nvim/lua/config/markdown.lua"

    run scan
    refute_contains "$output" "nvim-lua-no-hex-literal"

    run scan_exit
    [ "$status" -eq 0 ] || return 1
}

@test "without no-ignore hidden the scan silently sees nothing" {
    # なぜ --no-ignore hidden が要るのかを実行可能な事実として残す。
    # ast-grep が既定で隠しディレクトリを飛ばさなくなったら、このテストが赤くなって教えてくれる
    printf 'return { X = { fg = "#123456" } }\n' > "$FIXTURE/home/.config/nvim/lua/config/markdown.lua"

    run bash -c "cd '$FIXTURE' && ast-grep scan 2>&1"
    refute_contains "$output" "nvim-lua-no-hex-literal"

    run bash -c "cd '$FIXTURE' && ast-grep scan >/dev/null 2>&1"
    [ "$status" -eq 0 ] || return 1
}

@test "every ast-grep scan invocation searches hidden directories" {
    # --no-ignore hidden が無いと nvim の Lua を 1 件も検査しないまま緑になる。
    # ルールの検出力は上のテストが守るが、呼び出し側の配線を守るのはここだけである。
    #
    # 実行行だけを見るため entry: と run: で錨を打つ。
    # そうしないと pre-commit の name: ast-grep scan (...) という表示名まで拾って常に赤くなる。
    # CI の workflow は Task 5 が追加するので、そのときここへ足す
    pre_commit="$REPO_ROOT/.pre-commit-config.yaml"
    invocation='(entry|run):[[:space:]]*ast-grep scan'

    # 呼び出しが 0 件だと下の検査が空回りして緑になる
    calls=$(grep -cE "$invocation" "$pre_commit" || true)
    [ "$calls" -ge 1 ] || return 1

    missing=$(grep -hE "$invocation" "$pre_commit" | grep -cv -- '--no-ignore hidden' || true)
    [ "$missing" = "0" ] || return 1
}
```

fixture の中では設計値を使わない。コメントと文字列の区別を確かめるのに `palette.lua` が持つ値は要らず、任意の hex で同じ検査ができる。設計値を書き写すと、値を変えたときに fixture が黙って嘘になる。

Run: `bats scripts/tests/ast-grep.bats`

Expected: 最初の 4 件は PASS。`every ast-grep scan invocation searches hidden directories` だけが FAIL する。この時点の `.pre-commit-config.yaml` の `entry` にはまだフラグが無いためである。これが RED であり、Step 8 で緑になる。

- [ ] **Step 7: 変異注入でルールが効くことを確認する**

`markdown.lua` は `return { ... }` で終わる。Lua では `return` はブロックの最後の文でなければならないため、ファイル末尾に行を追記すると構文エラーになる。tree-sitter は ERROR ノードを作り、`kind: string` は成立しない。つまり末尾への追記ではルールが健全でも赤くならない。必ずテーブルの中へ、構文として正当な形で注入する。

```bash
perl -0pi -e 's/\nreturn \{\n/\nreturn {\n    ZZTest = { fg = "#123456" },\n/' home/.config/nvim/lua/config/markdown.lua
ast-grep scan --no-ignore hidden
ast-grep scan --no-ignore hidden >/dev/null 2>&1
echo "exit=$?"
```

Expected: `nvim-lua-no-hex-literal` の error が `markdown.lua` に 1 件出て、`exit=1` になる。

確認したら元へ戻す。この時点でコミットは済んでいないため、`git checkout` は使わず注入した行だけを消す。

```bash
perl -0pi -e 's/\n    ZZTest = \{ fg = "#123456" \},//' home/.config/nvim/lua/config/markdown.lua
grep -c ZZTest home/.config/nvim/lua/config/markdown.lua
ast-grep scan --no-ignore hidden >/dev/null 2>&1
echo "exit=$?"
```

Expected: `ZZTest` が 0 件で `exit=0`。

- [ ] **Step 8: pre-commit のフックを直す**

`.pre-commit-config.yaml` の `ast-grep-scan` フックを 2 箇所変える。

`entry` にフラグを足す。これが無いと nvim の Lua を 1 件も検査しない。

変更前:

```yaml
        entry: ast-grep scan
```

変更後:

```yaml
        entry: ast-grep scan --no-ignore hidden
```

`files` に Lua を足す。

変更前:

```yaml
        files: ^(.*\.bats|sgconfig\.yml|rules/.*)$
```

変更後:

```yaml
        files: ^(.*\.bats|.*\.lua|sgconfig\.yml|rules/.*)$
```

`ast-grep scan` は `pass_filenames: false` でリポジトリ全体を走るので、`files` は「いつ走らせるか」の条件でしかない。Lua を変更したときにも走るようにする。

- [ ] **Step 9: pre-commit と bats が通ることを確認する**

```bash
pre-commit run --all-files
bats scripts/tests/
```

Expected: `ast-grep scan` と `ast-grep test` が Passed。他のフックも Passed か Skipped。bats は全緑。

- [ ] **Step 10: コミットする**

```bash
mkdir -p tmp
cat > tmp/commitmsg.txt <<'EOF'
ci: nvim の Lua に色の hex リテラルを書くことを ast-grep で禁止する

- palette.lua だけを ignore し 写像側へのハードコードを構文レベルで弾く
- kind: string に regex を掛けるのが要点
  grep だとコメントに書いた実測値まで誤検出するが
  ast-grep は文字列ノードだけを見るのでコメントは無視される
  実効背景の実測値を根拠としてコメントに残せることは重要なのでこの区別が要る
- ast-grep scan は既定で隠しディレクトリを走査しない
  nvim の設定は home/.config 配下にあるため --no-ignore hidden が無いと
  1 件も検査せず exit 0 で素通りする
- ast-grep test は仮想スニペットに走るため files と ignores を通らない
  glob と隠しディレクトリの扱いは fixture を使った bats で検査する
- rule-tests で valid 6 形と invalid 4 形を固定する
- pre-commit の ast-grep scan が Lua の変更でも走るよう files を広げる
EOF
git add rules/nvim-lua-no-hex-literal.yml rule-tests/nvim-lua-no-hex-literal-test.yml scripts/tests/ast-grep.bats .pre-commit-config.yaml
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
- Test: `scripts/tests/ast-grep.bats`

**Interfaces:**
- Consumes: `rules/` と `rule-tests/` と `sgconfig.yml` (Task 4 が提供)
- Produces: なし

**controller が実測済みの事実 (再検証は不要):**

Task 4 の完了時点で変異注入を行ったところ、`.pre-commit-config.yaml` の `entry` から `--no-ignore hidden` を外すと、`markdown.lua` に hex リテラルが実在する状態でも `pre-commit run ast-grep-scan` は exit 0 で通り、`bats scripts/tests/` も全緑のままだった。フラグは一見すると余計に見えるため消されやすく、消えても誰も気づかない。ルールの検出力は守られているが、配線が守られていない。

Task 4 は `scripts/tests/ast-grep.bats` に `every ast-grep scan invocation searches hidden directories` を追加し、pre-commit 側の配線を固定した。CI 側は workflow がまだ存在しなかったため対象外だった。このタスクで同じテストを CI へ広げる。

もうひとつ、Task 4 が持ち込んだ CI の不整合を直す必要がある。`scripts/tests/ast-grep.bats` の `setup()` は、CI では `ast-grep` が無いときに skip せず fail する (緑のまま何も検証しない状態を防ぐため、`nvim` と同じ流儀)。ところが CI の `bats` ジョブは `ast-grep` を導入していない。controller がローカルで CI を模擬したところ (`env -i` で PATH を絞り `CI=true`)、5 件すべてが fail した。したがって `bats` ジョブにも `setup-ast-grep` を足す。

- [ ] **Step 1: 配線テストを CI へ広げる**

`scripts/tests/ast-grep.bats` の `every ast-grep scan invocation searches hidden directories` を書き換える。pre-commit だけを見ていたものを、workflow も見るようにする。

```bash
@test "every ast-grep scan invocation searches hidden directories" {
    # --no-ignore hidden が無いと nvim の Lua を 1 件も検査しないまま緑になる。
    # ルールの検出力は上のテストが守るが、呼び出し側の配線を守るのはここだけである。
    #
    # 実行行だけを見るため entry: と run: で錨を打つ。
    # そうしないと pre-commit の name: ast-grep scan (...) という表示名まで拾って常に赤くなる
    pre_commit="$REPO_ROOT/.pre-commit-config.yaml"
    workflow="$REPO_ROOT/.github/workflows/test.yml"
    invocation='(entry|run):[[:space:]]*ast-grep scan'

    # 呼び出しが 0 件だと下の検査が空回りして緑になる。
    # pre-commit と CI がそれぞれ 1 回以上呼んでいることを先に固定する
    pre_commit_calls=$(grep -cE "$invocation" "$pre_commit" || true)
    workflow_calls=$(grep -cE "$invocation" "$workflow" || true)
    [ "$pre_commit_calls" -ge 1 ] || return 1
    [ "$workflow_calls" -ge 1 ] || return 1

    # そのすべてがフラグを伴うこと
    missing=$(grep -hE "$invocation" "$pre_commit" "$workflow" | grep -cv -- '--no-ignore hidden' || true)
    [ "$missing" = "0" ] || return 1
}
```

- [ ] **Step 2: テストを実行して RED を確認する**

Run: `bats scripts/tests/ast-grep.bats -f "hidden directories"`

Expected: FAIL。`.github/workflows/test.yml` はまだ `ast-grep scan` を呼んでいないため `workflow_calls` が 0 になる。

- [ ] **Step 3: composite action を作る**

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

- [ ] **Step 4: ジョブを追加する**

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
      #
      # --no-ignore hidden が要る。ast-grep は既定で隠しディレクトリを走査しないため、
      # これが無いと home/.config 配下の nvim の Lua を 1 件も検査せず exit 0 で素通りする
      - name: Scan repository
        run: ast-grep scan --no-ignore hidden
```

- [ ] **Step 5: bats ジョブにも ast-grep を導入する**

`scripts/tests/ast-grep.bats` は CI で `ast-grep` が無いと skip せず fail する。`bats` ジョブは `scripts/tests/` を丸ごと走らせるため、導入しないとこのブランチを push した瞬間に CI が落ちる。

`.github/workflows/test.yml` の `bats` ジョブの `Setup Neovim` の直後に追加する。

```yaml
      - name: Setup ast-grep
        uses: ./.github/actions/setup-ast-grep
```

導入前後の挙動をローカルで確かめる。CI を 1 回も回さずに検証できる。

```bash
mkdir -p /tmp/ci-sim/bin
ln -sf "$(command -v bats)" /tmp/ci-sim/bin/bats
env PATH="/tmp/ci-sim/bin:/usr/bin:/bin:/usr/sbin:/sbin" CI=true bats scripts/tests/ast-grep.bats
```

Expected: 5 件すべて `not ok` になり、`ast-grep is required in CI but was not found` が出る。これが `bats` ジョブに `setup-ast-grep` が要る理由である。

- [ ] **Step 6: テストを実行して GREEN を確認する**

Run: `bats scripts/tests/`

Expected: 全テストが PASS。特に `every ast-grep scan invocation searches hidden directories` が緑になる。

- [ ] **Step 7: workflow の YAML が壊れていないことを確認する**

```bash
uv run --quiet --with pyyaml python -c "import yaml,sys; yaml.safe_load(open('.github/workflows/test.yml')); yaml.safe_load(open('.github/actions/setup-ast-grep/action.yml')); print('yaml ok')"
```

Expected: `yaml ok`

- [ ] **Step 8: sha256 が正しいことを手元で確認する**

CI が落ちてから気づくのを避けるため、action.yml に書いた値と実際のアーカイブを照合する。

```bash
curl --proto '=https' --tlsv1.2 -fsSL -o /tmp/ast-grep.zip "https://github.com/ast-grep/ast-grep/releases/download/0.44.1/app-x86_64-unknown-linux-gnu.zip"
shasum -a 256 /tmp/ast-grep.zip
```

Expected: `611f9e5e76f2611ecea1a35dd3468ceedf600641a11224b80341d79c6ee7b9dd`

action.yml の `expected_sha256` と一致すること。

- [ ] **Step 9: コミットする**

変異注入より先にコミットする。`git checkout <file>` は HEAD へ戻すため、コミットが復元点になる。

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
- --no-ignore hidden を欠いた scan は nvim の Lua を 1 件も検査しない
  フラグは余計に見えて消されやすいので 呼び出し側の配線をテストで固定する
- scripts/tests/ast-grep.bats は CI で ast-grep が無いと skip せず fail する
  bats ジョブにも setup-ast-grep を足さないと push した瞬間に CI が落ちる
  ローカルで CI を模擬して確認済み
- 既存の bats-no-bare-double-bracket と bats-test-name-ascii-only も
  CI で守られるようになる
EOF
git add .github/actions/setup-ast-grep/action.yml .github/workflows/test.yml scripts/tests/ast-grep.bats
git commit -F tmp/commitmsg.txt
```

- [ ] **Step 10: 変異注入で配線テストが効くことを確かめる**

コミット済みなので `git checkout <file>` で安全に戻せる。各変異のあと必ず戻して全緑を確認する。

変異注入 a (pre-commit のフラグを外す)。`.pre-commit-config.yaml` の `entry: ast-grep scan --no-ignore hidden` を `entry: ast-grep scan` にする。

Expected: `every ast-grep scan invocation searches hidden directories` が FAIL。他のテストは緑のまま。

変異注入 b (CI のフラグを外す)。`.github/workflows/test.yml` の `run: ast-grep scan --no-ignore hidden` を `run: ast-grep scan` にする。

Expected: 同じテストが FAIL。

変異注入 c (workflow から scan の呼び出しごと消す)。`run: ast-grep scan --no-ignore hidden` の行を削除する。

Expected: 同じテストが FAIL (`workflow_calls` が 0 になる)。呼び出しが消えたときに空回りして緑になる穴が塞がれていることを示す。

---

### Task 6: 実環境で live smoke を行う

ユニットテストが緑でも、実際に描画されるかは別問題である。neo-tree は lazy load されるため、プラグインの `setup()` が後から走ったときに定義を上書きしないかを実機で確かめる必要がある。

**Files:**
- 変更なし (確認のみ)

**Interfaces:**
- Consumes: Task 1 から Task 5 の成果すべて

- [ ] **Step 1: 実 config で neo-tree を読み込ませ、色が残ることを確認する**

`--clean` ではなく実際の設定 (lazy.nvim 経由) で起動し、neo-tree の `setup()` が走ったあとの色を取る。probe が通る `--clean` の rtp とはロード経路が違うため、ここを通さないと `create_highlight_group` による上書きを見逃す。

期待値は `config.neotree` から引く。書き写すと色を変えたときに手順書が黙って嘘になる。

一時ファイル `/tmp/live_smoke.lua` に次を書く。

```lua
local neotree = require("config.neotree")

local function fg_of(group)
    local hl = vim.api.nvim_get_hl(0, { name = group, link = false })
    return hl.fg and string.format("#%06x", hl.fg) or nil
end

local names = {}
for name in pairs(neotree) do
    names[#names + 1] = name
end
table.sort(names)

local mismatches = 0
for _, name in ipairs(names) do
    local want, got = neotree[name].fg, fg_of(name)
    if got ~= want then
        mismatches = mismatches + 1
    end
    print(string.format("%s %-22s want=%s got=%s", (got == want) and "OK  " or "FAIL", name, tostring(want), tostring(got)))
end
print("LIVE_NEOTREE_MISMATCHES=" .. mismatches)
print("LIVE_NEOTREE_CHECKED=" .. #names)
print("INDENT_MARKER_LINK=" .. tostring(vim.api.nvim_get_hl(0, { name = "NeoTreeIndentMarker" }).link))
```

```bash
nvim --headless -c 'Neotree show' -c 'luafile /tmp/live_smoke.lua' -c 'qa!' 2>&1
```

Expected: `LIVE_NEOTREE_MISMATCHES=0` かつ `LIVE_NEOTREE_CHECKED=9`。

`INDENT_MARKER_LINK=nil` であること。`NeoTreeDimText` が出たら既定の link を上書きできていない。

`FAIL` が出たら neo-tree の `create_highlight_group` が定義を上書きしている。その場合は `apply()` を neo-tree の setup 後にも走らせる必要があるので、`FileType neo-tree` の autocmd を追加して再度確認する。

- [ ] **Step 2: link 経由の伝播を実機で確認する**

`neotree.lua` は `NeoTreeIgnored` / `NeoTreeWindowsHidden` / `NeoTreeGitUnstaged` を定義しない。link で修正が伝播するという前提に立っているので、実機で確かめる。

一時ファイル `/tmp/link_check.lua` に次を書く。

```lua
local hex = require("config.palette").hex

local function fg_of(group)
    local hl = vim.api.nvim_get_hl(0, { name = group, link = false })
    return hl.fg and string.format("#%06x", hl.fg) or nil
end

local failures = 0
for _, e in ipairs({
    { "NeoTreeIgnored", hex.dotfile },
    { "NeoTreeWindowsHidden", hex.dotfile },
    { "NeoTreeGitUnstaged", hex.git_attention },
}) do
    local got = fg_of(e[1])
    if got ~= e[2] then
        failures = failures + 1
    end
    print(string.format("%s %-22s want=%s got=%s", (got == e[2]) and "OK  " or "FAIL", e[1], e[2], tostring(got)))
end
print("LINK_PROPAGATION_FAILURES=" .. failures)
```

```bash
nvim --headless -c 'Neotree show' -c 'luafile /tmp/link_check.lua' -c 'qa!' 2>&1
```

Expected: `LINK_PROPAGATION_FAILURES=0`

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

- [ ] **Step 4: 参照リンクの既知の挙動を機械的に確認する**

`[ref]` 全体が muted になることは spec に記録した既知の副作用である。目視ではなくキャプチャの解決結果で確かめる。

インジェクション言語 (`markdown_inline`) は `parser:parse(true)` を明示しないと解析されない。これを忘れると `@spell` しか観測できず、何も検証していない出力を見ることになる。

一時ファイル `/tmp/reflink.md` に `[label][ref]` と参照定義を書き、`/tmp/reflink_check.lua` に次を書く。

```lua
local hex = require("config.palette").hex

local parser = vim.treesitter.get_parser(0, "markdown")
parser:parse(true)

local function last_capture(row, col)
    local caps = vim.treesitter.get_captures_at_pos(0, row, col)
    if #caps == 0 then
        return nil, nil
    end
    return caps[#caps].capture, caps[#caps].lang
end

local function resolved_fg(capture, lang)
    local id = vim.api.nvim_get_hl_id_by_name("@" .. capture .. "." .. lang)
    local hl = vim.api.nvim_get_hl(0, { id = id, link = false })
    return hl.fg and string.format("#%06x", hl.fg) or nil
end

local line = vim.api.nvim_buf_get_lines(0, 0, 1, false)[1]
for col = 0, #line - 1 do
    local capture, lang = last_capture(0, col)
    print(string.format("col=%2d char=%s last=%s fg=%s", col, line:sub(col + 1, col + 1), tostring(capture), tostring(capture and resolved_fg(capture, lang))))
end
print("MUTED=" .. hex.muted)
print("LINK_LABEL=" .. hex.link_label)
```

```bash
nvim --headless /tmp/reflink.md -c 'luafile /tmp/reflink_check.lua' -c 'qa!' 2>&1
```

Expected:

- `[label]` の角括弧は `markup.link` で MUTED、`label` の 5 文字は `markup.link.label` で LINK_LABEL
- `[ref]` は角括弧も中身も `markup.link` で MUTED になる (後勝ち)

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
- `ast-grep scan --no-ignore hidden` が exit 0 (フラグを欠いた素の `ast-grep scan` は 1 件も検査しないので完了判定に使えない)
- CI の `ast-grep (syntax lint)` ジョブが success
- Task 6 の live smoke の全項目が目視で確認済み
- 色の hex が `home/.config/nvim/lua/config/palette.lua` 以外に存在しない (テストの probe と fixture は意図的な例外)
