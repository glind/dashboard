#!/usr/bin/env python3
"""
Personal Dashboard - Simple Native macOS Application
Opens the dashboard in the default browser and provides a native interface.
"""

import sys
import os
import logging
import webbrowser
import time
import threading
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Main application entry point."""
    try:
        logger.info("Starting Personal Dashboard Native App...")
        
        # Dashboard URL - use the main dashboard if it's running
        dashboard_url = "http://localhost:8008"
        
        # Create a simple status window using pywebview
        try:
            import webview
            
            # Create HTML content for the native window
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Personal Dashboard</title>
                <meta charset="utf-8">
                <style>
                    body {{
                        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
                        margin: 0;
                        padding: 40px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        min-height: 100vh;
                        display: flex;
                        align-items: center;
                        justify-content: center;
                    }}
                    .container {{
                        max-width: 600px;
                        background: white;
                        padding: 40px;
                        border-radius: 12px;
                        box-shadow: 0 10px 40px rgba(0,0,0,0.15);
                        text-align: center;
                    }}
                    h1 {{
                        color: #2d3748;
                        margin-bottom: 20px;
                        font-size: 2.2em;
                    }}
                    .status {{
                        background: linear-gradient(90deg, #48bb78, #38a169);
                        color: white;
                        padding: 20px;
                        border-radius: 8px;
                        margin: 20px 0;
                        font-weight: 600;
                    }}
                    .button {{
                        background: linear-gradient(145deg, #4299e1, #3182ce);
                        color: white;
                        border: none;
                        padding: 15px 30px;
                        border-radius: 8px;
                        font-size: 16px;
                        font-weight: 600;
                        cursor: pointer;
                        margin: 10px;
                        transition: all 0.3s ease;
                    }}
                    .button:hover {{
                        transform: translateY(-2px);
                        box-shadow: 0 5px 15px rgba(0,0,0,0.2);
                    }}
                    .links {{
                        margin-top: 30px;
                        text-align: left;
                    }}
                    .link-item {{
                        background: #f7fafc;
                        padding: 15px;
                        border-radius: 6px;
                        margin: 10px 0;
                        border: 1px solid #e2e8f0;
                    }}
                    .link-item h3 {{
                        margin: 0 0 5px 0;
                        color: #2d3748;
                    }}
                    .link-item a {{
                        color: #3182ce;
                        text-decoration: none;
                        font-weight: 500;
                    }}
                    .link-item a:hover {{
                        text-decoration: underline;
                    }}
                    .description {{
                        color: #718096;
                        font-size: 0.9em;
                        margin-top: 5px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🚀 Personal Dashboard</h1>
                    <div class="status">
                        ✅ Native macOS Application Ready
                    </div>
                    
                    <button class="button" onclick="openDashboard()">
                        📊 Open Dashboard in Browser
                    </button>
                    
                    <button class="button" onclick="checkStatus()">
                        🔍 Check Server Status
                    </button>
                    
                    <div class="links">
                        <h3>🔗 Quick Links</h3>
                        
                        <div class="link-item">
                            <h3>📊 Analytics Dashboard</h3>
                            <a href="#" onclick="openLink('http://localhost:8080')">http://localhost:8080</a>
                            <div class="description">Data analytics and metrics dashboard</div>
                        </div>
                        
                        <div class="link-item">
                            <h3>🏗️ Buildly Website</h3>
                            <a href="#" onclick="openLink('http://localhost:8000')">http://localhost:8000</a>
                            <div class="description">Main Buildly company website</div>
                        </div>
                        
                        <div class="link-item">
                            <h3>⚡ Foundry Website</h3>
                            <a href="#" onclick="openLink('http://localhost:8002')">http://localhost:8002</a>
                            <div class="description">Foundry development platform</div>
                        </div>
                        
                        <div class="link-item">
                            <h3>📱 Marketing Dashboard</h3>
                            <a href="#" onclick="openLink('http://localhost:5003')">http://localhost:5003</a>
                            <div class="description">Marketing campaigns and analytics</div>
                        </div>
                    </div>
                </div>
                
                <script>
                    function openDashboard() {{
                        window.pywebview.api.open_dashboard();
                    }}
                    
                    function checkStatus() {{
                        window.pywebview.api.check_status();
                    }}
                    
                    function openLink(url) {{
                        window.pywebview.api.open_link(url);
                    }}
                </script>
            </body>
            </html>
            """
            
            class Api:
                def open_dashboard(self):
                    logger.info("Opening dashboard in browser...")
                    webbrowser.open(dashboard_url)
                    return "Dashboard opened in browser"
                
                def check_status(self):
                    logger.info("Checking server status...")
                    try:
                        import requests
                        response = requests.get(dashboard_url, timeout=3)
                        if response.status_code == 200:
                            logger.info("Dashboard server is running")
                            return "Dashboard server is running ✅"
                        else:
                            logger.warning(f"Dashboard server returned status {response.status_code}")
                            return f"Dashboard server returned status {response.status_code} ⚠️"
                    except Exception as e:
                        logger.error(f"Dashboard server is not responding: {e}")
                        return f"Dashboard server is not responding: {e} ❌"
                
                def open_link(self, url):
                    logger.info(f"Opening link: {url}")
                    webbrowser.open(url)
                    return f"Opened {url}"
            
            # Create the native window
            api = Api()
            
            # Auto-open dashboard in browser after a short delay
            def auto_open_dashboard():
                time.sleep(1)  # Wait 1 second
                logger.info("Auto-opening dashboard in browser...")
                webbrowser.open(dashboard_url)
            
            # Start auto-open in background
            threading.Thread(target=auto_open_dashboard, daemon=True).start()
            
            # Create and start the native window
            logger.info("Creating native window...")
            webview.create_window(
                'Personal Dashboard',
                html=html_content,
                js_api=api,
                width=700,
                height=600,
                min_size=(600, 500),
                resizable=True
            )
            
            logger.info("Starting webview...")
            webview.start(debug=False)
            
        except ImportError:
            logger.error("PyWebView not available, falling back to browser-only mode")
            # Fallback: just open in browser
            logger.info("Opening dashboard in browser...")
            webbrowser.open(dashboard_url)
            
            # Keep the process alive for a bit
            print("Dashboard opened in browser. You can close this terminal.")
            time.sleep(5)
        
        except Exception as e:
            logger.error(f"Error creating native window: {e}")
            # Fallback: just open in browser
            logger.info("Opening dashboard in browser as fallback...")
            webbrowser.open(dashboard_url)
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        import traceback
        logger.error(traceback.format_exc())

if __name__ == "__main__":
    main()