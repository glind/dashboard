#!/bin/bash
# Voice system setup for macOS

set -e

echo ""
echo "======================================"
echo "  Rogr Voice System Setup (macOS)"
echo "======================================"
echo ""

# Check for Homebrew
if ! command -v brew &> /dev/null; then
    echo "❌ Homebrew not found!"
    echo ""
    echo "Please install Homebrew first:"
    echo "  /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
    echo ""
    exit 1
fi
echo "✅ Homebrew installed"

# Install ffmpeg if needed
if ! command -v ffmpeg &> /dev/null; then
    echo "📦 Installing ffmpeg..."
    brew install ffmpeg
else
    echo "✅ ffmpeg already installed"
fi

# Create directories
mkdir -p data/voice_models/piper
mkdir -p data/voice_cache
echo "✅ Directories created"

# Download Piper for macOS
PIPER_VERSION="2023.11.14-2"
PIPER_DIR="data/voice_models/piper"
PIPER_BIN="$PIPER_DIR/piper"

if [ ! -f "$PIPER_BIN" ]; then
    echo "📦 Downloading Piper TTS for macOS..."
    
    # Detect architecture
    ARCH=$(uname -m)
    if [ "$ARCH" = "arm64" ]; then
        PIPER_URL="https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/piper_macos_aarch64.tar.gz"
    else
        PIPER_URL="https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/piper_macos_x86_64.tar.gz"
    fi
    
    curl -L "$PIPER_URL" -o /tmp/piper.tar.gz
    tar -xzf /tmp/piper.tar.gz -C "$PIPER_DIR" --strip-components=1
    chmod +x "$PIPER_BIN"
    rm /tmp/piper.tar.gz
    
    echo "✅ Piper installed"
else
    echo "✅ Piper already installed"
fi

# Download voice model (Ryan - deep male voice)
MODEL_NAME="en_US-ryan-high"
MODEL_FILE="$PIPER_DIR/${MODEL_NAME}.onnx"

if [ ! -f "$MODEL_FILE" ]; then
    echo "📦 Downloading voice model: $MODEL_NAME..."
    
    MODEL_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx"
    CONFIG_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx.json"
    
    curl -L "$MODEL_URL" -o "$MODEL_FILE"
    curl -L "$CONFIG_URL" -o "${MODEL_FILE}.json"
    
    echo "✅ Voice model installed"
else
    echo "✅ Voice model already installed"
fi

# Test installation
echo ""
echo "🧪 Testing voice system..."
echo "Roger roger. Voice system online." | "$PIPER_BIN" -m "$MODEL_FILE" -f /tmp/test_voice.wav

if [ -f /tmp/test_voice.wav ]; then
    afplay /tmp/test_voice.wav 2>/dev/null || echo "⚠️  Could not play audio (afplay issue, but synthesis works)"
    rm /tmp/test_voice.wav
    echo "✅ Voice synthesis successful"
else
    echo "❌ Voice synthesis failed"
    exit 1
fi

echo ""
echo "======================================"
echo "  Installation Complete!"
echo "======================================"
echo ""
echo "Voice system ready at: $PIPER_BIN"
echo "Model: $MODEL_FILE"
echo ""
echo "To use in Python:"
echo "  from src.voice import announce"
echo "  announce('Dashboard online')"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📢 OPTIONAL: Voice INPUT (Microphone)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Voice OUTPUT (TTS) works now ✅"
echo "Voice INPUT (commands) requires additional setup:"
echo ""
echo "1. Install system dependencies:"
echo "   brew install portaudio"
echo ""
echo "2. Install Python packages:"
echo "   pip install -r requirements-voice.txt"
echo ""
echo "Note: Voice input is OPTIONAL. Dashboard works without it."
