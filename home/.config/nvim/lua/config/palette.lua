-- 配色の色トークン。
--
-- reference_background は、ターミナルの背景を透過させた結果として文字の背後に
-- 実際に現れる色のうち、最も明るくなるケースを取っている。
--
-- 導出:
--   Ghostty のテーマ Mariana の背景 #343d46 を background-opacity 0.8 で背後のウィンドウと
--   合成する。背後が白いとき 0.8 * #343d46 + 0.2 * #ffffff となり、この値になる。
--   スクリーンショットの実測最頻色と一致することを確認済み。
--   背後が黒いときは #2a3138 まで暗くなるが、暗い方向はコントラストが上がるだけなので、
--   明るい方 (最悪ケース) を基準に取れば全ての状況で読める。
--
-- 前提: Ghostty の theme = Mariana と background-opacity = 0.8。
--       ~/.config/ghostty/config は dotfiles の symlink 管理下にないため、他のマシンでは再現されない。
--
-- 記号を暗くして後退させることはできない。実効背景は明るい方向にしか動かず、
-- 暗い前景は必ず背景に溶ける。後退は彩度を落として表現する。
--
-- 各色は tier を持ち、基準背景に対する WCAG コントラスト比の下限を宣言する。
-- 検査は scripts/tests/nvim-markdown-probe.lua が行う。

local M = {}

M.reference_background = "#5d646b"

-- tier ごとの最低コントラスト比。
-- 本文の前景 (Mariana の #d8dee9) が基準背景に対して 4.44:1 で、これが事実上の上限になる。
M.minimum_contrast = {
    text = 4.0, -- 読む前景
    accent = 3.5, -- 補助的に読む前景
    symbol = 3.0, -- 意図的に後退させる記号
    decoration = 2.0, -- 装飾
}

-- 複数のトークンが共有する色。hex を一箇所にまとめて drift を防ぐ。
local RECEDED = "#aab6e4"
local LEAF_GREEN = "#a7d388"

M.colors = {
    -- 見出し: 階層を色相で分ける。OKLCh 色相環で隣接色相差 30 度以上を確保している
    heading_1 = { hex = "#83e4d4", tier = "text" },
    heading_2 = { hex = "#f0d399", tier = "text" },
    heading_3 = { hex = "#edc5ff", tier = "text" },
    heading_4 = { hex = "#aad9ff", tier = "text" },
    heading_5 = { hex = "#b6df9c", tier = "text" },
    heading_6 = { hex = "#8ee0f1", tier = "text" },

    strong = { hex = "#dcdfe4", tier = "text" },

    -- マークアップ記号とファイラの薄字。彩度を元の 30% まで落として後退させる
    muted = { hex = "#b5b8bc", tier = "symbol" },

    -- 赤は高輝度で sRGB のガマットが痩せる。text tier まで上げると淡いピンクになり
    -- コードであることの手がかりが失われるため accent tier に置いて赤みを残す
    inline_code = { hex = "#ffb2b4", tier = "accent" },
    code_block = { hex = "#b6c5f5", tier = "accent" },
    list_marker = { hex = "#75d4e1", tier = "accent" },
    link_label = { hex = "#90ccff", tier = "accent" },
    quote = { hex = LEAF_GREEN, tier = "accent" },
    checked = { hex = LEAF_GREEN, tier = "accent" },

    strikethrough = { hex = RECEDED, tier = "symbol" },
    unchecked = { hex = RECEDED, tier = "symbol" },

    line_number = { hex = "#64d9c7", tier = "accent" },
    cursor_line_number = { hex = "#e6c17b", tier = "accent" },

    -- ファイラ
    dotfile = { hex = "#a8b6e7", tier = "symbol" },
    gitignored = { hex = RECEDED, tier = "symbol" },
    -- git が注意を促す状態 (未追跡 / 衝突 / unstaged)。
    -- neo-tree は git status の色を filtered の色より後に上書きするため、
    -- この色はファイル名そのものに乗る。したがって読む前景として text tier に置く
    git_attention = { hex = "#ffc8a1", tier = "text" },
    -- ツリーのインデント線は装飾なので、見えるが目立たない位置に置く
    indent_guide = { hex = "#959594", tier = "decoration" },
}

-- 写像側が使う平坦な表。colors から導出するので二重管理にならない。
M.hex = {}
for token, spec in pairs(M.colors) do
    M.hex[token] = spec.hex
end

return M
