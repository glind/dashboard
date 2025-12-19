#!/bin/bash
# Quick test script for Rogr voice system

set -e

echo "🤖 Testing Rogr Voice System"
echo ""

# Check dependencies
echo "Checking dependencies..."
command -v ffmpeg >/dev/null 2>&1 || { echo "❌ ffmpeg not found. Run ./scripts/setup_voice.sh"; exit 1; }
command -v ffplay >/dev/null 2>&1 || { echo "❌ ffplay not found. Run ./scripts/setup_voice.sh"; exit 1; }

PIPER_BIN="data/voice_models/piper/piper"
MODEL_FILE="data/voice_models/piper/en_US-ryan-high.onnx"

if [ ! -f "$PIPER_BIN" ]; then
    echo "❌ Piper not found. Run ./scripts/setup_voice.sh"
    exit 1
fi

if [ ! -f "$MODEL_FILE" ]; then
    echo "❌ Voice model not found. Run ./scripts/setup_voice.sh"
    exit 1
fi

echo "✅ All dependencies present"
echo ""

# Test voice generation
echo "Testing voice styles..."
echo ""

mkdir -p /tmp/voice_test

# Test phrases
PHRASES=(
    "Dashboard online"
    "Three tasks are overdue"
    "Daily summary ready"
    "Roger roger"
)

# Test styles
STYLES=("clean" "droid" "radio" "pa_system")

for style in "${STYLES[@]}"; do
    echo "🔊 Testing style: $style"
    
    # Generate raw speech
    echo "  Generating speech..."
    echo "${PHRASES[0]}" | "$PIPER_BIN" -m "$MODEL_FILE" -f /tmp/voice_test/raw.wav
    
    # Apply effects based on style
    case $style in
        "clean")
            cp /tmp/voice_test/raw.wav /tmp/voice_test/${style}.wav
            ;;
        "droid")
            ffmpeg -y -loglevel error -i /tmp/voice_test/raw.wav \
                -af "highpass=f=200,lowpass=f=3400,acompressor=threshold=-16dB:ratio=4:attack=3:release=50,acrusher=bits=11:mix=0.3,chorus=0.5:0.7:30:0.35:0.2:2,aecho=0.8:0.6:20:0.2,highpass=f=180" \
                /tmp/voice_test/${style}.wav
            ;;
        "radio")
            ffmpeg -y -loglevel error -i /tmp/voice_test/raw.wav \
                -af "highpass=f=300,lowpass=f=3000,acompressor=threshold=-14dB:ratio=3:attack=5:release=80,acrusher=bits=12:mix=0.2,aecho=0.7:0.5:15:0.15" \
                /tmp/voice_test/${style}.wav
            ;;
        "pa_system")
            ffmpeg -y -loglevel error -i /tmp/voice_test/raw.wav \
                -af "highpass=f=250,lowpass=f=4000,acompressor=threshold=-12dB:ratio=2.5:attack=10:release=100,aecho=0.9:0.8:40:0.3" \
                /tmp/voice_test/${style}.wav
            ;;
    esac
    
    # Play the result
    echo "  Playing..."
    ffplay -nodisp -autoexit -loglevel quiet /tmp/voice_test/${style}.wav 2>/dev/null
    echo "  ✅ Done"
    echo ""
done

# Cleanup
rm -rf /tmp/voice_test

echo "✨ Voice system test complete!"
echo ""
echo "To use in Python:"
echo "  from src.voice import say, announce"
echo "  announce('Dashboard ready')"
