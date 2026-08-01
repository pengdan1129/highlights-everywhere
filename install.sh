#!/bin/bash
# ============================================
# Highlights Everywhere - One-click Installer
# ============================================
set -e

echo "📌 Highlights Everywhere Installer"
echo "=================================="

# 1. Create scripts directory
mkdir -p ~/scripts

# 2. Install CLI tool
echo "📝 Installing CLI tool..."
cp hl ~/scripts/hl
chmod +x ~/scripts/hl
echo "  -> ~/scripts/hl"

# 3. Install server
echo "🖥️  Installing server..."
cp hl-server.py ~/scripts/hl-server.py
chmod +x ~/scripts/hl-server.py
echo "  -> ~/scripts/hl-server.py"

# 4. Install launchd service (auto-start on login)
echo "🚀 Installing auto-start service..."
mkdir -p ~/Library/LaunchAgents
cp com.highlights.server.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.highlights.server.plist 2>/dev/null || true
echo "  -> ~/Library/LaunchAgents/com.highlights.server.plist"

# 5. Create highlights directory (local only; mobile reading via Apple Notes sync)
mkdir -p ~/Highlights
echo "  -> ~/Highlights/ (local; phone reading via Notes app)"

# 6. Add PATH to shell config
if ! grep -q 'scripts/hl' ~/.zshrc 2>/dev/null; then
    echo '' >> ~/.zshrc
    echo '# hl - Highlights Everywhere' >> ~/.zshrc
    echo 'export PATH="$HOME/scripts:$PATH"' >> ~/.zshrc
    echo 'alias hlweb="hl server"' >> ~/.zshrc
    echo '  -> Added PATH and alias to ~/.zshrc'
fi

# 7. Add hl-ext bookmarklet / Tampermonkey instructions
echo ""
echo "=================================="
echo "✅ Installation complete!"
echo "=================================="
echo ""
echo "📌 Next steps:"
echo ""
echo "  Option A - Browser auto-highlight (recommended):"
echo "    1. Install Tampermonkey for Chrome/Safari"
echo "    2. Open http://localhost:8899/highlight.user.js"
echo "    3. Click 'Install' when prompted"
echo ""
echo "  Option B - Bookmarklet (no extension needed):"
echo "    1. Open http://localhost:8899/install"
echo "    2. Drag 'HL Highlight' to your bookmarks bar"
echo ""
echo "📖 Usage:"
echo "  hl \"text\"         - Save a highlight"
echo "  hl search <q>     - Search highlights"
echo "  hl list           - List recent highlights"
echo "  hlweb             - Open web UI"
echo "  Cmd+Space         - Search via Spotlight"
echo ""
echo "🎨 Server running at: http://localhost:8899"
echo ""
