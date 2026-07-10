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
