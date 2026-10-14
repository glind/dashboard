#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

APP_NAME="FounderDashboard"
DISPLAY_NAME="Personal Dashboard"
PACKAGE_NAME="founder-dashboard"
MAINTAINER="Buildly <support@buildly.ai>"
DESCRIPTION="AI-powered founder dashboard desktop app"

if [[ "${OSTYPE:-}" != linux* ]]; then
    echo "❌ Linux packaging is only supported on Linux hosts."
    exit 1
fi

if ! command -v dpkg-deb >/dev/null 2>&1; then
    echo "❌ Missing required command: dpkg-deb"
    echo "   Install it with: sudo apt-get install dpkg-dev"
    exit 1
fi

ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"

VERSION="$(python3 - <<'PY'
import re
from pathlib import Path

version_file = Path("src/__version__.py")
text = version_file.read_text(encoding="utf-8")
match = re.search(r'__version__\s*=\s*"([^"]+)"', text)
print(match.group(1) if match else "0.0.0")
PY
)"

BUILD_DIR="build/linux-installer"
DIST_DIR="dist"
PKG_STAGING_DIR="$BUILD_DIR/pkg"
PYINSTALLER_DIR="$BUILD_DIR/pyinstaller"
DEB_ROOT="$PKG_STAGING_DIR/${PACKAGE_NAME}_${VERSION}_${ARCH}"

echo "🐧 Building Linux installer artifacts"
echo "   App: $DISPLAY_NAME"
echo "   Version: $VERSION"
echo "   Arch: $ARCH"

mkdir -p "$BUILD_DIR" "$DIST_DIR"
rm -rf "$PKG_STAGING_DIR" "$PYINSTALLER_DIR"

if [[ ! -d ".venv" ]]; then
    echo "📦 Creating virtual environment (.venv)..."
    python3 -m venv .venv
fi

source .venv/bin/activate

echo "📦 Installing build dependencies..."
pip install --upgrade pip >/dev/null
pip install -r requirements.txt pyinstaller pillow >/dev/null

echo "🔨 Building self-contained binary with PyInstaller..."
pyinstaller \
    --noconfirm \
    --clean \
    --onefile \
    --windowed \
    --name "$APP_NAME" \
    --distpath "$PYINSTALLER_DIR/dist" \
    --workpath "$PYINSTALLER_DIR/build" \
    --specpath "$PYINSTALLER_DIR/spec" \
    --add-data "src:src" \
    --add-data "src/templates:src/templates" \
    --add-data "src/static:src/static" \
    --add-data "config:config" \
    --add-data "splash.html:." \
    --hidden-import uvicorn \
    --hidden-import fastapi \
    --hidden-import webview \
    --hidden-import pydantic \
    --hidden-import sqlalchemy \
    --collect-all fastapi \
    --collect-all uvicorn \
    app_desktop.py

BIN_PATH="$PYINSTALLER_DIR/dist/$APP_NAME"
if [[ ! -f "$BIN_PATH" ]]; then
    echo "❌ Build failed: missing binary at $BIN_PATH"
    exit 1
fi

ICON_SOURCE="assets/images/icon-512.png"
if [[ ! -f "$ICON_SOURCE" ]]; then
    ICON_SOURCE="assets/images/buildly-new-logo.png"
fi

echo "📦 Creating Debian package structure..."
mkdir -p \
    "$DEB_ROOT/DEBIAN" \
    "$DEB_ROOT/opt/$PACKAGE_NAME" \
    "$DEB_ROOT/usr/local/bin" \
    "$DEB_ROOT/usr/share/applications" \
    "$DEB_ROOT/usr/share/icons/hicolor/512x512/apps"

cp "$BIN_PATH" "$DEB_ROOT/opt/$PACKAGE_NAME/$APP_NAME"
chmod 755 "$DEB_ROOT/opt/$PACKAGE_NAME/$APP_NAME"

cp "$ICON_SOURCE" "$DEB_ROOT/usr/share/icons/hicolor/512x512/apps/${PACKAGE_NAME}.png"

sed \
    -e "s|{{PACKAGE_NAME}}|$PACKAGE_NAME|g" \
    -e "s|{{VERSION}}|$VERSION|g" \
    -e "s|{{ARCH}}|$ARCH|g" \
    -e "s|{{MAINTAINER}}|$MAINTAINER|g" \
    -e "s|{{DESCRIPTION}}|$DESCRIPTION|g" \
    "ops/packaging/debian/control.template" > "$DEB_ROOT/DEBIAN/control"

sed \
    -e "s|{{DISPLAY_NAME}}|$DISPLAY_NAME|g" \
    -e "s|{{PACKAGE_NAME}}|$PACKAGE_NAME|g" \
    "ops/packaging/debian/desktop.template" > "$DEB_ROOT/usr/share/applications/${PACKAGE_NAME}.desktop"

cat > "$DEB_ROOT/usr/local/bin/${PACKAGE_NAME}" <<EOF
#!/usr/bin/env bash
exec /opt/${PACKAGE_NAME}/${APP_NAME} "\$@"
EOF
chmod 755 "$DEB_ROOT/usr/local/bin/${PACKAGE_NAME}"

DEB_FILE="$DIST_DIR/${PACKAGE_NAME}_${VERSION}_${ARCH}.deb"
echo "📀 Building .deb package..."
dpkg-deb --build "$DEB_ROOT" "$DEB_FILE" >/dev/null

TAR_DIR="$BUILD_DIR/tar/${PACKAGE_NAME}-${VERSION}-linux-${ARCH}"
mkdir -p "$TAR_DIR"
cp "$BIN_PATH" "$TAR_DIR/${APP_NAME}"
chmod 755 "$TAR_DIR/${APP_NAME}"
cat > "$TAR_DIR/run.sh" <<EOF
#!/usr/bin/env bash
SCRIPT_DIR="\$(cd "\$(dirname "\${BASH_SOURCE[0]}")" && pwd)"
exec "\$SCRIPT_DIR/${APP_NAME}" "\$@"
EOF
chmod 755 "$TAR_DIR/run.sh"

TAR_FILE="$DIST_DIR/${PACKAGE_NAME}-${VERSION}-linux-${ARCH}.tar.gz"
tar -C "$(dirname "$TAR_DIR")" -czf "$TAR_FILE" "$(basename "$TAR_DIR")"

echo ""
echo "✅ Linux artifacts created:"
echo "   - $DEB_FILE"
echo "   - $TAR_FILE"
echo ""
echo "Install on Ubuntu/Debian:"
echo "  sudo apt install ./$DEB_FILE"
echo "Launch app:"
echo "  $PACKAGE_NAME"
