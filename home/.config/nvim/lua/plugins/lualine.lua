local surfaces = require("config.palette").surfaces

return {
    {
        "nvim-lualine/lualine.nvim",
        dependencies = { "nvim-tree/nvim-web-devicons" },
        event = "VeryLazy",
        opts = {
            options = {
                theme = "auto",
                globalstatus = true, -- 画面下に1本の統合バー(laststatus=3相当)
                section_separators = "",
                component_separators = "|",
            },
            sections = {
                lualine_a = { "mode" },
                lualine_b = { "branch" },
                -- 開いてるバッファ一覧を下のバーに表示（アクティブなものが強調される）
                lualine_c = {
                    {
                        "buffers",
                        show_filename_only = true, -- パスでなくファイル名だけ
                        mode = 0,                  -- バッファ名を表示
                        symbols = {
                            modified = " ●", -- 未保存マーク
                            alternate_file = "", -- 直前バッファの余計な記号を消す
                            directory = "",
                        },
                        -- アクティブなバッファをtealでくっきり強調（追従が見えるように）
                        buffers_color = {
                            active = {
                                fg = surfaces.statusline_buffer_active.fg,
                                bg = surfaces.statusline_buffer_active.bg,
                                gui = "bold",
                            },
                            inactive = {
                                fg = surfaces.statusline_buffer_inactive.fg,
                                bg = surfaces.statusline_buffer_inactive.bg,
                            },
                        },
                    },
                },
                lualine_x = { "encoding", "filetype" },
                lualine_y = { "progress" },
                lualine_z = { "location" },
            },
            -- 上部のタブラインは使わない（下に出したいので）
            tabline = {},
        },
    }
}
