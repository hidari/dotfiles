---
status: open
---

# chore: user スコープのブラウザ操作の plugin と MCP の役割を分けて重なりを減らす

## 背景

2026-11-11に仕分けた受け箱のまとめから起票した。ブラウザを操作する道具が、user スコープの plugin とプロジェクトの MCP で重なっていて、使う側が1つか2つにまとめたいという声が届いた。既存の Issue のうち、ISSUE-123 は chrome-devtools-mcp と modern-web-guidance の導入元の移行、ISSUE-122 は skill 一覧の予算超過を扱っていて、道具の役割を分けて数を減らす判断はどこにも無かった。

### 届いた報告 (2026-11-11の仕分け)

- Playwright 系の道具は、プロジェクトの MCP、user スコープの playwright plugin、ほかのブラウザの MCP と重なっていて、ユーザーから「1つか2つにまとめたい」という声が出た (実測)。報告者の提案は、Playwright 系の MCP と plugin の役割を整理し、E2E 用 (プロジェクトの Test Agents の MCP) と汎用のブラウザ操作に分けて、user スコープの重複を減らすこと (推測)。dotfiles で確かめたこと (2026-11-11): `home/.claude/settings.json` の enabledPlugins は、ブラウザを操作するものとして chrome-devtools-mcp・playwright・superpowers-chrome の3つを有効にしている

## タスク

- [ ] user スコープで有効にしているブラウザ操作の道具 (plugin と、組み込みの claude-in-chrome) を棚卸しし、それぞれの役割 (E2E の生成、汎用のブラウザ操作、DevTools での計測) を書き出す
- [ ] プロジェクトの Playwright Test Agents の MCP と役割が重なるものを決め、user スコープから外すものをユーザーと決める
- [ ] 外すと決めたものを `home/.claude/settings.json` から外し、それを前提にした記述 (references と skill) が残っていないかを確かめる

## 関連

- ISSUE-123 — chrome-devtools-mcp と modern-web-guidance の導入元を公式 marketplace へ移す。外すものが決まると移す対象も変わる
- ISSUE-122 — skill 一覧の予算超過。plugin を外すと一覧の skill も減る
- ISSUE-134 — 「Playwright Test Agents とブラウザの MCP」節が、各道具の使用感の報告を持つ
- ISSUE-133 — この Issue を起票した受け箱の仕分けの元
- ISSUE-46 — マイルストーンの所属の canonical
