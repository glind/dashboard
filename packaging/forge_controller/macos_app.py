#!/usr/bin/env python3
"""
Buildly Forge Controller - macOS Menu Bar Version
Uses rumps for native macOS menu bar integration
"""

import os
import sys
import subprocess
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import rumps
except ImportError:
    print("Error: 'rumps' is required for macOS. Install with: pip3 install rumps")
    sys.exit(1)

from forge_controller.core import (
    ForgeControllerBase, ForgeService, ForgeServiceScanner, 
    ServiceStatus, get_platform
)


class MacOSForgeController(ForgeControllerBase):
    """macOS Menu Bar implementation of Forge Controller"""
    
    def __init__(self):
        super().__init__()
        
        # Hide from dock - menu bar only app
        try:
            import AppKit
            AppKit.NSApp.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)
        except:
            pass  # If AppKit not available, continue anyway
        
        # Find icon if available
        self.icon_path = Path(__file__).parent / "forge-logo.png"
        
        # Create the rumps app
        self.app = rumps.App(
            "Forge",
            icon=str(self.icon_path) if self.icon_path.exists() else None,
            quit_button=None  # We'll add our own quit button
        )
        
        # Initial menu setup
        self._build_menu()
        
        # Set up timer for status updates
        self.timer = rumps.Timer(self._on_timer, self.refresh_interval)
        self.timer.start()
        
    def _build_menu(self):
        """Build the menu bar menu"""
        services = self.get_services()
        
        # Clear existing menu
        self.app.menu.clear()
        
        if not services:
            # No services detected
            self.app.title = "⭕"
            self.app.menu.add(rumps.MenuItem("No Forge services detected", callback=None))
            self.app.menu.add(rumps.MenuItem("Scanning ports 8000-9000...", callback=None))
        else:
            # Show running services count
            running_count = sum(1 for s in services if s.status == ServiceStatus.RUNNING)
            if running_count > 0:
                self.app.title = f"✅ {running_count}"
            else:
                self.app.title = "⏳"
            
            # Add each service
            for service in services:
                self._add_service_menu(service)
        
        # Separator before global actions
        self.app.menu.add(None)
        
        # Refresh button
        refresh_item = rumps.MenuItem("🔄 Refresh", callback=self._on_refresh)
        self.app.menu.add(refresh_item)
        
        # Separator before quit
        self.app.menu.add(None)
        
        # Quit button
        quit_item = rumps.MenuItem("Quit Forge Controller", callback=self._on_quit)
        self.app.menu.add(quit_item)
    
    def _add_service_menu(self, service: ForgeService):
        """Add a service submenu"""
        # Status indicator
        if service.status == ServiceStatus.RUNNING:
            status_icon = "✅"
        elif service.status == ServiceStatus.STARTING:
            status_icon = "⏳"
        else:
            status_icon = "⭕"
        
        # Create submenu for this service
        service_menu = rumps.MenuItem(f"{status_icon} {service.name} (:{service.port})")
        
        # Status info
        status_text = f"Status: {service.status.value}"
        if service.pid:
            status_text += f" (PID: {service.pid})"
        service_menu.add(rumps.MenuItem(status_text, callback=None))
        
        if service.version:
            service_menu.add(rumps.MenuItem(f"Version: {service.version}", callback=None))
        
        service_menu.add(None)  # Separator
        
        # Actions based on status
        if service.status == ServiceStatus.RUNNING:
            open_item = rumps.MenuItem(
                "🌐 Open in Browser",
                callback=lambda _, p=service.port: self._open_browser(p)
            )
            service_menu.add(open_item)
            
            stop_item = rumps.MenuItem(
                "⏹️ Stop Service",
                callback=lambda _, p=service.port: self._stop_service(p)
            )
            service_menu.add(stop_item)
            
            restart_item = rumps.MenuItem(
                "🔄 Restart Service",
                callback=lambda _, p=service.port: self._restart_service(p)
            )
            service_menu.add(restart_item)
            
            # Option to save non-Forge services
            if not service.is_forge_service and not service.saved_by_user:
                service_menu.add(None)  # Separator
                save_item = rumps.MenuItem(
                    "💾 Save Service",
                    callback=lambda _, p=service.port: self._save_service(p)
                )
                service_menu.add(save_item)
                
        elif service.status == ServiceStatus.STARTING:
            service_menu.add(rumps.MenuItem("Starting...", callback=None))
        else:
            # Stopped service
            service_menu.add(rumps.MenuItem("Service stopped", callback=None))
            
            # Add start option for stopped services if we know how to start it
            service_menu.add(None)  # Separator
            start_item = rumps.MenuItem(
                "▶️ Start Service",
                callback=lambda _, p=service.port: self._start_service(p)
            )
            service_menu.add(start_item)
            
            # Add remove option for stopped services
            remove_item = rumps.MenuItem(
                "🗑️ Remove from List",
                callback=lambda _, p=service.port: self._remove_service(p)
            )
            service_menu.add(remove_item)
        
        self.app.menu.add(service_menu)
    
    def _on_timer(self, sender):
        """Timer callback for periodic updates"""
        self._build_menu()
    
    def _on_refresh(self, sender):
        """Manual refresh button callback"""
        self.scanner.scan_services(force=True)
        self._build_menu()
        rumps.notification(
            "Forge Controller",
            "Services Refreshed",
            f"Found {len(self.scanner._services)} service(s)"
        )
    
    def _open_browser(self, port: int):
        """Open service in browser"""
        service = self.scanner.get_service(port)
        if service:
            subprocess.run(['open', service.base_url])
    
    def _start_service(self, port: int):
        """Start a service"""
        service = self.scanner.get_service(port)
        
        if not service:
            return
        
        # Check if we have a known start script
        if service.start_script and os.path.exists(service.start_script):
            # Execute the startup script
            script_dir = os.path.dirname(service.start_script)
            script_name = os.path.basename(service.start_script)
            
            applescript = f'''
tell application "Terminal"
    activate
    do script "cd '{script_dir}' && echo '=== Starting {service.name} ===' && ./{script_name}"
end tell
'''
            subprocess.run(['osascript', '-e', applescript])
            
            # Show notification
            rumps.notification(
                "Forge Controller",
                "Starting Service",
                f"Running {script_name} for {service.name}"
            )
            return
        
        # No start script - open Terminal in working directory
        start_dir = service.working_dir or os.path.expanduser("~/Projects/me/dashboard/src")
        
        # Fallback to common locations if working_dir not set
        if not service.working_dir:
            project_paths = [
                "~/Projects/me/dashboard/src",
                "~/Projects/me/dashboard",
                "~/dashboard/src",
                "~/dashboard",
            ]
            for path in project_paths:
                expanded = os.path.expanduser(path)
                if os.path.exists(expanded):
                    start_dir = expanded
                    break
        
        service_name = service.custom_name or service.name
        
        # Open Terminal with instructions
        applescript = f'''
tell application "Terminal"
    activate
    do script "cd '{start_dir}' && echo '=== Start {service_name} ===' && echo 'No ops/startup.sh found.' && echo 'Run your start command here (e.g., python manage.py runserver {port})' && echo '' && pwd"
end tell
'''
        subprocess.run(['osascript', '-e', applescript])
    
    def _restart_service(self, port: int):
        """Restart a service"""
        service = self.scanner.get_service(port)
        if service:
            # Stop first
            if self._stop_service(port):
                rumps.notification(
                    "Forge Controller",
                    "Service Restarted",
                    f"Service on port {port} stopped.\nPlease restart it manually from its directory."
                )
    
    def _stop_service(self, port: int):
        """Stop a service"""
        service = self.scanner.get_service(port)
        if service:
            name = service.name
            if self.scanner.stop_service(port):
                rumps.notification("Forge Controller", "Service Stopped", f"{name} has been stopped")
                self._build_menu()
            else:
                rumps.notification("Forge Controller", "Error", f"Failed to stop {name}")
    
    def _save_service(self, port: int):
        """Save a service to persist it"""
        service = self.scanner.get_service(port)
        if service:
            if self.scanner.save_service(port):
                rumps.notification("Forge Controller", "Service Saved", f"{service.name} will be remembered")
                self._build_menu()
    
    def _remove_service(self, port: int):
        """Remove a stopped service from the list"""
        service = self.scanner.get_service(port)
        if service:
            name = service.name
            if self.scanner.remove_service(port):
                rumps.notification("Forge Controller", "Service Removed", f"{name} removed from list")
                self._build_menu()
            else:
                rumps.notification("Forge Controller", "Error", f"Cannot remove running service")
    
    def _on_quit(self, sender):
        """Quit the application"""
        rumps.quit_application()
    
    def update_ui(self):
        """Update UI from background thread - schedule on main thread"""
        # rumps handles this automatically via timer
        pass
    
    def show_notification(self, title: str, message: str):
        """Show macOS notification"""
        rumps.notification("Forge Controller", title, message)
    
    def run(self):
        """Start the application"""
        self.app.run()


def main():
    """Entry point for macOS version"""
    if get_platform() != 'macos':
        print("This script is for macOS only. Use the appropriate script for your platform.")
        sys.exit(1)
    
    try:
        controller = MacOSForgeController()
        controller.run()
    except Exception as e:
        print(f"Error starting Forge Controller: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
