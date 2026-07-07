return {
    {
        "nvim-neo-tree/neo-tree.nvim",
        branch = "v3.x",
        dependencies = {
            "nvim-lua/plenary.nvim",
            "MunifTanjim/nui.nvim",
            "nvim-tree/nvim-web-devicons", -- optional, but recommended
        },
        -- 起動時は非表示。キーを押したタイミングで初めて読み込む
        cmd = "Neotree",
        keys = {
            { "<leader>e", "<cmd>Neotree toggle<cr>", desc = "ファイラを開閉" },
            {
                "<leader>o",
                function()
                    if vim.bo.filetype == "neo-tree" then
                        vim.cmd.wincmd("p") -- ツリーにいるなら直前の編集画面へ戻る
                    else
                        vim.cmd("Neotree focus") -- 編集画面にいるならツリーへ移動（無ければ開く）
                    end
                end,
                desc = "ファイラ⇄編集を行き来",
            },
        },
        opts = {
            close_if_last_window = true, -- neo-treeが最後の窓なら自動で閉じる
            window = {
                position = "left",
            },
            filesystem = {
                filtered_items = {
                    visible = true,        -- 隠しファイル/ディレクトリを最初から表示
                    hide_dotfiles = false, -- ドットファイルを隠さない
                    hide_gitignored = false, -- gitignore対象も隠さない
                },
                window = {
                    mappings = {
                        ["H"] = "none",                  -- デフォルトのHトグルを無効化
                        ["<leader>h"] = "toggle_hidden", -- 隠しファイル表示トグルをleaderに統一
                    },
                },
            },
        },
    }
}
