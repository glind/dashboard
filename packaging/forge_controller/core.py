#!/usr/bin/env python3
"""
Buildly Forge Controller - Core Module
Cross-platform service detection and management for Buildly Forge apps

This module provides the shared logic for detecting and controlling
Buildly Forge applications running on ports 8000-9000.
"""

import os
import sys
import signal
import socket
import subprocess
import webbrowser
import json
import time
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict, Tuple, Callable
from enum import Enum
import threading

# Try to import requests, fall back to urllib for basic functionality
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False
    import urllib.request
    import urllib.error


class ServiceStatus(Enum):
    """Status of a detected service"""
    RUNNING = "running"
    STARTING = "starting"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


@dataclass
class ForgeService:
    """Represents a detected Buildly Forge service"""
    port: int
    name: str
    status: ServiceStatus
    pid: Optional[int] = None
    health_endpoint: Optional[str] = None
    version: Optional[str] = None
    base_url: str = ""
    is_forge_service: bool = False  # True if confirmed as a Forge service
    saved_by_user: bool = False  # True if user explicitly saved this service
    
    def __post_init__(self):
        self.base_url = f"http://localhost:{self.port}"
    
    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization"""
        return {
            'port': self.port,
            'name': self.name,
            'health_endpoint': self.health_endpoint,
            'version': self.version,
            'is_forge_service': self.is_forge_service,
            'saved_by_user': self.saved_by_user,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'ForgeService':
        """Create from dictionary"""
        return cls(
            port=data['port'],
            name=data['name'],
            status=ServiceStatus.STOPPED,  # Will be updated on scan
            health_endpoint=data.get('health_endpoint'),
            version=data.get('version'),
            is_forge_service=data.get('is_forge_service', False),
            saved_by_user=data.get('saved_by_user', False),
        )


@dataclass 
class ServiceConfig:
    """Configuration for a service that can be started/stopped"""
    name: str
    port: int
    start_command: List[str]
    stop_command: Optional[List[str]] = None
    working_dir: Optional[str] = None
    pid_file: Optional[str] = None
    log_file: Optional[str] = None


class ForgeServiceScanner:
    """
    Scans for and manages Buildly Forge services on ports 8000-9000.
    
    This class provides cross-platform functionality to:
    - Detect running services on specified ports
    - Identify service names via health endpoints
    - Start/stop/restart services
    - Monitor service health
    """
    
    # Port range for Buildly Forge apps
    PORT_RANGE_START = 8000
    PORT_RANGE_END = 9000
    
    # Common Forge service indicators
    HEALTH_ENDPOINTS = [
        '/api/health',
        '/health',
        '/api/v1/health',
        '/_health',
        '/status',
        '/api/status',
    ]
    
    # Common Forge app identifiers found in responses
    FORGE_IDENTIFIERS = [
        'buildly',
        'forge',
        'forgeweb',
        'dashboard',
        'gateway',
        'workflow',
        'datamesh',
        'core',
    ]
    
    def __init__(self, 
                 port_start: int = None, 
                 port_end: int = None,
                 scan_timeout: float = 0.5,
                 health_timeout: float = 2.0,
                 config_dir: Path = None):
        """
        Initialize the scanner.
        
        Args:
            port_start: Start of port range (default 8000)
            port_end: End of port range (default 9000)
            scan_timeout: Timeout for port scanning in seconds
            health_timeout: Timeout for health endpoint checks
            config_dir: Directory to store config/saved services (default ~/.forge_controller)
        """
        self.port_start = port_start or self.PORT_RANGE_START
        self.port_end = port_end or self.PORT_RANGE_END
        self.scan_timeout = scan_timeout
        self.health_timeout = health_timeout
        
        # Config directory for persistence
        self.config_dir = config_dir or Path.home() / '.forge_controller'
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.saved_services_file = self.config_dir / 'saved_services.json'
        
        # Cache of discovered services (includes both running and saved stopped services)
        self._services: Dict[int, ForgeService] = {}
        self._last_scan: float = 0
        self._scan_interval: float = 5.0  # Minimum seconds between full scans
        
        # Load saved services on startup
        self._load_saved_services()
        
        # Service configurations (can be loaded from config file)
        self._service_configs: Dict[str, ServiceConfig] = {}
        
        # Callbacks for status changes
        self._status_callbacks: List[Callable[[ForgeService], None]] = []
        
    def add_status_callback(self, callback: Callable[[ForgeService], None]):
        """Add a callback to be called when service status changes"""
        self._status_callbacks.append(callback)
        
    def _notify_status_change(self, service: ForgeService):
        """Notify all callbacks of a status change"""
        for callback in self._status_callbacks:
            try:
                callback(service)
            except Exception as e:
                print(f"Error in status callback: {e}")
    
    def _load_saved_services(self):
        """Load saved services from config file"""
        if self.saved_services_file.exists():
            try:
                with open(self.saved_services_file, 'r') as f:
                    data = json.load(f)
                    for service_data in data.get('services', []):
                        service = ForgeService.from_dict(service_data)
                        self._services[service.port] = service
                print(f"Loaded {len(self._services)} saved service(s)")
            except Exception as e:
                print(f"Error loading saved services: {e}")
    
    def _save_services(self):
        """Save Forge services and user-saved services to config file"""
        services_to_save = [
            service.to_dict() 
            for service in self._services.values()
            if service.is_forge_service or service.saved_by_user
        ]
        
        try:
            with open(self.saved_services_file, 'w') as f:
                json.dump({'services': services_to_save}, f, indent=2)
        except Exception as e:
            print(f"Error saving services: {e}")
    
    def save_service(self, port: int) -> bool:
        """
        Explicitly save a service so it persists even when stopped.
        
        Returns True if successfully saved.
        """
        if port in self._services:
            self._services[port].saved_by_user = True
            self._save_services()
            return True
        return False
    
    def remove_service(self, port: int) -> bool:
        """
        Remove a stopped service from the list.
        Only works for stopped services that aren't currently running.
        
        Returns True if successfully removed.
        """
        if port in self._services:
            service = self._services[port]
            if service.status == ServiceStatus.STOPPED:
                del self._services[port]
                self._save_services()
                return True
        return False
    
    def is_forge_service(self, service: ForgeService) -> bool:
        """
        Determine if a service is a Buildly Forge service.
        
        A service is considered a Forge service if:
        - It has a health endpoint that responded
        - Its name or response contains Forge identifiers
        """
        if service.health_endpoint:
            # Has a health endpoint - check if name contains identifiers
            name_lower = service.name.lower()
            for identifier in self.FORGE_IDENTIFIERS:
                if identifier in name_lower:
                    return True
            # If it has a health endpoint but no identifier, still consider it
            # since most random services don't have /api/health
            return True
        return False
    
    def is_port_open(self, port: int) -> bool:
        """Check if a port is open (has a service listening)"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.scan_timeout)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _http_get(self, url: str, timeout: float = None) -> Tuple[int, str]:
        """
        Make an HTTP GET request, returns (status_code, response_text).
        Works with or without requests library.
        """
        timeout = timeout or self.health_timeout
        
        if HAS_REQUESTS:
            try:
                response = requests.get(url, timeout=timeout)
                return response.status_code, response.text
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                # Connection refused or timeout - service might be websocket only
                # or incompatible protocol
                return 0, ""
            except Exception as e:
                # Any other error
                return 0, ""
        else:
            try:
                req = urllib.request.urlopen(url, timeout=timeout)
                return req.getcode(), req.read().decode('utf-8')
            except (urllib.error.URLError, urllib.error.HTTPError, Exception):
                return 0, ""
    
    def get_service_info(self, port: int, check_running: bool = True) -> Optional[ForgeService]:
        """
        Get information about a service running on a specific port.
        Attempts to identify the service via health endpoints.
        
        Args:
            port: Port number to check
            check_running: If True, only return info if port is actually open
        """
        if check_running and not self.is_port_open(port):
            return None
        
        base_url = f"http://localhost:{port}"
        service_name = f"Service on port {port}"
        health_endpoint = None
        version = None
        
        # Try each health endpoint to identify the service
        for endpoint in self.HEALTH_ENDPOINTS:
            url = f"{base_url}{endpoint}"
            status_code, response_text = self._http_get(url)
            
            if status_code == 200:
                health_endpoint = endpoint
                
                # Try to parse JSON response for service info
                try:
                    data = json.loads(response_text)
                    
                    # Look for common fields that might contain the service name
                    for field in ['name', 'service', 'app', 'application', 'title', 'service_name']:
                        if field in data and data[field]:
                            service_name = str(data[field])
                            break
                    
                    # Look for version info
                    for field in ['version', 'api_version', 'app_version']:
                        if field in data and data[field]:
                            version = str(data[field])
                            break
                    
                    # Check if entire response contains Forge identifiers
                    response_str = json.dumps(data).lower()
                    for identifier in self.FORGE_IDENTIFIERS:
                        if identifier in response_str:
                            if service_name == f"Service on port {port}":
                                service_name = f"Buildly {identifier.title()}"
                            break
                            
                except json.JSONDecodeError:
                    # Response is not JSON, check if it contains identifiers
                    response_lower = response_text.lower()
                    for identifier in self.FORGE_IDENTIFIERS:
                        if identifier in response_lower:
                            service_name = f"Buildly {identifier.title()}"
                            break
                
                break
        
        # If no health endpoint found, try to get service name from root
        got_http_response = False
        if not health_endpoint:
            status_code, response_text = self._http_get(base_url)
            if status_code == 200:
                got_http_response = True
                # Check for Forge identifiers in the page
                response_lower = response_text.lower()
                for identifier in self.FORGE_IDENTIFIERS:
                    if identifier in response_lower:
                        if service_name == f"Service on port {port}":
                            service_name = f"Buildly {identifier.title()}"
                        break
                
                # Check for common title patterns
                if '<title>' in response_text.lower():
                    import re
                    match = re.search(r'<title[^>]*>([^<]+)</title>', response_text, re.IGNORECASE)
                    if match:
                        title = match.group(1).strip()
                        # Only use title if it's not generic
                        if title and title.lower() not in ['home', 'index', 'welcome']:
                            service_name = title
        
        # Try to find the PID of the process using this port
        pid = self._get_pid_for_port(port)
        
        # Determine status
        # If we got any HTTP response (health endpoint or root page), it's running
        if health_endpoint or got_http_response:
            status = ServiceStatus.RUNNING
        elif self.is_port_open(port):
            # Port is open but not responding to HTTP
            # If it has a PID, it's likely a running service (WebSocket, gRPC, etc.)
            # Otherwise it might still be starting up
            if pid:
                status = ServiceStatus.RUNNING
                # Add note to name if we couldn't identify it
                if service_name == f"Service on port {port}":
                    service_name = f"Service on port {port} (Non-HTTP)"
            else:
                status = ServiceStatus.STARTING
        else:
            status = ServiceStatus.STOPPED
        
        # Create the service
        service = ForgeService(
            port=port,
            name=service_name,
            status=status,
            pid=pid,
            health_endpoint=health_endpoint,
            version=version
        )
        
        # Determine if this is a Forge service
        service.is_forge_service = self.is_forge_service(service)
        
        return service
    
    def _get_pid_for_port(self, port: int) -> Optional[int]:
        """Get the PID of the process listening on a port"""
        try:
            if sys.platform == 'darwin':
                # macOS
                result = subprocess.run(
                    ['lsof', '-i', f':{port}', '-t'],
                    capture_output=True,
                    text=True
                )
                if result.stdout.strip():
                    return int(result.stdout.strip().split('\n')[0])
                    
            elif sys.platform == 'win32':
                # Windows
                result = subprocess.run(
                    ['netstat', '-ano', '-p', 'tcp'],
                    capture_output=True,
                    text=True
                )
                for line in result.stdout.split('\n'):
                    if f':{port}' in line and 'LISTENING' in line:
                        parts = line.split()
                        if parts:
                            return int(parts[-1])
                            
            else:
                # Linux
                result = subprocess.run(
                    ['lsof', '-i', f':{port}', '-t'],
                    capture_output=True,
                    text=True
                )
                if result.stdout.strip():
                    return int(result.stdout.strip().split('\n')[0])
                    
        except Exception as e:
            print(f"Error getting PID for port {port}: {e}")
        
        return None
    
    def scan_services(self, force: bool = False) -> List[ForgeService]:
        """
        Scan the port range for running Forge services.
        
        Services that are identified as Forge services or saved by the user
        will persist in the list even when stopped.
        
        Args:
            force: If True, bypass the scan interval limit
            
        Returns:
            List of detected ForgeService objects
        """
        current_time = time.time()
        
        # Rate limit scanning unless forced
        if not force and (current_time - self._last_scan) < self._scan_interval:
            return list(self._services.values())
        
        self._last_scan = current_time
        
        # Keep track of what we find running
        running_ports = set()
        services_changed = False
        
        # Scan common ports first for faster detection
        common_ports = [8000, 8008, 8080, 8888, 9000]
        all_ports = common_ports + [p for p in range(self.port_start, self.port_end + 1) 
                                     if p not in common_ports]
        
        for port in all_ports:
            if self.is_port_open(port):
                running_ports.add(port)
                
                # Get current service info
                new_service_info = self.get_service_info(port)
                if new_service_info:
                    # If we already know about this service, update it intelligently
                    if port in self._services:
                        existing = self._services[port]
                        
                        # Update status and runtime info
                        status_changed = existing.status != new_service_info.status
                        existing.status = new_service_info.status
                        existing.pid = new_service_info.pid
                        
                        # Update service details if we got better info (has health endpoint)
                        if new_service_info.health_endpoint:
                            existing.name = new_service_info.name
                            existing.health_endpoint = new_service_info.health_endpoint
                            existing.version = new_service_info.version
                            existing.is_forge_service = self.is_forge_service(new_service_info)
                        
                        if status_changed:
                            self._notify_status_change(existing)
                            services_changed = True
                    else:
                        # New service discovered
                        new_service_info.is_forge_service = self.is_forge_service(new_service_info)
                        self._services[port] = new_service_info
                        services_changed = True
        
        # Update services that are no longer running
        for port, service in list(self._services.items()):
            if port not in running_ports:
                # Service has stopped - just update status, don't lose the service data
                if service.status != ServiceStatus.STOPPED:
                    service.status = ServiceStatus.STOPPED
                    service.pid = None
                    self._notify_status_change(service)
                    services_changed = True
                
                # Remove services that aren't Forge services and weren't saved by user
                if not service.is_forge_service and not service.saved_by_user:
                    del self._services[port]
                    services_changed = True
        
        # Save if anything changed
        if services_changed:
            self._save_services()
        
        return list(self._services.values())
    
    def get_service(self, port: int) -> Optional[ForgeService]:
        """Get a specific service by port"""
        return self._services.get(port) or self.get_service_info(port)
    
    def open_in_browser(self, port: int, path: str = "/"):
        """Open a service in the default web browser"""
        url = f"http://localhost:{port}{path}"
        webbrowser.open(url)
    
    def stop_service(self, port: int) -> bool:
        """
        Stop a service running on the specified port.
        
        Returns True if successfully stopped, False otherwise.
        """
        service = self.get_service(port)
        if not service or not service.pid:
            return False
        
        try:
            if sys.platform == 'win32':
                subprocess.run(['taskkill', '/F', '/PID', str(service.pid)], 
                             capture_output=True)
            else:
                os.kill(service.pid, signal.SIGTERM)
                
                # Wait a bit then force kill if needed
                time.sleep(2)
                try:
                    os.kill(service.pid, 0)  # Check if still running
                    os.kill(service.pid, signal.SIGKILL)
                except OSError:
                    pass  # Process already terminated
            
            # Update status
            if port in self._services:
                self._services[port].status = ServiceStatus.STOPPED
                self._services[port].pid = None
                self._notify_status_change(self._services[port])
            
            return True
            
        except Exception as e:
            print(f"Error stopping service on port {port}: {e}")
            return False
    
    def restart_service(self, port: int) -> bool:
        """Restart a service - stops it and relies on external process manager to restart"""
        return self.stop_service(port)
    
    def load_service_configs(self, config_file: Path):
        """Load service configurations from a JSON file"""
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    configs = json.load(f)
                    for name, config in configs.items():
                        self._service_configs[name] = ServiceConfig(
                            name=name,
                            port=config.get('port', 8000),
                            start_command=config.get('start_command', []),
                            stop_command=config.get('stop_command'),
                            working_dir=config.get('working_dir'),
                            pid_file=config.get('pid_file'),
                            log_file=config.get('log_file')
                        )
            except Exception as e:
                print(f"Error loading service configs: {e}")


class ForgeControllerBase:
    """
    Base class for platform-specific Forge Controller implementations.
    
    Subclasses should implement the UI-specific methods.
    """
    
    def __init__(self):
        self.scanner = ForgeServiceScanner()
        self.scanner.add_status_callback(self.on_status_change)
        
        # Auto-refresh interval in seconds
        self.refresh_interval = 5
        
        # Track if we're actively monitoring
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        
    def on_status_change(self, service: ForgeService):
        """Called when a service status changes - override in subclass"""
        pass
    
    def start_monitoring(self):
        """Start background service monitoring"""
        if self._monitoring:
            return
            
        self._monitoring = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()
    
    def stop_monitoring(self):
        """Stop background service monitoring"""
        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2)
    
    def _monitor_loop(self):
        """Background monitoring loop"""
        while self._monitoring:
            try:
                self.scanner.scan_services()
                self.update_ui()
            except Exception as e:
                print(f"Error in monitor loop: {e}")
            time.sleep(self.refresh_interval)
    
    def get_services(self) -> List[ForgeService]:
        """Get list of detected services"""
        return self.scanner.scan_services()
    
    def update_ui(self):
        """Update the UI with current service status - override in subclass"""
        pass
    
    def show_notification(self, title: str, message: str):
        """Show a system notification - override in subclass"""
        pass
    
    def open_browser(self, port: int):
        """Open service in browser"""
        self.scanner.open_in_browser(port)
    
    def stop_service(self, port: int):
        """Stop a service"""
        service = self.scanner.get_service(port)
        if service:
            if self.scanner.stop_service(port):
                self.show_notification("Service Stopped", f"{service.name} has been stopped")
            else:
                self.show_notification("Error", f"Failed to stop {service.name}")
    
    def view_logs(self, port: int):
        """View logs for a service - override in subclass for platform-specific behavior"""
        service = self.scanner.get_service(port)
        if service and service.pid:
            # Default implementation - can be overridden
            print(f"Logs for {service.name} (PID: {service.pid})")


def get_platform() -> str:
    """Get the current platform identifier"""
    if sys.platform == 'darwin':
        return 'macos'
    elif sys.platform == 'win32':
        return 'windows'
    else:
        return 'linux'


def check_dependencies() -> Dict[str, bool]:
    """Check if required dependencies are installed for the current platform"""
    platform = get_platform()
    deps = {}
    
    # Common dependencies
    deps['requests'] = HAS_REQUESTS
    
    if platform == 'macos':
        try:
            import rumps
            deps['rumps'] = True
        except ImportError:
            deps['rumps'] = False
            
    elif platform == 'windows':
        try:
            from PyQt5.QtWidgets import QApplication
            deps['PyQt5'] = True
        except ImportError:
            deps['PyQt5'] = False
            
    else:  # Linux
        try:
            import gi
            gi.require_version('Gtk', '3.0')
            from gi.repository import Gtk
            deps['gtk'] = True
        except (ImportError, ValueError):
            deps['gtk'] = False
            
        try:
            import gi
            gi.require_version('AppIndicator3', '0.1')
            from gi.repository import AppIndicator3
            deps['appindicator'] = True
        except (ImportError, ValueError):
            deps['appindicator'] = False
    
    return deps


def install_dependencies():
    """Install missing dependencies for the current platform"""
    platform = get_platform()
    
    # Install requests if missing
    if not HAS_REQUESTS:
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'requests'])
    
    if platform == 'macos':
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'rumps'])
    elif platform == 'windows':
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'PyQt5'])
    # Linux deps need system packages, handled by install script


if __name__ == '__main__':
    # Test the scanner
    print("Buildly Forge Service Scanner")
    print("=" * 40)
    
    scanner = ForgeServiceScanner()
    services = scanner.scan_services()
    
    if not services:
        print("No Forge services detected on ports 8000-9000")
    else:
        print(f"Found {len(services)} service(s):\n")
        for service in services:
            print(f"  {service.name}")
            print(f"    Port: {service.port}")
            print(f"    Status: {service.status.value}")
            if service.pid:
                print(f"    PID: {service.pid}")
            if service.version:
                print(f"    Version: {service.version}")
            if service.health_endpoint:
                print(f"    Health: {service.base_url}{service.health_endpoint}")
            print()
