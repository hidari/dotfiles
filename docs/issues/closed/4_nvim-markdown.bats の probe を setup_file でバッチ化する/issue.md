---
status: closed
---

# test: nvim-markdown.bats の probe を setup_file でバッチ化する

## 背景

`scripts/tests/nvim-markdown.bats` は 9 個の `@test` がそれぞれ probe（`nvim --clean --headless`）を spawn するが、probe の構成は `probe_with_extends` / `probe_without_extends` の 2 種類しかない。PR #49 の pre-merge gate の efficiency レビューによる実測では、1 invocation 約 50ms・ファイル全体 0.738s のうち約 0.4s（55%）が同一コマンドの反復。今後 assertion を足すたびに nvim spawn が +1 される構造でもある。

bats-core 1.13（ローカル・CI とも pin 済み）の `setup_file()` + `$BATS_FILE_TMPDIR` で probe を 2 回だけ実行して出力をキャッシュし、各テストはキャッシュを読んで assert する形にすれば spawn は 8→2 に減る。

PR #49 で見送った理由: `NVIM_BIN` / `CI` の skip ガードは `setup()` に実装されており、probe を `setup_file()` へ移すとガードとの整合の再設計が必要（`setup_file` 内での `skip` の bats semantics 確認を含む）。0.4s の利得に対して gate 終盤でのテストハーネス再設計はリスク過大と判断した。

## 決めたこと

既存のガード `require_command_or_skip` を `setup_file()` から呼ぶだけで済み、`setup()` は
消した。bats は `setup_file()` の skip をそのファイルの全 `@test` の skip として出し、
`setup_file()` の非 0 はファイル全体を赤くする (bats 1.14 で実測)。ローカル skip と
CI hard-fail がファイル単位でそのまま成り立つ。

途中で「`setup_file()` の中では skip を呼べない」と結論し、可否をフラグで `setup()` へ運ぶ
回避策を作ったが、誤りだった。再現に使った fixture の `@test` 名が日本語で、観測した
「0 件実行で rc=1」は skip ではなく日本語名による未実行だった
(`rules/bats-test-name-ascii-only.yml` が禁じる形)。fixture をリポジトリの検査の外に置いたので、
この規則が効かなかった。回避策は同じ PR の中で撤去した。

`@test` 側は 1 行も変えていない。`probe_with_extends` という関数名を保ったまま中身を
キャッシュ読みへ差し替え、spawn する側を `spawn_probe_*` として分離したため。呼び出し側の
契約 (`run probe_with_extends` で `$output` が得られる) が変わらないので、移行で 30 本の
アサーションを書き換える必要がなかった。

ガードの挙動は fixture を子プロセスで走らせるテスト (`test-helper-guards.bats`) が
pin するようにしたので、手でガードを確かめるための差し替え口 `NVIM_BIN` は外した。

所要時間は、main と変更後を別の worktree に展開し、同じ巡目で両者を交互に走らせて測った
(2026-09-17、開発機)。このファイル単体は 4 巡で、main の 3.02〜3.15 秒に対して
1.96〜2.21 秒になり、約 1 秒縮んだ。全スイートは 2 巡で、main の 51.9〜52.3 秒に対して
52.5〜53.5 秒だった。同じ PR でテストを足しているので、全スイートの差はこの変更の効果として
は読めない。

## タスク

- [x] bats 1.13 の `setup_file()` と `skip` の semantics を確認する（setup_file 内 skip の可否、CI hard-fail をファイル単位でどう表現するか）
- [x] probe 2 種を `setup_file()` で 1 回ずつ実行し `$BATS_FILE_TMPDIR` にキャッシュする
- [x] 各 `@test` をキャッシュ読み込みへ切り替え、ローカル skip / CI hard-fail のガード挙動を維持する
- [x] ガード検証（`NVIM_BIN=nvim-not-installed` と `CI=true NVIM_BIN=nvim-not-installed`）が現行と同じ結果になることを確認する
- [x] 全スイート緑 + 実測での短縮を確認する

## 関連

- PR #49（pre-merge gate の efficiency レビューで検出、実測値の出典）
- `scripts/tests/nvim-markdown.bats` / `scripts/tests/nvim-markdown-probe.lua`
- `.github/actions/setup-bats/action.yml`（bats の SHA pin を持つ）
- ISSUE-45: 同じ PR で解消した。どちらも `scripts/tests/` の同じファイル群を触る
