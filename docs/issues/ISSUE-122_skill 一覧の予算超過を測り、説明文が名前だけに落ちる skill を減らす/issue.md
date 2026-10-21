---
status: open
---

# agent: skill 一覧の予算超過を測り、説明文が名前だけに落ちる skill を減らす

## 背景

Claude Code は skill の一覧にコンテキストの1%の予算を持ち、溢れると呼び出しの少ない skill から説明文を落として名前だけにする (公式の skills のページ)。トリガの語彙は説明文にあるので、名前だけになった skill は自然言語からは起動されない。

2026-10-19の棚卸しで、名前だけの skill が多数あった。chrome-devtools-mcp の skill 群、superpowers の一部、account から同期される plugin の skill、`home:` 付きの双子の大半などである。同じ日に PR #263 で使われていない skill 3つと plugin 4つを外した。外した効果はバイト数ではなく、一覧に戻った説明文の数で測る。

一覧を膨らませている出所は、分かっている範囲で3つある。

- `home:` 付きの双子。dotfiles の `home/` 配下を触ると `home/.claude/skills/` が directory-scoped で登録され、同じ skill が `home:` 付きでもう一度並ぶ。登録はセッション中に戻らない。棚卸しのセッションでは、apm で消した3つの skill が `home:` 付きで一覧に残り続けた。何で登録されるかには観測の食い違いがある。手元の記録は Read / Write / Edit で発火し Bash では発火しないとしているが、Bash だけで触ったあとに登録されたという観測がある。ただし subagent は起動した時点で親の登録を持っていたので、どの操作が登録させたかは分けられていない
- account から同期される design / engineering / legal の plugin (knowledge-work-plugins)。同期の置き場は2つあり、skill は片方に26、もう片方に cowork-plugin-management の2つを足した28ある。MCP の認証ツールも載る。使用はどちらの設定ディレクトリでも0回だった。止める手段が claude.ai 側の設定か、`enabledPlugins` の `@synced` のキーかは確かめていない。後者なら config-guard の marketplace の許可リストに当たるので、同じ変更で許可リストも直す
- apm の flat 分解による二重登録。40 が扱う

外した skill に `skillOverrides` を使う案は採らない。外すという同じ決定を apm.yml と settings.json の2箇所に書くことになる。使うとすれば、残すが呼び出しの少ない skill で、上流の文面を変えられないものに限る。

## タスク

- [ ] 新しい headless のセッションで `/context` か `/skill-doctor` を使い、一覧の予算と、名前だけになっている skill を数える。実行中のセッションの一覧は古いので使わない
- [ ] 予算を変える設定があるかを確かめる。バイナリ (2.1.303) には `skillListingBudgetFraction` と `skillListingMaxDescChars` の文字列があるが、settings のキーとして効くかは分かっていない。未知のキーは警告なしで無視されるので、効いたことを一覧の変化で確かめる
- [ ] `home/` を一度も触っていない headless のセッションで、`home:` の双子が Read と Bash のどちらで登録されるかを測り直す。結果で手元の記録を直す
- [ ] `home:` の双子を止める手段 (`Skill(home:...)` の deny、`skillOverrides`、作業ディレクトリの置き方) があるか確かめる
- [ ] 同期される plugin を止める手段を確かめ、止めるかを決める (Hidari の判断)
- [ ] 手当てのあとに一覧を測り直し、戻った説明文の数を記録する

## 関連

- 40: apm の flat 分解による二重登録
- ISSUE-90: apm の依存が持ち込む常時ロード層の検知
- ISSUE-114: plugin の説明文も config-guard の予算の外で載る
