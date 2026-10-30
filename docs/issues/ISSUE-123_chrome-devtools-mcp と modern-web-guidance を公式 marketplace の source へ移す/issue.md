---
status: open
---

# config: chrome-devtools-mcp と modern-web-guidance を公式 marketplace の source へ移す

## 背景

`home/.claude/settings.json` は chrome-devtools-mcp を `chrome-devtools-plugins`、modern-web-guidance を `googlechrome` という第三者の marketplace から入れていて、どちらも `extraKnownMarketplaces` に宣言している。config-guard の `settings_invariants` も、この2つを公開の marketplace として許可リストに持つ。

公式の `claude-plugins-official` の catalog には、今は両方が載っている (どちらも url と sha を持つ source)。

2つの設定ディレクトリで、同じ settings.json から入れた plugin の版が食い違っている (2026-10-19に確認)。

- chrome-devtools-mcp: 1.4.0 と 1.8.0
- modern-web-guidance: 0.0.189 と 0.0.178

第三者の marketplace はどちらも `autoUpdate` を持たず、最終更新は設定ディレクトリごとにばらばらだった。chrome-devtools-mcp は MCP サーバーを起動する plugin なので、版の食い違いは2つのアカウントで別の版のサーバーが動いていることを意味する。

棚卸しでは、版の食い違いを告げるプローブを足す案も出たが、コードと drift する面が増えるので採らない。公式の source へ寄せれば、両方の設定ディレクトリが同じ更新の流れに乗り、宣言と許可リストの項目がそれぞれ2つ減る。

### 受け箱から届いた使い方の報告 (2026-10-31の仕分け)

別のリポジトリのセッションの報告で、dotfiles では確かめていない。導入元を移しても変わらない使い方の面にあたる。

- modern-web-guidance は、npx の代わりに `pnpm dlx modern-web-guidance@latest search|retrieve` で動いた。retrieve の出力はファイルへ出して grep すると要る行だけ読める。ブラウザ対応の欄に食い違って見える記述があるので、対応の判断は複数のガイドを突き合わせてから行う (実測)
- chrome-devtools MCP の `take_screenshot` は、`filePath` にセッションの scratchpad を渡すと workspace roots の外として拒まれた。保存せずに受け取るか、リポジトリの中の置き場を渡す (実測)

## タスク

- [ ] 公式 marketplace の更新の流れ (自動更新の有無と、sha の pin がいつ動くか) を確かめる。自動で上がるなら、MCP サーバーの版が黙って変わることを受け入れるかを決める (Hidari の判断)
- [ ] 公式の source の中身が、今の第三者の marketplace の plugin と同じもの (同じ上流リポジトリと skill の集合) かを確かめる
- [ ] `enabledPlugins` を公式の名前へ移し、`extraKnownMarketplaces` の2項目と config-guard の許可リストの2項目を外す
- [ ] 両方の設定ディレクトリで旧 marketplace の plugin を外して入れ直し、版が揃ったことを確かめる

## 関連

- ISSUE-101: pin が上流の最新から遅れたことを告げる。apm の pin を扱い、plugin の marketplace は射程の外
- ISSUE-53: 配布先の写しの drift
