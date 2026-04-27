# Linux & Ubuntu Installer

This project now includes a Linux packaging flow that produces:

- Ubuntu/Debian installer: `.deb`
- Generic self-contained Linux archive: `.tar.gz`

## Build

From the project root:

```bash
./ops/build_linux_installer.sh
```

The script will:

1. Create/use `.venv`
2. Install build dependencies
3. Build a self-contained desktop binary with PyInstaller
4. Package into Ubuntu `.deb`
5. Package into generic Linux `.tar.gz`

## Output Artifacts

Created in `dist/`:

- `founder-dashboard_<version>_<arch>.deb`
- `founder-dashboard-<version>-linux-<arch>.tar.gz`

## Install on Ubuntu/Debian

```bash
sudo apt install ./dist/founder-dashboard_<version>_<arch>.deb
```

Launch from app menu or terminal:

```bash
founder-dashboard
```

## Generic Linux Usage (`.tar.gz`)

```bash
tar -xzf dist/founder-dashboard-<version>-linux-<arch>.tar.gz
cd founder-dashboard-<version>-linux-<arch>
./run.sh
```
