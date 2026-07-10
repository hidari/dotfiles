-- Markdown の配色。
--
-- 副作用を持たず、ハイライトグループ名から nvim_set_hl の引数テーブルへの写像だけを返す。
-- 色は config.palette が単一の真実として持つ。
-- 適用は config.appearance の apply() が一手に引き受ける (colorscheme で消えるため再適用が要る)。
--
-- conceal 機能 (テキストを隠す conceallevel) は使わず、conceallevel は 0 のまま。
-- @conceal.markdown_inline は tree-sitter のキャプチャ名であり、記号を隠さず色を当てるためだけに使う。
-- 見出しは明度を上げて本文より目立たせ、階層は色相で分ける。色相だけに頼らないよう bold も併用する。
--
-- @markup.heading.marker は after/queries/markdown/highlights.scm が定義する拡張キャプチャで、
-- 既定のクエリには存在しない。
--
-- @punctuation.special / @conceal / @label / @markup.link は他の文法とも共有する汎用キャプチャ名なので、
-- 素で定義すると非 markdown のバッファへ色が漏れる。言語サフィックス付き
-- (@<capture>.markdown / @<capture>.markdown_inline) にすると tree-sitter highlighter が
-- その言語でだけ解決し (vim/treesitter/highlighter.lua の @<name>.<lang> 構築)、
-- 他言語では素の @<capture> にフォールバックするため漏れが止まる。
--
-- @markup.link が捕捉するのは URL ではなくリンクの記号 ( [ ] ( ) ! ) である。
-- 参照リンク [label][ref] の [ref] は @markup.link.label の後に @markup.link が評価されて
-- 後勝ちするため、[ref] 全体が muted になる (実測で確認済みの既知の挙動)。

local hex = require("config.palette").hex

return {
    -- 見出し: 階層を色相で分け、本文より明るくする
    ["@markup.heading.1"] = { fg = hex.heading_1, bold = true },
    ["@markup.heading.2"] = { fg = hex.heading_2, bold = true },
    ["@markup.heading.3"] = { fg = hex.heading_3, bold = true },
    ["@markup.heading.4"] = { fg = hex.heading_4, bold = true },
    ["@markup.heading.5"] = { fg = hex.heading_5, bold = true },
    ["@markup.heading.6"] = { fg = hex.heading_6, bold = true },

    -- 見出しの # 記号だけを引っ込める (拡張クエリ由来のキャプチャ)
    ["@markup.heading.marker"] = { fg = hex.muted },

    -- 引用の > 、表の | 、水平線の --- (markdown ブロック文法)
    ["@punctuation.special.markdown"] = { fg = hex.muted },

    -- リストマーカー ( - や 1. )
    ["@markup.list"] = { fg = hex.list_marker },

    -- インラインの記号 ( * ~ ` ) を引っ込める。markdown_inline の @conceal キャプチャ
    ["@conceal.markdown_inline"] = { fg = hex.muted },

    -- リンクの記号 ( [ ] ( ) ! ) を引っ込める
    ["@markup.link.markdown_inline"] = { fg = hex.muted },

    -- 強調
    ["@markup.strong"] = { fg = hex.strong, bold = true },
    ["@markup.italic"] = { italic = true },
    ["@markup.strikethrough"] = { fg = hex.strikethrough, strikethrough = true },

    -- コード: インラインは目立たせ、ブロックは注入された言語の色を邪魔しない
    ["@markup.raw"] = { fg = hex.inline_code },
    ["@markup.raw.block"] = { fg = hex.code_block },
    -- コードフェンスの言語ラベル (markdown ブロック文法)
    ["@label.markdown"] = { fg = hex.muted },

    -- 引用文
    ["@markup.quote"] = { fg = hex.quote, italic = true },

    -- リンク
    ["@markup.link.label"] = { fg = hex.link_label, underline = true },
    ["@markup.link.url"] = { fg = hex.muted, underline = true },

    -- チェックボックス
    ["@markup.list.checked"] = { fg = hex.checked },
    ["@markup.list.unchecked"] = { fg = hex.unchecked },
}
