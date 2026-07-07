return {
    {
        "nvim-treesitter/nvim-treesitter",
        -- Neovim 0.12以降はmainブランチ（書き直し版）。lazy-loading非対応。
        branch = "main",
        lazy = false,
        build = ":TSUpdate",
        config = function()
            require("nvim-treesitter").setup()

            -- 対象言語のパーサ＆queryを（未導入なら）非同期でインストール。
            -- 前提: tree-sitter CLI(0.26.1+) と Cコンパイラが必要。
            local langs = {
                -- Lua / Neovim
                "lua", "luadoc", "vim", "vimdoc",
                -- Web
                "javascript", "typescript", "tsx", "html", "css", "scss",
                -- Python / Go / Rust
                "python", "go", "gomod", "gosum", "rust",
                -- 設定ファイル系（jsoncはjsonパーサが担当）
                "json", "yaml", "toml",
                -- その他
                "markdown", "markdown_inline", "bash", "regex", "gitignore",
            }
            require("nvim-treesitter").install(langs)

            -- ファイルを開いたとき、パーサが使えるならハイライトを開始する。
            vim.api.nvim_create_autocmd("FileType", {
                callback = function(args)
                    local ft = vim.bo[args.buf].filetype
                    local lang = vim.treesitter.language.get_lang(ft)
                    if not lang then
                        return
                    end
                    -- パーサ未導入ならスキップ（インストール完了後、次に開けば有効）
                    local ok, added = pcall(vim.treesitter.language.add, lang)
                    if ok and added then
                        pcall(vim.treesitter.start, args.buf, lang)
                    end
                end,
            })
        end,
    }
}
