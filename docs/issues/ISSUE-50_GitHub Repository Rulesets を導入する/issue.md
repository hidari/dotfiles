---
status: open
---

# feat: GitHub Repository Rulesets を導入する

## 背景

`main` を常に動く状態に保ち、変更を必ず PR 経由にするためのガードレールを Repository Rulesets
で敷く。目的・採用するルール・見送る項目・未確認事項は同ディレクトリの
[github-rulesets-design.md](github-rulesets-design.md) が canonical で、本文では再掲しない。

本 Issue は dotfiles で実施する分と、そこから他リポジトリへ展開する分を追う。

## dotfiles の現況 (2026-08-27 実測)

設計文書は新規導入を前提に書かれているが、dotfiles には既に ruleset `protect-main` が active で
動いている (2026-08-12 作成)。作業になるのは差分だけで、設計文書が求める項目の過半は充足済み。

| 設計文書が求めるもの | dotfiles の現況 |
| --- | --- |
| 直接 push の禁止 (PR 必須) | 充足。直近 40 コミットに直 push は無い |
| force push のブロック | 充足 |
| ブランチ削除の禁止 | 充足 |
| 必要な承認数 0 | 充足 |
| linear history 必須 | 未設定。`allow_merge_commit` も true のままで、履歴にも merge commit が 2 件ある (2026-08-28 実測。起票時は「許可されたマージ方式が squash のみ」と書いていたが誤り) |
| 必須ステータスチェック | 未設定 |
| bypass list は原則空 | 未充足。User 1 名が always で入っている |
| 集約ジョブ | 存在しない。`test.yml` の 10 ジョブはすべて独立で `needs` を持たない |
| 適用タスクの置き場 | 設計文書が指名する `justfile` が dotfiles に無い |

classic の branch protection API は 404 を返す。ruleset は別系統で classic に出ないため、
classic だけで判定すると「保護なし」と誤読する。

展開先の候補として 2026-08-27 に実測した agentic-coding-tools は、ruleset が空で classic も
404 だった。あちらは差分ではなく新規導入になる。

2026-09-01 に測り直したところ、この記述は既に古い。classic は今も 404 (rc 1) だが、
`rules/branches/main` は `deletion` / `non_fast_forward` / `pull_request` /
`required_status_checks` の 4 rule を返す。あちら側の作業で `protect-main` が入ったためで、
下のタスク「agentic-coding-tools へ展開する」は展開ではなく既に入っているものの確認になる。
classic だけを見ると今も 404 なので、上の判定手順を使わないと「まだ空」に見える点も同じ形で
ある。

## 着手前に確認すること

- 必須ステータスチェックを入れると、CI の不安定さがそのままマージのブロックになる。
  Issue 37 が未着手なので、どちらを先にやるかを決める
- `require_extra_approval_for_unattributed_changes` が true で入っている。承認数 0 の運用と
  どう噛み合うかを確認する。追加承認を要求する条件に当たると、承認できないまま詰む
- bypass list を空にしたときに詰む経路が無いか。`dev-workflow:in-repo-issue` の Phase C/D は
  既定で main へ直接 commit してクローズする設計で、skill 側に feature PR へ同梱する代替経路が
  ある。dotfiles は既に代替経路で運用できているが、展開先では経路の確認が要る

## タスク

- [ ] 設計文書の未確認事項を検証し、ラベルを更新する
- [ ] 集約ジョブ名の規約を決める。置き場を skill / rules / スクリプトのどれにするかも決める
- [ ] dotfiles の `test.yml` に集約ジョブを追加する
- [ ] dotfiles の `protect-main` に必須ステータスチェックと linear history を足す
- [ ] リポジトリ設定の「Allow merge commits」を OFF にする
- [ ] bypass list の扱いを決める。空にするか、逃げ道として残すか
- [ ] タグ用 ruleset を作る
- [ ] ruleset の JSON をエクスポートし、汎用定義として dotfiles へ配置する。対象リポジトリの
      一覧は実行時に取得し、JSON へ列挙しない
- [ ] 適用タスクの置き場を決める。`justfile` を新規に入れるか、既存のスクリプト群へ寄せるか
- [ ] agentic-coding-tools へ展開する
- [ ] 残りのリポジトリへ展開する

## 関連

- Issue 37。必須ステータスチェックを入れると、ツール取得の一時障害がそのままマージのブロックに
  なる。着手順に影響する
- ISSUE-54 が gitleaks の検出網の穴を扱う。うち 1 件は merge commit の内容が CI の走査から
  漏れる問題で、本 Issue の「Allow merge commits を OFF にする」が入口を塞ぐのに対し、
  そちらは検査側の層を足す。両方あって多層になるので、どちらかで代替しない。
  なお本 Issue の現状評価の表にある「許可されたマージ方式が squash のみなので merge commit は
  既に入らない」は実測と食い違う (2026-08-28 に確認したところ `allow_merge_commit` は true の
  ままで、履歴にも merge commit が 2 件ある)。上のタスクが未完なのと整合しているので、
  表の側を訂正する必要がある
- agentic-coding-tools の ISSUE-48: 保護ブランチの判定手順が in-repo-issue skill の
  ライフサイクル節の内側にあり、Issue を扱っていない文脈からは到達しない。この Issue が
  ruleset を足すほど classic API だけの判定は外れるので、手順へ入る辺はあちらが作る
