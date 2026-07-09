---
status: open
---

# test: nvim-markdown.bats の probe を setup_file でバッチ化する

## 背景

`scripts/tests/nvim-markdown.bats` は 9 個の `@test` がそれぞれ probe（`nvim --clean --headless`）を spawn するが、probe の構成は `probe_with_extends` / `probe_without_extends` の 2 種類しかない。PR #49 の pre-merge gate の efficiency レビューによる実測では、1 invocation 約 50ms・ファイル全体 0.738s のうち約 0.4s（55%）が同一コマンドの反復。今後 assertion を足すたびに nvim spawn が +1 される構造でもある。

bats-core 1.13（ローカル・CI とも pin 済み）の `setup_file()` + `$BATS_FILE_TMPDIR` で probe を 2 回だけ実行して出力をキャッシュし、各テストはキャッシュを読んで assert する形にすれば spawn は 8→2 に減る。

PR #49 で見送った理由: `NVIM_BIN` / `CI` の skip ガードは `setup()` に実装されており、probe を `setup_file()` へ移すとガードとの整合の再設計が必要（`setup_file` 内での `skip` の bats semantics 確認を含む）。0.4s の利得に対して gate 終盤でのテストハーネス再設計はリスク過大と判断した。

## タスク

- [ ] bats 1.13 の `setup_file()` と `skip` の semantics を確認する（setup_file 内 skip の可否、CI hard-fail をファイル単位でどう表現するか）
- [ ] probe 2 種を `setup_file()` で 1 回ずつ実行し `$BATS_FILE_TMPDIR` にキャッシュする
- [ ] 各 `@test` をキャッシュ読み込みへ切り替え、ローカル skip / CI hard-fail のガード挙動を維持する
- [ ] ガード検証（`NVIM_BIN=nvim-not-installed` と `CI=true NVIM_BIN=nvim-not-installed`）が現行と同じ結果になることを確認する
- [ ] 全スイート緑 + 実測での短縮を確認する

## 関連

- PR #49（pre-merge gate の efficiency レビューで検出、実測値の出典）
- `scripts/tests/nvim-markdown.bats` / `scripts/tests/nvim-markdown-probe.lua`
- `.github/actions/setup-bats/action.yml`（bats 1.13 pin）
