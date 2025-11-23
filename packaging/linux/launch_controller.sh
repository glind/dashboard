#!/bin/bash
# Dashboard Controller Launcher
# Tries system tray version first, falls back to window version

cd "$(dirname "$0")"

# Try system tray version (requires AppIndicator)
if python3 -c "import gi; gi.require_version('AppIndicator3', '0.1')" 2>/dev/null; then
    echo "Launching system tray version..."
    ./dashboard_control.py
else
    echo "AppIndicator not available, launching window version..."
    ./dashboard_control_window.py
fi
