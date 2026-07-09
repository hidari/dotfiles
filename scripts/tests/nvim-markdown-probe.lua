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
