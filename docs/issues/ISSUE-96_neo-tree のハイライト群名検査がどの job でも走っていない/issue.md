---
status: open
---

# test: neo-tree のハイライト群名検査がどの job でも走っていない

## 背景

`scripts/tests/nvim-markdown.bats` の「neo-tree highlight group names exist in the plugin
source」は、neo-tree プラグインの実ソース
(`$HOME/.local/share/nvim/lazy/neo-tree.nvim/lua/neo-tree/ui/highlights.lua`) を読んで、
配色側が指定する群名がプラグインに実在することを確かめる。群名は treesitter のキャプチャでは
ないので、綴りを間違えても Neovim は黙って無視する。この検査だけがそれを捕まえる。

CI の bats job は `nvim` を入れるがプラグインは入れない。`nvim --clean` は user config を
読まず lazy.nvim を起動しないので、clone も起きない。したがってこの 1 本は **どの job でも
実行されていない**。

ISSUE-45 でこの skip を `skip_uncovered neo-tree` として宣言に載せた。宣言によって
「見えない skip」は「見える skip」になり、CI の緑が空虚でないことは示せるようになったが、
**カバレッジそのものは無いまま**である。宣言は現状の記述であって解決ではない。

同じ `skip_uncovered` に載る osacompile とは性質が違う。osacompile は macOS 専用で
Linux ランナーに原理的に無く、ローカル macOS では実行されるのでカバレッジは失われていない。
neo-tree はローカルでしか走らず、ローカルで走ることを保証する層も無い。

## タスク

- [ ] neo-tree を CI へ導入するコストを見積もる (プラグインの取得方法、キャッシュ、
      lazy.nvim を起動せずにソースだけ取る経路があるか)
- [ ] 群名の canonical をプラグインのソース以外から取れないか調べる (取れるなら
      この検査は外部依存を持たなくなる)
- [ ] 導入する / 別経路で検査する / 検査を落とす のいずれかを決めて適用する
- [ ] 決めた結果を `UNCOVERED_DEPENDENCIES` の宣言へ反映する (カバーできたら宣言を外す。
      外し忘れは `scripts/ci/assert-declared-skips.sh` が dead な宣言として落とす)

## 関連

- ISSUE-45 (この Issue の切り出し元。あちらは skip の宣言化までを扱い、
  neo-tree のカバレッジ不在はこちらへ残した)
