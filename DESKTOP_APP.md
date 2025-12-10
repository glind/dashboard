# Desktop Application Guide

## Quick Start

### Run in Development Mode
```bash
# Simplest way - auto-installs dependencies
./launch_desktop.sh

# Or using Python directly
python3 run_desktop.py

# Or the main app file
python3 app_desktop.py
```

### Build Standalone App
```bash
# Build .app bundle
./build_desktop.sh

# Run the built app
open dist/PersonalDashboard.app

# Create installer DMG
./build_installer.sh
```

## Features

### Native macOS Integration
- **WKWebView**: Uses native macOS WebKit (not Chromium)
- **Small Size**: ~50MB vs Electron's ~200MB+
- **Fast Startup**: Native window, instant launch
- **Battery Friendly**: Native rendering, lower CPU usage

### Security
- **Localhost Only**: Server binds to 127.0.0.1
- **No External Access**: Not exposed to network
- **Sandboxed**: Can be properly sandboxed for App Store

### User Experience
- Native window controls (minimize, maximize, close)
- Proper dock integration
- System menu bar support
- Keyboard shortcuts
- Text selection and copy/paste

## Architecture

```
app_desktop.py
├── Start FastAPI server (background thread)
│   └── Bind to 127.0.0.1:8008
├── Wait for server to be ready
└── Create pywebview window
    └── Load http://127.0.0.1:8008
```

## Configuration

### Change Port
Edit `app_desktop.py`:
```python
PORT = 8008  # Change to desired port
```

### Window Size
Edit `app_desktop.py`:
```python
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
MIN_WIDTH = 1024
MIN_HEIGHT = 768
```

### Debug Mode
Enable debug mode for development:
```python
webview.start(debug=True)  # Shows developer tools
```

## Building for Distribution

### Prerequisites
```bash
pip install pyinstaller pillow
```

### Build Process
The `build_desktop.sh` script:
1. Creates virtual environment
2. Installs dependencies
3. Generates app icon
4. Bundles everything with PyInstaller
5. Creates .app in `dist/` folder

### Bundle Contents
```
PersonalDashboard.app/
├── Contents/
│   ├── MacOS/
│   │   └── PersonalDashboard (executable)
│   ├── Resources/
│   │   ├── icon.icns
│   │   └── (app data)
│   └── Info.plist
```

### DMG Installer
The `build_installer.sh` script:
1. Creates DMG with app
2. Adds Applications symlink
3. Compresses and finalizes

Users can:
1. Mount the DMG
2. Drag app to Applications
3. Launch from Applications folder

## Advanced Features

### System Tray (Future)
Can add system tray icon:
```python
import pystray
from PIL import Image

# Create tray icon
icon = pystray.Icon("dashboard", Image.open("icon.png"))
icon.run()
```

### Auto-Start (Future)
Add launch agent:
```bash
# ~/Library/LaunchAgents/com.dashboard.plist
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.dashboard</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Applications/PersonalDashboard.app/Contents/MacOS/PersonalDashboard</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
</dict>
</plist>
```

### Keyboard Shortcuts (Future)
Global shortcuts using `keyboard` library:
```python
import keyboard

keyboard.add_hotkey('cmd+shift+d', show_dashboard)
```

## Troubleshooting

### Port Already in Use
Kill existing server:
```bash
lsof -ti:8008 | xargs kill -9
```

### Window Won't Open
Check server logs:
```bash
tail -f dashboard.log
```

### Build Fails
Clean and rebuild:
```bash
rm -rf build dist *.spec
./build_desktop.sh
```

### App Won't Launch
Check for Python in PATH:
```bash
which python3
python3 --version
```

## Performance

### Memory Usage
- **Web Version**: ~150MB (browser + tab)
- **Desktop Version**: ~80MB (just WebKit)

### Startup Time
- **Web Version**: 2-3 seconds (browser launch)
- **Desktop Version**: <1 second (native window)

### CPU Usage
- **Web Version**: Higher (full browser)
- **Desktop Version**: Lower (native rendering)

## Comparison with Electron

| Feature | pywebview | Electron |
|---------|-----------|----------|
| Size | ~50MB | ~200MB+ |
| Memory | ~80MB | ~150MB+ |
| Startup | <1s | 2-3s |
| Native | ✅ | ❌ |
| Python | ✅ | ❌ |
| Cross-platform | ✅ | ✅ |

## Future Enhancements

- [ ] System tray integration
- [ ] Global keyboard shortcuts
- [ ] Auto-update mechanism
- [ ] Offline mode support
- [ ] Menu bar app option
- [ ] Touch Bar support (MacBook Pro)
- [ ] Notification center integration
- [ ] Handoff support (iOS)

## License

Same as main project - Business Source License 1.1
