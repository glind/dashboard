#!/bin/bash
# Install macOS Dashboard Control App

set -e

echo "🍎 Installing Dashboard Controller for macOS..."
echo "===================================="

# Install rumps (menu bar app framework)
echo "📦 Installing Python dependencies..."
pip3 install --user rumps requests

# Make executable
chmod +x dashboard_control.py

echo ""
echo "✅ Installation complete!"
echo ""
echo "To run:"
echo "  python3 dashboard_control.py"
echo ""
echo "To add to login items:"
echo "  1. Open System Preferences → Users & Groups"
echo "  2. Click 'Login Items' tab"
echo "  3. Click '+' and add 'dashboard_control.py'"
echo ""
