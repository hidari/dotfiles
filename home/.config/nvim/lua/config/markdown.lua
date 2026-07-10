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
-- 色を持つキャプチャはすべて言語サフィックス付き (@<capture>.markdown / @<capture>.markdown_inline) で
-- 定義する。素で定義すると tree-sitter highlighter の @ 名前空間フォールバックにより
-- 非 markdown のバッファ (:help = vimdoc / HTML / JSX 等) へ markdown の色が漏れる。
-- highlighter は @<capture>.<lang> を引き、未定義なら素の @<capture> へ落ちるので
-- (vim/treesitter/highlighter.lua の解決経路)、素を定義しなければ他文法では既定色に落ちて漏れが止まる。
-- サフィックスはそのキャプチャを産出する文法に合わせる (Neovim 同梱の highlights クエリで確定)。
-- 誤ると markdown でも色が出なくなる。属性だけの @markup.italic は fg を持たず
-- 漏れても無害なので素のまま残す。
--
-- 見出しマーカー (#) には markdown スコープで明示的に色を与える。
-- after/queries/markdown/highlights.scm が @markup.heading.N.marker で捕捉するが、
-- 見出しを @markup.heading.N.markdown へスコープしたため素の @markup.heading.N が消えており、
-- 階層フォールバックでは見出し色を継承できない。見出し行と同じ hex.heading_N を参照して同色にする
-- (同一変数参照なので literal の二重記述にはならず drift しない)。
--
-- @markup.link はリンクや画像のノード全体を捕捉する。記号 ( [ ] ( ) ! ) だけでなく
-- URL の範囲も含む。それでも URL に muted が乗らないのは、クエリの後方で宣言された
-- @markup.link.url が同じ範囲を捕捉して後勝ちするためであり、@markup.link が URL を
-- 構造的に除外しているわけではない。結果として muted が最終的に乗るのは記号だけになる。
-- 同じ理由で、参照リンク [label][ref] の [ref] は @markup.link.label の後に
-- @markup.link が評価されて後勝ちするため、[ref] 全体が muted になる (実測で確認済み)。

local hex = require("config.palette").hex

return {
    -- 見出し: 階層を色相で分け、本文より明るくする (markdown ブロック文法)
    ["@markup.heading.1.markdown"] = { fg = hex.heading_1, bold = true },
    ["@markup.heading.2.markdown"] = { fg = hex.heading_2, bold = true },
    ["@markup.heading.3.markdown"] = { fg = hex.heading_3, bold = true },
    ["@markup.heading.4.markdown"] = { fg = hex.heading_4, bold = true },
    ["@markup.heading.5.markdown"] = { fg = hex.heading_5, bold = true },
    ["@markup.heading.6.markdown"] = { fg = hex.heading_6, bold = true },

    -- 見出しマーカー (#): 見出しと同色。素の @markup.heading.N が無いので継承できず明示定義する
    ["@markup.heading.1.marker.markdown"] = { fg = hex.heading_1, bold = true },
    ["@markup.heading.2.marker.markdown"] = { fg = hex.heading_2, bold = true },
    ["@markup.heading.3.marker.markdown"] = { fg = hex.heading_3, bold = true },
    ["@markup.heading.4.marker.markdown"] = { fg = hex.heading_4, bold = true },
    ["@markup.heading.5.marker.markdown"] = { fg = hex.heading_5, bold = true },
    ["@markup.heading.6.marker.markdown"] = { fg = hex.heading_6, bold = true },

    -- 引用の > 、表の | 、水平線の --- (markdown ブロック文法)
    ["@punctuation.special.markdown"] = { fg = hex.muted },

    -- リストマーカー ( - や 1. ) (markdown ブロック文法)
    ["@markup.list.markdown"] = { fg = hex.list_marker },

    -- インラインの記号 ( * ~ ` ) を引っ込める。markdown_inline の @conceal キャプチャ
    ["@conceal.markdown_inline"] = { fg = hex.muted },

    -- リンクの記号 ( [ ] ( ) ! ) を引っ込める
    ["@markup.link.markdown_inline"] = { fg = hex.muted },

    -- 強調 (markdown_inline 産出)
    ["@markup.strong.markdown_inline"] = { fg = hex.strong, bold = true },
    -- 斜体は fg を持たず属性だけ。他文法へ漏れても無害なので素のまま残す
    ["@markup.italic"] = { italic = true },
    ["@markup.strikethrough.markdown_inline"] = { fg = hex.strikethrough, strikethrough = true },

    -- コード: インラインは目立たせ、ブロックは注入された言語の色を邪魔しない。
    -- インラインの raw (code_span) は markdown_inline 産出、フェンス/インデントの raw.block は markdown 産出
    ["@markup.raw.markdown_inline"] = { fg = hex.inline_code },
    ["@markup.raw.block.markdown"] = { fg = hex.code_block },
    -- コードフェンスの言語ラベル (markdown ブロック文法)
    ["@label.markdown"] = { fg = hex.muted },

    -- 引用文 (markdown ブロック文法)
    ["@markup.quote.markdown"] = { fg = hex.quote, italic = true },

    -- リンク。ラベルと URL は markdown と markdown_inline の両文法が産出する
    ["@markup.link.label.markdown"] = { fg = hex.link_label, underline = true },
    ["@markup.link.label.markdown_inline"] = { fg = hex.link_label, underline = true },
    ["@markup.link.url.markdown"] = { fg = hex.muted, underline = true },
    ["@markup.link.url.markdown_inline"] = { fg = hex.muted, underline = true },

    -- チェックボックス (markdown ブロック文法)
    ["@markup.list.checked.markdown"] = { fg = hex.checked },
    ["@markup.list.unchecked.markdown"] = { fg = hex.unchecked },
}
