#!/usr/bin/env python3
"""
Personal Dashboard - macOS App Launcher
======================================
Standalone app launcher that starts the dashboard server and opens it in a WebKit window.
"""

import sys
import os
import time
import threading
import subprocess
import webbrowser
from pathlib import Path

import sys
import os
import time
import threading
import subprocess
import webbrowser
from pathlib import Path

# Determine if we're running as a PyInstaller bundle
if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
    # Running as PyInstaller bundle
    bundle_dir = Path(sys._MEIPASS)
    app_dir = Path(sys.executable).parent.parent  # Go up from MacOS to Contents
    dashboard_root = bundle_dir
    is_bundled = True
else:
    # Running as script - go up two levels to get to dashboard root
    script_dir = Path(__file__).parent  # packaging/macos/
    dashboard_root = script_dir.parent.parent  # dashboard/
    app_dir = dashboard_root
    is_bundled = False

# Set up paths
if is_bundled:
    # In bundled app, create config in user's home directory
    config_dir = Path.home() / ".personal-dashboard"
    config_dir.mkdir(exist_ok=True)
    
    # Copy default config files if they don't exist
    for config_file in ['config.yaml.example', 'credentials.yaml.example']:
        user_config = config_dir / config_file
        if not user_config.exists():
            try:
                bundle_config = bundle_dir / 'config' / config_file
                if bundle_config.exists():
                    import shutil
                    shutil.copy2(bundle_config, user_config)
                    print(f"Created default config: {user_config}")
            except Exception as e:
                print(f"Warning: Could not copy {config_file}: {e}")
    
    # Set environment variables for the app
    os.environ['DASHBOARD_CONFIG_DIR'] = str(config_dir)
    src_dir = bundle_dir
else:
    src_dir = dashboard_root / "src"

sys.path.insert(0, str(src_dir))

try:
    import webview
    WEBVIEW_AVAILABLE = True
except ImportError:
    WEBVIEW_AVAILABLE = False
    print("PyWebView not available, will use system browser")

def find_free_port():
    """Find a free port to run the server on."""
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port

def start_dashboard_server(port=8008):
    """Start the dashboard server in the background."""
    try:
        # Change to src directory if not bundled
        if not is_bundled:
            os.chdir(src_dir)
        
        # Start the server
        env = os.environ.copy()
        env['PYTHONPATH'] = str(src_dir)
        
        if is_bundled:
            # In bundled mode, run the main module directly
            import importlib.util
            spec = importlib.util.spec_from_file_location("main", src_dir / "main.py")
            main_module = importlib.util.module_from_spec(spec)
            
            # Start server in a thread
            def run_server():
                spec.loader.exec_module(main_module)
            
            server_thread = threading.Thread(target=run_server, daemon=True)
            server_thread.start()
            return server_thread
        else:
            # In script mode, use subprocess
            process = subprocess.Popen([
                sys.executable, 'main.py'
            ], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            print(f"Dashboard server starting on port {port}...")
            return process
    except Exception as e:
        print(f"Error starting server: {e}")
        return None

def wait_for_server(port=8008, timeout=30):
    """Wait for the server to be ready."""
    import socket
    import time
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            with socket.create_connection(('localhost', port), timeout=1):
                return True
        except (ConnectionRefusedError, OSError):
            time.sleep(0.5)
    return False

def create_webview_app(port=8008):
    """Create a WebKit-based window for the dashboard."""
    if not WEBVIEW_AVAILABLE:
        # Fallback to system browser
        url = f"http://localhost:{port}"
        print(f"Opening dashboard in system browser: {url}")
        webbrowser.open(url)
        return None
    
    # Create WebView window
    window = webview.create_window(
        title="Personal Dashboard",
        url=f"http://localhost:{port}",
        width=1400,
        height=900,
        min_size=(800, 600),
        resizable=True,
        fullscreen=False,
        minimized=False,
        on_top=False,
        shadow=True,
        focus=True
    )
    
    return window

def main():
    """Main application entry point."""
    print("🚀 Starting Personal Dashboard...")
    
    # Find available port
    port = 8008
    try:
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            result = s.connect_ex(('localhost', port))
            if result == 0:
                print(f"Port {port} is in use, finding alternative...")
                port = find_free_port()
                print(f"Using port {port}")
    except Exception:
        pass
    
    # Start the dashboard server
    server_process = start_dashboard_server(port)
    if not server_process:
        print("❌ Failed to start dashboard server")
        sys.exit(1)
    
    try:
        # Wait for server to be ready
        print("⏳ Waiting for server to start...")
        if not wait_for_server(port):
            print("❌ Server failed to start within timeout")
            server_process.terminate()
            sys.exit(1)
        
        print("✅ Server is ready!")
        
        # Create and show the WebView window
        if WEBVIEW_AVAILABLE:
            print("🖥️  Opening dashboard in WebKit window...")
            window = create_webview_app(port)
            
            # Start the WebView event loop
            webview.start(debug=False)
        else:
            print("🌐 Opening dashboard in system browser...")
            url = f"http://localhost:{port}"
            webbrowser.open(url)
            
            # Keep the server running
            print("📱 Dashboard is running. Close this terminal to stop.")
            try:
                server_process.wait()
            except KeyboardInterrupt:
                print("\n🛑 Shutting down...")
        
    finally:
        # Clean up
        if server_process:
            if is_bundled:
                # In bundled mode, server_process is a thread
                print("🛑 Server thread will stop when app exits")
            else:
                # In script mode, server_process is a subprocess
                server_process.terminate()
                try:
                    server_process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server_process.kill()
        
        print("👋 Dashboard stopped")

if __name__ == "__main__":
    main()