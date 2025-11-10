# Personal Dashboard - Packaging & Distribution

This directory contains packaging files for different platforms and deployment methods.

## Available Packages

### macOS App (`macos/`)
Creates a standalone macOS application using PyWebView.
- **Files**: `app_main.py`, `dashboard.spec`, `build_macos_app.sh`, `install_macos.sh`
- **Usage**: Run `./macos/install_macos.sh` to build the app
- **Features**: WebKit-based window, no external browser dependency

### Docker (Coming Soon)
- Containerized deployment
- Cross-platform compatibility

### Windows Installer (Coming Soon)
- Windows executable with installer
- PyInstaller-based packaging

### Linux AppImage (Coming Soon)
- Portable Linux application
- Single-file distribution

## Default Usage (No Packaging Required)

Most users should use the standard startup method:

```bash
# Standard startup (recommended)
./ops/startup.sh

# Direct Python execution
cd src && python3 main.py

# Development mode
./ops/dev.sh
```

Open http://localhost:8008 in any browser.

## When to Use Packaging

Consider packaging when you need:
- **Standalone app**: No terminal/command line interaction
- **Distribution**: Sharing with non-technical users
- **Deployment**: Running on servers or different environments
- **Integration**: Embedding in other applications

## Platform-Specific Instructions

### macOS App
```bash
cd packaging/macos
./install_macos.sh
```

### Other Platforms
Use the standard startup methods above. Platform-specific packages will be added as needed.