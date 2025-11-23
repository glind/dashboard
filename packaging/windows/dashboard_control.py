#!/usr/bin/env python3
"""
Dashboard Control App - Windows System Tray Version
A simple system tray application to control the Personal Dashboard server on Windows
"""

import sys
import os
import signal
import subprocess
import webbrowser
from pathlib import Path
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon, QMenu, QAction, QMessageBox
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QIcon
import requests

class DashboardController:
    def __init__(self):
        self.app = QApplication(sys.argv)
        
        # Find dashboard directory
        self.dashboard_dir = Path(__file__).parent.parent.parent.absolute()
        self.startup_script = self.dashboard_dir / "ops" / "startup.sh"
        self.pid_file = self.dashboard_dir / "dashboard.pid"
        
        # Create system tray icon
        self.tray_icon = QSystemTrayIcon(self.app)
        self.tray_icon.setToolTip("Dashboard Controller")
        
        # Create menu
        self.menu = QMenu()
        
        # Status item (disabled)
        self.status_action = QAction("⭕ Checking status...", self.app)
        self.status_action.setEnabled(False)
        self.menu.addAction(self.status_action)
        
        self.menu.addSeparator()
        
        # Control actions
        self.start_action = QAction("▶️ Start Server", self.app)
        self.start_action.triggered.connect(self.start_server)
        self.menu.addAction(self.start_action)
        
        self.restart_action = QAction("🔄 Restart Server", self.app)
        self.restart_action.triggered.connect(self.restart_server)
        self.menu.addAction(self.restart_action)
        
        self.stop_action = QAction("⏹️ Stop Server", self.app)
        self.stop_action.triggered.connect(self.stop_server)
        self.menu.addAction(self.stop_action)
        
        self.menu.addSeparator()
        
        # Open dashboard action
        self.open_action = QAction("🌐 Open Dashboard", self.app)
        self.open_action.triggered.connect(self.open_dashboard)
        self.menu.addAction(self.open_action)
        
        # View logs action
        self.logs_action = QAction("📋 View Logs", self.app)
        self.logs_action.triggered.connect(self.view_logs)
        self.menu.addAction(self.logs_action)
        
        self.menu.addSeparator()
        
        # Quit action
        quit_action = QAction("❌ Quit", self.app)
        quit_action.triggered.connect(self.quit_app)
        self.menu.addAction(quit_action)
        
        # Set menu and show tray icon
        self.tray_icon.setContextMenu(self.menu)
        self.tray_icon.show()
        
        # Start status update timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_status)
        self.timer.start(5000)  # Update every 5 seconds
        self.update_status()
    
    def get_server_status(self):
        """Check if server is running"""
        try:
            if self.pid_file.exists():
                with open(self.pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                # On Windows, check if process exists differently
                try:
                    # Try using tasklist on Windows
                    result = subprocess.run(
                        ['tasklist', '/FI', f'PID eq {pid}'],
                        capture_output=True,
                        text=True
                    )
                    
                    if str(pid) in result.stdout:
                        # Process exists, check if responding
                        try:
                            response = requests.get('http://localhost:8008/api/health', timeout=2)
                            if response.status_code == 200:
                                return 'running', pid
                        except:
                            pass
                        return 'starting', pid
                    else:
                        self.pid_file.unlink()
                        return 'stopped', None
                except:
                    # Fallback to UNIX-style check
                    try:
                        os.kill(pid, 0)
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
    
    def update_status(self):
        """Update status display"""
        status, pid = self.get_server_status()
        
        if status == 'running':
            self.status_action.setText(f"✅ Server Running (PID: {pid})")
            self.start_action.setEnabled(False)
            self.restart_action.setEnabled(True)
            self.stop_action.setEnabled(True)
            self.open_action.setEnabled(True)
        elif status == 'starting':
            self.status_action.setText(f"⏳ Server Starting (PID: {pid})")
            self.start_action.setEnabled(False)
            self.restart_action.setEnabled(True)
            self.stop_action.setEnabled(True)
            self.open_action.setEnabled(False)
        else:
            self.status_action.setText("⭕ Server Stopped")
            self.start_action.setEnabled(True)
            self.restart_action.setEnabled(False)
            self.stop_action.setEnabled(False)
            self.open_action.setEnabled(False)
    
    def kill_existing_server(self):
        """Kill any existing server process"""
        try:
            # On Windows, use taskkill
            if sys.platform == 'win32':
                subprocess.run(['taskkill', '/F', '/IM', 'python.exe', '/FI', 'WINDOWTITLE eq *main.py*'])
            else:
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
        except Exception as e:
            print(f"Error killing existing server: {e}")
    
    def start_server(self):
        """Start the dashboard server"""
        try:
            self.kill_existing_server()
            
            # On Windows, use .bat or .cmd file instead of .sh
            if sys.platform == 'win32':
                startup_cmd = self.dashboard_dir / "ops" / "startup.bat"
                if not startup_cmd.exists():
                    startup_cmd = self.dashboard_dir / "ops" / "startup.sh"
            else:
                startup_cmd = self.startup_script
            
            subprocess.Popen(
                [str(startup_cmd)],
                cwd=str(self.dashboard_dir),
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            self.tray_icon.showMessage(
                "Dashboard",
                "Server starting...",
                QSystemTrayIcon.Information,
                2000
            )
            QTimer.singleShot(2000, self.update_status)
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to start server: {e}")
    
    def restart_server(self):
        """Restart the dashboard server"""
        try:
            self.kill_existing_server()
            
            if sys.platform == 'win32':
                startup_cmd = self.dashboard_dir / "ops" / "startup.bat"
                if not startup_cmd.exists():
                    startup_cmd = self.dashboard_dir / "ops" / "startup.sh"
            else:
                startup_cmd = self.startup_script
            
            subprocess.Popen(
                [str(startup_cmd), 'restart'],
                cwd=str(self.dashboard_dir),
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            self.tray_icon.showMessage(
                "Dashboard",
                "Server restarting...",
                QSystemTrayIcon.Information,
                2000
            )
            QTimer.singleShot(2000, self.update_status)
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to restart server: {e}")
    
    def stop_server(self):
        """Stop the dashboard server"""
        try:
            if sys.platform == 'win32':
                startup_cmd = self.dashboard_dir / "ops" / "startup.bat"
                if not startup_cmd.exists():
                    startup_cmd = self.dashboard_dir / "ops" / "startup.sh"
            else:
                startup_cmd = self.startup_script
            
            subprocess.Popen(
                [str(startup_cmd), 'stop'],
                cwd=str(self.dashboard_dir),
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            self.tray_icon.showMessage(
                "Dashboard",
                "Server stopping...",
                QSystemTrayIcon.Information,
                2000
            )
            QTimer.singleShot(2000, self.update_status)
        except Exception as e:
            QMessageBox.critical(None, "Error", f"Failed to stop server: {e}")
    
    def open_dashboard(self):
        """Open dashboard in browser"""
        webbrowser.open('http://localhost:8008')
    
    def view_logs(self):
        """Open logs in notepad or default text editor"""
        log_file = self.dashboard_dir / "dashboard.log"
        if sys.platform == 'win32':
            os.startfile(str(log_file))
        else:
            subprocess.run(['open' if sys.platform == 'darwin' else 'xdg-open', str(log_file)])
    
    def quit_app(self):
        """Quit the application"""
        self.app.quit()
    
    def run(self):
        """Run the application"""
        sys.exit(self.app.exec_())

if __name__ == '__main__':
    controller = DashboardController()
    controller.run()
