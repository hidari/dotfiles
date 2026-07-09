-- Markdown の配色。
--
-- 副作用を持たず、ハイライトグループ名から nvim_set_hl の引数テーブルへの写像だけを返す。
-- 適用は config.appearance の apply() が一手に引き受ける (colorscheme で消えるため再適用が要る)。
--
-- conceal は使わない。記号を隠す代わりに MUTED で暗くして視覚的に後退させる。
-- 見出しは明度を上げて本文より目立たせ、階層は色相で分ける。
--
-- @markup.heading.marker は after/queries/markdown/highlights.scm が定義する拡張キャプチャで、
-- 既定のクエリには存在しない。

-- マークアップ記号に使う色。本文より暗くして視覚的に後退させる
local MUTED = "#5c6370"

return {
    -- 見出し: 階層を色相で分け、本文より明るくする
    ["@markup.heading.1"] = { fg = "#7fdfd0", bold = true },
    ["@markup.heading.2"] = { fg = "#f0d399", bold = true },
    ["@markup.heading.3"] = { fg = "#d8a0f0", bold = true },
    ["@markup.heading.4"] = { fg = "#8ac6f7", bold = true },
    ["@markup.heading.5"] = { fg = "#b5dd9b", bold = true },
    ["@markup.heading.6"] = { fg = "#7fd4dd", bold = true },

    -- 見出しの # 記号だけを引っ込める (拡張クエリ由来のキャプチャ)
    ["@markup.heading.marker"] = { fg = MUTED },

    -- 引用の > 、表の | 、水平線の ---
    ["@punctuation.special"] = { fg = MUTED },

    -- リストマーカー ( - や 1. )
    ["@markup.list"] = { fg = "#56b6c2" },

    -- 強調
    ["@markup.strong"] = { fg = "#dcdfe4", bold = true },
    ["@markup.italic"] = { italic = true },
    ["@markup.strikethrough"] = { fg = "#6f7aa5", strikethrough = true },

    -- コード: インラインは目立たせ、ブロックは注入された言語の色を邪魔しない
    ["@markup.raw"] = { fg = "#e06c75" },
    ["@markup.raw.block"] = { fg = "#8f9dcc" },
    ["@label"] = { fg = MUTED },

    -- 引用文
    ["@markup.quote"] = { fg = "#98c379", italic = true },

    -- リンク
    ["@markup.link.label"] = { fg = "#61afef", underline = true },
    ["@markup.link.url"] = { fg = MUTED, underline = true },

    -- チェックボックス
    ["@markup.list.checked"] = { fg = "#98c379" },
    ["@markup.list.unchecked"] = { fg = "#6f7aa5" },
}
