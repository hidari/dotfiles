-- ファイラ (neo-tree) の配色。
--
-- プラグインの設定は plugins/neo-tree.lua が持つ。ここは配色だけを持ち、副作用は無い。
-- 色は config.palette が単一の真実として持ち、適用は config.appearance の apply() が行う。
--
-- neo-tree はファイル名の色を、まず filtered (dotfile / gitignored など) で決め、
-- そのあと git status の色で上書きする (lua/neo-tree/sources/common/components.lua の M.name)。
-- このため未追跡ファイルは名前そのものが git の色で描かれる。
--
-- NeoTreeIgnored と NeoTreeWindowsHidden は NeoTreeDotfile への link なので、
-- ここで定義しなくても修正が伝播する。
-- NeoTreeGitUnstaged は NeoTreeGitConflict への link なので同様に伝播する。
--
-- グループ名は tree-sitter のキャプチャではないため、綴りを間違えても Neovim は黙って無視する。
-- 実在は scripts/tests/nvim-markdown.bats が neo-tree のソースに対して検査する。

local hex = require("config.palette").hex

return {
    -- 隠されている項目。名前で隠す指定とドットファイルは同じ意味なので同色にする
    NeoTreeDotfile = { fg = hex.dotfile },
    NeoTreeHiddenByName = { fg = hex.dotfile },

    -- gitignore 対象。dotfile よりさらに後退させる
    NeoTreeGitIgnored = { fg = hex.gitignored },

    -- git が注意を促す状態。ファイル名そのものに乗るので読める明るさが要る。
    -- 色だけに頼らないよう neo-tree 既定の italic を保つ
    NeoTreeGitUntracked = { fg = hex.git_attention, italic = true },
    NeoTreeGitConflict = { fg = hex.git_attention, bold = true, italic = true },

    -- 薄字。(empty folder) などのメッセージと、展開マーカーは状態を伝えるので見える必要がある
    NeoTreeDimText = { fg = hex.muted },
    NeoTreeMessage = { fg = hex.muted, italic = true },
    NeoTreeExpander = { fg = hex.muted },

    -- インデント線は装飾なので、既定の link (NeoTreeDimText) を外して控えめに残す
    NeoTreeIndentMarker = { fg = hex.indent_guide },
}
