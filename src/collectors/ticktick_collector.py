"""
TickTick data collector for fetching tasks and projects.
"""

import asyncio
import logging
import base64
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set
from urllib.parse import quote

import httpx

# Import database functions
try:
    from database import get_credentials, save_credentials, get_auth_token, save_auth_token
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

logger = logging.getLogger(__name__)


class TickTickCollector:
    """Collects tasks from TickTick using their API."""
    
    def __init__(self, settings=None):
        """Initialize TickTick collector with settings."""
        self.settings = settings
        self.base_url = "https://api.ticktick.com/open/v1"
        self.auth_url = "https://ticktick.com/oauth"
        
        # Get credentials from database first, fallback to env vars
        self.client_id = None
        self.client_secret = None
        self.redirect_uri = "http://localhost:8008"
        
        if DATABASE_AVAILABLE:
            creds = get_credentials('ticktick')
            if creds:
                self.client_id = creds.get('client_id')
                self.client_secret = creds.get('client_secret')
        
        # Fallback to environment variables if not in database
        if not self.client_id:
            self.client_id = os.getenv("TICKTICK_CLIENT_ID")
        if not self.client_secret:
            self.client_secret = os.getenv("TICKTICK_CLIENT_SECRET")
        
        # Check for direct API token
        self.api_token = os.getenv("TICKTICK_API_TOKEN")
        if DATABASE_AVAILABLE:
            creds = get_credentials('ticktick')
            if creds and creds.get('api_token'):
                self.api_token = creds.get('api_token')
        
        # If no API token and no client_secret, warn user
        if not self.api_token and not self.client_secret:
            logger.warning("TickTick: No API token or client credentials found. Configure credentials in Settings or set TICKTICK_API_TOKEN environment variable.")
        
    def get_auth_url(self, state: str = None) -> str:
        """Generate OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "scope": "tasks:write tasks:read",
            "response_type": "code",
            "redirect_uri": self.redirect_uri
        }
        if state:
            params["state"] = state
            
        query_string = "&".join([f"{k}={quote(str(v))}" for k, v in params.items()])
        return f"{self.auth_url}/authorize?{query_string}"
    
    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        # Create basic auth header
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode('utf-8')
        auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": self.redirect_uri
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.auth_url}/token",
                headers=headers,
                data=data
            )
            
            if response.status_code == 200:
                token_data = response.json()
                
                # Save token to database
                if DATABASE_AVAILABLE:
                    expires_at = datetime.now() + timedelta(seconds=token_data.get('expires_in', 3600))
                    save_auth_token('ticktick', token_data, expires_at)
                    
                return token_data
            else:
                logger.error(f"Token exchange failed: {response.status_code} - {response.text}")
                raise Exception(f"Token exchange failed: {response.status_code}")
    
    async def get_access_token(self) -> Optional[str]:
        """Get valid access token from database, settings, or direct token."""
        # First check for direct API token (simplest approach)
        if self.api_token:
            return self.api_token
            
        # Then check OAuth tokens in database
        if DATABASE_AVAILABLE:
            token_data = get_auth_token('ticktick')
            if token_data:
                return token_data.get('access_token')
        
        # Fallback to credentials database
        if DATABASE_AVAILABLE:
            creds = get_credentials("ticktick")
            if creds:
                return creds.get("access_token")
                
        return None
    
    async def refresh_access_token(self) -> Optional[str]:
        """Refresh access token using refresh token."""
        if not DATABASE_AVAILABLE:
            return None
            
        token_data = get_auth_token('ticktick')
        if not token_data or 'refresh_token' not in token_data:
            return None
            
        # Create basic auth header
        auth_string = f"{self.client_id}:{self.client_secret}"
        auth_bytes = auth_string.encode('utf-8')
        auth_b64 = base64.b64encode(auth_bytes).decode('utf-8')
        
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = {
            "grant_type": "refresh_token",
            "refresh_token": token_data['refresh_token']
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.auth_url}/token",
                    headers=headers,
                    data=data
                )
                
                if response.status_code == 200:
                    new_token_data = response.json()
                    expires_at = datetime.now() + timedelta(seconds=new_token_data.get('expires_in', 3600))
                    save_auth_token('ticktick', new_token_data, expires_at)
                    return new_token_data.get('access_token')
                    
        except Exception as e:
            logger.error(f"Token refresh failed: {e}")
            
        return None
    
    async def make_authenticated_request(self, endpoint: str, method: str = "GET", **kwargs) -> Optional[Dict[str, Any]]:
        """Make authenticated request to TickTick API."""
        access_token = await self.get_access_token()
        
        if not access_token:
            logger.warning("No TickTick access token available")
            return None
            
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        if 'headers' in kwargs:
            headers.update(kwargs['headers'])
            del kwargs['headers']
            
        async with httpx.AsyncClient() as client:
            try:
                response = await client.request(
                    method,
                    f"{self.base_url}/{endpoint}",
                    headers=headers,
                    **kwargs
                )
                
                if response.status_code == 401:
                    # Try to refresh token
                    new_token = await self.refresh_access_token()
                    if new_token:
                        headers["Authorization"] = f"Bearer {new_token}"
                        response = await client.request(
                            method,
                            f"{self.base_url}/{endpoint}",
                            headers=headers,
                            **kwargs
                        )
                    else:
                        logger.error("Unable to refresh TickTick token")
                        return None
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"TickTick API error: {response.status_code} - {response.text}")
                    return None
                    
            except Exception as e:
                logger.error(f"TickTick API request failed: {e}")
                return None
    
    async def collect_tasks(self, start_date: datetime = None, end_date: datetime = None) -> List[Dict[str, Any]]:
        """Collect tasks from TickTick."""
        try:
            # Get all projects first
            projects_data = await self.make_authenticated_request("project")
            projects = {}
            
            if projects_data:
                for project in projects_data:
                    projects[project['id']] = project['name']
            
            # Get all tasks
            tasks_data = await self.make_authenticated_request("task")
            
            if not tasks_data:
                logger.warning("No tasks data received from TickTick")
                return []
            
            tasks = []
            
            for task in tasks_data:
                # Parse task data
                task_info = {
                    "id": task.get("id"),
                    "title": task.get("title", ""),
                    "content": task.get("content", ""),
                    "completed": task.get("status") == 2,  # TickTick uses status 2 for completed
                    "priority": self._map_priority(task.get("priority", 0)),
                    "due_date": task.get("dueDate"),
                    "created_date": task.get("createdTime"),
                    "modified_date": task.get("modifiedTime"),
                    "project_id": task.get("projectId"),
                    "project_name": projects.get(task.get("projectId"), "Inbox"),
                    "tags": task.get("tags", []),
                    "url": f"https://ticktick.com/webapp/#p/{task.get('projectId')}/tasks/{task.get('id')}",
                    "source": "TickTick"
                }
                
                # Filter by date range if specified
                if start_date or end_date:
                    task_date = None
                    if task.get("dueDate"):
                        try:
                            task_date = datetime.fromisoformat(task["dueDate"].replace('Z', '+00:00'))
                        except:
                            pass
                    
                    if not task_date and task.get("createdTime"):
                        try:
                            task_date = datetime.fromisoformat(task["createdTime"].replace('Z', '+00:00'))
                        except:
                            pass
                    
                    if task_date:
                        if start_date and task_date < start_date:
                            continue
                        if end_date and task_date > end_date:
                            continue
                
                tasks.append(task_info)
            
            logger.info(f"Collected {len(tasks)} tasks from TickTick")
            return tasks
            
        except Exception as e:
            logger.error(f"Error collecting TickTick tasks: {e}")
            return []
    
    def _map_priority(self, priority: int) -> str:
        """Map TickTick priority to string."""
        priority_map = {
            0: "none",
            1: "low", 
            3: "medium",
            5: "high"
        }
        return priority_map.get(priority, "none")
    
    async def collect_projects(self) -> List[Dict[str, Any]]:
        """Collect projects from TickTick."""
        try:
            projects_data = await self.make_authenticated_request("project")
            
            if not projects_data:
                return []
            
            projects = []
            for project in projects_data:
                project_info = {
                    "id": project.get("id"),
                    "name": project.get("name", ""),
                    "color": project.get("color"),
                    "is_inbox": project.get("inboxProject", False),
                    "task_count": project.get("taskCount", 0),
                    "closed": project.get("closed", False),
                    "created_date": project.get("createdTime"),
                    "modified_date": project.get("modifiedTime"),
                    "source": "TickTick"
                }
                projects.append(project_info)
            
            logger.info(f"Collected {len(projects)} projects from TickTick")
            return projects
            
        except Exception as e:
            logger.error(f"Error collecting TickTick projects: {e}")
            return []
    
    async def get_task_statistics(self) -> Dict[str, Any]:
        """Get task statistics from TickTick."""
        try:
            tasks = await self.collect_tasks()
            
            if not tasks:
                return {
                    "total_tasks": 0,
                    "completed_tasks": 0,
                    "pending_tasks": 0,
                    "overdue_tasks": 0,
                    "today_tasks": 0,
                    "this_week_tasks": 0,
                    "priority_breakdown": {"none": 0, "low": 0, "medium": 0, "high": 0}
                }
            
            now = datetime.now()
            today = now.date()
            week_start = today - timedelta(days=today.weekday())
            
            stats = {
                "total_tasks": len(tasks),
                "completed_tasks": sum(1 for task in tasks if task["completed"]),
                "pending_tasks": sum(1 for task in tasks if not task["completed"]),
                "overdue_tasks": 0,
                "today_tasks": 0,
                "this_week_tasks": 0,
                "priority_breakdown": {"none": 0, "low": 0, "medium": 0, "high": 0}
            }
            
            for task in tasks:
                # Count priorities
                priority = task.get("priority", "none")
                if priority in stats["priority_breakdown"]:
                    stats["priority_breakdown"][priority] += 1
                
                # Check due dates
                if task.get("due_date") and not task["completed"]:
                    try:
                        due_date = datetime.fromisoformat(task["due_date"].replace('Z', '+00:00')).date()
                        
                        if due_date < today:
                            stats["overdue_tasks"] += 1
                        elif due_date == today:
                            stats["today_tasks"] += 1
                        elif due_date >= week_start and due_date <= today + timedelta(days=6):
                            stats["this_week_tasks"] += 1
                    except:
                        pass
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting TickTick statistics: {e}")
            return {
                "total_tasks": 0,
                "completed_tasks": 0,
                "pending_tasks": 0,
                "overdue_tasks": 0,
                "today_tasks": 0,
                "this_week_tasks": 0,
                "priority_breakdown": {"none": 0, "low": 0, "medium": 0, "high": 0}
            }
    
    async def is_authenticated(self) -> bool:
        """Check if TickTick is properly authenticated."""
        access_token = await self.get_access_token()
        if not access_token:
            return False
            
        # Test with a simple API call
        result = await self.make_authenticated_request("project")
        return result is not None
    
    async def create_task(self, title: str, content: str = "", project_id: str = None, 
                         due_date: datetime = None, priority: int = 0, tags: List[str] = None) -> Optional[Dict[str, Any]]:
        """Create a new task in TickTick."""
        try:
            if not await self.is_authenticated():
                logger.warning("TickTick not authenticated - cannot create task")
                return None
            
            # Prepare task data
            task_data = {
                "title": title,
                "content": content or "",
                "timeZone": "America/Los_Angeles",  # Adjust as needed
                "priority": priority  # 0=None, 1=Low, 3=Medium, 5=High
            }
            
            if project_id:
                task_data["projectId"] = project_id
            
            if due_date:
                task_data["dueDate"] = due_date.isoformat()
            
            if tags:
                task_data["tags"] = tags
            
            # Make API request to create task
            result = await self.make_authenticated_request("task", method="POST", json=task_data)
            
            if result:
                logger.info(f"Successfully created TickTick task: {title}")
                return result
            else:
                logger.error(f"Failed to create TickTick task: {title}")
                return None
                
        except Exception as e:
            logger.error(f"Error creating TickTick task '{title}': {e}")
            return None
    
    async def get_existing_task_titles(self) -> Set[str]:
        """Get titles of all existing tasks to avoid duplicates."""
        try:
            tasks = await self.collect_tasks()
            return {task.get("title", "").lower() for task in tasks}
        except Exception as e:
            logger.error(f"Error getting existing task titles: {e}")
            return set()

    async def collect_data(self) -> Dict[str, Any]:
        """Collect TickTick data (tasks and projects)."""
        try:
            if not await self.is_authenticated():
                logger.warning("TickTick not authenticated")
                return {
                    "tasks": [],
                    "projects": [],
                    "authenticated": False,
                    "error": "Not authenticated"
                }
            
            # Collect tasks and projects
            tasks = await self.collect_tasks()
            projects = await self.collect_projects()
            stats = await self.get_task_statistics()
            
            return {
                "tasks": tasks,
                "projects": projects,
                "statistics": stats,
                "authenticated": True,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error in TickTick collect_data: {e}")
            return {
                "tasks": [],
                "projects": [],
                "authenticated": False,
                "error": str(e)
            }
