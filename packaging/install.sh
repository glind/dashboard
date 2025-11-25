#!/bin/bash
#
# Buildly Forge Controller - Universal Installer
# Installs the cross-platform Forge Controller application
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="Buildly Forge Controller"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_header() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}          ${GREEN}Buildly Forge Controller Installer${NC}               ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}          Cross-Platform Service Manager                    ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${GREEN}►${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# Detect operating system
detect_os() {
    case "$(uname -s)" in
        Darwin*)    echo "macos" ;;
        Linux*)     echo "linux" ;;
        CYGWIN*|MINGW*|MSYS*) echo "windows" ;;
        *)          echo "unknown" ;;
    esac
}

# Check if Python 3 is installed
check_python() {
    if command -v python3 &> /dev/null; then
        PYTHON_CMD="python3"
    elif command -v python &> /dev/null; then
        # Check if it's Python 3
        if python --version 2>&1 | grep -q "Python 3"; then
            PYTHON_CMD="python"
        else
            return 1
        fi
    else
        return 1
    fi
    
    echo "$PYTHON_CMD"
    return 0
}

# Check if pip is available
check_pip() {
    local python_cmd=$1
    if $python_cmd -m pip --version &> /dev/null; then
        return 0
    fi
    return 1
}

# Install Python dependencies
install_python_deps() {
    local python_cmd=$1
    local os_type=$2
    
    print_step "Installing Python dependencies..."
    
    # Always install requests
    $python_cmd -m pip install --user requests 2>/dev/null || $python_cmd -m pip install requests
    
    # Platform-specific dependencies
    case "$os_type" in
        macos)
            print_step "Installing macOS dependencies (rumps)..."
            $python_cmd -m pip install --user rumps 2>/dev/null || $python_cmd -m pip install rumps
            ;;
        windows)
            print_step "Installing Windows dependencies (PyQt5)..."
            $python_cmd -m pip install --user PyQt5 2>/dev/null || $python_cmd -m pip install PyQt5
            ;;
        linux)
            print_step "Installing Linux dependencies..."
            # Python packages
            $python_cmd -m pip install --user requests 2>/dev/null || true
            ;;
    esac
    
    print_success "Python dependencies installed"
}

# Install Linux system dependencies
install_linux_system_deps() {
    print_step "Installing Linux system dependencies..."
    
    if command -v apt-get &> /dev/null; then
        print_step "Using apt (Debian/Ubuntu)..."
        sudo apt-get update
        sudo apt-get install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-appindicator3-0.1 libnotify-bin
    elif command -v dnf &> /dev/null; then
        print_step "Using dnf (Fedora/RHEL)..."
        sudo dnf install -y python3-gobject gtk3 libappindicator-gtk3 libnotify
    elif command -v pacman &> /dev/null; then
        print_step "Using pacman (Arch)..."
        sudo pacman -S --noconfirm python-gobject gtk3 libappindicator-gtk3 libnotify
    elif command -v zypper &> /dev/null; then
        print_step "Using zypper (openSUSE)..."
        sudo zypper install -y python3-gobject gtk3 typelib-1_0-AppIndicator3-0_1 libnotify-tools
    else
        print_warning "Unknown package manager. Please install manually:"
        echo "  - python3-gi (PyGObject)"
        echo "  - gir1.2-gtk-3.0 (GTK 3)"
        echo "  - gir1.2-appindicator3-0.1 (AppIndicator)"
        echo "  - libnotify-bin (Desktop notifications)"
    fi
    
    print_success "System dependencies installed"
}

# Copy icon files
copy_icons() {
    local os_type=$1
    
    print_step "Setting up icons..."
    
    # Look for existing icon in various locations
    local icon_locations=(
        "$SCRIPT_DIR/forge_controller/forge-logo.png"
        "$SCRIPT_DIR/macos/forge-logo.png"
        "$SCRIPT_DIR/macos/buildly_icon.png"
        "$SCRIPT_DIR/../assets/images/forge-logo.png"
        "$SCRIPT_DIR/../assets/forge-logo.png"
    )
    
    local dest="$SCRIPT_DIR/forge_controller/forge-logo.png"
    
    # Skip if destination already exists
    if [ -f "$dest" ]; then
        print_success "Icon already present"
        return
    fi
    
    local icon_found=""
    for loc in "${icon_locations[@]}"; do
        if [ -f "$loc" ] && [ "$loc" != "$dest" ]; then
            icon_found="$loc"
            break
        fi
    done
    
    if [ -n "$icon_found" ]; then
        cp "$icon_found" "$dest"
        print_success "Icon copied"
    else
        print_warning "No icon found. App will use default icon."
    fi
}

# Create desktop entry for Linux
create_linux_desktop_entry() {
    print_step "Creating desktop entry..."
    
    local desktop_dir="$HOME/.local/share/applications"
    mkdir -p "$desktop_dir"
    
    cat > "$desktop_dir/forge-controller.desktop" << EOF
[Desktop Entry]
Name=Buildly Forge Controller
Comment=Service manager for Buildly Forge applications
Exec=$SCRIPT_DIR/forge_controller_app.py
Icon=$SCRIPT_DIR/forge_controller/forge-logo.png
Terminal=false
Type=Application
Categories=Development;Utility;
StartupNotify=true
EOF
    
    # Update desktop database if available
    if command -v update-desktop-database &> /dev/null; then
        update-desktop-database "$desktop_dir" 2>/dev/null || true
    fi
    
    print_success "Desktop entry created"
}

# Create macOS app bundle (optional)
setup_macos_app() {
    print_step "Setting up macOS integration..."
    
    # Make the launcher executable
    chmod +x "$SCRIPT_DIR/forge_controller_app.py"
    chmod +x "$SCRIPT_DIR/forge_controller/macos_app.py"
    
    # Create a simple launcher script
    cat > "$SCRIPT_DIR/ForgeController.command" << EOF
#!/bin/bash
cd "$(dirname "\$0")"
python3 forge_controller_app.py
EOF
    chmod +x "$SCRIPT_DIR/ForgeController.command"
    
    print_success "macOS setup complete"
    echo ""
    echo "To add to Login Items:"
    echo "  1. Open System Preferences → Users & Groups → Login Items"
    echo "  2. Click '+' and navigate to: $SCRIPT_DIR"
    echo "  3. Select 'ForgeController.command'"
}

# Main installation
main() {
    print_header
    
    # Detect OS
    OS_TYPE=$(detect_os)
    print_step "Detected operating system: $OS_TYPE"
    
    if [ "$OS_TYPE" = "unknown" ]; then
        print_error "Unknown operating system. Cannot proceed."
        exit 1
    fi
    
    # Check Python
    print_step "Checking Python installation..."
    PYTHON_CMD=$(check_python)
    if [ $? -ne 0 ]; then
        print_error "Python 3 is required but not found."
        echo "Please install Python 3 from https://python.org"
        exit 1
    fi
    print_success "Python found: $($PYTHON_CMD --version)"
    
    # Check pip
    if ! check_pip "$PYTHON_CMD"; then
        print_error "pip is required but not found."
        echo "Please install pip: $PYTHON_CMD -m ensurepip"
        exit 1
    fi
    
    # Install system dependencies (Linux only)
    if [ "$OS_TYPE" = "linux" ]; then
        echo ""
        echo "Linux requires system packages for the GUI."
        read -p "Install system dependencies? (requires sudo) [Y/n]: " response
        if [ "$response" != "n" ] && [ "$response" != "N" ]; then
            install_linux_system_deps
        fi
    fi
    
    # Install Python dependencies
    install_python_deps "$PYTHON_CMD" "$OS_TYPE"
    
    # Copy icons
    copy_icons "$OS_TYPE"
    
    # Make scripts executable
    print_step "Making scripts executable..."
    chmod +x "$SCRIPT_DIR/forge_controller_app.py" 2>/dev/null || true
    chmod +x "$SCRIPT_DIR/forge_controller/"*.py 2>/dev/null || true
    print_success "Scripts are executable"
    
    # Platform-specific setup
    case "$OS_TYPE" in
        linux)
            create_linux_desktop_entry
            ;;
        macos)
            setup_macos_app
            ;;
    esac
    
    echo ""
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║${NC}              Installation Complete!                        ${GREEN}║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    echo ""
    echo "To run the Forge Controller:"
    echo ""
    
    case "$OS_TYPE" in
        macos)
            echo "  $PYTHON_CMD $SCRIPT_DIR/forge_controller_app.py"
            echo ""
            echo "Or double-click: $SCRIPT_DIR/ForgeController.command"
            ;;
        linux)
            echo "  $PYTHON_CMD $SCRIPT_DIR/forge_controller_app.py"
            echo ""
            echo "Or launch from your applications menu: 'Buildly Forge Controller'"
            ;;
        windows)
            echo "  python $SCRIPT_DIR/forge_controller_app.py"
            echo ""
            echo "Or run without console: pythonw forge_controller_app.py"
            ;;
    esac
    
    echo ""
    echo "The controller will scan ports 8000-9000 for running Forge services."
    echo ""
}

# Run main
main "$@"
