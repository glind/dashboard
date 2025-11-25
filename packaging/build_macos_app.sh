#!/bin/bash
#
# Build Buildly Forge Controller as macOS .app bundle
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="Forge Controller"
BUNDLE_ID="com.buildly.forge.controller"

echo "Building Forge Controller .app bundle for macOS..."
echo "=================================================="

# Check if PyInstaller is installed
if ! python3 -c "import PyInstaller" 2>/dev/null; then
    echo "Installing PyInstaller..."
    pip3 install pyinstaller
fi

# Create spec file for PyInstaller
cat > "$SCRIPT_DIR/forge_controller.spec" << 'EOF'
# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['forge_controller_app.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('forge_controller/*.py', 'forge_controller'),
        ('forge_controller/forge-logo.png', 'forge_controller'),
    ],
    hiddenimports=['rumps'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Forge Controller',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='forge_controller/forge-logo.png'
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Forge Controller',
)

app = BUNDLE(
    coll,
    name='Forge Controller.app',
    icon='forge_controller/forge-logo.png',
    bundle_identifier='com.buildly.forge.controller',
    info_plist={
        'NSPrincipalClass': 'NSApplication',
        'NSAppleScriptEnabled': False,
        'LSBackgroundOnly': False,
        'LSUIElement': '1',  # Makes it a menu bar only app (no dock icon by default)
        'CFBundleName': 'Forge Controller',
        'CFBundleDisplayName': 'Buildly Forge Controller',
        'CFBundleGetInfoString': 'Buildly Forge Controller - Service Manager',
        'CFBundleVersion': '1.0.0',
        'CFBundleShortVersionString': '1.0.0',
        'NSHumanReadableCopyright': 'Copyright © 2025 Buildly',
    },
)
EOF

# Build the app
echo "Running PyInstaller..."
pyinstaller --clean forge_controller.spec

if [ -d "dist/Forge Controller.app" ]; then
    echo ""
    echo "✅ Build successful!"
    echo ""
    echo "App location: $SCRIPT_DIR/dist/Forge Controller.app"
    echo ""
    echo "To install:"
    echo "  1. Drag 'Forge Controller.app' to Applications folder"
    echo "  2. Or run: open 'dist/Forge Controller.app'"
    echo ""
    echo "To add to Login Items:"
    echo "  System Preferences → Users & Groups → Login Items"
    echo ""
else
    echo "❌ Build failed"
    exit 1
fi
