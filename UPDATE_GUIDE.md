# Desktop App Update Flow

## 🔄 Visual Update Guide

### Development Mode (./launch_desktop.sh)
```
┌─────────────────────────────────────────────────────────────┐
│                    DEVELOPMENT MODE                          │
│                  (Recommended for You)                       │
└─────────────────────────────────────────────────────────────┘

Step 1: Pull Updates
   git pull origin main
        ↓
Step 2: Restart Launcher
   ./launch_desktop.sh
        ↓
   ✅ DONE! New code runs automatically

Time: < 5 seconds
Rebuild: NOT needed
```

---

### Standalone App (./build_desktop.sh)
```
┌─────────────────────────────────────────────────────────────┐
│                    STANDALONE MODE                           │
│               (For Sharing with Others)                      │
└─────────────────────────────────────────────────────────────┘

Step 1: Pull Updates
   git pull origin main
        ↓
Step 2: Rebuild App
   ./build_desktop.sh
        ↓ (~30 seconds)
Step 3: Test Built App
   open dist/PersonalDashboard.app
        ↓
   ✅ DONE! App updated with new code

Time: ~35 seconds
Rebuild: REQUIRED
```

---

## 🤔 Which Should You Use?

```
                 ┌─────────────────────┐
                 │   Are you sharing   │
                 │   with others?      │
                 └──────────┬──────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
           NO │                           │ YES
              │                           │
              ▼                           ▼
   ┌──────────────────────┐    ┌──────────────────────┐
   │  Development Mode    │    │   Standalone App     │
   │                      │    │                      │
   │  ./launch_desktop.sh │    │  ./build_desktop.sh  │
   │                      │    │                      │
   │  ✅ Auto-updates     │    │  📦 Self-contained   │
   │  🚀 Fast             │    │  🎁 Shareable        │
   │  🔧 Development      │    │  ⚠️  Manual rebuild  │
   └──────────────────────┘    └──────────────────────┘
```

---

## 📋 Update Checklist

### Before Updating
- [ ] Check current version: `git log -1 --oneline`
- [ ] Stop desktop app (if running)
- [ ] Commit any local changes

### During Update
- [ ] Pull latest: `git pull origin main`
- [ ] Review changes: `git log -3 --oneline`

### After Update - Development Mode
- [ ] Restart launcher: `./launch_desktop.sh`
- [ ] Verify it works: Open dashboard

### After Update - Standalone App
- [ ] Rebuild: `./build_desktop.sh`
- [ ] Test build: `open dist/PersonalDashboard.app`
- [ ] (Optional) Create DMG: `./build_installer.sh`

---

## 🎯 Common Scenarios

### "I just want to use the dashboard daily"
→ Use **Development Mode** (`./launch_desktop.sh`)
- Updates: Just pull and restart
- No rebuilding needed

### "I want to share with a colleague"
→ Build **Standalone App** (`./build_desktop.sh`)
- Gives them a complete `.app` file
- They don't need Python or dependencies

### "I want to install on multiple Macs"
→ Create **DMG Installer** (`./build_installer.sh`)
- Professional installer package
- Easy drag-and-drop installation

### "I made code changes"
→ **Development Mode**: Just restart
→ **Standalone App**: Must rebuild

---

## ⚡ Quick Command Reference

```bash
# Development Mode
./launch_desktop.sh              # Start in dev mode
git pull && ./launch_desktop.sh  # Update and run

# Standalone App
./build_desktop.sh               # Build .app
open dist/PersonalDashboard.app  # Test it
./build_installer.sh             # Create DMG

# Maintenance
./ops/startup.sh stop            # Stop server
./ops/startup.sh status          # Check health
rm -rf dist/ build/ *.spec       # Clean build files
```

---

## 🆘 "My updates aren't showing!"

### If using Development Mode:
1. Make sure you actually pulled: `git pull origin main`
2. Completely quit the app (Cmd+Q)
3. Restart: `./launch_desktop.sh`
4. Check you're editing the right files in `src/`

### If using Standalone App:
1. Did you rebuild? `./build_desktop.sh`
2. Are you running the NEW .app? Check date: `ls -lh dist/`
3. Did you quit the old app first? (Cmd+Q)
4. Try: `rm -rf dist/ && ./build_desktop.sh`

---

## 💡 Pro Tips

1. **Create an alias** for quick launching:
   ```bash
   echo 'alias dash="cd ~/Projects/dashboard && ./launch_desktop.sh"' >> ~/.zshrc
   source ~/.zshrc
   # Now just type: dash
   ```

2. **Check what changed** before updating:
   ```bash
   git fetch
   git log HEAD..origin/main --oneline
   ```

3. **Keep a stable version** while testing updates:
   ```bash
   git checkout -b testing
   git pull origin main
   ./launch_desktop.sh  # Test changes
   # If good: git checkout main && git pull
   ```

4. **Automate builds** with a script:
   ```bash
   cat > update_and_build.sh << 'EOF'
   #!/bin/bash
   git pull origin main && ./build_desktop.sh && echo "✅ Updated!"
   EOF
   chmod +x update_and_build.sh
   ```
