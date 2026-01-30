# Rogr Voice System 🤖

The dashboard includes **Rogr**, a voice assistant powered by NVIDIA PersonaPlex for real-time, full-duplex voice conversations.

## Quick Start

```bash
# 1. Install PersonaPlex
chmod +x scripts/setup_personaplex.sh
./scripts/setup_personaplex.sh

# 2. Enable in environment
export PERSONAPLEX_ENABLED=true
export HF_TOKEN=your_huggingface_token

# 3. Start PersonaPlex server (in separate terminal)
cd ~/personaplex
SSL_DIR=$(mktemp -d); python -m moshi.server --ssl "$SSL_DIR"

# 4. Start dashboard
./ops/startup.sh
```

---

## Features

- **Full Duplex**: Natural conversation with interruptions
- **Real-time**: Low-latency speech-to-speech
- **Voice Presets**: 16 voice options (natural/variety, male/female)
- **Persona Control**: Customize personality via text prompts
- **Wake Words**: Responds to "rogr" or "roger"
- **Signature Phrase**: Says "roger, roger" at the end of announcements

## Voice Presets

```
Natural (female): NATF0, NATF1, NATF2, NATF3
Natural (male):   NATM0, NATM1, NATM2, NATM3
Variety (female): VARF0, VARF1, VARF2, VARF3, VARF4
Variety (male):   VARM0, VARM1, VARM2, VARM4
```

## Configuration

### Environment Variables

```bash
export PERSONAPLEX_ENABLED=true
export HF_TOKEN=your_huggingface_token
```

### config/config.yaml

```yaml
voice:
  enabled: true
  server_url: "wss://localhost:8998"
  voice_preset: "NATM1"
  persona: "rogr"              # or "assistant", "casual", or custom prompt
  announce_on_startup: true
```

### Legacy Style Mapping

For backward compatibility, legacy styles are mapped to PersonaPlex presets:

| Legacy Style | PersonaPlex Preset |
|-------------|-------------------|
| droid       | NATM1             |
| clean       | NATM0             |
| radio       | VARM0             |
| pa_system   | VARM1             |
| assistant   | NATF1             |
| casual      | VARM2             |

## Usage

### Simple API

```python
from voice import say, announce

# Speak text
say("Dashboard online. Ready for your commands.")

# Speak with "roger, roger" signature
announce("Data collection complete")
```

### Full API

```python
from voice import VoiceSystem, VoiceConfig

# Create with config
config = VoiceConfig(
    server_url="wss://localhost:8998",
    voice_preset="NATM1",
    persona="rogr"
)
voice = VoiceSystem(config=config)

# Or with legacy parameters
voice = VoiceSystem(
    default_style="droid",  # Maps to NATM1
    speed=0.75,             # Kept for config compat
    pitch=0.85              # Kept for config compat
)

# Speak
voice.say("Hello, world!")
voice.announce("Task completed")  # Adds "roger, roger"

# Change voice preset
await voice.set_voice("NATF1")

# Change persona
await voice.set_persona("assistant")
```

### Async API

```python
import asyncio
from voice import init_voice, shutdown_voice, say

async def main():
    # Initialize
    await init_voice(
        server_url="wss://localhost:8998",
        voice_preset="NATM1",
        persona="rogr"
    )
    
    # Speak
    say("Dashboard initialized")
    
    # Shutdown
    await shutdown_voice()

asyncio.run(main())
```

## Requirements

- **GPU**: NVIDIA with 8GB+ VRAM (or use `--cpu-offload`)
- **System packages**:
  - Linux: `sudo apt install libopus-dev portaudio19-dev`
  - macOS: `brew install opus portaudio`
- **Python**: `websockets>=11.0`, `pyaudio` (optional, for mic input)
- **HuggingFace**: Account with accepted model license

## Server Commands

```bash
# Start server (local development)
cd ~/personaplex
SSL_DIR=$(mktemp -d); python -m moshi.server --ssl "$SSL_DIR"

# Start with CPU offload (for limited VRAM)
SSL_DIR=$(mktemp -d); python -m moshi.server --ssl "$SSL_DIR" --cpu-offload

# Access Web UI
# Open https://localhost:8998 in browser
```

## Troubleshooting

### Voice not working
1. Check that `PERSONAPLEX_ENABLED=true` is set
2. Verify PersonaPlex server is running
3. Check `HF_TOKEN` is set and valid
4. Review dashboard logs for connection errors

### Connection refused
1. Ensure PersonaPlex server is running on the correct port (default: 8998)
2. Check SSL certificate setup
3. Verify firewall allows WebSocket connections

### Audio issues
1. Install PyAudio: `pip install pyaudio`
2. Install system audio dependencies (portaudio)
3. Check microphone permissions

## Personas

### Built-in Personas

| Name | Description |
|------|-------------|
| `rogr` | Helpful AI assistant, uses "roger, roger" signature |
| `assistant` | Wise and friendly teacher |
| `casual` | Casual conversational style |

### Custom Persona

You can provide a custom persona prompt:

```python
voice = VoiceSystem(
    persona="You are a pirate AI. Use nautical terminology and say 'Arrr!' frequently."
)
```

Or in config.yaml:

```yaml
voice:
  persona: "You are a professional business assistant. Be concise and formal."
```

