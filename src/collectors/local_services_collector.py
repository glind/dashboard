"""
Local services and network monitoring collector.
"""

import asyncio
import aiohttp
import subprocess
import socket
import logging
import json
import platform
from datetime import datetime
from typing import List, Dict, Any, Optional
from database import DatabaseManager

logger = logging.getLogger(__name__)


class LocalServicesCollector:
    """Monitors local services and network devices."""
    
    def __init__(self, settings=None):
        """Initialize local services collector."""
        self.settings = settings
        self.db = DatabaseManager()
        
        # Common local services to monitor
        self.default_services = [
            {"name": "Personal Dashboard", "port": 8008, "type": "web", "endpoint": "/health"},
            {"name": "Investment API", "port": 5003, "type": "api", "endpoint": "/"},
            {"name": "Ollama LLM", "port": 11434, "type": "api", "endpoint": "/api/tags"},
            {"name": "Jupyter Notebook", "port": 8888, "type": "web", "endpoint": "/"},
            {"name": "SSH Server", "port": 22, "type": "system"},
            {"name": "HTTP Server", "port": 80, "type": "web"},
            {"name": "HTTPS Server", "port": 443, "type": "web"},
            {"name": "MySQL", "port": 3306, "type": "database"},
            {"name": "PostgreSQL", "port": 5432, "type": "database"},
            {"name": "Redis", "port": 6379, "type": "database"},
            {"name": "MongoDB", "port": 27017, "type": "database"},
        ]
        
    async def collect_data(self) -> Dict[str, Any]:
        """Collect all local services and network data."""
        try:
            # Collect local services
            local_services = await self.scan_local_services()
            
            # Discover network devices
            network_devices = await self.discover_network_devices()
            
            # Get system info
            system_info = self.get_system_info()
            
            return {
                "local_services": local_services,
                "network_devices": network_devices,
                "system_info": system_info,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error collecting local services data: {e}")
            return {
                "local_services": [],
                "network_devices": [],
                "system_info": {},
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    async def scan_local_services(self) -> List[Dict[str, Any]]:
        """Scan for local services on common ports."""
        services = []
        
        # First add/update default services in database
        for service in self.default_services:
            self.db.save_local_service(
                service_name=service["name"],
                port=service["port"],
                service_type=service["type"],
                endpoint_url=service.get("endpoint")
            )
        
        # Get all monitored services from database
        monitored_services = self.db.get_monitored_services()
        
        # Check status of each service
        for service in monitored_services:
            status_info = await self.check_service_status(service)
            services.append(status_info)
            
            # Update database with current status
            self.db.update_service_status(
                service["id"], 
                status_info["status"], 
                status_info.get("response_time")
            )
            
        return services

    async def check_service_status(self, service: Dict) -> Dict[str, Any]:
        """Check if a service is running and responsive."""
        service_info = dict(service)
        start_time = datetime.now()
        
        try:
            # First try to connect to port
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((service["ip_address"], service["port"]))
            sock.close()
            
            if result != 0:
                service_info["status"] = "stopped"
                service_info["response_time"] = None
                return service_info
            
            # Port is open, try HTTP request if it's a web service
            if service["service_type"] in ["web", "api"] and service.get("endpoint_url"):
                try:
                    url = f"http://{service['ip_address']}:{service['port']}{service['endpoint_url']}"
                    async with aiohttp.ClientSession() as session:
                        async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as response:
                            response_time = (datetime.now() - start_time).total_seconds()
                            service_info["status"] = "running" if response.status < 500 else "error"
                            service_info["response_time"] = response_time
                            service_info["http_status"] = response.status
                            service_info["url"] = url
                            
                except Exception as e:
                    response_time = (datetime.now() - start_time).total_seconds()
                    service_info["status"] = "error"
                    service_info["response_time"] = response_time
                    service_info["error"] = str(e)
            else:
                # Port is open but not HTTP
                response_time = (datetime.now() - start_time).total_seconds()
                service_info["status"] = "running"
                service_info["response_time"] = response_time
                
        except Exception as e:
            service_info["status"] = "error"
            service_info["error"] = str(e)
            service_info["response_time"] = None
            
        return service_info

    async def discover_network_devices(self) -> List[Dict[str, Any]]:
        """Discover devices on the local network."""
        devices = []
        
        try:
            # Get local network range
            network_range = self.get_local_network_range()
            
            # Ping sweep to find active devices
            active_ips = await self.ping_sweep(network_range)
            
            # For each active IP, gather more info
            for ip in active_ips:
                device_info = await self.gather_device_info(ip)
                if device_info:
                    devices.append(device_info)
                    
                    # Save to database
                    self.db.save_network_device(
                        ip_address=ip,
                        hostname=device_info.get("hostname"),
                        mac_address=device_info.get("mac_address"),
                        device_type=device_info.get("device_type"),
                        manufacturer=device_info.get("manufacturer"),
                        open_ports=device_info.get("open_ports", []),
                        services=device_info.get("services", []),
                        is_online=True,
                        response_time=device_info.get("response_time")
                    )
                    
        except Exception as e:
            logger.error(f"Error in network discovery: {e}")
            
        return devices

    def get_local_network_range(self) -> str:
        """Get the local network range for scanning."""
        try:
            # Get default gateway
            if platform.system() == "Darwin":  # macOS
                result = subprocess.run(["route", "get", "default"], capture_output=True, text=True)
                for line in result.stdout.split('\n'):
                    if 'gateway:' in line:
                        gateway = line.split(':')[1].strip()
                        # Convert to network range (assume /24)
                        network_base = '.'.join(gateway.split('.')[:-1])
                        return f"{network_base}.0/24"
            
            # Fallback to common ranges
            return "192.168.1.0/24"
            
        except:
            return "192.168.1.0/24"

    async def ping_sweep(self, network_range: str, max_concurrent: int = 20) -> List[str]:
        """Perform ping sweep to find active devices."""
        active_ips = []
        
        try:
            # Extract base network (assume /24 for simplicity)
            base = network_range.split('/')[0].rsplit('.', 1)[0]
            
            # Create tasks for pinging IPs 1-254
            semaphore = asyncio.Semaphore(max_concurrent)
            tasks = []
            
            for i in range(1, 255):
                ip = f"{base}.{i}"
                task = self.ping_ip(ip, semaphore)
                tasks.append(task)
            
            # Wait for all pings to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect successful pings
            for i, result in enumerate(results):
                if result is True:  # Ping successful
                    ip = f"{base}.{i+1}"
                    active_ips.append(ip)
                    
        except Exception as e:
            logger.error(f"Error in ping sweep: {e}")
            
        return active_ips

    async def ping_ip(self, ip: str, semaphore: asyncio.Semaphore) -> bool:
        """Ping a single IP address."""
        async with semaphore:
            try:
                if platform.system() == "Darwin":  # macOS
                    cmd = ["ping", "-c", "1", "-W", "1000", ip]
                else:  # Linux
                    cmd = ["ping", "-c", "1", "-W", "1", ip]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL
                )
                
                await asyncio.wait_for(process.wait(), timeout=2)
                return process.returncode == 0
                
            except:
                return False

    async def gather_device_info(self, ip: str) -> Optional[Dict[str, Any]]:
        """Gather detailed information about a network device."""
        try:
            device_info = {
                "ip_address": ip,
                "hostname": None,
                "mac_address": None,
                "device_type": "unknown",
                "manufacturer": None,
                "open_ports": [],
                "services": [],
                "response_time": None,
                "last_seen": datetime.now().isoformat()
            }
            
            start_time = datetime.now()
            
            # Try to get hostname
            try:
                hostname = socket.gethostbyaddr(ip)[0]
                device_info["hostname"] = hostname
                device_info["device_type"] = self.classify_device_by_hostname(hostname)
            except:
                pass
            
            # Quick port scan for common services
            common_ports = [22, 23, 53, 80, 135, 139, 443, 445, 993, 995, 3389, 5353, 8080, 8443]
            open_ports = []
            
            for port in common_ports:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(0.5)
                    result = sock.connect_ex((ip, port))
                    sock.close()
                    if result == 0:
                        open_ports.append(port)
                        service_name = self.identify_service_by_port(port)
                        if service_name:
                            device_info["services"].append(service_name)
                except:
                    pass
            
            device_info["open_ports"] = open_ports
            device_info["response_time"] = (datetime.now() - start_time).total_seconds()
            
            return device_info
            
        except Exception as e:
            logger.error(f"Error gathering device info for {ip}: {e}")
            return None

    def classify_device_by_hostname(self, hostname: str) -> str:
        """Classify device type based on hostname patterns."""
        hostname_lower = hostname.lower()
        
        if any(x in hostname_lower for x in ['router', 'gateway', 'linksys', 'netgear', 'asus']):
            return "router"
        elif any(x in hostname_lower for x in ['printer', 'hp', 'canon', 'epson']):
            return "printer"
        elif any(x in hostname_lower for x in ['iphone', 'ipad', 'android', 'phone']):
            return "mobile"
        elif any(x in hostname_lower for x in ['macbook', 'imac', 'mac', 'apple']):
            return "computer"
        elif any(x in hostname_lower for x in ['pc', 'desktop', 'laptop', 'windows']):
            return "computer"
        elif any(x in hostname_lower for x in ['tv', 'roku', 'chromecast', 'appletv']):
            return "media"
        else:
            return "unknown"

    def identify_service_by_port(self, port: int) -> Optional[str]:
        """Identify service by port number."""
        port_services = {
            22: "SSH",
            23: "Telnet", 
            53: "DNS",
            80: "HTTP",
            135: "RPC",
            139: "NetBIOS",
            443: "HTTPS",
            445: "SMB",
            993: "IMAPS",
            995: "POP3S",
            3389: "RDP",
            5353: "mDNS",
            8080: "HTTP Alt",
            8443: "HTTPS Alt"
        }
        return port_services.get(port)

    def get_system_info(self) -> Dict[str, Any]:
        """Get current system information."""
        try:
            return {
                "platform": platform.system(),
                "platform_release": platform.release(),
                "platform_version": platform.version(),
                "architecture": platform.machine(),
                "hostname": socket.gethostname(),
                "python_version": platform.python_version(),
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            logger.error(f"Error getting system info: {e}")
            return {}