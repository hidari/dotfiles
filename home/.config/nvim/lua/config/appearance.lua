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
