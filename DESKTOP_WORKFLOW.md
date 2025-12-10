# Desktop App Workflow Guide

## 📱 Two Modes: Development vs Distribution

### 🔧 Development Mode (Daily Use - AUTO-UPDATES)

**Use this for development and daily use:**

```bash
./launch_desktop.sh
# OR
python3 app_desktop.py
```

**How it works:**
- Runs Python source code directly from `src/` folder
- **Automatically uses latest code changes**
- No build/compile step needed
- Fast startup
- Perfect for development and personal use

**After code updates:**
```bash
git pull origin main
./launch_desktop.sh  # Just restart - that's it!
```

---

### 📦 Distribution Mode (For Sharing - FROZEN)

**Only use this to create standalone apps for others:**

```bash
# Build .app bundle
./build_desktop.sh

# Create DMG installer
./build_installer.sh
```

**How it works:**
- PyInstaller freezes all code into binary
- Creates standalone `PersonalDashboard.app`
- **Does NOT auto-update** - code is frozen at build time
- Takes ~30 seconds to build
- ~100MB app size

**After code updates:**
```bash
git pull origin main
./build_desktop.sh    # Must rebuild to include changes!
```

---

## 🎨 Icon Updates

The app icon is generated from `create_icon.py`:

```bash
# Regenerate icon (Buildly logo with bunny)
python3 create_icon.py

# Icon is saved to: assets/buildly_logo.png

# Rebuild app to use new icon
./build_desktop.sh
```

**Note:** Development mode doesn't show the icon in Dock (it's a Python script). Only the built `.app` shows the custom icon.

---

## 🚀 Recommended Workflow

**For yourself (development/personal use):**
1. Use `./launch_desktop.sh` always
2. Pull updates with `git pull`
3. Restart launcher - done!

**For sharing with others:**
1. Develop using launcher
2. When ready to share: `./build_desktop.sh`
3. Test the built app: `open dist/PersonalDashboard.app`
4. Create installer: `./build_installer.sh`
5. Share the DMG file

---

## 📂 File Structure

```
dashboard/
├── app_desktop.py          # Desktop launcher (runs source code)
├── launch_desktop.sh       # Simple wrapper script
├── build_desktop.sh        # Build frozen .app
├── build_installer.sh      # Create DMG
├── create_icon.py          # Generate Buildly icon
├── src/                    # Source code (used by launcher)
│   ├── main.py
│   ├── collectors/
│   ├── processors/
│   └── ...
├── dist/                   # Built apps (frozen)
│   └── PersonalDashboard.app
└── assets/
    └── buildly_logo.png    # App icon
```

---

## ❓ FAQ

**Q: Do I need to rebuild after pulling updates?**
- Development mode (launcher): ❌ No - just restart
- Distribution mode (.app): ✅ Yes - must rebuild

**Q: Why is the built app so large?**
- It includes Python runtime, all dependencies, and bundled resources
- Normal for PyInstaller apps (~100-150MB)

**Q: Can I distribute the launcher script?**
- Not really - requires Python + dependencies installed
- Use the built `.app` for distribution instead

**Q: How do I update the icon?**
- Edit `create_icon.py`
- Run `python3 create_icon.py`
- Rebuild: `./build_desktop.sh`

**Q: Which should I use daily?**
- **Use the launcher** (`./launch_desktop.sh`) for daily development
- It's faster and always has your latest changes
