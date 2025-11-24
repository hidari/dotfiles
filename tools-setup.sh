#!/bin/zsh

echo "This script will install:"
echo "  - Homebrew: https://brew.sh/"
echo "  - Rust (rustup): https://rustup.rs/"
echo "  - Deno: https://deno.land/"
echo "  - Volta (Node.js version manager): https://volta.sh/"
echo ""
echo -n "Continue? (y/N): "
read -r REPLY
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 0
fi

# Homebrew
echo ""
echo "Installing Homebrew..."
if command -v brew &> /dev/null; then
    echo "Homebrew is already installed. Skipping..."
else
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Rust (rustup)
echo ""
echo "Installing Rust..."
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y

# Deno
echo ""
echo "Installing Deno..."
curl -fsSL https://deno.land/install.sh | sh

# Volta (Node.js version manager)
echo ""
echo "Installing Volta..."
curl https://get.volta.sh | bash

echo ""
echo "Setup complete!"
echo "Run the following to update your PATH:"
echo "  source ~/.zshrc  # or your shell config file"
