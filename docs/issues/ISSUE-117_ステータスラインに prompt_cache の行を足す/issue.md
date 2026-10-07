---
status: in_progress
---

# feat: ステータスラインに prompt_cache の行を足す

## 背景

Claude Code は statusLine の入力に `prompt_cache` を渡す (https://code.claude.com/docs/en/statusline#prompt-cache-fields)。
キャッシュが warm のうちに次のメッセージを送れば再キャッシュのコストを払わずに済むので、残り時間と、cold になったときに払う量をステータスラインの最下行へ出す。

仕様の canonical は `scripts/tests/statusline-prompt-cache.bats`。ここには判断の経緯だけを残す。

- `prompt_cache` が無いあいだは行ごと出さない。手元の版に無いフィールドは、その部分だけ飛ばす
- warm は緑、残り10分以下は黄色、cold は赤。warm のまま期限を過ぎたデータは cold として出す
- カウントダウンを止めないため、settings.json の statusLine に `refreshInterval` を足す
- 行の並びは情報の所有者で分けてきたが、キャッシュの行はユーザーの依頼どおりリポジトリの行の下に置く

## タスク

- [ ] 仕様を表す bats テストを先に書き、赤を確かめる
- [ ] statusline-command.sh にキャッシュの行を実装する
- [ ] 黄色の境界、cold の判定、k の丸め、欠けたフィールドを飛ばす分岐への変異注入で、狙ったテストが赤になることを確かめる
- [ ] settings.json の statusLine に `refreshInterval` を足し、config-guard の scan と pytest を通す
- [ ] warm / 期限切れ間近 / cold のサンプル JSON を実スクリプトに流して出力を確かめる
- [ ] /simplify と feature-dev:code-reviewer を通し、PR の CI を全ジョブ pass させる

## 関連

- ISSUE-91 (statusLine へ並行セッション数を出す。同じスクリプトの別の行)
