# node-security-notifier

nodejs.org の配布一覧 (`index.json`) から security リリースの版を日次で取得し、状態ファイルへ書く。mise の global 設定にある node の pin と比べて告げるのは、Claude Code の SessionStart で走るプローブ (`home/.claude/hooks/guard_probes.py` の `probe_node_security`) の側である。

## 実行

```bash
uv run node-security-notifier
```

状態ファイルの置き場は `state.py` の `STATE_RELPATH` (ホームディレクトリからの相対) が持つ。

## 自動実行

bootstrap.sh が LaunchAgent (`com.hidari.node-security-notifier`) を導入し、plist の時刻に日次で `run.sh` を起動する。ログの置き場も plist が持つ。
