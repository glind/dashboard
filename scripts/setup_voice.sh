#!/bin/bash
# Setup voice system dependencies for the dashboard

set -e

echo "🤖 Setting up Rogr voice system..."

# Install ffmpeg if not present
if ! command -v ffmpeg &> /dev/null; then
    echo "📦 Installing ffmpeg..."
    sudo apt update
    sudo apt install -y ffmpeg
else
    echo "✅ ffmpeg already installed"
fi

# Create voice data directory
mkdir -p data/voice_cache
mkdir -p data/voice_models

# Download Piper TTS if not present
PIPER_VERSION="2023.11.14-2"
PIPER_DIR="data/voice_models/piper"
PIPER_BIN="$PIPER_DIR/piper"

if [ ! -f "$PIPER_BIN" ]; then
    echo "📦 Downloading Piper TTS..."
    mkdir -p "$PIPER_DIR"
    
    # Download appropriate version for Linux x64
    PIPER_URL="https://github.com/rhasspy/piper/releases/download/${PIPER_VERSION}/piper_linux_x86_64.tar.gz"
    
    curl -L "$PIPER_URL" -o /tmp/piper.tar.gz
    tar -xzf /tmp/piper.tar.gz -C "$PIPER_DIR" --strip-components=1
    chmod +x "$PIPER_BIN"
    rm /tmp/piper.tar.gz
    
    echo "✅ Piper installed to $PIPER_BIN"
else
    echo "✅ Piper already installed"
fi

# Download a voice model (en_US-ryan-high - deep male voice, perfect for battle-droid)
MODEL_NAME="en_US-ryan-high"
MODEL_FILE="$PIPER_DIR/${MODEL_NAME}.onnx"

if [ ! -f "$MODEL_FILE" ]; then
    echo "📦 Downloading voice model: $MODEL_NAME..."
    
    # Download model and config
    MODEL_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx"
    CONFIG_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high/en_US-ryan-high.onnx.json"
    
    curl -L "$MODEL_URL" -o "$MODEL_FILE"
    curl -L "$CONFIG_URL" -o "${MODEL_FILE}.json"
    
    echo "✅ Voice model installed"
else
    echo "✅ Voice model already installed"
fi

# Test the installation
echo ""
echo "🧪 Testing voice system..."
"$PIPER_BIN" -m "$MODEL_FILE" -f /tmp/test_voice.wav <<< "Roger roger. Voice system online."

if [ -f /tmp/test_voice.wav ]; then
    echo "✅ Voice synthesis successful"
    ffplay -nodisp -autoexit -loglevel quiet /tmp/test_voice.wav 2>/dev/null || echo "⚠️  Could not play audio (ffplay issue, but synthesis works)"
    rm /tmp/test_voice.wav
else
    echo "❌ Voice synthesis failed"
    exit 1
fi

echo ""
echo "✨ Rogr voice system ready!"
echo ""
echo "Usage in Python:"
echo "  from src.voice import announce"
echo "  announce('Dashboard online')"
echo ""
echo "Model location: $MODEL_FILE"
echo "Piper binary: $PIPER_BIN"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📢 OPTIONAL: Voice Input (Microphone Commands)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Voice OUTPUT (TTS) works now ✅"
echo "Voice INPUT (commands) requires additional setup:"
echo ""
echo "1. Install system dependencies:"
echo "   sudo apt install portaudio19-dev python3-pyaudio"
echo ""
echo "2. Install Python packages:"
echo "   pip install -r requirements-voice.txt"
echo ""
echo "3. Test voice commands:"
echo "   python3 src/voice_listener.py"
echo ""
echo "Note: Voice input is OPTIONAL. Dashboard works without it."
