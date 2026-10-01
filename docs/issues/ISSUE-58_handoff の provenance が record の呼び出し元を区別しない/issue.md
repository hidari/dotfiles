---
status: open
---

# fix(hooks): handoff の provenance が record の呼び出し元を区別しない

## 背景

`home/.claude/hooks/handoff-sentinel.py` の SessionStart 経路は `.cache/handoff.md` を
コンテキストへ注入する。注入された内容はモデルにとって指示と区別しにくいので、ここは
prompt injection の面になる。

この面には既に防御がある。注入の前に、user スコープの state に記録した内容ハッシュと
照合し、一致しなければ注入しない。コードのコメントも「リポにコミットされた第三者作成の
handoff.md を信頼された引き継ぎとして注入しない」と目的を明示しており、fail-closed である。

検証の順序も正しい。ハッシュは `raw` 全体で取り、切り詰めは照合の後に行う。逆順だと
先頭だけ正規で後半に注入を仕込んだファイルが通る。

使い捨てリポジトリで機構を測った結果、設計どおりに動く。

| 手順 | 結果 |
| --- | --- |
| record せずに session (対照) | 注入なし (0 バイト)、handoff.md はそのまま |
| record を実行 | provenance が 1 件書かれる |
| record 後に session | 注入あり、handoff.md は consumed へリネーム、provenance は削除 |

## 何が守られていないか

同じ検証で分かったのは、`record` が skill 専用の経路ではないことである。
`session-handoff` skill を経由せず、通常のシェル起動で直接呼ぶだけで provenance が書かれ、
次の SessionStart で注入される。

つまり provenance が弾くのは「第三者がリポジトリにコミットした handoff.md」だけで、
Bash ツールを持つエージェント自身が書いたものは素通りする。結果として、
1 セッション限りの prompt injection が、セッションを跨ぐ持続的な injection へ昇格する
経路が残る。

現実には prompt injection でモデルを操れる時点でそのセッション内で直接行動できるため、
新たに得られるのは永続性だけである。ただし永続性は質的な違いで、ユーザーが
「おかしいので新しいセッションを始める」という対処を無効化する。

skill も Bash 経由で `record` を呼ぶので、現在の設計では両者を区別する手段が無い。
これは構造的な限界であり、塞ぐには機構の追加が要る。

## 位置づけの食い違い

Issue 26 は必須フック検査の一般化を論じる中で、`handoff-sentinel` を必須に入れるかを
「個人ツールであり security guard ではない」として据え置いてよいとしている。

一方で現物のコードは provenance 照合を prompt injection 防御として実装し、fail-closed で
倒している。台帳側の位置づけと現物の位置づけが食い違っており、必須フック検査に入れるか
どうかの判断はこの食い違いを解消してから下す必要がある。

なお現在 `settings_invariants.py` が取り付けを pin しているのは PreToolUse の 2 本だけで、
SessionStart 側は配線を外しても config-guard は緑になる。

## タスク

- [x] `handoff-sentinel` を security guard として扱うかを決める (Issue 26 の据え置き判断を維持するか、改めるか)
- [x] 上の判断に応じて、`record` の呼び出し元を skill に限定する機構を持つか決める。案としては skill が one-time の nonce を state へ置き、`record` がそれを消費する形。ただし nonce を置く経路も Bash なので、どこまで塞げるかを先に見積もる
- [x] 注入時の文面を見直す。現在は「前セッションからの引き継ぎ」と名乗るが、内容の正しさは誰も保証していない。信頼の度合いを文面へ反映するか決める
- [x] `settings_invariants.py` の必須フック検査で SessionStart の配線を pin するか決める (イベント軸への一般化は PR #186 で済んでいる)
- [ ] 注入時の文面に、内容は検証されていない旨を添える
- [ ] `handoff-sentinel` の SessionStart 配線を必須フック検査で pin する
- [ ] 決めた方針を変異注入 3 種で pin する

## 裁定 (2026-10-02)

2026-10-02の棚卸しのあと、ユーザーが次のとおり決めた。

- `handoff-sentinel` を security guard として扱うか: 扱わない。Issue 26 の据え置きを維持する
- `record` の呼び出し元を限定する機構 (nonce 案): 持たない。nonce を置く経路が同じ Bash なので塞ぎきれないため
- 注入時の文面: 「内容は検証されていない」旨を添える。安く、読み手の信頼度を正しく下げられるため
- SessionStart 配線の pin: 必須フック検査で pin する。イベント軸への一般化は PR #186 で済んでいて、SessionStart で必須とされているのは guard-health.py と PRIVATE_CLAUDE.md の読み込みだけで、handoff-sentinel の配線は pin されていないため

## 関連

- Issue 26 が Claude Code フックの共通基盤を扱う。同 Issue の「必須フック検査をイベント軸で一般化する」は PR #186 で済んでいて、残るのは handoff-sentinel の配線を pin するかだった。本 Issue の裁定で pin すると決めた。
  同 Issue の未完タスクには観測フックの allowlist 廃止も含まれており、そちらは本レビューでも
  同じ箇所 (未知フィールドを丸ごとログへ書く形) が挙がったが、既に記録済みなので重複させない
- ISSUE-56 と ISSUE-55 が PreToolUse 層の穴を扱う。本 Issue は SessionStart 層で、
  守っている対象も違う (コマンド実行ではなくコンテキストへの注入)
- ISSUE-84 が同じ provenance の運用側を扱う。あちらは照合に失敗したことが無音で返る点を
  probe で塞ぐ話で、防御そのものは変えない。ただし上流委譲案 (書き出しと record を 1 つの
  ヘルパへ閉じる) は本 Issue の 2 番目のタスクが検討する nonce 案と同じ場所を触るため、
  どちらを先に決めるかで設計が変わる
