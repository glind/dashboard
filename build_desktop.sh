#!/bin/bash
# Build script for Personal Dashboard Desktop App

set -e  # Exit on error

echo "🏗️  Building Personal Dashboard Desktop App"
echo "==========================================="

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="FounderDashboard"
VERSION="0.5.0"
PYTHON_VERSION="3.11"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${BLUE}📦 Creating virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${BLUE}🔧 Activating virtual environment...${NC}"
source venv/bin/activate

# Install/update dependencies
echo -e "${BLUE}📦 Installing dependencies...${NC}"
pip install --upgrade pip
pip install -r requirements.txt
pip install pywebview pyinstaller pillow

# Check if pywebview is installed
if ! python -c "import webview" 2>/dev/null; then
    echo -e "${RED}❌ pywebview installation failed${NC}"
    exit 1
fi

echo -e "${GREEN}✅ Dependencies installed${NC}"

# Clean previous builds
echo -e "${BLUE}🧹 Cleaning previous builds...${NC}"
rm -rf build dist *.spec

# Use Buildly logo as icon
if [ -f "assets/images/buildly-new-logo.png" ]; then
    echo -e "${BLUE}🎨 Using Buildly logo as app icon...${NC}"
    
    # Convert Buildly logo to ICNS for macOS
    echo -e "${BLUE}🍎 Creating macOS icon from Buildly logo...${NC}"
    mkdir -p assets/icon.iconset
    
    # Create different sizes for iconset
    sips -z 16 16     assets/images/buildly-new-logo.png --out assets/icon.iconset/icon_16x16.png
    sips -z 32 32     assets/images/buildly-new-logo.png --out assets/icon.iconset/icon_16x16@2x.png
    sips -z 32 32     assets/images/buildly-new-logo.png --out assets/icon.iconset/icon_32x32.png
    sips -z 64 64     assets/images/buildly-new-logo.png --out assets/icon.iconset/icon_32x32@2x.png
    sips -z 128 128   assets/images/buildly-new-logo.png --out assets/icon.iconset/icon_128x128.png
    sips -z 256 256   assets/images/buildly-new-logo.png --out assets/icon.iconset/icon_128x128@2x.png
    sips -z 256 256   assets/images/buildly-new-logo.png --out assets/icon.iconset/icon_256x256.png
    sips -z 512 512   assets/images/buildly-new-logo.png --out assets/icon.iconset/icon_256x256@2x.png
    sips -z 512 512   assets/images/buildly-new-logo.png --out assets/icon.iconset/icon_512x512.png
    
    # Create ICNS file
    iconutil -c icns assets/icon.iconset -o assets/icon.icns
    rm -rf assets/icon.iconset
    
    echo -e "${GREEN}✅ Buildly logo icon created${NC}"
elif [ -f "assets/icon.icns" ]; then
    echo -e "${BLUE}🎨 Using existing icon file${NC}"
else
    echo -e "${RED}❌ No icon found${NC}"
    exit 1
fi

# Build with PyInstaller
echo -e "${BLUE}🔨 Building application with PyInstaller...${NC}"

pyinstaller \
    --name="${APP_NAME}" \
    --windowed \
    --onefile \
    --icon=assets/icon.icns \
    --add-data="src:src" \
    --add-data="src/templates:src/templates" \
    --add-data="src/static:src/static" \
    --add-data="config:config" \
    --hidden-import=uvicorn \
    --hidden-import=fastapi \
    --hidden-import=webview \
    --hidden-import=pydantic \
    --hidden-import=sqlalchemy \
    --collect-all=fastapi \
    --collect-all=uvicorn \
    --noconfirm \
    app_desktop.py

echo -e "${GREEN}✅ Build complete!${NC}"
echo ""
echo -e "${BLUE}📦 Application built to: ${GREEN}dist/${APP_NAME}.app${NC}"
echo ""
echo "To run the app:"
echo "  open dist/${APP_NAME}.app"
echo ""
echo "To create a DMG installer:"
echo "  ./build_installer.sh"
echo ""
