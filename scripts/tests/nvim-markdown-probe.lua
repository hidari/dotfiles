-- nvim の Markdown 配色の不変条件を headless で観測し KEY=VALUE 形式で出力する。
-- 判定は呼び出し側 (scripts/tests/nvim-markdown.bats) が行う。
--
-- nvim --clean で起動される前提。user config を読まないので lazy.nvim は動かず、
-- markdown / markdown_inline のパーサは Neovim 本体同梱のものが使われる。

local markdown = require("config.markdown")
local palette = require("config.palette")

-- 見出し 1..6 の fg が互いに異なること。同色だと階層が読めない
local levels, duplicates, seen = 0, 0, {}
for level = 1, 6 do
    local group = markdown["@markup.heading." .. level]
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
--
-- キーは 2 種類ある。
-- - 素のキー (@markup.strong 等) は markdown / markdown_inline どちらのキャプチャでもよいので
--   両方の和集合で照合する。
-- - 言語サフィックス付きのキー (@<capture>.markdown / @<capture>.markdown_inline) は汎用キャプチャを
--   特定言語へスコープするためのもの。素の @<capture> がその言語のクエリに実在することまで確かめる
--   (provenance を固定する。和集合照合より厳しい)。
local captures_by_lang = {}
local union = {}
for _, lang in ipairs({ "markdown", "markdown_inline" }) do
    local set = {}
    local query = vim.treesitter.query.get(lang, "highlights")
    if query then
        for _, name in ipairs(query.captures) do
            set["@" .. name] = true
            union["@" .. name] = true
        end
    end
    captures_by_lang[lang] = set
end

-- キーが言語サフィックス付きなら {素のキャプチャ名, 言語} を返す。素のキーなら nil。
-- markdown_inline を先に見る (markdown より長い接尾辞なので取りこぼさない)。
local function split_lang(group)
    for _, lang in ipairs({ "markdown_inline", "markdown" }) do
        local suffix = "." .. lang
        if group:sub(-#suffix) == suffix then
            return group:sub(1, #group - #suffix), lang
        end
    end
    return nil, nil
end

local missing = {}
for group in pairs(markdown) do
    local base, lang = split_lang(group)
    local present
    if lang then
        present = captures_by_lang[lang][base] == true
    else
        present = union[group] == true
    end
    if not present then
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
    if query.captures[id]:match("^markup%.heading%.%d%.marker$") then
        markers = markers + 1
    end
end
print("MARKER_CAPTURES=" .. markers)

-- **bold** の先頭 * (delimiter) 列で @markup.strong と @conceal のどちらが
-- 後からイテレートされるかを観測する。同一優先度では後発キャプチャが勝つため、
-- 記号を暗くする @conceal は @markup.strong より後に出る必要がある。
local strong_text = "**bold**"
local strong_parser = vim.treesitter.get_string_parser(strong_text, "markdown_inline")
local strong_tree = strong_parser:parse(true)[1]
local strong_query = vim.treesitter.query.get("markdown_inline", "highlights")
local strong_index, conceal_index, iter_index = nil, nil, 0
for id, node in strong_query:iter_captures(strong_tree:root(), strong_text, 0, -1) do
    iter_index = iter_index + 1
    local srow, scol = node:range()
    if srow == 0 and scol == 0 then
        local name = strong_query.captures[id]
        if name == "markup.strong" then
            strong_index = iter_index
        elseif name == "conceal" then
            conceal_index = iter_index
        end
    end
end
local conceal_after_strong = 0
if strong_index and conceal_index and conceal_index > strong_index then
    conceal_after_strong = 1
end
print("CONCEAL_AFTER_STRONG=" .. conceal_after_strong)

-- ここから適用側の観測。config.appearance は require した時点で apply() を 1 回走らせ、
-- ColorScheme autocmd を登録する。
require("config.appearance")

local function highlight(name)
    return vim.api.nvim_get_hl(0, { name = name, link = false })
end

print("NORMAL_BG=" .. tostring(highlight("Normal").bg))
print("H1_FG=" .. tostring(highlight("@markup.heading.1").fg))

-- 汎用キャプチャ名がグローバルへ muted を漏らしていないことを保証する。
-- markdown.lua は @<capture>.<lang> でスコープするので、他言語が共有する素の @<capture> は
-- muted を帯びてはならない。色は palette から直接取る
local MUTED_FG = tonumber(palette.hex.muted:sub(2), 16)
local bleed = 0
for _, name in ipairs({ "@punctuation.special", "@conceal", "@label", "@markup.link" }) do
    if highlight(name).fg == MUTED_FG then
        bleed = 1
    end
end
print("GLOBAL_BLEED=" .. bleed)

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

-- 逆に、スコープした markdown 用グループには MUTED が実際に乗っていること。
-- 漏れを止めた結果 markdown 側まで無色になっていないかを確かめる。
local scoped_applied = 1
for _, name in ipairs({
    "@punctuation.special.markdown",
    "@conceal.markdown_inline",
    "@label.markdown",
    "@markup.link.markdown_inline",
}) do
    if highlight(name).fg ~= MUTED_FG then
        scoped_applied = 0
    end
end
print("SCOPED_MUTED_APPLIED=" .. scoped_applied)

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

-- colorscheme の読み込みは hi clear を伴うため、autocmd が無いと定義が消える
vim.cmd("colorscheme habamax")
print("AFTER_CS_NORMAL_BG=" .. tostring(highlight("Normal").bg))
print("AFTER_CS_H1_FG=" .. tostring(highlight("@markup.heading.1").fg))

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
