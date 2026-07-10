-- nvim の Markdown 配色の不変条件を headless で観測し KEY=VALUE 形式で出力する。
-- 判定は呼び出し側 (scripts/tests/nvim-markdown.bats) が行う。
--
-- nvim --clean で起動される前提。user config を読まないので lazy.nvim は動かず、
-- markdown / markdown_inline のパーサは Neovim 本体同梱のものが使われる。

local markdown = require("config.markdown")
local palette = require("config.palette")

-- 見出し 1..6 の fg が互いに異なること。同色だと階層が読めない
local levels, duplicates, seen = 0, 0, {}
for level = 1, 6 do
    local group = markdown["@markup.heading." .. level]
    if group and group.fg then
        levels = levels + 1
        if seen[group.fg] then
            duplicates = duplicates + 1
        end
        seen[group.fg] = true
    end
end
print("HEADING_LEVELS=" .. levels)
print("HEADING_FG_DUPLICATES=" .. duplicates)

-- 定義したグループ名が実際のキャプチャ集合に含まれること。
-- 含まれないグループへ色を定義しても Neovim はエラーを出さず黙って無視する。
--
-- キーは 2 種類ある。
-- - 素のキー (@markup.strong 等) は markdown / markdown_inline どちらのキャプチャでもよいので
--   両方の和集合で照合する。
-- - 言語サフィックス付きのキー (@<capture>.markdown / @<capture>.markdown_inline) は汎用キャプチャを
--   特定言語へスコープするためのもの。素の @<capture> がその言語のクエリに実在することまで確かめる
--   (provenance を固定する。和集合照合より厳しい)。
local captures_by_lang = {}
local union = {}
for _, lang in ipairs({ "markdown", "markdown_inline" }) do
    local set = {}
    local query = vim.treesitter.query.get(lang, "highlights")
    if query then
        for _, name in ipairs(query.captures) do
            set["@" .. name] = true
            union["@" .. name] = true
        end
    end
    captures_by_lang[lang] = set
end

-- キーが言語サフィックス付きなら {素のキャプチャ名, 言語} を返す。素のキーなら nil。
-- markdown_inline を先に見る (markdown より長い接尾辞なので取りこぼさない)。
local function split_lang(group)
    for _, lang in ipairs({ "markdown_inline", "markdown" }) do
        local suffix = "." .. lang
        if group:sub(-#suffix) == suffix then
            return group:sub(1, #group - #suffix), lang
        end
    end
    return nil, nil
end

local missing = {}
for group in pairs(markdown) do
    local base, lang = split_lang(group)
    local present
    if lang then
        present = captures_by_lang[lang][base] == true
    else
        present = union[group] == true
    end
    if not present then
        missing[#missing + 1] = group
    end
end
table.sort(missing)
print("MISSING_CAPTURES=" .. table.concat(missing, ","))

-- 拡張クエリが 6 段階すべての見出しマーカーを捕捉すること
local buffer = vim.api.nvim_create_buf(false, true)
vim.api.nvim_buf_set_lines(buffer, 0, -1, false, {
    "# h1", "## h2", "### h3", "#### h4", "##### h5", "###### h6",
})
local tree = vim.treesitter.get_parser(buffer, "markdown"):parse(true)[1]
local query = vim.treesitter.query.get("markdown", "highlights")
local markers = 0
for id in query:iter_captures(tree:root(), buffer, 0, -1) do
    if query.captures[id]:match("^markup%.heading%.%d%.marker$") then
        markers = markers + 1
    end
end
print("MARKER_CAPTURES=" .. markers)

-- **bold** の先頭 * (delimiter) 列で @markup.strong と @conceal のどちらが
-- 後からイテレートされるかを観測する。同一優先度では後発キャプチャが勝つため、
-- 記号を暗くする @conceal は @markup.strong より後に出る必要がある。
local strong_text = "**bold**"
local strong_parser = vim.treesitter.get_string_parser(strong_text, "markdown_inline")
local strong_tree = strong_parser:parse(true)[1]
local strong_query = vim.treesitter.query.get("markdown_inline", "highlights")
local strong_index, conceal_index, iter_index = nil, nil, 0
for id, node in strong_query:iter_captures(strong_tree:root(), strong_text, 0, -1) do
    iter_index = iter_index + 1
    local srow, scol = node:range()
    if srow == 0 and scol == 0 then
        local name = strong_query.captures[id]
        if name == "markup.strong" then
            strong_index = iter_index
        elseif name == "conceal" then
            conceal_index = iter_index
        end
    end
end
local conceal_after_strong = 0
if strong_index and conceal_index and conceal_index > strong_index then
    conceal_after_strong = 1
end
print("CONCEAL_AFTER_STRONG=" .. conceal_after_strong)

-- ここから適用側の観測。config.appearance は require した時点で apply() を 1 回走らせ、
-- ColorScheme autocmd を登録する。
require("config.appearance")

local function highlight(name)
    return vim.api.nvim_get_hl(0, { name = name, link = false })
end

print("NORMAL_BG=" .. tostring(highlight("Normal").bg))
print("H1_FG=" .. tostring(highlight("@markup.heading.1").fg))

-- 汎用キャプチャ名がグローバルへ muted を漏らしていないことを保証する。
-- markdown.lua は @<capture>.<lang> でスコープするので、他言語が共有する素の @<capture> は
-- muted を帯びてはならない。色は palette から直接取る
local MUTED_FG = tonumber(palette.hex.muted:sub(2), 16)
local bleed = 0
for _, name in ipairs({ "@punctuation.special", "@conceal", "@label", "@markup.link" }) do
    if highlight(name).fg == MUTED_FG then
        bleed = 1
    end
end
print("GLOBAL_BLEED=" .. bleed)

-- highlighter (runtime/lua/vim/treesitter/highlighter.lua) が実際に使う解決経路。
-- キャプチャ名と言語から '@<capture>.<lang>' を組み立てて引く。
-- 定義が無ければ素の '@<capture>' へフォールバックする
local function resolved_fg(capture, lang)
    local id = vim.api.nvim_get_hl_id_by_name("@" .. capture .. "." .. lang)
    return vim.api.nvim_get_hl(0, { id = id, link = false }).fg
end

-- リンクの記号は markdown_inline でだけ muted になり、他言語へは漏れない
print("LINK_SCOPED_IN_MARKDOWN=" .. ((resolved_fg("markup.link", "markdown_inline") == MUTED_FG) and 1 or 0))
print("LINK_NO_BLEED_TO_LUA=" .. ((resolved_fg("markup.link", "lua") ~= MUTED_FG) and 1 or 0))

-- 見出しマーカーには色を定義しない。@markup.heading.N.marker という名前が
-- @ 名前空間の階層フォールバックで @markup.heading.N へ落ちるため、見出しと同色になる。
-- この検査は名前解決だけで成立するのでクエリの有無には依存しない。
-- 守っているのは、誰かがマーカーへ色を明示定義して継承を壊すことである
local marker_inherits = 1
for level = 1, 6 do
    local want = tonumber(palette.hex["heading_" .. level]:sub(2), 16)
    if resolved_fg("markup.heading." .. level .. ".marker", "markdown") ~= want then
        marker_inherits = 0
    end
end
print("MARKER_INHERITS_HEADING=" .. marker_inherits)

-- 逆に、スコープした markdown 用グループには MUTED が実際に乗っていること。
-- 漏れを止めた結果 markdown 側まで無色になっていないかを確かめる。
local scoped_applied = 1
for _, name in ipairs({
    "@punctuation.special.markdown",
    "@conceal.markdown_inline",
    "@label.markdown",
    "@markup.link.markdown_inline",
}) do
    if highlight(name).fg ~= MUTED_FG then
        scoped_applied = 0
    end
end
print("SCOPED_MUTED_APPLIED=" .. scoped_applied)

-- ---------------------------------------------------------------------------
-- ファイラの配色
--
-- NeoTree のグループ名は tree-sitter のキャプチャではないため、綴りを間違えても
-- Neovim は黙って無視する。ここではグループ名を出力し、実在の検査は bats が
-- neo-tree のソースに対して行う。
-- ---------------------------------------------------------------------------

local neotree = require("config.neotree")

local neotree_groups = {}
for name in pairs(neotree) do
    neotree_groups[#neotree_groups + 1] = name
end
table.sort(neotree_groups)
print("NEOTREE_GROUPS=" .. table.concat(neotree_groups, ","))
print("NEOTREE_GROUP_COUNT=" .. #neotree_groups)

-- 定義した色が実際に適用されていること。
-- link を張られている既定グループを上書きできているかもここで分かる。
-- fg を持たない group を skip すると、色が黙って消えても NEOTREE_APPLIED=1 のまま通る。
-- 現状すべての neotree group は fg を持つので、skip せず fg 前提で回して失敗させる
local neotree_applied = 1
for group, opts in pairs(neotree) do
    local want = tonumber(opts.fg:sub(2), 16)
    if highlight(group).fg ~= want then
        neotree_applied = 0
    end
end
print("NEOTREE_APPLIED=" .. neotree_applied)

-- 未知のトークン名を palette.hex から引くと error になること。
-- トークンを改名すると palette.hex.<旧名> が nil を返し、nvim_set_hl はそれを
-- fg 未指定と解釈して既定色へ黙って戻してしまう。palette.hex に __index ガードを
-- 掛けて nil ではなく error にすることで、改名が全テスト緑のまま色を消す事故を塞ぐ。
-- ここが 0 になったらガードが外れており、silent nil default への回帰を検出できない
local hex_guard_ok = pcall(function()
    return palette.hex.this_token_does_not_exist
end)
print("HEX_UNKNOWN_KEY_ERRORS=" .. (hex_guard_ok and 0 or 1))

-- palette.surfaces も同じガードを持つこと。lualine は surfaces.<面名> を直接引くので、
-- 面を改名すると nil を index して起動時に汚く落ちる。hex と同じ __index で名前付き error にし、
-- 半分だけ守られた状態 (hex だけガード) を残さない
local surfaces_guard_ok = pcall(function()
    return palette.surfaces.this_surface_does_not_exist
end)
print("SURFACES_UNKNOWN_KEY_ERRORS=" .. (surfaces_guard_ok and 0 or 1))

-- 色だけに頼らない情報伝達 (グローバル CLAUDE.md の MUST) を固定する。
-- 適用結果 (highlight) から直接読むので、写像の bold / italic 宣言を消しても
-- 検査が空回りして緑になることはない。fg 比較だけを見る NEOTREE_APPLIED では守れない不変条件。
-- 検査対象が 0 件だと空回りするので件数も出す
local attribute_violations = {}
local attribute_checks = 0

-- 見出しは色相だけでなく bold でも本文と区別する。全 6 レベルが bold であること
for level = 1, 6 do
    attribute_checks = attribute_checks + 1
    if highlight("@markup.heading." .. level).bold ~= true then
        attribute_violations[#attribute_violations + 1] = "heading_" .. level .. ":not-bold"
    end
end

-- git の未追跡と衝突はファイル名に同一の色 (git_attention) が乗る。
-- bold の有無だけが両者を分けるので、その区別が生きていること。
-- 色を読んで同一であることも確かめる (bold が真の区別子であることを保証する)
local untracked = highlight("NeoTreeGitUntracked")
local conflict = highlight("NeoTreeGitConflict")
attribute_checks = attribute_checks + 1
if untracked.fg ~= conflict.fg then
    attribute_violations[#attribute_violations + 1] = "git_states:fg-not-shared"
end
attribute_checks = attribute_checks + 1
if conflict.bold ~= true then
    attribute_violations[#attribute_violations + 1] = "git_conflict:not-bold"
end
attribute_checks = attribute_checks + 1
if untracked.bold == true then
    attribute_violations[#attribute_violations + 1] = "git_untracked:unexpected-bold"
end

table.sort(attribute_violations)
print("ATTRIBUTE_CHECK_COUNT=" .. attribute_checks)
print("ATTRIBUTE_VIOLATIONS=" .. table.concat(attribute_violations, ","))
print("ATTRIBUTE_VIOLATION_COUNT=" .. #attribute_violations)

-- colorscheme の読み込みは hi clear を伴うため、autocmd が無いと定義が消える
vim.cmd("colorscheme habamax")
print("AFTER_CS_NORMAL_BG=" .. tostring(highlight("Normal").bg))
print("AFTER_CS_H1_FG=" .. tostring(highlight("@markup.heading.1").fg))

-- ---------------------------------------------------------------------------
-- パレットのコントラスト検査
--
-- 基準背景と tier ごとの目標値は config.palette が単一の真実として持つ。
-- ここでは WCAG 2.x の相対輝度を計算するだけで、期待値は持たない。
-- ---------------------------------------------------------------------------

-- sRGB のガンマを解いて線形化する
local function linearize(byte)
    local c = byte / 255
    if c <= 0.03928 then
        return c / 12.92
    end
    return ((c + 0.055) / 1.055) ^ 2.4
end

local function relative_luminance(hex)
    local r = linearize(tonumber(hex:sub(2, 3), 16))
    local g = linearize(tonumber(hex:sub(4, 5), 16))
    local b = linearize(tonumber(hex:sub(6, 7), 16))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
end

local function contrast_ratio(fg, bg)
    local lf, lb = relative_luminance(fg), relative_luminance(bg)
    local hi, lo = math.max(lf, lb), math.min(lf, lb)
    return (hi + 0.05) / (lo + 0.05)
end

-- 検査ロジック自体の較正。白と黒は 21:1、同色どうしは 1:1 になる。
-- ここが崩れていたら以降の判定は全て無意味なので先に固定する。
-- 同色の検査には基準背景を使う。値を書き写すと palette と drift する
print(string.format("CONTRAST_SELFTEST_MAX=%.2f", contrast_ratio("#ffffff", "#000000")))
print(string.format(
    "CONTRAST_SELFTEST_MIN=%.2f",
    contrast_ratio(palette.reference_background, palette.reference_background)
))

local violations = {}
for token, spec in pairs(palette.colors) do
    local target = palette.minimum_contrast[spec.tier]
    if target == nil then
        violations[#violations + 1] = token .. ":unknown-tier"
    else
        local ratio = contrast_ratio(spec.hex, palette.reference_background)
        if ratio < target then
            violations[#violations + 1] = string.format("%s:%.2f<%.2f", token, ratio, target)
        end
    end
end
table.sort(violations)
print("PALETTE_VIOLATIONS=" .. table.concat(violations, ","))
print("PALETTE_VIOLATION_COUNT=" .. #violations)

-- 検出器が働いていることを示す negative case。
-- 旧 MUTED (#5c6370) は基準背景の上で背景とほぼ同色になり symbol tier に届かない。
-- ここが 0 になったらコントラスト検査は何も守っていない
local sentinel_ratio = contrast_ratio("#5c6370", palette.reference_background)
print("VIOLATION_DETECTOR_WORKS=" .. ((sentinel_ratio < palette.minimum_contrast.symbol) and 1 or 0))
print(string.format("SENTINEL_RATIO=%.2f", sentinel_ratio))

-- ---------------------------------------------------------------------------
-- パレットの区別可能性の検査
--
-- コントラスト検査は各色が tier の下限を超えるかしか見ない。
-- 下限に張り付いた色どうしが同化しても検出できないため、色差を別に測る。
--
-- OKLab は知覚的におおむね均等な色空間で、L は 0 から 1 に収まる。
-- 2 色のユークリッド距離が知覚閾値 (JND) を下回ると人間には同じ色に見える。
--
-- 意図的に同色のトークンは palette の中で同じリテラルを共有する。
-- したがって相異なる hex どうしだけを比べれば、区別すべき色だけが対象になる。
--
-- linearize は WCAG の閾値 0.03928 を使う。sRGB 規格は 0.04045 だが、
-- 8bit 入力では 10/255 = 0.0392 が両方を下回り 11/255 = 0.0431 が両方を上回るため、
-- 0 から 255 のどの値でも分岐は変わらない。よってここで使い回せる。
-- ---------------------------------------------------------------------------

local function to_oklab(hex)
    local r = linearize(tonumber(hex:sub(2, 3), 16))
    local g = linearize(tonumber(hex:sub(4, 5), 16))
    local b = linearize(tonumber(hex:sub(6, 7), 16))

    local l = 0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b
    local m = 0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b
    local s = 0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b

    local l_, m_, s_ = l ^ (1 / 3), m ^ (1 / 3), s ^ (1 / 3)

    return 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_,
        1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_,
        0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_
end

local function delta_e(hex_a, hex_b)
    local la, aa, ba = to_oklab(hex_a)
    local lb, ab, bb = to_oklab(hex_b)
    return math.sqrt((la - lb) ^ 2 + (aa - ab) ^ 2 + (ba - bb) ^ 2)
end

-- 検査ロジック自体の較正。OKLab の L は 0 から 1 なので白と黒はちょうど 1.0、
-- 同色どうしは 0.0 になる。ここが崩れたら以降の判定は全て無意味なので先に固定する
print(string.format("DELTA_E_SELFTEST_MAX=%.4f", delta_e("#ffffff", "#000000")))
print(string.format(
    "DELTA_E_SELFTEST_MIN=%.4f",
    delta_e(palette.reference_background, palette.reference_background)
))

-- 有彩ペアの known-answer。to_oklab の立方根指数 (1/3) を pin する。
-- 白黒較正は cube-root を固定点 1 と 0 でしか通さず、同色較正は 0 なので、
-- どちらも指数を 1/2 や 1.0 へ変えても値が動かない。有彩ペアだけが OKLab の非線形性を通す。
-- 期待値は Ottosson の OKLab 原典から Python で独立に導出したもので、この probe の出力から作らない。
-- 桁数は期待値に合わせて %.6f にする (小数第 4 位までだと mutation の差が丸めで潰れる余地を残す)
print(string.format("DELTA_E_KNOWN_CHROMATIC=%.6f", delta_e("#a8b6e7", "#aab6e4")))

-- 相異なる hex ごとに代表トークンを 1 つ選ぶ。辞書順で最小を取れば出力が安定する
local representative = {}
for token, spec in pairs(palette.colors) do
    if representative[spec.hex] == nil or token < representative[spec.hex] then
        representative[spec.hex] = token
    end
end

local distinct = {}
for hex in pairs(representative) do
    distinct[#distinct + 1] = hex
end
table.sort(distinct)
print("PALETTE_DISTINCT_HEX_COUNT=" .. #distinct)
print("PALETTE_JND_PAIR_COUNT=" .. (#distinct * (#distinct - 1) / 2))

local jnd_violations = {}
for i = 1, #distinct do
    for j = i + 1, #distinct do
        local distance = delta_e(distinct[i], distinct[j])
        if distance < palette.minimum_delta_e then
            jnd_violations[#jnd_violations + 1] = string.format(
                "%s|%s:%.4f",
                representative[distinct[i]],
                representative[distinct[j]],
                distance
            )
        end
    end
end
table.sort(jnd_violations)
print("PALETTE_JND_VIOLATIONS=" .. table.concat(jnd_violations, ","))
print("PALETTE_JND_VIOLATION_COUNT=" .. #jnd_violations)

-- 検出器が働いていることを示す negative case。
-- 旧 RECEDED (#aab6e4) は dotfile (#a8b6e7) と色差 0.0049 で同化していた。
-- ここが 0 になったら区別可能性の検査は何も守っていない
print("JND_DETECTOR_WORKS=" .. ((delta_e("#a8b6e7", "#aab6e4") < palette.minimum_delta_e) and 1 or 0))

-- ---------------------------------------------------------------------------
-- 見出しの色相分離の検査
--
-- 階層を色相で分ける以上、見出しどうしの色相が十分に離れている必要がある。
-- JND (色差) は色相が近くても輝度や彩度が違えば通してしまうため、色相を別の不変条件として測る。
-- OKLCh の色相は atan2(b, a) を度に直して 360 で正規化し、分離度は円環距離 min(d, 360-d) で測る。
-- 閾値は palette が minimum_heading_hue_separation として単一の真実で持つ。
-- ---------------------------------------------------------------------------

local function oklch_hue(hex)
    local _, a, b = to_oklab(hex)
    local deg = math.deg(math.atan2(b, a))
    if deg < 0 then
        deg = deg + 360
    end
    return deg
end

local function hue_separation(hex_a, hex_b)
    local d = math.abs(oklch_hue(hex_a) - oklch_hue(hex_b))
    return math.min(d, 360 - d)
end

local heading_hexes = {}
for level = 1, 6 do
    heading_hexes[level] = palette.hex["heading_" .. level]
end

local hue_violations = {}
local hue_pair_count = 0
local min_hue_separation = nil
for i = 1, #heading_hexes do
    for j = i + 1, #heading_hexes do
        hue_pair_count = hue_pair_count + 1
        local separation = hue_separation(heading_hexes[i], heading_hexes[j])
        if min_hue_separation == nil or separation < min_hue_separation then
            min_hue_separation = separation
        end
        if separation < palette.minimum_heading_hue_separation then
            hue_violations[#hue_violations + 1] =
                string.format("heading_%d|heading_%d:%.4f", i, j, separation)
        end
    end
end
table.sort(hue_violations)
print("HEADING_HUE_PAIR_COUNT=" .. hue_pair_count)
print("HEADING_HUE_VIOLATIONS=" .. table.concat(hue_violations, ","))
print("HEADING_HUE_VIOLATION_COUNT=" .. #hue_violations)
print(string.format("HEADING_MIN_HUE_SEPARATION=%.4f", min_hue_separation))

-- 検出器が働いていることを示す negative case。
-- 旧 H1 #7fdfd0 と旧 H6 #7fd4dd は色相差 21.58 度で閾値を割るが、OKLab 色差は 0.0407 で JND を超える。
-- つまり JND では守れず色相検査でしか捕まらない実在ペア。
-- HUE_DETECTOR_WORKS が 0 なら色相検査は何も守っておらず、
-- PASSES_JND が 0 なら JND で代替できてしまいこの検査の存在理由が消える
local sentinel_hue = hue_separation("#7fdfd0", "#7fd4dd")
local sentinel_de = delta_e("#7fdfd0", "#7fd4dd")
print(string.format("SENTINEL_HUE_SEPARATION=%.4f", sentinel_hue))
print("HUE_DETECTOR_WORKS=" .. ((sentinel_hue < palette.minimum_heading_hue_separation) and 1 or 0))
print(string.format("SENTINEL_HUE_DELTA_E=%.6f", sentinel_de))
print("SENTINEL_HUE_PAIR_PASSES_JND=" .. ((sentinel_de >= palette.minimum_delta_e) and 1 or 0))

-- ---------------------------------------------------------------------------
-- 不透明な面の配色の検査
--
-- ステータスラインのように自前の背景色を持つ面は、透過したターミナル背景の上には無い。
-- Ghostty の background-opacity はウィンドウ背景にだけ掛かり、
-- 明示的な背景色を持つセルは不透明に描かれる (background-opacity-cells が既定の false のとき)。
-- したがって前景色は reference_background ではなく自前の bg に対して評価する。
-- ---------------------------------------------------------------------------

local surface_violations = {}
local surface_count = 0
for name, surface in pairs(palette.surfaces) do
    surface_count = surface_count + 1
    local ratio = contrast_ratio(surface.fg, surface.bg)
    if ratio < palette.surface_minimum_contrast then
        surface_violations[#surface_violations + 1] = string.format(
            "%s:%.2f<%.2f",
            name,
            ratio,
            palette.surface_minimum_contrast
        )
    end
end
table.sort(surface_violations)
print("SURFACE_COUNT=" .. surface_count)
print("SURFACE_VIOLATIONS=" .. table.concat(surface_violations, ","))
print("SURFACE_VIOLATION_COUNT=" .. #surface_violations)

-- lualine の spec の入れ子から指定キーを再帰的に探す。
-- 添字を決め打ちにすると spec の並べ替えで壊れるため、キー名で辿る。
--
-- 前提: spec は循環参照の無い有限の木であり buffers_color は 1 箇所にしか現れない。
--       循環があればスタックオーバーフローで落ちるが、それは検査が壊れたことを示す赤である。
--       この前提が崩れる spec を書いたら、ここに visited 集合を足す
local function find_key(node, key)
    if type(node) ~= "table" then
        return nil
    end
    if node[key] ~= nil then
        return node[key]
    end
    for _, child in pairs(node) do
        local found = find_key(child, key)
        if found ~= nil then
            return found
        end
    end
    return nil
end

-- lualine が palette と同じ値を使っていること (drift ガード)。
-- palette を参照していること自体は ast-grep の nvim-lua-no-hex-literal が構文レベルで保証する。
-- ここは値の一致だけを見る
local buffers_color = find_key(require("plugins.lualine"), "buffers_color")
local lualine_matches = 0
if buffers_color ~= nil then
    local active = palette.surfaces.statusline_buffer_active
    local inactive = palette.surfaces.statusline_buffer_inactive
    if
        buffers_color.active.fg == active.fg
        and buffers_color.active.bg == active.bg
        and buffers_color.inactive.fg == inactive.fg
        and buffers_color.inactive.bg == inactive.bg
    then
        lualine_matches = 1
    end
end
print("LUALINE_MATCHES_PALETTE=" .. lualine_matches)
