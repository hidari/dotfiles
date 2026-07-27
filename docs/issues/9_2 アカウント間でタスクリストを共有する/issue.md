---
status: in_progress
---

# feat: 2 アカウント間でタスクリストを共有する

## 背景

Issue #7 で 2 アカウント運用を導入したとき、`tasks/` の扱いを決めなかった。共有する
symlink にも、除外する「アカウント固有の状態」の列挙にも入っていない。結果として
各アカウントが自分の設定ディレクトリ配下に別々のリストを持ったままになっている。

タスクリストはアカウントではなくプロジェクトに紐づく作業成果物であり、どちらの
アカウントで作業しても同じリストを見たい。同じ ID を指定しても参照先が分かれる現状は
不便で、同じプロジェクトの進捗が 2 つに割れてしまう。

```
CLAUDE_CODE_TASK_LIST_ID=dotfiles claude               # ~/.claude/tasks/dotfiles
CLAUDE_CODE_TASK_LIST_ID=dotfiles claude-hamiltonian   # ~/.claude-hamiltonian/tasks/dotfiles
```

この 2 つが同じ実体を指すようにする。

## 共有してよいと判断した根拠

Issue #7 が除外した「アカウント固有の状態」は `.claude.json` / `projects/` /
`history.jsonl` / `sessions/` / `todos/` / `shell-snapshots/` / `statsig/` / `debug/` /
`backups/` / `plugins/` で、`tasks/` は含まれない。名前の似た `todos/` は TodoWrite が
セッション単位で持つ状態で、タスクリスト機能とは別物。

むしろ #7 は起動関数の設計時点で `CLAUDE_CODE_TASK_LIST_ID` の軸を「プロジェクト」と
記録している。アカウント軸だけを関数に持たせ、タスクリストは前置で渡す設計もそこから
来ている。共有は当時の判断と整合する。

実データも確認した。タスクファイルが持つフィールドは `blockedBy` / `blocks` /
`description` / `id` / `status` / `subject` のみで、メールアドレス・資格情報・セッション ID
といったアカウント固有の情報を含まない。また `tasks/<id>/` には `.lock` が置かれており、
Claude Code 側が同時アクセスを想定した作りになっている。

残るリスクは 2 アカウントを同時起動して同じリストを書いたときの競合だが、`.lock` の存在から
処理系が扱う前提と判断する。運用して問題が出たら再検討する。

## 実装方針

`~/.claude-hamiltonian/tasks` を `~/.claude/tasks` へ symlink する。参照先が 1 つになるため、
どちらのアカウントから起動しても同じリストを読み書きする。

この symlink はホーム内で完結し、リポジトリをソースに持たない。bootstrap の `SYMLINK_PAIRS` は
source を `$DOTFILES_DIR` 相対として解決するため表現できない。ホーム内リンク専用の配列を
別に用意する。

あわせて `claude()` のバグを直す。タスクリストの確認先を `$HOME/.claude` で決め打ちして
おり、外から `CLAUDE_CONFIG_DIR` が渡されていても個人側を見にいく。実測で確認済み。

```
A: CLAUDE_CODE_TASK_LIST_ID=dotfiles claude-hamiltonian
   -> 警告が出る (hamiltonian 側に当該リストが無いため)
B: CLAUDE_CODE_TASK_LIST_ID=dotfiles CLAUDE_CONFIG_DIR=<hamiltonian> claude
   -> 警告が出ない (個人側を見にいくため)
```

どちらも同じアカウントで起動するのに警告の有無が食い違う。タスクリスト共有後は両者が同じ
実体に解決されるため実害は消えるが、3 つ目のアカウントを足したときに再燃するので直す。
`CLAUDE_CONFIG_DIR` を設定しない方針は維持し、外から設定されていれば尊重する形にする。

尊重するなら検査も伴わなければならない。存在検査は `claude-hamiltonian()` にしか無く、
`CLAUDE_CONFIG_DIR=<typo> claude` は素通りして初期状態の設定ディレクトリを生やす。
解決と検査を `_claude_config_dir()` に閉じ、2 つのランチャを「解決 → 通知 → 起動」の
同形にする。アカウントを固定する側は引数でディレクトリを名指しし、外から渡された値に
引きずられないようにする。

## タスク

- [x] bootstrap にホーム内リンク用の配列を追加する
  - [x] source 側のディレクトリが無い場合に壊れた symlink を張らないこと
  - [x] 既存の `SYMLINK_PAIRS` の処理と混ざらないこと
- [x] `~/.claude-hamiltonian/tasks` を `~/.claude/tasks` へ向ける
- [x] `claude()` がタスクリストの確認先に `CLAUDE_CONFIG_DIR` を尊重するよう直す
- [x] 設定ディレクトリの解決と存在検査を `_claude_config_dir()` に閉じ、2 つのランチャを同形にする
- [x] テストを追加し、変異注入で赤くなることを確認する
- [x] 両アカウントで同じリストが見えることを live smoke で確認する

## 関連

- [Issue #7: feat: Claude Code の 2 アカウント運用で設定を共有する](../closed/7_Claude%20Code%20の%202%20アカウント運用で設定を共有する/issue.md)
  本 Issue は #7 が扱わなかった `tasks/` を埋める。#7 の除外リストにも共有リストにも
  現れないため、どちらの判断でもなかったことをここに記録する。
