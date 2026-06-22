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

| Source                                            | Target                                     |
|---------------------------------------------------|--------------------------------------------|
| `home/.Brewfile`                                  | `~/.Brewfile`                              |
| `home/.zshrc`                                     | `~/.zshrc`                                 |
| `home/.gitconfig`                                 | `~/.gitconfig`                             |
| `home/.config/git/.gitignore_global`              | `~/.config/git/.gitignore_global`          |
| `home/.claude/settings.json`                      | `~/.claude/settings.json`                  |
| `home/.claude/statusline-command.sh`              | `~/.claude/statusline-command.sh`          |
| `home/.claude/CLAUDE.md`                          | `~/.claude/CLAUDE.md`                      |
| `home/.claude/.mcp.json`                          | `~/.claude/.mcp.json`                      |
| `home/.claude/skills`                             | `~/.claude/skills`                         |
| `scripts/backup-tool/backup.sh`                   | `~/.local/bin/backup.sh`                   |
| `scripts/util-tools/small-id-gen/small-id-gen.sh` | `~/.local/bin/small-id-gen`                |

Additionally, `home/.gitconfig.private.example` is copied to `~/.gitconfig.private` (if it doesn't exist).

## Testing

```bash
# bootstrap (bats)
bats scripts/tests/

# backup-tool (Python / pytest)
uv run --directory scripts/backup-tool pytest -q
```
