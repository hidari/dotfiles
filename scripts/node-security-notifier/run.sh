#!/usr/bin/env bash
# node-security-notifier を launchd 環境から起動する薄い wrapper。
# launchd の最小 PATH でも uv を解決できるよう主要パスを補う。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PATH="/opt/homebrew/bin:$HOME/.local/bin:$HOME/.cargo/bin:$PATH"

exec uv run --directory "$SCRIPT_DIR" node-security-notifier
