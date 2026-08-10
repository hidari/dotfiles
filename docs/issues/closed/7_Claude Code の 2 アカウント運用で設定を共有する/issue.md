---
status: closed
---

# feat: Claude Code の 2 アカウント運用で設定を共有する

## 背景

仕事の都合で Claude Code のサブスクリプションを 2 つ運用する必要が出た。設定は同じままアカウントだけを使い分けたい。

- 個人: `~/.claude`（ika5140@gmail.com）
- 仕事: `~/.claude-hamiltonian`（ikawa@hamiltonian.studio）

`CLAUDE_CONFIG_DIR` で分離されるのはユーザースコープのみ。プロジェクトスコープの `.claude/settings.json` と `.claude/settings.local.json` はどちらのアカウントで起動しても同じものが読まれる。実用上は望ましい挙動だが「アカウントを分ければ全部分かれる」という前提だと誤解しやすい。

5h / 週次のクォータはアカウント単位なので、分離すればレート枠が別になる。

### 着手時点の状態

新規構築ではない。`~/.claude` 側の共有は既に完成しており、`bootstrap.sh` の `SYMLINK_PAIRS` が配線の単一の真実源として次の 6 項目を dotfiles へ向けている。

| 対象 | 種別 | pair source |
| --- | --- | --- |
| `settings.json` | ファイル | `home/.claude/settings.json` |
| `CLAUDE.md` | ファイル | `home/.claude/CLAUDE.md` |
| `skills/` | ディレクトリ | `home/.claude/skills` |
| `hooks/` | ディレクトリ | `home/.claude/hooks` |
| `.mcp.json` | ファイル | `home/.claude/.mcp.json` |
| `statusline-command.sh` | ファイル | `home/.claude/statusline-command.sh` |

したがって本 Issue の作業は「hamiltonian 側の pair を足す」ことと、「アカウント固有の状態を掴んでいる箇所を分離する」ことに絞られる。

## 調査で確定した事実

### Keychain の service 名はアカウントごとに分かれる

`statusline-command.sh` は `security find-generic-password -s "Claude Code-credentials"` を無条件に読んでいる。実際の service 名は config dir ごとに分かれる。

| config dir | service 名 | 実在 |
| --- | --- | --- |
| `$HOME/.claude`（既定） | `Claude Code-credentials` | あり |
| `$HOME/.claude-hamiltonian` | `Claude Code-credentials-2a4c0d76` | あり |
| `$HOME/.claude` にサフィックス導出を適用 | `Claude Code-credentials-608b5dc5` | なし |

規則は「既定ディレクトリはサフィックス無し、`CLAUDE_CONFIG_DIR` 指定時は絶対パスの sha256 先頭 8 桁を付ける」。`2a4c0d76` は `$HOME/.claude-hamiltonian` を展開した絶対パスの sha256 先頭 8 桁と一致し、Keychain に実在する。既定ディレクトリに同じ導出を当てた `608b5dc5` は存在しない（負のコントロール）。

修正しないと hamiltonian で起動しても個人アカウントのトークンでプローブし、個人側のレート制限が黙って表示される。

これは Claude Code の非公開な実装詳細なので、規則が変わりうる前提で設計する。導出した item が存在しないときは他方へフォールバックせず `--%` 表示に落とす。誤情報より無情報を選ぶ。再検証コマンド:

```bash
security find-generic-password -s "Claude Code-credentials-$(printf '%s' "$HOME/.claude-hamiltonian" | shasum -a 256 | cut -c1-8)" > /dev/null 2>&1; echo "EXIT=$?"
```

### レート制限キャッシュが相互汚染する

`CACHE_FILE` が `$XDG_CACHE_HOME/claude/usage-cache.json` 固定で TTL 360 秒。両アカウントが同一ファイルを読み書きするため、片方の 5h / 7d 使用率がもう片方の statusLine に最大 6 分間表示される。レート枠を分離した目的そのものを裏切る。

### アカウント名は動的に取得できる

`.claude.json` の `oauthAccount.emailAddress` から読める。両アカウントとも当該フィールドの実在を確認済み。配置に非対称があるので分岐が要る。

- 既定ディレクトリ: `$HOME/.claude.json`（`~/.claude/` の中ではない）
- `CLAUDE_CONFIG_DIR` 指定時: `$CLAUDE_CONFIG_DIR/.claude.json`

動的に読めばコミット対象ファイルに個人情報を書かずに済み、アカウントを増やしてもスクリプト修正が要らず、表示が実際のログイン状態と乖離しない。

### クォート内のチルダは展開されない

`CLAUDE_CONFIG_DIR="~/.claude-hamiltonian" claude` はリテラル `~/.claude-hamiltonian` を渡す。zsh / bash 双方で実測。

```
FOO="~/.claude-hamiltonian" → ~/.claude-hamiltonian   （リテラルのまま）
FOO=~/.claude-hamiltonian   → $HOME を展開した絶対パス
```

`CLAUDE_CONFIG_DIR` は存在しないディレクトリを指しても警告されず、その場所に新しい設定ディレクトリを作って初期状態で起動する。「なぜか /login を求められる」という形でしか気づけない。上のチルダはこの罠を踏む具体例。

### 環境変数の前置は関数呼び出しにも効く

関数内で起動するコマンドの環境まで届き、呼び出し後には残らない。zsh / bash 双方で実測。

```
f() { printenv MYVAR; }; MYVAR=hello f   → hello        （関数の環境に入る）
呼び出し後の $MYVAR                       → 残っていない
```

## 設計判断

### statusLine スクリプトの置き場は現状維持

`~/.config/claude/` への新設は行わない。`settings.json` が `bash ~/.claude/statusline-command.sh` を、hooks が `$HOME/.claude/hooks/...` を、いずれも絶対パスで参照する規約が既に確立している。これらは symlink 経由でリポジトリに解決されるため hamiltonian から起動してもそのまま動く。中立な場所を新設すると hooks 側の参照も全て移さないと一貫性が崩れ、配線とテストの変更だけが増える。

`~/.claude` は「個人アカウントのディレクトリ」であると同時に「共有スクリプトの置き場」を兼ねる。

### settings.json は 1 本に統一する

`~/.claude-hamiltonian/settings.json` の独自内容（`language` の一人称が「わたし」、`theme: dark`、`preferredNotifChannel`、`showTurnDuration`、`terminalProgressBarEnabled`、`permissions.defaultMode`）は破棄する。

### 共有しないもの

`plugins/` は symlink しない。インストール状態を持つため。`settings.json` の `enabledPlugins` と `extraKnownMarketplaces` を共有すれば hamiltonian 側も同じ marketplace を自前で clone するので、実体の共有は不要。

`.mcp.json` は hamiltonian へ配線しない。Claude Code は `~/.claude/.mcp.json` を読まないため、2 箇所目を作っても増えるのは死んだ symlink だけ。

アカウント固有の状態（`.claude.json` / `projects/` / `history.jsonl` / `sessions/` / `todos/` / `shell-snapshots/` / `statsig/` / `debug/` / `backups/` / `plugins/`）は symlink 対象からも git 管理からも外す。認証情報は macOS では Keychain に入り `.credentials.json` は生成されない（両ディレクトリとも不在を確認済み）。

当初案にあった `agents/` `commands/` `rules/` `output-styles/` はリポジトリにも `~/.claude` にも存在しないため対象外。

### 起動はシェル関数にする

スニペット / alias / 関数の 3 案のうち関数を採る。

alias は環境変数の前置に名前を付けただけなので、スニペットと安全性は同等。関数だけが実行前に検査を挟める。存在しない config dir を黙って受け入れる罠を即座の明示エラーに変えられるのが決定的な理由。加えて `home/.zshrc` は既に `SYMLINK_PAIRS` にあり bootstrap で全マシンへ配布されるため、設定がリポジトリ管理下に収まる。スニペット機能はリポジトリ外に置かれるので、この設定だけが配布と版管理の外に落ちる。

### 2 つの環境変数は軸が違う

| 変数 | 軸 | 値の数 | 扱い |
| --- | --- | --- | --- |
| `CLAUDE_CONFIG_DIR` | アカウント | 2（固定） | 関数が持つ |
| `CLAUDE_CODE_TASK_LIST_ID` | プロジェクト | 20 以上（可変） | 前置のまま残す |

両方を関数に固定すると 2×N 個の関数が要る組み合わせ爆発になる。値が少なく検査できるアカウントだけを関数が持ち、タスクリストは前置で渡す。前置は関数呼び出しにも効くため `CLAUDE_CODE_TASK_LIST_ID=dotfiles claude-hamiltonian` がそのまま動く。

タスクリスト ID をリポジトリ名から自動導出はしない。既存のタスクリスト名には `dotfiles` `claude-plugins` のようなリポジトリ名と一致するものに加え、`cospl` `cpspl` `sptth` のような短縮コードや `studio-Hamiltonian-logo-automation` のような粒度違いが混在する。自動導出すると短縮コードを使うリポジトリで新しいリストが静かに作られ履歴が分裂する。代わりに未知の ID のときだけ標準エラーへ知らせる。新規作成自体は正当なのでブロックはしない。

### 個人アカウント側は CLAUDE_CONFIG_DIR に触らない

`claude` を関数化するが、個人アカウントでは `CLAUDE_CONFIG_DIR` を設定しない。Claude Code が「変数がセットされているか」だけで Keychain service 名の導出を分岐している場合、既定パスを明示指定すると存在しない `Claude Code-credentials-608b5dc5` を探しに行き再ログインを要求されうる。どちらの実装かは未確認なので、未確認の前提に賭けず変数に触れない。触れなければ挙動は現状と同一で、関数はタスクリスト警告だけを足す。

## 行構成

行は情報の所有者で分ける。1〜3 行目は Claude が持つ状態、4 行目はリポジトリが持つ状態。
視線が「どのアカウントでいくら使ったか」と「どのブランチにいるか」で混ざらない。

```
<account> │ <model> │ <context> │ <cost · duration>
5h  <bar>  <pct>  Resets at ...
7d  <bar>  <pct>  Resets at ...
<project> <flags>[<branch>] │ ± +added/-removed
```

git リポジトリの外では 4 行目が空になるため、行ごと省いて 3 行に畳む（空行を出さない）。
最終行にだけ改行を付けない規約があるので、4 行目の有無で最終行が変わる点に分岐が要る。

## タスク

- [x] statusline-command.sh のアカウント分離
  - [x] config dir / アカウントタグ / Keychain service 名 / `.claude.json` パスを導出する純粋関数を切り出す
  - [x] `# ヘルパー関数` `# メイン処理` のマーカーを入れ bats から marker-slice で source できるようにする
  - [x] `CACHE_FILE` をアカウントタグ別のパスにする
  - [x] Keychain service 名を導出値にし、item 不在時は他方へフォールバックせず `--%` に落とす
  - [x] line 1 の先頭にアカウント（メールアドレス）を色付きで表示する
  - [x] 4 行構成へ組み替える（リポジトリ情報を 4 行目へ分離）
- [x] `.zshrc` に起動関数を追加
  - [x] `_claude_task_list_notice` / `claude` / `claude-hamiltonian` を追加
  - [x] ディレクトリ不在時に非ゼロで終了し `claude` を起動しないこと
  - [x] `claude` の関数化が再帰しないこと（`command claude` を使う）
  - [x] 個人アカウント側が `CLAUDE_CONFIG_DIR` を設定しないこと
- [x] `bootstrap.sh` の `SYMLINK_PAIRS` に hamiltonian 側の 3 行を追加
- [x] drift 検出テストを追加
  - [x] `.claude/` を target に持つ pair に、同じ source を持つ `.claude-hamiltonian/` の pair が存在することを検証する
  - [x] statusline の導出ロジックのテスト（既定 / 指定時の service 名・タグ・`.claude.json` 探索先、2 つの config dir でキャッシュパスが異なること、item 不在時にフォールバックしないこと）
  - [x] 各テストが変異注入で赤くなることを確認する
- [x] 検証
  - [x] `bats scripts/tests/` が緑（125 件）
  - [x] `./bootstrap.sh --dry-run` で意図した symlink だけが出る
  - [x] 両アカウントを実起動して live smoke（shell-out と外部 CLI のオーケストレーションなのでユニットテスト緑では完了としない）

## 結果

### レート枠が実際に分かれていることの確認

live smoke で両アカウントの statusLine を実際に描画し、外部 CLI の実チェーン
（`security` / `curl` / `jq`）を通した。

| | 個人 | 仕事 |
| --- | --- | --- |
| 7d 使用率 | 100% | 0% |
| 7d リセット | 2026-07-29 00:00 | 2026-07-29 08:00 |

分離が失敗していれば同じトークンで引くため両方 100% になる。値もリセット時刻も
割れたことが、Keychain service 名の導出が実チェーンで効いている証拠になる。

キャッシュもアカウントごとに分かれた（`usage-cache-default.json` と
`usage-cache-<tag>.json`）。旧共有版の `usage-cache.json` は移行の残骸として削除した。

`.zshrc` の起動関数も実 zsh と実バイナリで確認した。`claude --version` がバージョンを
返すこと自体が、`command claude` でバイナリに解決されていて無限再帰していない証拠になる。
未知のタスクリスト ID では警告が出たうえで起動し、既知の ID では沈黙した。

### 変異注入で見つかった dead pin

「リポジトリ外では 3 行に畳む」テストが、変異（4 行目を常に出す）を入れても緑のままだった。

原因は bats の `$output` が末尾の改行を落とすこと。壊れた出力は `3 行目 + 改行` +
空文字なので、`$lines` の要素数では正常な出力と区別が付かない。つまり「最終行に改行を
付けない」という規約は要素数では原理的に観測できない。

生の出力をファイルへ落として改行の数で見る形に直したところ、期待どおり赤くなった。
アサーションは書かれていたが、観測手段が仕様を見られる場所に無かったという型。

変異注入は 3 領域で計 18 件（.zshrc 6 / statusline 9 / bootstrap 3）実施し、
上記 1 件の修正後は全件が期待どおり FAIL した。

## 関連

### settings.json の skip-worktree

`home/.claude/settings.json` は skip-worktree が立っており、コミット済みの内容と live の内容が異なる。live にはローカルの `claude-plugins` marketplace などホーム配下の絶対パスが含まれ、gitleaks の `macos-user-path` ルールがコミットを止める。コミットが必要な変更を入れるときは save → `--no-skip-worktree` → 編集 → commit → restore の手順を踏む。本 Issue では settings.json の内容変更は不要。

### live の絶対パスを $HOME 化できるか（フォローアップ）

skip-worktree を無くせるかを調べた。live の settings.json に残る `/Users/<name>` は 2 箇所。

1. herdr hook の `command` — シェルコマンド文字列なので `$HOME` にできる。同じファイルの
   兄弟 hook が既に `python3 "$HOME/.claude/hooks/tirith-check.py"` と書いて動いている。
   しかもコミット済み版にはこの hook 自体が無いため、直せばコミット可能になる。
2. marketplace の `directory` source の `path` — 未確定。

2 について分かったこと: `claude plugin marketplace add '~/Develop/claude-plugins'` は成功する
が、settings.json と known_marketplaces.json の両方へ絶対パスに正規化して書き込む。つまり
CLI は書き込み時にチルダを展開する。読み込み側が手書きのチルダを展開するかは別問題で、
`marketplace list` と `plugin list` はどちらも settings.json を同期しないため
（絶対パスの対照でも同じく何も出なかった）判別できなかった。決着には対話セッションの
起動が要る。

1 だけ直しても 2 が残る限り skip-worktree は外せないので、両方まとめて別 Issue で扱う。
調査内容は [Issue #8](../8_settings.json%20の%20live%20専用パスを変数化して%20skip-worktree%20を解消する/issue.md) へ切り出した。

### symlink が実ファイルに置き換わる可能性

Claude Code が `/config` などで設定を書き換えたとき、書き込みが tmp+rename の atomic write だと symlink が壊れる。どちらの実装かは未確認。現在 `~/.claude/settings.json` は symlink を保っているので通常運用では壊れていない。hamiltonian 側を追加したあと運用しながら確認する。

```bash
ls -la ~/.claude/settings.json ~/.claude-hamiltonian/settings.json
```

symlink でなくなっていたら `settings.json` だけ symlink をやめてコピー同期に切り替える。
