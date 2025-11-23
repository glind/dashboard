#!/usr/bin/env python3
"""
Dashboard Control App - Linux Desktop Application
A simple system tray application to control the Personal Dashboard server
"""

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('AppIndicator3', '0.1')
from gi.repository import Gtk, AppIndicator3, GLib
import subprocess
import os
import signal
import requests
from pathlib import Path

class DashboardController:
    def __init__(self):
        self.dashboard_dir = Path(__file__).parent.absolute()
        self.startup_script = self.dashboard_dir / "ops" / "startup.sh"
        self.pid_file = self.dashboard_dir / "dashboard.pid"
        
        # Create indicator
        self.indicator = AppIndicator3.Indicator.new(
            "dashboard-controller",
            "application-default-icon",
            AppIndicator3.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(self.build_menu())
        
        # Start status check loop
        GLib.timeout_add_seconds(5, self.update_status)
        self.update_status()
    
    def build_menu(self):
        """Build the system tray menu"""
        menu = Gtk.Menu()
        
        # Status item (non-clickable)
        self.status_item = Gtk.MenuItem(label="Checking status...")
        self.status_item.set_sensitive(False)
        menu.append(self.status_item)
        
        # Separator
        menu.append(Gtk.SeparatorMenuItem())
        
        # Start button
        self.start_item = Gtk.MenuItem(label="▶️ Start Server")
        self.start_item.connect('activate', self.start_server)
        menu.append(self.start_item)
        
        # Restart button
        self.restart_item = Gtk.MenuItem(label="🔄 Restart Server")
        self.restart_item.connect('activate', self.restart_server)
        menu.append(self.restart_item)
        
        # Stop button
        self.stop_item = Gtk.MenuItem(label="⏹️ Stop Server")
        self.stop_item.connect('activate', self.stop_server)
        menu.append(self.stop_item)
        
        # Separator
        menu.append(Gtk.SeparatorMenuItem())
        
        # Open Dashboard button
        self.open_item = Gtk.MenuItem(label="🌐 Open Dashboard")
        self.open_item.connect('activate', self.open_dashboard)
        menu.append(self.open_item)
        
        # View Logs button
        self.logs_item = Gtk.MenuItem(label="📋 View Logs")
        self.logs_item.connect('activate', self.view_logs)
        menu.append(self.logs_item)
        
        # Separator
        menu.append(Gtk.SeparatorMenuItem())
        
        # Quit button
        quit_item = Gtk.MenuItem(label="❌ Quit Controller")
        quit_item.connect('activate', self.quit_app)
        menu.append(quit_item)
        
        menu.show_all()
        return menu
    
    def get_server_status(self):
        """Check if server is running"""
        try:
            # Check if PID file exists
            if self.pid_file.exists():
                with open(self.pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
                # Check if process is actually running
                try:
                    os.kill(pid, 0)  # This doesn't kill, just checks
                    
                    # Check if server responds
                    try:
                        response = requests.get('http://localhost:8008/api/health', timeout=2)
                        if response.status_code == 200:
                            return 'running', pid
                    except:
                        pass
                    
                    return 'starting', pid
                except OSError:
                    # Process not running, clean up PID file
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
            self.status_item.set_label(f"✅ Server Running (PID: {pid})")
            self.indicator.set_icon("network-transmit-receive")
            self.start_item.set_sensitive(False)
            self.restart_item.set_sensitive(True)
            self.stop_item.set_sensitive(True)
            self.open_item.set_sensitive(True)
        elif status == 'starting':
            self.status_item.set_label(f"⏳ Server Starting (PID: {pid})")
            self.indicator.set_icon("network-idle")
            self.start_item.set_sensitive(False)
            self.restart_item.set_sensitive(True)
            self.stop_item.set_sensitive(True)
            self.open_item.set_sensitive(False)
        else:
            self.status_item.set_label("⭕ Server Stopped")
            self.indicator.set_icon("network-offline")
            self.start_item.set_sensitive(True)
            self.restart_item.set_sensitive(False)
            self.stop_item.set_sensitive(False)
            self.open_item.set_sensitive(False)
        
        return True  # Continue the timer
    
    def kill_existing_server(self):
        """Kill any existing server process"""
        try:
            # Try to find and kill process by pattern
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
                        print(f"Killed existing process: {pid}")
                    except:
                        pass
                # Wait a moment for graceful shutdown
                import time
                time.sleep(1)
        except Exception as e:
            print(f"Error killing existing server: {e}")
    
    def start_server(self, widget):
        """Start the dashboard server"""
        try:
            # Kill any existing server first
            self.kill_existing_server()
            
            subprocess.Popen(
                [str(self.startup_script)],
                cwd=str(self.dashboard_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            GLib.timeout_add(2000, self.update_status)
            self.show_notification("Dashboard", "Server starting...")
        except Exception as e:
            self.show_notification("Error", f"Failed to start server: {e}")
    
    def restart_server(self, widget):
        """Restart the dashboard server"""
        try:
            # Kill any existing server first
            self.kill_existing_server()
            
            subprocess.Popen(
                [str(self.startup_script), 'restart'],
                cwd=str(self.dashboard_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            GLib.timeout_add(2000, self.update_status)
            self.show_notification("Dashboard", "Server restarting...")
        except Exception as e:
            self.show_notification("Error", f"Failed to restart server: {e}")
    
    def stop_server(self, widget):
        """Stop the dashboard server"""
        try:
            subprocess.Popen(
                [str(self.startup_script), 'stop'],
                cwd=str(self.dashboard_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            GLib.timeout_add(2000, self.update_status)
            self.show_notification("Dashboard", "Server stopping...")
        except Exception as e:
            self.show_notification("Error", f"Failed to stop server: {e}")
    
    def open_dashboard(self, widget):
        """Open dashboard in browser"""
        try:
            subprocess.Popen(['xdg-open', 'http://localhost:8008'])
        except Exception as e:
            self.show_notification("Error", f"Failed to open browser: {e}")
    
    def view_logs(self, widget):
        """Open logs in terminal"""
        try:
            log_file = self.dashboard_dir / "dashboard.log"
            # Try common terminal emulators
            terminals = [
                ['gnome-terminal', '--', 'tail', '-f', str(log_file)],
                ['konsole', '-e', 'tail', '-f', str(log_file)],
                ['xterm', '-e', 'tail', '-f', str(log_file)],
                ['x-terminal-emulator', '-e', 'tail', '-f', str(log_file)],
            ]
            
            for terminal_cmd in terminals:
                try:
                    subprocess.Popen(terminal_cmd)
                    return
                except FileNotFoundError:
                    continue
            
            self.show_notification("Error", "No terminal emulator found")
        except Exception as e:
            self.show_notification("Error", f"Failed to open logs: {e}")
    
    def show_notification(self, title, message):
        """Show desktop notification"""
        try:
            subprocess.Popen([
                'notify-send',
                '-i', 'application-default-icon',
                title,
                message
            ])
        except:
            pass  # Notifications are optional
    
    def quit_app(self, widget):
        """Quit the controller app"""
        Gtk.main_quit()

def main():
    controller = DashboardController()
    Gtk.main()

if __name__ == '__main__':
    main()
