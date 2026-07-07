-- Tab入力をスペースに変換（タブ文字を使わない）
vim.opt.expandtab = true

-- Tab文字の表示幅を2スペースに設定
vim.opt.tabstop = 2

-- 自動インデントや >> << の移動幅を2スペースに設定
vim.opt.shiftwidth = 2

-- Tabキー押下時の実際の挿入スペース数（expandtab時）を2に設定
vim.opt.softtabstop = 2

-- 行番号を左端に表示
vim.opt.number = true

-- ファイルタイプ検出、プラグイン、インデントを有効化
vim.cmd("filetype plugin indent on")

-- Neovimのシステムクリップボードを有効化
vim.opt.clipboard:append('unnamedplus')

-- 行末で l を押したら次の行の先頭へ移動できるようにする
vim.opt.whichwrap:append('l')
