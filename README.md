# dotfiles

This is my own dotfiles repository.
To use it, clone it and put a symbolic link to your home directory.

## Setup

```bash
# install pre-requirements
cd ~/path/to/dotfiles
./bootstrap.sh

# tools
ln -sf ~/path/to/dotfiles/.Brewfile ~/.Brewfile
brew bundle --global

# directories
mkdir -p ~/.claude
mkdir -p ~/.config/git

# dotfiles
ln -sf ~/path/to/dotfiles/.zshrc ~/.zshrc
ln -sf ~/path/to/dotfiles/.gitconfig ~/.gitconfig
ln -sf ~/path/to/dotfiles/.config/.gitignore_global ~/.config/git/.gitignore_global
ln -sf ~/path/to/dotfiles/.claude/settings.json ~/.claude/settings.json
ln -sf ~/path/to/dotfiles/.claude/CLAUDE.md ~/.claude/CLAUDE.md

# copy and edit your personal Git configuration
cp ~/path/to/dotfiles/.gitconfig.private.example ~/.gitconfig.private

# claude skills
mkdir -p ~/.claude/skills/{code-reviewer, frontend-designer}
ln -sf ~/path/to/dotfiles/.claude/skills/code-reviewer/SKILL.md ~/.claude/skills/code-reviewer/SKILL.md
ln -sf ~/path/to/dotfiles/.claude/skills/frontend-designer/SKILL.md ~/.claude/skills/frontend-designer/SKILL.md

# backup script
# See scripts/README.md for details.
mkdir -p ~/.local/bin
ln -sf ~/path/to/dotfiles/scripts/backup.sh ~/.local/bin/backup.sh
```
