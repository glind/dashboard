# Rogr Voice System 🤖

The dashboard now includes **Rogr**, a battle-droid-style voice assistant that responds to wake words and provides audio feedback throughout the application.

## Features

- **Wake Words**: Responds to "rogr" or "roger"
- **Signature Phrase**: Says "roger, roger" at the end of announcements
- **Battle-Droid Voice**: Metallic, radio-transmission style audio effects
- **Voice Styles**: `droid`, `radio`, `pa_system`, `clean`
- **Smart Caching**: Pre-generates common phrases for instant playback
- **Background Processing**: Non-blocking audio generation and playback

## Setup

### 1. Install Dependencies

Run the setup script to install Piper TTS, ffmpeg, and download voice models:

```bash
chmod +x scripts/setup_voice.sh
./scripts/setup_voice.sh
```

This will:
- Install ffmpeg (if not present)
- Download Piper TTS binary
- Download `en_US-lessac-medium` voice model
- Create voice cache directory
- Test the installation

### 2. Install Python Packages

```bash
source venv/bin/activate
pip install -r requirements.txt
```

This installs:
- `SpeechRecognition` - For voice command listening
- `PyAudio` - For microphone access

### 3. Configure Voice System

Edit `config/config.yaml` (copy from `config.yaml.example`):

```yaml
voice:
  enabled: true
  default_style: "droid"  # Options: clean, droid, radio, pa_system
  announce_on_startup: true
  announce_on_collection: true
  announce_on_error: false
  wake_words:
    - "rogr"
    - "roger"
  signature_phrase: "roger, roger"
```

## Usage

### Basic Voice Output

```python
from src.voice import say, announce

# Simple speech
say("Dashboard online")

# With signature "roger, roger"
announce("Three tasks are overdue")

# Different voice styles
say("Radio transmission test", style="radio")
say("PA system announcement", style="pa_system")
```

### Voice Commands (Listening)

```python
from src.voice_listener import VoiceListener, process_dashboard_command

# Start listening for "rogr" or "roger"
listener = VoiceListener(command_handler=process_dashboard_command)
listener.start()

# Commands will be automatically processed
# Example: Say "Roger, show status" and dashboard will respond
```

### Integrate with Collectors

```python
from src.voice import announce

def collect_data():
    announce("Starting data collection")
    
    # ... your collection logic ...
    
    if success:
        announce("Data collection complete")
    else:
        say("Collection failed. Check logs.", style="radio")
```

## Architecture

### Voice Generation Pipeline

1. **Text Input** → `voice.py:say()`
2. **Cache Check** → Use cached WAV if available
3. **Piper TTS** → Generate raw speech WAV
4. **Audio Effects** → Apply style-specific ffmpeg filters
5. **Cache Save** → Store processed WAV for reuse
6. **Playback** → Non-blocking audio output via ffplay

### Voice Styles

#### Droid (Default)
- Narrow band-pass (200-3400 Hz)
- Heavy compression (4:1 ratio)
- Bit crushing (11-bit)
- Metallic chorus effect
- Short echo/reverb

#### Radio
- Telephone band-pass (300-3000 Hz)
- Moderate compression
- Light bit crushing
- Subtle echo

#### PA System
- Wide band-pass (250-4000 Hz)
- Light compression
- Room reverb

#### Clean
- No effects, pure TTS output

## File Structure

```
dashboard/
├── src/
│   ├── voice.py              # Core voice system
│   └── voice_listener.py     # Wake word detection
├── scripts/
│   └── setup_voice.sh        # Installation script
├── data/
│   ├── voice_cache/          # Cached audio files
│   └── voice_models/
│       └── piper/            # TTS engine & models
│           ├── piper         # Binary
│           └── en_US-*.onnx  # Voice model
└── config/
    └── config.yaml           # Voice settings
```

## API Reference

### VoiceSystem Class

```python
from src.voice import VoiceSystem

voice = VoiceSystem(
    piper_bin="path/to/piper",
    model_path="path/to/model.onnx",
    cache_dir="data/voice_cache",
    default_style="droid"
)

# Generate audio file
wav_path = voice.generate("Hello world", style="droid")

# Play audio
voice.play(wav_path, blocking=False)

# Say with signature
voice.announce("Status ready")

# Preload common phrases
voice.preload_common_phrases([
    "Dashboard online",
    "Three tasks overdue"
])
```

### VoiceListener Class

```python
from src.voice_listener import VoiceListener

def my_handler(command):
    print(f"Heard: {command.wake_word} - {command.command}")

listener = VoiceListener(
    wake_words=["rogr", "roger"],
    command_handler=my_handler
)

listener.start()  # Begin listening
listener.stop()   # Stop listening
```

## Voice Commands

When listening is active, say:

- **"Roger, status"** - Show dashboard status
- **"Roger, refresh"** - Update all data
- **"Roger, tasks"** - Show task summary
- **"Roger, calendar"** - Show upcoming events
- **"Roger, email"** - Show email stats
- **"Roger, GitHub"** - Show GitHub activity
- **"Roger, quiet"** - Silence voice announcements

## Troubleshooting

### No audio output
- Check `ffplay` is installed: `ffplay -version`
- Verify audio device: `pactl list sinks`
- Test with: `ffplay data/voice_cache/droid_*.wav`

### Voice sounds wrong
- Try different voice styles: `say("test", style="clean")`
- Download different Piper voice model
- Adjust ffmpeg filter parameters in `voice.py`

### Microphone not working
- Install PortAudio: `sudo apt install portaudio19-dev`
- Rebuild PyAudio: `pip install --force-reinstall pyaudio`
- Check permissions: `arecord -l`

### Piper not found
- Verify installation: `data/voice_models/piper/piper --version`
- Re-run setup: `./scripts/setup_voice.sh`

## Performance

- **First generation**: ~500ms (TTS + FX)
- **Cached playback**: ~50ms (instant)
- **Memory footprint**: ~2MB per cached phrase
- **Cache storage**: ~50KB per WAV file

## Legal & Safety

- Uses Piper TTS (MIT license) - ✅ Legal
- Voice effects are original transformations - ✅ Safe
- No copyrighted character voices - ✅ Compliant
- "Roger roger" phrase is generic military/CB radio terminology - ✅ Public domain

## Advanced Customization

### Custom Voice Styles

Edit `voice.py` and add to `fx_chains` dict:

```python
"custom_style": (
    "highpass=f=150,"
    "lowpass=f=5000,"
    "acompressor=threshold=-10dB:ratio=2:attack=10:release=100"
)
```

### Change Voice Model

Download from [Piper Voices](https://huggingface.co/rhasspy/piper-voices) and update paths:

```python
voice.model_path = "data/voice_models/piper/en_US-amy-medium.onnx"
```

### Add Custom Wake Words

```python
listener = VoiceListener(wake_words=["hey dashboard", "computer", "jarvis"])
```

## Roadmap

- [ ] Real-time voice activity detection (VAD)
- [ ] Multi-language support
- [ ] Voice speed/pitch controls
- [ ] Custom voice training
- [ ] WebSocket streaming for web UI
- [ ] Voice-controlled navigation

## Credits

- **Piper TTS**: [rhasspy/piper](https://github.com/rhasspy/piper)
- **Voice Models**: Rhasspy community
- **Effects Chain**: Inspired by radio/telecommunications processing
