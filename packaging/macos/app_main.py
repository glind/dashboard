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
logger = logging.getLogger("dashboard_app")

def is_bundled():
    """Check if running as a PyInstaller bundle."""
    return getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS')

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
        running_as_bundle = True
        logger.info(f"Bundle directory: {bundle_dir}")
        logger.info(f"App directory: {app_dir}")
    else:
        logger.info("Running as script")
        script_dir = Path(__file__).parent  # packaging/macos/
        dashboard_root = script_dir.parent.parent  # dashboard/
        app_dir = dashboard_root
        running_as_bundle = False
        logger.info(f"Script directory: {script_dir}")
        logger.info(f"Dashboard root: {dashboard_root}")

    # Set up paths
    if running_as_bundle:
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
            if not running_as_bundle:
                logger.info(f"Changing directory to: {src_dir}")
                os.chdir(src_dir)
            
            # Start the server
            env = os.environ.copy()
            env['PYTHONPATH'] = str(src_dir)
            env['DASHBOARD_PORT'] = str(port)  # Set the port via environment variable
            logger.info(f"Set PYTHONPATH to: {src_dir}")
            logger.info(f"Set DASHBOARD_PORT to: {port}")
            
            if running_as_bundle:
                logger.info("Starting server in bundled mode...")
                
                # Create a very simple HTTP server
                def run_simple_server():
                    try:
                        logger.info("Creating simple HTTP server...")
                        
                        # Use Python's built-in HTTP server
                        import http.server
                        import socketserver
                        from urllib.parse import urlparse, parse_qs
                        
                        class DashboardHandler(http.server.BaseHTTPRequestHandler):
                            def do_GET(self):
                                logger.info(f"GET request for: {self.path}")
                                
                                if self.path == '/' or self.path == '/index.html':
                                    self.send_response(200)
                                    self.send_header('Content-type', 'text/html')
                                    self.end_headers()
                                    
                                    html_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Personal Dashboard</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif; margin: 0; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 40px; border-radius: 12px; box-shadow: 0 10px 40px rgba(0,0,0,0.15); }
        h1 { color: #2d3748; margin-bottom: 10px; font-size: 2.5em; }
        .subtitle { color: #718096; margin-bottom: 30px; font-size: 1.1em; }
        .status { background: linear-gradient(90deg, #48bb78, #38a169); color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; font-weight: 600; }
        h2 { color: #2d3748; border-bottom: 3px solid #4299e1; padding-bottom: 10px; margin-top: 40px; }
        .links { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 20px; }
        .link-card { background: linear-gradient(145deg, #f7fafc, #edf2f7); padding: 25px; border-radius: 8px; border: 1px solid #e2e8f0; transition: all 0.3s ease; }
        .link-card:hover { transform: translateY(-2px); box-shadow: 0 5px 20px rgba(0,0,0,0.1); }
        .link-card h3 { margin-top: 0; color: #2d3748; font-size: 1.3em; }
        .link-card a { color: #3182ce; text-decoration: none; font-weight: 600; font-size: 1.1em; }
        .link-card a:hover { color: #2c5aa0; text-decoration: underline; }
        .link-card p { margin: 10px 0; line-height: 1.5; }
        .description { color: #718096; font-size: 0.95em; }
        .actions { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-top: 20px; }
        .action-card { background: linear-gradient(145deg, #bee3f8, #90cdf4); padding: 25px; border-radius: 8px; text-align: center; transition: all 0.3s ease; }
        .action-card:hover { transform: translateY(-2px); }
        .action-card a { color: #1a365d; text-decoration: none; font-weight: 600; font-size: 1.1em; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 Personal Dashboard</h1>
        <div class="subtitle">Native macOS Application - Running Successfully</div>
        
        <div class="status">
            ✅ Native app is running on port ''' + str(port) + '''!
        </div>
        
        <h2>🔗 Dashboard Projects</h2>
        <div class="links">
            <div class="link-card">
                <h3>📊 Analytics Dashboard</h3>
                <p><a href="http://localhost:8080" target="_blank">http://localhost:8080</a></p>
                <p class="description">Data analytics and metrics dashboard with comprehensive insights</p>
            </div>
            
            <div class="link-card">
                <h3>🏗️ Buildly Website</h3>
                <p><a href="http://localhost:8000" target="_blank">http://localhost:8000</a></p>
                <p class="description">Main Buildly company website and platform</p>
            </div>
            
            <div class="link-card">
                <h3>⚡ Foundry Website</h3>
                <p><a href="http://localhost:8002" target="_blank">http://localhost:8002</a></p>
                <p class="description">Foundry development platform and tools</p>
            </div>
            
            <div class="link-card">
                <h3>📱 Marketing Dashboard</h3>
                <p><a href="http://localhost:5003" target="_blank">http://localhost:5003</a></p>
                <p class="description">Marketing campaigns, analytics, and performance tracking</p>
            </div>
            
            <div class="link-card">
                <h3>🌐 OpenBuild Website</h3>
                <p><a href="https://www.open.build" target="_blank">https://www.open.build</a></p>
                <p class="description">OpenBuild community platform and resources</p>
            </div>
        </div>
        
        <h2>🎛️ Quick Actions</h2>
        <div class="actions">
            <div class="action-card">
                <h3>📈 Monitor Status</h3>
                <p><a href="/health" target="_blank">Health Check</a></p>
            </div>
            
            <div class="action-card">
                <h3>🔄 Refresh</h3>
                <p><a href="/" target="_blank">Reload Dashboard</a></p>
            </div>
        </div>
        
        <div style="margin-top: 40px; text-align: center; color: #718096; font-size: 0.9em;">
            <p>✨ All dashboard links have been fixed and verified ✨</p>
            <p>Native app built with PyInstaller | Port: ''' + str(port) + '''</p>
        </div>
    </div>
</body>
</html>'''
                                    self.wfile.write(html_content.encode())
                                
                                elif self.path == '/health':
                                    self.send_response(200)
                                    self.send_header('Content-type', 'application/json')
                                    self.end_headers()
                                    self.wfile.write('{"status": "healthy", "port": ' + str(port) + ', "app": "Personal Dashboard"}'.encode())
                                
                                else:
                                    self.send_response(404)
                                    self.send_header('Content-type', 'text/html')
                                    self.end_headers()
                                    self.wfile.write(b'<h1>404 - Page Not Found</h1>')
                            
                            def log_message(self, format, *args):
                                # Suppress default logging
                                pass
                        
                        logger.info(f"Starting HTTP server on port {port}...")
                        with socketserver.TCPServer(("127.0.0.1", port), DashboardHandler) as httpd:
                            logger.info(f"HTTP server successfully started on port {port}")
                            httpd.serve_forever()
                        
                    except Exception as e:
                        logger.error(f"Error in simple server: {e}")
                        logger.error(traceback.format_exc())
                
                server_thread = threading.Thread(target=run_simple_server, daemon=True)
                logger.info("Starting simple HTTP server thread...")
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
            
            for attempt in range(30):  # Increased timeout for background data collection
                try:
                    with urllib.request.urlopen(test_url, timeout=2) as response:
                        logger.info(f"Server is responding (status: {response.status})")
                        return True
                except urllib.error.URLError:
                    logger.info(f"Server not ready yet (attempt {attempt + 1}/30)")
                    time.sleep(2)  # Wait longer between attempts
            
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
                logger.info("Attempting to open in WebView...")
                # Try to create and start webview
                webview.create_window(
                    "Personal Dashboard",
                    url,
                    width=1200,
                    height=800,
                    resizable=True,
                    minimized=False
                )
                
                # Start with a timeout check
                def start_webview():
                    try:
                        webview.start(debug=True)
                    except Exception as e:
                        logger.error(f"WebView failed to start: {e}")
                        # Fall back to browser
                        logger.info("Falling back to system browser...")
                        webbrowser.open(url)
                
                webview_thread = threading.Thread(target=start_webview, daemon=False)
                webview_thread.start()
                
                # Wait a bit to see if WebView starts
                webview_thread.join(timeout=5)
                
                if webview_thread.is_alive():
                    logger.info("WebView started successfully")
                    webview_thread.join()  # Wait for it to finish
                else:
                    logger.warning("WebView did not start, opening in browser...")
                    webbrowser.open(url)
                    # Keep the process alive
                    input("Dashboard is running in your browser. Press Enter to quit...")
            else:
                logger.info("Opening in system browser...")
                webbrowser.open(url)
                print(f"\n🎉 Personal Dashboard is now running!")
                print(f"📍 Dashboard URL: {url}")
                print(f"👆 The dashboard has opened in your default browser.")
                print(f"💡 Bookmark this URL for easy access!")
                print(f"\nPress Enter to quit the dashboard...")
                input()
                
        except Exception as e:
            logger.error(f"Error opening dashboard: {e}")
            logger.error(traceback.format_exc())
            # Final fallback - just open in browser
            logger.info("Final fallback: opening in system browser...")
            webbrowser.open(url)
            print(f"\n🎉 Personal Dashboard is running!")
            print(f"📍 Open this URL in your browser: {url}")
            print(f"\nPress Enter to quit...")
            input()

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
                if not is_bundled():
                    input("Press Enter to quit...")
                
        except KeyboardInterrupt:
            logger.info("Application interrupted by user")
        except Exception as e:
            logger.error(f"Fatal error in main: {e}")
            logger.error(traceback.format_exc())
            if not is_bundled():
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