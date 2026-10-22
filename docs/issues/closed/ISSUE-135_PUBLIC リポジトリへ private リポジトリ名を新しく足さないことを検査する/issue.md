---
status: closed
---

# feat: PUBLIC リポジトリへ private リポジトリ名を新しく足さないことを検査する

## 背景

Issue 29 の残タスク「現ツリーに新規露出を足さないことを検査する手段を検討する」を切り出した (ユーザー決定 2026-10-22)。現ツリーの露出そのものは同じ日に除去し、Issue 29 は閉じて Issue 21 の露出一覧の7番へ統合した。

露出は事後に取り消せない。リモートブランチを消して PR を閉じても commit と diff は公開のまま残り、GitHub には PR を削除する API が無い。予防に価値があるのはこのためである。

検査手段の候補 (`docs/` 直下の allowlist、リポジトリ参照の allowlist 反転、追跡外の禁止語リスト) と、採らない案 (追跡外ファイルの追加イベントだけを門にする) は、Issue 29 の「検査手段の候補」節に 2026-08-11 の調査結果として残っている。private リポジトリ名を追跡下へ列挙して弾く方向は、守るべき名前を追跡下へ書くことになるので採れない。

3つ目の候補にあたる禁止語リストの在り処の配線は ISSUE-92 で入った。その後、公開される本文 (コミット、PR など) は `dev-workflow:commit-and-pr-message` の入口が禁止語リストの層を当てるようになった。追跡下へ入るファイルの内容に同じ層が当たっているかは確かめていない。

## タスク

- [x] 追跡下へ入るファイルの内容に、禁止語リストの層が pre-commit か CI で当たっているかを確かめる。当たっていなければ、当てる経路 (pre-commit の hook) を足すかを決める
- [x] Issue 29 の3候補を、ISSUE-92 以後の状態で比べ直して採るものを決める。リストを持たないマシンで静かに skip される点の扱いも決める
- [x] 採った検査に3種の変異 (対象 / 機構 / 取り付け) を当てる

## 実測 (2026-10-22、着手前)

禁止語リストの層は、追跡ファイルにはどこからも当たっていなかった。`.pre-commit-config.yaml` と `.github/workflows/` に checker を起動する hook も job も無い (対照として、同じ探し方で gitleaks の hook は見つかる)。当たっていたのはコミットや PR の本文だけで、それは `commit-and-pr-message` の入口が当てていた。

checker (`check-leak-guard-denylist.py`、apm の deploy 先に在る) には追跡ファイル全体を index の blob で走査する `--check` が既にあり、pre-commit へ取り付ける前提で書かれていた。手で当てると次のとおりで、1回あたり0.5秒、常駐36MB だった。

- 追跡435件のパスすべてと、431件の内容を照合した。内容を読まなかった4件は1MiB を超える blob (cheatsheet の `.af` と `.png`) で、checker の上限による除外である
- 既存の露出が見つかった。closed 配下の Issue 文書に、リストに載っている1語が現れていた。private リポジトリ名ではないが、Issue 21 の露出一覧に載っていない項目だった。伏字にし、Issue 21 の一覧へ8番として足した

checker は `--check` しか持たず差分だけを見る形が無いので、既存の露出を残したまま hook を入れると最初のコミットから赤くなる。伏字化を同じ PR に入れたのはこのためである。

## 決定 (ユーザー決定 2026-10-22)

### 採る検査は候補3と候補1

- 候補3 (禁止語リスト) を pre-commit の hook `leak-guard-denylist` にした。名前そのものを見る唯一の候補で、ISSUE-92 の配線とリストが既に在る
- 候補1 (`docs/` 直下の allowlist) を config-guard の `docs_layout` にした。名前は見ないが CI でも走るので、候補3が走らない経路 (`--no-verify`、CI) の backstop になる。追跡下の `docs/` 直下は今も `issues` `known-issues` `superpowers` の3つだけで、偽陽性は0件だった。受け箱 (`docs/.feedbacks-box/`) は ignore されているので、追跡下へ現れるのは `add -f` したときだけで、それも捕まえる
- 候補2 (リポジトリ参照の allowlist 反転) は採らない。偽陽性を測っておらず、候補3が名前を直接見るので射程の大半が重なる

### リストが届かない起動元では止める (fail-closed)

checker は環境変数が未設定のとき rc 0 の skip で、pre-commit は rc 0 の hook の出力を出さないので、そのままでは黙って通る。このリポジトリの hook では、変数が届かなければ rc 2 で止める入口 (`scripts/leak-guard/denylist-check.sh`) を挟んだ。リストを持たないマシンでは `SKIP=leak-guard-denylist` を明示して抜ける。

これで ISSUE-92 が「射程」節で塞がないまま残した GUI の git クライアントと IDE の VCS 機能も、黙って通らず止まる側へ移る。checker の未設定 skip という判断 (リストを持たない第三者のため) は変えていない。止めるのはこのリポジトリの hook だけである。

## 機構が覆う範囲 (2026-10-22、この変更の tree)

| 経路 | 禁止語リストの hook | docs_layout |
| --- | --- | --- |
| zsh から打つコミット (.zshenv が読まれる) | 全追跡ファイルのパスと内容を照合する | 走る |
| .zshenv を読まない起動元 (GUI、IDE、`env -i`) | rc 2 で止まる | 走る |
| `--no-verify` | 走らない | 走らない (CI で走る) |
| CI | 走らない (リストが無い) | 走る |

内容の照合が覆うのは、追跡440件のうち436件だった。外れる4件は上の cheatsheet で、Issue 21 の「バイナリを素通りする」と同じ穴にあたる。docs_layout は名前を見ないので、規約の置き場の中に書いた露出は CI では捕まらない。コミットの本文は別の層 (`commit-and-pr-message` の入口) が持ち、この2つは見ない。

## 検証

### 変異

入口は bats が `LEAK_GUARD_HOOK` で変異体を指して検査した (本体は書き換えていない)。config-guard 側は1箇所ずつ書き換えて pytest を回し、戻したあとハッシュで一致を確かめた。

- 対象: 禁止語を含むファイルを stage すると止まる (live の bats と下の live smoke)。`docs/notes/` へ置くと config-guard が止める
- 機構: 入口の8件 (未設定の判定を `:+` にする、判定を外す、止めずに rc 0 で抜ける、`--check` を落とす、rc を `|| true` で握りつぶす、cwd から checker を引く、抜け方の hook id を変える、checker を別の bundle のパスへ向ける) はすべて落ちた。`exec` を外すだけの変異と `exec ... || true` は、どちらも `set -e` と exec の下で rc が変わらない等価変異だった。docs_layout の9件 (allowlist を無効にする、前方一致にする、直下のファイルを許す、allowlist を広げる、`-z` を落とす、`docs` の判定を前方一致にする、大小文字の違う `Docs/` を通す、その判定と pathspec の `icase` を外す) もすべて落ちた。`Docs/` を通す変異は、検体が `Docs/notes/` だけのあいだ allowlist の側が先に止めて生き残ったので、置き場が規約どおりの `Docs/issues/` を検体に足した
- 取り付け: hook の id を変える、`always_run` を `files` に替える、入口を checker の直接呼び出しへ戻すの3件は `test_precommit_wiring.py` が落とした。`scan()` から docs_layout を外すと `test_cli.py` が落とした

途中で、bats の最後の文でない `[[ ]]` が偽でもテストを落とさないことを踏んだ (この環境の bats は bash 3.2 で動く)。`test_helper.bash` の `assert_contains` / `refute_contains` に揃えて直した。

### live smoke

ワークツリーで、環境変数を `env -i` で空にしてから起動した。

- `zsh -c` から陽性の検体を stage して `git commit`: hook が止めた (findings=1、rc 1)
- 同じく陰性の側: `status=checked tracked=440 scanned=436 ... findings=0` で通った
- `/bin/bash -c` (.zshenv を読まない) から `git commit`: 入口が rc 2 で止めた
- `SKIP=leak-guard-denylist`: hook は Skipped になった
- `docs/notes/` へ置いて config-guard の hook を起動: 1件を検出して止めた

## 関連

- Issue 21: 露出の棚卸し。private リポジトリ名の項目は7番、この Issue で見つけた項目は8番
- Issue 29 (closed): 検査手段の候補の調査結果を持つ
- ISSUE-92 (closed): 禁止語リストの在り処の配線
- ISSUE-54 (closed): gitleaks の検出網の穴
