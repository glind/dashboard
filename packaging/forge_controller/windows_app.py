#!/usr/bin/env python3
"""
Buildly Forge Controller - Windows System Tray Version
Uses PyQt5 for system tray integration
"""

import sys
import subprocess
import webbrowser
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from PyQt5.QtWidgets import (
        QApplication, QSystemTrayIcon, QMenu, QAction, 
        QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QScrollArea, QFrame, QMessageBox
    )
    from PyQt5.QtCore import QTimer, Qt
    from PyQt5.QtGui import QIcon
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False
    print("Error: PyQt5 is required. Install with: pip install PyQt5")

from forge_controller.core import (
    ForgeControllerBase, ForgeService, ForgeServiceScanner,
    ServiceStatus, get_platform
)


class WindowsForgeController(ForgeControllerBase):
    """Windows System Tray implementation of Forge Controller"""
    
    def __init__(self):
        super().__init__()
        
        self.app = QApplication(sys.argv)
        self.app.setQuitOnLastWindowClosed(False)
        
        # Find icon if available
        self.icon_path = Path(__file__).parent / "forge-logo.png"
        
        # Create system tray icon
        self.tray_icon = QSystemTrayIcon(self.app)
        self.tray_icon.setToolTip("Buildly Forge Controller")
        
        if self.icon_path.exists():
            self.tray_icon.setIcon(QIcon(str(self.icon_path)))
        
        # Build initial menu
        self._build_menu()
        
        # Show tray icon
        self.tray_icon.show()
        
        # Set up timer for status updates
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(self.refresh_interval * 1000)
        
    def _build_menu(self):
        """Build the system tray menu"""
        menu = QMenu()
        services = self.get_services()
        
        if not services:
            # No services detected
            status_action = QAction("No Forge services detected", self.app)
            status_action.setEnabled(False)
            menu.addAction(status_action)
            
            scan_action = QAction("Scanning ports 8000-9000...", self.app)
            scan_action.setEnabled(False)
            menu.addAction(scan_action)
        else:
            # Add each service
            for service in services:
                self._add_service_menu(menu, service)
        
        menu.addSeparator()
        
        # Refresh button
        refresh_action = QAction("🔄 Refresh Services", self.app)
        refresh_action.triggered.connect(self._on_refresh)
        menu.addAction(refresh_action)
        
        menu.addSeparator()
        
        # Quit button
        quit_action = QAction("❌ Quit Forge Controller", self.app)
        quit_action.triggered.connect(self._on_quit)
        menu.addAction(quit_action)
        
        self.tray_icon.setContextMenu(menu)
        self.menu = menu
    
    def _add_service_menu(self, menu, service: ForgeService):
        """Add a service submenu"""
        # Status indicator
        if service.status == ServiceStatus.RUNNING:
            status_icon = "✅"
        elif service.status == ServiceStatus.STARTING:
            status_icon = "⏳"
        else:
            status_icon = "⭕"
        
        # Create submenu for this service
        service_menu = QMenu(f"{status_icon} {service.name} (:{service.port})", menu)
        
        # Status info
        status_text = f"Status: {service.status.value}"
        if service.pid:
            status_text += f" (PID: {service.pid})"
        status_action = QAction(status_text, self.app)
        status_action.setEnabled(False)
        service_menu.addAction(status_action)
        
        if service.version:
            version_action = QAction(f"Version: {service.version}", self.app)
            version_action.setEnabled(False)
            service_menu.addAction(version_action)
        
        service_menu.addSeparator()
        
        # Actions based on status
        if service.status == ServiceStatus.RUNNING:
            open_action = QAction("🌐 Open in Browser", self.app)
            open_action.triggered.connect(lambda checked, p=service.port: self._open_browser(p))
            service_menu.addAction(open_action)
            
            stop_action = QAction("⏹️ Stop Service", self.app)
            stop_action.triggered.connect(lambda checked, p=service.port: self._stop_service(p))
            service_menu.addAction(stop_action)
            
            # Option to save non-Forge services
            if not service.is_forge_service and not service.saved_by_user:
                service_menu.addSeparator()
                save_action = QAction("💾 Save Service", self.app)
                save_action.triggered.connect(lambda checked, p=service.port: self._save_service(p))
                service_menu.addAction(save_action)
                
        elif service.status == ServiceStatus.STARTING:
            starting_action = QAction("Starting...", self.app)
            starting_action.setEnabled(False)
            service_menu.addAction(starting_action)
        else:
            # Stopped service
            stopped_action = QAction("Service stopped", self.app)
            stopped_action.setEnabled(False)
            service_menu.addAction(stopped_action)
            
            # Remove option
            service_menu.addSeparator()
            remove_action = QAction("🗑️ Remove from List", self.app)
            remove_action.triggered.connect(lambda checked, p=service.port: self._remove_service(p))
            service_menu.addAction(remove_action)
        
        menu.addMenu(service_menu)
    
    def _on_timer(self):
        """Timer callback for periodic updates"""
        self.scanner.scan_services()
        self._build_menu()
    
    def _on_refresh(self):
        """Manual refresh button callback"""
        self.scanner.scan_services(force=True)
        self._build_menu()
        self.tray_icon.showMessage(
            "Forge Controller",
            f"Found {len(self.scanner._services)} service(s)",
            QSystemTrayIcon.Information,
            2000
        )
    
    def _open_browser(self, port: int):
        """Open service in browser"""
        service = self.scanner.get_service(port)
        if service:
            webbrowser.open(service.base_url)
    
    def _stop_service(self, port: int):
        """Stop a service"""
        service = self.scanner.get_service(port)
        if service:
            name = service.name
            if self.scanner.stop_service(port):
                self.tray_icon.showMessage(
                    "Forge Controller",
                    f"{name} has been stopped",
                    QSystemTrayIcon.Information,
                    2000
                )
                self._build_menu()
            else:
                self.tray_icon.showMessage(
                    "Forge Controller",
                    f"Failed to stop {name}",
                    QSystemTrayIcon.Warning,
                    2000
                )
    
    def _save_service(self, port: int):
        """Save a service to persist it"""
        service = self.scanner.get_service(port)
        if service:
            if self.scanner.save_service(port):
                self.tray_icon.showMessage(
                    "Forge Controller",
                    f"{service.name} will be remembered",
                    QSystemTrayIcon.Information,
                    2000
                )
                self._build_menu()
    
    def _remove_service(self, port: int):
        """Remove a stopped service from the list"""
        service = self.scanner.get_service(port)
        if service:
            name = service.name
            if self.scanner.remove_service(port):
                self.tray_icon.showMessage(
                    "Forge Controller",
                    f"{name} removed from list",
                    QSystemTrayIcon.Information,
                    2000
                )
                self._build_menu()
            else:
                self.tray_icon.showMessage(
                    "Forge Controller",
                    "Cannot remove running service",
                    QSystemTrayIcon.Warning,
                    2000
                )
    
    def _on_quit(self):
        """Quit the application"""
        self.app.quit()
    
    def update_ui(self):
        """Update UI"""
        self._build_menu()
    
    def show_notification(self, title: str, message: str):
        """Show Windows notification"""
        self.tray_icon.showMessage(
            "Forge Controller",
            f"{title}: {message}",
            QSystemTrayIcon.Information,
            2000
        )
    
    def run(self):
        """Start the application"""
        sys.exit(self.app.exec_())


class WindowsWindowController(ForgeControllerBase):
    """Windows Window-based implementation (alternative to system tray)"""
    
    def __init__(self):
        super().__init__()
        
        self.app = QApplication(sys.argv)
        
        # Create main window
        self.window = QMainWindow()
        self.window.setWindowTitle("Buildly Forge Controller")
        self.window.setMinimumSize(450, 350)
        
        # Central widget
        central = QWidget()
        self.window.setCentralWidget(central)
        
        layout = QVBoxLayout(central)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Title
        title = QLabel("<h2>Buildly Forge Services</h2>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        # Scroll area for services
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        layout.addWidget(scroll)
        
        self.services_widget = QWidget()
        self.services_layout = QVBoxLayout(self.services_widget)
        self.services_layout.setAlignment(Qt.AlignTop)
        scroll.setWidget(self.services_widget)
        
        # Buttons
        btn_layout = QHBoxLayout()
        layout.addLayout(btn_layout)
        
        refresh_btn = QPushButton("🔄 Refresh")
        refresh_btn.clicked.connect(self._on_refresh)
        btn_layout.addWidget(refresh_btn)
        
        quit_btn = QPushButton("❌ Quit")
        quit_btn.clicked.connect(self.app.quit)
        btn_layout.addWidget(quit_btn)
        
        # Initial update
        self._update_services()
        
        # Set up timer
        self.timer = QTimer()
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(self.refresh_interval * 1000)
        
        self.window.show()
    
    def _update_services(self):
        """Update the services list"""
        # Clear existing
        while self.services_layout.count():
            item = self.services_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        services = self.get_services()
        
        if not services:
            label = QLabel("No Forge services detected\nScanning ports 8000-9000...")
            label.setAlignment(Qt.AlignCenter)
            self.services_layout.addWidget(label)
        else:
            for service in services:
                self._add_service_widget(service)
    
    def _add_service_widget(self, service: ForgeService):
        """Add a service widget"""
        frame = QFrame()
        frame.setFrameShape(QFrame.StyledPanel)
        frame.setStyleSheet("QFrame { background: #f5f5f5; border-radius: 5px; padding: 8px; }")
        
        layout = QVBoxLayout(frame)
        layout.setSpacing(4)
        
        # Status indicator
        if service.status == ServiceStatus.RUNNING:
            status_icon = "✅"
        elif service.status == ServiceStatus.STARTING:
            status_icon = "⏳"
        else:
            status_icon = "⭕"
        
        # Service name
        name_label = QLabel(f"<b>{status_icon} {service.name}</b>")
        layout.addWidget(name_label)
        
        # Port and status
        info_label = QLabel(f"Port: {service.port} | Status: {service.status.value}")
        layout.addWidget(info_label)
        
        if service.pid:
            pid_label = QLabel(f"PID: {service.pid}")
            layout.addWidget(pid_label)
        
        # Buttons
        btn_layout = QHBoxLayout()
        layout.addLayout(btn_layout)
        
        if service.status == ServiceStatus.RUNNING:
            open_btn = QPushButton("🌐 Open")
            open_btn.clicked.connect(lambda checked, p=service.port: self._open_browser(p))
            btn_layout.addWidget(open_btn)
            
            stop_btn = QPushButton("⏹️ Stop")
            stop_btn.clicked.connect(lambda checked, p=service.port: self._stop_service(p))
            btn_layout.addWidget(stop_btn)
        
        btn_layout.addStretch()
        
        self.services_layout.addWidget(frame)
    
    def _on_timer(self):
        """Timer callback"""
        self.scanner.scan_services()
        self._update_services()
    
    def _on_refresh(self):
        """Refresh button callback"""
        self.scanner.scan_services(force=True)
        self._update_services()
    
    def _open_browser(self, port: int):
        """Open in browser"""
        service = self.scanner.get_service(port)
        if service:
            webbrowser.open(service.base_url)
    
    def _stop_service(self, port: int):
        """Stop service"""
        service = self.scanner.get_service(port)
        if service:
            self.scanner.stop_service(port)
            self._update_services()
    
    def run(self):
        """Run the application"""
        sys.exit(self.app.exec_())


def main():
    """Entry point for Windows version"""
    if not HAS_PYQT:
        print("PyQt5 is required but not available.")
        sys.exit(1)
    
    try:
        # Try system tray first, fall back to window
        controller = WindowsForgeController()
        controller.run()
    except Exception as e:
        print(f"Error with system tray, trying window mode: {e}")
        try:
            controller = WindowsWindowController()
            controller.run()
        except Exception as e2:
            print(f"Error starting Forge Controller: {e2}")
            import traceback
            traceback.print_exc()
            sys.exit(1)


if __name__ == '__main__':
    main()
