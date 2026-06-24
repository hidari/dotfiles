# Volta から mise への移行 設計

## 背景と目的

dotfiles は Node.js のバージョン管理に Volta を使っている（bootstrap が curl で install、zshrc が `VOLTA_HOME` を PATH に追加、README に記載）。一方 mise は既に brew で install 済みかつ zshrc で activate 済みで、Volta と mise が共存している状態。これを mise へ一本化し、ツールチェインを宣言的・再現可能にする。

移行は 2 レイヤーに分かれる。

- リポジトリの宣言（bootstrap / zshrc / README / Brewfile / mise config）を Volta から mise へ書き換える。これが再現性の source。
- 今のマシンの実体（`~/.volta` のツール群）の撤去は破壊的なので、自動化せず計画に手動手順として明記する。

## 確定した設計判断

- bootstrap は `install_volta()` を `install_mise()`（`brew install mise`、`command -v mise` で冪等）へ置換し、`.Brewfile` にも `mise` を追記して宣言の source とする。
- mise の global config を dotfiles で tracked にする（`home/.config/mise/config.toml` を symlink）。再現性を最優先する。
- mise へ移すのは node と pnpm のみ。wrangler 等の global npm package は対象外（必要時に手動再インストール）。
- node / pnpm は exact pin。config の数値が単一 source of truth となり完全再現する。
- Volta の撤去は dotfiles からの除去のみ。`~/.volta` 実体の削除は計画に手動手順として併記し、自動実行しない。

## 調査で確定した一次情報

- zshrc: `# Voltaの設定` + `export VOLTA_HOME="$HOME/.volta"`、path 配列に `$VOLTA_HOME/bin(N-/)`。別箇所で `eval "$(mise activate zsh)"` が既に有効。`PNPM_HOME` は pnpm の global bin 置き場で Volta 非依存。
- bootstrap.sh: `install_volta()` は curl install。確認メッセージと install シーケンスで参照。`brew bundle` は呼ばず、`.Brewfile` は `~/.Brewfile` へ symlink される宣言マニフェスト。各ツールは `install_*()` で個別 install。
- mise は brew 管理（command -v mise 済み）。global config（`~/.config/mise/config.toml`）は未作成で global pin 無し。
- mise の partial version 解決は「installed のうち prefix 一致の最新を使う」挙動。`node = "24"` は新しい 24.x が出ても自動取得せず、`mise install` / `mise up` が必要。exact pin なら「数値変更 + mise install + commit」が upgrade の全手順になる。
- bats（scripts/tests/bootstrap.bats）は `install_*` / volta を参照しない。install 系は副作用 curl でテスト対象外。symlink 機構は既存の create_symlink テストでカバー済み。

## 変更内容

### tracked mise config

`home/.config/mise/config.toml` を新規作成する。

```toml
[tools]
node = "24.17.0"
pnpm = "10.24.0"
```

`scripts/backup-tool` の SYMLINK_PAIRS パターンに倣い、bootstrap の `SYMLINK_PAIRS` に `home/.config/mise/config.toml|.config/mise/config.toml` を追加する。`setup_dotfiles` に `ensure_directory "$HOME/.config/mise"` を加える（git config と同じ扱い）。

### bootstrap.sh

`install_volta()` を `install_mise()` に置換する。

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

`install_homebrew` が先に走るので brew 依存は満たされる。確認メッセージ（"Install Homebrew, Rust, Volta, Claude Code"）と install シーケンス（`install_volta`）を mise に書き換える。

### .Brewfile

開発ツール節に `brew "mise"` を 1 行追記する（宣言の source）。

### zshrc

Volta ブロックを削除する。

- `# Voltaの設定` + `export VOLTA_HOME="$HOME/.volta"`
- path 配列の `$VOLTA_HOME/bin(N-/)`

`eval "$(mise activate zsh)"` と `PNPM_HOME` は維持する。

### README

Node.js version manager の記載を Volta から mise（`https://mise.jdx.dev/`）へ書き換える。

## アップグレード運用

exact pin の upgrade 手順は次の 3 手。

1. `home/.config/mise/config.toml` の該当バージョン数値を変更する。
2. `mise install`（symlink された global config を読んで新バージョンを取得）。
3. commit する。これでリポジトリが単一 source of truth となり、各マシンは pull + `mise install` で再現する。

`mise outdated` で現在 pin が最新から遅れているかを可視化できる。数値変更だけでは取得されない（必ず `mise install` を伴う）点に留意する。

## マシン実体の移行（手動手順、自動実行しない）

1. dotfiles を反映し、`~/.config/mise/config.toml` が symlink になっていることを確認する。
2. `mise install` で node 24.17.0 / pnpm 10.24.0 を install し、`mise current` で global に確定したことを確認する。
3. `which node` / `which pnpm` が mise 解決になり、Volta より優先されることを確認する。
4. 動作確認後、手動で `rm -rf ~/.volta` する（自動実行しない）。
5. wrangler 等 Volta の global package は必要時に手動再インストールする（`pnpm add -g wrangler` 等）。

## 検証

- `./bootstrap.sh -n`（dry-run）が "Install mise" を表示し "Volta" を表示しない。
- `bats scripts/tests/` が緑のまま。
- gitleaks が緑（mise config に秘匿情報なし）。
- リポジトリ全体に `volta` / `VOLTA_HOME` 参照が残らない（grep 0 件）。

## スコープ外

- `~/.volta` 実体の自動削除（手動手順のみ）。
- Volta global packages（wrangler 等）の自動移行。
- pnpm を corepack で管理する方式（mise tool 管理を採用）。
