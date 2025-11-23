#!/usr/bin/env python3
"""
Dashboard Control App - Simple GTK Window Version
A simple window-based application to control the Personal Dashboard server
(Alternative to system tray version - works on all desktop environments)
"""

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib
import subprocess
import os
import signal
import requests
from pathlib import Path

class DashboardWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="Dashboard Controller")
        
        self.dashboard_dir = Path(__file__).parent.absolute()
        self.startup_script = self.dashboard_dir / "ops" / "startup.sh"
        self.pid_file = self.dashboard_dir / "dashboard.pid"
        
        self.set_border_width(10)
        self.set_default_size(400, 300)
        self.set_position(Gtk.WindowPosition.CENTER)
        
        # Create main box
        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.add(vbox)
        
        # Status label
        self.status_label = Gtk.Label()
        self.status_label.set_markup("<big><b>Server Status: Checking...</b></big>")
        vbox.pack_start(self.status_label, False, False, 10)
        
        # PID label
        self.pid_label = Gtk.Label()
        self.pid_label.set_text("")
        vbox.pack_start(self.pid_label, False, False, 0)
        
        # URL label
        url_label = Gtk.Label()
        url_label.set_markup('<a href="http://localhost:8008">http://localhost:8008</a>')
        vbox.pack_start(url_label, False, False, 0)
        
        # Separator
        separator = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        vbox.pack_start(separator, False, False, 10)
        
        # Buttons box
        button_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=5)
        vbox.pack_start(button_box, True, True, 0)
        
        # Start button
        self.start_btn = Gtk.Button(label="▶️ Start Server")
        self.start_btn.connect("clicked", self.on_start_clicked)
        button_box.pack_start(self.start_btn, False, False, 0)
        
        # Restart button
        self.restart_btn = Gtk.Button(label="🔄 Restart Server")
        self.restart_btn.connect("clicked", self.on_restart_clicked)
        button_box.pack_start(self.restart_btn, False, False, 0)
        
        # Stop button
        self.stop_btn = Gtk.Button(label="⏹️ Stop Server")
        self.stop_btn.connect("clicked", self.on_stop_clicked)
        button_box.pack_start(self.stop_btn, False, False, 0)
        
        # Separator
        separator2 = Gtk.Separator(orientation=Gtk.Orientation.HORIZONTAL)
        button_box.pack_start(separator2, False, False, 5)
        
        # Open browser button
        self.open_btn = Gtk.Button(label="🌐 Open in Browser")
        self.open_btn.connect("clicked", self.on_open_clicked)
        button_box.pack_start(self.open_btn, False, False, 0)
        
        # View logs button
        logs_btn = Gtk.Button(label="📋 View Logs")
        logs_btn.connect("clicked", self.on_logs_clicked)
        button_box.pack_start(logs_btn, False, False, 0)
        
        # Start status update timer
        GLib.timeout_add_seconds(3, self.update_status)
        self.update_status()
    
    def get_server_status(self):
        """Check if server is running"""
        try:
            if self.pid_file.exists():
                with open(self.pid_file, 'r') as f:
                    pid = int(f.read().strip())
                
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
            return 'unknown', None
    
    def update_status(self):
        """Update status display"""
        status, pid = self.get_server_status()
        
        if status == 'running':
            self.status_label.set_markup("<big><b>✅ Server Running</b></big>")
            self.pid_label.set_text(f"Process ID: {pid}")
            self.start_btn.set_sensitive(False)
            self.restart_btn.set_sensitive(True)
            self.stop_btn.set_sensitive(True)
            self.open_btn.set_sensitive(True)
        elif status == 'starting':
            self.status_label.set_markup("<big><b>⏳ Server Starting...</b></big>")
            self.pid_label.set_text(f"Process ID: {pid}")
            self.start_btn.set_sensitive(False)
            self.restart_btn.set_sensitive(True)
            self.stop_btn.set_sensitive(True)
            self.open_btn.set_sensitive(False)
        else:
            self.status_label.set_markup("<big><b>⭕ Server Stopped</b></big>")
            self.pid_label.set_text("")
            self.start_btn.set_sensitive(True)
            self.restart_btn.set_sensitive(False)
            self.stop_btn.set_sensitive(False)
            self.open_btn.set_sensitive(False)
        
        return True
    
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
    
    def on_start_clicked(self, widget):
        """Start server"""
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
        except Exception as e:
            self.show_error(f"Failed to start server: {e}")
    
    def on_restart_clicked(self, widget):
        """Restart server"""
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
        except Exception as e:
            self.show_error(f"Failed to restart server: {e}")
    
    def on_stop_clicked(self, widget):
        """Stop server"""
        try:
            subprocess.Popen(
                [str(self.startup_script), 'stop'],
                cwd=str(self.dashboard_dir),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            GLib.timeout_add(2000, self.update_status)
        except Exception as e:
            self.show_error(f"Failed to stop server: {e}")
    
    def on_open_clicked(self, widget):
        """Open in browser"""
        try:
            subprocess.Popen(['xdg-open', 'http://localhost:8008'])
        except Exception as e:
            self.show_error(f"Failed to open browser: {e}")
    
    def on_logs_clicked(self, widget):
        """View logs"""
        try:
            log_file = self.dashboard_dir / "dashboard.log"
            terminals = [
                ['gnome-terminal', '--', 'tail', '-f', str(log_file)],
                ['konsole', '-e', 'tail', '-f', str(log_file)],
                ['xterm', '-e', 'tail', '-f', str(log_file)],
            ]
            
            for terminal_cmd in terminals:
                try:
                    subprocess.Popen(terminal_cmd)
                    return
                except FileNotFoundError:
                    continue
            
            self.show_error("No terminal emulator found")
        except Exception as e:
            self.show_error(f"Failed to open logs: {e}")
    
    def show_error(self, message):
        """Show error dialog"""
        dialog = Gtk.MessageDialog(
            transient_for=self,
            flags=0,
            message_type=Gtk.MessageType.ERROR,
            buttons=Gtk.ButtonsType.OK,
            text="Error",
        )
        dialog.format_secondary_text(message)
        dialog.run()
        dialog.destroy()

def main():
    win = DashboardWindow()
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    Gtk.main()

if __name__ == '__main__':
    main()
