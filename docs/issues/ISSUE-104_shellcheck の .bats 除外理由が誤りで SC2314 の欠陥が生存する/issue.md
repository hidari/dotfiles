---
status: open
---

# fix(ci): shellcheck の .bats 除外理由が誤りで SC2314 の欠陥が生存する

## 背景

ISSUE-102 タスク 5 (`home/.zshrc` へ tgrep のラッパー関数を追加する作業) のレビュー中に見つけた。
新規に足した `.bats` の `!` の使い方を shellcheck が SC2314 として指摘したが、これは実装者が
`shellcheck -x -P SCRIPTDIR scripts/tests/zshrc-tgrep.bats` を手で叩いたから気づけたもので、
pre-commit や CI のどちらもこのクラスの欠陥を検出しない。ISSUE-102 のスコープでは、直すのに
このブランチが触らないファイル (`.pre-commit-config.yaml` と `.github/workflows/test.yml`) の
変更が要るため対象外にし、見失わないようにこの Issue へ切り出す。

### `.bats` は shellcheck の対象から外れている

対象選択は 2 箇所にある。

- `.pre-commit-config.yaml` の shellcheck hook の `files:` 正規表現
- `.github/workflows/test.yml` の shellcheck job が `git ls-files` に渡す pathspec

どちらも `.sh` / `.bash` などの拡張子と一部の拡張子無しスクリプトだけを対象にしており、
`.bats` を含まない。

### 除外の理由として書かれている文が誤り

`.pre-commit-config.yaml` の shellcheck hook のコメントは「`.bats` は bats 構文 (`@test`) を
shellcheck がパースできないため対象外」と書いている。実際に
`shellcheck -x -P SCRIPTDIR scripts/tests/*.bats` を実行すると、パースエラー系
(SC1009 / SC1072 / SC1073) は 1 件も出ない。そもそも指摘の 1 つである SC2314 自体が
「In Bats, `!` will not fail the test...」という bats 構文を前提にしたルールで、
bats 構文を読めないパーサはこの指摘を出せない。

### 除外を外すと今の設定のままでは CI が赤くなる

`scripts/tests/*.bats` 全体に対する `shellcheck -x -P SCRIPTDIR` の実測 (shellcheck 0.11.0、
CI が pin しているのと同じ版) は次のとおり。

| コード | 件数 |
| --- | --- |
| SC2031 | 36 |
| SC2030 | 21 |
| SC2314 | 7 |
| SC1090 | 6 |
| SC2034 | 4 |
| SC2016 | 3 |
| SC1003 | 1 |
| 合計 | 78 |

SC2030 / SC2031 は bats の `run` がサブシェルで実行されることに起因する誤検出の族で、
78 件のうち過半数 (57 件) を占める。`.bats` を対象へそのまま足すと、この族だけで CI が赤くなる。
除外を外す作業は、SC2314 を直すだけでなく、どのコードを抑制するか (あるいは SC2314 だけを
individually 有効化するか) を決める設計判断を伴うため、単純な 1 行修正では終わらない。

### SC2314 の 7 件は生死が分かれている

shellcheck の severity が実際の状態を分けている。

- **死んでいる (error、3 件)**: `scripts/tests/bootstrap_plugins.bats:147`、`:148`、
  `scripts/tests/bootstrap.bats:222`。前の 2 つは「既存のものは add / install しない」の
  アサーションで、後続 (`bootstrap_plugins.bats:150`-`153`) にさらにアサーションが続くため、
  この `!` は最後の文でなく今日も何も失敗させていない。つまりこの要件は現状ピン留めされて
  いない
- **生きているが壊れやすい (style、4 件)**: `scripts/tests/bootstrap_plugins.bats:62`、`:74`、
  `scripts/tests/bootstrap.bats:223`、`scripts/tests/gitleaks.bats:53`。今は `!` がテスト内の
  最後の文なので機能しているが、後ろに 1 行足された瞬間に無言で死ぬ

### メタな教訓

除外の理由がコメントとして canonical な設定ファイル (`.pre-commit-config.yaml`) 自身に
書かれている。canonical だからこそ再検証されにくく、この文がそもそも実行して確かめられずに
書かれた (パースエラーが出ないことを実際に試していない) まま残っていた。

## タスク

- [ ] `.pre-commit-config.yaml:237` 付近の除外理由のコメントを、実測 (パースエラーは出ない、
      SC2314 自体が bats 前提のルール) に合わせて訂正する
- [ ] `.bats` を対象へ含めたときに生き残らせる shellcheck コード (SC2030 / SC2031 の抑制、
      あるいは SC2314 だけを individually 有効化する形など) を決める
- [ ] `.pre-commit-config.yaml` の shellcheck hook の `files:` と
      `.github/workflows/test.yml` の shellcheck job の pathspec の両方に `.bats` を足す
      (どちらか片方だけだと drift する)
- [ ] SC2314 の 7 件を直す (死んでいる 3 件・生きているが壊れやすい 4 件の両方)。死んでいる
      3 件は「既存のものは add / install しない」の要件が実際にピン留めされているかを
      合わせて見直す
- [ ] 対象を壊す / 機構を壊す / 取り付けを外すの 3 種の変異で、追加した検査が赤くなることを
      確かめる

## 関連

- ISSUE-102: この Issue の発端になったレビュー (タスク 5) を持つ
- ISSUE-60: shellcheck の対象選択が拡張子ベースであることに起因する別の取りこぼし
  (拡張子を持てないファイルの無検査)。族は同じだが対象と原因が違う
- ISSUE-98: `test.yml` の shell 検査の射程と置き場を検討している。対象選択を 1 箇所に
  まとめる案が採られれば、この Issue の対象追加もそちらに合流しうる
