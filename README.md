# dotfiles

This is my own dotfiles repository.

## Quick Start

```bash
cd ~/Develop/dotfiles
./bootstrap.sh
```

## Usage

```bash
# Interactive mode (recommended for first setup)
./bootstrap.sh

# Non-interactive mode (for CI/automation)
./bootstrap.sh -y

# Dotfiles only (skip tool installation)
./bootstrap.sh --dotfiles-only

# Dry-run mode (preview changes without executing)
./bootstrap.sh -n

# Force mode (backup and overwrite existing files)
./bootstrap.sh -f
```

## Options

| Option            | Description                                    |
|-------------------|------------------------------------------------|
| `-y`, `--yes`     | Skip confirmation prompts                      |
| `-f`, `--force`   | Force overwrite existing files (with backup)   |
| `-n`, `--dry-run` | Show what would be done without making changes |
| `--dotfiles-only` | Skip tool installation, only setup dotfiles    |
| `-h`, `--help`    | Show help message                              |

## What Gets Installed

### Tools

- [Homebrew](https://brew.sh/) - Package manager
- [Rust](https://rustup.rs/) - Rust toolchain
- [mise](https://mise.jdx.dev/) - dev tool / runtime version manager
- [Claude Code](https://claude.ai/code) - AI coding assistant
- Claude Code plugins - the marketplaces and plugins declared in `home/.claude/settings.json` (`extraKnownMarketplaces` + `enabledPlugins`) are registered and installed via `claude plugin`
- [apm](https://github.com/microsoft/apm) - Agent Package Manager (skill/plugin の宣言的配信)

### Dotfiles

ホームディレクトリに張る symlink の正本は `bootstrap.sh` にある（source と target の対応）。
追加・変更はそこを編集する（README に一覧を再掲すると必ず drift するため載せない）。

- `SYMLINK_PAIRS`: source をリポジトリに持つもの。dotfiles 本体。
- `APM_SYMLINK_PAIRS`: source を apm が配置するもの。`apm install` の前は実体が無いので、
  存在するときだけ張る。

追加の Claude 設定ディレクトリ向けの pair は配列に書かず、既定の `.claude/` 向け pair から
生成する。一覧は追跡外のローカル設定ファイルから読む（ディレクトリ名をこのリポジトリへ
書かないための外部化）。

Additionally, `home/.gitconfig.private.example` is copied to `~/.gitconfig.private` (if it doesn't exist).

## Claude Code 設定の管理

`home/.claude/settings.json` は `~/.claude/settings.json` から symlink されており、リポジトリ内のファイルがそのまま live 設定である。committed と live は 1 本で、普通のファイルとして編集してコミットする。

以前は `git update-index --skip-worktree` で両者を分けていた。分ける理由はローカル絶対パスを持つ directory source の marketplace 宣言と、そこから来る plugin エントリの 2 つだったが、skill と plugin の供給を apm へ移したことで両方消えたため廃止した。

Claude Code は起動中に settings.json を書き換えることがある (承認した MCP サーバの記録など)。skip-worktree が無くなったのでその書き換えは `git status` に差分として現れる。意図しない差分はコミットせず `git checkout -- home/.claude/settings.json` で戻す。committed に置けないものの定義は config-guard の不変条件 (`scripts/config-guard/src/config_guard/settings_invariants.py`) が正本なので README には再掲しない。

config-guard は settings.json だけ working tree ではなく git の index から読む (`git show :home/.claude/settings.json`)。検査したいのはコミットされようとしている内容であって、未 stage の書き換えではないためである。skill や apm.yml など他の検査対象は working tree を読む。

committed 側は CI で 2 つの仕組みが守る。

- gitleaks: secret とユーザー名パス (`/Users/<name>`) の漏洩を検出する。
- config-guard: 構造 curation (禁止キー・directory marketplace・dead config・不正なツール名) を検出する。

## tirith によるコマンドセキュリティ

`tirith`（URL/コマンドセキュリティ CLI, mise 管理）で実行前チェックを二層に張る。

- 対話シェル: `home/.zshrc` の `tirith init` が zsh のコマンド実行前に検査する。
- Claude Code: `home/.claude/hooks/tirith-check.py` を PreToolUse(Bash) フックに登録し、エージェントの Bash 実行前に `tirith check` へ委譲する。判定ロジックとテストは `scripts/tirith-hook` を参照。

## apm による skill 配信 (vendored skills)

一部の Claude Code skill は自作せず、upstream から apm (Agent Package Manager) 経由で取り込む。宣言の正本は `home/apm.yml`、解決した commit と content hash の pin は `home/apm.lock.yaml`。

- 取り込み: `home/` で `apm install --frozen`（bootstrap の `install_apm_packages` が実行）。commit SHA pin で再現性を担保する。
- deploy 先 skill (`home/.claude/skills/<name>/`) と fetch キャッシュ (`home/apm_modules/`) は再生成物なので gitignore する（`home/.gitignore`）。gitignore の追記漏れは config-guard が apm.lock.yaml の deployed_files と突合して検出する。自作 skill は従来どおり tracked。
- upstream 追従は `apm outdated` / `apm update` で確認・更新する。
- apm 管理 skill は gitignore されるため fresh checkout（CI 含む）では未展開で、config-guard の allowed-tools 検査対象外。整合性は apm.lock.yaml の content_hash pin と `apm audit --ci` で担保する（自作 skill の config-guard 検査とはスコープを分離）。

## Testing

```bash
# all suites (bats)
bats scripts/tests/

# backup-tool (Python / pytest)
uv run --directory scripts/backup-tool pytest -q

# config-guard (Python / pytest)
uv run --directory scripts/config-guard pytest -q

# config-guard スキャン (skills + settings の stale 参照・構造逸脱検出)
# ここだけ --directory ではなく --project を使う。--directory は cwd を移すため引数の `.` が
# リポジトリルートを指さなくなり、skills の glob が 0 件のまま成功表示になる。
uv run --project scripts/config-guard config-guard .

# tirith-hook (Python / pytest) — Claude Code PreToolUse フックの統合テスト
uv run --directory scripts/tirith-hook pytest -q

# ast-grep (構文レベル lint)。どちらのフラグも外すと結果が嘘になる
# --skip-snapshot-tests: rules/ はスナップショットを持たないので、外すと baseline 不在で全件 fail する
# --no-ignore hidden: 既定で隠しディレクトリを飛ばすので、外すと home/.config 配下を 1 件も見ずに exit 0
ast-grep test --skip-snapshot-tests
ast-grep scan --no-ignore hidden

# apm 配信 skill の lockfile 整合性 / drift ゲート (違反時 exit 1)
( cd home && apm audit --ci )
```
