---
status: open
---

# chore(git): settings.local.json をグローバルの gitignore で無視するか決める

## 背景

2026-10-31に受け箱から仕分けた報告で起票した。他のリポジトリのセッションの報告で、報告の事象は dotfiles では再現していない。

- `.claude/settings.local.json` は、そのリポジトリの `.gitignore` に無いと untracked として `git status` に出る。報告者の提案: テンプレートから配置するなら、ignore も同時に足す (実測)

リポジトリごとに足す形だと、配置のたびに足し忘れる面が残る。全リポジトリに効くグローバルの gitignore で無視すれば一度で済むが、リポジトリの `.gitignore` だけを読む人や CI からは見えなくなる。

dotfiles で確かめたこと (2026-10-31): dotfiles のリポジトリの `.gitignore` は23行目に `**/.claude/settings.local.json` を持つ。グローバルの gitignore (`core.excludesfile` が指す `~/.config/git/.gitignore_global`、15行) には `settings.local` を含む行が無い。Issue 42 の spec は、28のリポジトリで `.claude/settings.local.json` の追跡が0件 (untracked 19 / absent 9) だったと記録している。この untracked は ignore されているものと区別していないので、`git status` に出ているリポジトリの数はまだ数えていない。

## タスク

- [ ] `.claude/settings.local.json` をグローバルの gitignore で無視するか、リポジトリごとの `.gitignore` に任せるかを決める
- [ ] グローバルで無視するなら、リポジトリごとの `.gitignore` に既にある行を残すか消すかを決める
- [ ] テンプレートから `settings.local.json` を配置する手順があるなら、決めた形に合わせて直す

## 関連

- Issue 42 (closed): リポジトリ固有の運用指示を外部ストレージから注入する仕組みを固める。各リポジトリの `.claude/settings.local.json` が追跡外であることを扱った
