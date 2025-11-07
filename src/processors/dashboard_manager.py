#!/usr/bin/env python3
"""
Dashboard Manager
================

Automatically discovers and manages all marketing dashboards, websites, and deployments.
Provides one-click starting, stopping, and monitoring of various projects.

Features:
- Auto-discovery of marketing websites and dashboards
- Process management (start/stop/status)
- GitHub Pages deployment monitoring  
- Port conflict detection and management
- Health checks and status monitoring
- Brand website URL tracking
"""

import asyncio
import aiohttp
import json
import logging
import os
import subprocess
import signal
import psutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
import re
import yaml

logger = logging.getLogger(__name__)

@dataclass
class DashboardProject:
    """Represents a discoverable dashboard or website project"""
    name: str
    path: str
    type: str  # 'flask', 'fastapi', 'static', 'react', 'vue', 'github_pages'
    port: Optional[int] = None
    start_command: Optional[str] = None
    url: Optional[str] = None
    github_pages_url: Optional[str] = None
    status: str = "stopped"  # 'running', 'stopped', 'error', 'unknown'
    pid: Optional[int] = None
    brand: Optional[str] = None
    description: Optional[str] = None
    last_checked: Optional[datetime] = None
    health_endpoint: Optional[str] = None
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.dependencies is None:
            self.dependencies = []

@dataclass
class BrandWebsite:
    """Represents a brand website deployment"""
    name: str
    brand: str
    live_url: str
    github_repo: Optional[str] = None
    deployment_type: str = "github_pages"  # 'github_pages', 'netlify', 'vercel', 'custom'
    status: str = "unknown"
    last_deployed: Optional[str] = None
    build_status: str = "unknown"

class DashboardManager:
    """Manages all marketing dashboards and websites"""
    
    def __init__(self, marketing_path: str = None):
        # Default marketing path: go up from dashboard to parent, then into marketing
        if marketing_path is None:
            # From src/processors/dashboard_manager.py: up to src/, up to dashboard/, up to me/, then into marketing/
            dashboard_parent = Path(__file__).parent.parent.parent.parent
            marketing_path = str(dashboard_parent / "marketing")
        
        self.marketing_path = Path(marketing_path).resolve()
        self.dashboard_path = Path(__file__).parent.parent
        self.discovered_projects = []
        self.brand_websites = []
        self.session = None
        
        # Import database manager
        from database import DatabaseManager
        self.db = DatabaseManager()
        
        # Common port ranges for different frameworks
        self.port_patterns = {
            'flask': [5000, 5001, 5002, 8080, 8081],
            'fastapi': [8000, 8001, 8002, 8008, 8080],
            'react': [3000, 3001, 3002],
            'vue': [8080, 8081, 3000],
            'static': [8000, 8080, 3000],
            'streamlit': [8501, 8502, 8503]
        }
        
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def discover_all_projects(self) -> List[DashboardProject]:
        """Discover all dashboard and website projects"""
        logger.info("🔍 Discovering marketing dashboards and websites...")
        logger.info(f"📂 Marketing path configured as: {self.marketing_path}")
        logger.info(f"📂 Marketing path exists: {self.marketing_path.exists()}")
        logger.info(f"📂 Marketing path is directory: {self.marketing_path.is_dir() if self.marketing_path.exists() else 'N/A'}")
        
        projects = []
        
        # First, load saved configurations from database
        saved_projects = self.db.get_dashboard_projects(active_only=True)
        saved_projects_dict = {p['name']: p for p in saved_projects}
        logger.info(f"📂 Loaded {len(saved_projects)} saved project configurations")
        
        # Discover projects in marketing directory
        if self.marketing_path.exists():
            logger.info(f"📁 Starting marketing directory scan...")
            discovered = await self._discover_marketing_projects()
            logger.info(f"📁 Marketing scan found {len(discovered)} projects")
            
            # Merge discovered projects with saved configurations
            for project in discovered:
                if project.name in saved_projects_dict:
                    # Use saved configuration, but update status
                    saved = saved_projects_dict[project.name]
                    project.url = saved.get('custom_domain') or saved.get('url') or project.url
                    project.github_pages_url = saved.get('github_pages_url') or project.github_pages_url
                    project.start_command = saved.get('start_command') or project.start_command
                    project.port = saved.get('port') or project.port
                    project.brand = saved.get('brand') or project.brand
                    project.description = saved.get('description') or project.description
                    logger.info(f"✓ Merged saved config for: {project.name}")
                
                projects.append(project)
        else:
            logger.warning(f"⚠️  Marketing path does not exist: {self.marketing_path}")
        
        # Add any saved projects that weren't discovered (e.g., GitHub Pages sites with custom domains)
        for name, saved in saved_projects_dict.items():
            if not any(p.name == name for p in projects):
                project = DashboardProject(
                    name=saved['name'],
                    path=saved['path'],
                    type=saved['type'],
                    port=saved.get('port'),
                    start_command=saved.get('start_command'),
                    url=saved.get('custom_domain') or saved.get('url'),
                    github_pages_url=saved.get('github_pages_url'),
                    brand=saved.get('brand'),
                    description=saved.get('description'),
                    health_endpoint=saved.get('health_endpoint')
                )
                projects.append(project)
                logger.info(f"✓ Added saved-only project: {name}")
        
        # Discover GitHub Pages websites
        projects.extend(await self._discover_github_pages_sites())
        
        # Discover brand websites
        await self._discover_brand_websites()
        
        # Update project statuses
        for project in projects:
            await self._update_project_status(project)
        
        self.discovered_projects = projects
        logger.info(f"✅ Discovered {len(projects)} dashboard projects")
        return projects
    
    async def _discover_marketing_projects(self) -> List[DashboardProject]:
        """Scan marketing directory for dashboard projects"""
        projects = []
        
        logger.info(f"🔍 Scanning marketing path: {self.marketing_path}")
        
        # Directories to skip (virtual environments, dependencies, etc.)
        skip_patterns = [
            'venv', '.venv', 'env', '.env', 'virtualenv',
            'node_modules', '__pycache__', '.git', '.github',
            'dist', 'build', '.pytest_cache', '.mypy_cache',
            'site-packages', 'lib', 'lib64', 'include', 'bin',
            '.tox', '.eggs', '.egg-info'
        ]
        
        for root, dirs, files in os.walk(self.marketing_path):
            root_path = Path(root)
            
            # Skip if any parent directory matches skip patterns
            path_parts = root_path.parts
            should_skip = any(
                any(pattern in part or part.startswith('.') for pattern in skip_patterns)
                for part in path_parts
            )
            
            if should_skip:
                dirs[:] = []  # Don't recurse into this directory
                continue
            
            # Filter out directories we don't want to recurse into
            dirs[:] = [d for d in dirs if not (
                d.startswith('.') or 
                d == '__pycache__' or
                any(pattern in d for pattern in skip_patterns)
            )]
            
            # Log directories being scanned
            logger.debug(f"Scanning directory: {root_path.name} ({len(files)} files)")
            
            project = await self._analyze_directory(root_path, files)
            if project:
                logger.info(f"✓ Found project: {project.name} ({project.type}) at {project.path}")
                projects.append(project)
        
        logger.info(f"📦 Discovered {len(projects)} marketing projects")
        return projects
    
    async def _analyze_directory(self, path: Path, files: List[str]) -> Optional[DashboardProject]:
        """Analyze a directory to determine if it's a dashboard project"""
        
        # Check for various project indicators
        project_indicators = {
            'flask': ['app.py', 'main.py', 'run.py', 'wsgi.py'],
            'fastapi': ['main.py', 'app.py', 'api.py'],
            'react': ['package.json', 'src/App.js', 'src/App.tsx'],
            'vue': ['package.json', 'src/main.js', 'vue.config.js'],
            'static': ['index.html'],
            'streamlit': ['streamlit_app.py', 'app.py'],
            'django': ['manage.py', 'settings.py']
        }
        
        detected_type = None
        main_file = None
        
        for file_type, indicators in project_indicators.items():
            for indicator in indicators:
                if indicator in files or (Path(path) / indicator).exists():
                    detected_type = file_type
                    main_file = indicator
                    logger.debug(f"  → Detected {file_type} project at {path.name} (found {indicator})")
                    break
            if detected_type:
                break
        
        if not detected_type:
            return None
        
        # Extract project info
        project_name = path.name
        
        # Look for configuration files to get more details
        config_info = await self._extract_config_info(path, files)
        
        # Determine start command
        start_command = await self._determine_start_command(path, detected_type, main_file)
        
        # Determine port
        port = await self._determine_port(path, detected_type, config_info)
        
        # Check for brand info
        brand = await self._extract_brand_info(path)
        
        project = DashboardProject(
            name=project_name,
            path=str(path),
            type=detected_type,
            port=port,
            start_command=start_command,
            url=f"http://localhost:{port}" if port else None,
            brand=brand,
            description=config_info.get('description', f"{detected_type.title()} dashboard in {project_name}"),
            health_endpoint=config_info.get('health_endpoint', '/health' if detected_type in ['fastapi', 'flask'] else None)
        )
        
        return project
    
    async def _extract_config_info(self, path: Path, files: List[str]) -> Dict[str, Any]:
        """Extract configuration information from various config files"""
        config_info = {}
        
        # Check package.json for Node.js projects
        if 'package.json' in files:
            try:
                with open(path / 'package.json', 'r') as f:
                    package_data = json.load(f)
                    config_info['description'] = package_data.get('description', '')
                    config_info['scripts'] = package_data.get('scripts', {})
                    
                    # Extract port from scripts
                    for script_name, script_cmd in config_info['scripts'].items():
                        if 'port' in script_cmd:
                            port_match = re.search(r'--port[= ](\d+)', script_cmd)
                            if port_match:
                                config_info['port'] = int(port_match.group(1))
            except Exception as e:
                logger.warning(f"Error reading package.json in {path}: {e}")
        
        # Check for Python config files
        config_files = ['config.py', 'settings.py', 'config.yaml', 'config.yml']
        for config_file in config_files:
            if config_file in files:
                try:
                    if config_file.endswith(('.yaml', '.yml')):
                        with open(path / config_file, 'r') as f:
                            yaml_data = yaml.safe_load(f)
                            if yaml_data:
                                config_info.update(yaml_data)
                except Exception as e:
                    logger.warning(f"Error reading {config_file} in {path}: {e}")
        
        return config_info
    
    async def _determine_start_command(self, path: Path, project_type: str, main_file: str) -> str:
        """Determine the command to start the project"""
        
        commands = {
            'flask': f"cd {path} && python {main_file}",
            'fastapi': f"cd {path} && python {main_file}",
            'streamlit': f"cd {path} && streamlit run {main_file}",
            'django': f"cd {path} && python manage.py runserver",
            'react': f"cd {path} && npm start",
            'vue': f"cd {path} && npm run serve",
            'static': f"cd {path} && python -m http.server"
        }
        
        # Check for custom start scripts
        if (path / 'start.sh').exists():
            return f"cd {path} && ./start.sh"
        elif (path / 'run.sh').exists():
            return f"cd {path} && ./run.sh"
        elif (path / 'package.json').exists():
            # Check for npm scripts
            try:
                with open(path / 'package.json', 'r') as f:
                    package_data = json.load(f)
                    scripts = package_data.get('scripts', {})
                    if 'dev' in scripts:
                        return f"cd {path} && npm run dev"
                    elif 'serve' in scripts:
                        return f"cd {path} && npm run serve"
                    elif 'start' in scripts:
                        return f"cd {path} && npm start"
            except:
                pass
        
        return commands.get(project_type, f"cd {path} && python {main_file}")
    
    async def _determine_port(self, path: Path, project_type: str, config_info: Dict) -> Optional[int]:
        """Determine the port the project runs on"""
        
        # Check config info first
        if 'port' in config_info:
            return config_info['port']
        
        # Check for port in various files
        port_files = ['app.py', 'main.py', 'run.py']
        for file_name in port_files:
            file_path = path / file_name
            if file_path.exists():
                try:
                    with open(file_path, 'r') as f:
                        content = f.read()
                        # Look for port definitions
                        port_patterns = [
                            r'port[=:]?\s*(\d+)',
                            r'PORT[=:]?\s*(\d+)',
                            r'\.run\([^)]*port[=:]?\s*(\d+)',
                            r'uvicorn\.run\([^)]*port[=:]?\s*(\d+)'
                        ]
                        for pattern in port_patterns:
                            match = re.search(pattern, content)
                            if match:
                                return int(match.group(1))
                except Exception as e:
                    logger.debug(f"Error reading {file_path}: {e}")
        
        # Return default port for project type
        default_ports = self.port_patterns.get(project_type, [8000])
        return default_ports[0]
    
    async def _extract_brand_info(self, path: Path) -> Optional[str]:
        """Extract brand information from project directory"""
        
        # Look for brand indicators in path name
        brand_indicators = {
            'buildly': 'Buildly Labs',
            'openbuild': 'OpenBuild',
            'oregon': 'Oregon Software',
            'portfolio': 'Portfolio',
            'personal': 'Personal',
            'marketing': 'Marketing Hub'
        }
        
        path_lower = str(path).lower()
        for indicator, brand in brand_indicators.items():
            if indicator in path_lower:
                return brand
        
        return None
    
    async def _discover_github_pages_sites(self) -> List[DashboardProject]:
        """Discover GitHub Pages deployments"""
        projects = []
        
        # Look for GitHub Pages configuration
        github_sites = [
            {
                'name': 'buildly-website',
                'brand': 'Buildly Labs',
                'github_pages_url': 'https://buildlylabs.github.io/website',
                'description': 'Buildly Labs main website'
            },
            {
                'name': 'openbuild-website', 
                'brand': 'OpenBuild',
                'github_pages_url': 'https://openbuild.github.io',
                'description': 'OpenBuild community website'
            },
            {
                'name': 'oregon-software-site',
                'brand': 'Oregon Software',
                'github_pages_url': 'https://oregon-software.github.io',
                'description': 'Oregon Software company website'
            }
        ]
        
        for site in github_sites:
            project = DashboardProject(
                name=site['name'],
                path="",  # GitHub Pages, no local path
                type="github_pages",
                url=site['github_pages_url'],
                github_pages_url=site['github_pages_url'],
                brand=site['brand'],
                description=site['description']
            )
            projects.append(project)
        
        return projects
    
    async def _discover_brand_websites(self):
        """Discover brand website deployments"""
        
        # This would typically read from a configuration file or scan for deployment configs
        brand_sites = [
            BrandWebsite(
                name="Buildly Labs Website",
                brand="Buildly Labs",
                live_url="https://buildlylabs.com",
                github_repo="buildlylabs/website",
                deployment_type="github_pages"
            ),
            BrandWebsite(
                name="OpenBuild Platform",
                brand="OpenBuild", 
                live_url="https://openbuild.xyz",
                deployment_type="custom"
            ),
            BrandWebsite(
                name="Oregon Software",
                brand="Oregon Software",
                live_url="https://oregon-software.com",
                deployment_type="github_pages"
            )
        ]
        
        for site in brand_sites:
            await self._check_website_status(site)
        
        self.brand_websites = brand_sites
    
    async def _update_project_status(self, project: DashboardProject):
        """Update the status of a project"""
        if project.type == "github_pages":
            await self._check_github_pages_status(project)
        else:
            await self._check_local_project_status(project)
    
    async def _check_local_project_status(self, project: DashboardProject):
        """Check if a local project is running"""
        # Check if process is running on the expected port
        if project.port:
            for proc in psutil.process_iter(['pid', 'name', 'connections']):
                try:
                    for conn in proc.info['connections'] or []:
                        if conn.laddr.port == project.port:
                            project.status = "running"
                            project.pid = proc.info['pid']
                            
                            # Health check if endpoint available
                            if project.health_endpoint and project.url:
                                health_url = f"{project.url}{project.health_endpoint}"
                                if await self._health_check(health_url):
                                    project.status = "running"
                                else:
                                    project.status = "error"
                            return
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        
        project.status = "stopped"
        project.pid = None
    
    async def _check_github_pages_status(self, project: DashboardProject):
        """Check GitHub Pages deployment status"""
        if project.github_pages_url:
            if await self._health_check(project.github_pages_url):
                project.status = "running"
            else:
                project.status = "error"
    
    async def _check_website_status(self, website: BrandWebsite):
        """Check brand website status"""
        if await self._health_check(website.live_url):
            website.status = "online"
        else:
            website.status = "offline"
    
    async def _health_check(self, url: str) -> bool:
        """Perform health check on a URL"""
        try:
            async with self.session.get(url, timeout=10) as response:
                return response.status < 400
        except Exception:
            return False
    
    async def start_project(self, project_name: str) -> Dict[str, Any]:
        """Start a dashboard project"""
        project = next((p for p in self.discovered_projects if p.name == project_name), None)
        
        if not project:
            return {"success": False, "error": "Project not found"}
        
        if project.type == "github_pages":
            return {"success": False, "error": "Cannot start GitHub Pages projects locally"}
        
        if project.status == "running":
            return {"success": False, "error": "Project already running"}
        
        try:
            # Start the project
            process = subprocess.Popen(
                project.start_command,
                shell=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=os.setsid  # Create new process group
            )
            
            # Give it a moment to start
            await asyncio.sleep(2)
            
            # Update status
            await self._update_project_status(project)
            
            return {
                "success": True,
                "pid": process.pid,
                "status": project.status,
                "url": project.url
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def stop_project(self, project_name: str) -> Dict[str, Any]:
        """Stop a dashboard project"""
        project = next((p for p in self.discovered_projects if p.name == project_name), None)
        
        if not project:
            return {"success": False, "error": "Project not found"}
        
        if project.status != "running" or not project.pid:
            return {"success": False, "error": "Project not running"}
        
        try:
            # Kill process group
            os.killpg(os.getpgid(project.pid), signal.SIGTERM)
            
            # Wait and check if it stopped
            await asyncio.sleep(1)
            await self._update_project_status(project)
            
            return {"success": True, "status": project.status}
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    async def get_dashboard_overview(self) -> Dict[str, Any]:
        """Get complete overview of all dashboards and websites"""
        
        # Refresh all project statuses
        for project in self.discovered_projects:
            await self._update_project_status(project)
        
        # Refresh website statuses
        for website in self.brand_websites:
            await self._check_website_status(website)
        
        # Organize by status
        running_projects = [p for p in self.discovered_projects if p.status == "running"]
        stopped_projects = [p for p in self.discovered_projects if p.status == "stopped"]
        error_projects = [p for p in self.discovered_projects if p.status == "error"]
        
        online_websites = [w for w in self.brand_websites if w.status == "online"]
        offline_websites = [w for w in self.brand_websites if w.status == "offline"]
        
        return {
            "projects": {
                "total": len(self.discovered_projects),
                "running": len(running_projects),
                "stopped": len(stopped_projects),
                "error": len(error_projects),
                "details": [asdict(p) for p in self.discovered_projects]
            },
            "websites": {
                "total": len(self.brand_websites),
                "online": len(online_websites),
                "offline": len(offline_websites),
                "details": [asdict(w) for w in self.brand_websites]
            },
            "last_updated": datetime.now().isoformat()
        }

# Utility functions for API integration
async def discover_dashboards() -> Dict[str, Any]:
    """Main function to discover all dashboards - for API use"""
    async with DashboardManager() as manager:
        await manager.discover_all_projects()
        return await manager.get_dashboard_overview()

async def start_dashboard(project_name: str) -> Dict[str, Any]:
    """Start a specific dashboard - for API use"""
    async with DashboardManager() as manager:
        await manager.discover_all_projects()
        return await manager.start_project(project_name)

async def stop_dashboard(project_name: str) -> Dict[str, Any]:
    """Stop a specific dashboard - for API use"""
    async with DashboardManager() as manager:
        await manager.discover_all_projects()
        return await manager.stop_project(project_name)

if __name__ == "__main__":
    # Test the dashboard discovery
    async def test_discovery():
        async with DashboardManager() as manager:
            projects = await manager.discover_all_projects()
            overview = await manager.get_dashboard_overview()
            
            print("🎯 Dashboard Discovery Results:")
            print(f"Found {len(projects)} projects")
            print("\n📊 Overview:")
            print(json.dumps(overview, indent=2, default=str))
    
    asyncio.run(test_discovery())