return {
    {
        "saghen/blink.cmp",
        version = "1.*", -- プリビルドのファジーマッチャを自動取得する安定版
        event = "InsertEnter",
        dependencies = { "rafamadriz/friendly-snippets" },
        ---@module 'blink.cmp'
        ---@type blink.cmp.Config
        opts = {
            keymap = {
                -- 既定プリセット: <C-y>で確定 / <C-n><C-p>で候補移動 / <C-Space>で表示
                preset = "default",
            },
            appearance = {
                nerd_font_variant = "mono",
            },
            completion = {
                -- 選択中の候補のドキュメントを自動表示
                documentation = { auto_show = true },
            },
            -- 補完ソース: LSP / パス / スニペット / バッファ
            sources = {
                default = { "lsp", "path", "snippets", "buffer" },
            },
            fuzzy = { implementation = "prefer_rust_with_warning" },
        },
        opts_extend = { "sources.default" },
    }
}
