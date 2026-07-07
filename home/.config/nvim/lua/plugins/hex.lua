return {
    {
        "RaafatTurki/hex.nvim",
        -- コマンドかキーを使ったとき初めて読み込む（起動を軽く保つ）
        cmd = { "HexToggle", "HexDump", "HexAssemble" },
        keys = {
            { "<leader>x", "<cmd>HexToggle<cr>", desc = "Hex(16進)表示をトグル" },
        },
        opts = {}, -- デフォルト設定でセットアップ（内部でxxdを使用）
    }
}
