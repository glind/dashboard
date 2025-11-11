#!/usr/bin/env python3
"""
Server Management Utility
Discovers, monitors, and controls Python web servers on the system
"""

import psutil
import re
import json
import subprocess
import signal
import requests
import socket
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import time
import logging

logger = logging.getLogger(__name__)

class ServerManager:
    """Manages Python web servers running on the system"""
    
    def __init__(self):
        self.known_servers = {}
        self.server_patterns = [
            r'python.*uvicorn.*--port\s+(\d+)',
            r'python.*fastapi.*--port\s+(\d+)',
            r'python.*flask.*--port\s+(\d+)',
            r'python.*django.*runserver.*:(\d+)',
            r'python.*-m\s+http\.server\s+(\d+)',
            r'python.*main\.py.*--port\s+(\d+)',
            r'uvicorn.*--port\s+(\d+)',
            r'gunicorn.*--bind.*:(\d+)',
        ]
    
    def discover_python_servers(self) -> List[Dict]:
        """Discover all Python web servers running on the system"""
        servers = []
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info', 'create_time']):
            try:
                if not proc.info['cmdline']:
                    continue
                    
                cmdline = ' '.join(proc.info['cmdline'])
                
                # Check if it's a Python process
                if not ('python' in cmdline.lower() or 'uvicorn' in cmdline.lower() or 'gunicorn' in cmdline.lower()):
                    continue
                
                # Check for web server patterns
                port = self._extract_port_from_cmdline(cmdline)
                if port:
                    # Try to determine the server type and name
                    server_info = self._analyze_server_process(proc, port, cmdline)
                    if server_info:
                        servers.append(server_info)
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        
        # Check for servers running on common ports even if we didn't find them via cmdline
        common_ports = [3000, 5000, 8000, 8008, 8080, 8888, 9000]
        for port in common_ports:
            if not any(s['port'] == port for s in servers):
                server_info = self._check_port_for_server(port)
                if server_info:
                    servers.append(server_info)
        
        return servers
    
    def _extract_port_from_cmdline(self, cmdline: str) -> Optional[int]:
        """Extract port number from command line"""
        for pattern in self.server_patterns:
            match = re.search(pattern, cmdline, re.IGNORECASE)
            if match:
                try:
                    return int(match.group(1))
                except (ValueError, IndexError):
                    continue
        
        # Look for common port patterns
        port_patterns = [
            r'--port[= ](\d+)',
            r'-p[= ](\d+)',
            r':(\d{4,5})',
            r'localhost:(\d+)',
            r'127\.0\.0\.1:(\d+)',
        ]
        
        for pattern in port_patterns:
            match = re.search(pattern, cmdline, re.IGNORECASE)
            if match:
                try:
                    port = int(match.group(1))
                    if 3000 <= port <= 9999:  # Reasonable port range for web servers
                        return port
                except (ValueError, IndexError):
                    continue
        
        return None
    
    def _analyze_server_process(self, proc, port: int, cmdline: str) -> Optional[Dict]:
        """Analyze a process to determine server details"""
        try:
            # Determine server type
            server_type = "unknown"
            if "fastapi" in cmdline.lower() or "uvicorn" in cmdline.lower():
                server_type = "FastAPI"
            elif "flask" in cmdline.lower():
                server_type = "Flask"
            elif "django" in cmdline.lower():
                server_type = "Django"
            elif "gunicorn" in cmdline.lower():
                server_type = "Gunicorn"
            elif "http.server" in cmdline.lower():
                server_type = "HTTP Server"
            
            # Try to determine project name from path
            project_name = self._extract_project_name(cmdline)
            
            # Check if the port is actually listening
            is_responsive = self._check_port_health(port)
            
            return {
                'pid': proc.info['pid'],
                'name': project_name,
                'type': server_type,
                'port': port,
                'url': f"http://localhost:{port}",
                'status': 'running' if is_responsive else 'not_responding',
                'cpu_percent': proc.info.get('cpu_percent', 0),
                'memory_mb': proc.info.get('memory_info', {}).get('rss', 0) / 1024 / 1024,
                'start_time': proc.info.get('create_time', 0),
                'cmdline': cmdline,
                'can_control': True  # We have the PID so we can control it
            }
            
        except Exception as e:
            logger.error(f"Error analyzing process: {e}")
            return None
    
    def _extract_project_name(self, cmdline: str) -> str:
        """Extract project name from command line"""
        # Look for common project directory patterns
        for part in cmdline.split():
            if '/' in part and ('main.py' in part or 'app.py' in part or 'server.py' in part):
                path = Path(part)
                if path.is_absolute():
                    return path.parent.name
                else:
                    # Try to find the project root
                    for parent_part in cmdline.split():
                        if parent_part.startswith('/') and parent_part in part:
                            return Path(parent_part).parent.name
        
        # Fallback: look for directory names in the cmdline
        parts = cmdline.split()
        for part in parts:
            if '/' in part:
                path_parts = part.split('/')
                for path_part in path_parts:
                    if path_part and not path_part.startswith('-') and not path_part.endswith('.py'):
                        return path_part
        
        return f"Server-{hash(cmdline) % 10000}"
    
    def _check_port_for_server(self, port: int) -> Optional[Dict]:
        """Check if a server is running on a specific port"""
        if not self._is_port_listening(port):
            return None
        
        # Try to get process info for the port
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                connections = proc.connections()
                for conn in connections:
                    if conn.laddr.port == port and conn.status == psutil.CONN_LISTEN:
                        cmdline = ' '.join(proc.info.get('cmdline', []))
                        if 'python' in cmdline.lower():
                            return self._analyze_server_process(proc, port, cmdline)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # If we can't find the process but the port is listening, create a basic entry
        is_responsive = self._check_port_health(port)
        return {
            'pid': None,
            'name': f"Unknown-{port}",
            'type': "Unknown",
            'port': port,
            'url': f"http://localhost:{port}",
            'status': 'running' if is_responsive else 'not_responding',
            'cpu_percent': 0,
            'memory_mb': 0,
            'start_time': 0,
            'cmdline': "",
            'can_control': False  # No PID so we can't control it
        }
    
    def _is_port_listening(self, port: int) -> bool:
        """Check if a port is listening"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(('127.0.0.1', port))
            sock.close()
            return result == 0
        except Exception:
            return False
    
    def _check_port_health(self, port: int) -> bool:
        """Check if a server on a port is responsive"""
        try:
            response = requests.get(f"http://localhost:{port}/", timeout=2)
            return response.status_code < 500
        except Exception:
            try:
                response = requests.get(f"http://localhost:{port}/health", timeout=2)
                return response.status_code < 500
            except Exception:
                return self._is_port_listening(port)
    
    def stop_server(self, server_info: Dict) -> bool:
        """Stop a server"""
        if not server_info.get('can_control') or not server_info.get('pid'):
            return False
        
        try:
            proc = psutil.Process(server_info['pid'])
            proc.terminate()
            
            # Wait for graceful shutdown
            try:
                proc.wait(timeout=5)
            except psutil.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=2)
            
            return True
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            logger.error(f"Failed to stop server: {e}")
            return False
    
    def start_server(self, server_config: Dict) -> bool:
        """Start a server (if we have the command)"""
        # This would need to be implemented based on stored configurations
        # For now, return False as we don't have start commands
        return False
    
    def get_server_status(self, port: int) -> Dict:
        """Get detailed status for a specific server"""
        servers = self.discover_python_servers()
        for server in servers:
            if server['port'] == port:
                # Add additional health check info
                server['health_check'] = self._detailed_health_check(port)
                server['response_time'] = self._measure_response_time(port)
                return server
        
        return {'status': 'not_found'}
    
    def _detailed_health_check(self, port: int) -> Dict:
        """Perform detailed health check"""
        try:
            start_time = time.time()
            response = requests.get(f"http://localhost:{port}/", timeout=5)
            response_time = time.time() - start_time
            
            return {
                'status': 'healthy' if response.status_code < 500 else 'unhealthy',
                'status_code': response.status_code,
                'response_time': response_time,
                'content_length': len(response.content),
                'headers': dict(response.headers)
            }
        except Exception as e:
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _measure_response_time(self, port: int) -> float:
        """Measure response time for a server"""
        try:
            start_time = time.time()
            requests.get(f"http://localhost:{port}/", timeout=3)
            return time.time() - start_time
        except Exception:
            return -1