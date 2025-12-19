#!/bin/bash
# Quick voice system installer - detects OS and runs appropriate setup

set -e

echo "╔════════════════════════════════════════════════════════════╗"
echo "║                                                            ║"
echo "║   🤖 ROGR VOICE SYSTEM INSTALLER                          ║"
echo "║                                                            ║"
echo "║   Battle-droid style voice assistant for your dashboard   ║"
echo "║                                                            ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""

# Detect operating system
OS="$(uname -s)"
case "${OS}" in
    Linux*)
        echo "Detected: Linux"
        ./scripts/setup_voice.sh
        ;;
    Darwin*)
        echo "Detected: macOS"
        ./scripts/setup_voice_macos.sh
        ;;
    CYGWIN*|MINGW*|MSYS*)
        echo "Detected: Windows"
        echo ""
        echo "Please run: scripts\\setup_voice_windows.bat"
        echo ""
        exit 0
        ;;
    *)
        echo "Unknown operating system: ${OS}"
        echo "Please manually run the appropriate setup script:"
        echo "  - Linux: ./scripts/setup_voice.sh"
        echo "  - macOS: ./scripts/setup_voice_macos.sh"
        echo "  - Windows: scripts\\setup_voice_windows.bat"
        exit 1
        ;;
esac

echo ""
echo "╔════════════════════════════════════════════════════════════╗"
echo "║  ✨ Installation Complete!                                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo ""
echo "1. Test the installation:"
echo "   ./scripts/test_voice.sh"
echo ""
echo "2. Try the interactive demo:"
echo "   python3 scripts/demo_voice.py"
echo ""
echo "3. Configure settings in config/config.yaml:"
echo "   voice:"
echo "     enabled: true"
echo "     default_style: \"droid\""
echo ""
echo "4. Start the dashboard:"
echo "   ./ops/startup.sh"
echo ""
echo "   You'll hear: \"Dashboard initialization complete. Roger, roger.\""
echo ""
echo "📚 Documentation:"
echo "   - Quick Start: VOICE_QUICK_START.md"
echo "   - Full Docs: devdocs/VOICE_SYSTEM.md"
echo "   - Summary: VOICE_IMPLEMENTATION_SUMMARY.md"
echo ""
echo "🎤 Voice Commands:"
echo "   Say \"Roger, show status\" to control the dashboard"
echo ""
echo "Roger, roger! 🤖"
