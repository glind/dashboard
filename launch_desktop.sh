#!/bin/bash
# Simple launcher for desktop app

cd "$(dirname "$0")"

# Check if pywebview is installed
if ! python3 -c "import webview" 2>/dev/null; then
    echo "📦 Installing pywebview..."
    python3 -m pip install -q pywebview
fi

# Launch desktop app
python3 app_desktop.py
