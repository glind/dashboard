#!/usr/bin/env python3
"""
PersonaPlex Voice System Integration

Integrates NVIDIA PersonaPlex for real-time, full-duplex voice conversations.
PersonaPlex supports voice conditioning and persona control via text prompts.

See: https://github.com/NVIDIA/personaplex
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
import threading
import websockets
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, Literal

logger = logging.getLogger(__name__)

# Available voice presets from PersonaPlex
VoicePreset = Literal[
    "NATF0", "NATF1", "NATF2", "NATF3",  # Natural female
    "NATM0", "NATM1", "NATM2", "NATM3",  # Natural male
    "VARF0", "VARF1", "VARF2", "VARF3", "VARF4",  # Variety female
    "VARM0", "VARM1", "VARM2", "VARM3", "VARM4",  # Variety male
]

DEFAULT_PERSONA_PROMPT = """You are Rogr, a helpful AI assistant for a personal dashboard application. 
You answer questions clearly and concisely. You help with productivity, scheduling, and information lookup.
After completing commands, you acknowledge with "roger, roger" as your signature phrase."""

ASSISTANT_PROMPT = """You are a wise and friendly teacher. Answer questions or provide advice in a clear and engaging way."""

CASUAL_PROMPT = """You enjoy having a good conversation. You are Rogr, a helpful assistant for a personal dashboard."""


@dataclass
class PersonaPlexConfig:
    """Configuration for PersonaPlex voice system"""
    server_url: str = "wss://localhost:8998"
    voice_preset: VoicePreset = "NATM1"  # Natural male voice
    persona_prompt: str = DEFAULT_PERSONA_PROMPT
    hf_token: Optional[str] = None
    ssl_verify: bool = False  # Local dev with self-signed certs
    cpu_offload: bool = False  # For lower VRAM GPUs


class PersonaPlexClient:
    """
    WebSocket client for PersonaPlex server communication.
    Handles real-time bidirectional audio streaming.
    """
    
    def __init__(self, config: PersonaPlexConfig):
        self.config = config
        self.websocket = None
        self.connected = False
        self.audio_callback: Optional[Callable[[bytes], None]] = None
        self.text_callback: Optional[Callable[[str], None]] = None
        self._receive_task = None
        
    async def connect(self) -> bool:
        """Connect to PersonaPlex WebSocket server"""
        try:
            import ssl
            ssl_context = ssl.create_default_context()
            if not self.config.ssl_verify:
                ssl_context.check_hostname = False
                ssl_context.verify_mode = ssl.CERT_NONE
            
            self.websocket = await websockets.connect(
                self.config.server_url,
                ssl=ssl_context,
                ping_interval=20,
                ping_timeout=10
            )
            self.connected = True
            
            # Send initial configuration
            init_msg = {
                "type": "init",
                "voice_prompt": f"{self.config.voice_preset}.pt",
                "text_prompt": self.config.persona_prompt
            }
            await self.websocket.send(json.dumps(init_msg))
            
            # Start receive loop
            self._receive_task = asyncio.create_task(self._receive_loop())
            
            logger.info(f"Connected to PersonaPlex server at {self.config.server_url}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to PersonaPlex: {e}")
            self.connected = False
            return False
    
    async def disconnect(self):
        """Disconnect from PersonaPlex server"""
        self.connected = False
        if self._receive_task:
            self._receive_task.cancel()
        if self.websocket:
            await self.websocket.close()
        logger.info("Disconnected from PersonaPlex")
    
    async def _receive_loop(self):
        """Receive audio/text responses from server"""
        try:
            while self.connected and self.websocket:
                message = await self.websocket.recv()
                
                if isinstance(message, bytes):
                    # Audio data
                    if self.audio_callback:
                        self.audio_callback(message)
                else:
                    # Text/JSON message
                    try:
                        data = json.loads(message)
                        if data.get("type") == "transcript" and self.text_callback:
                            self.text_callback(data.get("text", ""))
                    except json.JSONDecodeError:
                        if self.text_callback:
                            self.text_callback(message)
                            
        except websockets.exceptions.ConnectionClosed:
            logger.info("PersonaPlex connection closed")
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"PersonaPlex receive error: {e}")
        finally:
            self.connected = False
    
    async def send_audio(self, audio_data: bytes):
        """Send audio data to PersonaPlex for processing"""
        if self.connected and self.websocket:
            await self.websocket.send(audio_data)
    
    async def send_text(self, text: str):
        """Send text message to PersonaPlex"""
        if self.connected and self.websocket:
            msg = {"type": "text", "content": text}
            await self.websocket.send(json.dumps(msg))
    
    async def update_persona(self, prompt: str):
        """Update the persona/role prompt"""
        if self.connected and self.websocket:
            msg = {"type": "update_prompt", "text_prompt": prompt}
            await self.websocket.send(json.dumps(msg))
            self.config.persona_prompt = prompt
    
    async def change_voice(self, voice: VoicePreset):
        """Change the voice preset"""
        if self.connected and self.websocket:
            msg = {"type": "update_voice", "voice_prompt": f"{voice}.pt"}
            await self.websocket.send(json.dumps(msg))
            self.config.voice_preset = voice


class PersonaPlexVoiceSystem:
    """
    Full voice system using PersonaPlex for speech-to-speech conversation.
    Replaces the Piper TTS + SpeechRecognition approach with NVIDIA's
    full-duplex conversational AI.
    """
    
    def __init__(
        self,
        server_url: str = "wss://localhost:8998",
        voice: VoicePreset = "NATM1",
        persona: str = DEFAULT_PERSONA_PROMPT,
        hf_token: Optional[str] = None
    ):
        self.config = PersonaPlexConfig(
            server_url=server_url,
            voice_preset=voice,
            persona_prompt=persona,
            hf_token=hf_token or os.environ.get("HF_TOKEN")
        )
        self.client = PersonaPlexClient(self.config)
        self._audio_thread = None
        self._running = False
        
        # Audio playback
        try:
            import pyaudio
            self.pyaudio = pyaudio.PyAudio()
            self.audio_stream = None
            self.has_audio = True
        except ImportError:
            self.pyaudio = None
            self.has_audio = False
            logger.warning("PyAudio not available - audio playback disabled")
        
        # Audio capture
        try:
            import pyaudio
            self.mic_stream = None
        except ImportError:
            pass
    
    def _audio_callback(self, audio_data: bytes):
        """Handle incoming audio from PersonaPlex"""
        if self.audio_stream and self.has_audio:
            try:
                self.audio_stream.write(audio_data)
            except Exception as e:
                logger.error(f"Audio playback error: {e}")
    
    def _text_callback(self, text: str):
        """Handle incoming text transcripts"""
        logger.info(f"PersonaPlex: {text}")
    
    async def start(self) -> bool:
        """Start the voice system"""
        if not await self.client.connect():
            return False
        
        self.client.audio_callback = self._audio_callback
        self.client.text_callback = self._text_callback
        
        # Start audio output stream
        if self.has_audio:
            self.audio_stream = self.pyaudio.open(
                format=self.pyaudio.get_format_from_width(2),
                channels=1,
                rate=24000,  # PersonaPlex uses 24kHz
                output=True,
                frames_per_buffer=1024
            )
        
        self._running = True
        logger.info("PersonaPlex voice system started")
        return True
    
    async def stop(self):
        """Stop the voice system"""
        self._running = False
        await self.client.disconnect()
        
        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
        
        if self.mic_stream:
            self.mic_stream.stop_stream()
            self.mic_stream.close()
        
        if self.pyaudio:
            self.pyaudio.terminate()
        
        logger.info("PersonaPlex voice system stopped")
    
    async def start_listening(self):
        """Start capturing microphone audio and sending to PersonaPlex"""
        if not self.has_audio:
            logger.error("PyAudio required for microphone input")
            return
        
        self.mic_stream = self.pyaudio.open(
            format=self.pyaudio.get_format_from_width(2),
            channels=1,
            rate=24000,
            input=True,
            frames_per_buffer=1024
        )
        
        logger.info("Listening... (speak to PersonaPlex)")
        
        while self._running:
            try:
                audio_data = self.mic_stream.read(1024, exception_on_overflow=False)
                await self.client.send_audio(audio_data)
                await asyncio.sleep(0.01)  # Small delay to prevent overwhelming
            except Exception as e:
                logger.error(f"Mic capture error: {e}")
                break
    
    def stop_listening(self):
        """Stop microphone capture"""
        if self.mic_stream:
            self.mic_stream.stop_stream()
            self.mic_stream.close()
            self.mic_stream = None
    
    async def say(self, text: str):
        """Send text to be spoken by PersonaPlex"""
        await self.client.send_text(text)
    
    async def set_voice(self, voice: VoicePreset):
        """Change voice preset"""
        await self.client.change_voice(voice)
    
    async def set_persona(self, prompt: str):
        """Change persona/role"""
        await self.client.update_persona(prompt)


class PersonaPlexServer:
    """
    Manages the PersonaPlex server process.
    Starts/stops the server as needed.
    """
    
    def __init__(
        self,
        personaplex_path: str = None,
        port: int = 8998,
        voice: VoicePreset = "NATM1",
        cpu_offload: bool = False
    ):
        self.personaplex_path = personaplex_path or os.environ.get(
            "PERSONAPLEX_PATH",
            str(Path.home() / "personaplex")
        )
        self.port = port
        self.voice = voice
        self.cpu_offload = cpu_offload
        self.process = None
        self.ssl_dir = None
    
    def is_installed(self) -> bool:
        """Check if PersonaPlex is installed"""
        moshi_path = Path(self.personaplex_path) / "moshi"
        return moshi_path.exists()
    
    def start(self) -> bool:
        """Start the PersonaPlex server"""
        if not self.is_installed():
            logger.error(f"PersonaPlex not found at {self.personaplex_path}")
            return False
        
        import tempfile
        self.ssl_dir = tempfile.mkdtemp()
        
        cmd = [
            sys.executable, "-m", "moshi.server",
            "--ssl", self.ssl_dir,
            "--port", str(self.port)
        ]
        
        if self.cpu_offload:
            cmd.append("--cpu-offload")
        
        env = os.environ.copy()
        if not env.get("HF_TOKEN"):
            logger.warning("HF_TOKEN not set - may fail to download model")
        
        try:
            self.process = subprocess.Popen(
                cmd,
                cwd=self.personaplex_path,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            # Wait for server to start
            import time
            for _ in range(30):  # 30 second timeout
                if self._check_server():
                    logger.info(f"PersonaPlex server started on port {self.port}")
                    return True
                time.sleep(1)
            
            logger.error("PersonaPlex server failed to start within timeout")
            self.stop()
            return False
            
        except Exception as e:
            logger.error(f"Failed to start PersonaPlex server: {e}")
            return False
    
    def _check_server(self) -> bool:
        """Check if server is responding"""
        import socket
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('localhost', self.port))
            sock.close()
            return result == 0
        except:
            return False
    
    def stop(self):
        """Stop the PersonaPlex server"""
        if self.process:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
            logger.info("PersonaPlex server stopped")
        
        # Clean up SSL directory
        if self.ssl_dir:
            import shutil
            shutil.rmtree(self.ssl_dir, ignore_errors=True)
            self.ssl_dir = None


# =============================================================================
# Convenience functions matching the original voice.py API
# =============================================================================

_voice_system: Optional[PersonaPlexVoiceSystem] = None
_event_loop: Optional[asyncio.AbstractEventLoop] = None


def get_personaplex_voice() -> Optional[PersonaPlexVoiceSystem]:
    """Get the global PersonaPlex voice system instance"""
    return _voice_system


async def init_personaplex(
    server_url: str = "wss://localhost:8998",
    voice: VoicePreset = "NATM1",
    persona: str = DEFAULT_PERSONA_PROMPT
) -> bool:
    """Initialize the PersonaPlex voice system"""
    global _voice_system
    
    _voice_system = PersonaPlexVoiceSystem(
        server_url=server_url,
        voice=voice,
        persona=persona
    )
    
    return await _voice_system.start()


async def shutdown_personaplex():
    """Shutdown the PersonaPlex voice system"""
    global _voice_system
    if _voice_system:
        await _voice_system.stop()
        _voice_system = None


def say_personaplex(text: str):
    """
    Speak text using PersonaPlex (blocking wrapper).
    Compatible with original voice.py API.
    """
    if not _voice_system:
        logger.warning("PersonaPlex not initialized")
        return
    
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(_voice_system.say(text))
        else:
            loop.run_until_complete(_voice_system.say(text))
    except RuntimeError:
        # No event loop - create one
        asyncio.run(_voice_system.say(text))


def announce_personaplex(text: str):
    """
    Announce text with signature phrase.
    Compatible with original voice.py API.
    """
    say_personaplex(f"{text}. Roger, roger.")


# =============================================================================
# Installation helper
# =============================================================================

def install_personaplex(install_path: str = None) -> bool:
    """
    Clone and install PersonaPlex from GitHub.
    Requires: git, pip, libopus-dev
    """
    install_path = install_path or str(Path.home() / "personaplex")
    
    logger.info(f"Installing PersonaPlex to {install_path}")
    
    # Check prerequisites
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
    except:
        logger.error("git not found - please install git")
        return False
    
    # Clone repository
    if not Path(install_path).exists():
        try:
            subprocess.run([
                "git", "clone",
                "https://github.com/NVIDIA/personaplex.git",
                install_path
            ], check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"Failed to clone PersonaPlex: {e}")
            return False
    
    # Install Python package
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install",
            str(Path(install_path) / "moshi") + "/."
        ], check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install PersonaPlex Python package: {e}")
        return False
    
    logger.info("PersonaPlex installed successfully!")
    logger.info("Next steps:")
    logger.info("  1. Install libopus: sudo apt install libopus-dev")
    logger.info("  2. Set HF_TOKEN environment variable")
    logger.info("  3. Accept model license at https://huggingface.co/nvidia/personaplex-7b-v1")
    
    return True


if __name__ == "__main__":
    # Quick test
    import argparse
    
    parser = argparse.ArgumentParser(description="PersonaPlex Voice System")
    parser.add_argument("--install", action="store_true", help="Install PersonaPlex")
    parser.add_argument("--server", action="store_true", help="Start PersonaPlex server")
    parser.add_argument("--test", action="store_true", help="Test connection")
    args = parser.parse_args()
    
    logging.basicConfig(level=logging.INFO)
    
    if args.install:
        install_personaplex()
    elif args.server:
        server = PersonaPlexServer()
        if server.start():
            print(f"PersonaPlex server running on port {server.port}")
            print("Press Ctrl+C to stop")
            try:
                while True:
                    import time
                    time.sleep(1)
            except KeyboardInterrupt:
                server.stop()
    elif args.test:
        async def test():
            if await init_personaplex():
                print("Connected to PersonaPlex!")
                await _voice_system.say("Hello, I am your AI assistant. Roger, roger.")
                await asyncio.sleep(5)
                await shutdown_personaplex()
            else:
                print("Failed to connect to PersonaPlex")
        
        asyncio.run(test())
