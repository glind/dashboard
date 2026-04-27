#!/usr/bin/env python3
"""
Unified Voice System for Dashboard - "Rogr" AI Assistant

Uses NVIDIA PersonaPlex for real-time, full-duplex voice conversations.
Maintains backward compatibility with previous configuration options.

Configuration (via config.yaml):
  voice:
    enabled: true
    voice_preset: "NATM1"      # Voice: NATF0-3, NATM0-3, VARF0-4, VARM0-4
    persona: "rogr"            # Personality: rogr, assistant, casual
    server_url: "wss://localhost:8998"
    announce_on_startup: true

Environment variables:
  PERSONAPLEX_ENABLED=true     # Enable voice system
  HF_TOKEN=xxx                 # HuggingFace token for model access
"""

import asyncio
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Literal

logger = logging.getLogger(__name__)

def strip_markdown(text: str) -> str:
    """
    Strip Markdown syntax from text for speech.
    Removes formatting markers while keeping the content readable.
    """
    if not text:
        return text
    
    cleaned = text
    
    # Remove code blocks entirely (they don't speak well)
    cleaned = re.sub(r'```[\s\S]*?```', ' code block ', cleaned)
    
    # Remove inline code backticks
    cleaned = re.sub(r'`([^`]+)`', r'\1', cleaned)
    
    # Remove header markers
    cleaned = re.sub(r'^#{1,6}\s+', '', cleaned, flags=re.MULTILINE)
    
    # Remove bold markers
    cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', cleaned)
    cleaned = re.sub(r'__([^_]+)__', r'\1', cleaned)
    
    # Remove italic markers
    cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)
    cleaned = re.sub(r'(?<![a-zA-Z])_([^_]+)_(?![a-zA-Z])', r'\1', cleaned)
    
    # Remove strikethrough
    cleaned = re.sub(r'~~([^~]+)~~', r'\1', cleaned)
    
    # Convert links to just the text
    cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)
    
    # Remove blockquote markers
    cleaned = re.sub(r'^>\s*', '', cleaned, flags=re.MULTILINE)
    
    # Remove list markers
    cleaned = re.sub(r'^[\-\*]\s+', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'^\d+\.\s+', '', cleaned, flags=re.MULTILINE)
    
    # Remove horizontal rules
    cleaned = re.sub(r'^---$', '', cleaned, flags=re.MULTILINE)
    
    # Remove excess whitespace
    cleaned = re.sub(r'\n{3,}', '\n\n', cleaned)
    
    return cleaned


def sanitize_text_for_speech(text: str) -> str:
    """
    Clean text for natural speech by removing or replacing elements that
    don't sound good when spoken aloud.
    
    Removes:
    - Markdown syntax (bold, italic, code, links, etc.)
    - URLs (http/https/www links)
    - Email addresses
    - Hash strings (sha256, md5, etc.)
    - Long numeric sequences (> 6 digits)
    - UUIDs
    - File paths
    - JSON/code snippets
    - Long hexadecimal strings
    
    Returns:
        Cleaned text suitable for speech synthesis
    """
    if not text:
        return text
    
    # First strip markdown syntax
    text = strip_markdown(text)
    
    # URL patterns
    text = re.sub(r'https?://[^\s<>"{}|\\^`\[\]]+', 'link', text)
    text = re.sub(r'www\.[^\s<>"{}|\\^`\[\]]+', 'link', text)
    
    # Email addresses
    text = re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', 'email address', text)
    
    # UUIDs (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx)
    text = re.sub(r'[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}', 'ID', text)
    
    # SHA256/SHA512/MD5 hashes (long hex strings 32+ chars)
    text = re.sub(r'\b[a-fA-F0-9]{32,}\b', 'hash', text)
    
    # Long hex strings (16+ chars that look like hex)
    text = re.sub(r'\b0x[a-fA-F0-9]{8,}\b', 'hex value', text)
    
    # Long numeric sequences (phone numbers OK, but skip 7+ digit sequences)
    text = re.sub(r'\b\d{7,}\b', 'number', text)
    
    # File paths (Unix and Windows)
    text = re.sub(r'[/\\][\w./\\-]{10,}', ' file path ', text)
    
    # Base64-like strings (long alphanumeric with + / =)
    text = re.sub(r'[A-Za-z0-9+/=]{40,}', 'encoded data', text)
    
    # JSON-like content in curly braces (if long)
    text = re.sub(r'\{[^{}]{100,}\}', 'data object', text)
    
    # Code-like content with special chars
    text = re.sub(r'[\[\]{}();]{3,}', '', text)
    
    # Multiple consecutive special characters
    text = re.sub(r'[_\-=]{4,}', ' ', text)
    
    # Clean up multiple spaces
    text = re.sub(r'\s+', ' ', text)
    
    # Clean up artifacts
    text = text.strip()
    
    return text

# Voice presets from PersonaPlex
VoicePreset = Literal[
    "NATF0", "NATF1", "NATF2", "NATF3",  # Natural female
    "NATM0", "NATM1", "NATM2", "NATM3",  # Natural male
    "VARF0", "VARF1", "VARF2", "VARF3", "VARF4",  # Variety female
    "VARM0", "VARM1", "VARM2", "VARM4",  # Variety male
]

# Style to voice preset mapping (backward compatibility)
STYLE_TO_PRESET = {
    "droid": "NATM1",
    "clean": "NATM0",
    "radio": "VARM0",
    "pa_system": "VARM1",
    "assistant": "NATF1",
    "casual": "VARM2",
}

# Persona prompts
PERSONA_PROMPTS = {
    "rogr": """You are Rogr, a helpful AI assistant for a personal dashboard application.
You answer questions clearly and concisely. You help with productivity, scheduling, and information lookup.
After completing commands, you acknowledge with "roger, roger" as your signature phrase.""",
    "assistant": """You are a wise and friendly teacher. Answer questions or provide advice in a clear and engaging way.""",
    "casual": """You enjoy having a good conversation. You are Rogr, a helpful assistant for a personal dashboard.""",
}


@dataclass
class VoiceConfig:
    """Configuration for the voice system"""
    enabled: bool = True
    server_url: str = "wss://localhost:8998"
    voice_preset: str = "NATM1"
    persona: str = "rogr"
    hf_token: Optional[str] = None
    ssl_verify: bool = False
    announce_on_startup: bool = True
    default_style: str = "droid"
    speed: float = 0.75
    pitch: float = 0.85

class VoiceSystem:
    """Unified voice system using NVIDIA PersonaPlex."""
    
    def __init__(
        self,
        config: Optional[VoiceConfig] = None,
        default_style: str = "droid",
        speed: float = 0.75,
        pitch: float = 0.85,
        server_url: str = "wss://localhost:8998",
        voice_preset: Optional[str] = None,
        persona: str = "rogr"
    ):
        if config:
            self.config = config
        else:
            preset = voice_preset or STYLE_TO_PRESET.get(default_style, "NATM1")
            self.config = VoiceConfig(
                enabled=True,
                server_url=server_url,
                voice_preset=preset,
                persona=persona,
                hf_token=os.environ.get("HF_TOKEN"),
                default_style=default_style,
                speed=speed,
                pitch=pitch
            )
        
        self._client = None
        self._running = False
        self._pyaudio = None
        self._audio_stream = None
        self._mic_stream = None
        
        self.wake_words = ["rogr", "roger"]
        self.signature = "roger, roger"
        
        logger.info(f"Voice system initialized: preset={self.config.voice_preset}, persona={self.config.persona}")
    
    async def _get_client(self):
        """Get or create the PersonaPlex client"""
        if self._client is not None:
            return self._client
        
        try:
            import websockets
            import ssl
            import json
            
            ssl_context = ssl.create_default_context()
            if not self.config.ssl_verify:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            
            self._client = await websockets.connect(
                self.config.server_url,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10
            )
            
            persona_prompt = PERSONA_PROMPTS.get(self.config.persona, self.config.persona)
            init_msg = {
                "type": "init",
                "voice_prompt": f"{self.config.voice_preset}.pt",
                "text_prompt": persona_prompt
            }
            await self._client.send(json.dumps(init_msg))
            
            logger.info(f"Connected to PersonaPlex at {self.config.server_url}")
            return self._client
            
        except ImportError:
            logger.error("websockets package not installed. Run: pip install websockets")
            return None
        except Exception as e:
            logger.error(f"Failed to connect to PersonaPlex: {e}")
            return None
    
    async def _disconnect(self):
        """Disconnect from PersonaPlex"""
        if self._client:
            await self._client.close()
            self._client = None
            logger.info("Disconnected from PersonaPlex")
    
    async def say_async(self, text: str, skip_sanitize: bool = False) -> bool:
        """Send text to be spoken by PersonaPlex (async)
        
        Args:
            text: Text to speak
            skip_sanitize: If True, skip text sanitization (for pre-cleaned text)
        """
        try:
            # Sanitize text for natural speech unless skipped
            if not skip_sanitize:
                text = sanitize_text_for_speech(text)
            
            if not text or len(text.strip()) < 2:
                logger.debug("Skipping empty or too-short text")
                return True
            
            client = await self._get_client()
            if not client:
                logger.warning(f"PersonaPlex not available. Would say: {text}")
                return False
            
            import json
            msg = {"type": "text", "content": text}
            await client.send(json.dumps(msg))
            logger.debug(f"Sent to PersonaPlex: {text}")
            return True
        except Exception as e:
            logger.error(f"Failed to send text to PersonaPlex: {e}")
            return False
    
    def say(
        self,
        text: str,
        style: Optional[str] = None,
        add_signature: bool = False,
        blocking: bool = False
    ) -> bool:
        """Generate and play speech using PersonaPlex."""
        if add_signature:
            text = f"{text}. {self.signature}"
        
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.say_async(text))
                return True
            else:
                return loop.run_until_complete(self.say_async(text))
        except RuntimeError:
            return asyncio.run(self.say_async(text))
    
    def announce(self, text: str, **kwargs) -> bool:
        """Say with 'roger, roger' signature"""
        return self.say(text, add_signature=True, **kwargs)
    
    async def set_voice(self, voice: str) -> bool:
        """Change voice preset"""
        try:
            client = await self._get_client()
            if not client:
                return False
            import json
            msg = {"type": "update_voice", "voice_prompt": f"{voice}.pt"}
            await client.send(json.dumps(msg))
            self.config.voice_preset = voice
            logger.info(f"Voice changed to: {voice}")
            return True
        except Exception as e:
            logger.error(f"Failed to change voice: {e}")
            return False
    
    async def set_persona(self, persona: str) -> bool:
        """Change persona/role"""
        try:
            client = await self._get_client()
            if not client:
                return False
            import json
            prompt = PERSONA_PROMPTS.get(persona, persona)
            msg = {"type": "update_prompt", "text_prompt": prompt}
            await client.send(json.dumps(msg))
            self.config.persona = persona
            logger.info(f"Persona changed to: {persona}")
            return True
        except Exception as e:
            logger.error(f"Failed to change persona: {e}")
            return False
    
    def preload_common_phrases(self, phrases: list) -> None:
        """Pre-cache common phrases (no-op for PersonaPlex)"""
        logger.debug("Preload skipped - PersonaPlex uses real-time synthesis")
    
    def generate(
        self,
        text: str,
        style: Optional[str] = None,
        force: bool = False
    ) -> Optional[Path]:
        """Generate voice audio (compatibility method)"""
        logger.warning("generate() not supported with PersonaPlex - use say() instead")
        return None
    
    async def shutdown(self):
        """Clean up resources"""
        await self._disconnect()
        if self._pyaudio:
            self._pyaudio.terminate()
        logger.info("Voice system shutdown complete")


# =============================================================================
# Singleton and convenience functions
# =============================================================================

_voice: Optional[VoiceSystem] = None


def get_voice() -> VoiceSystem:
    """Get or create the global voice system instance"""
    global _voice
    if _voice is None:
        _voice = VoiceSystem()
    return _voice


def say(text: str, **kwargs) -> bool:
    """Convenience function: generate and play speech"""
    return get_voice().say(text, **kwargs)


def announce(text: str, **kwargs) -> bool:
    """Convenience function: say with 'roger, roger' signature"""
    return get_voice().announce(text, **kwargs)


async def init_voice(
    server_url: str = "wss://localhost:8998",
    voice_preset: str = "NATM1",
    persona: str = "rogr"
) -> bool:
    """Initialize the voice system"""
    global _voice
    config = VoiceConfig(
        server_url=server_url,
        voice_preset=voice_preset,
        persona=persona,
        hf_token=os.environ.get("HF_TOKEN")
    )
    _voice = VoiceSystem(config=config)
    try:
        await _voice._get_client()
        return True
    except:
        return False


async def shutdown_voice():
    """Shutdown the voice system"""
    global _voice
    if _voice:
        await _voice.shutdown()
        _voice = None
