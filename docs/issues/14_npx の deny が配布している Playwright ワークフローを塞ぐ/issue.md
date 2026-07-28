---
status: open
---

# fix: npx の deny が配布している Playwright ワークフローを塞ぐ

## 背景

`home/.claude/settings.json` の `permissions.deny` に `Bash(npx:*)` がある。この設定は `~/.claude/settings.json` の実体なので全プロジェクトに効く。

一方で同じリポジトリが次を配っている。

- `home/.claude/CLAUDE.md` の「テストコード」節が、E2E テストを `npx playwright init-agents --loop=claude` で生成することを要求している
- `home/apm.yml` が `playwright-cli` と `playwright-test` の 2 skill を apm 経由で全マシンへ配る。本文の実行例は `npx playwright ...` が中心で、前者に 24 箇所、後者に 13 箇所ある

`deny` は `allow` より優先され、確認プロンプトも出ない。プロジェクト側の `settings.local.json` の `allow` でも抜けられないため、逃げ道はセッション中に設定を編集することだけになる。新マシンで bootstrap を回した直後にエージェントが CLAUDE.md どおり E2E を書き始めると、そこでハードブロックされる。

矛盾は live 側に以前から存在していたもので、settings.json の committed 同期 (Issue #8 とは別系統の作業) で committed 側にも入った。同期は live を忠実に写す作業なので、矛盾の解消はこちらで扱う。

なお MCP サーバの npx 起動はハーネスのプロセス生成であって Bash ツール呼び出しではないため、この deny の影響を受けない。

## タスク

- [ ] `npx` を一律 deny する意図を確認する。pnpm へ寄せる方針なのか、npm のグローバル汚染を避けたいのか
- [ ] 解消方針を決める
  - [ ] deny を `Bash(npm install:*)` 等の lockfile を汚す側に絞り、runner 用途の `npx` を通す
  - [ ] `npx` を `deny` から `ask` へ移し、必要な経路だけ都度許可する
  - [ ] deny を維持し、`home/.claude/CLAUDE.md` の E2E 手順を `pnpm dlx` へ書き換える。ただし apm 配布の 2 skill は上流が別リポジトリなので書き換えられず、skill 本文の `npx` は残る
- [ ] 決めた方針を live と committed の両方へ反映する。片方だけ直すと新しい drift になる
- [ ] 配布物 (`home/.claude/CLAUDE.md`) と設定が矛盾していないことを確認する

## 関連

同種の「配布物どうしの不整合」を機械検出できるかは未検討。config-guard は現状 committed settings.json の構造しか見ておらず、設定と CLAUDE.md や skill 本文との整合は対象外である。
