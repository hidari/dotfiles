---
status: open
---

# refactor: skill と plugin を新規 PUBLIC リポジトリへ集約し apm 配布へ移行する

本 Issue でも Issue #21 と同じく、private リポジトリ名と追加の設定ディレクトリ名は伏字にする。
ファイルパスと件数は公開情報なのでそのまま書く。

## 背景

skill と plugin の管理が 4 つの問題を抱えている。いずれも置き場と公開範囲に起因する。

なお apm による skill 配布自体は既に稼働しており (`home/apm.yml` + `home/apm.lock.yaml` +
`bootstrap.sh` の `install_apm_skills`)、本 Issue は新規導入ではなく既存運用の再設計である。

### 1. 置き場が分かれていて基準がない

skill 12 個は dotfiles に、plugin 3 個は private リポジトリにある。どちらも「エージェントの
振る舞い」を表す成果物なのに公開範囲が違う。live の `settings.json` が private 側を絶対パスで
参照しているため、他マシンへ配布できず skip-worktree が必要になっている (Issue #8)。

committed 版の `settings.json` は全履歴を通じてクリーンなので、公開情報からの推測経路は
この参照ではなく、切り出し時の削除コミットのメッセージ等である (Issue #21 の露出 1)。

### 2. 他者由来の skill が pin で固定されている

dotfiles の 12 skill のうち 7 個は他者由来。うち 6 個は apm 管理下で vendored されているが、
コミットハッシュで pin されているため上流に追随しない。残り 1 個は上流未特定の手動管理。

### 3. plugin の配布経路が private リポジトリに依存している

`settings.json` の directory marketplace 経由なので、参照先が private である限り公開側から
切り離せない。private にしている理由は品質であって秘匿ではない。

### 4. 追加の設定ディレクトリ名がテストに露出している

追跡ファイル 8 件に計 77 件 (`git grep -c` の一致行数)。うち 52 件はテストコード。
テストが具体的な名前をハードコードしているため、その名前でしか動かないことを固定してもいる。
Issue #21 の露出一覧はこの分類を持っていない。

本体コードで名前を持つのは `bootstrap.sh` 5 件と `home/.zshrc` 2 件のみ。
`statusline-command.sh` は既に名前非依存に動いている。

## 方針

役割で分ける。dotfiles は「マシンの設定」、新規リポジトリ `agentic-coding-tools` は
「エージェント資産」。配布は動作実績のある project scope 機構
(`cd home && apm install --frozen` + committed lockfile + symlink) を維持し、
`home/.claude/skills/` は削除ではなく追跡停止に留める。

新規リポジトリにするのは、現行 private リポジトリを公開に切り替えると private 前提の履歴も
すべて公開されるため。新規なら公開して問題ない状態だけを最初のコミットにできる。

追加の設定ディレクトリ一覧は追跡外のローカル設定ファイルから読む。ただし達成できるのは
「現ツリーに新規露出を足さない」ことまでで、履歴に残る分は消えない。

設計の詳細と実測の根拠は [25-spec.md](25-spec.md) にある。

## タスク

### Phase 1: 前提の確定

- [ ] plugin の配布経路を決める (marketplace 経由を維持するか、schema 参照を書き換えて apm 化するか)
- [ ] 外部由来 skill 1 個の上流を特定する
- [ ] 新リポジトリの形で GitHub 経由の取得が成ることを確認する

### Phase 2: 新規リポジトリの構築

- [ ] plugin の公開基準を決める (公開は不可逆なので構築前に行う)
- [ ] 初回コミット前の露出監査を行う
- [ ] 新リポジトリの検出網 (pre-commit + gitleaks) を整備する
- [ ] `agentic-coding-tools` を PUBLIC で作成し、自作 skill 5 個と plugin 3 個を移設する
- [ ] README を frontmatter から生成する仕組みと CI 検査を入れる

### Phase 3: dotfiles 側の切り替え

- [ ] `home/apm.yml` に自作 skill を追加し lockfile を更新する
- [ ] 設定ディレクトリ一覧の読み込みを `bootstrap.sh` と `home/.zshrc` へ入れる
- [ ] stale symlink の撤去を `bootstrap.sh` に実装する
- [ ] `home/.claude/skills/` を追跡停止する
- [ ] テストをパラメータ化し、任意の名前で動くことを検証する形にする

### Phase 4: 後始末

- [ ] Issue ドキュメントの記述を伏字化する
- [ ] `settings.json` の marketplace と `enabledPlugins` を経路に合わせて整理する
- [ ] hook の `herdr-agent-state.sh` パスを `$HOME` 参照へ変える
- [ ] skip-worktree を解除する
- [ ] 現行 private plugin リポジトリをアーカイブする

## 関連

- [Issue #8: refactor: settings.json の live 専用パスを変数化して skip-worktree を解消する](../8_settings.json%20の%20live%20専用パスを変数化して%20skip-worktree%20を解消する/issue.md)
  本 Issue の帰結として解ける。marketplace の絶対パスが消え、hook パスを `$HOME` 参照に変えれば
  skip-worktree の理由が両方なくなる
- [Issue #21: PUBLIC リポジトリに露出している個人情報と private リポジトリ情報を棚卸しする](../21_PUBLIC%20リポジトリに露出している個人情報と%20private%20リポジトリ情報を棚卸しする/issue.md)
  露出の除去は #21、構造の変更は本 Issue という分担。ただし #21 の露出一覧に
  「追加の設定ディレクトリ名 77 件」が漏れているため、#21 側への追記が必要
