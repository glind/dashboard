#!/usr/bin/env python3
"""
Minimal test app to verify database creation in bundled mode.
"""

import sys
import sqlite3
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(Path.home() / ".personal-dashboard" / "minimal_test.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

def get_database_path():
    """Get the appropriate database path for bundled vs script mode."""
    # Check if running as a PyInstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as bundle - store database in user's home directory
        config_dir = Path.home() / ".personal-dashboard"
        config_dir.mkdir(exist_ok=True)
        logger.info(f"Bundle mode - config dir: {config_dir}")
        return str(config_dir / "test_dashboard.db")
    else:
        # Running as script - store in project root
        path = str(Path(__file__).parent / "test_dashboard.db")
        logger.info(f"Script mode - database path: {path}")
        return path

def test_database_creation():
    """Test database creation with proper path handling."""
    try:
        db_path = get_database_path()
        logger.info(f"Database path: {db_path}")
        
        # Ensure the directory exists for the database file
        db_dir = Path(db_path).parent
        logger.info(f"Database directory: {db_dir}")
        logger.info(f"Directory exists: {db_dir.exists()}")
        
        db_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Directory created/confirmed: {db_dir.exists()}")
        
        # Try to create a test database
        logger.info(f"Attempting to connect to: {db_path}")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create a simple test table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test (
                id INTEGER PRIMARY KEY,
                message TEXT
            )
        """)
        
        # Insert test data
        cursor.execute("INSERT INTO test (message) VALUES (?)", ("Database works!",))
        conn.commit()
        
        # Read back the data
        cursor.execute("SELECT message FROM test")
        result = cursor.fetchone()
        
        conn.close()
        
        logger.info(f"Database test successful: {result[0] if result else 'No data'}")
        logger.info(f"Database file created: {Path(db_path).exists()}")
        logger.info(f"Database file size: {Path(db_path).stat().st_size if Path(db_path).exists() else 0} bytes")
        
        return True
        
    except Exception as e:
        logger.error(f"Database test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

def main():
    """Main function for the test app."""
    logger.info("=== Minimal Database Test App ===")
    logger.info(f"Python executable: {sys.executable}")
    logger.info(f"sys.frozen: {getattr(sys, 'frozen', False)}")
    logger.info(f"sys._MEIPASS: {getattr(sys, '_MEIPASS', 'Not set')}")
    logger.info(f"Running from: {Path(__file__).parent if '__file__' in globals() else 'Unknown'}")
    logger.info("")
    
    success = test_database_creation()
    logger.info(f"Test {'PASSED' if success else 'FAILED'}")
    
    if success:
        print("✅ Database creation test PASSED!")
    else:
        print("❌ Database creation test FAILED!")
        
    # Keep the window open briefly if running as app
    import time
    time.sleep(3)

if __name__ == "__main__":
    main()