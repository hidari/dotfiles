# config-guard

リポジトリ内の設定ファイルの構造逸脱を静的検出するツール。

- skills の `allowed-tools` と committed `home/.claude/settings.json` の stale なツール名参照
- `home/apm.lock.yaml` の deployed_files が gitignore されているか（追記漏れ）
- `home/.config/herdr/config.toml` の keybinding（`previous_*` と `next_*` の方向整合、chord 重複、アクション名の綴り）

```bash
uv run config-guard /path/to/repo-root
```

検出が 1 件以上あれば非ゼロ終了する。CI（test.yml）と pre-commit から呼ばれる。

herdr のアクション名検査だけは `herdr --default-config` を真実源に引くため、herdr が入っていない
環境（CI）では自動的に skip される。方向整合と chord 重複はどこでも走る。
