# Claude Code Plugins (dotfiles 管理)

この dotfiles で管理する Claude Code plugin の仕組みと、開発時 / 運用時のワークフローをまとめる。

現在の plugin:

- `security-blue-red-team` — product-agnostic な Vulnerability Assessment / Red Team / Blue Team セキュリティテスト自動化

## 1. plugin がロードされる仕組み

Claude Code の plugin は「ファイルがそこにある」だけではロードされない。次の 4 要素が揃って初めて有効になる（symlink を貼っただけでは認識されない点に注意）。

```
① plugin 本体ファイル        home/.claude/plugins/security-blue-red-team/
   (この repo が source of truth)
        │
② marketplace catalog        home/.claude/plugins/.claude-plugin/marketplace.json
   plugin の存在と source: "./security-blue-red-team" を宣言する。
   source は marketplace root (= .claude-plugin/ の親 = home/.claude/plugins/) からの相対パス。
        │
③ marketplace 登録           ~/.claude/settings.json の extraKnownMarketplaces
   hidari-dotfiles: { source: directory, path: <この repo>/home/.claude/plugins }
        │
④ plugin 有効化              ~/.claude/settings.json の enabledPlugins
   "security-blue-red-team@hidari-dotfiles": true
        ↓
   Claude Code が起動時に ③ の directory を読み → ② の catalog を解釈 → ① をロードする
```

ポイント:

- `source: directory` なので Claude Code は clone-cache を作らず、この repo を直接読む。
  repo の plugin を編集すると `/reload-plugins` で即反映される（能動開発に向く）。
- `~/.claude/plugins/security-blue-red-team` の symlink（`bootstrap.sh` が貼る）も存在するが、
  実際にロードを成立させているのは ③④ の marketplace 登録である。

## 2. settings.json の登録 (③④) をコミットしない理由

③④ は `~/.claude/settings.json`（= `home/.claude/settings.json` への symlink、追跡対象）に書かれるが、
**machine-specific な絶対パス**（`/Users/<user>/.../home/.claude/plugins`）を含むため、公開 repo にコミットしない。

- user-level の `settings.local.json` は Claude Code 非サポート（project-level のみ）なので、登録の逃がし先がない。
- そのため `git update-index --skip-worktree home/.claude/settings.json` で
  「ローカルには登録を残しつつ git の追跡からは外す」運用にする。
  これで `git status` はクリーンに保たれ、登録行が誤ってコミットされることを防げる。

コミットするのは ②（`marketplace.json`、相対パスのみでマシン非依存）だけ。

## 3. ワークフロー

### A. plugin を編集する（日常開発）

1. `home/.claude/plugins/<plugin>/` を直接編集
2. Claude Code で `/reload-plugins`（即反映、clone-cache なし）
3. plugin ファイルのみを commit → PR（`settings.json` は触らない）

### B. バージョンを上げる

1. plugin 本体を更新
2. `marketplace.json` の `plugins[].version` と `metadata.version` を更新
3. commit → PR

### C. 新しいマシンに展開する（bootstrap 後の手動 4 step）

1. `git clone` + `./bootstrap.sh`（symlink 配置。`settings.json` も symlink される）
2. `/plugin marketplace add ~/Develop/dotfiles/home/.claude/plugins`
3. `/plugin install <plugin>@hidari-dotfiles`
4. `/reload-plugins`
5. `git update-index --skip-worktree home/.claude/settings.json`（③④ の登録を git から隠す）

### D. settings.json を正当に変更する（唯一の摩擦点）

`skip-worktree` 中は LSP 追加などの正当な変更もコミットできないので、一時解除する。

1. `git update-index --no-skip-worktree home/.claude/settings.json`
2. `git add -p home/.claude/settings.json`（正当な変更だけ選択し、`extraKnownMarketplaces` / `enabledPlugins` の登録行は除外）
3. commit
4. `git update-index --skip-worktree home/.claude/settings.json`（再設定）

## 4. トレードオフと代替案

この設計（directory source + marketplace.json のみコミット + skip-worktree）の評価:

- 得たもの: 公開 repo に実ユーザー名 / 絶対パスをコミットしない、dev の即時反映を維持、catalog は repo 管理で再現可能
- コスト: D の摩擦（settings.json コミット時に skip-worktree 解除が必要）、新マシンで手動 4 step

検討した代替案: **github source**（`extraKnownMarketplaces` を `{ source: github, repo: <owner>/dotfiles }` にする）

- 利点: settings.json がポータブル（絶対パスなし）になり、そのままコミットできる
- 欠点: Claude Code が repo を clone-cache してそこから読むため、編集の即時反映が失われ、反映に `/plugin marketplace update` が必要になる。
  また github source は `marketplace.json` を **repo root の `.claude-plugin/`** に置くことが必須（サブパス指定構文は無い）ため、
  現在の `home/.claude/plugins/.claude-plugin/marketplace.json` を root へ移動し、plugin source を `./home/.claude/plugins/<plugin>` に修正する必要がある。

能動開発中は directory source を採用する。plugin が安定して編集頻度が下がったら github source へ移行する選択肢を残す。
