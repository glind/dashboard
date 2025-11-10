#!/usr/bin/env python3
"""
Personal Dashboard - macOS App Launcher (Debug Version)
=======================================================
Standalone app launcher with extensive debugging and error handling.
"""

import sys
import os
import time
import threading
import subprocess
import webbrowser
import logging
import traceback
from pathlib import Path

# Set up comprehensive logging
log_dir = Path.home() / ".personal-dashboard"
log_dir.mkdir(exist_ok=True)
log_file = log_dir / "app_debug.log"

# Configure logging to both file and console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_file, mode='w'),  # Overwrite each time
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('dashboard_app')

def log_system_info():
    """Log comprehensive system information for debugging"""
    logger.info("=" * 60)
    logger.info("Personal Dashboard App - Debug Session Starting")
    logger.info("=" * 60)
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Python executable: {sys.executable}")
    logger.info(f"Platform: {sys.platform}")
    logger.info(f"Current working directory: {os.getcwd()}")
    logger.info(f"Script file: {__file__}")
    logger.info(f"sys.argv: {sys.argv}")
    logger.info(f"Environment PATH: {os.environ.get('PATH', 'Not set')}")
    logger.info(f"Log file location: {log_file}")
    
    # Check if running as bundle
    is_frozen = getattr(sys, 'frozen', False)
    has_meipass = hasattr(sys, '_MEIPASS')
    logger.info(f"sys.frozen: {is_frozen}")
    logger.info(f"sys._MEIPASS exists: {has_meipass}")
    
    if has_meipass:
        logger.info(f"Bundle directory: {sys._MEIPASS}")
        bundle_path = Path(sys._MEIPASS)
        if bundle_path.exists():
            logger.info(f"Bundle contents: {list(bundle_path.iterdir())}")

try:
    log_system_info()
    
    # Determine if we're running as a PyInstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        logger.info("Running as PyInstaller bundle")
        bundle_dir = Path(sys._MEIPASS)
        app_dir = Path(sys.executable).parent.parent  # Go up from MacOS to Contents
        dashboard_root = bundle_dir
        is_bundled = True
        logger.info(f"Bundle directory: {bundle_dir}")
        logger.info(f"App directory: {app_dir}")
    else:
        logger.info("Running as script")
        script_dir = Path(__file__).parent  # packaging/macos/
        dashboard_root = script_dir.parent.parent  # dashboard/
        app_dir = dashboard_root
        is_bundled = False
        logger.info(f"Script directory: {script_dir}")
        logger.info(f"Dashboard root: {dashboard_root}")

    # Set up paths
    if is_bundled:
        logger.info("Setting up bundled app configuration...")
        # In bundled app, create config in user's home directory
        config_dir = Path.home() / ".personal-dashboard"
        config_dir.mkdir(exist_ok=True)
        logger.info(f"Config directory: {config_dir}")
        
        # Copy default config files if they don't exist
        for config_file in ['config.yaml.example', 'credentials.yaml.example']:
            user_config = config_dir / config_file
            if not user_config.exists():
                try:
                    bundle_config = bundle_dir / 'config' / config_file
                    logger.info(f"Looking for bundle config: {bundle_config}")
                    if bundle_config.exists():
                        import shutil
                        shutil.copy2(bundle_config, user_config)
                        logger.info(f"Created default config: {user_config}")
                    else:
                        logger.warning(f"Bundle config not found: {bundle_config}")
                except Exception as e:
                    logger.error(f"Could not copy {config_file}: {e}")
                    logger.error(traceback.format_exc())
        
        # Set environment variables for the app
        os.environ['DASHBOARD_CONFIG_DIR'] = str(config_dir)
        src_dir = bundle_dir
        logger.info(f"Set DASHBOARD_CONFIG_DIR to: {config_dir}")
    else:
        src_dir = dashboard_root / "src"
        logger.info(f"Source directory: {src_dir}")

    # Add source directory to Python path
    sys.path.insert(0, str(src_dir))
    logger.info(f"Added to sys.path: {src_dir}")
    logger.info(f"Current sys.path: {sys.path[:3]}...")  # First 3 entries

    # Check for PyWebView
    logger.info("Checking for PyWebView...")
    try:
        import webview
        WEBVIEW_AVAILABLE = True
        logger.info(f"PyWebView available, version: {getattr(webview, '__version__', 'Unknown')}")
    except ImportError as e:
        WEBVIEW_AVAILABLE = False
        logger.error(f"PyWebView not available: {e}")
        logger.info("Will use system browser instead")

    def find_free_port():
        """Find a free port to run the server on."""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', 0))
                s.listen(1)
                port = s.getsockname()[1]
            logger.info(f"Found free port: {port}")
            return port
        except Exception as e:
            logger.error(f"Error finding free port: {e}")
            return 8008  # Default fallback

    def start_dashboard_server(port=8008):
        """Start the dashboard server in the background."""
        logger.info(f"Starting dashboard server on port {port}...")
        try:
            # Change to src directory if not bundled
            if not is_bundled:
                logger.info(f"Changing directory to: {src_dir}")
                os.chdir(src_dir)
            
            # Start the server
            env = os.environ.copy()
            env['PYTHONPATH'] = str(src_dir)
            logger.info(f"Set PYTHONPATH to: {src_dir}")
            
            if is_bundled:
                logger.info("Starting server in bundled mode...")
                # In bundled mode, run the main module directly
                import importlib.util
                main_py = src_dir / "main.py"
                logger.info(f"Loading main.py from: {main_py}")
                
                if not main_py.exists():
                    raise FileNotFoundError(f"main.py not found at {main_py}")
                
                spec = importlib.util.spec_from_file_location("main", main_py)
                if spec is None:
                    raise ImportError(f"Could not create spec for {main_py}")
                
                main_module = importlib.util.module_from_spec(spec)
                
                # Start server in a thread
                def run_server():
                    try:
                        logger.info("Executing main module...")
                        spec.loader.exec_module(main_module)
                    except Exception as e:
                        logger.error(f"Error in server thread: {e}")
                        logger.error(traceback.format_exc())
                
                server_thread = threading.Thread(target=run_server, daemon=True)
                logger.info("Starting server thread...")
                server_thread.start()
                
            else:
                logger.info("Starting server in script mode...")
                # In script mode, run as subprocess
                python_cmd = [sys.executable, "main.py"]
                logger.info(f"Running command: {' '.join(python_cmd)}")
                
                process = subprocess.Popen(
                    python_cmd,
                    cwd=src_dir,
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True
                )
                
                # Log subprocess output
                def log_output(pipe, level):
                    for line in pipe:
                        logger.log(level, f"Server: {line.strip()}")
                
                threading.Thread(target=log_output, args=(process.stdout, logging.INFO), daemon=True).start()
                threading.Thread(target=log_output, args=(process.stderr, logging.ERROR), daemon=True).start()
            
            # Wait for server to start
            logger.info("Waiting for server to start...")
            time.sleep(3)
            
            # Test if server is responding
            import urllib.request
            import urllib.error
            
            test_url = f"http://localhost:{port}/"
            logger.info(f"Testing server at: {test_url}")
            
            for attempt in range(10):
                try:
                    with urllib.request.urlopen(test_url, timeout=2) as response:
                        logger.info(f"Server is responding (status: {response.status})")
                        return True
                except urllib.error.URLError:
                    logger.info(f"Server not ready yet (attempt {attempt + 1}/10)")
                    time.sleep(1)
            
            logger.error("Server failed to start or is not responding")
            return False
            
        except Exception as e:
            logger.error(f"Error starting dashboard server: {e}")
            logger.error(traceback.format_exc())
            return False

    def open_dashboard(port=8008):
        """Open the dashboard in WebView or browser."""
        url = f"http://localhost:{port}/"
        logger.info(f"Opening dashboard at: {url}")
        
        try:
            if WEBVIEW_AVAILABLE:
                logger.info("Opening in WebView...")
                webview.create_window(
                    "Personal Dashboard",
                    url,
                    width=1200,
                    height=800,
                    resizable=True,
                    minimized=False
                )
                webview.start(debug=True)
            else:
                logger.info("Opening in system browser...")
                webbrowser.open(url)
                # Keep the process alive
                input("Press Enter to quit...")
                
        except Exception as e:
            logger.error(f"Error opening dashboard: {e}")
            logger.error(traceback.format_exc())
            # Fallback to system browser
            logger.info("Falling back to system browser...")
            webbrowser.open(url)
            input("Press Enter to quit...")

    def main():
        """Main application entry point."""
        logger.info("Starting main application...")
        
        try:
            # Find a free port
            port = find_free_port()
            
            # Start the dashboard server
            if start_dashboard_server(port):
                logger.info("Server started successfully, opening dashboard...")
                open_dashboard(port)
            else:
                logger.error("Failed to start server")
                input("Press Enter to quit...")
                
        except KeyboardInterrupt:
            logger.info("Application interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error in main: {e}")
            logger.error(traceback.format_exc())
            input("Press Enter to quit...")

    if __name__ == "__main__":
        main()
        
except Exception as e:
    # Catch any errors that occur before main() even starts
    try:
        logger.error(f"Fatal startup error: {e}")
        logger.error(traceback.format_exc())
    except:
        # If logging fails, print to stdout
        print(f"FATAL ERROR: {e}")
        traceback.print_exc()
    
    input("Press Enter to quit...")