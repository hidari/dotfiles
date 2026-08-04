---
status: open
---

# refactor: skill と plugin を新規 PUBLIC リポジトリへ集約し apm 配布へ移行する

本 Issue でも Issue #21 と同じく、private リポジトリ名と追加の設定ディレクトリ名は伏字にする。
ファイルパスと件数は公開情報なのでそのまま書く。

## 背景

skill と plugin の管理が 4 つの問題を同時に抱えている。いずれも置き場と配布方法に起因する。

### 1. 置き場が分かれていて基準がない

skill 12 個は dotfiles に、plugin 3 個は private リポジトリにある。どちらも「エージェントの
振る舞い」を表す成果物なのに公開範囲が違う。しかも PUBLIC 側の `settings.json` が private 側を
絶対パスで参照しているため、公開情報から private リポジトリの存在が推測できる。

### 2. 他者由来の skill を手でコピーしている

dotfiles の 12 skill のうち 7 個は他者由来だった。6 個は mizchi/skills とバイト単位で同一、
1 個は外部由来と本人確認済み。apm で入れた後に手でコピーしているため上流に追随しない。
`justfile/apm.yml` が `version: d799945` で固定されているのがその証拠で、CLAUDE.md が言う
「二重管理は CI が捕捉できない形で drift する」がそのまま起きている。

### 3. settings.json に絶対パスが入る

marketplace の directory source がローカルユーザー名を含む絶対パスになるため、他マシンへ配布
できず skip-worktree が必要になっている (Issue #8)。

### 4. 追加の設定ディレクトリ名がテストに露出している

追跡ファイル 8 件に計 77 件。うち 52 件はテストコードにある。テストが具体的な名前を
ハードコードしているため、その名前でしか動かないことを固定してもいる。Issue #21 の露出一覧は
この分類を持っていない。

## 方針

役割で分ける。dotfiles は「マシンの設定」、新規リポジトリ `agentic-coding-tools` は
「エージェント資産」。dotfiles は skill の実体を持たず、`apm.yml` で宣言だけを持つ。

新規リポジトリにするのは、現行 private リポジトリを公開に切り替えると private 前提の履歴も
すべて公開されるため。新規なら公開して問題ない状態だけを最初のコミットにできる。

配置は次のとおり。カテゴリー名は mizchi/skills の分類に合わせ、将来 skill が増えても同じ語彙で
探せるようにする。

```
agentic-coding-tools (PUBLIC, 新規)
├── README.md
├── .claude-plugin/marketplace.json   plugins/ のためだけに必要
├── skills/
│   ├── meta/session-handoff/
│   ├── tooling/herdr/
│   ├── tooling/markdown-to-pdf/
│   ├── tooling/chrome-devtools-debugger/
│   └── devops/windows-vm-verification/
└── plugins/
    ├── dev-workflow/
    ├── security-blue-red-team/
    └── web-monkey-qa/
```

追加の設定ディレクトリは追跡外のローカル設定ファイルから読む。公開されるのは「複数の設定
ディレクトリに対応する仕組みがある」ことだけで、数も名前も現れない。`CLAUDE_CONFIG_DIR` は
Claude Code の公式機能なので、対応していること自体は秘匿にならない。

設計の詳細は [25-spec.md](25-spec.md) にある。

## タスク

- [ ] GitHub 経由でカテゴリー階層の skill を取得できることを検証する (ローカルパスでは実測済み)
- [ ] ax の上流を特定する
- [ ] 新規 PUBLIC リポジトリを作成し、自作 skill 5 個と plugin 3 個を移設する
- [ ] README を SKILL.md の frontmatter から生成する仕組みと CI 検査を入れる
- [ ] dotfiles に `apm.yml` を追加し、他者由来 skill と自作 skill を依存として宣言する
- [ ] 追加の設定ディレクトリ一覧を追跡外ファイルへ外部化する
- [ ] テストからディレクトリ名のハードコードを除去し、任意の名前で動くことを検証する形にする
- [ ] `bootstrap.sh` の symlink ペアから skills を外し、`apm install -g` を呼ぶ形にする
- [ ] `settings.json` から marketplace の絶対パスと `enabledPlugins` の該当分を削除する
- [ ] `herdr-agent-state.sh` の hook パスを `$HOME` 参照へ変える
- [ ] skip-worktree を解除し、live と committed を 1 本にする
- [ ] 現行 private plugin リポジトリをアーカイブする

## 関連

- [Issue #8: refactor: settings.json の live 専用パスを変数化して skip-worktree を解消する](../8_settings.json%20の%20live%20専用パスを変数化して%20skip-worktree%20を解消する/issue.md)
  本 Issue の帰結として解ける。marketplace の絶対パスが消え、hook パスを `$HOME` 参照に変えれば
  skip-worktree の理由が両方なくなる
- [Issue #21: PUBLIC リポジトリに露出している個人情報と private リポジトリ情報を棚卸しする](../21_PUBLIC%20リポジトリに露出している個人情報と%20private%20リポジトリ情報を棚卸しする/issue.md)
  露出の除去は #21、構造の変更は本 Issue という分担。ただし #21 の露出一覧に
  「追加の設定ディレクトリ名 77 件」が漏れているため、#21 側への追記が必要
