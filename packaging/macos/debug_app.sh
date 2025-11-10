#!/bin/bash

# Debug launcher for Personal Dashboard macOS App
# ==============================================
# This script helps debug issues with the macOS app

echo "🔍 Personal Dashboard - Debug Mode"
echo "================================="

APP_PATH="/Users/greglind/Projects/me/dashboard/packaging/macos/dist/Personal Dashboard.app"

if [ ! -d "$APP_PATH" ]; then
    echo "❌ App not found at: $APP_PATH"
    echo "Make sure you've built the app first with ./install_macos.sh"
    exit 1
fi

echo "✅ Found app at: $APP_PATH"
echo ""

# Check if the app is properly signed
echo "📝 Checking app signature..."
codesign -dv "$APP_PATH" 2>&1

echo ""
echo "📋 App bundle contents:"
ls -la "$APP_PATH/Contents/"

echo ""
echo "📋 MacOS directory contents:"
ls -la "$APP_PATH/Contents/MacOS/"

echo ""
echo "🚀 Launching app with debug output..."
echo "Press Ctrl+C to stop"
echo ""

# Launch the app and capture output
"$APP_PATH/Contents/MacOS/Personal Dashboard" 2>&1

echo ""
echo "🔍 Debug session ended."