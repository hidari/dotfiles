---
status: open
---

# fix(ci): gitleaks の検出網が merge commit と allowlist 境界で素通りする

## 背景

セキュリティレビューで、`.gitleaks.toml` と CI の組み合わせに 2 つの穴が見つかった。どちらも
対照実験で確定させている。ISSUE-21 が既に列挙している穴とは別で、どちらも履歴の書き換えを
伴わずに塞げる。

### 1. CI の range scan が merge commit の内容を走査しない

`.github/workflows/test.yml` の leak guard は次の形で走る。

```
gitleaks git --log-opts="$RANGE" --redact --no-banner -c .gitleaks.toml
```

`git log` は既定で merge commit の diff を出力しないため、merge commit で初めて導入された
内容は gitleaks へ一切渡らない。使い捨てリポジトリで evil merge を合成して測った結果:

| スキャン | 検出 |
| --- | --- |
| `--log-opts="BASE..HEAD"` (CI の実際の形) | 1 件 (通常コミットのみ) |
| `--log-opts="-m BASE..HEAD"` | 3 件 (merge commit 由来も検出) |
| merge commit 単独、`-m` なし (対照) | 0 件 |
| 通常コミット単独 (対照) | 1 件 |

`-m` を足すだけで塞がる。対照が 0 件と 1 件に割れているので、検査自体は生きている。

現在の運用は squash merge だが、リポジトリ設定は `allow_merge_commit=true` のままで、
履歴にも merge commit が 2 件実在する (どちらも 2025-11 の初期 PR)。ISSUE-50 が
「許可されたマージ方式が squash のみなので merge commit は既に入らない」と書いているのは
実測と食い違う。同 Issue のタスクには「Allow merge commits を OFF にする」が未完で残っており、
表とタスクが互いに矛盾している。

ISSUE-50 が完了すれば入口は塞がるが、`-m` は 1 語で足りるうえ検査側の層なので、
入口の設定に依存せず独立して持つ価値がある。

### 2. allowlist の境界文字 `.` が実在しうる名前を通す

`macos-user-path` の allowlist は placeholder を許可するために境界を見ている。この境界集合に
`.` が入っているため、許可語で始まり `.` が続く名前が丸ごと通る。同じ構造が
`email-address` の `^git@` にもあり、SSH URL 以外の任意ドメインを通す。

使い捨てリポジトリで 14 検体を stage して測った結果、対照 6 件は期待どおりに振る舞い、
3 件が素通りした。

| 検体 | 結果 | |
| --- | --- | --- |
| 実在しそうな名前 (対照) | 検出 | ルールは生きている |
| 許可語の直後に境界文字が無い形 (対照) | 検出 | 境界の設計自体は効いている |
| 許可語 + `.` + 続き (`/Users/user.smith/` など 3 形) | 素通り | 本項目 |
| `git@` + 内部ホスト名 | 素通り | 本項目 |
| 例示ドメインのメール (対照) | 素通り | 意図どおり |

`.` を境界から外すと `/Users/user.local` のような正当な placeholder 表記が検出側へ回る
可能性があるため、境界集合を狭めるか、許可語の直後を明示的に終端させるかの判断が要る。

なお同じ実験で大文字始まりと小文字 `/users/` も素通りしたが、これは ISSUE-21 が
「検出できない表記が 3 つある」として既に記録している。本 Issue では扱わない。

## タスク

- [ ] CI の range scan に `-m` を足す
- [ ] merge commit で導入したリークが CI で赤くなることを変異注入で pin する
      (検査対象を壊す / 検査機構を壊す / 取り付けを外す の 3 種)
- [ ] `macos-user-path` の allowlist から境界文字 `.` を外すか、許可語を終端させる形へ直す
- [ ] `email-address` の `^git@` を SSH URL の形に限定する
- [ ] 上記 2 つのルール変更を `scripts/tests/gitleaks.bats` へ negative case として足す
      (素通りした 4 形をそのまま検体にする)
- [ ] ISSUE-50 の表にある「許可されたマージ方式が squash のみ」の記述を実測に合わせて訂正する

## 関連

- ISSUE-21 が検出網の穴を既に 3 種類記録している (バイナリ素通り、表記の 3 形、
  コミットメッセージ)。本 Issue の 2 件はそこに無く、かつ履歴の書き換えを伴わない
- ISSUE-50 が merge commit の入口側を塞ぐ。本 Issue は検査側の層で、両方あって多層になる。
  同 Issue の記述の訂正も本 Issue のタスクに含めた
- ISSUE-29 が private リポジトリ名の露出を扱う。allowlist の境界はそちらの検出にも効く
