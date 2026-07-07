-- ターミナルの背景をそのまま透過させたい場合
vim.api.nvim_set_hl(0, "Normal", { bg = "NONE", ctermbg = "NONE" })
vim.api.nvim_set_hl(0, "NormalNC", { bg = "NONE", ctermbg = "NONE" })

-- 通常の行番号の色（文字色: 明るいグレー, 背景色: デフォルト）
vim.api.nvim_set_hl(0, 'LineNr', { fg = '#53c9b8', bg = 'NONE' })

-- カーソルがある行の行番号の色（文字色: イエロー, 背景色: デフォルト）
vim.api.nvim_set_hl(0, 'CursorLineNr', { fg = '#e5c07b', bg = 'NONE', bold = true })

-- neo-treeの隠しファイル/gitignore対象が灰色すぎて見えない対策
vim.api.nvim_set_hl(0, 'NeoTreeDotfile', { fg = '#8f9dcc' })       -- ドットファイル（読みやすい青みグレー）
vim.api.nvim_set_hl(0, 'NeoTreeHiddenByName', { fg = '#8f9dcc' })  -- 名前で隠される項目も同色
vim.api.nvim_set_hl(0, 'NeoTreeGitIgnored', { fg = '#6f7aa5' })    -- gitignore対象は少し暗めで区別

