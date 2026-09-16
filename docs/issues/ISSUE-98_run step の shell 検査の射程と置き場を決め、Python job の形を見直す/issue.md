---
status: open
---

# ci: run step の shell 検査の射程と置き場を決め、Python job の形を見直す

## 背景

PR #223 で `test.yml` の全 run step を bash (pipefail 付き) で動かすようにした。各 step の実効の
shell は `scripts/tests/ci-shell-probe.py` が YAML の構造から判定し、`ci-wiring.bats` が照合する。
検査の対象は `test.yml` だけである。

同じ PR のマージ前レビュー (simplify の altitude 観点) が次の 3 点を挙げた。PR のレビュー範囲を
超えるので切り出す。

### 1. 射程が test.yml に閉じている

根本原因 (shell を省いた run step は `bash -e` で動き pipefail が付かない) は、リポジトリの全
workflow に共通する。

- `mise-update-check.yml` の run step 2 つは shell も `defaults.run` も持たない。各 step の先頭で
  `set -euo pipefail` を書くという別の仕組みで、同じ懸念に対処している。プローブをこのファイルへ
  向けると 2 件とも違反として出る
- composite action の run step は shell の明示が必須だが、`sh` を選んでも今の検査は見ない。
  `.github/actions/` の 6 つのうち run step を持つ 5 つは、今はすべて bash を明示している

### 2. 検査の置き場

今の検査は、`uv run --with pyyaml` で起動する単発のスクリプト、`KEY=VALUE` 形式の出力、bats での
照合という 3 段を経る。

- config-guard は pyyaml を依存に持ち、pytest と scan が pre-commit で走る
- bats は pre-commit で走らないので、`test.yml` から shell を消す編集は CI の bats job まで検出されない
- 判定のモデル (job の `defaults.run` が workflow 側を丸ごと置き換える) の pin も、YAML を
  書き出して別プロセスで読む遠回りになっている
- `ast-grep-wiring-probe.py` も同じ形なので、移すなら両方を扱う

### 3. Python job の形

job 側に `defaults.run` を持つのは working-directory のためで、Python 系の 5 job (backup-tool /
config-guard / mise-update-notifier / node-security-notifier / claude-hooks) がそれぞれ持つ。
job 側の `defaults.run` は workflow 側を丸ごと置き換えるので、job を足すたびに shell を書き忘れる
罠が残る (今は検査が拾う)。backup-tool / mise-update-notifier / node-security-notifier の 3 つは、
working-directory と pytest の引数以外がほぼ同じである。

## 決めること

- **射程。**全 workflow へ広げるか、composite action の run step まで含めるか。
  `mise-update-check.yml` に workflow 側の `defaults.run` を足して仕組みを 1 つに揃えるなら、
  各 step の `set -euo pipefail` に残る意味は `-u` だけになる
- **置き場。**bats とプローブのまま残すか、config-guard の check にするか。config-guard へ移すと、
  判定の関数を dict の fixture で直接テストでき、違反は commit 時に止まる
- **job の形。**次のどちらかで job 側の `defaults.run` を無くせる
  - (a) step から `uv run --directory scripts/<project>` で呼ぶ。`.pre-commit-config.yaml` は
    既にこの形で呼んでいる
  - (b) matrix でまとめる。job 名が変わるので、必須ステータスチェックの名前 (ISSUE-50) に
    影響しうる。ISSUE-50 が集約ジョブを必須チェックにする形で先に入れば、影響は集約ジョブの
    `needs` だけに閉じる。`jobs.<id>.defaults.run` で matrix の値を使えるかは確かめていない
- job を減らすと setup-uv の取得回数も減る。Issue 37 の影響範囲 (本文の「8 job」は、2026-09-17
  時点の `test.yml` では 6 job) に効く

## タスク

- [ ] 射程を決め、対象になる run step を数える (composite action を含めるなら `runs.steps` も)
- [ ] 検査の置き場を決める。`ast-grep-wiring-probe.py` の扱いも同時に決める
- [ ] job の形を決める。matrix にするなら ISSUE-50 との前後を決める
- [ ] 決めた形で実装し、対象を壊す / 機構を壊す / 取り付けを外すの 3 種の変異で赤を確かめる
- [ ] 検査が対象集合のどこまでを覆うかを数える

## 関連

- Issue 45 (closed): プローブを入れた PR が閉じた Issue
- ISSUE-50: 必須ステータスチェックと集約ジョブ。job 名の変更と前後関係がある
- Issue 37: setup-uv の取得失敗。job を減らすと取得回数も減る
- Issue 38: 同じ 4 プロジェクト (claude-hooks 以外) へ一斉に適用する作業。job の見直しと着手を揃えられる
- Issue 26: uv ハーネス 3 本を claude-hooks の 1 job へまとめた前例
- ISSUE-60 と ISSUE-85: config-guard に置く検査の候補で、置き場の議論が重なる
- ISSUE-57: YAML などに埋め込んだシェルの構文検査。こちらは構文ではなく実効の shell を見るので観点が違う
