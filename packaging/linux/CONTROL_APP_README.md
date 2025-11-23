# Dashboard Control App

A simple Linux desktop application to control your Personal Dashboard server from the system tray.

## Features

- 🎯 **System Tray Icon** - Always visible status indicator
- ✅ **Real-time Status** - See if server is running, starting, or stopped
- ▶️ **Start/Stop/Restart** - Control server with one click
- 🌐 **Quick Access** - Open dashboard in browser instantly
- 📋 **View Logs** - Monitor server logs in real-time
- 🔔 **Notifications** - Desktop notifications for server events

## Installation

### Quick Install

```bash
./install_control_app.sh
```

This will install all required dependencies and set up the desktop application.

### Manual Installation

If the automatic installer doesn't work for your system:

1. **Install system dependencies:**

   **Ubuntu/Debian:**
   ```bash
   sudo apt-get install python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-appindicator3-0.1 libnotify-bin
   ```

   **Fedora:**
   ```bash
   sudo dnf install python3-gobject gtk3 libappindicator-gtk3 libnotify
   ```

   **Arch:**
   ```bash
   sudo pacman -S python-gobject gtk3 libappindicator-gtk3 libnotify
   ```

2. **Install Python requests:**
   ```bash
   pip3 install --user requests
   ```

3. **Make executable:**
   ```bash
   chmod +x dashboard_control.py
   ```

## Usage

### Launch the App

**Option 1: From terminal**
```bash
./dashboard_control.py
```

**Option 2: From applications menu**
- Search for "Dashboard Controller" in your application launcher

**Option 3: Add to startup** (auto-launch on login)
- GNOME: `gnome-session-properties`
- KDE: System Settings → Startup and Shutdown → Autostart
- XFCE: Settings → Session and Startup → Application Autostart

### Using the System Tray Icon

Click the system tray icon to access:

- **Status** - Current server state (Running/Stopped/Starting)
- **Start Server** - Launch the dashboard server
- **Restart Server** - Restart the running server
- **Stop Server** - Shut down the server
- **Open Dashboard** - Open http://localhost:8008 in browser
- **View Logs** - Open dashboard.log in terminal
- **Quit Controller** - Close the control app (doesn't stop server)

### Status Indicators

- ✅ **Green/Running** - Server is running and responding
- ⏳ **Yellow/Starting** - Server process started but not yet responding
- ⭕ **Red/Stopped** - Server is not running

## Requirements

- **Linux** (tested on Ubuntu, Fedora, Arch)
- **Python 3.6+**
- **GTK 3**
- **AppIndicator3** (for system tray)
- **Desktop Environment** with system tray support (GNOME, KDE, XFCE, etc.)

## Troubleshooting

### System tray icon not showing

Some desktop environments hide the system tray by default:

- **GNOME**: Install `gnome-shell-extension-appindicator`
  ```bash
  sudo apt install gnome-shell-extension-appindicator
  ```
  
- **KDE**: Enable system tray in Panel settings

### "Module gi not found" error

Install PyGObject:
```bash
sudo apt-get install python3-gi
```

### Server won't start

Make sure the startup script is executable:
```bash
chmod +x ops/startup.sh
```

## Uninstall

```bash
rm ~/.local/share/applications/dashboard-control.desktop
update-desktop-database ~/.local/share/applications
```

## Development

The control app is a simple Python script using:
- **PyGObject** - GTK bindings for Python
- **AppIndicator3** - System tray integration
- **subprocess** - Server control
- **requests** - Health checks

Feel free to modify `dashboard_control.py` to customize behavior!

## License

Same as the main dashboard project (BSL 1.1 → Apache-2.0).
