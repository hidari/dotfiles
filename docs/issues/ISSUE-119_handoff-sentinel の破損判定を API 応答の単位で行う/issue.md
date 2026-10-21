---
status: open
---

# fix: handoff-sentinel の破損判定を API 応答の単位で行う

## 背景

handoff-sentinel の Stop 判定は transcript の assistant entry を 1 件ずつ見ている。ところが Claude Code の transcript は、1 つの API 応答 (`message.id`) を content block ごとに別の entry へ分けて書く。2026-10-16 に dotfiles の transcript 8 本 (Claude Code 2.1.295〜2.1.301) を数えたところ、1 entry が持つ content block はどれも 1 つで、応答 1 つが 2〜2.5 entry に分かれていた。

ここから 2 つの問題が出ている。

- 窓の長さがぶれる: 窓 (`DEFAULT_TAIL_ASSISTANTS`) は entry の件数なので、実際に入る応答の数はテキストだけの応答が多いかツールの多い応答が多いかで約 2.5 倍変わる。Claude Code が entry の分け方を変えると、窓の大きさも黙って変わる。バイト数の窓が 2.1.300 の api-request 記録で縮んだのと同じ型の依存が、1 段ずれて残っている
- 誤検知ガードが働いていない (前からある問題): `_is_broken` は、tool-call の記法を話題にした会話を破損と数えないために、同じ entry に `tool_use` があれば数えない。しかし text と tool_use を両方持つ entry は 8 本で 0 件で、両方を持つ応答 (8〜57 件) はすべて別々の entry に分かれていた。記法を本文で説明してからツールを呼ぶ応答の text は破損として数えられ、窓の中に規定数たまると Stop が誤って block する

いまの窓 (entry 100 件) は応答にすると 40〜50 件で、2.1.300 より前の 1 MiB の窓 (entry 107〜135 件) とほぼ同じ範囲にある。だから窓を件数で切り直した変更 (`fix/cc-herdr-version-followup` ブランチ) は、以前の意味を保ったまま入れ、単位の変更はこの Issue に分けた。

## タスク

- [ ] 窓を `message.id` の異なり数 (API 応答の数) で数える形と、既定の件数を決める
- [ ] `_is_broken` の判定を応答単位にまとめ、同じ応答のどこかに `tool_use` があれば text を破損と数えないようにする
- [ ] 応答が複数の entry に分かれた形の fixture で、窓の件数とガードの両方をテストで pin する (変異注入で確かめる)
- [ ] `message.id` を持たない assistant entry の扱いを決める (8 本では 0 件だったが、合成のメッセージで現れうる)

## 関連

- ISSUE-67 (コンテキスト閾値の通知が 1 セッション 1 回で再武装しない。同じフックの別の契機)
