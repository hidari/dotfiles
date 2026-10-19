---
status: open
---

# config: rust-analyzer と swift の LSP plugin を測ってから有効にするか決める

## 背景

公式 marketplace の LSP plugin 5つは、PR #203 で UI からの変更を取り込む形で `enabledPlugins` から外れていた。外した理由は記録されていない。

2026-10-19の棚卸しで、言語サーバーの実体が無い pyright / typescript / kotlin の3つはアンインストールした (Hidari の判断)。残る rust-analyzer-lsp と swift-lsp は、実体 (`rust-analyzer` と `sourcekit-lsp`) が手元にあるので、有効に戻す候補になる。Hidari の判断で、測ってから決める。

- 2つともインストールされているのは `~/.claude` だけで、もう一方の設定ディレクトリには無い。`enabledPlugins` は共有の settings.json にあるので、有効にすると両方の設定ディレクトリに効く
- rust-analyzer は実リポジトリの索引でメモリを大きく使いうる。ホストを守る規範 (入力の大きさを先に確かめ、常駐メモリを見る) に従って測る
- 編集のたびに診断がコンテキストへ流れ込むので、トークンの費用も測る

## タスク

- [ ] 実際の Rust のリポジトリで rust-analyzer-lsp を有効にし、索引の間の常駐メモリと、編集ごとに入る診断の量を測る
- [ ] swift-lsp も同じく測る
- [ ] 測った結果から、それぞれ有効にするか、アンインストールするかを決める (Hidari の判断)
- [ ] 有効にするなら、もう一方の設定ディレクトリにも入れて揃える

## 関連

- PR #203: LSP plugin 5つを `enabledPlugins` から外した変更を取り込んだ
