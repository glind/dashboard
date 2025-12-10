# Desktop App Quick Reference

## 🚀 Quick Commands

### For Daily Development (Recommended)
```bash
./launch_desktop.sh    # Run in development mode
```

### For Building Distributable App
```bash
./build_desktop.sh     # Build PersonalDashboard.app
./build_installer.sh   # Create DMG installer
```

---

## 📊 Mode Comparison

| | Development Mode | Standalone App |
|---|---|---|
| **Command** | `./launch_desktop.sh` | `./build_desktop.sh` |
| **Source** | Runs from `src/` folder | Frozen binary |
| **Updates** | ✅ Automatic (just restart) | ❌ Must rebuild |
| **Build Time** | None | ~30 seconds |
| **Size** | Source files only | ~100MB bundled |
| **Icon** | Default Python | Custom Buildly logo |
| **Best For** | Development & personal use | Sharing with others |

---

## 🔄 How to Update

### Development Mode
```bash
# 1. Pull latest code
git pull origin main

# 2. Restart the app
./launch_desktop.sh

# That's it! ✅
```

### Standalone App
```bash
# 1. Pull latest code
git pull origin main

# 2. Rebuild the app
./build_desktop.sh

# 3. Open rebuilt app
open dist/PersonalDashboard.app

# Done! ✅
```

---

## 🎨 Customizing the Icon

```bash
# 1. Edit the icon generator
edit create_icon.py

# 2. Regenerate icon
python3 create_icon.py

# 3. Rebuild app (to see new icon)
./build_desktop.sh
```

Icon is saved to: `assets/buildly_logo.png`

---

## 🐛 Troubleshooting

### App won't start
```bash
# Check Python version (needs 3.10+)
python3 --version

# Install pywebview
python3 -m pip install pywebview

# Try launcher again
./launch_desktop.sh
```

### Server already running
```bash
# Stop existing server
./ops/startup.sh stop

# Restart desktop app
./launch_desktop.sh
```

### Changes not showing up

**Development Mode:**
- Just restart the launcher - changes load automatically

**Standalone App:**
- You must rebuild: `./build_desktop.sh`
- The `.app` file is frozen at build time

---

## 📂 Generated Files

```
dist/
├── PersonalDashboard.app          # Built app (from ./build_desktop.sh)
└── PersonalDashboard.dmg          # Installer (from ./build_installer.sh)

build/                              # PyInstaller temp files (auto-generated)
*.spec                             # PyInstaller spec (auto-generated)

assets/
└── buildly_logo.png               # App icon (from create_icon.py)
    └── icon.icns                  # macOS icon format (auto-generated)
```

You can delete `dist/`, `build/`, and `*.spec` files anytime - they'll be regenerated on next build.

---

## 💡 Best Practices

1. **Use development mode daily** - It's faster and auto-updates
2. **Only build .app when sharing** - No need to rebuild for personal use
3. **Test built app before sharing** - Make sure it works on a clean system
4. **Keep source code updated** - Pull regularly for bug fixes and features
5. **Commit before building** - So you know what version is in the .app

---

## 🆘 Need Help?

- Check `DESKTOP_WORKFLOW.md` for detailed workflow guide
- See `README.md` for full setup instructions
- Run `./ops/startup.sh status` to check server health
