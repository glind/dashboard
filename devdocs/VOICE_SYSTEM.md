# Rogr Voice System 🤖

The dashboard includes **Rogr**, a voice assistant with two backend options:

1. **PersonaPlex (NVIDIA)** - Full-duplex real-time conversations (recommended)
2. **Piper TTS** - Local text-to-speech with battle-droid audio effects (fallback)

## Quick Start

### Option 1: PersonaPlex (Recommended)

PersonaPlex provides real-time, full-duplex voice conversations with natural turn-taking and interruption handling.

```bash
# Install PersonaPlex
chmod +x scripts/setup_personaplex.sh
./scripts/setup_personaplex.sh

# Enable PersonaPlex in environment
export PERSONAPLEX_ENABLED=true
export HF_TOKEN=your_huggingface_token

# Start PersonaPlex server (in separate terminal)
cd ~/personaplex
SSL_DIR=$(mktemp -d); python -m moshi.server --ssl "$SSL_DIR"

# Start dashboard
./ops/startup.sh
```

### Option 2: Piper TTS (Fallback)

Piper TTS provides local text-to-speech with robot/radio voice effects.

```bash
chmod +x scripts/setup_voice.sh
./scripts/setup_voice.sh
```

---

## PersonaPlex Voice System (NVIDIA)

### Features

- **Full Duplex**: Natural conversation with interruptions
- **Real-time**: Low-latency speech-to-speech
- **Voice Presets**: 16 voice options (natural/variety, male/female)
- **Persona Control**: Customize personality via text prompts
- **Based on Moshi**: Built on Kyutai's conversation model

### Voice Presets

```
Natural (female): NATF0, NATF1, NATF2, NATF3
Natural (male):   NATM0, NATM1, NATM2, NATM3
Variety (female): VARF0, VARF1, VARF2, VARF3, VARF4
Variety (male):   VARM0, VARM1, VARM2, VARM3, VARM4
```

### Configuration

Add to `config/config.yaml`:

```yaml
personaplex:
  enabled: true
  server_url: "wss://localhost:8998"
  voice: "NATM1"
  persona: "You are Rogr, a helpful AI assistant for a personal dashboard. After completing commands, acknowledge with 'roger, roger' as your signature phrase."
  cpu_offload: false  # Set true if GPU has <8GB VRAM
```

### Usage

```python
import asyncio
from voice_personaplex import init_personaplex, say_personaplex, shutdown_personaplex

async def main():
    # Initialize
    await init_personaplex(
        server_url="wss://localhost:8998",
        voice="NATM1",
        persona="You are Rogr, a helpful assistant."
    )
    
    # Speak
    say_personaplex("Dashboard online. Ready for your commands.")
    
    # Shutdown
    await shutdown_personaplex()

asyncio.run(main())
```

### Requirements

- **GPU**: NVIDIA with 8GB+ VRAM (or use `--cpu-offload`)
- **System**: libopus-dev, portaudio19-dev
- **Python**: websockets, pyaudio
- **HuggingFace**: Account with accepted model license

### Server Commands

```bash
# Start server (local development)
cd ~/personaplex
SSL_DIR=$(mktemp -d); python -m moshi.server --ssl "$SSL_DIR"

# Start with CPU offload (for limited VRAM)
SSL_DIR=$(mktemp -d); python -m moshi.server --ssl "$SSL_DIR" --cpu-offload

# Access Web UI
# Open https://localhost:8998 in browser
```

---

## Piper TTS Voice System (Legacy)

### Features

- **Wake Words**: Responds to "rogr" or "roger"
- **Signature Phrase**: Says "roger, roger" at the end of announcements
- **Battle-Droid Voice**: Metallic, radio-transmission style audio effects
- **Voice Styles**: `droid`, `radio`, `pa_system`, `clean`
- **Smart Caching**: Pre-generates common phrases for instant playback
- **Background Processing**: Non-blocking audio generation and playback

### Setup

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

### Install Python Packages

```bash
source venv/bin/activate
pip install -r requirements-voice.txt
```

### Configure Voice System

Edit `config/config.yaml`:

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

### Usage

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

---

## Voice Commands

When listening is active, say:

- **"Roger, status"** - Show dashboard status
- **"Roger, refresh"** - Update all data
- **"Roger, tasks"** - Show task summary
- **"Roger, calendar"** - Show upcoming events
- **"Roger, email"** - Show email stats
- **"Roger, GitHub"** - Show GitHub activity
- **"Roger, quiet"** - Silence voice announcements

---

## File Structure

```
dashboard/
├── src/
│   ├── voice.py              # Piper TTS voice system
│   ├── voice_personaplex.py  # PersonaPlex integration
│   ├── voice_helper.py       # Unified import helper
│   └── voice_listener.py     # Wake word detection
├── scripts/
│   ├── setup_voice.sh        # Piper TTS installation
│   └── setup_personaplex.sh  # PersonaPlex installation
├── data/
│   ├── voice_cache/          # Cached audio files
│   └── voice_models/
│       └── piper/            # TTS engine & models
└── config/
    └── config.yaml           # Voice settings
```

---

## Troubleshooting

### PersonaPlex Issues

**Server won't start:**
- Check HF_TOKEN is set: `echo $HF_TOKEN`
- Accept model license at https://huggingface.co/nvidia/personaplex-7b-v1
- First run downloads ~14GB model

**Out of memory:**
- Use `--cpu-offload` flag
- Close other GPU applications
- Try smaller batch size

**Connection refused:**
- Ensure server is running
- Check port 8998 is available
- Verify SSL certificates

### Piper TTS Issues

**No audio output:**
- Check `ffplay` is installed: `ffplay -version`
- Verify audio device: `pactl list sinks`
- Test with: `ffplay data/voice_cache/droid_*.wav`

**Voice sounds wrong:**
- Try different voice styles: `say("test", style="clean")`
- Download different Piper voice model
- Adjust ffmpeg filter parameters in `voice.py`

**Microphone not working:**
- Install PortAudio: `sudo apt install portaudio19-dev`
- Rebuild PyAudio: `pip install --force-reinstall pyaudio`
- Check permissions: `arecord -l`

---

## API Reference

### PersonaPlex

```python
from voice_personaplex import (
    PersonaPlexVoiceSystem,
    init_personaplex,
    say_personaplex,
    announce_personaplex,
    shutdown_personaplex
)

# Async initialization
await init_personaplex(server_url, voice, persona)

# Sync speech (auto-handles event loop)
say_personaplex("Hello world")
announce_personaplex("Task complete")  # Adds "Roger, roger"

# Cleanup
await shutdown_personaplex()
```

### Piper TTS

```python
from voice import VoiceSystem, say, announce

voice = VoiceSystem(
    piper_bin="path/to/piper",
    model_path="path/to/model.onnx",
    cache_dir="data/voice_cache",
    default_style="droid"
)

say("Hello world", style="droid")
announce("Status ready")  # Adds "roger, roger"
```

### Unified Helper

```python
# Automatically uses PersonaPlex if enabled, else Piper
from voice_helper import say, announce, get_voice

say("This works with either backend")
announce("Complete")
```

---

## Credits

- **PersonaPlex**: [NVIDIA/personaplex](https://github.com/NVIDIA/personaplex)
- **Moshi**: [Kyutai](https://kyutai.org/) - Base conversational model
- **Piper TTS**: [rhasspy/piper](https://github.com/rhasspy/piper)
- **Voice Models**: Rhasspy community

