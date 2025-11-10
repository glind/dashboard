#!/bin/bash

# Quick installer for Personal Dashboard macOS App
# ================================================

echo "🏗️  Personal Dashboard - macOS App Builder"
echo "==========================================="
echo ""

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is required but not found."
    echo "Please install Python 3 from https://python.org"
    exit 1
fi

echo "✅ Python 3 found"

# Determine if we're in the right directory and adjust paths
if [ -f "build_macos_app.sh" ]; then
    # We're in packaging/macos/ directory
    BUILD_SCRIPT="./build_macos_app.sh"
    DASHBOARD_ROOT="../../"
    echo "✅ Running from packaging/macos/ directory"
elif [ -f "packaging/macos/build_macos_app.sh" ]; then
    # We're in dashboard root directory  
    BUILD_SCRIPT="./packaging/macos/build_macos_app.sh"
    DASHBOARD_ROOT="./"
    echo "✅ Running from dashboard root directory"
else
    echo "❌ Error: Could not find build_macos_app.sh"
    echo ""
    echo "Please run this script from either:"
    echo "  • Dashboard root: ./packaging/macos/install_macos.sh"
    echo "  • macOS directory: cd packaging/macos && ./install_macos.sh"
    exit 1
fi

# Verify we can find the main dashboard files
if [ ! -f "${DASHBOARD_ROOT}src/main.py" ]; then
    echo "❌ Error: Cannot find src/main.py at ${DASHBOARD_ROOT}src/main.py"
    echo "Make sure you're running from the correct dashboard directory"
    exit 1
fi

echo "✅ Found dashboard source files"

# Change to packaging/macos directory if we're not already there
if [ ! -f "build_macos_app.sh" ]; then
    cd packaging/macos
fi

echo "📋 This will:"
echo "  1. Create a build environment"
echo "  2. Install required dependencies"
echo "  3. Build Personal Dashboard.app"
echo "  4. Create a standalone macOS application"
echo ""

read -p "Continue? (y/N): " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "🚀 Starting build process..."

# Run the build script
./build_macos_app.sh

if [ $? -eq 0 ]; then
    echo ""
    echo "🎉 SUCCESS! Your Personal Dashboard app has been built."
    echo ""
    echo "📱 Next steps:"
    echo "  1. Open Finder and navigate to this folder"
    echo "  2. Look for 'dist/Personal Dashboard.app'"
    echo "  3. Copy it to your Applications folder (optional)"
    echo "  4. Double-click to launch!"
    echo ""
    echo "⚙️  First-time setup:"
    echo "  1. The app will create config files in ~/.personal-dashboard/"
    echo "  2. Configure your API keys in ~/.personal-dashboard/credentials.yaml"
    echo "  3. Set your Obsidian vault path in the app's Settings section"
    echo ""
    
    # Ask if user wants to open the dist folder
    read -p "Open dist folder now? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        open dist/
    fi
else
    echo ""
    echo "❌ Build failed. Please check the error messages above."
    exit 1
fi