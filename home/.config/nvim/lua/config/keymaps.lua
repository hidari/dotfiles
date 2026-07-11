-- インサートモードで「jj」を押すとEsc（ノーマルモードへ）
vim.keymap.set("i", "jj", "<Esc>", { silent = true, desc = "Insertモード解除" })

-- ノーマルモードで <leader>+「|」キー → 画面縦分割（:vsplit）
vim.keymap.set("n", "<leader>|", ":vsplit<cr>", { silent = true, desc = "縦分割" })
-- ノーマルモードで <leader>+「-」キー → 画面横分割（:split）
vim.keymap.set("n", "<leader>-", ":split<cr>", { silent = true, desc = "横分割" })

-- 画面分割後の画面間移動設定
vim.keymap.set("n", "<C-h>", "<C-w>h", { desc = "左ウィンドウへ" })
vim.keymap.set("n", "<C-j>", "<C-w>j", { desc = "下ウィンドウへ" })
vim.keymap.set("n", "<C-k>", "<C-w>k", { desc = "上ウィンドウへ" })
vim.keymap.set("n", "<C-l>", "<C-w>l", { desc = "右ウィンドウへ" })

-- バッファの移動（Shift+h → 前 / Shift+l → 次）
-- 旧: <C-[> は端末上ではEscと同一コードでEscが暴発するため変更
vim.keymap.set('n', '<S-h>', '<cmd>bprev<CR>', { desc = "前のバッファ" })
vim.keymap.set('n', '<S-l>', '<cmd>bnext<CR>', { desc = "次のバッファ" })
