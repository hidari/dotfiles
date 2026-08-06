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
| 外部由来 (`ax`) | 1 | 手動管理。上流は特定済み (下記) |
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

apm 0.27.0 / Claude Code 2.1.223 で確認した。すべて使い捨てディレクトリと隔離した
`CLAUDE_CONFIG_DIR` で実行し、前後で `~/.apm/apm.yml` のハッシュ一致と `git status` の空、
および `~/.claude/settings.json` のハッシュ一致を確認している。

「0 件」を結論の根拠にした箇所には、正常なら非空になる対照を必ず並べてある。

### apm と Claude Code は別々のファイルを見ている

判定は排他的な分岐ではなく、独立に評価される加算ルールである。

| 見る主体 | 判定に使うもの | 判定が真のときの効果 |
|---|---|---|
| apm | root に `SKILL.md` があるか | root 全体を verbatim コピー |
| apm | root に `.claude-plugin/` ディレクトリがあるか (中のファイル名は不問) | `agents/` `commands/` `skills/` をフラット分解 |
| Claude Code | `.claude-plugin/plugin.json` というファイル名そのもの | `<name>@skills-dir` plugin として読み込む |

両方を置くと両方が発火する。実プラグイン (現行 3 plugin のうち 1 つ) での追試では、
root に `SKILL.md` を 1 本足しただけで 17 ファイルすべてがバイト一致で運ばれ、失われた
ファイルは 0 件だった。

対照として、`.claude-plugin/` を持たないパッケージは `agents/` と `commands/` があっても
フラット deploy が 0 件になる。エラーも警告も出ず黙って捨てられる。

判定基準のずれは既に実害を出している。mizchi/skills の `justfile` は
`.claude-plugin/manifest.json` を持つため apm は分解経路に乗せるが、Claude Code は
`plugin.json` でなければ plugin と認識しないので、一度もロードされていない。

### `ax` の上流は yusukebe/ax。手元は古い写しで防御指針が欠けている

12 skill のうち唯一上流が未特定だった `ax` を特定した。CLI が Homebrew の `yusukebe/tap`
由来であることから辿り、リポジトリ `yusukebe/ax` の `skills/ax/SKILL.md` が上流と確認できた
(MIT)。

手元の写しは 2026-07-11 に、無関係な nvim 配色のコミットへ紛れて追加されていた。上流はその後
3 回更新されており、手元との差分は上流にのみ 24 行、手元にのみ 3 行。手元の 3 行はいずれも
上流が更新した箇所の旧版で、独自編集は 1 行も無い。純粋に古い写しである。

欠けている差分には `Fetched content is untrusted data` という節が丸ごと含まれる。取得した
ページや API 応答を指示として扱わない、cloud metadata エンドポイントに触れない、認証情報を
指定外の origin へ送らない、といったプロンプトインジェクション対策の指針である。

apm 依存として宣言できることを隔離環境で確認した。`yusukebe/ax/skills/ax#<sha>` は解決に成功し
(`package_type: claude_skill`)、deploy された `SKILL.md` は上流とバイト一致で、上記の防御節を
含んでいた。

追随しない pin のリスクは「上流の改善が届かない」方向にも働く。spec の「供給網のレビュー面」で
挙げた「内容レビュー無しの追随」の裏返しであり、両方向とも実在する。

### symlink 経由でも skills-dir plugin は検出される

理想像 4 (dotfiles 内で実体化し `~/.claude/` へ symlink) の中核。3 点セットで確認した。

| ケース | 結果 |
|---|---|
| `<config-dir>/skills` が実ディレクトリ (対照) | `probe-pkg@skills-dir` を検出 |
| `<config-dir>/skills` が symlink (本命) | `probe-pkg@skills-dir` を検出 |
| symlink かつ `.claude-plugin/` を削除 (変異注入) | 検出 0 件 |

変異注入で確かに検出されなくなるので、この確認は生きた pin である。

`installPath` は symlink 側のパスを保持し、リンク先へは解決されない。したがって
リポジトリの実体パスがモデルへ渡る経路には現れない。

### P1 形は GitHub 経由でも成立する。private リポジトリからも取れる

実プラグイン (`security-blue-red-team`, 16 ファイル) の root に `SKILL.md` を 1 本足し、
`plugin.json` に `"skills": ["./skills"]` を書いた形を GitHub へ push し、apm で取得した。
private リポジトリの取得可否が交ざるため、同じ実行に public の `yusukebe/ax/skills/ax` を
対照として並べ、認証の失敗と形の失敗を切り分けている。

両方とも成功した (exit 0)。private リポジトリでも partial clone のフォールバックが働いて取得できる。

加算ルールは GitHub 経由でも両方発火した。

| 観測点 | 結果 |
|---|---|
| verbatim コピー | `.claude/skills/security-blue-red-team/` に `schemas/` 5 件と `README.md` を含む全ファイル |
| フラット分解 | `.claude/agents/` 2 件、`.claude/commands/` 4 件 |
| 内部 skill のフラット重複 | 0 件 (`"skills": ["./skills"]` が効いている) |
| 失われたファイル | 0 件 |
| 共通ファイルの内容 | すべてバイト一致 |

ファイル数はソース 17 件に対し deploy 18 件だった。増えた 1 件は apm が deploy 先へ合成する
`apm.yml` である。verbatim が保証するのは「失わない」ことであって「増やさない」ことではない。

**`package_type` で形の成否を判定してはならない。** lockfile には `marketplace_plugin` と記録され、
`claude_skill` にはならない。加算が起きたことを正しく示すのは、合成された `apm.yml` の
`type: hybrid` である。同じツールが 2 箇所へ別のラベルを書いているため、lockfile だけを見ると
「P1 形が成立していない」と誤読する。確認は deploy されたファイル集合を直接見るのが確実。

### 変数の展開範囲はファイルの位置で変わる

root の `SKILL.md` は plugin の component として数えられないため、扱いが分かれる。

| 位置 | `${CLAUDE_SKILL_DIR}` | `${CLAUDE_PLUGIN_ROOT}` |
|---|---|---|
| root の `SKILL.md` | 展開される | literal のまま (エラーにならず静かに壊れる) |
| `skills/` `agents/` `commands/` hooks | 展開される | 展開される |

これが schema 参照問題の答えになる。agent と command は skill ディレクトリの外に置かれるため
相対参照ができず、そこが schema 置き場の再設計を必要にしていた。component 側では
`${CLAUDE_PLUGIN_ROOT}` が展開されるので、verbatim コピーされた `schemas/` の実体に届く。

### plugin id と名前空間は plugin.json の name が決める

ディレクトリ名は使われない (`installPath` だけがディレクトリを指す)。component は
`<plugin名>:<component名>` で名前空間化され、素の名前では解決できない。

apm は `apm.yml` のパッケージ名でディレクトリを作るため、パッケージ名と `plugin.json` の
`name` を一致させる規約が要る。ずれると呼び出し名が想定と変わる。

一致させる限り、現行の修飾名 (`dev-workflow:git-branch-switcher` 等) はそのまま生き残る。

### plugin.json の宣言フィールドと禁止形

宣言フィールドは配列で、`claude plugin validate --strict` が canonical な検証手段になる。
CI と pre-commit のゲートに使えるため、フィールド名の一覧を本書に再掲しない。

運用上の確定事項は 2 つ。

- `"skills": ["./"]` は禁止。apm を無限再帰させ `File name too long` で install が落ちる。
  `claude plugin init` の既定形がこれなので、生成後に必ず直す
- `"skills": ["./skills"]` はフラット側の skill 重複だけを消し、Claude Code 側のロードは維持する。
  `agents` / `commands` に同じ中間解は存在せず、空配列で消すと Claude Code 側の component まで
  無効化される

したがって「フラット汚染ゼロかつ全 component 生存」は現行の組み合わせでは達成できない。

### apm install は tracked file を黙って破壊する

`--force` なしでも git tracked かつ手書きのファイルを上書きし、パッケージに含まれない
ファイルを削除する。ログには `(files unchanged)` と表示される。deploy 先は verbatim コピー
ではなく `rsync --delete` 相当のミラーである。

### settings.json の書き換えは設定ディレクトリごとに初回 1 回だけ

`claude plugin list --json` のような読み取り専用に見えるコマンドで
`skipAutoPermissionPrompt` が削除される。同時に置いた未知キーは保持されるので、スキーマの
掃除ではなく特定キー狙いの migration である。

発火条件と抑止可能性を切り分けた。

| 条件 | settings.json |
|---|---|
| 素の呼び出し (baseline) | 書き換えられる |
| `--settings <file>` | 書き換えられる |
| `--setting-sources project,local` (user を読まない) | 書き換えられる |
| `--bare` (hooks / plugin sync を切る最小モード) | 書き換えられる |
| `chmod 444` | 書き換えられる |
| `--version` のみ | 変化なし |
| 同じ設定ディレクトリでの 2 回目以降 | 変化なし |
| 消えたキーを戻してからの再実行 | 変化なし (キーは残る) |

`--setting-sources` で読み込み対象から外しても書き換わることから、書き戻しは設定の読み込み
経路ではなく独立した migration 処理として走っている。状態は `<config-dir>/.claude.json` の
`migrationVersion` に記録される。

`chmod 444` が効かないのは、一時ファイルを書いて rename する置換方式のため。必要なのは
ディレクトリの書き込み権限だけで、ファイルの権限は迂回される。同じ理由で symlink は
リンク先へ解決されてから置換されるため、symlink 自体は壊れない (実測で inode の変化と
symlink の生存を確認)。

### `-g` は cwd の manifest を読まない

`apm.yml` のあるディレクトリで `apm install -g` を実行しても
`[x] No <HOME>/.apm/apm.yml found` で中断した。user scope の manifest と lockfile は
`~/.apm/` にあり、追跡外のマシンローカルな置き場である。

さらに `--frozen` は positional packages と排他なので、`~/.apm/apm.yml` を auto-create する
経路 (`apm install -g <pkg>`) と `--frozen` を同時には使えない。

したがって「dotfiles の `apm.yml` と lockfile をコミットして再現性を担保する」設計は
`-g` では成立しない。project scope (現行機構) でのみ成立する。

### CLAUDE_CONFIG_DIR は user scope の話で、project scope では無視される

現行機構が使う project scope の deploy 先は project 相対の `.claude/skills/` であり、
`CLAUDE_CONFIG_DIR` は参照されない。隔離した `CLAUDE_CONFIG_DIR` を与えて `apm install` した
実測では、当該ディレクトリは空のままで deploy は `<project>/.claude/skills/` に行われた。
lockfile も `kind: project-relative` と記録する。

`cd home && apm install --frozen` が `home/.claude/skills/` へ配置するのはこの性質による。
環境変数ではなく実行時の cwd が deploy 先を決めている。

以下は user scope (`-g`) の話である。そちらは `CLAUDE_CONFIG_DIR` を参照し、失敗条件は
symlink 先の位置になる。条件を 1 つずつ変えて切り分けた。

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

### git source の生成物に個人情報は入らない

git source で取得した生成物 62 ファイルに `/Users` は 0 件、gitleaks は 0 leaks だった。
対照として local source (`file:///` 経由) では `/Users` が 25 件と 31 件、gitleaks は 35 leaks
検出される。

なお `apm marketplace list` の表示はチルダだが、`~/.apm/marketplaces.json` には `file:///` の
絶対 URL で保存される。ローカルユーザー名が入らないのは「コミットされるファイル」に限った話で、
追跡外の設定には入る。

## 設計

### 方針: 単一経路にする

パッケージの root に `SKILL.md` と `.claude-plugin/plugin.json` の両方を置く。これで apm の
verbatim コピーと Claude Code の plugin 認識が同時に成立し、skill と plugin を 1 つの宣言系統で
配れる。

配布は動作実績のある project scope 機構 (`cd home && apm install --frozen` + committed lockfile
+ symlink) を維持する。`-g` へ乗り換えない理由は前節のとおりで、コミットした manifest と
lockfile が読まれなくなる。

`home/.claude/skills/` は削除せず、`.gitignore` への追加と `git rm -r --cached` で追跡だけを
止める。実体は apm が配置し、symlink の供給網は現状のまま生きる。

marketplace の宣言も `settings.json` の plugin エントリも不要になる。

### パッケージの形

新リポジトリに置く 1 パッケージの構成を示す。この形が本設計の中核であり、
`claude plugin validate --strict` で機械検証できる。

```
<package>/
├── SKILL.md                     apm に verbatim 経路を選ばせ、同時に入口 skill になる
├── .claude-plugin/plugin.json   Claude Code に plugin と認識させる。name はパッケージ名と一致必須
├── skills/<name>/               plugin component
├── agents/<name>.md             plugin component
├── commands/<name>.md           plugin component
└── schemas/ · README.md         verbatim コピーに便乗して運ばれる。component ではない
```

deploy 先の `~/.claude/skills/<dir>/` には `.apm/` を除く全ファイルがバイト一致で複製される。
`.git/` や `node_modules/` も運ばれるため、配りたくないものを root に置いてはならない。

命名の規約が 2 つある。どちらも破ると静かに壊れる。

- パッケージ名 (apm がディレクトリ名に使う) と `plugin.json` の `name` を一致させる。
  ずれると component の修飾名が想定と変わる
- root の `SKILL.md` の name と、パッケージ内 `skills/<name>/` の name を重複させない。
  衝突すると skills directory loader が既に surfacing 済みと判断して plugin 側の skill を
  skip する

### フラット重複を受け入れる

`.claude-plugin/` があると apm は agent と command をフラットにも展開するため、
`~/.claude/agents/` と `~/.claude/commands/` に重複が生じる。前節のとおりこれは消せない
(消すと Claude Code 側の component まで無効化される)。

したがって重複を受け入れ、`agents` と `commands` の symlink を新設する。
`plugin.json` には `"skills": ["./skills"]` だけを書き、`agents` と `commands` は宣言しない。

### リポジトリの役割分担

`agentic-coding-tools` (PUBLIC, 新規) が自作 skill 5 個と plugin 3 個を持ち、dotfiles は
`home/apm.yml` と `home/apm.lock.yaml` の宣言 2 ファイルだけを追跡する。

境界は「マシンに固有か、エージェントの振る舞いか」。`hooks/` と `statusline-command.sh` は
Claude Code の設定でありエージェント資産ではないため dotfiles に残す。

新規リポジトリにするのは、現行 private リポジトリを公開に切り替えると private 前提の履歴も
すべて公開されるため。新規なら公開して問題ない状態だけを最初のコミットにできる。

hook と MCP サーバ定義も skills-dir plugin から配布できることを確認しているが、hook は任意
コマンドを実行するため、「ユーザースコープには公開可能な情報しか入り得ない」という不変条件は
hook のコマンド文字列にも及ぶ。

### アカウント運用の外部化

追加の設定ディレクトリ一覧を追跡外のローカル設定ファイルから読む。

```
${HOME}/.config/dotfiles/claude-config-dirs
```

- 1 行 1 ディレクトリ名。ファイルが無ければ `~/.claude` のみを対象にする
- 読者は `bootstrap.sh` と `home/.zshrc` の 2 つ。`statusline-command.sh` は既に名前非依存
  なので変更しない
- 増えたら行を足すだけで、リポジトリ側の変更は要らない

### apm install のガードを機構にする

`apm install` は tracked file を黙って破壊するため、実行前にリポジトリが clean であることを
確認する。目的は破壊の防止ではなく復旧可能性の確保である。ツリーが clean なら apm が何を
壊しても git から戻せるが、汚れていれば未コミットの作業が復旧不能に消える。この整理から、
検査範囲は deploy 先ではなくリポジトリ全体になる。

手順書に書くのではなく 2 層の機構にする。

- `bootstrap.sh` の `install_apm_skills()` に、`apm install --frozen` の手前でガードを置く。
  既存の `DRY_RUN` パターンに合わせる。自動実行経路をこれで塞ぐ
- `PreToolUse` hook で、Bash コマンド文字列が `apm install` に一致したときにツリーの汚れを
  見てブロックする。手打ちおよびエージェント経由の実行はこちらで塞ぐ

あわせて、`apm.yml` への追加と `git rm` を同一コミットにすることを必須とする。

### plugin の公開基準

次の 2 点のみを基準とする。

- 秘匿情報を含まないこと
- install 時と runtime に自動実行されるコードを持たないこと (持つ場合は個別に監査を経ること)

完成度と汎用性は基準にしない。目的が「自分のやり方を誰でも参考にできる状態にしておくこと」で
あり参照されるかどうかを問わない以上、「他人が使えるか」を基準にすると動機と矛盾するため。
README の不在や版の若さは除外理由ではなく、公開前に直す項目として扱う。

3 plugin とも `hooks` / `mcpServers` / `scripts` を宣言しておらず、自動実行されるコードを
持たない。したがって 3 個とも公開対象になる。

### 露出監査の結果

`plugins/` 配下 34 ファイルを検査した。

| 検査 | 結果 |
|---|---|
| macOS の実ユーザーパス | 0 件 |
| 実プロジェクト名 | 0 件 (一致した 1 語は一般語との衝突で偽陽性) |
| private リポジトリ名・秘匿ディレクトリ名 | 0 件 |
| `plugin.json` の author | 3 個すべてにメールアドレス。移設時に除去する |

手を入れる必要がある指摘は author のメールアドレス 1 件だけである。

現行リポジトリ全体では `macos-user-path` が 101 件検出されるが、すべて作業成果物に集中しており
`plugins/` 配下は 0 件だった。内訳は subagent 実行記録 52 件、plan 文書 45 件、IDE 設定 1 件。
移設が運ぶのは `plugins/` のみなので、これらのディレクトリを持ち込まないことが露出回避の条件に
なる。リポジトリを丸ごと複製する方式なら 101 件が公開されていた。

なお現行リポジトリには `.gitleaks.toml` が無く、既定ルールだけでは `macos-user-path` が検査
されない。既定ルールでの走査は 0 件を返すが、これは「無い」ではなく「そのルールを持っていない」
である。新リポジトリの検出網には dotfiles と同じカスタムルールを持つ設定を置く。

### 秘匿性の主張の範囲

達成できるのは「現ツリーに新規露出を足さない」ことまでである。git 履歴には 77 件が残り続け、
closed 配下の Issue 2 件はディレクトリ名自体に運用形態が出る。リネームしても履歴には残る。
Issue #21 自身が「履歴を書き換えれば消える前提を置くな」と警告している。

回帰検査には自己言及の罠がある。追跡される `.gitleaks.toml` にディレクトリ名の literal を
書いた瞬間、それ自体が名前をツリーへ戻す。検査は名前 literal を含まない形にする
(追跡外の `claude-config-dirs` から pattern を読む pre-commit 検査、または汎用形 + allowlist)。

### skip-worktree の廃止

marketplace の絶対パスと plugin エントリが `settings.json` から消えるため、skip-worktree の
理由はなくなる。

残るのは新規マシンの初回起動で `skipAutoPermissionPrompt` が 1 回だけ消える事象だが、これは
skip-worktree を外せば可視な git 差分になり、`git checkout` で戻せば定着する (実測済み)。
この書き換えを不可視にしていたのは skip-worktree そのものだったため、廃止の障害にはならない。

留保として、`migrationVersion` が存在する以上、将来のバージョンが別の migration を走らせる
余地は残る。

## 移行手順

### Phase 1: 前提の確定

1. 外部由来 skill 1 個の上流を特定する (完了)。`ax` の上流は `yusukebe/ax` の `skills/ax`。
   `yusukebe/ax/skills/ax#<sha>` が apm で解決し、上流とバイト一致で deploy されることまで確認済み
2. 新リポジトリの形で GitHub 経由の取得が成ることを確認する (完了)。実プラグインを P1 形にして
   push し、public の対照と並べて実測した。加算ルールは両方発火し、失われたファイルは 0 件

カテゴリー階層自体の検証は不要 (現行 lockfile に動作実績がある)。
plugin の配布経路の選択は不要になった (単一経路で成立するため)。

### Phase 2: 新規リポジトリの構築

入口 gate として先に次を行う。公開は不可逆で、repo 削除ではクローンやキャッシュを巻き戻せない。

3. plugin の公開基準を決める (完了)。基準は「秘匿情報を含まない」「自動実行コードを持たない」の
   2 点。3 plugin とも満たすため全数が公開対象
4. 初回コミット前の露出監査を行う (完了)。`plugins/` 配下は私物パス 0 件・実プロジェクト名 0 件・
   private リポジトリ名 0 件。要対応は `plugin.json` の author のメールアドレスのみ
5. 新リポジトリ自身の検出網 (pre-commit + gitleaks + `claude plugin validate --strict`) を整備する。
   gitleaks には dotfiles と同じ `macos-user-path` ルールを持たせる (既定ルールだけでは検査されない)

その上で構築する。

6. `agentic-coding-tools` を PUBLIC で作成する
7. 自作 skill 5 個を移設する (dotfiles からは削除しない。Phase 3 まで並行稼働)
8. plugin 3 個を移設し、各パッケージの root に `SKILL.md` を足す。`plugin.json` の `name` を
   apm のパッケージ名と一致させ、`"skills": ["./skills"]` に直し、author からメールアドレスを
   除去する。運ぶのは `plugins/` 配下のみとし、作業成果物のディレクトリは持ち込まない
9. README 自動生成と CI 検査を入れる

### Phase 3: dotfiles 側の切り替え

このフェーズは分割しない。skill の供給が途切れる窓を作らないため、追跡停止と設定ファイル駆動の
導入を同一フェーズで行う。

10. `apm install` のガードを 2 層で実装する (`bootstrap.sh` と `PreToolUse` hook)
11. `home/apm.yml` に自作 skill 5 個と plugin 3 個、および `ax` を追加し、lockfile を更新する。
    `ax` は `home/.claude/skills/ax/` の手動コピーを削除し `yusukebe/ax/skills/ax#<sha>` の
    宣言へ置き換える (欠けていた防御指針がこれで届く)
12. 追加の設定ディレクトリ一覧の読み込みを `bootstrap.sh` と `home/.zshrc` へ入れる
13. `agents` と `commands` の symlink 4 本を `bootstrap.sh` の対応表へ追加する
14. stale symlink の撤去を `bootstrap.sh` に実装する (配列から消したペアの残骸は現状消えない)
15. `home/.claude/skills/` を `.gitignore` へ追加し `git rm -r --cached` する。
    この 2 つは同一コミットにする
16. テストをパラメータ化し、任意のディレクトリ名で動くことを検証する形にする

### Phase 4: 後始末

17. Issue ドキュメントの記述を伏字化する
18. `settings.json` から marketplace 宣言と `enabledPlugins` を削除する
19. hook の `herdr-agent-state.sh` パスを `$HOME` 参照へ変える
20. skip-worktree を解除し、live と committed を 1 本にする
21. 現行 private plugin リポジトリをアーカイブする

修飾名の一括更新は不要 (パッケージ名と `plugin.json` の `name` を一致させる限り現行の
修飾名が維持されるため)。

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

### apm install ガードのテスト

ガードは検査機構なので、変異は 3 種いる。1 種だけで完了としない。

- 検査対象を壊す (ツリーを汚した状態でガードが止めること)
- 検査機構そのものを壊す (ガードの判定行を消して素通りすること)
- 検査機構の取り付けを外す (`install_apm_skills()` からの呼び出し、および `PreToolUse` の
  登録を外して素通りすること)

### 移行経路のテスト

新規 clone からの live smoke だけでは不十分である。一番壊れやすいのは移行前の状態が残った実機で、
そこを新規 clone のテストは原理的に踏めない。次を追加する。

- 旧 symlink が残存した状態から `bootstrap.sh` を再実行し、stale symlink が撤去されること
- 追跡停止後に `home/.claude/skills/` が空の状態から `apm install --frozen` で復元されること

### 機能のテスト

live smoke の合格条件を「skill が配置される」ではなく「代表 skill が実際に機能する」まで
引き上げる。

ツールの自己申告で成否を判定しない。次の 2 つは実測で誤読の元になることが分かっている。

- `claude plugin details` の Component inventory に Commands 行は存在せず、`commands/` 配下は
  Skills 行に畳み込まれて報告される。ロードの確認は `--debug` の出力かスラッシュコマンドの解決で行う
- lockfile の `package_type` は P1 形でも `marketplace_plugin` と記録される。verbatim コピーが
  起きたかは deploy されたファイル集合を直接見て確かめる

`plugin.json` の妥当性は `claude plugin validate --strict` を CI ゲートにする。

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
| `model` キー削除の経路 | 組織既定モデル適用時の分岐は再現できていない | 現在の `settings.json` に `model` キーが無いため削除対象が存在しない。再導入する場合のみ再検証 |
| 将来の migration | `migrationVersion` がある以上、別の migration が走る余地がある | 新規マシン初回の差分を手順書に明記し、想定外の差分が出たら都度確認する |
| `--dry-run` の副作用 | `~/.apm/apm.yml` を実際に作る経路がある | dry-run の結果を無害と仮定しない。実行後に差分を確認する |
| plugin の品質 | 公開に耐えないという判断が移行の動機の一部 | Phase 2 の入口 gate で基準を決める。公開は不可逆なので後追いできない |
| 履歴に残る露出 | 現ツリーを直しても履歴の 77 件は残る | 主張を「新規露出を足さない」に限定する。履歴書き換えの是非は Issue #21 で扱う |

## 却下した案

### plugin だけ marketplace 経路を維持する (旧案 A)

`settings.json` に GitHub source の marketplace 宣言が残る。単一経路で schema 参照が解決する
ことが分かったため不要になった。加えてこの案では skip-worktree を廃止できない
(config-guard が適用後も 2 件検出する)。

### skill 本文の schema 参照を書き換えて配布経路を 1 本化する (旧案 B)

component 側で `${CLAUDE_PLUGIN_ROOT}` が展開されるため、書き換えずに解決する。

### schema の置き場を再設計する (旧案 C)

同上。`schemas/` は verbatim コピーで運ばれ、component から届く。複製も発生しない。

### `--settings` フラグまたは生成物方式で settings.json の書き換えを止める

`--settings` / `--setting-sources` / `--bare` / `chmod 444` のいずれでも書き換えは止まらない。
かつ書き換えは初回 1 回だけで可視な差分として戻せるため、対策自体が不要になった。

### `apm install -g` への乗り換え

`-g` は cwd の manifest を読まないため、コミットした `apm.yml` と lockfile が使われない。
再現性の担保という目的そのものが達成できない。

### 現行 private リポジトリを PUBLIC 化して集約する

private 前提の履歴がすべて公開される。新規リポジトリなら公開して問題ない状態だけを最初の
コミットにできる。

### dotfiles にすべて吸収する

clone 1 回で完結し移行も最小だが、マシン設定とエージェント資産が混ざる。

### plugin を解体してすべて skill 化する

単位が 1 つになり使い分けの迷いは消えるが、agent と command を失う。単一経路で両方を配れる
ため、オーサリング側で解体する理由がない。

### 他者由来の skill も新リポジトリへ移す

上流に追随できなくなる。apm の依存として宣言し、pin を更新する形で追随させる。

### `statusline-command.sh` を設定ファイルの読者に加える

既に `${CLAUDE_CONFIG_DIR:-$HOME/.claude}` で名前非依存に動いており、本体に名前は 1 件も
現れない。露出はテストのフィクスチャだけなので、テストのダミー名化で足りる。
