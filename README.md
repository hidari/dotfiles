# dotfiles

This is my own dotfiles repository.
To use it, clone it and put a symbolic link to your home directory.

## Setup

```bash
# install automatically
cd ~/path/to/dotfiles
./bootstrap.sh
```

```bash
# install pre-requirements
cd ~/path/to/dotfiles
./bootstrap.sh

# tools
ln -sf "$PWD/home/.Brewfile" ~/.Brewfile
brew bundle --global

# directories
mkdir -p ~/.claude/skills
mkdir -p ~/.config/git

# dotfiles
ln -sf "$PWD/home/.zshrc" ~/.zshrc
ln -sf "$PWD/home/.gitconfig" ~/.gitconfig
ln -sf "$PWD/home/.config/git/.gitignore_global" ~/.config/git/.gitignore_global
ln -sf "$PWD/home/.claude/settings.json" ~/.claude/settings.json
ln -sf "$PWD/home/.claude/CLAUDE.md" ~/.claude/CLAUDE.md
ln -sf "$PWD/home/.claude/.mcp.json" ~/.claude/.mcp.json

# copy and edit your personal Git configuration
cp "$PWD/home/.gitconfig.private.example" ~/.gitconfig.private

# claude skills (link each skill directory)
for skill in "$PWD/home/.claude/skills"/*/; do
  ln -sf "$skill" ~/.claude/skills/
done

# backup script
# See scripts/README.md for details.
mkdir -p ~/.local/bin
ln -sf "$PWD/scripts/backup.sh" ~/.local/bin/backup.sh
```
