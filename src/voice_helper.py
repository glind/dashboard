"""
Voice system helper - makes imports easier throughout the codebase

Uses NVIDIA PersonaPlex for real-time, full-duplex voice conversations.
PersonaPlex provides natural speech synthesis with multiple voice presets
and customizable personas.

Configuration:
  - Set PERSONAPLEX_ENABLED=true to enable voice
  - Set HF_TOKEN for HuggingFace authentication
  - See devdocs/VOICE_SYSTEM.md for full setup

Voice presets:
  Natural female: NATF0, NATF1, NATF2, NATF3
  Natural male:   NATM0, NATM1, NATM2, NATM3
  Variety female: VARF0, VARF1, VARF2, VARF3, VARF4
  Variety male:   VARM0, VARM1, VARM2, VARM4
"""

import os
import logging

logger = logging.getLogger(__name__)

# Check if voice system is enabled
VOICE_ENABLED = os.environ.get("PERSONAPLEX_ENABLED", "false").lower() == "true"

if VOICE_ENABLED:
    try:
        from voice import (
            say,
            announce,
            get_voice,
            VoiceSystem,
            VoiceConfig,
            VoicePreset,
            init_voice,
            shutdown_voice,
            PERSONA_PROMPTS,
            STYLE_TO_PRESET
        )
        logger.info("Voice system: PersonaPlex (enabled)")
    except ImportError as e:
        logger.warning(f"Voice system import failed: {e}")
        VOICE_ENABLED = False

if not VOICE_ENABLED:
    # Provide stub functions when voice is disabled
    logger.info("Voice system: disabled (set PERSONAPLEX_ENABLED=true to enable)")
    
    def say(text, **kwargs):
        logger.debug(f"[Voice disabled] {text}")
        return False
    
    def announce(text, **kwargs):
        logger.debug(f"[Voice disabled] {text}")
        return False
    
    def get_voice():
        return None
    
    async def init_voice(**kwargs):
        return False
    
    async def shutdown_voice():
        pass
    
    class VoiceSystem:
        def __init__(self, *args, **kwargs):
            pass
        def say(self, text, **kwargs):
            return False
        def announce(self, text, **kwargs):
            return False
    
    class VoiceConfig:
        pass
    
    VoicePreset = str
    PERSONA_PROMPTS = {}
    STYLE_TO_PRESET = {}

__all__ = [
    'say', 
    'announce', 
    'get_voice', 
    'VoiceSystem',
    'VoiceConfig',
    'VoicePreset',
    'init_voice',
    'shutdown_voice',
    'PERSONA_PROMPTS',
    'STYLE_TO_PRESET',
    'VOICE_ENABLED'
]

