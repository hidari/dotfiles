return {
    {
        "neovim/nvim-lspconfig",
        event = { "BufReadPre", "BufNewFile" },
        dependencies = {
            { "mason-org/mason.nvim", opts = {} },
            "mason-org/mason-lspconfig.nvim",
            "saghen/blink.cmp",
        },
        config = function()
            -- 各言語サーバーとサーバー固有設定
            local servers = {
                lua_ls = {
                    settings = {
                        Lua = {
                            -- `vim`をグローバルとして認識させて誤診断を消す
                            diagnostics = { globals = { "vim" } },
                        },
                    },
                },
                ts_ls = {},        -- JavaScript / TypeScript / TSX
                html = {},
                cssls = {},
                jsonls = {},
                pyright = {},      -- Python
                gopls = {},        -- Go
                rust_analyzer = {},-- Rust
                yamlls = {},
                taplo = {},        -- TOML
            }

            -- blink.cmpの補完ケイパビリティを全サーバー共通で有効化
            local capabilities = require("blink.cmp").get_lsp_capabilities()
            vim.lsp.config("*", { capabilities = capabilities })

            -- サーバーごとの設定を登録（有効化はmason-lspconfigが行う）
            for name, cfg in pairs(servers) do
                vim.lsp.config(name, cfg)
            end

            require("mason").setup()
            require("mason-lspconfig").setup({
                -- 未導入のサーバーは自動インストール
                ensure_installed = vim.tbl_keys(servers),
                -- 既定でinstalled serverをvim.lsp.enable()する(v2)
            })

            -- LSPがバッファにアタッチしたとき、便利なキーマップを設定
            vim.api.nvim_create_autocmd("LspAttach", {
                callback = function(ev)
                    local map = function(keys, fn, desc)
                        vim.keymap.set("n", keys, fn, { buffer = ev.buf, desc = desc })
                    end
                    map("gd", vim.lsp.buf.definition, "定義へジャンプ")
                    map("gr", vim.lsp.buf.references, "参照一覧")
                    map("gi", vim.lsp.buf.implementation, "実装へジャンプ")
                    map("K", vim.lsp.buf.hover, "ホバー情報を表示")
                    map("<leader>rn", vim.lsp.buf.rename, "シンボル名をリネーム")
                    map("<leader>ca", vim.lsp.buf.code_action, "コードアクション")
                    map("<leader>f", function()
                        vim.lsp.buf.format({ async = true })
                    end, "フォーマット")
                    map("[d", function() vim.diagnostic.jump({ count = -1 }) end, "前の診断へ")
                    map("]d", function() vim.diagnostic.jump({ count = 1 }) end, "次の診断へ")
                    map("<leader>d", vim.diagnostic.open_float, "診断をフロートで表示")
                end,
            })
        end,
    }
}
