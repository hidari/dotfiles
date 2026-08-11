---
status: in_progress
---

# refactor: skill と plugin を新規 PUBLIC リポジトリへ集約し apm 配布へ移行する

本 Issue でも Issue #21 と同じく、private リポジトリ名と追加の設定ディレクトリ名は伏字にする。
ファイルパスと件数は公開情報なのでそのまま書く。

## 背景

skill と plugin の管理が 4 つの問題を抱えている。いずれも置き場と公開範囲に起因する。

なお apm による skill 配布自体は既に稼働しており (`home/apm.yml` + `home/apm.lock.yaml` +
`bootstrap.sh` の `install_apm_packages`)、本 Issue は新規導入ではなく既存運用の再設計である。

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

起票時点で追跡ファイル 8 件に計 77 件 (`git grep -c` の一致行数)。うち 52 件はテストコード。
現在値は同じコマンドで数える (Phase 3a 以降にテストが増えており起票時点とは一致しない)。
テストが具体的な名前をハードコードしているため、その名前でしか動かないことを固定してもいる。
Issue #21 の露出一覧はこの分類を持っていない。

本体コードで名前を持つのは `bootstrap.sh` 5 件と `home/.zshrc` 2 件のみ。
`statusline-command.sh` は既に名前非依存に動いている。

## 方針

役割で分ける。dotfiles は「マシンの設定」、新規リポジトリ `agentic-coding-tools` は
「エージェント資産」。配布は動作実績のある project scope 機構
(`cd home && apm install --frozen` + committed lockfile + symlink) を維持し、
`home/.claude/skills/` は削除ではなく追跡停止に留める。

skill と plugin は別経路にしない。パッケージの root に `SKILL.md` と
`.claude-plugin/plugin.json` の両方を置くことで、apm の verbatim コピーと Claude Code の
plugin 認識が同時に成立する。marketplace の宣言も `settings.json` の plugin エントリも
不要になる。

新規リポジトリにするのは、現行 private リポジトリを公開に切り替えると private 前提の履歴も
すべて公開されるため。新規なら公開して問題ない状態だけを最初のコミットにできる。

追加の設定ディレクトリ一覧は追跡外のローカル設定ファイルから読む。ただし達成できるのは
「現ツリーに新規露出を足さない」ことまでで、履歴に残る分は消えない。

設計の詳細と実測の根拠は [25-spec.md](25-spec.md) にある。

## タスク

### Phase 1: 前提の確定

- [x] 外部由来 skill 1 個の上流を特定する (`ax` → `yusukebe/ax` の `skills/ax`)
- [x] 新リポジトリの形で GitHub 経由の取得が成ることを確認する

### Phase 2: 新規リポジトリの構築

- [x] plugin の公開基準を決める (安全性の 2 点のみ。3 個とも公開対象)
- [x] 初回コミット前の露出監査を行う (要対応は `plugin.json` の author のメールアドレスのみ)
- [x] 新リポジトリの検出網 (pre-commit + gitleaks + `claude plugin validate --strict`) を整備する
- [x] `agentic-coding-tools` を PUBLIC で作成し、自作 skill 5 個と plugin 3 個を移設する
- [x] 各パッケージの root に `SKILL.md` を足し、`plugin.json` の `name` を apm のパッケージ名と
      一致させ、`"skills": ["./skills"]` に直す
- [x] README を frontmatter から生成する仕組みと CI 検査を入れる
- [x] 決め打ちのインストールパス 17 箇所を変数参照へ直し、同じ形を弾く検査を足す

### Phase 3a: 供給経路の切り替えとガード

- [x] `home/apm.yml` に自作 skill と plugin と `ax` を追加し lockfile を更新する
- [x] `home/.claude/skills/` を追跡停止する (`.gitignore` 追加と `git rm -r --cached` は同一コミット)
- [x] apm 生成物を source とする symlink を `APM_SYMLINK_PAIRS` へ分離する
- [x] `apm install` のガードを `bootstrap.sh` と `PreToolUse` hook の 2 層で実装する

### Phase 3b: 設定ディレクトリの外部化

- [x] 設定ディレクトリ一覧の読み込みを `bootstrap.sh` と `home/.zshrc` へ入れる
- [x] stale symlink の撤去を `bootstrap.sh` に実装する
- [x] テストをパラメータ化し、任意の名前で動くことを検証する形にする

背景の 4 で予告した現在値を、同じ検索式のまま revision だけ変えて数え直した結果:
main の追跡ツリーは 8 ファイル 107 行、closed 配下を除くと 6 ファイル 90 行。Phase 3b 完了後は
closed 配下の 2 ファイル 17 行だけが残り、それを除くと 0 件になった。closed を対象外にするのは
過去の記録を後から書き換えないためで、履歴に残る分は消えないという当初の想定は変わらない。

### Phase 4: 後始末

- [x] skills-dir plugin の component が修飾名で解決されることを隔離環境で確認する
      (入口 gate。3 パッケージとも `enabled=true`。対照 2 本付き。実測は 25-spec.md)
- [x] Issue ドキュメントの記述を伏字化する
- [x] `settings.json` から marketplace 宣言と `enabledPlugins` を削除する
- [x] hook の `herdr-agent-state.sh` パスを `$HOME` 参照へ変える
- [x] skip-worktree を解除する
- [x] 現行 private plugin リポジトリをアーカイブする
- [x] `install.sh` が張った symlink 3 本と、旧経路の marketplace cache と registry のエントリを撤去する

アーカイブと symlink 撤去は、Claude Code を再起動して apm 版が実際に読まれることを追加の
設定ディレクトリ側で確認してから行った。確認前に撤去すると切り戻しの経路まで同時に失われる
ためこの順序にした。撤去後の既定の設定ディレクトリ側も後日確認済みである。

実測と、撤去範囲を計画より広げた理由は [25-spec.md](25-spec.md) の
「実環境での供給切り替えの実測 (Phase 4 の項目 22-23)」節と「既定の設定ディレクトリ側の実測」
節にある。

## 関連

- [Issue #8: refactor: settings.json の live 専用パスを変数化して skip-worktree を解消する](../closed/8_settings.json%20の%20live%20専用パスを変数化して%20skip-worktree%20を解消する/issue.md)
  本 Issue の帰結として解ける。marketplace の絶対パスが消え、hook パスを `$HOME` 参照に変えれば
  skip-worktree の理由が両方なくなる
- [Issue #21: PUBLIC リポジトリに露出している個人情報と private リポジトリ情報を棚卸しする](../21_PUBLIC%20リポジトリに露出している個人情報と%20private%20リポジトリ情報を棚卸しする/issue.md)
  露出の除去は #21、構造の変更は本 Issue という分担。ただし #21 の露出一覧に
  「追加の設定ディレクトリ名の露出」が漏れているため、#21 側への追記が必要
- [Issue #26: refactor: Claude Code フックの共通基盤を集約する](../26_Claude%20Code%20フックの共通基盤を集約する/issue.md)
  Phase 3a のレビューで検出したフック周りの重複。本 Issue のスコープを超えるため分けた
- [Issue #29: refactor: PUBLIC リポジトリに残る private リポジトリ名の露出を棚卸しする](../29_PUBLIC%20リポジトリに残る%20private%20リポジトリ名の露出を棚卸しする/issue.md)
  Phase 4 のゲートが検出。本 Issue の露出の棚卸しは追加の設定ディレクトリ名しか数えておらず、
  private リポジトリ名の現ツリー露出が抜けていた
- [Issue #30: feat: Markdown 内のシェルスニペットを構文検査する](../30_Markdown%20内のシェルスニペットを構文検査する/issue.md)
  Phase 4 の伏字化で実際にスニペットを壊した。既存の検査はどれも Markdown 内のコードブロックを
  見ておらず、検出はゲートの目視に依存していた
- [Issue #31: docs: spec が参照する bootstrap.sh の関数名と行番号を実体に合わせる](../31_spec%20が参照する%20bootstrap.sh%20の関数名と行番号を実体に合わせる/issue.md)
  Phase 4 のゲートが検出。25-spec.md 自身が持つ rot
