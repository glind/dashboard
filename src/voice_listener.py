#!/usr/bin/env python3
"""
Voice command listener for dashboard
Listens for wake words "rogr" or "roger" and processes commands

NOTE: Requires PyAudio and portaudio19-dev system package
Install with: sudo apt install portaudio19-dev && pip install SpeechRecognition PyAudio
"""

import logging
from typing import Optional, Callable
import threading
import queue
from dataclasses import dataclass

# Try to import speech recognition (optional dependency)
try:
    import speech_recognition as sr
    SPEECH_RECOGNITION_AVAILABLE = True
except ImportError:
    SPEECH_RECOGNITION_AVAILABLE = False
    sr = None

logger = logging.getLogger(__name__)

@dataclass
class VoiceCommand:
    """Parsed voice command"""
    wake_word: str
    command: str
    raw_text: str
    confidence: float


class VoiceListener:
    """
    Listen for wake words and process voice commands
    Uses Google Speech Recognition (free, no API key needed)
    
    NOTE: Requires SpeechRecognition and PyAudio packages
    """
    
    def __init__(
        self,
        wake_words: list[str] = None,
        command_handler: Optional[Callable[[VoiceCommand], None]] = None
    ):
        if not SPEECH_RECOGNITION_AVAILABLE:
            raise ImportError(
                "SpeechRecognition not available. Install with:\n"
                "  sudo apt install portaudio19-dev\n"
                "  pip install SpeechRecognition PyAudio"
            )
        
        self.wake_words = wake_words or ["rogr", "roger"]
        self.command_handler = command_handler
        self.recognizer = sr.Recognizer()
        self.microphone = None
        self.listening = False
        self.command_queue = queue.Queue()
        
        # Adjust for ambient noise on startup
        self._calibrate_microphone()
    
    def _calibrate_microphone(self) -> bool:
        """Calibrate microphone for ambient noise"""
        try:
            self.microphone = sr.Microphone()
            with self.microphone as source:
                logger.info("Calibrating microphone for ambient noise...")
                self.recognizer.adjust_for_ambient_noise(source, duration=1)
            logger.info("Microphone calibration complete")
            return True
        except Exception as e:
            logger.error(f"Microphone calibration failed: {e}")
            return False
    
    def _parse_command(self, text: str) -> Optional[VoiceCommand]:
        """
        Parse text for wake word + command
        Returns VoiceCommand if wake word found, else None
        """
        text_lower = text.lower()
        
        for wake_word in self.wake_words:
            if wake_word in text_lower:
                # Extract command after wake word
                parts = text_lower.split(wake_word, 1)
                command = parts[1].strip() if len(parts) > 1 else ""
                
                return VoiceCommand(
                    wake_word=wake_word,
                    command=command,
                    raw_text=text,
                    confidence=1.0  # Google SR doesn't provide confidence
                )
        
        return None
    
    def _listen_loop(self):
        """Background thread: continuous listening"""
        logger.info("Voice listener started. Say 'rogr' or 'roger' to activate.")
        
        while self.listening:
            try:
                with self.microphone as source:
                    # Listen for audio
                    audio = self.recognizer.listen(source, timeout=5, phrase_time_limit=10)
                
                # Recognize speech
                try:
                    text = self.recognizer.recognize_google(audio)
                    logger.debug(f"Heard: {text}")
                    
                    # Check for wake word
                    command = self._parse_command(text)
                    if command:
                        logger.info(f"Command detected: {command.command}")
                        self.command_queue.put(command)
                        
                        if self.command_handler:
                            self.command_handler(command)
                
                except sr.UnknownValueError:
                    # Speech not understood
                    pass
                except sr.RequestError as e:
                    logger.error(f"Speech recognition error: {e}")
            
            except sr.WaitTimeoutError:
                # No speech detected in timeout period
                pass
            except Exception as e:
                logger.error(f"Listener error: {e}")
                if self.listening:
                    logger.info("Restarting listener...")
    
    def start(self) -> bool:
        """Start listening for voice commands"""
        if self.listening:
            logger.warning("Listener already running")
            return False
        
        if not self.microphone:
            if not self._calibrate_microphone():
                return False
        
        self.listening = True
        self.listener_thread = threading.Thread(
            target=self._listen_loop,
            daemon=True
        )
        self.listener_thread.start()
        
        logger.info("Voice listener started")
        return True
    
    def stop(self):
        """Stop listening"""
        self.listening = False
        if hasattr(self, 'listener_thread'):
            self.listener_thread.join(timeout=2)
        logger.info("Voice listener stopped")
    
    def get_command(self, timeout: Optional[float] = None) -> Optional[VoiceCommand]:
        """
        Get next command from queue (blocking)
        Returns None if timeout expires
        """
        try:
            return self.command_queue.get(timeout=timeout)
        except queue.Empty:
            return None


# Example command processor
def process_dashboard_command(command: VoiceCommand):
    """
    Process voice commands for dashboard
    """
    from src.voice import announce
    
    cmd = command.command.lower()
    
    # Dashboard control commands
    if "status" in cmd or "report" in cmd:
        announce("Generating status report")
        # TODO: Trigger dashboard status report
    
    elif "update" in cmd or "refresh" in cmd:
        announce("Refreshing dashboard data")
        # TODO: Trigger data collection
    
    elif "tasks" in cmd:
        announce("Loading task summary")
        # TODO: Show task overview
    
    elif "calendar" in cmd:
        announce("Loading calendar events")
        # TODO: Show calendar
    
    elif "email" in cmd:
        announce("Loading email summary")
        # TODO: Show email stats
    
    elif "github" in cmd:
        announce("Loading GitHub activity")
        # TODO: Show GitHub stats
    
    elif "stop" in cmd or "quiet" in cmd or "silence" in cmd:
        announce("Voice system standby")
        # TODO: Pause voice announcements
    
    else:
        # Unknown command
        announce(f"Command not recognized: {cmd}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    if not SPEECH_RECOGNITION_AVAILABLE:
        print("❌ SpeechRecognition not installed")
        print("\nInstall with:")
        print("  sudo apt install portaudio19-dev")
        print("  pip install SpeechRecognition PyAudio")
        exit(1)
    
    print("🎤 Voice command listener test")
    print("Say 'rogr' or 'roger' followed by a command")
    print("Example: 'Roger, show status'")
    print("Press Ctrl+C to exit")
    print()
    
    listener = VoiceListener(command_handler=process_dashboard_command)
    
    if listener.start():
        try:
            # Keep running until interrupted
            while True:
                import time
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping listener...")
            listener.stop()
    else:
        print("❌ Failed to start listener. Check microphone permissions.")
