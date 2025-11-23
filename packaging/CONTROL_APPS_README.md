# Dashboard Control Apps - Cross-Platform Launchers

Simple desktop applications for controlling the Personal Dashboard server on Linux, macOS, and Windows.

## Quick Start

### 🐧 Linux
```bash
cd linux
./install_control_app.sh
./launch_controller.sh
```

### 🍎 macOS  
```bash
cd macos
./install_control_app.sh
python3 dashboard_control.py
```

### 🪟 Windows
```batch
cd windows
install_control_app.bat
pythonw dashboard_control.py
```

---

## Platform Details

### Linux (GTK System Tray)

**Two versions available:**
- **System Tray** - Lives in notification area (requires AppIndicator)
- **Window** - Standalone window (works everywhere)

**Features:**
- Real-time server status
- Desktop notifications
- One-click start/stop/restart
- Quick browser access
- Log viewer

**Installation:**
```bash
cd linux
./install_control_app.sh
```

**Run:**
```bash
./launch_controller.sh  # Auto-selects best version
```

**Add to Startup:**
- GNOME: `gnome-session-properties`
- KDE: System Settings → Autostart
- XFCE: Settings → Session → Autostart

---

### macOS (Menu Bar)

**Features:**
- Clean menu bar icon
- Native macOS notifications
- Lightweight (using rumps)
- System integration

**Installation:**
```bash
cd macos
./install_control_app.sh  # Installs rumps + dependencies
```

**Run:**
```bash
python3 dashboard_control.py
```

**Add to Login Items:**
1. System Preferences → Users & Groups
2. Login Items
3. Click '+' and select `dashboard_control.py`

**Build as App:**
```bash
./build_macos_app.sh  # Creates .app bundle
```

---

### Windows (System Tray)

**Features:**
- Windows system tray icon
- Native notifications
- PyQt5-based
- Clean interface

**Installation:**
```batch
cd windows
install_control_app.bat
```

**Run:**
```batch
REM With console:
python dashboard_control.py

REM Background (no console):
pythonw dashboard_control.py
```

**Add to Startup:**
1. Press `Win+R`
2. Type: `shell:startup`
3. Create shortcut to script

---

## Common Features

All versions include:

✅ **Status Monitoring** - Real-time server state
✅ **Start/Stop/Restart** - Full server control
✅ **Open Dashboard** - Quick browser launch
✅ **View Logs** - Monitor server activity
✅ **Auto-cleanup** - Kills stale processes
✅ **Health Checks** - Verifies server responding

## Status Indicators

- ✅ **Running** - Server active on port 8008
- ⏳ **Starting** - Server initializing
- ⭕ **Stopped** - Server not running

## Requirements

### All Platforms
- Python 3.6+
- requests (`pip install requests`)

### Platform-Specific

**Linux:**
- GTK 3
- AppIndicator3 (for tray version)
- `python3-gi`, `gir1.2-gtk-3.0`, `gir1.2-appindicator3-0.1`

**macOS:**
- rumps (`pip install rumps`)
- macOS 10.12+

**Windows:**
- PyQt5 (`pip install PyQt5`)
- Windows 10/11

## Troubleshooting

### Linux: System tray not showing
```bash
sudo apt install gnome-shell-extension-appindicator
```

### macOS: rumps not found
```bash
pip3 install --user rumps
```

### Windows: Icon not in system tray
Check taskbar settings → Select which icons appear

## Architecture

Each control app:
1. Checks server status every 5 seconds
2. Reads PID file to detect running server
3. Verifies server health via `/api/health`
4. Manages server lifecycle via `ops/startup.sh`
5. Updates UI based on server state

## Files Structure

```
packaging/
├── README.md                  # This file
├── linux/                     # Linux versions
│   ├── dashboard_control.py           # System tray
│   ├── dashboard_control_window.py    # Window
│   ├── launch_controller.sh           # Auto-launcher
│   ├── install_control_app.sh
│   └── dashboard-control.desktop
├── macos/                     # macOS version
│   ├── dashboard_control.py   # Menu bar app
│   ├── install_control_app.sh
│   └── build_macos_app.sh     # Build .app
└── windows/                   # Windows version
    ├── dashboard_control.py   # System tray
    └── install_control_app.bat
```

## Development

To customize, edit the `dashboard_control.py` file for your platform. All versions follow similar patterns:

```python
# 1. Check status
def get_server_status(): ...

# 2. Update UI
def update_status(): ...

# 3. Control server
def start_server(): ...
def stop_server(): ...
def restart_server(): ...
```

## License

Same as main project (BSL 1.1 → Apache-2.0).
