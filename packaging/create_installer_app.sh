#!/bin/bash
# Creates a double-clickable macOS app for installing Forge Controller

APP_NAME="Install Forge Controller.app"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "Creating macOS installer app..."

# Create app bundle structure
mkdir -p "$APP_NAME/Contents/MacOS"
mkdir -p "$APP_NAME/Contents/Resources"

# Create the Info.plist
cat > "$APP_NAME/Contents/Info.plist" << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleExecutable</key>
    <string>installer</string>
    <key>CFBundleIconFile</key>
    <string>AppIcon</string>
    <key>CFBundleIdentifier</key>
    <string>com.buildly.forge.installer</string>
    <key>CFBundleName</key>
    <string>Install Forge Controller</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleVersion</key>
    <string>1</string>
</dict>
</plist>
EOF

# Create the executable script
cat > "$APP_NAME/Contents/MacOS/installer" << 'EOF'
#!/bin/bash

# Get the directory where this app bundle is located
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../" && pwd)"

# Check if already running
if pgrep -f "forge_controller_app.py" > /dev/null; then
    osascript -e 'display notification "Forge Controller is already running. Check your menu bar." with title "Forge Controller"'
    exit 0
fi

# Open a terminal and run the installer
osascript <<-APPLESCRIPT
    tell application "Terminal"
        activate
        do script "cd '$APP_DIR' && ./install.sh && echo '' && echo '🚀 Launching Forge Controller...' && nohup python3 forge_controller_app.py > /dev/null 2>&1 & echo 'Forge Controller is running in the menu bar.' && echo 'You can close this window - the app will keep running.' && sleep 2"
    end tell
APPLESCRIPT
EOF

# Make the executable script executable
chmod +x "$APP_NAME/Contents/MacOS/installer"

# Copy icon if it exists
if [ -f "forge_controller/forge-logo.png" ]; then
    # Create an icns file from the PNG (requires sips)
    mkdir -p "/tmp/forge-icon.iconset"
    sips -z 16 16     forge_controller/forge-logo.png --out "/tmp/forge-icon.iconset/icon_16x16.png" 2>/dev/null
    sips -z 32 32     forge_controller/forge-logo.png --out "/tmp/forge-icon.iconset/icon_16x16@2x.png" 2>/dev/null
    sips -z 32 32     forge_controller/forge-logo.png --out "/tmp/forge-icon.iconset/icon_32x32.png" 2>/dev/null
    sips -z 64 64     forge_controller/forge-logo.png --out "/tmp/forge-icon.iconset/icon_32x32@2x.png" 2>/dev/null
    sips -z 128 128   forge_controller/forge-logo.png --out "/tmp/forge-icon.iconset/icon_128x128.png" 2>/dev/null
    sips -z 256 256   forge_controller/forge-logo.png --out "/tmp/forge-icon.iconset/icon_128x128@2x.png" 2>/dev/null
    sips -z 256 256   forge_controller/forge-logo.png --out "/tmp/forge-icon.iconset/icon_256x256.png" 2>/dev/null
    sips -z 512 512   forge_controller/forge-logo.png --out "/tmp/forge-icon.iconset/icon_256x256@2x.png" 2>/dev/null
    sips -z 512 512   forge_controller/forge-logo.png --out "/tmp/forge-icon.iconset/icon_512x512.png" 2>/dev/null
    sips -z 1024 1024 forge_controller/forge-logo.png --out "/tmp/forge-icon.iconset/icon_512x512@2x.png" 2>/dev/null
    
    iconutil -c icns "/tmp/forge-icon.iconset" -o "$APP_NAME/Contents/Resources/AppIcon.icns" 2>/dev/null
    rm -rf "/tmp/forge-icon.iconset"
fi

echo "✅ Created: $APP_NAME"
echo ""
echo "You can now double-click '$APP_NAME' to install and launch Forge Controller!"
echo "You can also distribute this .app file to users."
