---
status: open
---

# fix: Phase D.1 の status 置換が in_progress の Issue に当たらない

## 背景

`dev-workflow:in-repo-issue` の Phase D.1 は、クローズ実行の第 1 手をこう書いている。

> D.1 frontmatter `status` を `closed` に書き換え (Edit ツールで `status: open` を `status: closed` に置換)。

置換元が `status: open` の literal になっているが、同じ skill には `status` を `in_progress` にする経路がある。

- Phase B が通常の着手で `open → in_progress` の遷移を規定している
- Phase C.3 の未完タスクがある分岐が「status を `in_progress` に更新するだけ、close しない」と規定している
- Phase F.1 が reopen で `closed` から `in_progress` へ書き換える

したがって Phase D が回る対象は `open` とは限らない。`in_progress` の Issue に D.1 をそのまま適用すると、置換対象が 1 件も見つからない。Edit ツールは一致しなければ失敗するので、その場では気づける。だが手順どおりに進めた結果として失敗するので、実行者は「skill が間違っているのか自分の読み違いか」を切り分けるところから始めることになる。

D.4 の理由文も同じ前提を再掲している。

> 明示 stage を省くと `status: open` のまま `closed/` 配下に入り、検索手順が頼る `^status: open$` の grep が壊れる。

`in_progress` の Issue で同じ手順違反が起きた場合、`closed/` 配下に入るのは `status: in_progress` であって `open` ではない。理由文が名指しする grep はそもそも `in_progress` を拾わないので、この説明は起こりうる不整合の一部しか説明していない。

同じ `^status: open$` の grep は、D.4 の理由文が引用するだけでなく、「検索手順」節が全 open Issue を列挙するコマンドと、「Red flags」の表でも根拠になっている。この 2 箇所は D.1 と倒れ方が違う。D.1 は Edit の不一致で止まるので失敗が表に出るが、grep は `in_progress` の Issue を黙って結果から落とすだけで、「該当なし」と「そもそも見ていない」を区別しない。

実測 (2026-09-04) では dotfiles の active な Issue 45 件のうち 2 件が `in_progress` で、「検索手順」節のコマンドは 43 件しか返さない。この 2 件はクローズするときに Phase D が回るので、D.1 の空振りもあわせて踏む。仮想の経路ではない。

## タスク

- [ ] Phase D.1 から literal 前提を外す。`status` 行が `open` と `in_progress` のどちらでもありうることを書き、literal 置換ではなく「`status` 行を `closed` にする」形の指示にする
- [ ] Phase D.4 の理由文を `open` 固定ではなく「編集前の値のまま `closed/` 配下に入る」形へ直す。あわせて、その状態が検索手順のどの経路からも異常として現れないことを述べる
- [ ] 他に `status: open` を literal で前提している箇所が無いか skill 全体を走査する。「検索手順」節の grep と「Red flags」の表が少なくとも該当する

## 関連

Issue 18 は同じ不整合を config-guard で検出する提案で、本 Issue は不整合を作る側の指示文を直す。Issue 18 の検査は本 Issue を直しても要る (手順を読む側への指示は検出ではない) ので、片方が他方を不要にしない。

skill の canonical は agentic-coding-tools なので実際の修正はそちらで行う。本 Issue は dotfiles 側の受け口として立てている。
