#!/bin/bash

# Personal Dashboard - macOS App Builder
# ======================================
# This script builds a standalone macOS app using PyInstaller

set -e

echo "🚀 Building Personal Dashboard for macOS..."

# Check if we're in the right directory
if [ ! -f "../../src/main.py" ]; then
    echo "❌ Error: main.py not found. Run this script from packaging/macos/ directory."
    echo "Current directory: $(pwd)"
    echo "Looking for: ../../src/main.py"
    exit 1
fi

# Get the dashboard root path
DASHBOARD_ROOT="$(cd ../../ && pwd)"
echo "📁 Dashboard root: $DASHBOARD_ROOT"

# Create virtual environment for building if it doesn't exist
if [ ! -d "venv_build" ]; then
    echo "📦 Creating build environment..."
    python3 -m venv venv_build
fi

# Activate build environment
source venv_build/bin/activate

echo "📥 Installing build dependencies..."

# Install PyInstaller and dependencies
pip install --upgrade pip
pip install pyinstaller
pip install pywebview  # For WebKit window

# Install app dependencies
if [ -f "$DASHBOARD_ROOT/requirements.txt" ]; then
    pip install -r "$DASHBOARD_ROOT/requirements.txt"
else
    echo "⚠️  No requirements.txt found, installing common dependencies..."
    pip install fastapi uvicorn pydantic requests pyyaml jinja2
    pip install google-auth google-auth-oauthlib google-api-python-client
fi

echo "🔨 Building macOS app..."

# Clean previous builds
rm -rf dist build

# Set the dashboard root for the spec file
export DASHBOARD_ROOT="$DASHBOARD_ROOT"

# Build the app
pyinstaller dashboard.spec

# Check if build was successful
if [ -d "dist/Personal Dashboard.app" ]; then
    echo "✅ Build successful!"
    echo ""
    echo "📱 Your app is ready at: dist/Personal Dashboard.app"
    echo ""
    echo "🚀 To install:"
    echo "   1. Copy 'dist/Personal Dashboard.app' to /Applications/"
    echo "   2. Or double-click to run from current location"
    echo ""
    echo "⚙️  First run setup:"
    echo "   1. The app will create config files in your home directory"
    echo "   2. Edit ~/.personal-dashboard/credentials.yaml with your API keys"
    echo "   3. Configure your Obsidian vault path in the Settings section"
    echo ""
    echo "🔧 Troubleshooting:"
    echo "   - If the app won't open, try: 'xattr -dr com.apple.quarantine \"dist/Personal Dashboard.app\"'"
    echo "   - Check Console.app for error messages if needed"
else
    echo "❌ Build failed!"
    exit 1
fi

# Deactivate build environment
deactivate

echo "🎉 Build complete!"