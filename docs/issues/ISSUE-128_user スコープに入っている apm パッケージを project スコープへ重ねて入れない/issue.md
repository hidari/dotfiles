---
status: open
---

# fix: user スコープに入っている apm パッケージを project スコープへ重ねて入れない

## 背景

2026-10-20 に他リポジトリのセッションから届いた報告。security-audit skill を試用するとき、dotfiles の apm で user スコープへ入っている同じコミットを、そのリポジトリの project スコープへも apm install した。入れる前に user スコープを確かめなかった。報告元では取り下げてある (ISSUE-114 の「full audit の試用記録」節と同じ試用)。

報告者の提案は、apm install の前に user スコープの lock (`home/apm.lock.yaml`) に同じ `repo_url` があるかを確かめる検査を置くこと。

既存の `home/.claude/hooks/apm-install-guard.py` と `scripts/apm-guard/` の shim は、ツリーが汚れているときに apm の書き込みを止めるもので、重ねて入れることは見ていない。

重ねて入れたときに何が起きるかは確かめていない (同じ skill が2回載るのか、どちらかが優先されるのか)。

## タスク

- [ ] 同じパッケージを user と project の両スコープへ入れたとき、Claude Code に何が載るかを確かめる。実害が無ければこの Issue は閉じる
- [ ] 実害があるなら、検査を置く場所を決める (apm-install-guard、shim、apm.yml を編集したときの告知のどれか)。user スコープの lock は dotfiles の作業ツリーにあるので、他リポジトリから読む経路も決める

## 関連

- ISSUE-114: 報告元の試用
- ISSUE-124: apm-install-guard の起動失敗の扱い。検査を同じ hook に足すなら一緒に効く
