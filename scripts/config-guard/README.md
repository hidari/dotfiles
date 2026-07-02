# config-guard

skills の `allowed-tools` と committed `home/.claude/settings.json` の stale な
ツール名参照・構造逸脱を静的検出するリポジトリ内ツール。

```bash
uv run config-guard /path/to/repo-root
```

検出が 1 件以上あれば非ゼロ終了する。CI（test.yml）と pre-commit から呼ばれる。
