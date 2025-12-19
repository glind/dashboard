#!/usr/bin/env python3
"""
Voice system for the dashboard - "Rogr" battle-droid-style assistant
Uses Piper TTS + ffmpeg for robot voice effects
Answers to "rogr" or "roger" and says "roger, roger" after commands
"""

import subprocess
import threading
from pathlib import Path
from typing import Optional, Literal
import hashlib
import logging
import sys

logger = logging.getLogger(__name__)

# Voice styles available
VoiceStyle = Literal["clean", "droid", "radio", "pa_system"]

class VoiceSystem:
    """
    Battle-droid-style voice assistant for dashboard
    """
    
    def __init__(
        self,
        piper_bin: str = "piper",
        model_path: Optional[str] = None,
        cache_dir: str = "data/voice_cache",
        default_style: VoiceStyle = "droid"
    ):
        self.piper_bin = piper_bin
        self.model_path = model_path
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_style = default_style
        self.playback_lock = threading.Lock()
        
        # Wake words
        self.wake_words = ["rogr", "roger"]
        
        # Signature phrase
        self.signature = "roger, roger"
        
        logger.info(f"Voice system initialized with style: {default_style}")
    
    def _check_dependencies(self) -> bool:
        """Check if required binaries are available"""
        try:
            subprocess.run(
                [self.piper_bin, "--version"],
                capture_output=True,
                check=False
            )
            piper_ok = True
        except FileNotFoundError:
            piper_ok = False
            logger.warning(f"Piper not found at {self.piper_bin}")
        
        try:
            subprocess.run(
                ["ffmpeg", "-version"],
                capture_output=True,
                check=True
            )
            ffmpeg_ok = True
        except (FileNotFoundError, subprocess.CalledProcessError):
            ffmpeg_ok = False
            logger.warning("ffmpeg not found")
        
        return piper_ok and ffmpeg_ok
    
    def _get_cache_path(self, text: str, style: str) -> Path:
        """Generate cache filename from text + style"""
        h = hashlib.md5(f"{text}:{style}".encode()).hexdigest()[:16]
        return self.cache_dir / f"{style}_{h}.wav"
    
    def _synthesize_piper(self, text: str, out_wav: Path) -> bool:
        """
        Generate speech using Piper TTS
        Returns True if successful
        """
        if not self.model_path:
            logger.error("No Piper model path configured")
            return False
        
        try:
            # Piper command: reads text from stdin, outputs to file
            cmd = [
                self.piper_bin,
                "-m", self.model_path,
                "-f", str(out_wav),
            ]
            
            result = subprocess.run(
                cmd,
                input=text.encode("utf-8"),
                capture_output=True,
                check=True
            )
            
            logger.debug(f"Piper TTS generated: {out_wav}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"Piper TTS failed: {e.stderr.decode()}")
            return False
        except Exception as e:
            logger.error(f"Piper TTS error: {e}")
            return False
    
    def _apply_fx(self, in_wav: Path, out_wav: Path, style: VoiceStyle) -> bool:
        """
        Apply audio effects based on style
        Returns True if successful
        """
        fx_chains = {
            "clean": "",  # No effects
            
            "droid": (
                # Battle-droid style: aggressive processing for robotic sound
                # Step 1: Slow down speech by 25% for better clarity and comprehension
                "atempo=0.75,"
                # Step 2: Pitch shift down significantly for deeper, more mechanical voice
                "asetrate=44100*0.85,aresample=44100,"
                # Step 3: Narrow band-pass for radio/comms quality
                "highpass=f=250,lowpass=f=3000,"
                # Step 4: Heavy compression for that clipped, limited sound
                "acompressor=threshold=-18dB:ratio=5:attack=2:release=40,"
                # Step 5: Bit crushing for digital degradation
                "acrusher=bits=10:mix=0.35,"
                # Step 6: Tremolo for metallic vibrato
                "tremolo=f=100:d=0.12,"
                # Step 7: Short echo for radio transmission
                "aecho=0.7:0.4:18:0.25,"
                # Step 8: Final high-pass to remove mud
                "highpass=f=220,"
                # Step 9: Hard limiter to prevent clipping
                "alimiter=limit=0.85"
            ),
            
            "radio": (
                # Radio transmission style
                "highpass=f=300,"
                "lowpass=f=3000,"
                "acompressor=threshold=-14dB:ratio=3:attack=5:release=80,"
                "acrusher=bits=12:mix=0.2,"
                "aecho=0.7:0.5:15:0.15"
            ),
            
            "pa_system": (
                # PA/intercom style
                "highpass=f=250,"
                "lowpass=f=4000,"
                "acompressor=threshold=-12dB:ratio=2.5:attack=10:release=100,"
                "aecho=0.9:0.8:40:0.3"
            ),
        }
        
        fx = fx_chains.get(style, fx_chains["droid"])
        
        if not fx:
            # Clean style: just copy
            import shutil
            shutil.copy(in_wav, out_wav)
            return True
        
        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", str(in_wav),
                "-af", fx,
                str(out_wav),
            ]
            
            subprocess.run(
                cmd,
                capture_output=True,
                check=True
            )
            
            logger.debug(f"Applied {style} FX: {out_wav}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg FX failed: {e.stderr.decode()}")
            return False
        except Exception as e:
            logger.error(f"FX error: {e}")
            return False
    
    def _clean_text(self, text: str) -> str:
        """
        Clean text for speech synthesis
        - Remove emojis
        - Fix common formatting issues
        - Remove markdown symbols
        """
        import re
        
        # Remove emojis (Unicode ranges for emoji characters)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002500-\U00002BEF"  # chinese char
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001f926-\U0001f937"
            "\U00010000-\U0010ffff"
            "\u2640-\u2642"
            "\u2600-\u2B55"
            "\u200d"
            "\u23cf"
            "\u23e9"
            "\u231a"
            "\ufe0f"  # dingbats
            "\u3030"
            "]+", flags=re.UNICODE
        )
        text = emoji_pattern.sub('', text)
        
        # Remove markdown formatting
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)  # bold
        text = re.sub(r'\*(.+?)\*', r'\1', text)      # italic
        text = re.sub(r'`(.+?)`', r'\1', text)        # code
        text = re.sub(r'#{1,6}\s', '', text)          # headers
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text
    
    def generate(
        self,
        text: str,
        style: Optional[VoiceStyle] = None,
        force: bool = False
    ) -> Optional[Path]:
        """
        Generate voice audio for text
        Returns path to WAV file, or None if failed
        
        Args:
            text: Text to speak
            style: Voice style (defaults to self.default_style)
            force: Force regeneration even if cached
        """
        if style is None:
            style = self.default_style
        
        # Clean text before synthesis
        text = self._clean_text(text)
        
        if not text:  # Skip if text is empty after cleaning
            logger.warning("Text is empty after cleaning")
            return None
        
        cache_path = self._get_cache_path(text, style)
        
        # Check cache
        if cache_path.exists() and not force:
            logger.debug(f"Using cached voice: {cache_path}")
            return cache_path
        
        # Generate raw TTS
        raw_path = self.cache_dir / "temp_raw.wav"
        if not self._synthesize_piper(text, raw_path):
            return None
        
        # Apply FX
        if not self._apply_fx(raw_path, cache_path, style):
            return None
        
        # Cleanup temp
        raw_path.unlink(missing_ok=True)
        
        return cache_path
    
    def play(self, wav_path: Path, blocking: bool = False) -> bool:
        """
        Play audio file using ffplay (part of ffmpeg)
        
        Args:
            wav_path: Path to WAV file
            blocking: If True, wait for playback to finish
        """
        def _play():
            try:
                # ffplay with minimal output, auto-exit
                cmd = [
                    "ffplay",
                    "-nodisp",  # No video window
                    "-autoexit",  # Exit when done
                    "-loglevel", "quiet",  # Suppress logs
                    str(wav_path)
                ]
                subprocess.run(cmd, check=True)
            except Exception as e:
                logger.error(f"Playback error: {e}")
        
        if blocking:
            _play()
        else:
            thread = threading.Thread(target=_play, daemon=True)
            thread.start()
        
        return True
    
    def say(
        self,
        text: str,
        style: Optional[VoiceStyle] = None,
        add_signature: bool = False,
        blocking: bool = False
    ) -> bool:
        """
        Generate and play speech
        
        Args:
            text: Text to speak
            style: Voice style
            add_signature: If True, append "roger, roger"
            blocking: Wait for playback to finish
        
        Returns:
            True if successful
        """
        if add_signature:
            text = f"{text}. {self.signature}"
        
        wav_path = self.generate(text, style)
        if not wav_path:
            logger.error("Voice generation failed")
            return False
        
        return self.play(wav_path, blocking=blocking)
    
    def announce(self, text: str, **kwargs) -> bool:
        """
        Convenience method: say with signature
        """
        return self.say(text, add_signature=True, **kwargs)
    
    def preload_common_phrases(self, phrases: list[str]) -> None:
        """
        Pre-generate and cache common phrases for faster playback
        """
        logger.info(f"Preloading {len(phrases)} common phrases...")
        for phrase in phrases:
            self.generate(phrase)
            if phrase != f"{phrase}. {self.signature}":
                self.generate(f"{phrase}. {self.signature}")
        logger.info("Preload complete")


# Singleton instance
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


# Example usage
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    voice = VoiceSystem()
    
    # Check dependencies
    if not voice._check_dependencies():
        print("⚠️  Missing dependencies!")
        print("Install with: sudo apt install ffmpeg")
        print("Download Piper: https://github.com/rhasspy/piper/releases")
        print("Download voice model: https://huggingface.co/rhasspy/piper-voices")
        sys.exit(1)
    
    # Demo phrases
    phrases = [
        "Dashboard online",
        "Three tasks are overdue",
        "Daily summary ready",
        "No urgent items detected",
    ]
    
    print("Preloading common phrases...")
    voice.preload_common_phrases(phrases)
    
    print("\n🤖 Rogr voice system ready")
    print("Testing announcement...")
    voice.announce("Dashboard initialization complete", blocking=True)
