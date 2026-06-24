# Volta から mise への移行 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** dotfiles の Node.js ツールチェイン宣言を Volta から mise へ一本化し、node / pnpm を exact pin した宣言的・再現可能な構成にする。

**Architecture:** 移行は 2 レイヤー。(1) リポジトリの宣言（mise config・bootstrap・Brewfile・zshrc・README）を Volta から mise へ書き換える。これが再現性の source。(2) マシン実体（`~/.volta`）の撤去は破壊的なので自動化せず、本計画末尾に手動手順として記す。mise は brew 管理・zshrc で activate 済みのため、宣言の置換のみで完結する。

**Tech Stack:** mise (brew 管理), bash (bootstrap.sh), zsh (.zshrc), TOML (mise config), Homebrew Bundle (.Brewfile), bats (既存テスト)。

## Global Constraints

- node は exact pin `24.17.0`、pnpm は exact pin `10.24.0`（config が単一 source of truth）。
- 移行スコープは node + pnpm のみ。wrangler 等 global npm package は対象外。
- Volta 撤去は dotfiles からの除去のみ。`~/.volta` 実体の削除は自動実行しない（手動手順）。
- ファイル末尾は必ず 1 つの空行。
- コード内コメントは日本語。内部ログは日本語、外部表示は英語。
- Markdown では `**強調**`・`---` 区切り線・過剰な絵文字を避ける。
- committed ファイルに `/Users/<実名>` リテラルを書かない（gitleaks ガード）。今回追加する mise config にパスは含めない。
- コミットメッセージは Conventional Commits。末尾に `Claude-Session: https://claude.ai/code/session_01TsSiv2WjaQE2Sjh8cxPwmS` を付ける。
- 各タスク完了時、`bats scripts/tests/` が 17/17 緑、`zsh -n home/.zshrc` が OK であること。

## テスト戦略（重要・実行者は必読）

新規 bats テストは追加しない。これは手抜きではなく、既存設計に基づく意図的判断である。

- `install_homebrew` / `install_rust` / `install_volta` / `install_claude_code` の 4 つの install 関数は、どれも 1 件も bats テストされていない。理由は `command -v <tool>` が実 PATH を参照し、`brew install` / `curl` が副作用を持つため。`install_mise` も同じ構造で、テストすると環境依存（ローカルは mise 導入済→「already installed」、CI は未導入→「[DRY-RUN] Install mise」）で flaky になる。よって既存パターンに揃えてノーテストとする。
- symlink 生成機構（`create_symlink`）と `ensure_directory` は既存の汎用テストでカバー済み。SYMLINK_PAIRS の個別エントリ（既存 11 件）はどれも個別テストされていない。今回追加する mise config のエントリも同方針。
- 検証は「既存 bats が緑のまま」＋「dry-run / grep / zsh -n のスモーク」で行う（各タスクの Step に明記）。

実行者へ: install_mise の bats テストを新規に書こうとしないこと。書くと flaky になり、既存スイートの no-mock 方針からも逸脱する。

## File Structure

- `home/.config/mise/config.toml`（新規）: mise の global tool pin。node / pnpm の exact version を宣言する単一 source of truth。bootstrap が `~/.config/mise/config.toml` へ symlink する。
- `bootstrap.sh`（変更）: install 関数・確認メッセージ・install シーケンス・SYMLINK_PAIRS・setup_dotfiles を Volta から mise へ。
- `home/.Brewfile`（変更）: 開発ツール節に `brew "mise"` を追記（宣言の source）。
- `home/.zshrc`（変更）: Volta 環境変数ブロックと path エントリを削除。mise activate と PNPM_HOME は維持。
- `README.md`（変更）: tools 一覧の Volta 行を mise へ。symlink テーブルに mise config の行を追加（テーブルと SYMLINK_PAIRS の drift 防止）。

---

## Task 1: bootstrap が mise を provision する（config + install + Brewfile）

mise の宣言 config を tracked にし、bootstrap が「mise バイナリを install」かつ「pin 済み config を symlink」するようにする。Brewfile にも mise を宣言する。完了時、bootstrap / Brewfile に Volta 参照が残らない。

**Files:**
- Create: `home/.config/mise/config.toml`
- Modify: `bootstrap.sh`（SYMLINK_PAIRS / install 関数 / 確認メッセージ / install シーケンス / setup_dotfiles）
- Modify: `home/.Brewfile`（開発ツール節）

**Interfaces:**
- Produces: `install_mise()` 関数（bash, 引数なし, 冪等。`command -v mise` で skip、DRY_RUN で `[DRY-RUN] Install mise` を出力、それ以外で `brew install mise`）。SYMLINK_PAIRS への新エントリ `"home/.config/mise/config.toml|.config/mise/config.toml"`。
- Consumes: 既存の `log` / `create_symlink` / `ensure_directory` ヘルパー、`install_homebrew`（mise の brew 依存を先に満たす）。

- [ ] **Step 1: mise config を作成する**

`home/.config/mise/config.toml` を新規作成（末尾は空行 1 つ）:

```toml
[tools]
node = "24.17.0"
pnpm = "10.24.0"
```

- [ ] **Step 2: SYMLINK_PAIRS に mise config を追加する**

`bootstrap.sh` の SYMLINK_PAIRS 配列、`.config/git/.gitignore_global` の行の直後に追加（`.config` エントリを隣接させる）:

```bash
    "home/.gitconfig|.gitconfig"
    "home/.config/git/.gitignore_global|.config/git/.gitignore_global"
    "home/.config/mise/config.toml|.config/mise/config.toml"
    "home/.claude/settings.json|.claude/settings.json"
```

- [ ] **Step 3: setup_dotfiles に mise config ディレクトリ作成を追加する**

`bootstrap.sh` の `setup_dotfiles()` 内、`ensure_directory "$HOME/.config/git"` の直後に追加（既存の `.config/git` と同じ明示パターンに揃える）:

```bash
    # 必要なディレクトリを作成
    ensure_directory "$HOME/.config/git"
    ensure_directory "$HOME/.config/mise"
    ensure_directory "$HOME/.local/bin"
```

- [ ] **Step 4: install_volta を install_mise へ置換する**

`bootstrap.sh` の `install_volta()` 関数全体（`# =====` セクション内）を以下へ置換:

```bash
install_mise() {
    log "Installing mise..."
    if command -v mise &> /dev/null; then
        log "mise is already installed. Skipping..."
        return 0
    fi

    if [ "$DRY_RUN" = true ]; then
        echo "[DRY-RUN] Install mise"
        return 0
    fi

    brew install mise
}
```

- [ ] **Step 5: 確認メッセージとインストールシーケンスを更新する**

`bootstrap.sh` の確認メッセージ:

```bash
            echo "  - Install Homebrew, Rust, mise, Claude Code"
```

install シーケンス（`install_homebrew` / `install_rust` / ... のブロック）の `install_volta` を `install_mise` へ:

```bash
        install_homebrew
        install_rust
        install_mise
        install_claude_code
```

- [ ] **Step 6: .Brewfile に mise を追記する**

`home/.Brewfile` の `# --- 開発ツール ---` 節の末尾（`brew "libpq"` の次の行）に追加。コメントは周囲の桁揃えに合わせる:

```
brew "libpq"                              # PostgreSQL通信するクライアントライブラリ
brew "mise"                               # ランタイム/ツールバージョン管理 (node, pnpm)
```

- [ ] **Step 7: 既存 bats が緑のままか確認する**

Run: `bats scripts/tests/`
Expected: `1..17` で全行 `ok`（17/17 緑）。SYMLINK_PAIRS データ追加と install 関数 rename はテスト対象関数を変えないため緑のまま。

- [ ] **Step 8: dry-run スモークで mise 化を確認する**

Run: `./bootstrap.sh -n`
Expected:
- `[INFO] Installing mise...` が出る（ローカルは mise 導入済のため続けて `mise is already installed. Skipping...`。これが正常）。
- `[DRY-RUN] ln -sf <repo>/home/.config/mise/config.toml <home>/.config/mise/config.toml` の行が出る。
- `Volta` / `Installing Volta` の行が一切出ない。

- [ ] **Step 9: コミットする**

```bash
git add home/.config/mise/config.toml bootstrap.sh home/.Brewfile
git commit -m "build: bootstrap を Volta から mise の provision へ移行

- mise の global config (node 24.17.0 / pnpm 10.24.0 exact pin) を tracked 化し symlink
- install_volta() を install_mise() (brew install, command -v で冪等) へ置換
- .Brewfile に mise を宣言として追記

Claude-Session: https://claude.ai/code/session_01TsSiv2WjaQE2Sjh8cxPwmS"
```

---

## Task 2: zshrc から Volta を撤去する

シェルの環境変数と PATH から Volta 参照を削除する。mise activation（`eval "$(mise activate zsh)"`）と PNPM_HOME（Volta 非依存）は維持する。

**Files:**
- Modify: `home/.zshrc`（環境変数ブロック / path 配列）

**Interfaces:**
- Consumes: なし（既存の mise activation 行 `eval "$(mise activate zsh)"` がツール解決を担う）。
- Produces: なし。

- [ ] **Step 1: Volta 環境変数ブロックを削除する**

`home/.zshrc` の以下 3 行（コメント + export + 直後の空行）を削除する:

```zsh
# Voltaの設定
export VOLTA_HOME="$HOME/.volta"

```

削除後、`export GOPATH="$HOME/.go"` の次が（空行を挟んで）`# pnpmの設定` になること。空行が 2 連続しないよう注意する。

- [ ] **Step 2: path 配列から Volta エントリを削除する**

`home/.zshrc` の path 配列内の以下 1 行を削除する:

```zsh
    $VOLTA_HOME/bin(N-/)
```

`$PNPM_HOME(N-/)` と `$HOME/.bun/bin(N-/)` は残し、その間の Volta 行のみ抜く。

- [ ] **Step 3: zsh が parse できるか確認する**

Run: `zsh -n home/.zshrc`
Expected: 出力なし・exit 0（構文 OK）。

- [ ] **Step 4: zshrc に Volta 参照が残らないことを確認する**

Run: `grep -ni 'volta' home/.zshrc || echo "NO VOLTA"`
Expected: `NO VOLTA`。

- [ ] **Step 5: コミットする**

```bash
git add home/.zshrc
git commit -m "build: zshrc から Volta の環境変数と PATH を撤去

- VOLTA_HOME export と path 配列の \$VOLTA_HOME/bin を削除
- mise activation と PNPM_HOME は維持 (Volta 非依存)

Claude-Session: https://claude.ai/code/session_01TsSiv2WjaQE2Sjh8cxPwmS"
```

---

## Task 3: README を Volta から mise へ更新する

ドキュメントの tools 一覧を mise に更新し、symlink テーブルに mise config の行を追加してテーブルと SYMLINK_PAIRS の drift を防ぐ。

**Files:**
- Modify: `README.md`（What Gets Installed / Tools 一覧、Dotfiles symlink テーブル）

**Interfaces:**
- Consumes: Task 1 で追加した SYMLINK_PAIRS エントリ（テーブル行はこれと一致させる）。
- Produces: なし。

- [ ] **Step 1: Tools 一覧の Volta 行を mise へ書き換える**

`README.md` の Tools 一覧:

```markdown
- [mise](https://mise.jdx.dev/) - dev tool / runtime version manager
```

（`- [Volta](https://volta.sh/) - Node.js version manager` を置換する）

- [ ] **Step 2: symlink テーブルに mise config の行を追加する**

`README.md` の Dotfiles symlink テーブル、`home/.config/git/.gitignore_global` の行の直後に追加する。列はテーブルの桁揃えに合わせる:

```markdown
| `home/.config/git/.gitignore_global`              | `~/.config/git/.gitignore_global`          |
| `home/.config/mise/config.toml`                   | `~/.config/mise/config.toml`               |
| `home/.claude/settings.json`                      | `~/.claude/settings.json`                  |
```

- [ ] **Step 3: README に Volta 参照が残らないことを確認する**

Run: `grep -ni 'volta' README.md || echo "NO VOLTA"`
Expected: `NO VOLTA`。

- [ ] **Step 4: コミットする**

```bash
git add README.md
git commit -m "docs: README の Node.js version manager を Volta から mise へ

- Tools 一覧を mise (https://mise.jdx.dev/) へ更新
- symlink テーブルに mise config 行を追加 (SYMLINK_PAIRS との drift 防止)

Claude-Session: https://claude.ai/code/session_01TsSiv2WjaQE2Sjh8cxPwmS"
```

---

## 受け入れ基準（全タスク完了後・PR 前に確認）

- `bats scripts/tests/` が 17/17 緑。
- `zsh -n home/.zshrc` が OK（exit 0）。
- `./bootstrap.sh -n` が `Installing mise...` と mise config の symlink 行を表示し、`Volta` を一切表示しない。
- `grep -rni 'volta' . --exclude-dir=.git --exclude-dir=docs` が 0 件（docs 配下の移行記録 spec/plan には "Volta" 文字列が残るため除外して判断）。
- gitleaks 緑（mise config に secret / user-path なし）。

## マシン実体の移行（手動手順・自動実行しない）

PR マージ後、各自のマシンで手動実行する。本計画では自動化しない。

1. dotfiles を反映し、`~/.config/mise/config.toml` が symlink になっていることを確認する（`ls -l ~/.config/mise/config.toml`）。
2. `mise install` で node 24.17.0 / pnpm 10.24.0 を install し、`mise current` で global に確定したことを確認する。
3. `which node` / `which pnpm` が mise 解決になり、Volta より優先されることを確認する。
4. 動作確認後、手動で `rm -rf ~/.volta` する。
5. wrangler 等 Volta の global package は必要時に手動再インストールする（`pnpm add -g wrangler` 等）。

## アップグレード運用

exact pin の upgrade は次の 3 手（数値変更だけでは取得されない点に留意）:

1. `home/.config/mise/config.toml` の該当バージョン数値を変更する。
2. `mise install`（symlink された global config を読んで新バージョンを取得）。
3. commit する。

`mise outdated` で現在 pin が最新から遅れているかを可視化できる。

## スコープ外

- `~/.volta` 実体の自動削除（手動手順のみ）。
- Volta global packages（wrangler 等）の自動移行。
- pnpm を corepack で管理する方式（mise tool 管理を採用）。
