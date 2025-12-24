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
    # Set the correct path as requested
    correct_path = str(Path.home() / "Projects/ramona/dashboard/data/voice_models/piper")
    db.save_setting('voice_model_path', correct_path)
    print(f"voice_model_path set to: {correct_path}")

if __name__ == "__main__":
    main()
