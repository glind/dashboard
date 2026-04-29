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
import os
import ipaddress
from concurrent.futures import ThreadPoolExecutor, as_completed
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
        return self.discover_web_servers(port_min=3000, port_max=9999)

    def discover_web_servers(self, port_min: int = 8000, port_max: int = 9000) -> List[Dict]:
        """Discover user web servers in a port range."""
        servers = []
        seen_ports = set()
        
        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info', 'create_time']):
            try:
                if not proc.info['cmdline']:
                    continue

                cmdline_parts = proc.info['cmdline']
                cmdline = ' '.join(cmdline_parts)

                if not self._looks_like_web_server(cmdline):
                    continue

                port = self._extract_port_from_cmdline(cmdline)
                if port and port_min <= port <= port_max and port not in seen_ports:
                    server_info = self._analyze_server_process(proc, port, cmdline)
                    if server_info and self._include_server(server_info):
                        servers.append(server_info)
                        seen_ports.add(port)
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue

        # Avoid scanning every port in broad ranges; probe common dev/app ports first
        common_ports = [
            3000, 4200, 5000, 5173, 5500,
            7860, 8000, 8001, 8008, 8080, 8081,
            8501, 8787, 8888, 8890, 9000
        ]
        candidate_ports = [p for p in common_ports if port_min <= p <= port_max]
        if not candidate_ports:
            # Fallback to previous behavior only for tight ranges
            if (port_max - port_min) <= 50:
                candidate_ports = list(range(port_min, port_max + 1))
            else:
                candidate_ports = [port_min, port_max]

        for port in candidate_ports:
            if port not in seen_ports:
                server_info = self._check_port_for_server(port)
                if server_info and self._include_server(server_info):
                    servers.append(server_info)
                    seen_ports.add(port)

        return sorted(servers, key=lambda s: s.get('port', 0))

    def _looks_like_web_server(self, cmdline: str) -> bool:
        lowered = cmdline.lower()
        markers = [
            'uvicorn', 'gunicorn', 'hypercorn', 'flask', 'django', 'fastapi',
            'http.server', 'node', 'next', 'vite', 'webpack-dev-server', 'npm run'
        ]
        return any(marker in lowered for marker in markers)

    def _include_server(self, server_info: Dict) -> bool:
        if not server_info:
            return False

        cmdline = str(server_info.get('cmdline', '')).lower()
        excluded = [
            'docker-proxy', 'containerd', 'kube', 'systemd',
            'avahi', 'cupsd', 'dbus', 'sshd'
        ]
        if any(token in cmdline for token in excluded):
            return False

        return True
    
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
            app_path = self._extract_app_path(proc, cmdline)
            working_dir = self._safe_get_cwd(proc)
            repo_info = self._find_git_info(app_path or working_dir)
            restart_command = self._build_restart_command(proc, app_path, working_dir, port)
            memory_info = proc.info.get('memory_info')
            memory_mb = 0
            try:
                if memory_info is not None and hasattr(memory_info, 'rss'):
                    memory_mb = float(memory_info.rss) / 1024 / 1024
            except Exception:
                memory_mb = 0
            
            # Check if the port is actually listening
            is_responsive = self._check_port_health(port)
            
            return {
                'pid': proc.info['pid'],
                'name': project_name,
                'type': server_type,
                'source': 'local',
                'port': port,
                'url': f"http://localhost:{port}",
                'status': 'running' if is_responsive else 'not_responding',
                'cpu_percent': proc.info.get('cpu_percent', 0),
                'memory_mb': memory_mb,
                'start_time': proc.info.get('create_time', 0),
                'cmdline': cmdline,
                'working_dir': working_dir,
                'app_path': app_path,
                'entrypoint': self._extract_entrypoint(cmdline),
                'repo': repo_info,
                'restart_command': restart_command,
                'can_restart': bool(restart_command),
                'service_guess': server_type,
                'likely_use': self._guess_local_use(cmdline, app_path, project_name),
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

    def _guess_local_use(self, cmdline: str, app_path: Optional[str], project_name: str) -> str:
        text = f"{cmdline} {app_path or ''} {project_name}".lower()
        if 'dashboard' in text:
            return 'Dashboard web app'
        if 'api' in text or 'fastapi' in text or 'flask' in text:
            return 'REST API service'
        if 'jupyter' in text:
            return 'Notebook or data workspace'
        if 'admin' in text:
            return 'Admin console'
        if 'streamlit' in text:
            return 'Data app (Streamlit)'
        return 'Custom web application'

    def _extract_entrypoint(self, cmdline: str) -> str:
        parts = cmdline.split()
        for part in parts:
            if part.endswith('.py'):
                return part
        return parts[0] if parts else 'unknown'

    def _extract_app_path(self, proc, cmdline: str) -> Optional[str]:
        for token in cmdline.split():
            if token.endswith('.py') or '/src/' in token or '/app/' in token:
                candidate = Path(token)
                if candidate.is_absolute() and candidate.exists():
                    return str(candidate.parent if candidate.is_file() else candidate)

        cwd = self._safe_get_cwd(proc)
        if cwd:
            return cwd
        return None

    def _safe_get_cwd(self, proc) -> Optional[str]:
        try:
            return proc.cwd()
        except Exception:
            return None

    def _find_git_info(self, start_path: Optional[str]) -> Optional[Dict]:
        if not start_path:
            return None

        path = Path(start_path)
        if path.is_file():
            path = path.parent

        git_root = None
        for parent in [path] + list(path.parents):
            if (parent / '.git').exists():
                git_root = parent
                break

        if not git_root:
            return None

        remotes = self._read_git_remotes(git_root)
        github_remotes = [r for r in remotes if 'github.com' in r.get('url', '').lower()]

        return {
            'root': str(git_root),
            'remotes': remotes,
            'github_remotes': github_remotes
        }

    def _read_git_remotes(self, git_root: Path) -> List[Dict]:
        try:
            result = subprocess.run(
                ['git', '-C', str(git_root), 'remote', '-v'],
                capture_output=True,
                text=True,
                timeout=3
            )
            if result.returncode != 0:
                return []

            parsed = []
            seen = set()
            for line in result.stdout.splitlines():
                parts = line.split()
                if len(parts) >= 3:
                    name, url, kind = parts[0], parts[1], parts[2].strip('()')
                    key = (name, url, kind)
                    if key in seen:
                        continue
                    seen.add(key)
                    parsed.append({'name': name, 'url': url, 'type': kind})
            return parsed
        except Exception:
            return []

    def _build_restart_command(self, proc, app_path: Optional[str], working_dir: Optional[str], port: int) -> Optional[List[str]]:
        base_dir = None
        if app_path:
            app_dir = Path(app_path)
            for parent in [app_dir] + list(app_dir.parents):
                if (parent / 'ops' / 'startup.sh').exists():
                    base_dir = parent
                    break

        if base_dir:
            return ['bash', '-lc', f'cd {self._shell_quote(str(base_dir))} && ./ops/startup.sh restart']

        try:
            cmdline = proc.cmdline()
            if cmdline:
                return cmdline
        except Exception:
            pass

        return None

    def _shell_quote(self, value: str) -> str:
        return "'" + value.replace("'", "'\\''") + "'"
    
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
                        if self._looks_like_web_server(cmdline):
                            return self._analyze_server_process(proc, port, cmdline)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        # If we can't find the process but the port is listening, create a basic entry
        is_responsive = self._check_port_health(port)
        return {
            'pid': None,
            'name': f"Unknown-{port}",
            'type': "Unknown",
            'source': 'local',
            'port': port,
            'url': f"http://localhost:{port}",
            'status': 'running' if is_responsive else 'not_responding',
            'cpu_percent': 0,
            'memory_mb': 0,
            'start_time': 0,
            'cmdline': "",
            'working_dir': None,
            'app_path': None,
            'entrypoint': None,
            'repo': None,
            'restart_command': None,
            'can_restart': False,
            'service_guess': 'Unknown web service',
            'likely_use': 'Custom web application',
            'can_control': False  # No PID so we can't control it
        }

    def discover_remote_web_servers(self, port_min: int = 8000, port_max: int = 9000) -> List[Dict]:
        """Best-effort discovery for LAN web services on likely app ports."""
        hosts = self._candidate_lan_hosts(limit_hosts=64)
        if not hosts:
            return []

        likely_ports = [8000, 8001, 8008, 8080, 8081, 8501, 8787, 8888, 8890, 9000]
        ports = [p for p in likely_ports if port_min <= p <= port_max]
        if not ports:
            return []

        results = []
        futures = []
        with ThreadPoolExecutor(max_workers=32) as pool:
            for host in hosts:
                for port in ports:
                    futures.append(pool.submit(self._probe_remote_service, host, port))

            for future in as_completed(futures):
                try:
                    item = future.result()
                    if item:
                        results.append(item)
                except Exception:
                    continue

        return sorted(results, key=lambda x: (x.get('host', ''), x.get('port', 0)))

    def _candidate_lan_hosts(self, limit_hosts: int = 64) -> List[str]:
        local_ip = self._get_primary_local_ip()
        if not local_ip:
            return []

        if not (
            local_ip.startswith('10.') or
            local_ip.startswith('192.168.') or
            local_ip.startswith('172.')
        ):
            return []

        try:
            network = ipaddress.ip_network(f"{local_ip}/24", strict=False)
            hosts = [str(host) for host in network.hosts() if str(host) != local_ip]
            return hosts[:limit_hosts]
        except Exception:
            return []

    def _get_primary_local_ip(self) -> Optional[str]:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.connect(('8.8.8.8', 80))
            ip = sock.getsockname()[0]
            sock.close()
            return ip
        except Exception:
            return None

    def _probe_remote_service(self, host: str, port: int) -> Optional[Dict]:
        url = f"http://{host}:{port}"
        try:
            response = requests.get(url, timeout=0.7, allow_redirects=True)
            if not self._looks_like_web_response(response):
                return None

            guess = self._guess_remote_service(response)
            return {
                'pid': None,
                'name': f"{guess} ({host})",
                'type': 'Remote Web Service',
                'source': 'remote',
                'host': host,
                'port': port,
                'url': url,
                'status': 'running',
                'cpu_percent': 0,
                'memory_mb': 0,
                'start_time': 0,
                'cmdline': '',
                'working_dir': None,
                'app_path': None,
                'entrypoint': None,
                'repo': None,
                'restart_command': None,
                'can_restart': False,
                'can_control': False,
                'service_guess': guess,
                'likely_use': self._guess_remote_use(response, guess)
            }
        except Exception:
            return None

    def _looks_like_web_response(self, response) -> bool:
        content_type = (response.headers.get('content-type') or '').lower()
        if 'text/html' in content_type or 'application/json' in content_type:
            return True
        if response.status_code in (200, 201, 301, 302, 401, 403):
            return True
        return False

    def _guess_remote_service(self, response) -> str:
        headers = {k.lower(): v for k, v in response.headers.items()}
        body = (response.text or '')[:2000].lower()
        server_header = headers.get('server', '').lower()

        if 'jupyter' in body or 'jupyter' in server_header:
            return 'Jupyter'
        if 'grafana' in body or 'grafana' in server_header:
            return 'Grafana'
        if 'portainer' in body:
            return 'Portainer'
        if 'wordpress' in body:
            return 'WordPress'
        if 'next.js' in body or '__next' in body:
            return 'Next.js App'
        if 'react' in body:
            return 'React App'
        if 'fastapi' in body or 'swagger ui' in body:
            return 'FastAPI'
        if 'flask' in body:
            return 'Flask App'
        if 'django' in body:
            return 'Django App'
        if 'nginx' in server_header:
            return 'Nginx Web Service'
        return 'Unknown Web App'

    def _guess_remote_use(self, response, guess: str) -> str:
        lowered_guess = (guess or '').lower()
        if 'jupyter' in lowered_guess:
            return 'Notebook and data science workspace'
        if 'grafana' in lowered_guess:
            return 'Monitoring dashboards and metrics'
        if 'portainer' in lowered_guess:
            return 'Container management UI'
        if 'fastapi' in lowered_guess or 'flask' in lowered_guess or 'django' in lowered_guess:
            return 'Backend API or web application'
        if 'react' in lowered_guess or 'next.js' in lowered_guess:
            return 'Frontend application'

        body = (response.text or '')[:2000].lower()
        if 'login' in body or 'sign in' in body:
            return 'Web admin or authenticated app'
        if 'api' in body:
            return 'API endpoint service'
        return 'Custom LAN web service'
    
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
        # Avoid self-referential HTTP probes (e.g., checking dashboard port from /api/servers)
        # which can block in single-worker setups; socket check is enough for local discovery.
        try:
            dashboard_port = int(os.getenv('PORT', '8008'))
        except Exception:
            dashboard_port = 8008

        if port == dashboard_port:
            return self._is_port_listening(port)

        try:
            response = requests.get(f"http://localhost:{port}/", timeout=0.6)
            return response.status_code < 500
        except Exception:
            try:
                response = requests.get(f"http://localhost:{port}/health", timeout=0.6)
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

    def restart_server(self, server_info: Dict) -> bool:
        """Restart a server using discovered restart command."""
        command = server_info.get('restart_command')
        if not command:
            return False

        try:
            if isinstance(command, list) and len(command) >= 3 and command[0] == 'bash' and command[1] == '-lc':
                subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=os.setpgrp
                )
                return True

            if server_info.get('can_control') and server_info.get('pid'):
                self.stop_server(server_info)

            subprocess.Popen(
                command,
                cwd=server_info.get('working_dir') or None,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setpgrp
            )
            return True
        except Exception as e:
            logger.error(f"Failed to restart server: {e}")
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