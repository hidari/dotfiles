---
status: closed
---

# refactor: herdr ターミナル版から herdr-app へ移行し nvim を撤去する

## 背景

ターミナル内で動く herdr (TUI、`~/.config/herdr/config.toml`) から、独立した GUI アプリの herdr-app (`~/.config/herdr-app/`) へ乗り換えた。キーと設定は 2026-10-30 に live の `~/.config/herdr-app/` へ移してある。dotfiles には旧 herdr の設定・検査・hook・チートシートが残り、旧本体が無い環境では何もしないまま追跡下に居座っている。

同時に nvim も使わなくなったので撤去し、依存ツールを減らす。

### 確かめた事実 (2026-10-30)

- herdr-app の端末には `HERDR_*` の環境変数が無く、`HC_*` だけがある。旧 herdr の integration hook (`herdr-agent-state.sh`) と `guard_probes.py` の `herdr-ids` プローブは、herdr-app の中では何もしない
- herdr-app は hook 無しで Claude Code を agent (`claude-code`、`working`) として表示した
- keys.json の ctrl+英字の prefix (`"ctrl-b h"` のシーケンスも、`ctrl-b` 単体を global / terminal に置く形も) は parse を通るが、押しても発火しなかった (ユーザーが確認)
- keys.json の存在しないアクション名は `keys.error` にも `herdr-app status` にも出ない
- mod はフォルダ外のモジュールを import できない。ファイル単位の symlink (`mods/<name>/main.js` → リポジトリ) にすると `./helper.js` の import が「application directory の外」として拒否された。mod フォルダごとの symlink なら `herdr-app check` が通った
- フォルダごとの symlink では、herdr-app が `gpui-kit.d.ts` と `jsconfig.json` を symlink の先 (リポジトリ側) に書き込む
- herdr-app は settings.json を書くたびに inode を替える (atomic rename)。symlink にするとアプリの書き込みで実ファイルに置き換わる
- herdr-app (`/Applications/Herdr.app`) は Homebrew の cask に無い (`brew info --cask herdr` は unavailable)。Homebrew の `herdr` formula は旧 TUI 本体

## 決めたこと (2026-10-30、ユーザー裁定)

- 運用は ⌘ 起点にする。prefix 方式は採らない
- チートシートは herdr-app の app.help (⌘/) に任せて撤去する。app.help は keys.json を直接読むので drift しない
- herdr-app の settings.json は dotfiles で管理しない。管理するのは keys.json と自作の mod (`unread` / `pane-next` / `pane-prev`) だけ
- 旧 herdr 本体 (サーバの停止と `brew uninstall herdr`) はユーザーが行う。dotfiles 側は参照の整理だけ
- nvim はアンインストールする。snacks.lua の herdr 判定は nvim ごと消える

## タスク

### PR 1: herdr

- [x] 旧 herdr の設定・スクリプト・チートシート (`home/.config/herdr/`、raycast の `herdr-cheatsheet.sh`) を撤去する
- [x] herdr-app の keys.json と自作の mod 3 つを追跡下へ入れ、bootstrap の SYMLINK_PAIRS で配る (mod はフォルダ単位)。アプリが書き込む `gpui-kit.d.ts` と `jsconfig.json` を ignore する
- [x] `pane-next` と `pane-prev` が持つ同じ `cycle.js` が食い違わないことをテストで pin する
- [x] config-guard の `herdr_keys` を herdr-app の keys.json の検査に置き換える (JSON のキーの重複、アクションが組み込みコマンドに解決するか、`mod.open:` の宛先の mod が在るか)
- [x] 旧 herdr の integration hook と `herdr-ids` プローブを撤去する
- [x] `.zshrc` の `herdr-reload` を撤去する
- [x] 旧 herdr の機構を記述しているメモリを訂正する

### PR 2: nvim

- [x] nvim の設定、チートシート、CI の取得手順、検査とテスト (`nvim-markdown.bats`、ast-grep の `nvim-lua-no-hex-literal`) を撤去する
- [x] マージ後に live の `~/.config/nvim` の symlink を外し、`brew uninstall neovim` と依存の掃除を行う (残すデータはユーザーに確認する)

## 未決 (ISSUE-95 へ移した)

- ISSUE-95 は「設定を配る 4 件 (herdr / neovim / ghostty / raycast) を Brewfile に宣言する」と決めている。この Issue で herdr と neovim は消えたが、herdr-app は cask が無いので、設定を配るのに本体を Brewfile で入れられない。この Issue を閉じると見張りが無くなるので、2026-10-30 に ISSUE-95 の「2026-10-30 の変化」へ移した

## 結果 (2026-10-30)

- PR 1 (PR #289) で旧 herdr を撤去し、herdr-app の keys.json と mod を配り始めた。置き換えた config-guard の検査は、旧検査が持っていた前後の向きの整合も引き継いでいる
- PR 2 で nvim を撤去した。ast-grep の `--no-ignore hidden` は、隠しディレクトリ配下の対象が今は無いが残した。外すと、隠しディレクトリへルールの対象を足したときに 1 件も見ないまま緑になるため (`scripts/tests/ast-grep.bats` が残るルールで pin する)
- bootstrap の `prune_stale_symlinks` は、nvim の対応を外すと `~/.config` 直下を見なくなった (走査先が「今の対応の行き先の親」だけで、`~/.config` 直下を行き先にしていたのが nvim の 1 本だった)。ユーザー裁定で、親に加えて祖先を `$HOME` まで見る形にした
- ホスト側 (2026-10-30、ユーザーの裁定どおり): `~/.config/nvim` の symlink を外し、Homebrew の neovim とその依存、tree-sitter と tree-sitter-cli を uninstall した。luajit (wrk が使う) と lua (wireshark が使う) は残る。`~/.local/share/nvim` / `~/.local/state/nvim` / `~/.cache/nvim` を消した
- 旧 herdr 本体 (Homebrew の herdr と `~/.config/herdr/`) の停止と削除はユーザーが行う

## 関連

- ISSUE-95: 設定を配るツールを Brewfile に宣言する裁定を持つ。この Issue で対象の 4 件のうち herdr と neovim が消え、herdr-app が増える
- ISSUE-83: セッション頭のプローブの待ち時間を扱う。この Issue で `herdr-ids` プローブが消える
