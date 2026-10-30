# config-guard

リポジトリ内の設定ファイルとドキュメントの構造逸脱を静的検出するツール。

- skills の `allowed-tools` と committed `home/.claude/settings.json` の stale なツール名参照
- committed `home/.claude/settings.json` の不変条件（含めてはならないキー、ローカル絶対パス、marketplace / plugin の非公開参照、permissions トークンの妥当性）
- 追跡ファイルに変更を隠す index の bit（skip-worktree / assume-unchanged）が立っていないか
- `home/apm.lock.yaml` の deployed_files が gitignore されているか（追記漏れ）
- `home/.config/mise/config.toml` の global ツール pin が exact か
- `home/apm.yml` の依存 pin が commit SHA で固定され、同一リポジトリを指す行どうしと `home/apm.lock.yaml` が記録する実配置で揃っているか
- `home/.config/herdr-app/keys.json` の keybinding（JSON の構文とキーの重複、`next` / `prev` のアクションとキーの向きの整合、アクションが herdr-app の組み込みコマンドと mod に解決するか）
- 追跡下の Markdown（`git ls-files '*.md'`）の相対リンクが実在するか（Issue を `closed/` へ移すと両端のリンクが切れる）
- 常時ロードされる指示ファイル（`home/.claude/CLAUDE.md` と `paths` を持たない `home/.claude/rules/*.md`）の総バイト数が予算内か

```bash
uv run config-guard /path/to/repo-root
```

検出が 1 件以上あれば非ゼロ終了する。CI（test.yml）と pre-commit から呼ばれる。

リンク検査は散文中のリンク記法を実リンクとして解決する。記法を例として書きたいときはインラインコードかバッククォートのコードフェンスで囲むこと（コード領域は検査対象外）。

keys.json のアクションの解決は herdr-app が持つ一覧（`herdr-app commands` と live の mod）に照らすので、herdr-app が入っていない環境（CI）では自動的に skip される。JSON の構文・キーの重複・向きの整合はどこでも走る。
