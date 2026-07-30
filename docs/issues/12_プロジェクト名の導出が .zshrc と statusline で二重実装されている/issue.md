---
status: open
---

# refactor: プロジェクト名の導出が .zshrc と statusline で二重実装されている

## 背景

「git リポジトリルートの basename をプロジェクト名とする」という規則が 2 箇所に独立して書かれている。

- `home/.zshrc` の `_claude_task_list_id()` — タスクリスト ID を導出する
- `home/.claude/statusline-command.sh` — statusline に出すプロジェクト名を導出する

同じ規則を 2 箇所で持っているため、片方だけ変えると同じディレクトリにいるのに statusline とタスクリストで違う名前が出る。worktree 対応のように導出規則を変える判断をしたとき、2 箇所に適用し忘れると静かに食い違う。

既に差もある。statusline 側は `--no-optional-locks` を付けているが `.zshrc` 側は付けていない。

単純な関数抽出では届かない。`.zshrc` は対話 zsh に source され、`statusline-command.sh` は Claude Code から独立したサブプロセスとして起動されるので、共有するなら両者が読み込める shell lib を新設することになる。それ自体が設計判断を要するため、重複を許容して両方に相互参照のコメントを置くという選択肢もある。

## タスク

- [ ] 共有 shell lib を作るか、重複を許容して相互参照のコメントを置くかを決める
- [ ] `--no-optional-locks` の有無をどちらかに揃える
- [ ] 決めた方針で実装する

## 関連

[Issue #10: タスクリスト ID を作業ディレクトリから自動導出する](../closed/10_タスクリスト%20ID%20を作業ディレクトリから自動導出する/issue.md) のマージ前レビューで検出し、スコープ外として別タスクとした。
