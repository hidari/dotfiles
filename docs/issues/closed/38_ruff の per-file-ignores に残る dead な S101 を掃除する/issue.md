---
status: closed
---

# chore: ruff の per-file-ignores に残る dead な S101 を掃除する

## 背景

4 つの uv プロジェクトの `pyproject.toml` が `[tool.ruff.lint.per-file-ignores]` に
`"tests/*" = ["S101"]` を持つ。しかしどのプロジェクトも `select` に `S` (flake8-bandit) を
入れていないため、S101 (ベア `assert` の使用) は元から検出されていない。無効化しているつもりの
設定が、そもそも何も無効化していない。

対象は `scripts/backup-tool` / `scripts/config-guard` / `scripts/mise-update-notifier` /
`scripts/node-security-notifier` の 4 本。Issue 26 の集約で作った `scripts/claude-hooks` も
同じ状態だったが、そのレビューで見つかったため先に落としてある。

no-op であることは対照付きで実測した。`assert True` だけを持つプローブを作り、プロジェクトの
設定で `ruff check` すると `All checks passed!`、同じファイルを `--isolated --select S101` で
検査すると `Found 1 error.` になる。設定が S101 を抑止しているのではなく、S101 が最初から
選ばれていない。

ruff は使われていない `per-file-ignores` を警告しないので、この種の設定は静かに残り続ける。
読む側からは「tests では assert を許している」という意図が伝わるのに、実際には tests 以外でも
assert が通る。宣言と実態が食い違ったまま検査に出ない状態になっている。

## タスク

- [x] 4 プロジェクトのどちらへ寄せるか決める。`S101` を落として現状の検査面に合わせるか、
      `select` へ `S` を足して tests 以外のベア `assert` を検出する側へ寄せるか
- [x] 決めた方針を 4 プロジェクトへ一斉に適用する。1 本だけ直すとリポジトリ内で表記が割れる
- [x] `select` へ `S` を足す側を選んだ場合は、既存コードに S 系の指摘が出ないか実測してから入れる (S を足す側は選ばなかったので該当しない)
- [x] 同種の dead config が他にないか確認する。`per-file-ignores` の各エントリについて、
      対応するルールが `select` に含まれるかを突き合わせる

## 決めたこと (2026-10-22)

`S101` を落とす側へ寄せた (ユーザー裁定)。ISSUE-131 の PR のボーイスカウトで 4 本の `pyproject.toml` から `"tests/*" = ["S101"]` を消し、中身が空になった `[tool.ruff.lint.per-file-ignores]` の見出しも消した。tests 以外のベア `assert` の検出は今回は増やしていない。

## 残りの ignore の突き合わせ (2026-10-22)

`select` に含まれるかだけでなく、ignore を外したときに実際に抑止しているものがあるかを `ruff check --isolated --select <ルール>` で数えた。

- `per-file-ignores` に残るのは claude-hooks の 9 ファイルと config-guard の 3 ファイルの `N802` だけで、12 エントリすべてが 2〜103 件を抑止している。死んだものは無い
- 共通の `ignore` にある `RUF002` / `RUF003` は、config-guard で 65 件、backup-tool と claude-hooks で各 2 件を抑止している。mise-update-notifier と node-security-notifier では今は 0 件だが、`RUF` が `select` に入っているので日本語の docstring に全角の括弧を書いた時点で発火する。`S101` のように原理的に発火しない設定とは違い、方針として生きているので残した

## 関連

- Issue 26: Claude Code フックの共通基盤を集約する。集約 PR のレビューで他 4 本の同型が分かり、
  対象がフック以外のプロジェクトにも及ぶため分離した
- ISSUE-98: 同じ 4 本を含む Python 系の job の形を見直す。着手を揃えられる
