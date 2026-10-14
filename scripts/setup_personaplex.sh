#!/bin/bash
#
# PersonaPlex Voice System Setup
# Installs NVIDIA PersonaPlex for full-duplex voice conversations
#
# Prerequisites:
#   - NVIDIA GPU with CUDA support (recommended 8GB+ VRAM, or use --cpu-offload)
#   - Python 3.10+
#   - HuggingFace account with accepted model license
#
# Usage:
#   ./scripts/setup_personaplex.sh
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
INSTALL_DIR="${PERSONAPLEX_PATH:-$HOME/personaplex}"

echo "🎙️ PersonaPlex Voice System Setup"
echo "=================================="
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

# Check for git
if ! command -v git &> /dev/null; then
    echo "❌ git not found. Please install git first."
    exit 1
fi
echo "   ✅ git found"

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 not found. Please install Python 3.10+"
    exit 1
fi
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "   ✅ Python $PYTHON_VERSION found"

# Check for CUDA (optional but recommended)
if command -v nvidia-smi &> /dev/null; then
    GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader | head -1)
    GPU_MEM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader | head -1)
    echo "   ✅ NVIDIA GPU found: $GPU_NAME ($GPU_MEM)"
else
    echo "   ⚠️  No NVIDIA GPU detected. Will use CPU (slower)"
    CPU_OFFLOAD="--cpu-offload"
fi

# Install system dependencies
echo ""
echo "📦 Installing system dependencies..."

if command -v apt-get &> /dev/null; then
    # Debian/Ubuntu
    sudo apt-get update
    sudo apt-get install -y libopus-dev portaudio19-dev
    echo "   ✅ libopus and portaudio installed"
elif command -v dnf &> /dev/null; then
    # Fedora/RHEL
    sudo dnf install -y opus-devel portaudio-devel
    echo "   ✅ opus and portaudio installed"
elif command -v brew &> /dev/null; then
    # macOS
    brew install opus portaudio
    echo "   ✅ opus and portaudio installed"
else
    echo "   ⚠️  Could not detect package manager. Please install libopus manually."
fi

# Clone PersonaPlex repository
echo ""
echo "📥 Cloning PersonaPlex repository..."

if [ -d "$INSTALL_DIR" ]; then
    echo "   PersonaPlex directory exists. Updating..."
    cd "$INSTALL_DIR"
    git pull
else
    git clone https://github.com/NVIDIA/personaplex.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi
echo "   ✅ PersonaPlex cloned to $INSTALL_DIR"

# Activate project venv if it exists
if [ -d "$PROJECT_ROOT/venv" ]; then
    echo ""
    echo "🔧 Activating project virtual environment..."
    source "$PROJECT_ROOT/venv/bin/activate"
fi

# Install PersonaPlex Python package
echo ""
echo "📦 Installing PersonaPlex Python package..."
pip install "$INSTALL_DIR/moshi/."
echo "   ✅ PersonaPlex Python package installed"

# Install additional dependencies for dashboard integration
echo ""
echo "📦 Installing additional voice dependencies..."
pip install websockets pyaudio SpeechRecognition
echo "   ✅ Voice dependencies installed"

# Check for HuggingFace token
echo ""
echo "🔑 Checking HuggingFace authentication..."
if [ -z "$HF_TOKEN" ]; then
    echo "   ⚠️  HF_TOKEN environment variable not set"
    echo ""
    echo "   To use PersonaPlex, you need to:"
    echo "   1. Create a HuggingFace account at https://huggingface.co"
    echo "   2. Accept the model license at https://huggingface.co/nvidia/personaplex-7b-v1"
    echo "   3. Create an access token at https://huggingface.co/settings/tokens"
    echo "   4. Set the token: export HF_TOKEN=your_token_here"
    echo ""
    read -p "   Enter your HuggingFace token (or press Enter to skip): " HF_TOKEN_INPUT
    if [ -n "$HF_TOKEN_INPUT" ]; then
        echo "export HF_TOKEN=$HF_TOKEN_INPUT" >> "$PROJECT_ROOT/.env"
        echo "   ✅ Token saved to .env file"
    fi
else
    echo "   ✅ HF_TOKEN is set"
fi

# Set PERSONAPLEX_PATH in .env
echo ""
echo "⚙️  Configuring environment..."
if ! grep -q "PERSONAPLEX_PATH" "$PROJECT_ROOT/.env" 2>/dev/null; then
    echo "export PERSONAPLEX_PATH=$INSTALL_DIR" >> "$PROJECT_ROOT/.env"
fi
echo "   ✅ PERSONAPLEX_PATH set to $INSTALL_DIR"

# Create voice config
echo ""
echo "⚙️  Updating voice configuration..."

# Update config.yaml if it exists
if [ -f "$PROJECT_ROOT/config/config.yaml" ]; then
    # Add personaplex section if not present
    if ! grep -q "personaplex:" "$PROJECT_ROOT/config/config.yaml"; then
        cat >> "$PROJECT_ROOT/config/config.yaml" << EOF

# PersonaPlex Voice System (NVIDIA full-duplex speech)
personaplex:
  enabled: true
  server_url: "wss://localhost:8998"
  voice: "NATM1"  # Options: NATF0-3, NATM0-3, VARF0-4, VARM0-4
  persona: "You are Rogr, a helpful AI assistant for a personal dashboard. After commands, say 'roger, roger'."
  cpu_offload: false  # Set true if GPU has <8GB VRAM
EOF
        echo "   ✅ PersonaPlex config added to config.yaml"
    else
        echo "   ℹ️  PersonaPlex config already exists in config.yaml"
    fi
fi

# Test installation
echo ""
echo "🧪 Testing PersonaPlex installation..."
python3 -c "from moshi.server import main; print('PersonaPlex module loaded successfully')" 2>/dev/null && \
    echo "   ✅ PersonaPlex module loads correctly" || \
    echo "   ⚠️  Could not load PersonaPlex module (may need to download model first)"

# Summary
echo ""
echo "=================================="
echo "✅ PersonaPlex Setup Complete!"
echo "=================================="
echo ""
echo "📁 Installation path: $INSTALL_DIR"
echo ""
echo "🚀 To start PersonaPlex server:"
echo "   cd $INSTALL_DIR"
echo "   SSL_DIR=\$(mktemp -d); python -m moshi.server --ssl \"\$SSL_DIR\"${CPU_OFFLOAD:+ $CPU_OFFLOAD}"
echo ""
echo "   Or from the dashboard:"
echo "   python -c \"from voice_personaplex import PersonaPlexServer; s = PersonaPlexServer(); s.start()\""
echo ""
echo "🎤 To use voice in dashboard:"
echo "   The voice system will automatically use PersonaPlex when available."
echo "   Make sure the PersonaPlex server is running first!"
echo ""
echo "📖 Available voices:"
echo "   Natural (female): NATF0, NATF1, NATF2, NATF3"
echo "   Natural (male):   NATM0, NATM1, NATM2, NATM3"
echo "   Variety (female): VARF0, VARF1, VARF2, VARF3, VARF4"
echo "   Variety (male):   VARM0, VARM1, VARM2, VARM3, VARM4"
echo ""
echo "💡 First run will download the model (~14GB) from HuggingFace."
