#!/usr/bin/env bash
"""
Setup script for obsidian-vault skill.
Installs the CLI tool and verifies vault structure.
"""

set -euo pipefail

VAULT_PATH="~/obsidian-vault"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLI_SOURCE="$SCRIPT_DIR/obsidian-cli.py"
CLI_TARGET="~/.local/bin/obsidian"

echo "🔧 Setting up obsidian-vault skill..."

# Create vault structure if not exists
echo "📁 Creating vault structure..."
mkdir -p "$VAULT_PATH"/{Inbox,Projects,Areas,Resources,Archives,Templates,Daily}
mkdir -p "$VAULT_PATH/.obsidian"

# Create symlink for CLI
echo "🔗 Installing CLI tool..."
mkdir -p "$(dirname "$CLI_TARGET")"
cp "$CLI_SOURCE" "$CLI_TARGET"
chmod +x "$CLI_TARGET"
echo "   Installed to $CLI_TARGET"

# Verify installation
echo "✅ Verifying installation..."
if command -v obsidian &> /dev/null; then
    echo "   obsidian command available"
    obsidian stats
else
    echo "   ⚠️  Add ~/.local/bin to PATH to use 'obsidian' command directly"
    echo "   export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""
echo "✨ Setup complete!"
echo ""
echo "Usage:"
echo "  obsidian daily              # Open/create today's daily note"
echo "  obsidian new -t Project \"Title\"  # Create project note"
echo "  obsidian search \"query\"     # Search vault"
echo "  obsidian random -s          # Random note with content"
echo "  obsidian stats              # Vault statistics"
echo ""
echo "Vault location: $VAULT_PATH"