# Neovim の Markdown シンタックスハイライト強化

作成: 2026-07-09 / 対象: `home/.config/nvim`

## 背景

Markdown を編集するとき、見出しの階層が視覚的に区別できない。原因を実測で特定した。

```
@markup.heading.1.markdown   bold=true fg=14738154
@markup.heading.2.markdown   bold=true fg=14738154   (H1 と同一)
```

treesitter のハイライト自体は動作しており、コードブロックの言語注入も効いている。欠けているのは配色である。この設定は colorscheme プラグインを使っておらず (`vim.g.colors_name` は `nil`)、Neovim 組み込みの既定配色が H1 から H6 まで同じ色を割り当てている。

## 目的

VSCode のように、Markdown の各要素を色で描き分ける。マークアップ記号は隠さず、暗い色で視覚的に後退させる。

## 決定事項

| 決定 | 理由 |
| --- | --- |
| conceal を使わない | 記号が編集中に伸び縮みするのを避けたい。記号を暗くすれば conceal に近い可読性が得られる |
| 行全体の背景を敷かない | `appearance.lua` が `Normal` に `bg = "NONE"` を設定して端末背景を透過させている。行全体背景はその行だけ不透明な帯になり、意匠と衝突する |
| プラグインを追加しない | 必要なのは配色のみで、`nvim_set_hl` と treesitter クエリ拡張で完結する |
| 見出しマーカーを暗くする | `#` を独立して色付けするため `after/queries` でクエリを拡張する |
| `ColorScheme` autocmd を導入する | `colorscheme` を読むと `nvim_set_hl` の定義が消える。既存の透過設定も同じ脆さを持つ |
| headless nvim で bats テストを書く | 存在しないハイライトグループへの色定義を Neovim は黙って無視するため、静的検査が要る |

### 検討して却下した案

`markview.nvim` は preview 有効時に `vim.wo[win].conceallevel = 3` を強制設定するため、conceal なしで運用する正規の方法がない。

`render-markdown.nvim` は要件を満たせるが、見出しアイコンの既定 `heading.position = 'overlay'` が conceal ではなく extmark overlay で `#` を覆うため `heading.icons` を空にする必要がある。加えて背景だけを使うには `bullet` / `checkbox` / `pipe_table` / `link` / `quote` / `dash` / `sign` を全て無効化することになる。日本語のテーブルで列がズレる既知 issue (#575) もある。依存を 1 つ増やして得るものが小さい。

`headlines.nvim` は要件に最も近い実装 (conceal 不使用、`hl_eol = true` による行全体背景) だが、最終コミットが 2024-09-13 で約 22 か月前のメンテナンスモードにあり、作者自身が README で `render-markdown.nvim` を後継として推奨している。

いずれも行全体背景を前提にした比較であり、その要件を落とした時点で採用理由が消えた。

## スコープ外

- プレビュー用の別窓 (ブラウザ / ターミナル内 / Quick Look)
- 行全体の背景 (extmark の `hl_eol` / `line_hl_group`)
- 表の罫線整形とチェックボックスの記号化
- colorscheme プラグインの導入

いずれも本設計の上に後から積める。特に行全体背景は `markdown.lua` を触らずに追加できる。

## アーキテクチャ

3 つのファイルで構成する。

`home/.config/nvim/lua/config/markdown.lua` (新規) は Markdown 配色の単一の責務を持つ。副作用を持たず、ハイライトグループ名から `nvim_set_hl` の引数テーブルへの写像を返すだけにする。純粋なテーブルなので、ハイライタを起動せずに内容を検証できる。

`home/.config/nvim/after/queries/markdown/highlights.scm` (新規) は `;; extends` で既定クエリに追記し、`atx_h1_marker` から `atx_h6_marker` を `@markup.heading.marker` として捕捉する。これが無いと `#` を見出し本体と別の色にできない。

`home/.config/nvim/lua/config/appearance.lua` (変更) が唯一の適用点になる。`apply()` が既存の定義 (`Normal` / `LineNr` / `CursorLineNr` / `NeoTree*`) と `markdown.lua` のテーブルをまとめて `nvim_set_hl` へ流す。`ColorScheme` autocmd から同じ `apply()` を呼ぶ。

## 構成要素

見出しは明度を上げて本文より目立たせ、階層は色相で分ける。マークアップ記号は本文より暗くする。

| グループ | 色 | 効果 | 対象 |
| --- | --- | --- | --- |
| `@markup.heading.1` | `#7fdfd0` | bold | H1 |
| `@markup.heading.2` | `#f0d399` | bold | H2 |
| `@markup.heading.3` | `#d8a0f0` | bold | H3 |
| `@markup.heading.4` | `#8ac6f7` | bold | H4 |
| `@markup.heading.5` | `#b5dd9b` | bold | H5 |
| `@markup.heading.6` | `#7fd4dd` | bold | H6 |
| `@markup.heading.marker` | `#5c6370` | | `#` から `######` (拡張クエリ由来) |
| `@punctuation.special` | `#5c6370` | | `>` `\|` `---` |
| `@markup.list` | `#56b6c2` | | `- ` `1. ` |
| `@markup.strong` | `#dcdfe4` | bold | `**bold**` |
| `@markup.italic` | | italic | `*italic*` |
| `@markup.strikethrough` | `#6f7aa5` | strikethrough | `~~strike~~` |
| `@markup.raw` | `#e06c75` | | インラインコード |
| `@markup.raw.block` | `#8f9dcc` | | フェンスと非注入ブロック |
| `@label` | `#5c6370` | | フェンスの言語名 |
| `@markup.quote` | `#98c379` | italic | `> 引用文` |
| `@markup.link.label` | `#61afef` | underline | `[リンク]` |
| `@markup.link.url` | `#5c6370` | underline | `(https://...)` |
| `@markup.list.checked` | `#98c379` | | `[x]` |
| `@markup.list.unchecked` | `#6f7aa5` | | `[ ]` |

色相は既存の `appearance.lua` が使う One Dark 系に揃えた (`#53c9b8` と `#e5c07b` の明度を上げたものが H1 と H2 になる)。

実装後は `markdown.lua` が配色の唯一の真実源になる。本表は初期提案であり、以後の微調整で本表を追随させない。

インラインコードに背景は付けない。透過が部分的に破れるため。

## データフロー

```
init.lua
  require("config.appearance")
    apply()                          起動時に 1 回
    autocmd ColorScheme -> apply()   colorscheme 読込のたび再適用

apply()
  既存の定義を nvim_set_hl
  require("config.markdown") のテーブルを反復して nvim_set_hl

ファイルを開く
  FileType markdown -> 既存の treesitter autocmd が vim.treesitter.start
    合成クエリ (nvim 同梱 + nvim-treesitter/site + after/extends)
      キャプチャ -> 定義済みハイライトが適用
```

拡張クエリのキャプチャは既定クエリより後に評価されるため、同じ範囲が重なったときに勝つ。実測で `@markup.heading.1` の後に `@markup.heading.marker` が生成されることを確認した。

## エラー処理

拡張クエリは grammar の node 名に依存する。パーサ更新で `atx_h1_marker` が消えると `vim.treesitter.query.get` が例外を投げ、Markdown のハイライトが丸ごと止まる。ここに `pcall` の防御は入れない。握り潰すと色が消えたまま誰も気づかないため、テストで検出する。

存在しないハイライトグループに色を定義しても Neovim はエラーを出さず黙って無視する。これが最も危険な失敗で、テストで検査する。

パーサ未導入の環境では既存の `FileType` autocmd が `pcall` で skip するため、色定義は無害に残る。

## テスト

`scripts/tests/nvim-markdown.bats` を追加する。既存の `scripts/tests/` は CI が `bats scripts/tests/` でディレクトリごと実行するため、追加するだけで CI に載る。

テストは `nvim --clean` に repo の nvim ディレクトリと `after/` を rtp として渡して起動する。`--clean` は user config を読まないので lazy.nvim が起動せず、プラグインの clone もパーサのビルドも起きない。markdown と markdown_inline のパーサは Neovim 本体に同梱されている。

| # | 検証内容 | これが守るもの |
| --- | --- | --- |
| 1 | `markdown.lua` の H1 から H6 の `fg` が 6 色すべて異なる | 階層が同色という元の不満の再発 |
| 2 | 定義した全グループ名が実クエリのキャプチャ集合に含まれる | 存在しないグループへの色定義 |
| 3 | 拡張クエリが `#` から `######` を捕捉する | grammar 更新によるクエリ破損 |
| 4 | 拡張クエリを rtp から外すと 2 と 3 が落ちる | テスト自体が常に緑にならないこと |
| 5 | `Normal` の `bg` が `nil` | 透過の破壊 |
| 6 | `colorscheme` 読込後も色と透過が復活する | `ColorScheme` autocmd の退行 |

4 番が肝になる。検査を追加しても、それが何も守っていなければ意味がない。拡張クエリを外した状態で確かに落ちることをテストとして固定する。

テスト 2 のキャプチャ集合は `markdown` と `markdown_inline` の両方のクエリの和集合をとる。配色表の `@markup.strong` `@markup.italic` `@markup.strikethrough` `@markup.raw` `@markup.link.label` `@markup.link.url` は `markdown_inline` 由来で、`markdown` のクエリだけを見ると存在しないグループと誤判定する。`@markup.heading.marker` は拡張クエリ由来で `markdown` 側に現れる。

## CI

`.github/actions/setup-neovim/action.yml` (新規) を `setup-bats` と同じ流儀で追加する。公式リリースの tarball をバージョン pin して展開し `GITHUB_PATH` へ追加する。`nvim-linux-x86_64.tar.gz` が v0.12.3 のアセットに存在することを確認済み。

pin するバージョンは開発機に合わせて v0.12.3 とする。最新安定版は v0.12.4 (2026-07-05) だが、開発機と CI がずれると再現性を失うため、上げるときは両方を意図的に上げる。pin する値の真実源は `action.yml` とし、本節の記述は執筆時点の記録として追随させない。

`test.yml` の `bats` ジョブに Neovim のセットアップ手順を足す。Neovim を入れるだけで済み、tree-sitter CLI も C コンパイラも不要なため CI コストの増分は小さい。

## 実測した事実

設計の前提はすべて手元で確認した。

| 事実 | 確認方法 |
| --- | --- |
| treesitter ハイライトは markdown で有効 | `vim.treesitter.highlighter.active[buf]` が真 |
| コードブロックの言語注入が動作 | 親パーサの子に `lua` が現れる |
| `#` は独立キャプチャを持たず見出し行全体に含まれる | `@markup.heading.1` の範囲が `"# H1\n"` |
| `@punctuation.special` は `>` `\|` `---` のみ | 各キャプチャの被覆文字を列挙 |
| `@conceal` は `*` `~` `` ` `` のみ (markdown_inline 由来) | 同上 |
| `atx_h1_marker` から `atx_h6_marker` が存在 | 見出しノードの子を走査 |
| `after/queries` の `;; extends` が機能する | `XDG_CONFIG_HOME` を差し替えて 4 件捕捉 |
| 拡張キャプチャは既定より後に評価される | `iter_captures` の生成順 |
| `colorscheme` 読込で `nvim_set_hl` の定義が消える | `Normal.bg` が `nil` から不透明へ変化 |
| markdown パーサは Neovim 本体に同梱 | `lib/nvim/parser/markdown.so` が `--clean` の rtp 配下に存在 |

lazy.nvim は起動時に runtimepath を再構築するため、`--cmd 'set rtp+=...'` で足したエントリは消える。テストで `--clean` を使う理由でもある。

## 実装時に確認する項目

`@conceal` を暗くすることで `**` `~~` `` ` `` が後退するかは未確認。`@markup.strong` が `**bold**` 全体を覆うため、`@conceal` が後勝ちするかどうかに依存する。headless では描画が走らず `vim.inspect_pos` が空を返すので、実端末で目視確認する。後勝ちしない場合は `@conceal` への色定義を落とす。

`termguicolors` の状態は headless では偽になるため未検証。Ghostty は truecolor を報告するので実運用では真になるはずだが、実端末で確認する。
