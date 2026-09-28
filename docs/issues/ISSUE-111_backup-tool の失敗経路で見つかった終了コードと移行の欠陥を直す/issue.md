---
status: open
---

# fix(backup-tool): 失敗経路で見つかった終了コードと移行の欠陥を直す

## 背景

jev-lint-curated の tests-cover-failure-paths が指した backup-tool の関数に、失敗経路のテストを足した (2026-09-28)。その途中で、プロダクトコードの欠陥が4つ見つかった。どれもコードを読んで再現を確かめてある。主目的 (jev-lint の指摘への対応) から外れるので、直さずにここへ切り出した。悪い振る舞いを固めないよう、足したテストは該当する戻り値を縛っていない。

- error_behavior が stop のとき、最初のペアが失敗して残りを飛ばすと、成功が0件でも終了コード2 (一部のペアが失敗) を返す。runner の `_determine_exit_code` は `fail == total` のときだけ3を返し、total は飛ばしたペアも数えるが、飛ばしたペアは fail に入らない。README の終了コードの表は2を「一部のペアが失敗」、3を「全ペアが失敗」としている
- rsync が無いと traceback で落ちる。`rsync.run` は起動時の FileNotFoundError をそのまま呼び出し元へ渡す。`run_backup` は BackupAbortedError だけを、cli の `_run_command` は ConfigError だけを受けるので、Python の終了コード1で終わる。README の終了コード1は「設定不備・ユーザー中止・マイグレーション失敗」で、意味がぶつかる
- `parse_bash_conf` は空の BACKUP_PAIRS と負の数値 (MINIMUM_FREE_SPACE_GB など) を通す。`load_config` はどちらも拒むので、`migrate_file` は読めない backup.toml を書いたうえで、旧 backup.conf を .bak へ移す。移行は成功したように見えて、読めない設定だけが残る
- パス検証で中断したときのログで、ペア名が二重になる (`[p1] [p1] ソース のディレクトリが存在しません`)。`_execute_pair` が `_verify_path` に渡す role がペア名を含み、`run_backup` が例外を記録するときにもう一度付けている

マージ前のレビュー (2026-09-29) で5つ目が見つかった。

- 空のソースディレクトリの容量が取れない。本物の du は空のディレクトリで0を返すが、`_measure_kb` は `size > 0` の規則を du と df に一律に掛けるので、0は None に畳まれる。runner は「ソース容量を取得できませんでした」と警告して容量チェックを省く。df の0は不正な値だが、du の0は正当な値である。この振る舞いを固めていた du 側のテストは、同じレビューで外した

## 決めること

- stop で飛ばしたペアを、終了コードの集計でどう扱うか。失敗に数えるか、飛ばした件数を別に持って3の条件に入れるか。README の終了コードの表も合わせて直す
  - もう1つの候補は、ループがペアごとの結果 (成功・部分・失敗・中断・未実行) の列を作り、要約ログと終了コードをその列から導く形。カウンタを1つ足す案だと、どのペアが始まったかをテストがログの文面 (test_runner の `_PAIR_STARTED`) から拾う形が残る
- 外部コマンドの不在を1か所で扱うか。今は mount が無いと False (マウントされていないと誤診する)、du と df が無いと None (容量チェックを警告付きで省く)、rsync が無いと例外 (traceback) と、3通りに分かれている。rsync だけを決めると、残りの2通りが残る。候補は、run_backup か cli の冒頭で存在を1回確かめる事前検査。今の3通りを固めているテスト (test_paths・test_disk・test_rsync の、コマンドが無いときのテスト) は書き換えの対象になる
- 移行の検証を `load_config` の規則とどう揃えるか。`parse_bash_conf` に同じ規則を書き足すと2か所に分かれるので、書き出す前に生成した TOML を `load_config` へ通す形を第一候補にする
  - ただし、この案では型の検査が migrate 側に残る。レビューの委譲先の報告によると、ADDITIONAL_EXCLUDE の型検査を外すと文字列が1文字ずつの配列として書かれて `load_config` を通り、LOG_BASE_DIR の型検査を外すと直列化が AttributeError で落ちる (自分では再現していない)
  - 別の候補は、`load_config` を `tomllib.loads` と「dict から Config への検証」に分け、`parse_bash_conf` が Bash の値を同じ形の dict にして検証へ渡す形。migrate 側に残るのは Bash 構文の解析と数値変換だけになり、空の BACKUP_PAIRS と負の数値も同じ1か所で塞がる
  - test_migrate のうち、migrate 固有の文面で縛っている3本 (`空フィールド`・`ERROR_BEHAVIOR`・`LOG_BASE_DIR` を match するもの) は、検証を1つにすると落ちるので書き換えの対象になる
- du の0を正当な値として扱うか。候補は、`size > 0` の規則を `_measure_kb` から `measure_dest_total_kb` の側へ移す形

## タスク

- [ ] 上の各点を決める
- [ ] 5つの欠陥を、直した後の振る舞いを表すテストを先に書いてから直す
- [ ] README の終了コードの表を、決めた集計に合わせる

## 関連

なし
