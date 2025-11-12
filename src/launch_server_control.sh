#!/bin/bash
# Server Control Panel Launcher
# Launches the native Python server control application

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DASHBOARD_DIR="$(dirname "$SCRIPT_DIR")"

echo "🖥️ Starting Python Server Control Panel..."

# Check if we're in a virtual environment, if not, try to activate one
if [[ "$VIRTUAL_ENV" == "" ]]; then
    if [[ -f "$DASHBOARD_DIR/.venv/bin/activate" ]]; then
        echo "🐍 Activating virtual environment..."
        source "$DASHBOARD_DIR/.venv/bin/activate"
    elif [[ -f "$DASHBOARD_DIR/venv/bin/activate" ]]; then
        echo "🐍 Activating virtual environment..."
        source "$DASHBOARD_DIR/venv/bin/activate"
    fi
fi

# Install required packages if not available
python3 -c "import tkinter, requests" 2>/dev/null || {
    echo "📦 Installing required packages..."
    pip install requests 2>/dev/null || pip3 install requests
}

# Launch the app
echo "🚀 Launching Server Control Panel..."
cd "$SCRIPT_DIR"
python3 server_control_app.py

echo "👋 Server Control Panel closed."