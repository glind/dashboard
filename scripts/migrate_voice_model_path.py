"""
Migration script to add the default voice_model_path setting to the dashboard database.
Run this script with the same Python environment as your dashboard app.
"""


import sys
import os
from pathlib import Path

# Ensure src is in sys.path
script_dir = Path(__file__).resolve().parent.parent
src_dir = script_dir / 'src'
sys.path.insert(0, str(src_dir))

from database import DatabaseManager


def main():
    db = DatabaseManager()
<<<<<<< HEAD
    # Set the default voice model path if not already set
    default_path = "/home/glind/Projects/ramona/data/voice_models/piper/en_US-ryan-high.onnx"
    current = db.get_setting('voice_model_path', None)
    if not current:
        db.save_setting('voice_model_path', default_path)
        print(f"voice_model_path set to: {default_path}")
    else:
        print(f"voice_model_path already set: {current}")
=======
    # Set the correct path as requested, always update
    correct_path = str(Path.home() / "Projects/ramona/dashboard/data/voice_models/piper")
    db.save_setting('voice_model_path', correct_path)
    print(f"voice_model_path updated to: {correct_path}")
>>>>>>> origin/master

if __name__ == "__main__":
    main()
