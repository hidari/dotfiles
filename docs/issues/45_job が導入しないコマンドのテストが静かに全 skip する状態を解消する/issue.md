---
status: open
---

# fix: job が導入しないコマンドのテストが静かに全 skip する状態を解消する

## 背景

CI の `bats` job は `bats scripts/tests/` でスイート全件を走らせるが、導入するのは
bats / Neovim / ast-grep / uv / zsh だけである。テスト側は不在のコマンドを `skip` で
かわすので、そのコマンドを必要とするファイルは **1 件も検証せずに緑** になる。

カバレッジが失われているわけではない。gitleaks を要するテストは専用の `gitleaks` job が
gitleaks を導入して同じファイルを走らせる。問題は `bats` job の緑が「そのファイルを
検証した」ことの証拠にならない点で、これはこのリポジトリが繰り返し塞いでいる
「空・緑が健全と未検査を区別しない」形そのものである。

## 現状

`scripts/tests/test_helper.bash` の `require_command_or_skip` は「CI なら必須」を
環境の性質として持っているが、実際には job とコマンドの組み合わせの性質である。

- `gitleaks` は `bats` job に無いのが正しい (専用 job が持つ)
- macOS 専用のコマンドは Linux ランナーに無いのが正しい

このため現在のヘルパへ一括移行すると、正当な不在で CI が赤くなる。ヘルパのコメントには
契約の射程を書いてあるが、書いただけでは次の移行を止められない。

## 決めること

2 案ある。

1. 共有の composite action を切り出し、専用 job と `bats` job の両方から使う。pin を
   1 箇所へ集約して job 間の drift を防ぐという既存 composite の理由がそのまま当てはまる。
   静かな skip も消える
2. ヘルパへ「このコマンドはこの実行環境で必須か」という軸を渡す。正当な skip を残したまま、
   それ以外を fail loud にできる

どちらを採るかで、テスト側の書き換え量と CI の実行時間が変わる。

## タスク

- [ ] `bats` job で実際に skip されているテストの数と対象ファイルを CI ログから数える
- [ ] 上の 2 案から方針を決める
- [ ] 決めた方針を適用し、生の `skip` が残っているファイルを移行する
- [ ] 移行後に「skip 0 件」ではなく「実行されたテストの ID 集合」で確認する

## 関連

- [Issue #27: run-pester.ps1 の件数ガードを実効化する](../27_run-pester.ps1%20の件数ガードを実効化する/issue.md)
  - 同じ「0 件実行が緑になる」形。あちらは Pester のラッパ、こちらは bats と CI job の
    組み合わせで、機構は別
- [Issue #4: nvim-markdown.bats の probe を setup_file でバッチ化する](../4_nvim-markdown.bats%20の%20probe%20を%20setup_file%20でバッチ化する/issue.md)
  - 同じファイル群を触るので、着手順によっては衝突する
