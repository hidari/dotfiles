# spec: skill と plugin を新規 PUBLIC リポジトリへ集約し apm 配布へ移行する

Issue #25 の設計。private リポジトリ名と追加の設定ディレクトリ名は伏字にする。

## 目的

dotfiles を PUBLIC に保ったまま、秘匿情報を構造的に分離する。動機は「自分のやり方を誰でも
参考にできる状態にしておくこと」であり、参照されるかどうかは問わない。したがって stars や
forks のような実績値は判断材料にしない。

## 実測した事実

設計の前提はすべて実測で確認した。以下は再検証できるよう手順ごと記録する。

### apm は plugin を配布し、ネイティブ配置先へ展開する

apm 0.27.0 で `apm install <plugin>@<marketplace> --root <dir> --target claude` を実行した結果、
plugin 1 個が次のように展開された。

```
.claude/agents/{2 ファイル}
.claude/commands/{4 ファイル}
.claude/skills/{3 ディレクトリ}
```

plugin はバンドルの単位であり、配置後は素の agent / command / skill になる。したがって
「plugin を解体して skill 化する」必要はない。オーサリングは plugin 単位のまま、配布時に
apm が解体する。

### カテゴリー階層は配置時にフラットへ畳まれる

`skills/testing/probe-skill-a/SKILL.md` を用意して install したところ
`.claude/skills/probe-skill-a/` へ配置された。カテゴリーはリポジトリ内の整理のためだけに
存在し、skill 名の一意性さえ保てば任意の階層を切れる。

### marketplace.json と skills/ は同居できる

`.claude-plugin/marketplace.json` と `skills/` を持つリポジトリを marketplace として登録し、
plugin が認識されることを確認した。skill だけを配るなら manifest は不要で、apm はリポジトリ内の
パスを直接指定して取得する (mizchi/skills がこの形で運用されている)。

### apm は source をチルダ表記で保存する

`apm marketplace list` の Source 欄が `~/Develop/...` と表示された。Claude Code の
`claude plugin marketplace add` が絶対パスへ正規化するのと対照的で、ローカルユーザー名が
設定へ入らない。

### dotfiles の skill 12 個のうち 7 個は他者由来

mizchi/skills の同名 skill と `SKILL.md` を突き合わせ、6 個がバイト単位で同一と確認した
(apm-usage / ast-grep-practice / empirical-prompt-tuning / justfile / playwright-cli /
playwright-test)。残り 1 個 (ax) は本人確認で外部由来と判明。

自作は 5 個 (chrome-devtools-debugger / herdr / markdown-to-pdf / session-handoff /
windows-vm-verification)。いずれも専用コミットで追加され、内容が dotfiles 固有である。

### 追加の設定ディレクトリ名は追跡ファイル 8 件に 77 件

内訳はテストコード 52 件、`bootstrap.sh` 5 件、`.zshrc` 2 件、Issue ドキュメント 18 件。
加えて closed 配下の Issue 2 件はディレクトリ名自体に運用形態が現れている。

## 設計

### リポジトリ構成

```
agentic-coding-tools (PUBLIC, 新規)
├── README.md                        skill 一覧と install 例 (自動生成)
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
├── home/{.zshrc, .gitconfig, .Brewfile, .config/*}
├── home/.claude/{settings.json, CLAUDE.md, hooks/, statusline-command.sh}
├── scripts/, bootstrap.sh
└── apm.yml                          依存の宣言のみ。skill の実体は持たない
```

境界は「マシンに固有か、エージェントの振る舞いか」。`hooks/` と `statusline-command.sh` は
Claude Code の設定でありエージェント資産ではないため dotfiles に残す。

カテゴリー名は mizchi/skills の分類 (meta / tooling / devops / testing / ai ほか) に合わせる。
`windows-vm-verification` を devops に置くのは、VM という検証環境そのものの運用だから。
`herdr` は特定ツールの操作方法なので tooling に寄せる。

### 配布経路

dotfiles の `apm.yml` が依存を宣言し、実体は apm が配置する。

```yaml
name: hidari-dotfiles
version: 1.0.0
targets:
  - claude
dependencies:
  apm:
    # 他者由来。上流に追随する
    - mizchi/skills/tooling/apm-usage
    - mizchi/skills/tooling/ast-grep-practice
    - mizchi/skills/tooling/justfile
    - mizchi/skills/meta/empirical-prompt-tuning
    - mizchi/skills/testing/playwright-cli
    - mizchi/skills/testing/playwright-test
    # 自作
    - hidari/agentic-coding-tools/skills/meta/session-handoff
    - hidari/agentic-coding-tools/skills/tooling/herdr
    - hidari/agentic-coding-tools/skills/tooling/markdown-to-pdf
    - hidari/agentic-coding-tools/skills/tooling/chrome-devtools-debugger
    - hidari/agentic-coding-tools/skills/devops/windows-vm-verification
```

`ax` の上流は未特定なので、確定してから追記する。

lockfile (`apm.lock.yaml`) はコミットする。新しいマシンで同じバージョンが入ることを保証し、
`apm install --frozen` で drift を検出できる。

### アカウント運用の外部化

追加の設定ディレクトリ一覧を追跡外のローカル設定ファイルから読む。

```
${HOME}/.config/dotfiles/claude-config-dirs
```

- 1 行 1 ディレクトリ名。ファイルが無ければ `~/.claude` のみを対象にする
- `bootstrap.sh` / `.zshrc` / `statusline-command.sh` が同じファイルを読む
- 増えたら行を足すだけで、リポジトリ側の変更は要らない

skill の配布は apm の挙動に依存させない。

```
apm install -g   →  ~/.claude/skills/ へ配置
bootstrap.sh     →  追加の設定ディレクトリへ symlink を張る (現行機構をそのまま使う)
```

apm が `CLAUDE_CONFIG_DIR` を参照するかは未実測だが、この形なら apm の挙動に関係なく成立する。

### settings.json の変化

| 項目 | 現在 | 変更後 |
|---|---|---|
| `extraKnownMarketplaces` の該当エントリ | ローカルユーザー名を含む絶対パス | 削除。apm の marketplace が持つ |
| `enabledPlugins` の該当 3 件 | live のみ、committed に無い | 削除。apm が配置する |
| hook の `herdr-agent-state.sh` | 絶対パス | `$HOME` 参照へ変更 |
| skip-worktree | 必要 | 解除 |

## 移行手順

依存関係があるので順に行う。各フェーズの境界でテストが緑であることを確認する。

### Phase 1: 前提の検証

1. GitHub 経由でカテゴリー階層の skill を取得できることを確認する
2. `ax` の上流を特定する

Phase 1 が失敗した場合、カテゴリー階層を諦めて 1 階層にする (`skills/<name>/`)。設計全体は
維持できる。

### Phase 2: 新規リポジトリの構築

3. `agentic-coding-tools` を PUBLIC で作成する
4. 自作 skill 5 個を移設する (dotfiles からは削除しない。Phase 5 まで並行稼働)
5. plugin 3 個を現行 private リポジトリから移設する
6. README 自動生成と CI 検査を入れる

### Phase 3: dotfiles の apm 化

7. `apm.yml` と `apm.lock.yaml` を追加する
8. `bootstrap.sh` から skills の symlink ペアを外し、`apm install -g --frozen` を呼ぶ
9. `home/.claude/skills/` を削除する

### Phase 4: アカウント運用の外部化

10. 設定ファイルの読み込みを `bootstrap.sh` / `.zshrc` / `statusline-command.sh` へ入れる
11. テストをパラメータ化し、任意のディレクトリ名で動くことを検証する形にする
12. Issue ドキュメントの記述を伏字化する

### Phase 5: 後始末

13. `settings.json` から marketplace と `enabledPlugins` の該当分を削除する
14. hook パスを `$HOME` 参照へ変える
15. skip-worktree を解除し、live と committed を 1 本にする
16. 現行 private plugin リポジトリをアーカイブする

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

### apm 配布のテスト

`bootstrap.sh` が `apm install` を呼ぶ部分は shell-out なので、ユニットテストが緑でも完了と
しない。CLAUDE.md の live smoke ルールに従い、新規 clone した状態から `bootstrap.sh` を通しで
実行し、skill が実際に配置されることを確認する。

### 露出の回帰検査

移行後に追加の設定ディレクトリ名が追跡ファイルへ再び入らないことを、gitleaks または
config-guard の検査で pin する。Issue #21 の「検出網の穴を塞ぐ」と重なるため、そちらと
実装を揃える。

## 未確認事項とリスク

| 項目 | 内容 | 対処 |
|---|---|---|
| GitHub 経由のカテゴリー階層 | ローカルパスでは実測済みだがリモートは未確認 | Phase 1 で検証。失敗したら 1 階層へ |
| `ax` の上流 | 外部由来と本人確認済みだが出所が未特定 | Phase 1 で特定。不明なら依存宣言から外して手動管理を継続 |
| apm と `CLAUDE_CONFIG_DIR` | apm が参照するか未実測 | 参照しない前提で設計済み。symlink で吸収する |
| `--dry-run` の副作用 | `~/.apm/apm.yml` を実際に作る (実測) | dry-run の結果を無害と仮定しない。実行後に差分を確認する |
| `--root` と `apm.yml` | `--root` を指定しても `apm.yml` は $PWD に作られる (実測) | dotfiles の `apm.yml` は先にコミットしておく |
| plugin の品質 | 公開に耐えないという判断が移行の動機の一部 | 公開基準は別途決める。基準を満たさないものは `apm.yml` に載せない運用で分離できる |

## 却下した案

### 現行 private リポジトリを PUBLIC 化して集約する

private 前提の履歴がすべて公開される。新規リポジトリなら公開して問題ない状態だけを最初の
コミットにできるため、履歴書き換えの検討自体が不要になる。

### dotfiles にすべて吸収する

clone 1 回で完結し移行も最小だが、マシン設定とエージェント資産が混ざる。他人が apm で
取り込むとき skill 単位の指定はできるものの、リポジトリの性格が曖昧になる。

### plugin を解体してすべて skill 化する

単位が 1 つになり使い分けの迷いは消えるが、agent と command を失う。apm が配布時に解体する
ことが実測で分かったため、オーサリング側で解体する理由がない。

### 他者由来の skill も新リポジトリへ移す

上流に追随できなくなる。現状の手動コピーが抱えている drift をそのまま引き継ぐことになる。
apm の依存として宣言し、`apm install --update` で追随させる。
