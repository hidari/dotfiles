-- encodingの設定
vim.opt.fileencoding     = "utf-8"
vim.opt.encoding         = "utf-8"

-- leaderの設定
vim.g.mapleader          = " "
vim.g.maplocalleader     = "\\"

vim.g.loaded_netrw       = 1
vim.g.loaded_netrwPlugin = 1

-- プラグインマネージャーを読み込む
require("config.lazy")

-- configフォルダ配下の各Luaファイルを読み込む
require("config.appearance")
require("config.options")
require("config.keymaps")
require("config.autocmd")
require("config.cmd")

