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
- [Volta](https://volta.sh/) - Node.js version manager
- [Claude Code](https://claude.ai/code) - AI coding assistant

### Dotfiles

The following symlinks are created in your home directory:

| Source                               | Target                            |
|--------------------------------------|-----------------------------------|
| `home/.Brewfile`                     | `~/.Brewfile`                     |
| `home/.zshrc`                        | `~/.zshrc`                        |
| `home/.gitconfig`                    | `~/.gitconfig`                    |
| `home/.config/git/.gitignore_global` | `~/.config/git/.gitignore_global` |
| `home/.claude/settings.json`         | `~/.claude/settings.json`         |
| `home/.claude/statusline-command.sh` | `~/.claude/statusline-command.sh` |
| `home/.claude/CLAUDE.md`             | `~/.claude/CLAUDE.md`             |
| `home/.claude/.mcp.json`             | `~/.claude/.mcp.json`             |
| `home/.claude/skills`                | `~/.claude/skills`                |
| `home/.claude/plugins/security-blue-red-team` | `~/.claude/plugins/security-blue-red-team` |
| `scripts/backup-tool/backup.sh`      | `~/.local/bin/backup.sh`          |
| `scripts/util-tools/small-id-gen/small-id-gen.sh` | `~/.local/bin/small-id-gen` |

Additionally, `home/.gitconfig.private.example` is copied to `~/.gitconfig.private` (if it doesn't exist).

## Claude Code Plugins

How the bundled Claude Code plugins load, and the development / bootstrap workflow, is documented in [`home/.claude/plugins/README.md`](home/.claude/plugins/README.md). Note that the plugin marketplace registration in `settings.json` is kept machine-local via `git update-index --skip-worktree` and is **not** committed (it contains a machine-specific absolute path).

## Testing

```bash
# Run all tests
bats scripts/tests/

# Run specific test file
bats scripts/tests/bootstrap.bats
bats scripts/tests/backup.bats
```
