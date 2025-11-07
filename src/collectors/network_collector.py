"""
Network Scanner Collector - Discovers devices and services on local network.
"""

import asyncio
import logging
import ipaddress
import socket
from datetime import datetime
from typing import Dict, Any, List, Optional
import subprocess
import json

from .base_collector import BaseCollector, CollectionResult

logger = logging.getLogger(__name__)


class NetworkCollector(BaseCollector):
    """Collector for local network discovery and service enumeration."""
    
    def __init__(self, settings=None):
        """Initialize network collector."""
        super().__init__(settings)
        self.common_ports = {
            22: 'SSH',
            80: 'HTTP',
            443: 'HTTPS', 
            8000: 'HTTP-Alt',
            8080: 'HTTP-Proxy',
            8443: 'HTTPS-Alt',
            11434: 'Ollama'
        }
        
    async def collect_data(self, start_date: datetime, end_date: datetime) -> CollectionResult:
        """
        Collect network data by scanning local network.
        Date range is not applicable for network scanning.
        """
        try:
            network_data = await self.scan_network()
            
            return CollectionResult(
                source="network",
                data=network_data.get('hosts', []),
                metadata=network_data.get('summary', {}),
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error scanning network: {e}")
            return CollectionResult(
                source="network",
                data=[],
                metadata={},
                timestamp=datetime.now(),
                error=str(e),
                success=False
            )
    
    async def scan_network(self) -> Dict[str, Any]:
        """
        Perform comprehensive network scan.
        
        Returns:
            Dictionary with hosts and summary information
        """
        try:
            # Get local network range
            network_range = await self._get_network_range()
            self.logger.info(f"Scanning network range: {network_range}")
            
            # Discover active hosts
            active_hosts = await self._discover_hosts(network_range)
            self.logger.info(f"Found {len(active_hosts)} active hosts")
            
            # Scan services on active hosts
            hosts_with_services = await self._scan_services(active_hosts)
            
            # Generate summary
            summary = self._generate_summary(hosts_with_services, network_range)
            
            return {
                'hosts': hosts_with_services,
                'summary': summary,
                'last_scan': datetime.now().isoformat()
            }
            
        except Exception as e:
            self.logger.error(f"Network scan failed: {e}")
            raise
    
    async def _get_network_range(self) -> str:
        """Determine the local network range."""
        try:
            # Get default gateway and local IP
            result = await asyncio.create_subprocess_exec(
                'ip', 'route', 'show', 'default',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                # Parse output to get default interface
                output = stdout.decode().strip()
                parts = output.split()
                if 'dev' in parts:
                    dev_index = parts.index('dev')
                    if dev_index + 1 < len(parts):
                        interface = parts[dev_index + 1]
                        
                        # Get IP and subnet for this interface
                        result = await asyncio.create_subprocess_exec(
                            'ip', 'addr', 'show', interface,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        stdout, stderr = await result.communicate()
                        
                        if result.returncode == 0:
                            output = stdout.decode()
                            # Look for inet line
                            for line in output.split('\n'):
                                if 'inet ' in line and 'scope global' in line:
                                    parts = line.split()
                                    for part in parts:
                                        if '/' in part and not part.startswith('fe80'):
                                            # This is likely our IP/subnet
                                            try:
                                                network = ipaddress.IPv4Network(part, strict=False)
                                                return str(network)
                                            except:
                                                continue
            
            # Fallback to common private networks
            return "192.168.1.0/24"
            
        except Exception as e:
            self.logger.warning(f"Could not determine network range: {e}")
            return "192.168.1.0/24"
    
    async def _discover_hosts(self, network_range: str) -> List[str]:
        """Discover active hosts using ping."""
        try:
            network = ipaddress.IPv4Network(network_range)
            hosts = []
            
            # Create ping tasks for all IPs in range (but limit to reasonable size)
            tasks = []
            ip_list = list(network.hosts())
            
            # Limit to first 254 IPs to avoid overwhelming
            if len(ip_list) > 254:
                ip_list = ip_list[:254]
            
            for ip in ip_list:
                task = self._ping_host(str(ip))
                tasks.append(task)
            
            # Execute pings concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Collect successful pings
            for i, result in enumerate(results):
                if result is True:
                    hosts.append(str(ip_list[i]))
            
            return hosts
            
        except Exception as e:
            self.logger.error(f"Host discovery failed: {e}")
            return []
    
    async def _ping_host(self, host: str) -> bool:
        """Ping a single host to check if it's alive."""
        try:
            # Apply rate limiting
            await self._rate_limit()
            
            process = await asyncio.create_subprocess_exec(
                'ping', '-c', '1', '-W', '1', host,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            await process.communicate()
            return process.returncode == 0
            
        except Exception:
            return False
    
    async def _scan_services(self, hosts: List[str]) -> List[Dict[str, Any]]:
        """Scan services on discovered hosts."""
        results = []
        
        # Create tasks for all hosts
        tasks = []
        for host in hosts:
            task = self._scan_host_services(host)
            tasks.append(task)
        
        # Execute scans concurrently
        host_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for i, result in enumerate(host_results):
            if not isinstance(result, Exception) and result:
                results.append(result)
        
        return results
    
    async def _scan_host_services(self, host: str) -> Optional[Dict[str, Any]]:
        """Scan services on a single host."""
        try:
            services = {}
            ollama_info = {'running': False, 'models': []}
            
            # Get hostname
            try:
                hostname = socket.gethostbyaddr(host)[0]
            except:
                hostname = host
            
            # Scan common ports
            for port, service_name in self.common_ports.items():
                if await self._check_port(host, port):
                    services[port] = service_name
                    
                    # Special handling for Ollama
                    if port == 11434:
                        ollama_info = await self._get_ollama_info(host)
            
            # Only return hosts with interesting services
            if services:
                host_info = {
                    'ip': host,
                    'hostname': hostname,
                    'services': services,
                    'ollama': ollama_info,
                    'scanned_at': datetime.now().isoformat()
                }
                
                # Try to get OS info
                try:
                    os_info = await self._get_os_info(host)
                    host_info['os_info'] = os_info
                except:
                    host_info['os_info'] = 'Unknown'
                
                return host_info
            
            return None
            
        except Exception as e:
            self.logger.debug(f"Error scanning {host}: {e}")
            return None
    
    async def _check_port(self, host: str, port: int) -> bool:
        """Check if a port is open on a host."""
        try:
            # Apply rate limiting
            await self._rate_limit()
            
            future = asyncio.open_connection(host, port)
            try:
                reader, writer = await asyncio.wait_for(future, timeout=2.0)
                writer.close()
                await writer.wait_closed()
                return True
            except asyncio.TimeoutError:
                return False
                
        except Exception:
            return False
    
    async def _get_ollama_info(self, host: str) -> Dict[str, Any]:
        """Get Ollama model information."""
        try:
            url = f"http://{host}:11434/api/tags"
            data = await self._fetch_json(url)
            
            models = []
            if 'models' in data:
                for model in data['models']:
                    models.append({
                        'name': model.get('name', 'unknown'),
                        'size': model.get('size', 0),
                        'modified_at': model.get('modified_at', '')
                    })
            
            return {
                'running': True,
                'models': models
            }
            
        except Exception as e:
            self.logger.debug(f"Could not get Ollama info from {host}: {e}")
            return {'running': False, 'models': []}
    
    async def _get_os_info(self, host: str) -> str:
        """Try to get OS information for a host."""
        try:
            # Try nmap if available
            process = await asyncio.create_subprocess_exec(
                'nmap', '-O', '-Pn', '--osscan-limit', host,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL
            )
            
            stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10.0)
            
            if process.returncode == 0:
                output = stdout.decode()
                # Parse OS info from nmap output
                for line in output.split('\n'):
                    if 'Running:' in line:
                        return line.split('Running:')[1].strip()
                    elif 'OS details:' in line:
                        return line.split('OS details:')[1].strip()
            
            return 'Unknown'
            
        except Exception:
            return 'Unknown'
    
    def _generate_summary(self, hosts: List[Dict[str, Any]], network_range: str) -> Dict[str, Any]:
        """Generate summary statistics."""
        total_hosts = len(hosts)
        ssh_enabled = len([h for h in hosts if 22 in h.get('services', {})])
        web_servers = len([h for h in hosts if any(port in h.get('services', {}) for port in [80, 443, 8000, 8080])])
        ollama_servers = len([h for h in hosts if h.get('ollama', {}).get('running', False)])
        
        return {
            'network': network_range,
            'total_hosts': total_hosts,
            'ssh_enabled': ssh_enabled,
            'web_servers': web_servers,
            'ollama_servers': ollama_servers,
            'scan_timestamp': datetime.now().isoformat()
        }
    
    def get_data_schema(self) -> Dict[str, Any]:
        """Return the database schema for network data."""
        return {
            'ip': 'TEXT PRIMARY KEY',
            'hostname': 'TEXT',
            'services': 'TEXT',  # JSON
            'ollama_info': 'TEXT',  # JSON
            'os_info': 'TEXT',
            'scanned_at': 'TEXT',
            'last_seen': 'TEXT DEFAULT CURRENT_TIMESTAMP'
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for network scanner."""
        try:
            # Test basic network connectivity
            network_range = await self._get_network_range()
            
            return {
                'collector': 'NetworkCollector',
                'status': 'healthy',
                'network_range': network_range,
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'collector': 'NetworkCollector',
                'status': 'unhealthy',
                'error': str(e),
                'last_check': datetime.now().isoformat()
            }
