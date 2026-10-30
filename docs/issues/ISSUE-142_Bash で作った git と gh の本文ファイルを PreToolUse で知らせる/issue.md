---
status: open
---

# feat(hooks): Bash で作った git と gh の本文ファイルを PreToolUse で知らせる

## 背景

2026-10-31に受け箱から仕分けた報告で起票した。別のリポジトリのセッションの報告で、報告の事象は dotfiles では再現していない。

- 日本語のコミット本文を Write ツールではなくシェルの `printf` でファイルに書く違反を、規約を把握したまま繰り返した。前のセッションに続いて2回目である (実測)
- 報告者の提案: 散文の規範だけでは止まらないので、git / gh に渡す本文ファイルを Bash の `printf` / `echo` / heredoc で作ることを、PreToolUse の hook で検出できないか検討する (推測)

規範の canonical は skill commit-and-pr-message (agentic-coding-tools) にあり、hook を置くなら dotfiles の `home/.claude/hooks` になる。Bash からのファイルへの書き出しが全部 git や gh の本文とは限らないので、誤検知の面を持つ。PreToolUse のフックには、Tirith のフックを撤去して誤検知率を測らずに再導入しないと決めた前例がある (ISSUE-115)。

dotfiles で確かめたこと (2026-10-31): `home/.claude/settings.json` の PreToolUse で Bash に配線されている hook は apm-install-guard の1本だけである。`home/.claude/hooks` 配下に、本文ファイルの書き方 (`-F` / `--body-file` と `printf` の組み合わせ) を見るものは無い。

## タスク

- [ ] 誤検知率を何で測るかを先に決める (どの transcript の Bash 呼び出しを母集団にし、何を正解とするか)
- [ ] 検出する形を決める。`printf` / `echo` / heredoc から書いたファイルが、同じコマンドか後続の `-F` / `--body-file` / `--notes-file` に渡る形をどこまで拾うか
- [ ] 知らせるだけにするか止めるかを、測った誤検知率で決める
- [ ] 入れるなら hook を実装し、変異注入で pin する

## 関連

- ISSUE-124: apm-install-guard の起動失敗の扱いと誤検知。同じ PreToolUse の Bash に載る hook の前例
- ISSUE-115 (closed): Tirith の PreToolUse フックを撤去した前例。誤検知率を測らずに再導入しないと決めた
- ISSUE-87: コミットのメタデータ面に検査が届かない。本文の検査の面の外にある件で、近いが対象は別
- Issue 26: Claude Code フックの共通基盤を集約する。hook を足すときの基盤
