# Rogr Voice System - Quick Start 🤖

The dashboard includes **Rogr**, a battle-droid-style voice assistant that announces events and responds to voice commands.

## Installation (5 minutes)

### Cross-Platform (Recommended)

```bash
# Auto-detects your OS and runs the right installer
./install_voice.sh
```

### Platform-Specific

**Linux:**
```bash
./scripts/setup_voice.sh
```

**macOS:**
```bash
./scripts/setup_voice_macos.sh
```

**Windows:**
```cmd
scripts\setup_voice_windows.bat
```

### What Gets Installed

- **ffmpeg** - Audio processing (if not already installed)
- **Piper TTS** - Local text-to-speech engine (~100MB)
- **Voice model** - Ryan (deep male voice) (~115MB)
- **Voice cache** - Generated audio files (auto-created)

**Note:** Voice models are ~100-130MB and are NOT stored in git. They download automatically during installation.

## Usage

### In Your Code

```python
from src.voice import say, announce

# Simple announcement
say("Dashboard online")

# With "roger, roger" signature
announce("Three tasks are overdue")

# Different voice styles
say("Radio test", style="radio")
say("PA announcement", style="pa_system")
```

### Voice Commands

When voice listening is enabled, say:
- **"Roger, status"** - Show dashboard status
- **"Roger, refresh"** - Update all data
- **"Roger, tasks"** - Show tasks
- **"Roger, calendar"** - Show calendar

## Configuration

Edit `config/config.yaml`:

```yaml
voice:
  enabled: true
  default_style: "droid"  # Options: clean, droid, radio, pa_system
  announce_on_startup: true
  wake_words:
    - "rogr"
    - "roger"
```

## Features

- ✅ **Local TTS** - Piper engine (fast, private)
- ✅ **Battle-droid voice** - Metallic radio effects
- ✅ **Smart caching** - Instant playback of common phrases
- ✅ **Multiple styles** - Clean, droid, radio, PA system
- ✅ **Wake words** - Responds to "rogr" or "roger"
- ✅ **Signature phrase** - Says "roger, roger" after announcements

## Voice Styles

| Style | Description |
|-------|-------------|
| `droid` (default) | Narrow band, metallic, clipped - battle droid |
| `radio` | Radio transmission, telephone band |
| `pa_system` | PA/intercom announcement |
| `clean` | No effects, pure TTS |

## Files Created

```
data/
  voice_cache/          # Cached audio files (~50KB each)
  voice_models/
    piper/              # TTS engine
      piper             # Binary
      en_US-*.onnx      # Voice model
```

## Troubleshooting

**No audio?**
```bash
# Check ffplay works
ffplay data/voice_cache/droid_*.wav
```

**Microphone not working?**
```bash
# Install PortAudio
sudo apt install portaudio19-dev
pip install --force-reinstall pyaudio
```

**Piper not found?**
```bash
# Re-run setup
./scripts/setup_voice.sh
```

## Legal Notice

- Uses Piper TTS (MIT license) - ✅ Legal
- Voice effects are original audio transformations - ✅ Safe  
- No copyrighted character voices - ✅ Compliant
- "Roger roger" is generic military/CB radio terminology - ✅ Public domain

## Full Documentation

See [`devdocs/VOICE_SYSTEM.md`](devdocs/VOICE_SYSTEM.md) for complete API reference, advanced customization, and integration examples.
