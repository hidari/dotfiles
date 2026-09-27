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

## 決めること

- stop で飛ばしたペアを、終了コードの集計でどう扱うか。失敗に数えるか、飛ばした件数を別に持って3の条件に入れるか。README の終了コードの表も合わせて直す
- rsync が無いことを、ペアの失敗 (BackupAbortedError) として扱うか、実行前の検査で止めるか
- 移行の検証を `load_config` の規則とどう揃えるか。`parse_bash_conf` に同じ規則を書き足すと2か所に分かれるので、書き出す前に生成した TOML を `load_config` へ通す形を第一候補にする

## タスク

- [ ] 上の各点を決める
- [ ] 4つの欠陥を、直した後の振る舞いを表すテストを先に書いてから直す
- [ ] README の終了コードの表を、決めた集計に合わせる

## 関連

なし
