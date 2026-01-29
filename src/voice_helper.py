"""
Voice system helper - makes imports easier throughout the codebase

Supports two voice backends:
1. PersonaPlex (NVIDIA) - Full-duplex real-time conversation (recommended)
2. Piper TTS - Local text-to-speech with audio effects (fallback)

PersonaPlex is used when:
- PERSONAPLEX_ENABLED=true in environment
- PersonaPlex server is running at configured URL

Otherwise falls back to Piper TTS.
"""

import os
import logging

logger = logging.getLogger(__name__)

# Check which voice system to use
USE_PERSONAPLEX = os.environ.get("PERSONAPLEX_ENABLED", "false").lower() == "true"

if USE_PERSONAPLEX:
    try:
        from voice_personaplex import (
            say_personaplex as say,
            announce_personaplex as announce,
            get_personaplex_voice as get_voice,
            PersonaPlexVoiceSystem as VoiceSystem,
            init_personaplex,
            shutdown_personaplex,
            VoicePreset,
            DEFAULT_PERSONA_PROMPT
        )
        logger.info("Voice system: PersonaPlex (NVIDIA)")
    except ImportError as e:
        logger.warning(f"PersonaPlex import failed: {e}, falling back to Piper TTS")
        USE_PERSONAPLEX = False

if not USE_PERSONAPLEX:
    try:
        from voice import say, announce, get_voice, VoiceSystem
        logger.info("Voice system: Piper TTS")
    except ImportError as e:
        logger.warning(f"Voice system not available: {e}")
        # Provide dummy functions
        def say(text, **kwargs):
            logger.info(f"[Voice disabled] {text}")
        
        def announce(text, **kwargs):
            logger.info(f"[Voice disabled] {text}")
        
        def get_voice():
            return None
        
        class VoiceSystem:
            pass

__all__ = ['say', 'announce', 'get_voice', 'VoiceSystem']
