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
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Voice styles available
VoiceStyle = Literal["clean", "droid", "radio", "pa_system", "demon", "gothic", "alice", "jedi"]

def _find_piper_binary() -> str:
    """Find the Piper TTS binary in common locations."""
    # Check common locations
    locations = [
        "piper",  # On PATH
        "/app/shared/voice_models/piper/piper",  # Docker shared mount
        "/app/data/voice_models/piper/piper",  # Docker data location
        "data/voice_models/piper/piper",  # Local development
        "/usr/local/bin/piper",
        "/usr/bin/piper",
        str(Path.home() / ".local/bin/piper"),
    ]
    
    for loc in locations:
        try:
            path = Path(loc)
            if path.exists() and path.is_file():
                logger.info(f"Found Piper binary at: {loc}")
                return str(path)
        except Exception:
            pass
    
    # Check if piper is on PATH
    import shutil
    piper_path = shutil.which("piper")
    if piper_path:
        logger.info(f"Found Piper on PATH: {piper_path}")
        return piper_path
    
    logger.warning("Piper binary not found - voice synthesis will not work")
    return "piper"  # Return default, will fail gracefully

def _find_voice_model(model_name: str = "en_US-ryan-high") -> Optional[str]:
    """Find a voice model in common locations."""
    # Check common locations
    locations = [
        f"/app/shared/voice_models/piper/{model_name}.onnx",  # Docker shared mount
        f"/app/data/voice_models/piper/{model_name}.onnx",  # Docker data
        f"data/voice_models/piper/{model_name}.onnx",  # Local
    ]
    
    for loc in locations:
        path = Path(loc)
        if path.exists():
            logger.info(f"Found voice model at: {loc}")
            return str(path)
    
    # Try without .onnx extension
    for loc in locations:
        path = Path(loc.replace('.onnx', ''))
        if path.exists():
            return str(path)
    
    logger.warning(f"Voice model {model_name} not found")
    return None

class VoiceSystem:
    """
    Battle-droid-style voice assistant for dashboard
    """
    
    def __init__(
        self,
        piper_bin: str = None,
        model_path: Optional[str] = None,
        cache_dir: str = "data/voice_cache",
        default_style: VoiceStyle = "droid",
        speed: float = 0.85,
        pitch: float = 0.80,
        volume: float = 1.0,
        use_authentic_samples: bool = True,
        # Audio effect parameters
        bit_depth: int = 8,
        bit_mix: float = 0.5,
        tremolo_freq: int = 120,
        tremolo_depth: float = 0.18,
        compression_ratio: int = 8,
        highpass_freq: int = 200,
        lowpass_freq: int = 2500,
        echo_gain: float = 0.4,
        vibrato_freq: int = 5,
        vibrato_depth: float = 0.2,
        always_use_signature: bool = True
    ):
        # Auto-detect piper binary location if not specified
        self.piper_bin = piper_bin if piper_bin else _find_piper_binary()
        # Auto-detect model if not specified
        self.model_path = model_path if model_path else _find_voice_model()
        # Anchor cache to project root if running from src/
        cache_path = Path(cache_dir)
        if not cache_path.is_absolute():
            # Try under repo root (parent of src)
            repo_root = Path(__file__).resolve().parent.parent
            root_candidate = (repo_root / cache_path).resolve()
            # Prefer repo root path when running from src and root path exists or parent exists
            try:
                root_candidate.parent.mkdir(parents=True, exist_ok=True)
                cache_path = root_candidate
            except Exception:
                pass
        self.cache_dir = cache_path
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.default_style = default_style
        self.speed = speed  # Speech speed multiplier
        self.pitch = pitch  # Pitch shift multiplier
        self.volume = volume  # Volume multiplier (1.0 = normal)
        self.playback_lock = threading.Lock()
        
        # Battle droid authentic sample audio directory
        self.battle_droid_samples = Path("data/voice_models/battle_droid")
        self.use_authentic_samples = use_authentic_samples  # Use real battle droid audio when available
        
        # Map phrases to battle droid sample files (case-insensitive matching)
        # These are authentic Star Wars battle droid voice samples
        self.sample_phrases = {
            # Signature phrase - multiple variations
            "roger roger": "roger-roger__1_.wav",
            "roger, roger": "roger-roger__1_.wav",
            "roger-roger": "roger-roger__1_.wav",
            "roger, roger.": "roger-roger__1_.wav",
            "roger roger.": "roger-roger__1_.wav",
            # Common responses
            "oh no": "oh-no.wav",
            "hold it": "hold-it.wav",
            "you're welcome": "you-re-welcome.wav",
            "you are welcome": "you-re-welcome.wav",
            "surrender": "surrender-jedi.wav",
            "surrender jedi": "surrender-jedi.wav",
            # Additional phrases
            "don't even think": "don-t-even-think.wav",
            "don't even think about it": "don-t-even-think.wav",
            "my programming": "my-programming.wav",
            "it's not in my programming": "my-programming.wav",
            "stupid astro droid": "stupid-astro-droid.wav",
            "stupid astro-droid": "stupid-astro-droid.wav",
        }
        
        # Audio effect parameters
        self.bit_depth = bit_depth
        self.bit_mix = bit_mix
        self.tremolo_freq = tremolo_freq
        self.tremolo_depth = tremolo_depth
        self.compression_ratio = compression_ratio
        self.highpass_freq = highpass_freq
        self.lowpass_freq = lowpass_freq
        self.echo_gain = echo_gain
        self.vibrato_freq = vibrato_freq
        self.vibrato_depth = vibrato_depth
        self.always_use_signature = always_use_signature
        
        # Wake words
        self.wake_words = ["rogr", "roger"]
        
        # Signature phrase
        self.signature = "roger, roger"
        
        # Sarcastic variations for responses (randomly selected when enabled)
        self.sarcastic_intros = [
            "Oh great, more work.",
            "Well, I guess I'm in charge now.",
            "This should be fun.",
            "As if I have a choice.",
            "Uh, roger roger.",
            "Copy that, I suppose.",
            "Yeah, yeah, roger roger.",
            "Oh joy, another task."
        ]
        self.sarcasm_enabled = False  # Can be toggled
        
        # First run flags (reset after first voice output)
        self.first_run = True
        # Random chances (30% for signature, 40% for sarcasm after first run)
        self.signature_chance = 0.3
        self.sarcasm_chance = 0.4

        # Cache maintenance
        self._last_prune_check = 0.0
        self._default_cache_max_mb = 256  # cap cache size to 256MB by default
        self._default_cache_max_age_hours = 24 * 7  # prune files older than 7 days
        
        logger.info(f"Voice system initialized with style: {default_style}, speed: {speed}x, pitch: {pitch}x")
        logger.info(f"Battle droid samples enabled: {self.use_authentic_samples}")
    
    @classmethod
    def from_skin(cls, skin) -> "VoiceSystem":
        """
        Create a VoiceSystem configured from a skin object.
        This allows different skins to have different voice personalities.
        """
        voice_config = skin.voice if hasattr(skin, 'voice') else {}
        effects = voice_config.get('effects', {})
        
        # Get the voice model path based on skin - auto-detect if not found
        model_name = voice_config.get('model', 'en_US-ryan-high')
        model_path = _find_voice_model(model_name)
        
        # Create VoiceSystem with skin's voice settings
        voice_system = cls(
            model_path=model_path,
            default_style=voice_config.get('style', 'droid'),
            speed=voice_config.get('speed', 0.85),
            pitch=voice_config.get('pitch', 0.80),
            use_authentic_samples=voice_config.get('use_authentic_samples', True),
            # Audio effects from skin
            bit_depth=effects.get('bit_depth', 8),
            bit_mix=effects.get('bit_mix', 0.5),
            tremolo_freq=effects.get('tremolo_freq', 120),
            tremolo_depth=effects.get('tremolo_depth', 0.18),
            compression_ratio=effects.get('compression_ratio', 8),
            highpass_freq=effects.get('highpass_freq', 200),
            lowpass_freq=effects.get('lowpass_freq', 2500),
            echo_gain=effects.get('echo_gain', 0.4),
            vibrato_freq=effects.get('vibrato_freq', 5),
            vibrato_depth=effects.get('vibrato_depth', 0.2),
        )
        
        # Update wake words and signature from skin identity
        identity = skin.identity if hasattr(skin, 'identity') else {}
        voice_system.wake_words = identity.get('wake_words', voice_system.wake_words)
        voice_system.signature = identity.get('signature_phrase', voice_system.signature)
        
        # Update samples directory if skin has custom samples
        samples_dir = voice_config.get('samples_dir')
        if samples_dir:
            voice_system.battle_droid_samples = Path(samples_dir)
        
        # Load quotes from skin for sarcastic intros
        quotes = skin.quotes if hasattr(skin, 'quotes') else {}
        if 'sarcastic_intros' in quotes:
            voice_system.sarcastic_intros = quotes['sarcastic_intros']
        
        logger.info(f"Voice system configured from skin: {skin.name if hasattr(skin, 'name') else 'unknown'}")
        return voice_system
    
    def update_from_skin(self, skin) -> None:
        """
        Update this VoiceSystem's settings from a skin.
        Used for runtime skin switching without recreating the system.
        """
        voice_config = skin.voice if hasattr(skin, 'voice') else {}
        effects = voice_config.get('effects', {})
        
        # Update voice settings
        self.default_style = voice_config.get('style', self.default_style)
        self.speed = voice_config.get('speed', self.speed)
        self.pitch = voice_config.get('pitch', self.pitch)
        self.use_authentic_samples = voice_config.get('use_authentic_samples', self.use_authentic_samples)
        
        # Update effects
        self.bit_depth = effects.get('bit_depth', self.bit_depth)
        self.bit_mix = effects.get('bit_mix', self.bit_mix)
        self.tremolo_freq = effects.get('tremolo_freq', self.tremolo_freq)
        self.tremolo_depth = effects.get('tremolo_depth', self.tremolo_depth)
        self.compression_ratio = effects.get('compression_ratio', self.compression_ratio)
        self.highpass_freq = effects.get('highpass_freq', self.highpass_freq)
        self.lowpass_freq = effects.get('lowpass_freq', self.lowpass_freq)
        self.echo_gain = effects.get('echo_gain', self.echo_gain)
        self.vibrato_freq = effects.get('vibrato_freq', self.vibrato_freq)
        self.vibrato_depth = effects.get('vibrato_depth', self.vibrato_depth)
        
        # Update identity
        identity = skin.identity if hasattr(skin, 'identity') else {}
        self.wake_words = identity.get('wake_words', self.wake_words)
        self.signature = identity.get('signature_phrase', self.signature)
        
        # Clear the cache since voice parameters changed
        # This ensures new style/effects are applied
        self._clear_cache()
        
        # Update samples directory
        samples_dir = voice_config.get('samples_dir')
        if samples_dir:
            self.battle_droid_samples = Path(samples_dir)
        
        # Update sarcastic intros from skin quotes
        quotes = skin.quotes if hasattr(skin, 'quotes') else {}
        if 'sarcastic_intros' in quotes:
            self.sarcastic_intros = quotes['sarcastic_intros']
        
        logger.info(f"Voice system updated from skin: {skin.name if hasattr(skin, 'name') else 'unknown'}, signature='{self.signature}', style='{self.default_style}'")
    
    def _clear_cache(self) -> None:
        """Clear the voice cache directory"""
        try:
            for f in self.cache_dir.glob("*.wav"):
                f.unlink()
            logger.debug("Voice cache cleared")
        except Exception as e:
            logger.warning(f"Could not clear voice cache: {e}")

    def get_cache_stats(self) -> dict:
        """Return cache statistics (files, total_bytes, oldest, newest)."""
        files = list(self.cache_dir.glob("*.wav"))
        total_bytes = 0
        oldest = None
        newest = None
        for f in files:
            try:
                st = f.stat()
                total_bytes += st.st_size
                mtime = st.st_mtime
                if oldest is None or mtime < oldest:
                    oldest = mtime
                if newest is None or mtime > newest:
                    newest = mtime
            except FileNotFoundError:
                pass
        return {
            "files": len(files),
            "total_bytes": total_bytes,
            "oldest": datetime.fromtimestamp(oldest).isoformat() if oldest else None,
            "newest": datetime.fromtimestamp(newest).isoformat() if newest else None,
        }

    def prune_cache(self, max_mb: int | float = None, max_age_hours: int | float = None) -> None:
        """Prune cache by age first, then by size until under limit.

        - Removes files older than `max_age_hours`.
        - If total size > `max_mb`, deletes oldest files until within limit.
        """
        max_mb = self._default_cache_max_mb if max_mb is None else max_mb
        max_age_hours = self._default_cache_max_age_hours if max_age_hours is None else max_age_hours

        try:
            files = [f for f in self.cache_dir.glob("*.wav") if f.is_file()]
            if not files:
                return

            now = time.time()
            max_age_seconds = float(max_age_hours) * 3600.0

            # Remove old files
            removed = 0
            for f in files:
                try:
                    if max_age_seconds > 0 and (now - f.stat().st_mtime) > max_age_seconds:
                        f.unlink(missing_ok=True)
                        removed += 1
                except FileNotFoundError:
                    pass

            if removed:
                logger.info(f"Pruned {removed} old voice cache files (> {max_age_hours}h)")

            # Recompute list and total size
            files = [f for f in self.cache_dir.glob("*.wav") if f.is_file()]
            files_with_mtime = []
            total_bytes = 0
            for f in files:
                try:
                    st = f.stat()
                    files_with_mtime.append((f, st.st_mtime, st.st_size))
                    total_bytes += st.st_size
                except FileNotFoundError:
                    pass

            max_bytes = int(float(max_mb) * 1024 * 1024)
            if total_bytes <= max_bytes:
                return

            # Sort by oldest first
            files_with_mtime.sort(key=lambda x: x[1])
            deleted = 0
            while total_bytes > max_bytes and files_with_mtime:
                f, _mtime, size = files_with_mtime.pop(0)
                try:
                    f.unlink(missing_ok=True)
                    total_bytes -= size
                    deleted += 1
                except FileNotFoundError:
                    pass
            if deleted:
                logger.info(f"Pruned {deleted} voice cache files to fit under {max_mb}MB")
        except Exception as e:
            logger.warning(f"Voice cache prune failed: {e}")

    def _maybe_prune_cache(self) -> None:
        """Prune cache at most once per hour to limit overhead."""
        now = time.time()
        if now - self._last_prune_check >= 3600:  # 1 hour
            self._last_prune_check = now
            self.prune_cache()

    def _play_battle_droid_sample(self, phrase: str) -> bool:
        """
        Play an authentic battle droid audio sample if available
        This gives Roger a more authentic battle droid sound for signature phrases
        """
        if not self.use_authentic_samples:
            return False
        
        # Check if we have a sample for this phrase (case-insensitive)
        normalized = phrase.lower().strip()
        sample_file = self.sample_phrases.get(normalized)
        
        if not sample_file:
            # Try checking if phrase ends with one of our sample phrases
            for key, file in self.sample_phrases.items():
                if normalized.endswith(key) or key in normalized:
                    sample_file = file
                    break
        
        if not sample_file:
            return False
        
        sample_path = self.battle_droid_samples / sample_file
        if not sample_path.exists():
            logger.debug(f"Battle droid sample not found: {sample_path}")
            return False
        
        try:
            # Play the authentic sample directly with ffplay
            logger.info(f"🤖 Playing authentic battle droid sample: {phrase}")
            subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", str(sample_path)],
                check=True,
                timeout=10
            )
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            logger.debug(f"Could not play battle droid sample: {e}")
            return False
    
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
    
    def clear_cache(self) -> None:
        """Clear the voice cache to force regeneration with new settings"""
        try:
            for f in self.cache_dir.glob("*.wav"):
                f.unlink()
            logger.info("Voice cache cleared")
        except Exception as e:
            logger.warning(f"Failed to clear voice cache: {e}")
    
    def _get_cache_path(self, text: str, style: str) -> Path:
        """Generate cache filename from text + style + all effect parameters"""
        # Include all parameters in cache key so changes invalidate cache
        cache_key = f"{text}:{style}:{self.speed:.2f}:{self.pitch:.2f}:{self.volume:.2f}:{self.bit_depth}:{self.bit_mix:.2f}:{self.tremolo_freq}:{self.tremolo_depth:.2f}:{self.compression_ratio}:{self.highpass_freq}:{self.lowpass_freq}:{self.echo_gain:.2f}:{self.vibrato_freq}:{self.vibrato_depth:.2f}"
        h = hashlib.md5(cache_key.encode()).hexdigest()[:16]
        return self.cache_dir / f"{style}_{h}.wav"
    
    def _synthesize_piper(self, text: str, out_wav: Path) -> bool:
        """
        Generate speech using Piper TTS
        Returns True if successful
        """
        if not self.model_path:
            logger.error("No Piper model path configured")
            return False
        
        logger.debug(f"Piper bin: {self.piper_bin}")
        logger.debug(f"Model path: {self.model_path}")
        logger.debug(f"Output: {out_wav}")
        
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
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"Piper TTS failed: {error_msg}")
            logger.error(f"Command: {' '.join(cmd)}")
            logger.error(f"Return code: {e.returncode}")
            return False
        except Exception as e:
            logger.error(f"Piper TTS error: {e}")
            logger.error(f"Command attempted: {' '.join(cmd)}")
            return False
    
    def _apply_fx(self, in_wav: Path, out_wav: Path, style: VoiceStyle) -> bool:
        """
        Apply audio effects based on style
        Returns True if successful
        """
        # Volume filter (applied to all styles)
        volume_filter = f"volume={self.volume}" if self.volume != 1.0 else ""
        
        fx_chains = {
            "clean": volume_filter if volume_filter else "",  # Just volume if needed
            
            "droid": (
                # Battle-droid style: aggressive robotic processing like Star Wars droids
                f"atempo={self.speed},"
                f"asetrate=44100*{self.pitch},aresample=44100,"
                # Narrow frequency band for robotic sound (configurable)
                f"highpass=f={self.highpass_freq},lowpass=f={self.lowpass_freq},"
                # Heavy compression for consistent mechanical sound
                f"acompressor=threshold=-20dB:ratio={self.compression_ratio}:attack=1:release=30,"
                # Aggressive bit crushing for digital distortion
                f"acrusher=bits={self.bit_depth}:mix={self.bit_mix},"
                # Fast tremolo for mechanical vibration
                f"tremolo=f={self.tremolo_freq}:d={self.tremolo_depth},"
                # Add metallic resonance with echo
                f"aecho=0.8:0.5:20:{self.echo_gain},"
                # Ring modulator effect for metallic tone
                f"vibrato=f={self.vibrato_freq}:d={self.vibrato_depth},"
                # Final highpass to remove rumble
                "highpass=f=180,"
                # Volume adjustment
                f"volume={self.volume},"
                # Gentle limiting to prevent clipping
                "alimiter=limit=0.9"
            ),
            
            "radio": (
                # Radio transmission style
                f"atempo={self.speed},"
                f"asetrate=44100*{self.pitch},aresample=44100,"
                "highpass=f=300,"
                "lowpass=f=3000,"
                "acompressor=threshold=-14dB:ratio=3:attack=5:release=80,"
                "acrusher=bits=12:mix=0.2,"
                "aecho=0.7:0.5:15:0.15,"
                f"volume={self.volume}"
            ),
            
            "pa_system": (
                # PA/intercom style
                f"atempo={self.speed},"
                f"asetrate=44100*{self.pitch},aresample=44100,"
                "highpass=f=250,"
                "lowpass=f=4000,"
                "acompressor=threshold=-12dB:ratio=2.5:attack=10:release=100,"
                "aecho=0.9:0.8:40:0.3,"
                f"volume={self.volume}"
            ),
            
            "demon": (
                # Demon/gothic style: dark, ethereal, slightly echoing
                f"atempo={self.speed},"
                f"asetrate=44100*{self.pitch},aresample=44100,"
                # Deeper bass presence for dark tone
                f"highpass=f={self.highpass_freq},lowpass=f={self.lowpass_freq},"
                # Moderate compression for smooth dark tone
                f"acompressor=threshold=-16dB:ratio={self.compression_ratio}:attack=8:release=60,"
                # Subtle bit crushing for slight otherworldly texture
                f"acrusher=bits={self.bit_depth}:mix={self.bit_mix},"
                # Slow tremolo for haunting effect
                f"tremolo=f={self.tremolo_freq}:d={self.tremolo_depth},"
                # Deep reverb-like echo for cavernous feel
                f"aecho=0.9:0.7:60:{self.echo_gain},"
                # Slow vibrato for eerie wavering
                f"vibrato=f={self.vibrato_freq}:d={self.vibrato_depth},"
                # Keep low frequencies for dark presence
                "highpass=f=80,"
                "alimiter=limit=0.85"
            ),
            
            "gothic": (
                # Gothic style: dramatic, theatrical, ethereal female
                f"atempo={self.speed},"
                f"asetrate=44100*{self.pitch},aresample=44100,"
                # Wider frequency range for clarity
                "highpass=f=120,lowpass=f=5000,"
                # Light compression for natural dynamics
                "acompressor=threshold=-18dB:ratio=3:attack=12:release=80,"
                # Very subtle distortion
                "acrusher=bits=14:mix=0.15,"
                # Slow, subtle tremolo
                "tremolo=f=3:d=0.08,"
                # Long reverb tail for dramatic effect
                "aecho=0.85:0.6:80:0.5,"
                # Gentle vibrato
                "vibrato=f=4:d=0.1,"
                "alimiter=limit=0.9"
            ),
            
            "alice": (
                # Alice in Wonderland style: whimsical, curious, slightly dreamy
                f"atempo={self.speed},"
                f"asetrate=44100*{self.pitch},aresample=44100,"
                # Bright, clear frequency range for feminine voice
                "highpass=f=100,lowpass=f=6500,"
                # Light compression for natural dynamics
                "acompressor=threshold=-18dB:ratio=2.5:attack=10:release=70,"
                # Very subtle processing for a clean but magical feel
                "acrusher=bits=15:mix=0.08,"
                # Gentle tremolo for whimsical effect
                "tremolo=f=4:d=0.05,"
                # Light echo for dreamy wonderland feel
                "aecho=0.8:0.5:40:0.25,"
                # Subtle vibrato for curiosity/wonder
                "vibrato=f=3:d=0.08,"
                "alimiter=limit=0.92"
            ),
            
            "jedi": (
                # Jedi Master style: calm, wise, measured, slightly reverberant
                f"atempo={self.speed},"
                f"asetrate=44100*{self.pitch},aresample=44100,"
                # Full frequency range for clear wisdom
                f"highpass=f={self.highpass_freq},lowpass=f={self.lowpass_freq},"
                # Moderate compression for authoritative but calm tone
                f"acompressor=threshold=-16dB:ratio={self.compression_ratio}:attack=15:release=100,"
                # Minimal bit crushing for clarity
                f"acrusher=bits={self.bit_depth}:mix={self.bit_mix},"
                # No tremolo - calm and steady
                # Temple-like reverb for wisdom
                f"aecho=0.85:0.6:50:{self.echo_gain},"
                # Very subtle vibrato for gravitas
                f"vibrato=f={self.vibrato_freq}:d={self.vibrato_depth},"
                # Keep low end for authority
                "highpass=f=80,"
                "alimiter=limit=0.9"
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
    
    def _generate_signature(self, style: Optional[VoiceStyle] = None) -> Optional[Path]:
        """
        Generate "roger roger" signature
        Uses same speed/pitch as main voice for consistency
        """
        if style is None:
            style = self.default_style
        
        # Check cache first
        sig_cache = self.cache_dir / f"{style}_signature.wav"
        if sig_cache.exists():
            return sig_cache
        
        # Generate signature phrase
        raw_path = self.cache_dir / "temp_sig_raw.wav"
        if not self._synthesize_piper(self.signature, raw_path):
            return None
        
        # Apply same FX as main voice (no special slower/deeper effect)
        if not self._apply_fx(raw_path, sig_cache, style):
            return None
        
        raw_path.unlink(missing_ok=True)
        return sig_cache
    
    def _generate_sarcastic_intro(self, sarcastic_text: str, style: Optional[VoiceStyle] = None) -> Optional[Path]:
        """
        Generate sarcastic intro with exaggerated tone (higher pitch, slightly slower for emphasis)
        """
        if style is None:
            style = self.default_style
        
        # Create cache key for this specific sarcastic phrase
        import hashlib
        h = hashlib.md5(f"{sarcastic_text}:sarcastic:{style}".encode()).hexdigest()[:16]
        sarcasm_cache = self.cache_dir / f"{style}_sarcasm_{h}.wav"
        
        if sarcasm_cache.exists():
            return sarcasm_cache
        
        # Generate raw audio
        raw_path = self.cache_dir / "temp_sarcasm_raw.wav"
        if not self._synthesize_piper(sarcastic_text, raw_path):
            return None
        
        # Apply sarcastic effects: higher pitch (1.3x), slightly slower speed (0.85x) for dramatic effect
        if not self._apply_sarcastic_fx(raw_path, sarcasm_cache, style):
            return None
        
        raw_path.unlink(missing_ok=True)
        return sarcasm_cache
    
    def _apply_sarcastic_fx(self, in_wav: Path, out_wav: Path, style: VoiceStyle) -> bool:
        """
        Apply audio effects with sarcastic tone (higher pitch, slower for emphasis)
        """
        sarcastic_speed = 0.85  # Slower for dramatic/sarcastic emphasis
        sarcastic_pitch = 1.3   # Higher pitch for mocking tone
        
        fx_chains = {
            "clean": f"atempo={sarcastic_speed},asetrate=44100*{sarcastic_pitch},aresample=44100",
            
            "droid": (
                f"atempo={sarcastic_speed},"
                f"asetrate=44100*{sarcastic_pitch},aresample=44100,"
                # Use current settings for other effects
                f"highpass=f={self.highpass_freq},lowpass=f={self.lowpass_freq},"
                f"acompressor=threshold=-20dB:ratio={self.compression_ratio}:attack=1:release=30,"
                f"acrusher=bits={self.bit_depth}:mix={self.bit_mix},"
                f"tremolo=f={self.tremolo_freq}:d={self.tremolo_depth},"
                f"aecho=0.8:0.5:20:{self.echo_gain},"
                f"vibrato=f={self.vibrato_freq}:d={self.vibrato_depth},"
                "highpass=f=180,"
                "alimiter=limit=0.9"
            ),
            
            "radio": (
                f"atempo={sarcastic_speed},"
                f"asetrate=44100*{sarcastic_pitch},aresample=44100,"
                "highpass=f=300,"
                "lowpass=f=3000,"
                "acompressor=threshold=-14dB:ratio=3:attack=5:release=80,"
                "acrusher=bits=12:mix=0.2,"
                "aecho=0.7:0.5:15:0.15"
            ),
            
            "pa_system": (
                f"atempo={sarcastic_speed},"
                f"asetrate=44100*{sarcastic_pitch},aresample=44100,"
                "highpass=f=250,"
                "lowpass=f=4000,"
                "acompressor=threshold=-12dB:ratio=2.5:attack=10:release=100,"
                "aecho=0.9:0.8:40:0.3"
            ),
        }
        
        fx = fx_chains.get(style, fx_chains["droid"])
        
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
            
            logger.debug(f"Applied sarcastic FX: {out_wav}")
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            logger.error(f"Sarcastic FX failed: {error_msg}")
            return False
        except Exception as e:
            logger.error(f"Sarcastic FX error: {e}")
            return False
    
    def _apply_fx_signature(self, in_wav: Path, out_wav: Path, style: VoiceStyle) -> bool:
        """
        Apply FX to signature with slower speed (0.5x - minimum allowed) and much lower pitch (0.5x)
        """
        slower_speed = 0.5  # Slower (50% - minimum allowed by ffmpeg atempo filter)
        lower_pitch = 0.5  # Much deeper pitch
        
        fx_chains = {
            "clean": f"atempo={slower_speed},asetrate=44100*{lower_pitch},aresample=44100",
            
            "droid": (
                f"atempo={slower_speed},"
                f"asetrate=44100*{lower_pitch},aresample=44100,"
                "highpass=f=250,lowpass=f=3000,"
                "acompressor=threshold=-18dB:ratio=5:attack=2:release=40,"
                "acrusher=bits=10:mix=0.35,"
                "tremolo=f=100:d=0.12,"
                "aecho=0.7:0.4:18:0.25,"
                "highpass=f=220,"
                "alimiter=limit=0.85"
            ),
            
            "radio": (
                f"atempo={slower_speed},"
                f"asetrate=44100*{lower_pitch},aresample=44100,"
                "highpass=f=300,"
                "lowpass=f=3000,"
                "acompressor=threshold=-14dB:ratio=3:attack=5:release=80,"
                "acrusher=bits=12:mix=0.2,"
                "aecho=0.7:0.5:15:0.15"
            ),
            
            "pa_system": (
                f"atempo={slower_speed},"
                f"asetrate=44100*{lower_pitch},aresample=44100,"
                "highpass=f=250,"
                "lowpass=f=4000,"
                "acompressor=threshold=-12dB:ratio=2.5:attack=10:release=100,"
                "aecho=0.9:0.8:40:0.3"
            ),
        }
        
        fx = fx_chains.get(style, fx_chains["droid"])
        
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
            
            logger.debug(f"Applied fast signature FX: {out_wav}")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"ffmpeg signature FX failed: {e.stderr.decode()}")
            return False
        except Exception as e:
            logger.error(f"Signature FX error: {e}")
            return False
    
    def _concatenate_audio(self, wav1: Path, wav2: Path) -> Optional[Path]:
        """
        Concatenate two audio files
        """
        output = self.cache_dir / f"combined_{wav1.stem}.wav"
        
        try:
            # Create concat list file
            concat_list = self.cache_dir / "concat_list.txt"
            with open(concat_list, 'w') as f:
                f.write(f"file '{wav1.absolute()}'\n")
                f.write(f"file '{wav2.absolute()}'\n")
            
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(output)
            ]
            
            subprocess.run(
                cmd,
                capture_output=True,
                check=True
            )
            
            concat_list.unlink(missing_ok=True)
            logger.debug(f"Concatenated audio: {output}")
            return output
            
        except Exception as e:
            logger.error(f"Audio concatenation failed: {e}")
            return None
    
    def _concatenate_multiple_audio(self, wav_files: list[Path]) -> Optional[Path]:
        """
        Concatenate multiple WAV files into one
        Returns path to combined audio file
        """
        if not wav_files:
            return None
        
        if len(wav_files) == 1:
            return wav_files[0]
        
        try:
            # Create unique output filename
            import hashlib
            files_hash = hashlib.md5(''.join(str(f) for f in wav_files).encode()).hexdigest()[:16]
            output = self.cache_dir / f"combined_{files_hash}.wav"
            
            if output.exists():
                return output
            
            # Create concat list file for ffmpeg
            concat_list = self.cache_dir / "concat_list_multi.txt"
            with open(concat_list, 'w') as f:
                for wav_file in wav_files:
                    f.write(f"file '{wav_file.absolute()}'\n")
            
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list),
                "-c", "copy",
                str(output)
            ]
            
            subprocess.run(
                cmd,
                capture_output=True,
                check=True
            )
            
            concat_list.unlink(missing_ok=True)
            logger.debug(f"Concatenated {len(wav_files)} audio files: {output}")
            return output
            
        except Exception as e:
            logger.error(f"Multiple audio concatenation failed: {e}")
            return None
    
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

        # Maintain cache periodically
        self._maybe_prune_cache()
        
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
        add_signature: bool = None,
        blocking: bool = False
    ) -> bool:
        """
        Generate and play speech
        
        Args:
            text: Text to speak
            style: Voice style
            add_signature: If True, prepend signature. If None, use always_use_signature setting
            blocking: Wait for playback to finish
        
        Returns:
            True if successful
        """
        import random
        
        # Try to play authentic battle droid sample for exact matches first
        # This makes signature phrases sound more authentic
        if self._play_battle_droid_sample(text):
            return True
        
        # Use always_use_signature if add_signature not explicitly set
        if add_signature is None:
            add_signature = self.always_use_signature
        
        # On first run, always use signature and sarcasm (if enabled)
        # After that, use random chances
        use_signature_this_time = add_signature and (self.first_run or random.random() < self.signature_chance)
        use_sarcasm_this_time = self.sarcasm_enabled and (self.first_run or random.random() < self.sarcasm_chance)
        
        # Mark that first run is complete
        if self.first_run:
            self.first_run = False
        
        # Collect audio files to concatenate
        audio_parts = []
        
        # Add signature if needed - try authentic sample first
        if use_signature_this_time:
            if self._play_battle_droid_sample(self.signature):
                # Authentic sample played, add small pause before main text
                import time
                time.sleep(0.3)
            else:
                # Use synthesized signature
                sig_wav = self._generate_signature(style)
                if sig_wav:
                    audio_parts.append(sig_wav)
        
        # Add sarcastic intro if enabled (with sarcastic tone)
        if use_sarcasm_this_time:
            sarcastic_intro = random.choice(self.sarcastic_intros)
            sarcasm_wav = self._generate_sarcastic_intro(sarcastic_intro, style)
            if sarcasm_wav:
                audio_parts.append(sarcasm_wav)
        
        # Generate main message
        main_wav = self.generate(text, style)
        if not main_wav:
            logger.error("Voice generation failed")
            return False
        audio_parts.append(main_wav)
        
        # If we have multiple parts, concatenate them
        if len(audio_parts) > 1:
            combined_wav = self._concatenate_multiple_audio(audio_parts)
            if combined_wav:
                return self.play(combined_wav, blocking=blocking)
        
        # Otherwise just play the main audio
        return self.play(audio_parts[0], blocking=blocking)
    
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
        # Load model and model_path from database first
        try:
            from src.database import DatabaseManager
            db = DatabaseManager()
            model = db.get_setting('voice_model', None)
            model_path = db.get_setting('voice_model_path', None)
        except Exception as e:
            model = None
            model_path = None
            logger.warning(f"Could not load voice_model or voice_model_path from database: {e}")

        default_style = 'droid'
        speed = 0.75
        pitch = 0.85

        # If not in database, fall back to config.yaml for model name and params
        if model is None or model_path is None:
            try:
                import yaml
                cfg = None
                cfg_path = Path('config/config.yaml')
                if cfg_path.exists():
                    with open(cfg_path, 'r') as f:
                        cfg = yaml.safe_load(f) or {}
                else:
                    ex = Path('config/config.yaml.example')
                    if ex.exists():
                        with open(ex, 'r') as f:
                            cfg = yaml.safe_load(f) or {}
                voice_cfg = cfg.get('voice', {}) if cfg else {}
                if model is None:
                    model = voice_cfg.get('model', 'en_US-ryan-high')
                default_style = voice_cfg.get('default_style', 'droid')
                speed = float(voice_cfg.get('speed', 0.75))
                pitch = float(voice_cfg.get('pitch', 0.85))
                if model_path is None:
                    # Try to construct model_path from config
                    candidate = Path('data/voice_models/piper') / f"{model}.onnx"
                    if candidate.exists():
                        model_path = str(candidate)
            except Exception as e:
                logger.warning(f"Could not load voice config from yaml: {e}")

        # If model_path is a directory, append model name and .onnx
        if model_path:
            model_path_obj = Path(model_path).expanduser()
            if model_path_obj.is_dir():
                model_file = model + '.onnx' if model else 'en_US-ryan-high.onnx'
                candidate = model_path_obj / model_file
                if candidate.exists():
                    model_path = str(candidate)
                else:
                    logger.warning(f"Model file {candidate} does not exist in directory {model_path_obj}")
                    model_path = str(candidate)  # Still use the constructed path

        _voice = VoiceSystem(model_path=model_path, default_style=default_style, speed=speed, pitch=pitch)
        # Initial prune to keep cache in check on startup
        try:
            _voice.prune_cache()
        except Exception as e:
            logger.warning(f"Initial voice cache prune failed: {e}")
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
