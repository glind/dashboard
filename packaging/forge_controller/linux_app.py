#!/usr/bin/env python3
"""
Buildly Forge Controller - Linux System Tray Version
Uses GTK3 and AppIndicator for system tray integration
"""

import sys
import subprocess
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import gi
    gi.require_version('Gtk', '3.0')
    from gi.repository import Gtk, GLib
    HAS_GTK = True
except (ImportError, ValueError):
    HAS_GTK = False
    print("Error: GTK3 is required. Install with: sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-3.0")

try:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3
    HAS_APPINDICATOR = True
except (ImportError, ValueError):
    HAS_APPINDICATOR = False
    print("Warning: AppIndicator not available. Install with: sudo apt install gir1.2-appindicator3-0.1")

from forge_controller.core import (
    ForgeControllerBase, ForgeService, ForgeServiceScanner,
    ServiceStatus, get_platform
)


class LinuxForgeController(ForgeControllerBase):
    """Linux System Tray implementation of Forge Controller"""
    
    def __init__(self):
        super().__init__()
        
        # Find icon if available
        self.icon_path = Path(__file__).parent / "forge-logo.png"
        
        if HAS_APPINDICATOR:
            # Create AppIndicator for system tray
            self.indicator = AppIndicator3.Indicator.new(
                "forge-controller",
                "network-offline" if not self.icon_path.exists() else str(self.icon_path),
                AppIndicator3.IndicatorCategory.APPLICATION_STATUS
            )
            self.indicator.set_status(AppIndicator3.IndicatorStatus.ACTIVE)
        else:
            self.indicator = None
        
        # Build initial menu
        self._build_menu()
        
        # Set up timer for status updates
        GLib.timeout_add_seconds(self.refresh_interval, self._on_timer)
        
    def _build_menu(self):
        """Build the system tray menu"""
        menu = Gtk.Menu()
        services = self.get_services()
        
        if not services:
            # No services detected
            status_item = Gtk.MenuItem(label="No Forge services detected")
            status_item.set_sensitive(False)
            menu.append(status_item)
            
            scan_item = Gtk.MenuItem(label="Scanning ports 8000-9000...")
            scan_item.set_sensitive(False)
            menu.append(scan_item)
            
            if self.indicator:
                self.indicator.set_icon("network-offline")
        else:
            # Update icon based on running services
            running_count = sum(1 for s in services if s.status == ServiceStatus.RUNNING)
            if running_count > 0 and self.indicator:
                self.indicator.set_icon("network-transmit-receive")
            elif self.indicator:
                self.indicator.set_icon("network-idle")
            
            # Add each service
            for service in services:
                self._add_service_menu(menu, service)
        
        # Separator
        menu.append(Gtk.SeparatorMenuItem())
        
        # Refresh button
        refresh_item = Gtk.MenuItem(label="🔄 Refresh Services")
        refresh_item.connect('activate', self._on_refresh)
        menu.append(refresh_item)
        
        # Separator
        menu.append(Gtk.SeparatorMenuItem())
        
        # Quit button
        quit_item = Gtk.MenuItem(label="❌ Quit Forge Controller")
        quit_item.connect('activate', self._on_quit)
        menu.append(quit_item)
        
        menu.show_all()
        
        if self.indicator:
            self.indicator.set_menu(menu)
        
        self.menu = menu
    
    def _add_service_menu(self, menu, service: ForgeService):
        """Add a service to the menu"""
        # Status indicator
        if service.status == ServiceStatus.RUNNING:
            status_icon = "✅"
        elif service.status == ServiceStatus.STARTING:
            status_icon = "⏳"
        else:
            status_icon = "⭕"
        
        # Create submenu for this service
        service_item = Gtk.MenuItem(label=f"{status_icon} {service.name} (:{service.port})")
        submenu = Gtk.Menu()
        
        # Status info
        status_text = f"Status: {service.status.value}"
        if service.pid:
            status_text += f" (PID: {service.pid})"
        status_item = Gtk.MenuItem(label=status_text)
        status_item.set_sensitive(False)
        submenu.append(status_item)
        
        if service.version:
            version_item = Gtk.MenuItem(label=f"Version: {service.version}")
            version_item.set_sensitive(False)
            submenu.append(version_item)
        
        submenu.append(Gtk.SeparatorMenuItem())
        
        # Actions based on status
        if service.status == ServiceStatus.RUNNING:
            open_item = Gtk.MenuItem(label="🌐 Open in Browser")
            open_item.connect('activate', lambda w, p=service.port: self._open_browser(p))
            submenu.append(open_item)
            
            stop_item = Gtk.MenuItem(label="⏹️ Stop Service")
            stop_item.connect('activate', lambda w, p=service.port: self._stop_service(p))
            submenu.append(stop_item)
            
            # Option to save non-Forge services
            if not service.is_forge_service and not service.saved_by_user:
                submenu.append(Gtk.SeparatorMenuItem())
                save_item = Gtk.MenuItem(label="💾 Save Service")
                save_item.connect('activate', lambda w, p=service.port: self._save_service(p))
                submenu.append(save_item)
                
        elif service.status == ServiceStatus.STARTING:
            starting_item = Gtk.MenuItem(label="Starting...")
            starting_item.set_sensitive(False)
            submenu.append(starting_item)
        else:
            # Stopped service
            stopped_item = Gtk.MenuItem(label="Service stopped")
            stopped_item.set_sensitive(False)
            submenu.append(stopped_item)
            
            # Remove option
            submenu.append(Gtk.SeparatorMenuItem())
            remove_item = Gtk.MenuItem(label="🗑️ Remove from List")
            remove_item.connect('activate', lambda w, p=service.port: self._remove_service(p))
            submenu.append(remove_item)
        
        service_item.set_submenu(submenu)
        menu.append(service_item)
    
    def _on_timer(self):
        """Timer callback for periodic updates"""
        self.scanner.scan_services()
        self._build_menu()
        return True  # Continue timer
    
    def _on_refresh(self, widget):
        """Manual refresh button callback"""
        self.scanner.scan_services(force=True)
        self._build_menu()
        self._show_notification("Services Refreshed", f"Found {len(self.scanner._services)} service(s)")
    
    def _open_browser(self, port: int):
        """Open service in browser"""
        service = self.scanner.get_service(port)
        if service:
            subprocess.Popen(['xdg-open', service.base_url])
    
    def _stop_service(self, port: int):
        """Stop a service"""
        service = self.scanner.get_service(port)
        if service:
            name = service.name
            if self.scanner.stop_service(port):
                self._show_notification("Service Stopped", f"{name} has been stopped")
                self._build_menu()
            else:
                self._show_notification("Error", f"Failed to stop {name}")
    
    def _save_service(self, port: int):
        """Save a service to persist it"""
        service = self.scanner.get_service(port)
        if service:
            if self.scanner.save_service(port):
                self._show_notification("Service Saved", f"{service.name} will be remembered")
                self._build_menu()
    
    def _remove_service(self, port: int):
        """Remove a stopped service from the list"""
        service = self.scanner.get_service(port)
        if service:
            name = service.name
            if self.scanner.remove_service(port):
                self._show_notification("Service Removed", f"{name} removed from list")
                self._build_menu()
            else:
                self._show_notification("Error", "Cannot remove running service")
    
    def _show_notification(self, title: str, message: str):
        """Show desktop notification"""
        try:
            subprocess.Popen([
                'notify-send',
                '-i', 'application-default-icon',
                f"Forge Controller: {title}",
                message
            ])
        except Exception:
            pass  # Notifications are optional
    
    def _on_quit(self, widget):
        """Quit the application"""
        Gtk.main_quit()
    
    def update_ui(self):
        """Update UI - called from GLib main loop"""
        GLib.idle_add(self._build_menu)
    
    def show_notification(self, title: str, message: str):
        """Show notification"""
        self._show_notification(title, message)
    
    def run(self):
        """Start the application"""
        Gtk.main()


class LinuxWindowController(ForgeControllerBase):
    """Linux Window-based implementation (fallback when AppIndicator unavailable)"""
    
    def __init__(self):
        super().__init__()
        
        # Create main window
        self.window = Gtk.Window(title="Buildly Forge Controller")
        self.window.set_default_size(400, 300)
        self.window.connect('destroy', Gtk.main_quit)
        
        # Main container
        self.vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.vbox.set_margin_top(10)
        self.vbox.set_margin_bottom(10)
        self.vbox.set_margin_start(10)
        self.vbox.set_margin_end(10)
        self.window.add(self.vbox)
        
        # Title
        title_label = Gtk.Label()
        title_label.set_markup("<b>Buildly Forge Services</b>")
        self.vbox.pack_start(title_label, False, False, 0)
        
        # Scrolled window for services
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.vbox.pack_start(scrolled, True, True, 0)
        
        # Services list
        self.services_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        scrolled.add(self.services_box)
        
        # Buttons
        button_box = Gtk.Box(spacing=6)
        self.vbox.pack_start(button_box, False, False, 0)
        
        refresh_btn = Gtk.Button(label="Refresh")
        refresh_btn.connect('clicked', self._on_refresh)
        button_box.pack_start(refresh_btn, True, True, 0)
        
        quit_btn = Gtk.Button(label="Quit")
        quit_btn.connect('clicked', lambda w: Gtk.main_quit())
        button_box.pack_start(quit_btn, True, True, 0)
        
        # Initial update
        self._update_services()
        
        # Set up timer
        GLib.timeout_add_seconds(self.refresh_interval, self._on_timer)
        
        self.window.show_all()
    
    def _update_services(self):
        """Update the services list"""
        # Clear existing
        for child in self.services_box.get_children():
            self.services_box.remove(child)
        
        services = self.get_services()
        
        if not services:
            label = Gtk.Label(label="No Forge services detected\nScanning ports 8000-9000...")
            self.services_box.pack_start(label, False, False, 10)
        else:
            for service in services:
                self._add_service_widget(service)
        
        self.services_box.show_all()
    
    def _add_service_widget(self, service: ForgeService):
        """Add a service widget"""
        frame = Gtk.Frame()
        frame.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        frame.add(box)
        
        # Status indicator
        if service.status == ServiceStatus.RUNNING:
            status_icon = "✅"
        elif service.status == ServiceStatus.STARTING:
            status_icon = "⏳"
        else:
            status_icon = "⭕"
        
        # Service name
        name_label = Gtk.Label()
        name_label.set_markup(f"<b>{status_icon} {service.name}</b>")
        name_label.set_halign(Gtk.Align.START)
        box.pack_start(name_label, False, False, 0)
        
        # Port and status
        info_label = Gtk.Label(label=f"Port: {service.port} | Status: {service.status.value}")
        info_label.set_halign(Gtk.Align.START)
        box.pack_start(info_label, False, False, 0)
        
        if service.pid:
            pid_label = Gtk.Label(label=f"PID: {service.pid}")
            pid_label.set_halign(Gtk.Align.START)
            box.pack_start(pid_label, False, False, 0)
        
        # Buttons
        btn_box = Gtk.Box(spacing=6)
        box.pack_start(btn_box, False, False, 4)
        
        if service.status == ServiceStatus.RUNNING:
            open_btn = Gtk.Button(label="🌐 Open")
            open_btn.connect('clicked', lambda w, p=service.port: self._open_browser(p))
            btn_box.pack_start(open_btn, False, False, 0)
            
            stop_btn = Gtk.Button(label="⏹️ Stop")
            stop_btn.connect('clicked', lambda w, p=service.port: self._stop_service(p))
            btn_box.pack_start(stop_btn, False, False, 0)
        
        self.services_box.pack_start(frame, False, False, 0)
    
    def _on_timer(self):
        """Timer callback"""
        self.scanner.scan_services()
        self._update_services()
        return True
    
    def _on_refresh(self, widget):
        """Refresh button callback"""
        self.scanner.scan_services(force=True)
        self._update_services()
    
    def _open_browser(self, port: int):
        """Open in browser"""
        service = self.scanner.get_service(port)
        if service:
            subprocess.Popen(['xdg-open', service.base_url])
    
    def _stop_service(self, port: int):
        """Stop service"""
        service = self.scanner.get_service(port)
        if service:
            self.scanner.stop_service(port)
            self._update_services()
    
    def run(self):
        """Run the application"""
        Gtk.main()


def main():
    """Entry point for Linux version"""
    if get_platform() != 'linux':
        print("This script is for Linux only. Use the appropriate script for your platform.")
        sys.exit(1)
    
    if not HAS_GTK:
        print("GTK3 is required but not available.")
        sys.exit(1)
    
    try:
        if HAS_APPINDICATOR:
            controller = LinuxForgeController()
        else:
            print("AppIndicator not available, using window mode")
            controller = LinuxWindowController()
        controller.run()
    except Exception as e:
        print(f"Error starting Forge Controller: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()
