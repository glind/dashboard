#!/bin/bash
# Download additional Piper voice models

set -e

MODELS_DIR="data/voice_models/piper"
mkdir -p "$MODELS_DIR"

echo "════════════════════════════════════════════════"
echo "  Piper Voice Model Downloader"
echo "════════════════════════════════════════════════"
echo ""
echo "Available models:"
echo ""
echo "🔵 Male Voices:"
echo "  1. en_US-ryan-high (115MB) ⭐ Current default - Deep male"
echo "  2. en_US-libritts-high (130MB) - Varied male voice"
echo "  3. en_US-joe-medium (63MB) - Casual male"
echo ""
echo "🟣 Female Voices:"
echo "  4. en_US-lessac-medium (63MB) - Professional female"
echo "  5. en_US-ljspeech-high (106MB) - Clear female"
echo "  6. en_US-amy-medium (63MB) - Friendly female"
echo ""
echo "🟢 Other Languages:"
echo "  7. Browse all: https://huggingface.co/rhasspy/piper-voices/tree/v1.0.0"
echo ""

read -p "Select a model (1-6) or press Enter to cancel: " choice

case $choice in
    1)
        MODEL="en_US-ryan-high"
        BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ryan/high"
        ;;
    2)
        MODEL="en_US-libritts-high"
        BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/libritts/high"
        ;;
    3)
        MODEL="en_US-joe-medium"
        BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/joe/medium"
        ;;
    4)
        MODEL="en_US-lessac-medium"
        BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/lessac/medium"
        ;;
    5)
        MODEL="en_US-ljspeech-high"
        BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/ljspeech/high"
        ;;
    6)
        MODEL="en_US-amy-medium"
        BASE_URL="https://huggingface.co/rhasspy/piper-voices/resolve/v1.0.0/en/en_US/amy/medium"
        ;;
    "")
        echo "Cancelled."
        exit 0
        ;;
    *)
        echo "Invalid choice."
        exit 1
        ;;
esac

MODEL_FILE="$MODELS_DIR/${MODEL}.onnx"
CONFIG_FILE="$MODELS_DIR/${MODEL}.onnx.json"

if [ -f "$MODEL_FILE" ]; then
    echo ""
    echo "⚠️  Model already exists: $MODEL_FILE"
    read -p "Re-download? (y/N): " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Skipped."
        exit 0
    fi
fi

echo ""
echo "📦 Downloading $MODEL..."
echo ""

# Download model
echo "Downloading model file..."
curl -L "${BASE_URL}/${MODEL}.onnx" -o "$MODEL_FILE" --progress-bar

# Download config
echo "Downloading config file..."
curl -L "${BASE_URL}/${MODEL}.onnx.json" -o "$CONFIG_FILE" --progress-bar

echo ""
echo "✅ Download complete!"
echo ""
echo "To use this voice, update config/config.yaml:"
echo ""
echo "voice:"
echo "  model: \"$MODEL\""
echo ""
echo "Then restart the dashboard:"
echo "  ./ops/startup.sh restart"
