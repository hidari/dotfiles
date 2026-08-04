# spec: skill と plugin を新規 PUBLIC リポジトリへ集約し apm 配布へ移行する

Issue #25 の設計。private リポジトリ名と追加の設定ディレクトリ名は伏字にする。

## 目的

dotfiles を PUBLIC に保ったまま、秘匿情報を構造的に分離する。動機は「自分のやり方を誰でも
参考にできる状態にしておくこと」であり、参照されるかどうかは問わない。したがって stars や
forks のような実績値は判断材料にしない。

## 現状

前提を取り違えないよう、まず既にあるものを書く。

### apm による skill 配布は既に稼働している

```
home/apm.yml         追跡済み。name: dotfiles-skills
home/apm.lock.yaml   追跡済み
bootstrap.sh:330     install_apm_skills() { ( cd "$DOTFILES_DIR/home" && apm install --frozen ) }
```

`home/apm.yml` は mizchi/skills の 6 skill をコミットハッシュ `d7999453` で pin している。
lockfile には `virtual_path: tooling/apm-usage` のようにカテゴリー階層の解決結果が記録されて
おり、GitHub 経由でのカテゴリー階層取得は既に動作実績がある。

したがって本 Issue は「apm の新規導入」ではなく「既存の apm 運用の再設計」である。

### 配布されている skill の内訳

| 分類 | 件数 | 配布経路 |
|---|---|---|
| mizchi/skills 由来 | 6 | apm で vendored。`d7999453` で pin されているため上流に追随しない |
| 外部由来 (上流未特定) | 1 | 手動管理 |
| 自作 | 5 | 手動管理 |
| plugin (現行 private リポジトリ) | 3 | `settings.json` の directory marketplace 経由 |

自作 5 個は chrome-devtools-debugger / herdr / markdown-to-pdf / session-handoff /
windows-vm-verification。

### 追加の設定ディレクトリ名の露出

| 場所 | 件数 |
|---|---|
| `scripts/tests/zshrc-claude.bats` | 35 |
| `scripts/tests/statusline.bats` | 11 |
| `scripts/tests/bootstrap.bats` | 6 |
| `bootstrap.sh` | 5 |
| `home/.zshrc` | 2 |
| Issue ドキュメント 3 件 | 18 |

計測は `git grep -c` (一致行数) による。出現数を数える `git grep -o` では 80 になる。

本体コードで名前を持つのは `bootstrap.sh` と `home/.zshrc` の 2 ファイル 7 件のみ。
`statusline-command.sh` は `${CLAUDE_CONFIG_DIR:-$HOME/.claude}` で既に名前非依存に動いており、
露出は `statusline.bats` のフィクスチャ側だけである。

closed 配下の Issue 2 件はディレクトリ名自体に運用形態が現れている。

## 実測した事実

apm 0.27.0 で確認した。隔離した HOME 配下で実行し、実環境は変更していない。

### plugin は agents / commands / skills へ展開されるが、schemas は展開されない

plugin 1 個を install した結果、`.claude/agents/` 2 件、`.claude/commands/` 4 件、
`.claude/skills/` 3 件が配置された。一方 `schemas/` 4 件は `apm_modules/` の下にしか置かれず、
`.claude/plugins/` は作られない。

これは機能破壊になる。plugin の skill 本文が
`~/.claude/plugins/<plugin>/schemas/<name>.schema.yml` という Claude Code ネイティブの plugin
配置を名指ししているため (4 skill、計 7 箇所)、apm 配布に切り替えるとこのパスが存在しなくなる。
「plugin は配置後に素の primitive になる」は agents / commands / skills に限った話で、
共有アセットには成り立たない。

### `-g` は cwd の manifest を読まない

`apm.yml` のあるディレクトリで `apm install -g` を実行しても
`[x] No <HOME>/.apm/apm.yml found` で中断した。user scope の manifest と lockfile は
`~/.apm/` にあり、追跡外のマシンローカルな置き場である。

さらに `--frozen` は positional packages と排他なので、`~/.apm/apm.yml` を auto-create する
経路 (`apm install -g <pkg>`) と `--frozen` を同時には使えない。

したがって「dotfiles の `apm.yml` と lockfile をコミットして再現性を担保する」設計は
`-g` では成立しない。project scope (現行機構) でのみ成立する。

### apm は CLAUDE_CONFIG_DIR を参照する。失敗条件は symlink 先の位置

条件を 1 つずつ変えて切り分けた。

| 条件 | 結果 |
|---|---|
| `CLAUDE_CONFIG_DIR` 未設定 | `~/.claude/skills/` へ配置。成功 |
| `CLAUDE_CONFIG_DIR` = 実ディレクトリ | そのディレクトリの `skills/` へ配置。成功 |
| `CLAUDE_CONFIG_DIR` の `skills` が symlink、リンク先が HOME 内 | symlink を辿って配置。成功 |
| `CLAUDE_CONFIG_DIR` の `skills` が symlink、リンク先が HOME 外 | 失敗 |

実環境は `HOME=/Users/<user>` で symlink 先が `~/Develop/dotfiles/...` なので HOME の内側に
収まり、失敗条件には該当しない。

この切り分けを行う前は「symlink だと失敗する」と読めていた。隔離が足りない状態
(`CLAUDE_CONFIG_DIR` に実環境の値が残る) と隔離が効きすぎる状態 (fake HOME にしたため symlink
先が HOME 外へ出る) が重なると、実環境では起きない失敗が再現する。隔離環境で実環境の再現を
主張するには、環境変数だけでなくパスの相対関係まで写す必要がある。

### marketplace の source は絶対 URL で保存される

`apm marketplace list` の表示はチルダだが、`~/.apm/marketplaces.json` には `file:///` の絶対
URL で保存される。ローカルユーザー名が入らないのは「コミットされるファイル」に限った話で、
追跡外の設定には入る。

## 設計

### 方針: 現行機構を維持する

動作実績のある project scope 機構をそのまま使う。

```
bootstrap.sh    ( cd "$DOTFILES_DIR/home" && apm install --frozen )
                → home/.claude/skills/ へ配置
                → 既存の symlink 2 本が ~/.claude/skills と追加の設定ディレクトリへ供給
```

`-g` へ乗り換えない理由は前節のとおりで、コミットした manifest と lockfile が読まれなくなる。

`home/.claude/skills/` は削除せず、`.gitignore` への追加と `git rm -r --cached` で追跡だけを
止める。実体は apm が配置し、symlink の供給網は現状のまま生きる。

### リポジトリ構成

```
agentic-coding-tools (PUBLIC, 新規)
├── README.md                        skill 一覧と install 例 (frontmatter から生成)
├── .claude-plugin/marketplace.json  plugins/ のためだけに必要
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

dotfiles (PUBLIC, 継続)
├── home/apm.yml       他者由来 + 自作の skill を宣言 (既存ファイルの書き換え)
├── home/apm.lock.yaml pin を更新
└── home/.claude/skills/  追跡停止。実体は apm が配置
```

境界は「マシンに固有か、エージェントの振る舞いか」。`hooks/` と `statusline-command.sh` は
Claude Code の設定でありエージェント資産ではないため dotfiles に残す。

新規リポジトリにするのは、現行 private リポジトリを公開に切り替えると private 前提の履歴も
すべて公開されるため。新規なら公開して問題ない状態だけを最初のコミットにできる。

### plugin の配布経路

schemas が展開されない問題があるため、2 案のいずれかを選ぶ。実装前に決める。

- 案 A: plugin だけは新 PUBLIC リポジトリを marketplace として Claude Code に登録し、
  `claude plugin install` 経路を維持する。schema 参照は現状のまま動く。ただし
  `settings.json` に marketplace の宣言が残る (絶対パスではなく GitHub source になるので
  秘匿情報は入らない)
- 案 B: skill 本文の schema 参照をレイアウト非依存に書き換え (skill 同梱の相対参照へ寄せる)、
  plugin も apm で配る

案 A のほうが変更が小さく、機能破壊のリスクがない。案 B は配布経路が 1 本化するが、
4 skill 7 箇所の書き換えと、書き換え後に実際に schema を読めることの確認が要る。

### namespace の消失

apm が展開すると `dev-workflow:git-branch-switcher` のような plugin 修飾名は消え、
素の `git-branch-switcher` になる。以下が修飾名を名指ししているため、案 B を採る場合は
一括更新が要る。

- global CLAUDE.md の作業プロトコル (MUST)
- project CLAUDE.md
- skill 間の相互参照 (pre-merge-quality-gate から e2e-scenario-impact-check 等)

案 A ならこの問題は起きない。

### アカウント運用の外部化

追加の設定ディレクトリ一覧を追跡外のローカル設定ファイルから読む。

```
${HOME}/.config/dotfiles/claude-config-dirs
```

- 1 行 1 ディレクトリ名。ファイルが無ければ `~/.claude` のみを対象にする
- 読者は `bootstrap.sh` と `home/.zshrc` の 2 つ。`statusline-command.sh` は既に名前非依存
  なので変更しない
- 増えたら行を足すだけで、リポジトリ側の変更は要らない

### 秘匿性の主張の範囲

達成できるのは「現ツリーに新規露出を足さない」ことまでである。git 履歴には 77 件が残り続け、
closed 配下の Issue 2 件はディレクトリ名自体に運用形態が出る。リネームしても履歴には残る。
Issue #21 自身が「履歴を書き換えれば消える前提を置くな」と警告している。

回帰検査には自己言及の罠がある。追跡される `.gitleaks.toml` にディレクトリ名の literal を
書いた瞬間、それ自体が名前をツリーへ戻す。検査は名前 literal を含まない形にする
(追跡外の `claude-config-dirs` から pattern を読む pre-commit 検査、または汎用形 + allowlist)。

## 移行手順

### Phase 1: 前提の確定

1. plugin の配布経路を案 A / 案 B から選ぶ
2. 外部由来 skill 1 個の上流を特定する
3. 新リポジトリの形 (marketplace.json と skills/ の同居) で GitHub 経由の取得が成ることを確認する

カテゴリー階層自体の検証は不要 (現行 lockfile に動作実績がある)。

### Phase 2: 新規リポジトリの構築

入口 gate として先に次を行う。公開は不可逆で、repo 削除ではクローンやキャッシュを巻き戻せない。

4. plugin の公開基準を決める。基準を満たさないものは初回コミットに含めない
5. 初回コミット前の露出監査を行う (`gitleaks dir` 走査、私物パスと実プロジェクト名の scrub、
   plugin.json の author に個人情報が入っていないかの確認)
6. 新リポジトリ自身の検出網 (pre-commit + gitleaks) を整備する

その上で構築する。

7. `agentic-coding-tools` を PUBLIC で作成する
8. 自作 skill 5 個を移設する (dotfiles からは削除しない。Phase 3 まで並行稼働)
9. plugin 3 個を移設する
10. README 自動生成と CI 検査を入れる

### Phase 3: dotfiles 側の切り替え

このフェーズは分割しない。skill の供給が途切れる窓を作らないため、追跡停止と設定ファイル駆動の
導入を同一フェーズで行う。

11. `home/apm.yml` に自作 skill 5 個を追加し、lockfile を更新する
12. 追加の設定ディレクトリ一覧の読み込みを `bootstrap.sh` と `home/.zshrc` へ入れる
13. stale symlink の撤去を `bootstrap.sh` に実装する (配列から消したペアの残骸は現状消えない)
14. `home/.claude/skills/` を `.gitignore` へ追加し `git rm -r --cached` する
15. テストをパラメータ化し、任意のディレクトリ名で動くことを検証する形にする

### Phase 4: 後始末

16. Issue ドキュメントの記述を伏字化する
17. 案 A なら `settings.json` の marketplace を GitHub source へ差し替え、案 B なら削除する
18. `enabledPlugins` を経路に合わせて整理する
19. hook の `herdr-agent-state.sh` パスを `$HOME` 参照へ変える
20. skip-worktree を解除し、live と committed を 1 本にする
21. 案 B を選んだ場合、修飾名の参照を一括更新する
22. 現行 private plugin リポジトリをアーカイブする

## テスト戦略

### アカウント外部化のテスト

現状のテストは具体的なディレクトリ名をハードコードしており、その名前でしか動かないことを
固定している。パラメータ化して次を検証する。

- 設定ファイルが無いとき `~/.claude` のみを対象にする
- 設定ファイルに 1 行あるとき、その名前のディレクトリへ symlink が張られる
- 設定ファイルに複数行あるとき、すべてに張られる
- 設定ファイルが空のとき `~/.claude` のみを対象にする (境界)

各テストは変異注入で pin が生きていることを確認する。特に「設定ファイルが無いときの
フォールバック」は、壊しても既定値が偶然一致して緑のままになりやすいので、フォールバック先を
別の名前へ変えて赤くなることを見る。

### 移行経路のテスト

新規 clone からの live smoke だけでは不十分である。一番壊れやすいのは移行前の状態が残った実機で、
そこを新規 clone のテストは原理的に踏めない。次を追加する。

- 旧 symlink が残存した状態から `bootstrap.sh` を再実行し、stale symlink が撤去されること
- 追跡停止後に `home/.claude/skills/` が空の状態から `apm install --frozen` で復元されること

### 機能のテスト

live smoke の合格条件を「skill が配置される」ではなく「代表 skill が実際に機能する」まで
引き上げる。特に案 B を選ぶ場合、schema を読む skill が schema を見つけられることを確認する。
配置の有無しか見ないテストでは schema 参照切れを検出できない。

### 露出の回帰検査

移行後に追加の設定ディレクトリ名が追跡ファイルへ再び入らないことを pin する。検査自体が名前を
ツリーへ戻さない形にする (前節参照)。Issue #21 の「検出網の穴を塞ぐ」と実装を揃える。

### 供給網のレビュー面

他者由来 skill の実体をコミットしなくなると、上流変更のレビューが PR の内容 diff から lockfile
の hash diff に縮む。skill はエージェントへの指示文なので、内容レビュー無しの追随は
プロンプトインジェクション面の後退になる。`apm audit` (hidden Unicode / drift 検査) を
bootstrap か CI に組み込む。

## 未確認事項とリスク

| 項目 | 内容 | 対処 |
|---|---|---|
| plugin の配布経路 | 案 A / 案 B の選択が未確定 | Phase 1 で決める。案 A が変更小 |
| 外部由来 skill の上流 | 出所が未特定 | Phase 1 で特定。不明なら依存宣言から外し手動管理を継続 |
| 新リポジトリ形での GitHub 取得 | marketplace.json と skills/ の同居はローカルで確認済み、リモートは未確認 | Phase 1 step 3 で検証 |
| `--dry-run` の副作用 | `~/.apm/apm.yml` を実際に作る経路がある | dry-run の結果を無害と仮定しない。実行後に差分を確認する |
| plugin の品質 | 公開に耐えないという判断が移行の動機の一部 | Phase 2 の入口 gate で基準を決める。公開は不可逆なので後追いできない |
| 履歴に残る露出 | 現ツリーを直しても履歴の 77 件は残る | 主張を「新規露出を足さない」に限定する。履歴書き換えの是非は Issue #21 で扱う |

## 却下した案

### `apm install -g` への乗り換え

`-g` は cwd の manifest を読まないため、コミットした `apm.yml` と lockfile が使われない。
再現性の担保という目的そのものが達成できない。

### 現行 private リポジトリを PUBLIC 化して集約する

private 前提の履歴がすべて公開される。新規リポジトリなら公開して問題ない状態だけを最初の
コミットにできる。

### dotfiles にすべて吸収する

clone 1 回で完結し移行も最小だが、マシン設定とエージェント資産が混ざる。

### plugin を解体してすべて skill 化する

単位が 1 つになり使い分けの迷いは消えるが、agent と command を失う。apm が配布時に展開する
ことが実測で分かったため、オーサリング側で解体する理由がない。

### 他者由来の skill も新リポジトリへ移す

上流に追随できなくなる。apm の依存として宣言し、pin を更新する形で追随させる。

### `statusline-command.sh` を設定ファイルの読者に加える

既に `${CLAUDE_CONFIG_DIR:-$HOME/.claude}` で名前非依存に動いており、本体に名前は 1 件も
現れない。露出はテストのフィクスチャだけなので、テストのダミー名化で足りる。
