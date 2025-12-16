#!/usr/bin/env python3
"""
Personal Dashboard - Desktop Application
Native desktop app using pywebview + FastAPI backend
"""

import os
import sys
import time
import threading
import logging
import signal
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

try:
    import webview
except ImportError:
    print("❌ pywebview not installed. Installing...")
    os.system(f"{sys.executable} -m pip install pywebview")
    import webview

import uvicorn
from src.main import app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Configuration
APP_NAME = "Personal Dashboard"
HOST = "127.0.0.1"
PORT = 8008
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 900
MIN_WIDTH = 1024
MIN_HEIGHT = 768

class DesktopApp:
    """Desktop application manager."""
    
    def __init__(self):
        self.server_thread = None
        self.server_started = False
        self.window = None
        self.splash_window = None
        
    def start_server(self):
        """Start FastAPI server in background thread."""
        try:
            logger.info(f"🚀 Starting FastAPI server on {HOST}:{PORT}")
            uvicorn.run(
                app,
                host=HOST,
                port=PORT,
                log_level="info",
                access_log=False,  # Disable access logs for cleaner output
                reload=False  # Disable reload for desktop mode
            )
        except Exception as e:
            logger.error(f"❌ Failed to start server: {e}")
            sys.exit(1)
    
    def wait_for_server(self, max_attempts=30, delay=0.5):
        """Wait for server to be ready."""
        import socket
        
        logger.info("⏳ Waiting for server to start...")
        
        for attempt in range(max_attempts):
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(1)
                result = sock.connect_ex((HOST, PORT))
                sock.close()
                
                if result == 0:
                    self.server_started = True
                    logger.info("✅ Server is ready!")
                    return True
                    
            except Exception as e:
                pass
            
            time.sleep(delay)
            
        logger.error("❌ Server failed to start within timeout")
        return False
    
    def create_splash_window(self):
        """Create splash screen window."""
        logger.info("🪟 Creating splash screen...")
        
        splash_path = Path(__file__).parent / 'splash.html'
        if not splash_path.exists():
            logger.warning("⚠️  Splash screen not found, skipping...")
            return None
        
        self.splash_window = webview.create_window(
            title='Loading...',
            url=str(splash_path),
            width=600,
            height=500,
            resizable=False,
            fullscreen=False,
            frameless=True,
            easy_drag=True,
            background_color='#1a1a1a',
            on_top=True
        )
        
        return self.splash_window
    
    def create_window(self):
        """Create and configure desktop window."""
        logger.info("🪟 Creating desktop window...")
        
        self.window = webview.create_window(
            title=APP_NAME,
            url=f"http://{HOST}:{PORT}",
            width=WINDOW_WIDTH,
            height=WINDOW_HEIGHT,
            resizable=True,
            fullscreen=False,
            min_size=(MIN_WIDTH, MIN_HEIGHT),
            background_color='#1a1a1a',
            text_select=True,
            hidden=True  # Start hidden, show after splash
        )
        
        return self.window
    
    def on_closing(self):
        """Handle window closing event."""
        logger.info("👋 Closing application...")
        
    def transition_from_splash(self):
        """Transition from splash screen to main app."""
        def do_transition():
            time.sleep(0.5)  # Brief delay for smooth transition
            
            if self.window:
                logger.info("✨ Showing main window...")
                self.window.show()
            
            if self.splash_window:
                logger.info("👋 Closing splash screen...")
                self.splash_window.destroy()
        
        threading.Thread(target=do_transition, daemon=True).start()
    
    def run(self):
        """Run the desktop application."""
        try:
            # Create splash screen first
            self.create_splash_window()
            
            # Start server in background thread
            self.server_thread = threading.Thread(
                target=self.start_server,
                daemon=True,
                name="FastAPI-Server"
            )
            self.server_thread.start()
            
            # Create main window (hidden)
            self.create_window()
            
            # Start webview with splash screen
            logger.info("✨ Launching application...")
            
            # Wait for server in background, then transition
            def wait_and_transition():
                if self.wait_for_server():
                    logger.info("✅ Server ready, transitioning to main app...")
                    self.transition_from_splash()
                else:
                    logger.error("❌ Could not start server")
                    # Show error in splash or close
                    if self.splash_window:
                        self.splash_window.destroy()
            
            threading.Thread(target=wait_and_transition, daemon=True).start()
            
            webview.start(debug=False)
            
            logger.info("👋 Application closed")
            
        except KeyboardInterrupt:
            logger.info("\n⚠️  Interrupted by user")
        except Exception as e:
            logger.error(f"❌ Application error: {e}")
            sys.exit(1)


def main():
    """Main entry point."""
    print("""
    ╔══════════════════════════════════════════╗
    ║     Personal Dashboard - Desktop App     ║
    ║                                          ║
    ║  🚀 Native desktop application           ║
    ║  🎯 FastAPI + pywebview                  ║
    ║  💻 Running on localhost:{PORT}            ║
    ╚══════════════════════════════════════════╝
    """.format(PORT=PORT))
    
    # Handle graceful shutdown
    def signal_handler(sig, frame):
        logger.info("\n⚠️  Shutting down...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Run application
    app_instance = DesktopApp()
    app_instance.run()


if __name__ == "__main__":
    main()
