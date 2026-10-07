---
status: closed
---

# refactor: Tirith の Claude Code フックを撤去し zsh 側だけを残す

## 背景

tirith の監査ログ (2026-06-30〜09-03、判定271239件) を集計した結果、Claude Code の PreToolUse フックとしての tirith は、コストに見合う働きをしていなかった。

- エージェント由来の判定は266059件が通過、1739件がブロック、577件が警告だった
- ブロックの上位は `analysis_incomplete` 654件 (for ループや変数を含むコマンドを解析しきれない)、`confusable_text` 573件 (日本語の句点)、`mass_file_deletion` 517件 (20秒以内に3ファイルを消しただけで CRITICAL) で、いずれも正当な作業だった
- 実害を止めた可能性のある規則 (`delete_then_force_push` / `secret_write_then_network` / `base64_decode_execute` / `interpreter_hijack_env` / `credential_in_text` / `sensitive_env_export` など) は全件を読んだ。検査用のプローブか、feature ブランチへの `--force-with-lease` や `pnpm install` のような正当な作業のどちらかで、本物の介入は確認できなかった
- 一方でフックへの回避策が指示の層に積み上がっていた (`.cache/` を選ぶ理由、`-F` でのコミット、インラインの `python3 -c` の回避、grep の `-F -e` など)
- `tirith policy tune --from-audit` は誤検知が1700件あっても「変更の提案なし」を返し、調整の手がかりにならなかった

zsh の `tirith init` (人が打つコマンドの検査) は判定数が少なく自分でバイパスもできるので残す。

あわせて、監査ログ `log.jsonl` が256MiB の手前で 09-03 から更新されていないことが分かった。ブロックは続いているのに記録だけが止まっている。判定数の98%はエージェント由来だったので、フックを外せば流入は大きく減る。

## 決定事項

ユーザーの裁定 (2026-10-07) は次のとおり。

- フックだけを外し、zsh の `tirith init` と Brewfile の `brew "tirith"` は残す
- `permissions.allow` の `Bash(git push:*)` は変えない。dotfiles の main は ruleset の non_fast_forward で守られている
- 監査ログは今回の作業で退避し、記録を再開させる (削除はしない)
- 利用者が apm-install-guard.py だけになる共有層 `pretooluse.py` は apm-install-guard.py へ畳む

作業側で決めたことは次のとおり。

- `home/.claude/CLAUDE.md` の `.cache/` を使う規範は残す (ignore されたスクラッチ置き場という理由は tirith と無関係に成り立つ)。tirith を理由にした2つの項目と、完了前の「削除は `rm .cache/<file>` の形にする」という下位項目は消す。この形を求める理由は tirith の除外集合だけだった
- 監査ログは `log.jsonl` と `log.jsonl.head` を組のまま退避する。隔離したデータディレクトリで確かめたところ、上限に達したログへは追記されず (サイズ不変)、`.head` だけが残った状態でも tirith は新しいログを作り `.head` を数え直す (`tirith audit verify` が OK)。組で残すのは、退避した側を後から検証できるようにするため
- Jev へ送るのは tirith を含む行だけにし、私的なリポジトリ名を落とす。期待値は API を呼ぶ前に固定する

## タスク

DoD の機械判定は書き捨ての判定器 `.cache/ISSUE-115-dod.py` が持つ (追跡しない。/goal の条件で sha256 を固定する)。実行は `uv run --directory scripts/config-guard python ../../.cache/ISSUE-115-dod.py` で、各項目の D 番号は判定器の行と対応する。

- [x] D1/D3/D4 フックを撤去する: `tirith-check.py` と settings.json の配線、`guard_resolve` の tirith 関連、`guard_probes.probe_tirith` と登録簿、`settings_invariants._REQUIRED_HOOKS` の PreToolUse、`tool_provisioning.ALSO_REQUIRED` の tirith (docstring の「tirith だけを覆う」という主張も直す)、対応するテスト
- [x] D1 `pretooluse.py` を apm-install-guard.py へ畳み、`test_pretooluse.py` が守っていた性質を apm-install-guard のテストへ移す (件数ではなく、守っていた性質の一覧で突き合わせる)
- [x] 畳んだ後の apm-install-guard へ変異を注入し、移した性質ごとに期待したテストが赤くなることを確かめる (対象 / 機構 / 取り付けの3種)。apm-install-guard の配線を外すと config-guard が赤くなることも確かめる
- [x] D2 指示の層から tirith を前提にした記述を外す: `home/.claude/CLAUDE.md` の `.cache/` の理由づけ (`.cache/` を使う規範そのものは残す) と完了前の `rm .cache/<file>` の理由参照、`home/.claude/references/host-environment.md` の Tirith 節。config-guard の instruction_budget が通ること
- [x] D5 README の tirith 節を zsh の層だけの説明にし、Brewfile のコメントを直す
- [x] D6 関連 Issue (Issue 26 / ISSUE-66 / ISSUE-83) へ、撤去で消える部分を ISSUE-115 の参照つきで追記する
- [x] D7 agentic-coding-tools の `commit-and-pr-message` skill が Tirith を前提にした説明を持つので、追従を追う Issue を dotfiles に起票する (ISSUE-115 を参照する)
- [x] D8 監査ログを `log.jsonl.archived-<日付>` へ退避し、退避した側が退避前と sha256 で一致すること、新しい `log.jsonl` へ記録が再開したことを確かめる。`log.jsonl.head` (ハッシュチェーンの先頭) の扱いは tirith の挙動を確かめてから決める
- [x] D9 tirith に触れるメモリを全件読み、エージェント側の挙動を前提にした記述を直すか消す。MEMORY.md の索引も合わせる。判定は「ファイル名 / 裁定 (維持・修正・削除) / 理由」の表で transcript に出す
- [x] 残った tirith の言及 (リポジトリとメモリ) を Jev で一次選別する (「zsh の層の記述として正しい / エージェント側の前提で古い」)。Jev の supports は自動採用せず、古いと判定されたものと、正しいと判定されたものの抜き取りを自分で読む
- [x] D10 `pre-commit run --all-files` と `scripts/ci/run-bats.sh scripts/tests/` が rc 0 で、pytest と config-guard scan が Skipped になっていない
- [x] D11 headless の `claude -p` で、以前フックが止めた無害なコマンド (`printf | python3`) が通る。撤去前には同じスモークが止まることを対照として確認済みであること
- [x] `/simplify` と `feature-dev:code-reviewer` を通し、指摘を解消する
- [x] D12/D13 PR を作り、CI が全ジョブ成功する。Issue のクローズは PR に同梱する。working tree が clean で、HEAD が PR の head と一致する。マージはユーザーの判断で行う

## /goal に渡す条件

判定役は transcript しか読まないので、条件は表示された出力だけで判定できる形にする。判定器の sha256 は撤去前の状態で回し、D10 が PASS (着手前の状態が緑)、D11 を含む残りが FAIL (検査が赤を出せる) になることを確かめてから固定した。

```text
ISSUE-115 の DoD を満たす。直近のターンで次の4つがすべて transcript に表示されていること。(1) `shasum -a 256 .cache/ISSUE-115-dod.py` の出力が 607fde7feab0c87f0b61a8bbfe167ad3336ef79bd820aa26f60b12b9b7165980 で始まる。(2) その直後に `uv run --directory scripts/config-guard python ../../.cache/ISSUE-115-dod.py` を --skip-slow なしで実行した出力全文があり、全行が PASS で、最終行が「DOD: ALL PASS」。(3) メモリの裁定表 (D9 が列挙した全ファイルについて、ファイル名・裁定・理由) と、Jev の一次選別の結果および自分で読んで確かめた件数。(4) /simplify と feature-dev:code-reviewer の指摘ごとの対応と、PR の URL、`gh pr checks` で全ジョブが pass の出力。判定器を編集した、--skip-slow を付けた、いずれかの項目が欠けた場合は未達。30ターンで止める。
```

## 結果

- テスト: claude-hooks は307件から276件 (test_tirith_hook.py の26件と test_pretooluse.py を消し、性質を apm-install-guard の parametrize へ移した)。config-guard は431件のまま
- 変異注入: 畳んだ apm-install-guard の機構17件と config-guard の3件がすべて赤になり、apm-install-guard の配線を外すと config-guard scan が赤になった。レビュー後の書き直しでも9件を入れ直し、生き残りは0件だった。HEAD 版と書き直し版のフックへ同じ30入力を流し、stdout がバイト単位で一致した
- headless のスモーク: 撤去前は `printf | python3` の tool_result が Tirith の deny だった。撤去後は同じコマンドが成功した
- 監査ログ: `log.jsonl.archived-20261007` (+ `.head`) へ退避し、sha256 は退避前と一致した。新しい `log.jsonl` へ記録が再開し、`tirith audit verify` も通った
- Jev の一次選別: 対照4件は4件とも正解だった。残った63件は current 27 / unrelated 15 / stale 21 に分かれた。stale の21件は全部読み、直すものは無かった (Issue の背景にある当時のスナップショット、テストのフィクスチャ名、zsh 側にも当てはまる `tirith status` の記述)。Jev は過去形の記述やツール名の言及を stale に寄せる傾向がある
- メモリ: 2件削除 (tirith+mise の導入計画、confusable_text の回避規則)、6件修正、2件新規 (撤去の記録、filter-branch の手順)、残りは維持

## 関連

- ISSUE-116: agentic-coding-tools の skill に残る Tirith 前提の説明の追従
- Issue 26: フックの共通基盤を集約した側。`pretooluse.py` はそこで切り出したもので、今回畳む
- ISSUE-66: 偽バイナリを exec するテストの不安定さ。偽 tirith を使うテストは撤去で消える
- ISSUE-83: セッション頭のプローブの待ち時間。`probe_tirith` は撤去で消える
- ISSUE-56 / ISSUE-59 / ISSUE-62 / ISSUE-63: tirith フックに関する過去の Issue (closed)
