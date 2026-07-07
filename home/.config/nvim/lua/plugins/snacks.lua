-- herdrペイン内では端末の画像対応クエリに応答が返らずnvimがフリーズするため、
-- herdrの外（素のGhostty等）で起動したときだけ画像機能を有効にする。
local function in_herdr()
    for key, _ in pairs(vim.fn.environ()) do
        if key:find("^HERDR") then
            return true
        end
    end
    return false
end

local images_ok = not in_herdr()

-- カーソル行のmarkdown画像リンク ![alt](path) からパスを取り出して
-- 別タブでフルサイズ表示する（大きく見たい・ズームしたいとき用）
local function open_image_under_cursor()
    if not images_ok then
        vim.notify("herdr内では画像表示は無効です（素のGhosttyで開いてね）", vim.log.levels.WARN)
        return
    end
    local line = vim.api.nvim_get_current_line()
    local src = line:match("!%[.-%]%((.-)%)") or line:match("%((.-)%)")
    if not src or src == "" then
        vim.notify("この行に画像リンクが見つからないよ", vim.log.levels.WARN)
        return
    end
    -- 相対パスは現在ファイルのディレクトリ基準で解決
    if not src:match("^/") and not src:match("^%a[%w+.-]*://") then
        local dir = vim.fn.expand("%:p:h")
        src = vim.fs.normalize(dir .. "/" .. src)
    end
    vim.cmd("tabedit " .. vim.fn.fnameescape(src))
end

return {
    {
        "folke/snacks.nvim",
        priority = 1000,
        lazy = false,
        opts = {
            -- 単体の画像ファイルを開いたときは画面内にインライン描画する
            -- 前提: Ghostty(Kittyグラフィックス) + ImageMagick(magick)
            image = {
                enabled = images_ok,
                -- markdown等ドキュメント内の画像リンクは自動展開しない
                doc = {
                    enabled = false,
                },
            },
        },
        keys = {
            {
                "<leader>i",
                function()
                    if images_ok then
                        -- カーソル位置の画像をフローティングで小さくプレビュー
                        Snacks.image.hover()
                    else
                        vim.notify(
                            "herdr内では画像表示は無効です（素のGhosttyで開いてね）",
                            vim.log.levels.WARN
                        )
                    end
                end,
                desc = "画像をプレビュー（小・カーソル位置）",
            },
            {
                "<leader>I",
                open_image_under_cursor,
                desc = "画像を別タブでフルサイズ表示（拡大縮小はGhosttyの⌘+/⌘−）",
            },
            {
                "<leader>bd",
                function()
                    -- ウィンドウ/分割のレイアウトを保ったまま現在のバッファだけ閉じる
                    Snacks.bufdelete()
                end,
                desc = "現在のバッファを閉じる",
            },
        },
    }
}
