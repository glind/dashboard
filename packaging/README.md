# Buildly Forge Controller

A cross-platform desktop application for managing Buildly Forge services running on ports 8000-9000.

## Quick Install

### macOS / Linux
```bash
./install.sh
```

### Windows
```batch
install.bat
```

## Features

- **Auto-Discovery**: Scans ports 8000-9000 for running Forge services
- **Service Detection**: Identifies service names via health endpoints
- **Status Monitoring**: Real-time status updates every 5 seconds
- **One-Click Actions**: Start, stop, open in browser
- **Native UI**: Menu bar (macOS), system tray (Linux/Windows), or window mode
- **Cross-Platform**: Works on macOS, Linux, and Windows

## How It Works

The Forge Controller:

1. **Scans ports 8000-9000** for active web services
2. **Probes health endpoints** (`/api/health`, `/health`, etc.) to identify services
3. **Displays discovered services** with status indicators
4. **Provides quick actions** to open in browser or stop services

## Status Indicators

- ✅ **Running** - Service is active and responding to health checks
- ⏳ **Starting** - Port is open but health endpoint not responding yet
- ⭕ **Stopped** - No service detected on port

## Platform Support

### macOS (Menu Bar)
- Lives in the menu bar
- Uses `rumps` for native integration
- Requires: `pip install rumps requests`

### Linux (System Tray)
- System tray with AppIndicator
- Falls back to window mode if AppIndicator unavailable
- Requires: GTK3, AppIndicator3, and `requests`

### Windows (System Tray)
- Native Windows system tray icon
- Uses PyQt5 for cross-platform GUI
- Requires: `pip install PyQt5 requests`

## Manual Run

After installation, you can run directly:

```bash
# macOS/Linux
python3 forge_controller_app.py

# Windows
python forge_controller_app.py

# Windows (no console)
pythonw forge_controller_app.py
```

## File Structure

```
packaging/
├── install.sh              # Unix installer (macOS/Linux)
├── install.bat             # Windows installer
├── forge_controller_app.py # Universal launcher
├── forge_controller/       # Main package
│   ├── __init__.py
│   ├── core.py            # Cross-platform service scanner
│   ├── macos_app.py       # macOS menu bar implementation
│   ├── linux_app.py       # Linux system tray implementation
│   ├── windows_app.py     # Windows system tray implementation
│   └── forge-logo.png     # App icon (copied during install)
└── README.md              # This file
```

## Configuration

The controller automatically discovers services. No configuration needed!

For advanced use, you can customize:

- **Port range**: Edit `PORT_RANGE_START` and `PORT_RANGE_END` in `core.py`
- **Health endpoints**: Add custom endpoints to `HEALTH_ENDPOINTS` list
- **Scan interval**: Modify `refresh_interval` (default: 5 seconds)

## Troubleshooting

### macOS: "rumps not found"
```bash
pip3 install rumps
```

### Linux: System tray not showing
```bash
# Ubuntu/Debian
sudo apt install gnome-shell-extension-appindicator
# Then log out and back in

# Or use window mode (automatic fallback)
```

### Windows: Icon not in system tray
1. Right-click taskbar → Taskbar settings
2. Find "Select which icons appear on the taskbar"
3. Enable "Forge Controller"

### No services detected
- Ensure your Forge app is running
- Check it's on a port in the 8000-9000 range
- Try the health endpoint manually: `curl http://localhost:8000/api/health`

## Development

### Testing the scanner
```bash
python3 -c "from forge_controller.core import ForgeServiceScanner; s = ForgeServiceScanner(); print(s.scan_services())"
```

### Adding platform support
1. Create new file in `forge_controller/` (e.g., `newplatform_app.py`)
2. Implement `ForgeControllerBase` subclass
3. Add detection in `forge_controller_app.py`

## License

Same as main Buildly project (BSL 1.1 → Apache-2.0).
