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

### Dotfiles

ホームディレクトリに張る symlink の正本は `bootstrap.sh` の `SYMLINK_PAIRS`（source と target の対応）。
追加・変更はそこを編集する（README に一覧を再掲すると必ず drift するため載せない）。

Additionally, `home/.gitconfig.private.example` is copied to `~/.gitconfig.private` (if it doesn't exist).

## Claude Code 設定の管理 (skip-worktree 契約)

`home/.claude/settings.json` は `git update-index --skip-worktree` で管理しており、二重の状態を持つ。

- committed (HEAD): 公開して安全な curated subset。`/Users/<name>` パス・個人トグル・ローカル marketplace を含まない。
- working tree (`~/.claude/settings.json` の symlink 実体): 個人環境の live superset。

ローカル固有の設定を commit に混ぜないため、committed 側だけを編集するときは working file を触らず index の blob を差し替える。

```bash
# committed blob を取り出して編集し、index だけ差し替える
git show HEAD:home/.claude/settings.json > /tmp/settings.json
# /tmp/settings.json を編集する
SHA=$(git hash-object -w /tmp/settings.json)
git update-index --cacheinfo 100644,"$SHA",home/.claude/settings.json
git diff --cached home/.claude/settings.json   # 差分が意図通りか検証する
git commit -m "..."
git update-index --skip-worktree home/.claude/settings.json
```

committed 側は CI で 2 つの仕組みが守る。

- gitleaks: secret とユーザー名パス (`/Users/<name>`) の漏洩を検出する。
- config-guard: 構造 curation (禁止キー・directory marketplace・dead config・不正なツール名) を検出する。

## tirith によるコマンドセキュリティ

`tirith`（URL/コマンドセキュリティ CLI, mise 管理）で実行前チェックを二層に張る。

- 対話シェル: `home/.zshrc` の `tirith init` が zsh のコマンド実行前に検査する。
- Claude Code: `home/.claude/hooks/tirith-check.py` を PreToolUse(Bash) フックに登録し、エージェントの Bash 実行前に `tirith check` へ委譲する。判定ロジックとテストは `scripts/tirith-hook` を参照。

## Testing

```bash
# bootstrap (bats)
bats scripts/tests/

# backup-tool (Python / pytest)
uv run --directory scripts/backup-tool pytest -q

# config-guard (Python / pytest)
uv run --directory scripts/config-guard pytest -q

# config-guard スキャン (skills + settings の stale 参照・構造逸脱検出)
uv run --directory scripts/config-guard config-guard .

# tirith-hook (Python / pytest) — Claude Code PreToolUse フックの統合テスト
uv run --directory scripts/tirith-hook pytest -q
```
