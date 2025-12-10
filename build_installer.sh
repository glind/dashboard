#!/bin/bash
# Create macOS DMG installer for Personal Dashboard

set -e

echo "📀 Creating DMG Installer"
echo "========================="

APP_NAME="PersonalDashboard"
VERSION="1.0.0"
DMG_NAME="${APP_NAME}-${VERSION}.dmg"
VOLUME_NAME="Personal Dashboard"

# Check if app exists
if [ ! -d "dist/${APP_NAME}.app" ]; then
    echo "❌ App not found. Run ./build_desktop.sh first"
    exit 1
fi

# Create temporary DMG directory
echo "📁 Creating temporary directory..."
mkdir -p dist/dmg
rm -rf dist/dmg/*

# Copy app to DMG directory
echo "📦 Copying application..."
cp -R "dist/${APP_NAME}.app" dist/dmg/

# Create Applications symlink
echo "🔗 Creating Applications symlink..."
ln -s /Applications dist/dmg/Applications

# Create DMG
echo "💿 Creating DMG..."
hdiutil create \
    -volname "${VOLUME_NAME}" \
    -srcfolder dist/dmg \
    -ov \
    -format UDZO \
    "dist/${DMG_NAME}"

# Clean up
echo "🧹 Cleaning up..."
rm -rf dist/dmg

echo ""
echo "✅ DMG created: dist/${DMG_NAME}"
echo ""
echo "To install:"
echo "  1. Open dist/${DMG_NAME}"
echo "  2. Drag Personal Dashboard to Applications"
echo "  3. Open from Applications folder"
echo ""
