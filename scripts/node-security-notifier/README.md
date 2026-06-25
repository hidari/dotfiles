# node-security-notifier

Node の脆弱性 RSS (`https://nodejs.org/en/feed/vulnerability.xml`) を日次で監視し、
新着セキュリティリリースを macOS 通知で知らせる。exact full-version で pin した node を
手動 bump する起点に使う。

## 実行

```bash
uv run node-security-notifier
```

初回実行は通知せず現状を seed する。以降は既読 GUID 集合と比較し、新着のみ通知する。
状態ファイルは `~/.local/state/node-security-notifier/seen.json`。

## 自動実行

bootstrap.sh が LaunchAgent (`com.hidari.node-security-notifier`) を導入し、日次 18:00 に
`run.sh` を起動する。ログは `~/.local/state/node-security-notifier/launchd.log`。
