---
status: open
---

# chore: ruff の per-file-ignores に残る dead な S101 を掃除する

## 背景

4 つの uv プロジェクトの `pyproject.toml` が `[tool.ruff.lint.per-file-ignores]` に
`"tests/*" = ["S101"]` を持つ。しかしどのプロジェクトも `select` に `S` (flake8-bandit) を
入れていないため、S101 (ベア `assert` の使用) は元から検出されていない。無効化しているつもりの
設定が、そもそも何も無効化していない。

対象は `scripts/backup-tool` / `scripts/config-guard` / `scripts/mise-update-notifier` /
`scripts/node-security-notifier` の 4 本。Issue #26 の集約で作った `scripts/claude-hooks` も
同じ状態だったが、そのレビューで見つかったため先に落としてある。

no-op であることは対照付きで実測した。`assert True` だけを持つプローブを作り、プロジェクトの
設定で `ruff check` すると `All checks passed!`、同じファイルを `--isolated --select S101` で
検査すると `Found 1 error.` になる。設定が S101 を抑止しているのではなく、S101 が最初から
選ばれていない。

ruff は使われていない `per-file-ignores` を警告しないので、この種の設定は静かに残り続ける。
読む側からは「tests では assert を許している」という意図が伝わるのに、実際には tests 以外でも
assert が通る。宣言と実態が食い違ったまま検査に出ない状態になっている。

## タスク

- [ ] 4 プロジェクトのどちらへ寄せるか決める。`S101` を落として現状の検査面に合わせるか、
      `select` へ `S` を足して tests 以外のベア `assert` を検出する側へ寄せるか
- [ ] 決めた方針を 4 プロジェクトへ一斉に適用する。1 本だけ直すとリポジトリ内で表記が割れる
- [ ] `select` へ `S` を足す側を選んだ場合は、既存コードに S 系の指摘が出ないか実測してから入れる
- [ ] 同種の dead config が他にないか確認する。`per-file-ignores` の各エントリについて、
      対応するルールが `select` に含まれるかを突き合わせる

## 関連

- Issue #26 の集約 PR のレビューで検出。`scripts/claude-hooks` の同じ設定を落とした際、他 4 本にも
  同型があることが分かった
- [Issue #26: refactor: Claude Code フックの共通基盤を集約する](../26_Claude%20Code%20フックの共通基盤を集約する/issue.md)。
  集約の過程で見つかったが、対象がフック以外のプロジェクトにも及ぶため分離した
