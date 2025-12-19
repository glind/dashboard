#!/usr/bin/env python3
"""
Quick demo of Rogr voice system
Run this to hear the different voice styles
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from voice import VoiceSystem
import logging

logging.basicConfig(level=logging.INFO)

def main():
    print("🤖 Rogr Voice System Demo")
    print("=" * 50)
    print()
    
    # Initialize voice system
    project_root = Path(__file__).parent.parent
    piper_bin = project_root / "data" / "voice_models" / "piper" / "piper"
    model_path = project_root / "data" / "voice_models" / "piper" / "en_US-ryan-high.onnx"
    
    if not piper_bin.exists() or not model_path.exists():
        print("❌ Voice system not set up.")
        print("Run: ./scripts/setup_voice.sh")
        return
    
    voice = VoiceSystem(
        piper_bin=str(piper_bin),
        model_path=str(model_path),
        default_style="droid"
    )
    
    # Demo phrases
    demos = [
        ("droid", "Roger roger. Battle droid voice online."),
        ("radio", "This is a radio transmission test."),
        ("pa_system", "Attention. This is a PA system announcement."),
        ("clean", "This is the clean, unprocessed voice."),
    ]
    
    print("Testing voice styles...\n")
    
    for style, text in demos:
        print(f"🔊 {style.upper()}: {text}")
        voice.say(text, style=style, blocking=True)
        print("   ✅ Complete\n")
    
    # Demo with signature
    print("🔊 With signature phrase:")
    voice.announce("Dashboard initialization complete", blocking=True)
    print("   ✅ Complete\n")
    
    print("✨ Demo complete!")
    print("\nUsage:")
    print("  from src.voice import say, announce")
    print("  say('Your message here')")
    print("  announce('Message with roger roger')")

if __name__ == "__main__":
    main()
