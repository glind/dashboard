"""
Migration script to add the default voice_model_path setting to the dashboard database.
Run this script with the same Python environment as your dashboard app.
"""

from src.database import DatabaseManager

def main():
    db = DatabaseManager()
    # Set the default voice model path if not already set
    default_path = "data/voice_models/piper/en_US-ryan-high.onnx"
    current = db.get_setting('voice_model_path', None)
    if not current:
        db.save_setting('voice_model_path', default_path)
        print(f"voice_model_path set to: {default_path}")
    else:
        print(f"voice_model_path already set: {current}")

if __name__ == "__main__":
    main()
