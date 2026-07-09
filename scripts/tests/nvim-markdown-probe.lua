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

-- colorscheme の読み込みは hi clear を伴うため、autocmd が無いと定義が消える
vim.cmd("colorscheme habamax")
print("AFTER_CS_NORMAL_BG=" .. tostring(highlight("Normal").bg))
print("AFTER_CS_H1_FG=" .. tostring(highlight("@markup.heading.1").fg))
