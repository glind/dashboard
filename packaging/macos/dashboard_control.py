#!/usr/bin/env python3
"""
Dashboard Control App - macOS Menu Bar Version
A simple menu bar application to control the Personal Dashboard server
"""

import rumps
import subprocess
import os
import signal
import requests
from pathlib import Path
import time

class DashboardController(rumps.App):
    def __init__(self):
        super(DashboardController, self).__init__("Dashboard", "⭕")
        
        # Find dashboard directory
        self.dashboard_dir = Path(__file__).parent.parent.parent.absolute()
        self.startup_script = self.dashboard_dir / "ops" / "startup.sh"
        self.pid_file = self.dashboard_dir / "dashboard.pid"
        
        # Set up menu
        self.menu = [
            rumps.MenuItem("Status: Checking...", callback=None),
            None,  # Separator
            "Start Server",
            "Restart Server",
            "Stop Server",
            None,
            "Open Dashboard",
            "View Logs",
            None,
            "Quit"
        ]
        
        # Start status checker
        self.timer = rumps.Timer(self.update_status, 5)
        self.timer.start()
        self.update_status(None)
    
    def get_server_status(self):
        """Check if server is running"""
        try:
            if self.pid_file.exists():
                with open(self.pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                try:
                    os.kill(pid, 0)  # Check if process exists
                    
                    try:
                        response = requests.get('http://localhost:8008/api/health', timeout=2)
                        if response.status_code == 200:
                            return 'running', pid
                    except:
                        pass
                    
                    return 'starting', pid
                except OSError:
                    self.pid_file.unlink()
                    return 'stopped', None
            
            return 'stopped', None
        except Exception as e:
            print(f"Error checking status: {e}")
            return 'unknown', None
    
    def update_status(self, sender):
        """Update status display"""
        status, pid = self.get_server_status()
        
        if status == 'running':
            self.menu["Status: Checking..."].title = f"✅ Running (PID: {pid})"
            self.icon = "✅"
            self.menu["Start Server"].set_callback(None)
            self.menu["Restart Server"].set_callback(self.restart_server)
            self.menu["Stop Server"].set_callback(self.stop_server)
            self.menu["Open Dashboard"].set_callback(self.open_dashboard)
        elif status == 'starting':
            self.menu["Status: Checking..."].title = f"⏳ Starting (PID: {pid})"
            self.icon = "⏳"
            self.menu["Start Server"].set_callback(None)
            self.menu["Restart Server"].set_callback(self.restart_server)
            self.menu["Stop Server"].set_callback(self.stop_server)
            self.menu["Open Dashboard"].set_callback(None)
        else:
            self.menu["Status: Checking..."].title = "⭕ Stopped"
            self.icon = "⭕"
            self.menu["Start Server"].set_callback(self.start_server)
            self.menu["Restart Server"].set_callback(None)
            self.menu["Stop Server"].set_callback(None)
            self.menu["Open Dashboard"].set_callback(None)
    
    def kill_existing_server(self):
        """Kill any existing server process"""
        try:
            result = subprocess.run(
                ['pgrep', '-f', 'python.*main.py'],
                capture_output=True,
                text=True
            )
            
            if result.stdout.strip():
                pids = result.stdout.strip().split('\n')
                for pid in pids:
                    try:
                        os.kill(int(pid), signal.SIGTERM)
                    except:
                        pass
                time.sleep(1)
        except Exception as e:
            print(f"Error killing existing server: {e}")
    
    @rumps.clicked("Start Server")
    def start_server(self, _):
        """Start the dashboard server"""
        try:
            self.kill_existing_server()
            subprocess.Popen(
                [str(self.startup_script)],
                cwd=str(self.dashboard_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            rumps.notification("Dashboard", "Server Starting", "The dashboard server is starting up...")
            rumps.Timer(self.update_status, 2).start()
        except Exception as e:
            rumps.alert(f"Failed to start server: {e}")
    
    @rumps.clicked("Restart Server")
    def restart_server(self, _):
        """Restart the dashboard server"""
        try:
            self.kill_existing_server()
            subprocess.Popen(
                [str(self.startup_script), 'restart'],
                cwd=str(self.dashboard_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            rumps.notification("Dashboard", "Server Restarting", "The dashboard server is restarting...")
            rumps.Timer(self.update_status, 2).start()
        except Exception as e:
            rumps.alert(f"Failed to restart server: {e}")
    
    @rumps.clicked("Stop Server")
    def stop_server(self, _):
        """Stop the dashboard server"""
        try:
            subprocess.Popen(
                [str(self.startup_script), 'stop'],
                cwd=str(self.dashboard_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            rumps.notification("Dashboard", "Server Stopping", "The dashboard server is shutting down...")
            rumps.Timer(self.update_status, 2).start()
        except Exception as e:
            rumps.alert(f"Failed to stop server: {e}")
    
    @rumps.clicked("Open Dashboard")
    def open_dashboard(self, _):
        """Open dashboard in browser"""
        subprocess.run(['open', 'http://localhost:8008'])
    
    @rumps.clicked("View Logs")
    def view_logs(self, _):
        """Open logs in terminal"""
        log_file = self.dashboard_dir / "dashboard.log"
        subprocess.run([
            'open', '-a', 'Terminal',
            str(self.dashboard_dir / "ops" / "startup.sh"),
            '--args', 'tail', '-f', str(log_file)
        ])

if __name__ == '__main__':
    try:
        app = DashboardController()
        app.run()
    except Exception as e:
        print(f"Error starting app: {e}")
        import traceback
        traceback.print_exc()
