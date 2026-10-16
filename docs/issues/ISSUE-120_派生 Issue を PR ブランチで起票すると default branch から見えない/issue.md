---
status: open
---

# docs: 派生 Issue を PR ブランチで起票すると default branch から見えない

## 背景

in-repo-issue skill (canonical は agentic-coding-tools) は、Issue をどのブランチで起票するかを決めていない。Phase A は起票先のブランチに触れず、関連節は「起票後に必ずブランチを作る」とだけ書く。

別リポジトリでの実例 (2026-10-08 の報告)。セッションが PR ブランチの上で、その PR が Closes する実装 Issue と一緒に、調査中に見つけた派生 Issue 2 本 (その PR では直さないもの) を起票した。PR が設計判断待ちで長く Draft のまま残ったので、派生 Issue は 4 日間 default branch に無かった。そのうち 1 本は本番での実害が確認されて最優先になり、着手するために Issue だけを default branch へ移す docs PR を別に作ることになった。

移すときにもう 1 つ問題が出た。実装 Issue も一緒に移すと、未マージのコード変更を `[x]` で主張する形になる。各行に「PR のブランチ上、未マージ」と書き足す必要があった。

採番の衝突 (未マージのブランチで起票済みの識別子) は、`issue-id.py --next` の全 ref の走査で既に防いでいる。足りないのは衝突ではなく可視性の側である。

報告側の提案 (採否はこちらで決める)。

- 起票先の規則を足す。PR ブランチへ同梱してよいのは、その PR が Closes する Issue だけにする。派生 Issue は default branch への docs PR で起票する
- 機械で検出するなら、`issue-id.py` に「default branch に無く、他の ref にしか無い open な Issue」を列挙する入口を足す

## タスク

- [ ] 起票先の規則を in-repo-issue の Phase A に足すか決める (Closes する Issue だけを PR ブランチへ同梱し、派生 Issue は default branch 側で起票する)
- [ ] 検出の入口 (default branch に無く他の ref にしか無い open な Issue の列挙) を `issue-id.py` に足すか決める。足すなら全 ref の走査を `--next` と共有する
- [ ] 決めた変更を agentic-coding-tools で実装し、apm の pin を上げて配る

## 関連

- agentic-coding-tools の ISSUE-69 (起票前の重複検索が、分岐後に main で起票された Issue を拾わない。可視性の逆向きの形)
