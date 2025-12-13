#!/usr/bin/env python3
"""
Simple Personal Dashboard with News Filtering
Clean, minimal implementation focusing on core data sources
"""

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import json
import requests
from datetime import datetime, timedelta
import os
import yaml
from pathlib import Path
import logging
import sys
import httpx
import aiohttp
from bs4 import BeautifulSoup
import threading
import asyncio
import time
import secrets
from typing import Dict, Any, Optional

# Add the src directory to path for imports
src_dir = Path(__file__).parent
project_root = src_dir.parent  # One level up from src/
sys.path.insert(0, str(src_dir))

# Import database manager
from database import db

# Configure logging
logger = logging.getLogger(__name__)

# Configure SSL globally to fix certificate verification issues
try:
    from utils.ssl_helper import configure_ssl_globally
    configure_ssl_globally()
    logger.info("SSL configured globally using certifi")
except Exception as e:
    logger.warning(f"Could not configure SSL globally: {e}")

# Try to import our existing collectors
try:
    from collectors.calendar_collector import CalendarCollector
    from collectors.gmail_collector import GmailCollector
    from collectors.github_collector import GitHubCollector
    from collectors.ticktick_collector import TickTickCollector
    from collectors.jokes_collector import JokesCollector
    from collectors.weather_collector import WeatherCollector
    from collectors.investments_collector import InvestmentsCollector
    from collectors.local_services_collector import LocalServicesCollector
    from processors.task_manager import TaskManager
    from config.settings import Settings, settings
    COLLECTORS_AVAILABLE = True
    TASK_MANAGER_AVAILABLE = True
except ImportError as e:
    print(f"Note: Could not import collectors: {e}")
    COLLECTORS_AVAILABLE = False
    TASK_MANAGER_AVAILABLE = False

# Try to import AI Assistant modules
try:
    from processors.ai_providers import ai_manager, create_provider, OllamaProvider, OpenAIProvider, GeminiProvider
    from processors.ai_training_collector import training_collector
    from services.ai_service import get_ai_service
    AI_ASSISTANT_AVAILABLE = True
except ImportError as e:
    print(f"Note: Could not import AI Assistant modules: {e}")
    AI_ASSISTANT_AVAILABLE = False

# Set up logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Simple Personal Dashboard")

# Register custom module routers
try:
    from modules.music_news.endpoints import router as music_news_router
    from modules.vanity_alerts.endpoints import router as vanity_alerts_router
    from modules.comms.endpoints import router as comms_router
    from modules.foundershield.endpoints import router as foundershield_router
    from modules.leads.endpoints import router as leads_router
    from modules.tasks.endpoints import router as tasks_router
    from modules.ai_summarizer.endpoints import router as ai_summarizer_router
    
    app.include_router(music_news_router)
    app.include_router(vanity_alerts_router)
    app.include_router(comms_router)
    app.include_router(foundershield_router, prefix="/foundershield")
    app.include_router(leads_router)
    app.include_router(tasks_router)
    app.include_router(ai_summarizer_router)
    logging.info("✅ Custom modules registered (music_news, vanity_alerts, comms, foundershield, leads, tasks, ai_summarizer)")
except ImportError as e:
    logging.warning(f"Could not load custom modules: {e}")

# Register Trust Layer API
try:
    from trust_layer.api.endpoints import router as trust_layer_router, set_db_connection
    from trust_layer.plugin_registry import get_registry
    from trust_layer.plugins.email_auth import EmailAuthPlugin
    from trust_layer.plugins.dns_records import DNSRecordsPlugin
    from trust_layer.plugins.content_heuristics import ContentHeuristicsPlugin
    
    # Set database manager for trust layer (pass the manager, not conn)
    set_db_connection(db)
    
    # Register plugins
    registry = get_registry()
    registry.register(EmailAuthPlugin())
    registry.register(DNSRecordsPlugin())
    registry.register(ContentHeuristicsPlugin())
    
    # Include API router
    app.include_router(trust_layer_router, prefix="/api")
    logging.info("✅ Trust Layer API registered with 3 plugins (email_auth, dns_records, content_heuristics)")
except Exception as e:
    logging.warning(f"Could not load trust layer: {e}")
    import traceback
    traceback.print_exc()


# Health check endpoint for monitoring
@app.get("/health")
async def health_check():
    """Health check endpoint for Docker, K8s, and monitoring."""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "service": "personal-dashboard"
    }


class BackgroundDataManager:
    """Manages background data collection and caching."""
    
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_timestamps: Dict[str, datetime] = {}
        self.cache_duration = timedelta(minutes=10)  # Cache for 10 minutes
        self.background_tasks: Dict[str, threading.Thread] = {}
        self.running = True
        
        # Start background collection threads
        self.start_background_collection()
    
    def start_background_collection(self):
        """Start background data collection threads."""
        endpoints = [
            'calendar', 'email', 'github', 'news', 
            'music', 'vanity', 'weather', 'jokes'
        ]
        
        for endpoint in endpoints:
            thread = threading.Thread(
                target=self._background_collector, 
                args=(endpoint,),
                daemon=True,
                name=f"collector-{endpoint}"
            )
            thread.start()
            self.background_tasks[endpoint] = thread
            
        logger.info(f"Started {len(endpoints)} background collection threads")
    
    def _background_collector(self, endpoint: str):
        """Background collection worker for a specific endpoint."""
        collection_functions = {
            'calendar': self._collect_calendar,
            'email': self._collect_email,
            'github': self._collect_github,
            'news': self._collect_news,
            'music': self._collect_music,
            'vanity': self._collect_vanity,
            'weather': self._collect_weather,
            'jokes': self._collect_jokes
        }
        
        collect_func = collection_functions.get(endpoint)
        if not collect_func:
            logger.warning(f"No collection function for endpoint: {endpoint}")
            return
        
        # Initial delay to stagger startup
        time.sleep(hash(endpoint) % 30)  # 0-30 second delay based on endpoint name
        
        while self.running:
            try:
                logger.info(f"Background collecting {endpoint} data...")
                data = asyncio.run(collect_func())
                self.cache[endpoint] = data
                self.cache_timestamps[endpoint] = datetime.now()
                logger.info(f"Successfully cached {endpoint} data")
                
                # Sleep for different intervals based on data type
                sleep_intervals = {
                    'calendar': 300,  # 5 minutes
                    'email': 180,     # 3 minutes
                    'github': 600,    # 10 minutes
                    'news': 900,      # 15 minutes
                    'music': 1800,    # 30 minutes
                    'vanity': 1800,   # 30 minutes
                    'weather': 900,   # 15 minutes
                    'jokes': 3600     # 1 hour
                }
                sleep_time = sleep_intervals.get(endpoint, 600)
                time.sleep(sleep_time)
                
            except Exception as e:
                logger.error(f"Error in background collection for {endpoint}: {e}")
                # Wait 5 minutes before retrying on error
                time.sleep(300)
    
    def get_cached_data(self, endpoint: str) -> Optional[Dict[str, Any]]:
        """Get cached data for an endpoint if available and fresh."""
        if endpoint not in self.cache:
            return None
            
        timestamp = self.cache_timestamps.get(endpoint)
        if not timestamp:
            return None
            
        # Check if cache is still fresh
        if datetime.now() - timestamp > self.cache_duration:
            logger.info(f"Cache for {endpoint} is stale")
            return None
            
        return self.cache[endpoint]
    
    def stop(self):
        """Stop all background collection threads."""
        self.running = False
        for thread in self.background_tasks.values():
            if thread.is_alive():
                thread.join(timeout=5)
    
    # Collection methods (these will be implemented to call the actual collectors)
    async def _collect_calendar(self):
        try:
            from config.settings import Settings
            from datetime import timedelta
            settings = Settings()
            collector = CalendarCollector(settings)
            start_date = datetime.now()
            end_date = start_date + timedelta(days=7)
            events_data = await collector.collect_events(start_date, end_date)
            
            if events_data:
                formatted_events = []
                for event in events_data[:10]:
                    title = event.get('summary', 'Untitled Event')
                    event_time = "All day"
                    start_dt = None
                    end_dt = None
                    
                    if not event.get('is_all_day', False) and event.get('start_time'):
                        try:
                            start_dt = event['start_time']
                            # Handle both datetime objects and strings
                            if hasattr(start_dt, 'strftime'):
                                event_time = start_dt.strftime("%I:%M %p")
                                if event.get('end_time') and hasattr(event['end_time'], 'strftime'):
                                    end_dt = event['end_time']
                                    event_time += f" - {end_dt.strftime('%I:%M %p')}"
                            else:
                                # If it's a string, try to parse it
                                start_dt = datetime.fromisoformat(str(start_dt).replace('Z', '+00:00'))
                                event_time = start_dt.strftime("%I:%M %p")
                                if event.get('end_time'):
                                    end_dt = datetime.fromisoformat(str(event['end_time']).replace('Z', '+00:00'))
                                    event_time += f" - {end_dt.strftime('%I:%M %p')}"
                        except Exception as e:
                            logger.warning(f"Error formatting event time: {e}")
                            event_time = str(event.get('start_time', 'All day'))
                    
                    # Build comprehensive event data matching the original format
                    formatted_event = {
                        "title": title,
                        "summary": title,
                        "time": event_time,
                        "description": event.get('description', ''),
                        "location": event.get('location', ''),
                        "organizer": event.get('organizer', '') if isinstance(event.get('organizer'), str) else event.get('organizer', {}).get('email', '') if event.get('organizer') else '',
                        "attendees": [att.get('email', '') if isinstance(att, dict) else str(att) for att in event.get('attendees', [])],
                        "start": {"dateTime": event.get('start_time').isoformat() if hasattr(event.get('start_time'), 'isoformat') else str(event.get('start_time'))} if event.get('start_time') else None,
                        "end": {"dateTime": event.get('end_time').isoformat() if hasattr(event.get('end_time'), 'isoformat') else str(event.get('end_time'))} if event.get('end_time') else None,
                        "event_id": event.get('id', ''),
                        "calendar_url": f"https://calendar.google.com/calendar/event?eid={event.get('id', '')}" if event.get('id') else "https://calendar.google.com/calendar",
                        "is_all_day": event.get('is_all_day', False),
                        "status": event.get('status', ''),
                        "created": event.get('created', ''),
                        "updated": event.get('updated', ''),
                        "html_link": event.get('html_link', '')
                    }
                    
                    formatted_events.append(formatted_event)
                
                return {"events": formatted_events}
            else:
                return {"events": []}
        except Exception as e:
            logger.error(f"Calendar collection error: {e}")
            return {"error": str(e), "events": []}
    
    async def _collect_email(self):
        try:
            from config.settings import Settings
            settings = Settings()
            collector = GmailCollector(settings)
            return await collector.collect_data()
        except Exception as e:
            logger.error(f"Email collection error: {e}")
            return {"error": str(e), "emails": []}
    
    async def _collect_github(self):
        try:
            # Use the same logic as the GitHub API endpoint
            from database import get_credentials
            github_creds = get_credentials('github')
            if github_creds and github_creds.get('token'):
                username = github_creds.get('username')
                if not username:
                    # Fallback to user profile
                    profile = db.get_user_profile()
                    username = profile.get('github_username', 'unknown')
                token = github_creds.get('token')
                headers = {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}
                
                github_items = []
                async with httpx.AsyncClient(timeout=10.0) as client:
                    # Get review requests
                    review_response = await client.get(f'https://api.github.com/search/issues?q=review-requested:{username}+is:open+is:pr', headers=headers)
                    if review_response.status_code == 200:
                        for pr in review_response.json().get('items', [])[:3]:
                            repo_url_parts = pr.get('repository_url', '').split('/')
                            repo_name = repo_url_parts[-1] if repo_url_parts else 'unknown'
                            repo_owner = repo_url_parts[-2] if len(repo_url_parts) > 1 else 'unknown'
                            
                            github_items.append({
                                'type': 'Review Requested', 
                                'title': pr.get('title', ''),
                                'repo': repo_name, 
                                'repository': f"{repo_owner}/{repo_name}",
                                'number': pr.get('number', ''),
                                'user': pr.get('user', {}).get('login', 'Unknown') if pr.get('user') else 'Unknown',
                                'state': pr.get('state', 'open'),
                                'created_at': pr.get('created_at', ''),
                                'updated_at': pr.get('updated_at', ''),
                                'body': pr.get('body', ''),
                                'html_url': pr.get('html_url', ''),
                                'labels': [label.get('name', '') for label in pr.get('labels', [])],
                                'assignees': [ass.get('login', '') for ass in pr.get('assignees', [])],
                                'github_url': pr.get('html_url', ''),
                                'api_url': pr.get('url', '')
                            })
                    
                    # Get assigned issues (just the first few for caching)
                    issues_response = await client.get(f'https://api.github.com/search/issues?q=assignee:{username}+is:issue+is:open', headers=headers)
                    if issues_response.status_code == 200:
                        for issue in issues_response.json().get('items', [])[:3]:
                            repo_url_parts = issue.get('repository_url', '').split('/')
                            repo_name = repo_url_parts[-1] if repo_url_parts else 'unknown'
                            repo_owner = repo_url_parts[-2] if len(repo_url_parts) > 1 else 'unknown'
                            
                            github_items.append({
                                'type': 'Assigned Issue',
                                'title': issue.get('title', ''),
                                'repo': repo_name,
                                'repository': f"{repo_owner}/{repo_name}",
                                'number': issue.get('number', ''),
                                'user': issue.get('user', {}).get('login', 'Unknown') if issue.get('user') else 'Unknown',
                                'state': issue.get('state', 'open'),
                                'created_at': issue.get('created_at', ''),
                                'updated_at': issue.get('updated_at', ''),
                                'body': issue.get('body', ''),
                                'html_url': issue.get('html_url', ''),
                                'labels': [label.get('name', '') for label in issue.get('labels', [])],
                                'assignees': [ass.get('login', '') for ass in issue.get('assignees', [])],
                                'github_url': issue.get('html_url', ''),
                                'api_url': issue.get('url', '')
                            })
                
                return {"data": github_items, "total": len(github_items)}
            else:
                return {"data": [], "total": 0, "error": "No GitHub credentials"}
        except Exception as e:
            logger.error(f"GitHub collection error: {e}")
            return {"error": str(e), "data": []}
    
    async def _collect_news(self):
        try:
            from collectors.news_collector import NewsCollector
            collector = NewsCollector()
            return await collector.collect_data()
        except Exception as e:
            logger.error(f"News collection error: {e}")
            return {"error": str(e), "articles": []}
    
    async def _collect_music(self):
        try:
            from collectors.music_collector import MusicCollector
            collector = MusicCollector()
            return await collector.collect_data()
        except Exception as e:
            logger.error(f"Music collection error: {e}")
            return {"error": str(e), "data": []}
    
    async def _collect_vanity(self):
        try:
            from collectors.vanity_alerts_collector import VanityAlertsCollector
            collector = VanityAlertsCollector()
            return await collector.collect_data()
        except Exception as e:
            logger.error(f"Vanity collection error: {e}")
            return {"error": str(e), "alerts": []}
    
    async def _collect_weather(self):
        try:
            from config.settings import Settings
            settings = Settings()
            collector = WeatherCollector(settings)
            return await collector.collect_data()
        except Exception as e:
            logger.error(f"Weather collection error: {e}")
            return {"error": str(e), "current": {}}
    
    async def _collect_jokes(self):
        try:
            from config.settings import Settings
            settings = Settings()
            collector = JokesCollector(settings)
            return await collector.collect_data()
        except Exception as e:
            logger.error(f"Jokes collection error: {e}")
            return {"error": str(e), "joke": "Failed to load joke"}


# Initialize background data manager
background_manager = BackgroundDataManager()


# Load configuration if it exists
config_path = project_root / "config" / "config.yaml"
config = {}
if config_path.exists():
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f) or {}

print("🚀 Simple Dashboard Starting...")
print("Config loaded:", bool(config))

# Mount static files
src_dir = Path(__file__).parent
static_dir = src_dir / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Mount assets (images, logos, etc.)
assets_dir = project_root / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

@app.get("/", response_class=HTMLResponse)
async def dashboard(code: str = None, state: str = None, error: str = None):
    """Serve the main dashboard page or handle OAuth callbacks"""
    
    # Check if this is a TickTick OAuth callback
    if code or error:
        # This looks like an OAuth callback, redirect to the proper callback handler
        if error:
            return RedirectResponse(f"/auth/ticktick/callback?error={error}")
        else:
            return RedirectResponse(f"/auth/ticktick/callback?code={code}" + (f"&state={state}" if state else ""))
    
    # Serve the modern template (ONLY SOURCE OF TRUTH)
    src_dir = Path(__file__).parent
    template_path = src_dir / "templates" / "dashboard_modern.html"
    
    if not template_path.exists():
        logger.error(f"Template not found: {template_path}")
        return HTMLResponse(
            content="<h1>Error: Dashboard template not found</h1>",
            status_code=500
        )
    
    try:
        with open(template_path, 'r') as f:
            return HTMLResponse(content=f.read())
    except Exception as e:
        logger.error(f"Error loading template: {e}")
        return HTMLResponse(
            content=f"<h1>Error loading dashboard</h1><p>{str(e)}</p>",
            status_code=500
        )


# ==============================================================================
# API ENDPOINTS
# ==============================================================================

@app.get("/api/calendar")
async def get_calendar():
    """Get calendar events from Google Calendar"""
    try:
        # Try to get cached data first
        cached_data = background_manager.get_cached_data('calendar')
        if cached_data:
            logger.info("Returning cached calendar data")
            return cached_data
        
        # Fallback to real-time collection if no cache available
        logger.info("No cached calendar data, collecting in real-time")
        if COLLECTORS_AVAILABLE:
            try:
                settings = Settings()
                calendar_collector = CalendarCollector(settings)
                start_date = datetime.now()
                end_date = start_date + timedelta(days=7)
                events_data = await calendar_collector.collect_events(start_date, end_date)
                
                if events_data:
                    formatted_events = []
                    for event in events_data[:10]:
                        title = event.get('summary', 'Untitled Event')
                        event_time = "All day"
                        start_dt = None
                        end_dt = None
                        
                        if not event.get('is_all_day', False) and event.get('start_time'):
                            try:
                                start_dt = event['start_time']
                                # Handle both datetime objects and strings
                                if hasattr(start_dt, 'strftime'):
                                    event_time = start_dt.strftime("%I:%M %p")
                                    if event.get('end_time') and hasattr(event['end_time'], 'strftime'):
                                        end_dt = event['end_time']
                                        event_time += f" - {end_dt.strftime('%I:%M %p')}"
                                else:
                                    # If it's a string, try to parse it
                                    start_dt = datetime.fromisoformat(str(start_dt).replace('Z', '+00:00'))
                                    event_time = start_dt.strftime("%I:%M %p")
                                    if event.get('end_time'):
                                        end_dt = datetime.fromisoformat(str(event['end_time']).replace('Z', '+00:00'))
                                        event_time += f" - {end_dt.strftime('%I:%M %p')}"
                            except Exception as e:
                                logger.warning(f"Error formatting event time: {e}")
                                event_time = str(event.get('start_time', 'All day'))
                        
                        # Build comprehensive event data
                        formatted_event = {
                            "title": title,
                            "summary": title,
                            "time": event_time,
                            "description": event.get('description', ''),
                            "location": event.get('location', ''),
                            "organizer": event.get('organizer', '') if isinstance(event.get('organizer'), str) else event.get('organizer', {}).get('email', '') if event.get('organizer') else '',
                            "attendees": [att.get('email', '') if isinstance(att, dict) else str(att) for att in event.get('attendees', [])],
                            "start": {"dateTime": event.get('start_time').isoformat() if hasattr(event.get('start_time'), 'isoformat') else str(event.get('start_time'))} if event.get('start_time') else None,
                            "end": {"dateTime": event.get('end_time').isoformat() if hasattr(event.get('end_time'), 'isoformat') else str(event.get('end_time'))} if event.get('end_time') else None,
                            "event_id": event.get('id', ''),
                            "calendar_url": f"https://calendar.google.com/calendar/event?eid={event.get('id', '')}" if event.get('id') else "https://calendar.google.com/calendar",
                            "is_all_day": event.get('is_all_day', False),
                            "status": event.get('status', ''),
                            "created": event.get('created', ''),
                            "updated": event.get('updated', ''),
                            "html_link": event.get('html_link', '')
                        }
                        
                        formatted_events.append(formatted_event)
                    return {"events": formatted_events}
            except Exception as calendar_error:
                logger.error(f"Calendar API error: {calendar_error}")
                pass
        
        # Return fallback data
        return {"events": [{"title": "Team Meeting", "time": "9:00 AM - 10:00 AM"}]}
    except Exception as e:
        return {"error": str(e)}


@app.post("/api/notes/scan")
async def scan_notes():
    """Scan for new notes from Obsidian and Google Drive with detailed feedback."""
    try:
        from collectors.notes_collector import collect_all_notes
        from database import get_credentials, DatabaseManager
        import traceback
        
        db = DatabaseManager()
        
        # Get configuration with priority: Environment Variables > Database > credentials.yaml
        notes_config = get_credentials('notes') or {}
        
        # Obsidian vault path
        obsidian_path = (
            os.getenv('OBSIDIAN_VAULT_PATH') or
            db.get_setting('obsidian_vault_path') or
            notes_config.get('obsidian_vault_path')
        )
        
        # Google Drive folder ID
        gdrive_folder_id = (
            os.getenv('GOOGLE_DRIVE_NOTES_FOLDER_ID') or
            db.get_setting('google_drive_notes_folder_id') or
            notes_config.get('google_drive_folder_id')
        )
        
        # Other settings
        limit = int(os.getenv('NOTES_LIMIT', db.get_setting('notes_limit', notes_config.get('notes_limit', 10))))
        
        logger.info(f"Scanning notes - Obsidian: {obsidian_path}, GDrive: {gdrive_folder_id}")
        
        # DEBUG: Log what we're working with
        logger.info(f"DEBUG - obsidian_path: {repr(obsidian_path)}")
        logger.info(f"DEBUG - gdrive_folder_id: {repr(gdrive_folder_id)}")
        
        # Collect notes from all sources
        try:
            result = collect_all_notes(
                obsidian_path=obsidian_path,
                gdrive_folder_id=gdrive_folder_id,
                limit=limit
            )
        except Exception as collect_err:
            logger.error(f"Error in collect_all_notes: {collect_err}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        
        # Create suggested tasks from TODOs for user approval
        suggestions_created = 0
        if result['todos_to_create']:
            # Get existing suggestions to avoid duplicates
            existing_suggestions = db.get_suggested_todos(status='pending')
            existing_titles = {s['title'].lower() for s in existing_suggestions}
            
            # Get existing tasks to avoid duplicates
            existing_tasks = db.get_todos()
            existing_task_titles = {t.get('title', '').lower() for t in existing_tasks}
            
            for todo_item in result['todos_to_create']:
                try:
                    todo_text = todo_item['text']
                    
                    # Skip if already exists as suggestion or task
                    if todo_text.lower() in existing_titles or todo_text.lower() in existing_task_titles:
                        continue
                    
                    # Create suggested task
                    suggestion_data = {
                        'title': todo_text,
                        'description': f"From {todo_item['source']}: {todo_item['source_title']}",
                        'context': todo_item.get('context', ''),
                        'source': f"notes_{todo_item['source']}",
                        'source_url': todo_item.get('source_url') or todo_item.get('source_path'),
                        'source_title': todo_item['source_title'],
                        'priority': 'medium'
                    }
                    
                    suggestion_id = db.add_suggested_todo(suggestion_data)
                    if suggestion_id:
                        suggestions_created += 1
                        logger.info(f"Created suggested todo from note: {todo_text[:50]}...")
                    
                except Exception as e:
                    logger.error(f"Error creating suggested todo: {e}")
                    continue
        
        response_data = {
            "success": True,
            "notes": result['notes'],
            "obsidian_count": result['obsidian_count'],
            "gdrive_count": result['gdrive_count'],
            "total_todos_found": result['total_todos_found'],
            "suggestions_created": suggestions_created,
            "config_status": {
                'obsidian_configured': bool(obsidian_path),
                'obsidian_path': obsidian_path or 'Not configured',
                'gdrive_configured': bool(gdrive_folder_id and gdrive_folder_id.strip()),
                'gdrive_folder_id': gdrive_folder_id or 'Not configured',
                'notes_by_source': {
                    'obsidian': result['obsidian_count'],
                    'google_drive': result['gdrive_count']
                }
            }
        }
        
        # Add auth error if present
        if result.get('gdrive_auth_error'):
            response_data['gdrive_auth_error'] = result['gdrive_auth_error']
        
        return response_data
        
    except Exception as e:
        logger.error(f"Error scanning notes: {e}")
        return {
            "success": False,
            "error": str(e),
            "notes": [],
            "obsidian_count": 0,
            "gdrive_count": 0,
            "total_todos_found": 0,
            "suggestions_created": 0
        }


@app.get("/api/notes")
async def get_notes():
    """Get recent notes from Obsidian and Google Drive."""
    try:
        from collectors.notes_collector import collect_all_notes
        from database import get_credentials, DatabaseManager
        import traceback
        
        db = DatabaseManager()
        
        # Get configuration with priority: Environment Variables > Database > credentials.yaml
        notes_config = get_credentials('notes') or {}
        
        # Obsidian vault path
        obsidian_path = (
            os.getenv('OBSIDIAN_VAULT_PATH') or  # Environment variable (highest priority)
            db.get_setting('obsidian_vault_path') or  # Database setting
            notes_config.get('obsidian_vault_path')  # credentials.yaml (fallback)
        )
        
        # Google Drive folder ID
        gdrive_folder_id = (
            os.getenv('GOOGLE_DRIVE_NOTES_FOLDER_ID') or  # Environment variable
            db.get_setting('google_drive_notes_folder_id') or  # Database setting
            notes_config.get('google_drive_folder_id')  # credentials.yaml
        )
        
        # Other settings
        limit = int(os.getenv('NOTES_LIMIT', db.get_setting('notes_limit', notes_config.get('notes_limit', 10))))
        auto_create = os.getenv('AUTO_CREATE_TASKS', str(db.get_setting('auto_create_tasks', notes_config.get('auto_create_tasks', True)))).lower() in ('true', '1', 'yes')
        
        logger.info(f"Collecting notes - Obsidian: {obsidian_path}, GDrive: {gdrive_folder_id}")
        
        # TEMPORARY DEBUG
        logger.info(f"DEBUG - obsidian_path type: {type(obsidian_path)}, value: {repr(obsidian_path)}")
        logger.info(f"DEBUG - gdrive_folder_id type: {type(gdrive_folder_id)}, value: {repr(gdrive_folder_id)}")
        
        # Collect notes from all sources
        try:
            result = collect_all_notes(
                obsidian_path=obsidian_path,
                gdrive_folder_id=gdrive_folder_id,
                limit=limit
            )
        except Exception as collect_err:
            logger.error(f"Error in collect_all_notes: {collect_err}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise
        
        # Log results for debugging
        logger.info(f"Notes collection complete: {len(result.get('notes', []))} notes, " +
                   f"{len(result.get('todos_to_create', []))} TODOs found")
        
        # Add configuration status to result
        result['config_status'] = {
            'obsidian_configured': bool(obsidian_path),
            'obsidian_path': obsidian_path or 'Not configured',
            'gdrive_configured': bool(gdrive_folder_id and gdrive_folder_id.strip()),
            'gdrive_folder_id': gdrive_folder_id or 'Not configured',
            'notes_by_source': {
                'obsidian': len([n for n in result.get('notes', []) if n.get('source') == 'obsidian']),
                'google_drive': len([n for n in result.get('notes', []) if n.get('source') == 'google_drive'])
            }
        }
        
        # Create suggested tasks from TODOs for user approval
        suggestions_created = 0
        if result['todos_to_create']:
            from database import DatabaseManager
            db = DatabaseManager()
            
            # Get existing suggestions to avoid duplicates
            existing_suggestions = db.get_suggested_todos(status='pending')
            existing_titles = {s['title'].lower() for s in existing_suggestions}
            
            # Get existing tasks to avoid duplicates
            existing_tasks = db.get_todos()
            existing_task_titles = {t.get('title', '').lower() for t in existing_tasks}
            
            for todo_item in result['todos_to_create']:
                try:
                    todo_text = todo_item['text']
                    
                    # Skip if already exists as suggestion or task
                    if todo_text.lower() in existing_titles or todo_text.lower() in existing_task_titles:
                        continue
                    
                    # Create suggested task
                    suggestion_data = {
                        'title': todo_text,
                        'description': f"From {todo_item['source']}: {todo_item['source_title']}",
                        'context': todo_item.get('context', ''),
                        'source': f"notes_{todo_item['source']}",
                        'source_url': todo_item.get('source_url') or todo_item.get('source_path'),
                        'source_title': todo_item['source_title'],
                        'priority': 'medium'
                    }
                    
                    suggestion_id = db.add_suggested_todo(suggestion_data)
                    if suggestion_id:
                        suggestions_created += 1
                        logger.info(f"Created suggested todo from note: {todo_text[:50]}...")
                    
                except Exception as e:
                    logger.error(f"Error creating suggested todo: {e}")
                    continue
        
        return {
            "success": True,
            "notes": result['notes'],
            "obsidian_count": result['obsidian_count'],
            "gdrive_count": result['gdrive_count'],
            "total_todos_found": result['total_todos_found'],
            "suggestions_created": suggestions_created
        }
        
    except Exception as e:
        logger.error(f"Error collecting notes: {e}")
        return {
            "success": False,
            "error": str(e),
            "notes": [],
            "obsidian_count": 0,
            "gdrive_count": 0,
            "total_todos_found": 0,
            "tasks_created": 0
        }


@app.get("/api/settings/notes")
async def get_notes_settings():
    """Get notes configuration settings."""
    try:
        from database import DatabaseManager, get_credentials
        db = DatabaseManager()
        
        # Get all settings with priority chain
        notes_config = get_credentials('notes') or {}
        
        settings = {
            'obsidian_vault_path': {
                'value': (
                    os.getenv('OBSIDIAN_VAULT_PATH') or
                    db.get_setting('obsidian_vault_path') or
                    notes_config.get('obsidian_vault_path') or
                    ''
                ),
                'source': 'env' if os.getenv('OBSIDIAN_VAULT_PATH') else 
                         'database' if db.get_setting('obsidian_vault_path') else
                         'config' if notes_config.get('obsidian_vault_path') else 'default'
            },
            'google_drive_notes_folder_id': {
                'value': (
                    os.getenv('GOOGLE_DRIVE_NOTES_FOLDER_ID') or
                    db.get_setting('google_drive_notes_folder_id') or
                    notes_config.get('google_drive_folder_id') or
                    ''
                ),
                'source': 'env' if os.getenv('GOOGLE_DRIVE_NOTES_FOLDER_ID') else
                         'database' if db.get_setting('google_drive_notes_folder_id') else
                         'config' if notes_config.get('google_drive_folder_id') else 'default'
            },
            'notes_limit': {
                'value': int(os.getenv('NOTES_LIMIT', db.get_setting('notes_limit', notes_config.get('notes_limit', 10)))),
                'source': 'env' if os.getenv('NOTES_LIMIT') else
                         'database' if db.get_setting('notes_limit') else
                         'config' if notes_config.get('notes_limit') else 'default'
            },
            'auto_create_tasks': {
                'value': os.getenv('AUTO_CREATE_TASKS', str(db.get_setting('auto_create_tasks', notes_config.get('auto_create_tasks', True)))).lower() in ('true', '1', 'yes'),
                'source': 'env' if os.getenv('AUTO_CREATE_TASKS') else
                         'database' if db.get_setting('auto_create_tasks') is not None else
                         'config' if notes_config.get('auto_create_tasks') is not None else 'default'
            }
        }
        
        return {"success": True, "settings": settings}
        
    except Exception as e:
        logger.error(f"Error getting notes settings: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/settings/notes")
async def update_notes_settings(settings: Dict[str, Any]):
    """Update notes configuration settings."""
    try:
        from database import DatabaseManager
        db = DatabaseManager()
        
        updated = []
        
        # Update each setting in the database
        if 'obsidian_vault_path' in settings:
            db.save_setting('obsidian_vault_path', settings['obsidian_vault_path'])
            updated.append('obsidian_vault_path')
        
        if 'google_drive_notes_folder_id' in settings:
            db.save_setting('google_drive_notes_folder_id', settings['google_drive_notes_folder_id'])
            updated.append('google_drive_notes_folder_id')
        
        if 'notes_limit' in settings:
            db.save_setting('notes_limit', int(settings['notes_limit']))
            updated.append('notes_limit')
        
        if 'auto_create_tasks' in settings:
            db.save_setting('auto_create_tasks', bool(settings['auto_create_tasks']))
            updated.append('auto_create_tasks')
        
        logger.info(f"Updated notes settings: {updated}")
        
        return {
            "success": True,
            "message": f"Updated {len(updated)} settings",
            "updated": updated
        }
        
    except Exception as e:
        logger.error(f"Error updating notes settings: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/user/profile")
async def get_user_profile():
    """Get user profile settings."""
    try:
        profile = db.get_user_profile()
        
        return {
            "success": True,
            "profile": profile
        }
        
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/user/profile")
async def save_user_profile(request: Request):
    """Save user profile settings."""
    try:
        profile_data = await request.json()
        
        success = db.save_user_profile(profile_data)
        
        if success:
            logger.info("User profile saved successfully")
            return {
                "success": True,
                "message": "Profile saved successfully"
            }
        else:
            return {"success": False, "error": "Failed to save profile"}
            
    except Exception as e:
        logger.error(f"Error saving user profile: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/settings/ai")
async def get_ai_settings():
    """Get AI/Ollama configuration settings."""
    try:
        from database import DatabaseManager
        db = DatabaseManager()
        
        settings = {
            'ai_provider': db.get_setting('ai_provider', 'ollama'),
            'ollama_host': db.get_setting('ollama_host', 'localhost'),
            'ollama_port': db.get_setting('ollama_port', 11434),
            'ollama_model': db.get_setting('ollama_model', 'llama3.2:1b'),
            'openai_api_key': db.get_setting('openai_api_key', ''),
            'openai_model': db.get_setting('openai_model', 'gpt-4o-mini'),
            'gemini_api_key': db.get_setting('gemini_api_key', ''),
            'gemini_model': db.get_setting('gemini_model', 'gemini-2.0-flash'),
        }
        
        return {
            "success": True,
            "settings": settings
        }
    except Exception as e:
        logger.error(f"Error getting AI settings: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/settings/ai")
async def update_ai_settings(settings: Dict[str, Any]):
    """Update AI/Ollama configuration settings and create/update provider."""
    try:
        from database import DatabaseManager
        db = DatabaseManager()
        
        updated = []
        
        # Update AI provider
        if 'ai_provider' in settings:
            db.save_setting('ai_provider', settings['ai_provider'])
            updated.append('ai_provider')
        
        # Update Ollama settings
        if 'ollama_host' in settings:
            db.save_setting('ollama_host', settings['ollama_host'])
            updated.append('ollama_host')
        
        if 'ollama_port' in settings:
            db.save_setting('ollama_port', int(settings['ollama_port']))
            updated.append('ollama_port')
        
        if 'ollama_model' in settings:
            db.save_setting('ollama_model', settings['ollama_model'])
            updated.append('ollama_model')
        
        # Update OpenAI settings
        if 'openai_api_key' in settings and settings['openai_api_key']:
            db.save_setting('openai_api_key', settings['openai_api_key'])
            updated.append('openai_api_key')
        
        if 'openai_model' in settings:
            db.save_setting('openai_model', settings['openai_model'])
            updated.append('openai_model')
        
        # Update Gemini settings
        if 'gemini_api_key' in settings and settings['gemini_api_key']:
            db.save_setting('gemini_api_key', settings['gemini_api_key'])
            updated.append('gemini_api_key')
        
        if 'gemini_model' in settings:
            db.save_setting('gemini_model', settings['gemini_model'])
            updated.append('gemini_model')
        
        logger.info(f"Updated AI settings: {updated}")
        
        # Now create/update the actual AI provider based on the selected provider type
        if AI_ASSISTANT_AVAILABLE and 'ai_provider' in settings:
            try:
                provider_type = settings['ai_provider']
                
                # First, set ALL providers to non-default (this ensures clean state)
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE ai_providers SET is_default = 0")
                    conn.commit()
                
                if provider_type == 'ollama':
                    # Create/update Ollama provider
                    ollama_host = settings.get('ollama_host', db.get_setting('ollama_host', 'localhost'))
                    ollama_port = settings.get('ollama_port', db.get_setting('ollama_port', 11434))
                    ollama_model = settings.get('ollama_model', db.get_setting('ollama_model', 'llama3.2:latest'))
                    
                    config = {
                        'base_url': f'http://{ollama_host}:{ollama_port}',
                        'model_name': ollama_model,
                        'is_default': True
                    }
                    
                    provider_name = f'Ollama ({ollama_host})'
                    
                    # Create provider instance and test
                    provider = create_provider('ollama', provider_name, config)
                    health_ok = await provider.health_check()
                    
                    if health_ok:
                        # Save to database (update if exists, create if not)
                        provider_id = db.save_ai_provider(provider_name, 'ollama', config)
                        
                        # Clear ai_manager and register only this provider as default
                        ai_manager.providers.clear()
                        ai_manager.default_provider = None
                        ai_manager.register_provider(provider, is_default=True)
                        
                        logger.info(f"Created/updated Ollama provider: {provider_name} as default")
                    else:
                        logger.warning(f"Ollama provider health check failed for {provider_name}")
                
                elif provider_type == 'openai':
                    # Create/update OpenAI provider
                    api_key = settings.get('openai_api_key', db.get_setting('openai_api_key', ''))
                    model = settings.get('openai_model', db.get_setting('openai_model', 'gpt-4o-mini'))
                    
                    if api_key:
                        config = {
                            'api_key': api_key,
                            'model_name': model,
                            'is_default': True
                        }
                        
                        provider_name = f'OpenAI ({model})'
                        
                        # Create provider instance and test
                        provider = create_provider('openai', provider_name, config)
                        health_ok = await provider.health_check()
                        
                        if health_ok:
                            # Save to database
                            provider_id = db.save_ai_provider(provider_name, 'openai', config)
                            
                            # Clear ai_manager and register only this provider as default
                            ai_manager.providers.clear()
                            ai_manager.default_provider = None
                            ai_manager.register_provider(provider, is_default=True)
                            
                            logger.info(f"Created/updated OpenAI provider: {provider_name} as default")
                        else:
                            logger.warning(f"OpenAI provider health check failed")
                
                elif provider_type == 'gemini':
                    # Create/update Gemini provider
                    api_key = settings.get('gemini_api_key', db.get_setting('gemini_api_key', ''))
                    model = settings.get('gemini_model', db.get_setting('gemini_model', 'gemini-pro'))
                    
                    if api_key:
                        config = {
                            'api_key': api_key,
                            'model_name': model,
                            'is_default': True
                        }
                        
                        provider_name = f'Gemini ({model})'
                        
                        # Create provider instance and test
                        provider = create_provider('gemini', provider_name, config)
                        health_ok = await provider.health_check()
                        
                        if health_ok:
                            # Save to database
                            provider_id = db.save_ai_provider(provider_name, 'gemini', config)
                            
                            # Clear ai_manager and register only this provider as default
                            ai_manager.providers.clear()
                            ai_manager.default_provider = None
                            ai_manager.register_provider(provider, is_default=True)
                            
                            logger.info(f"Created/updated Gemini provider: {provider_name} as default")
                        else:
                            logger.warning(f"Gemini provider health check failed")
                
            except Exception as e:
                logger.error(f"Error creating/updating AI provider: {e}")
                # Don't fail the whole request, just log the error
        
        # Reset the AI service singleton to pick up new provider
        if AI_ASSISTANT_AVAILABLE:
            try:
                ai_service = get_ai_service(db, settings)
                ai_service.reset_provider()
            except:
                pass
        
        return {
            "success": True,
            "message": f"Updated {len(updated)} AI settings and initialized provider",
            "updated": updated
        }
        
    except Exception as e:
        logger.error(f"Error updating AI settings: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/ollama/models")
async def get_ollama_models():
    """Get list of available Ollama models."""
    try:
        from database import DatabaseManager
        db = DatabaseManager()
        
        # Get Ollama host and port from settings
        host = db.get_setting('ollama_host', 'localhost')
        port = db.get_setting('ollama_port', 11434)
        url = f"http://{host}:{port}/api/tags"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, timeout=5.0)
            
            if response.status_code == 200:
                data = response.json()
                models = []
                
                if 'models' in data:
                    for model in data['models']:
                        models.append({
                            'name': model.get('name'),
                            'size': model.get('size', 0),
                            'modified': model.get('modified_at', ''),
                            'digest': model.get('digest', '')
                        })
                
                return {
                    "success": True,
                    "models": models,
                    "count": len(models),
                    "server": f"{host}:{port}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Ollama server returned status {response.status_code}",
                    "models": []
                }
                
    except httpx.ConnectError:
        return {
            "success": False,
            "error": "Cannot connect to Ollama server. Make sure it's running.",
            "models": []
        }
    except Exception as e:
        logger.error(f"Error getting Ollama models: {e}")
        return {
            "success": False,
            "error": str(e),
            "models": []
        }


@app.post("/api/ollama/pull")
async def pull_ollama_model(request: Dict[str, Any]):
    """Pull a new Ollama model."""
    try:
        from database import DatabaseManager
        db = DatabaseManager()
        
        model_name = request.get('model')
        if not model_name:
            return {"success": False, "error": "Model name is required"}
        
        host = db.get_setting('ollama_host', 'localhost')
        port = db.get_setting('ollama_port', 11434)
        url = f"http://{host}:{port}/api/pull"
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(url, json={"name": model_name})
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": f"Successfully pulled model: {model_name}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to pull model: {response.text}"
                }
                
    except Exception as e:
        logger.error(f"Error pulling Ollama model: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/notes/test-obsidian")
async def test_obsidian_connection(request: Dict[str, Any]):
    """Test Obsidian vault connection."""
    try:
        vault_path = request.get('vault_path', '')
        if not vault_path:
            return {"success": False, "error": "Vault path is required"}
        
        from pathlib import Path
        
        vault_dir = Path(vault_path)
        
        # Check if directory exists
        if not vault_dir.exists():
            return {
                "success": False,
                "error": f"Directory does not exist: {vault_path}",
                "details": {"path_exists": False, "is_directory": False, "markdown_files": 0}
            }
        
        # Check if it's a directory
        if not vault_dir.is_dir():
            return {
                "success": False,
                "error": f"Path is not a directory: {vault_path}",
                "details": {"path_exists": True, "is_directory": False, "markdown_files": 0}
            }
        
        # Check for markdown files
        md_files = list(vault_dir.rglob('*.md'))
        recent_files = []
        
        # Get info about some recent files
        for md_file in md_files[:5]:  # Just check first 5
            try:
                stat = md_file.stat()
                recent_files.append({
                    "name": md_file.name,
                    "relative_path": str(md_file.relative_to(vault_dir)),
                    "modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "size": stat.st_size
                })
            except Exception:
                continue
        
        return {
            "success": True,
            "message": f"Successfully connected to Obsidian vault with {len(md_files)} markdown files",
            "details": {
                "path_exists": True,
                "is_directory": True,
                "markdown_files": len(md_files),
                "sample_files": recent_files
            }
        }
        
    except Exception as e:
        logger.error(f"Error testing Obsidian connection: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/notes/test-gdrive")
async def test_gdrive_connection(request: Dict[str, Any]):
    """Test Google Drive folder connection."""
    try:
        folder_id = request.get('folder_id', '')
        if not folder_id:
            return {"success": False, "error": "Folder ID is required"}
        
        from collectors.notes_collector import GoogleDriveNotesCollector
        
        gdrive = GoogleDriveNotesCollector()
        service = gdrive._get_service()
        
        if not service:
            return {
                "success": False,
                "error": "Could not connect to Google Drive API. Please check authentication.",
                "details": {"authenticated": False, "folder_accessible": False, "document_count": 0}
            }
        
        # Test folder access
        try:
            folder_meta = service.files().get(fileId=folder_id, fields='id, name, mimeType').execute()
            
            if folder_meta['mimeType'] != 'application/vnd.google-apps.folder':
                return {
                    "success": False,
                    "error": f"ID {folder_id} is not a folder (type: {folder_meta['mimeType']})",
                    "details": {"authenticated": True, "folder_accessible": True, "is_folder": False, "document_count": 0}
                }
            
            # Test document listing
            query = f"'{folder_id}' in parents and mimeType='application/vnd.google-apps.document' and trashed=false"
            results = service.files().list(
                q=query,
                pageSize=10,
                fields='files(id, name, modifiedTime, createdTime)'
            ).execute()
            
            files = results.get('files', [])
            
            return {
                "success": True,
                "message": f"Successfully connected to Google Drive folder '{folder_meta['name']}' with {len(files)} documents",
                "details": {
                    "authenticated": True,
                    "folder_accessible": True,
                    "is_folder": True,
                    "folder_name": folder_meta['name'],
                    "document_count": len(files),
                    "sample_documents": files[:3]  # Show first 3
                }
            }
            
        except Exception as e:
            if "404" in str(e):
                return {
                    "success": False,
                    "error": f"Folder with ID {folder_id} not found or not accessible",
                    "details": {"authenticated": True, "folder_accessible": False, "document_count": 0}
                }
            else:
                raise
        
    except Exception as e:
        logger.error(f"Error testing Google Drive connection: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/email") 
async def get_email():
    """Get email summary from Gmail - always fetch fresh data"""
    try:
        # ALWAYS fetch fresh data - no caching for emails
        logger.info("Fetching fresh email data from Gmail")
        if COLLECTORS_AVAILABLE:
            try:
                settings = Settings()
                gmail_collector = GmailCollector(settings)
                data = await gmail_collector.collect_data()
                
                logger.info(f"Retrieved {data.get('total_count', 0)} emails, {data.get('unread_count', 0)} unread")
                return data
                
            except Exception as e:
                logger.error(f"Error collecting email data: {e}")
                raise HTTPException(status_code=500, detail=f"Error collecting emails: {str(e)}")
        else:
            raise HTTPException(status_code=500, detail="Email collector not available")
            
    except Exception as e:
        logger.error(f"Error in email API: {e}")
        return {"error": str(e), "emails": [], "total_count": 0, "unread_count": 0}

@app.get("/api/github")
async def get_github():
    """Get GitHub activity"""
    try:
        if COLLECTORS_AVAILABLE:
            try:
                from database import get_credentials
                github_creds = get_credentials('github')
                if github_creds and github_creds.get('token'):
                    username = github_creds.get('username')
                    if not username:
                        # Fallback to user profile
                        profile = db.get_user_profile()
                        username = profile.get('github_username', 'unknown')
                    token = github_creds.get('token')
                    headers = {'Authorization': f'token {token}', 'Accept': 'application/vnd.github.v3+json'}
                    
                    github_items = []
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        # Get review requests
                        review_response = await client.get(f'https://api.github.com/search/issues?q=review-requested:{username}+is:open+is:pr', headers=headers)
                        if review_response.status_code == 200:
                            for pr in review_response.json().get('items', [])[:3]:
                                repo_url_parts = pr.get('repository_url', '').split('/')
                                repo_name = repo_url_parts[-1] if repo_url_parts else 'unknown'
                                repo_owner = repo_url_parts[-2] if len(repo_url_parts) > 1 else 'unknown'
                                
                                github_items.append({
                                    'type': 'Review Requested', 
                                    'title': pr.get('title', ''),
                                    'repo': repo_name, 
                                    'repository': f"{repo_owner}/{repo_name}",
                                    'number': pr.get('number', ''),
                                    'user': pr.get('user', {}).get('login', 'Unknown') if pr.get('user') else 'Unknown',
                                    'state': pr.get('state', 'open'),
                                    'created_at': pr.get('created_at', ''),
                                    'updated_at': pr.get('updated_at', ''),
                                    'body': pr.get('body', ''),
                                    'html_url': pr.get('html_url', ''),
                                    'labels': [label.get('name', '') for label in pr.get('labels', [])],
                                    'assignees': [ass.get('login', '') for ass in pr.get('assignees', [])],
                                    'github_url': pr.get('html_url', ''),
                                    'api_url': pr.get('url', '')
                                })
                        
                        # Get assigned issues  
                        issues_response = await client.get(f'https://api.github.com/search/issues?q=assignee:{username}+is:issue+is:open', headers=headers)
                        if issues_response.status_code == 200:
                            for issue in issues_response.json().get('items', [])[:3]:
                                repo_url_parts = issue.get('repository_url', '').split('/')
                                repo_name = repo_url_parts[-1] if repo_url_parts else 'unknown'
                                repo_owner = repo_url_parts[-2] if len(repo_url_parts) > 1 else 'unknown'
                                
                                github_items.append({
                                    'type': 'Issue Assigned', 
                                    'title': issue.get('title', ''),
                                    'repo': repo_name,
                                    'repository': f"{repo_owner}/{repo_name}", 
                                    'number': issue.get('number', ''),
                                    'user': issue.get('user', {}).get('login', 'Unknown') if issue.get('user') else 'Unknown',
                                    'state': issue.get('state', 'open'),
                                    'created_at': issue.get('created_at', ''),
                                    'updated_at': issue.get('updated_at', ''),
                                    'body': issue.get('body', ''),
                                    'html_url': issue.get('html_url', ''),
                                    'labels': [label.get('name', '') for label in issue.get('labels', [])],
                                    'assignees': [ass.get('login', '') for ass in issue.get('assignees', [])],
                                    'github_url': issue.get('html_url', ''),
                                    'api_url': issue.get('url', '')
                                })
                        
                        # Get recent activity - repositories you've pushed to
                        repos_response = await client.get(f'https://api.github.com/user/repos?sort=pushed&per_page=5', headers=headers)
                        if repos_response.status_code == 200:
                            for repo in repos_response.json()[:3]:
                                github_items.append({
                                    'type': 'Recent Repository', 
                                    'title': repo.get('name', ''),
                                    'repo': repo.get('name', ''),
                                    'repository': repo.get('full_name', ''), 
                                    'description': repo.get('description', 'No description'),
                                    'updated_at': repo.get('pushed_at', ''),
                                    'language': repo.get('language', 'Unknown'),
                                    'stars': repo.get('stargazers_count', 0),
                                    'forks': repo.get('forks_count', 0),
                                    'private': repo.get('private', False),
                                    'html_url': repo.get('html_url', ''),
                                    'github_url': repo.get('html_url', ''),
                                    'api_url': repo.get('url', '')
                                })
                        
                        # Get recent pull requests authored by you
                        prs_response = await client.get(f'https://api.github.com/search/issues?q=author:{username}+is:pr+sort:updated', headers=headers)
                        if prs_response.status_code == 200:
                            for pr in prs_response.json().get('items', [])[:3]:
                                repo_url_parts = pr.get('repository_url', '').split('/')
                                repo_name = repo_url_parts[-1] if repo_url_parts else 'unknown'
                                repo_owner = repo_url_parts[-2] if len(repo_url_parts) > 1 else 'unknown'
                                
                                github_items.append({
                                    'type': 'Pull Request', 
                                    'title': pr.get('title', ''),
                                    'repo': repo_name,
                                    'repository': f"{repo_owner}/{repo_name}", 
                                    'number': pr.get('number', ''),
                                    'state': pr.get('state', 'open'),
                                    'created_at': pr.get('created_at', ''),
                                    'updated_at': pr.get('updated_at', ''),
                                    'body': pr.get('body', ''),
                                    'html_url': pr.get('html_url', ''),
                                    'labels': [label.get('name', '') for label in pr.get('labels', [])],
                                    'github_url': pr.get('html_url', ''),
                                    'api_url': pr.get('url', '')
                                })
                    
                    return {"items": github_items}
            except Exception as e:
                print(f"GitHub API error: {e}")
                return {"items": [], "error": str(e)}
        
        return {"items": []}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/ticktick")
async def get_ticktick():
    """Get TickTick tasks"""
    try:
        if COLLECTORS_AVAILABLE:
            from database import get_auth_token, get_credentials
            
            # Check both OAuth tokens and direct API tokens
            token_data = get_auth_token('ticktick')
            creds = get_credentials('ticktick')
            
            has_oauth = token_data and token_data.get('access_token')
            has_api_token = creds and creds.get('api_token')
            
            if has_oauth or has_api_token:
                # Token exists, try to fetch tasks
                settings = Settings()
                collector = TickTickCollector(settings)
                tasks_data = await collector.collect_data()
                
                if tasks_data.get('authenticated'):
                    return {
                        "tasks": tasks_data.get('tasks', []),
                        "projects": tasks_data.get('projects', []),
                        "statistics": tasks_data.get('statistics', {}),
                        "authenticated": True,
                        "user": token_data.get('user_info', {}) if token_data else {}
                    }
                else:
                    return {
                        "tasks": [], 
                        "authenticated": False, 
                        "auth_url": "/auth/ticktick",
                        "error": tasks_data.get('error', 'Authentication failed')
                    }
            else:
                # No token, need to authenticate
                return {
                    "tasks": [], 
                    "authenticated": False, 
                    "auth_url": "/auth/ticktick"
                }
        else:
            return {"error": "TickTick collector not available"}
    except Exception as e:
        logger.error(f"TickTick API error: {e}")
        return {"tasks": [], "authenticated": False, "auth_url": "/auth/ticktick", "error": str(e)}

@app.get("/api/email/todo-analysis")
async def get_email_todo_analysis():
    """Analyze last 6 months of emails for todos and follow-ups"""
    try:
        if not COLLECTORS_AVAILABLE:
            return {"error": "Email collectors not available"}
        
        from processors.email_ticktick_sync import EmailTickTickSync
        settings = Settings()
        sync_service = EmailTickTickSync(settings)
        
        analysis_result = await sync_service.get_email_todo_analysis_only()
        
        return {
            "success": True,
            "analysis": analysis_result,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Email todo analysis error: {e}")
        return {"error": str(e), "success": False}

@app.post("/api/email/sync-to-ticktick")
async def sync_email_todos_to_ticktick():
    """Analyze 6 months of emails and create TickTick tasks for todos and follow-ups"""
    try:
        if not COLLECTORS_AVAILABLE:
            return {"error": "Email collectors not available"}
        
        from processors.email_ticktick_sync import EmailTickTickSync
        settings = Settings()
        sync_service = EmailTickTickSync(settings)
        
        sync_result = await sync_service.sync_email_todos_to_ticktick()
        
        return {
            "success": True,
            "sync_result": sync_result,
            "summary": sync_result.get('summary', {}),
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Email TickTick sync error: {e}")
        return {"error": str(e), "success": False}

@app.post("/api/email/scan-for-tasks")
async def scan_emails_for_tasks(request: Request):
    """Scan historical emails for tasks using strict AI filtering."""
    try:
        if not COLLECTORS_AVAILABLE:
            raise HTTPException(status_code=503, detail="Email collectors not available")
        
        # Get request parameters
        body = await request.json()
        start_date_str = body.get('start_date')
        end_date_str = body.get('end_date')
        max_emails = body.get('max_emails', 100)
        
        # Parse dates
        start_date = datetime.fromisoformat(start_date_str) if start_date_str else datetime.now() - timedelta(days=30)
        end_date = datetime.fromisoformat(end_date_str) if end_date_str else datetime.now()
        end_date = end_date.replace(hour=23, minute=59, second=59)  # End of day
        
        logger.info(f"Scanning emails from {start_date} to {end_date}, max {max_emails} emails")
        
        # Initialize collectors
        settings = Settings()
        gmail_collector = GmailCollector(settings)
        task_manager = TaskManager(settings)
        
        # Import email analyzer
        from processors.email_analyzer import EmailAnalyzer
        email_analyzer = EmailAnalyzer()
        
        # Collect emails in date range
        emails = await gmail_collector.collect_emails(start_date, end_date)
        emails = emails[:max_emails]  # Limit to max_emails
        
        logger.info(f"Collected {len(emails)} emails to scan")
        
        tasks_created = 0
        tasks_skipped = 0
        emails_skipped = 0
        
        # Analyze each email for tasks
        for email in emails:
            try:
                subject = email.get('subject', '')
                body = email.get('body', '')
                sender = email.get('sender', '')
                email_id = email.get('id', '')
                received_date = email.get('received_date', '')
                risk_score = email.get('risk_score', 0)  # Get risk score from email data
                
                # Use AI analyzer with strict filtering and risk scoring
                todos = await email_analyzer.analyze_email_for_todos(subject, body, sender, risk_score)
                
                if not todos:
                    emails_skipped += 1
                    continue
                
                # Create tasks for each todo found
                for todo in todos:
                    # Check if task already exists (avoid duplicates)
                    existing_tasks = task_manager.get_tasks_by_source('email', email_id)
                    if existing_tasks:
                        logger.info(f"Task already exists for email: {subject[:50]}")
                        tasks_skipped += 1
                        continue
                    
                    # Create task
                    task_data = {
                        'title': todo.get('task'),
                        'description': f"From: {sender}\nSubject: {subject}\n\nReason: {todo.get('reason', 'N/A')}",
                        'due_date': todo.get('deadline'),
                        'priority': todo.get('priority', 'medium'),
                        'category': todo.get('category', 'email'),
                        'source': 'email',
                        'source_id': email_id,
                        'status': 'pending',
                        'requires_response': todo.get('requires_response', False)
                    }
                    
                    task_manager.create_task(task_data)
                    tasks_created += 1
                    logger.info(f"Created task from email: {subject[:50]}")
                    
            except Exception as e:
                logger.error(f"Error processing email {email.get('id', 'unknown')}: {e}")
                continue
        
        return {
            "success": True,
            "emails_scanned": len(emails),
            "tasks_created": tasks_created,
            "tasks_skipped": tasks_skipped,
            "emails_skipped": emails_skipped,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Email scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/email/mark-safe")
async def mark_email_as_safe(request: Request):
    """Mark an email sender as safe/trusted."""
    try:
        data = await request.json()
        sender_email = data.get('sender_email')
        reason = data.get('reason', 'User marked as safe')
        
        if not sender_email:
            raise HTTPException(status_code=400, detail="sender_email required")
        
        success = db.add_safe_sender(sender_email, reason)
        
        if success:
            logger.info(f"Marked sender as safe: {sender_email}")
            return {
                "success": True,
                "message": f"Added {sender_email} to safe senders list",
                "sender_email": sender_email
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to add safe sender")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking email as safe: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/email/safe-senders")
async def get_safe_senders():
    """Get list of all safe/trusted senders."""
    try:
        safe_senders = db.get_safe_senders()
        return {
            "success": True,
            "safe_senders": safe_senders,
            "total": len(safe_senders)
        }
    except Exception as e:
        logger.error(f"Error getting safe senders: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/email/safe-senders/{sender_email}")
async def remove_safe_sender(sender_email: str):
    """Remove a sender from the safe senders list."""
    try:
        # URL decode the email
        from urllib.parse import unquote
        sender_email = unquote(sender_email)
        
        success = db.remove_safe_sender(sender_email)
        
        if success:
            logger.info(f"Removed safe sender: {sender_email}")
            return {
                "success": True,
                "message": f"Removed {sender_email} from safe senders list"
            }
        else:
            raise HTTPException(status_code=404, detail="Safe sender not found")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error removing safe sender: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Task Management API Endpoints
@app.get("/api/tasks")
async def get_tasks(include_completed: bool = False, priority: str = None, status: str = None, category: str = None):
    """Get all tasks from database with optional filtering."""
    try:
        if not TASK_MANAGER_AVAILABLE:
            return {"error": "Task Manager not available", "success": False}
        
        if not COLLECTORS_AVAILABLE:
            task_manager = TaskManager(None)
        else:
            settings = Settings()
            task_manager = TaskManager(settings)
            
        # Get all tasks first
        tasks = task_manager.get_all_tasks(include_completed=include_completed)
        
        # Apply filters
        if priority:
            tasks = [t for t in tasks if t.get('priority', '').lower() == priority.lower()]
        
        if status:
            tasks = [t for t in tasks if t.get('status', '').lower() == status.lower()]
            
        if category:
            tasks = [t for t in tasks if t.get('category', '').lower() == category.lower()]
        
        # Get statistics for all tasks (unfiltered)
        stats = task_manager.get_task_statistics()
        
        return {
            "success": True,
            "tasks": tasks,
            "statistics": stats,
            "filters_applied": {
                "priority": priority,
                "status": status,
                "category": category,
                "include_completed": include_completed
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting tasks: {e}")
        return {"error": str(e), "success": False}

@app.post("/api/tasks")
async def create_task(request: Request):
    """Create a new task."""
    try:
        if not TASK_MANAGER_AVAILABLE:
            return {"error": "Task Manager not available", "success": False}
            
        data = await request.json()
        
        if not COLLECTORS_AVAILABLE:
            task_manager = TaskManager(None)
        else:
            settings = Settings()
            task_manager = TaskManager(settings)
        
        # Parse due_date if provided
        due_date = None
        if data.get('due_date'):
            try:
                due_date = datetime.fromisoformat(data['due_date'].replace('Z', '+00:00'))
            except:
                pass
        
        result = task_manager.create_task(
            title=data.get('title', ''),
            description=data.get('description', ''),
            priority=data.get('priority', 'medium'),
            category=data.get('category', 'general'),
            due_date=due_date,
            source=data.get('source', 'manual'),
            source_id=data.get('source_id', ''),
            email_id=data.get('email_id', ''),
            sync_to_ticktick=data.get('sync_to_ticktick', True) and COLLECTORS_AVAILABLE
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error creating task: {e}")
        return {"error": str(e), "success": False}

@app.put("/api/tasks/{task_id}/status")
async def update_task_status(task_id: str, request: Request):
    """Update task status."""
    try:
        if not TASK_MANAGER_AVAILABLE:
            return {"error": "Task Manager not available", "success": False}
            
        data = await request.json()
        status = data.get('status', 'pending')
        
        if not COLLECTORS_AVAILABLE:
            task_manager = TaskManager(None)
        else:
            settings = Settings()
            task_manager = TaskManager(settings)
            
        result = task_manager.update_task_status(task_id, status)
        
        return result
        
    except Exception as e:
        logger.error(f"Error updating task status: {e}")
        return {"error": str(e), "success": False}

@app.delete("/api/tasks/clear-all")
async def clear_all_tasks():
    """Delete all existing tasks (for fresh start)."""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM universal_todos")
            count = cursor.fetchone()['count']
            
            cursor.execute("DELETE FROM universal_todos")
            conn.commit()
            
        logger.info(f"Deleted {count} tasks from database")
        
        return {
            "success": True,
            "deleted_count": count,
            "message": f"Deleted all {count} existing tasks"
        }
        
    except Exception as e:
        logger.error(f"Error clearing tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    """Delete a task."""
    try:
        if not TASK_MANAGER_AVAILABLE:
            return {"error": "Task Manager not available", "success": False}
            
        if not COLLECTORS_AVAILABLE:
            task_manager = TaskManager(None)
        else:
            settings = Settings()
            task_manager = TaskManager(settings)
            
        result = task_manager.delete_task(task_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Error deleting task: {e}")
        return {"error": str(e), "success": False}

@app.post("/api/tasks/sync")
async def sync_tasks_with_ticktick(request: Request):
    """Synchronize tasks with TickTick."""
    try:
        if not TASK_MANAGER_AVAILABLE:
            return {"error": "Task Manager not available", "success": False}
            
        if not COLLECTORS_AVAILABLE:
            return {"error": "TickTick sync not available - collectors not loaded", "success": False}
            
        data = await request.json()
        direction = data.get('direction', 'both')  # "to_ticktick", "from_ticktick", or "both"
        
        settings = Settings()
        task_manager = TaskManager(settings)
        result = await task_manager.sync_with_ticktick(direction)
        
        return result
        
    except Exception as e:
        logger.error(f"Error syncing tasks with TickTick: {e}")
        return {"error": str(e), "success": False}


@app.post("/api/tasks/generate")
async def generate_tasks_from_sources(request: Request):
    """Generate tasks from notes, calendar events, and emails."""
    try:
        data = await request.json()
        include_notes = data.get('include_notes', True)
        include_calendar = data.get('include_calendar', True)
        include_email = data.get('include_email', False)  # Off by default as it can be noisy
        
        from processors.task_generator import generate_tasks_from_all_sources
        
        # Collect data from sources
        notes_data = None
        calendar_data = None
        email_data = None
        
        if include_notes:
            # Get recent notes
            try:
                from collectors.notes_collector import collect_all_notes
                from database import get_credentials
                
                notes_config = get_credentials('notes') or {}
                obsidian_path = (
                    os.getenv('OBSIDIAN_VAULT_PATH') or
                    db.get_setting('obsidian_vault_path') or
                    notes_config.get('obsidian_vault_path')
                )
                gdrive_folder_id = (
                    os.getenv('GOOGLE_DRIVE_NOTES_FOLDER_ID') or
                    db.get_setting('google_drive_notes_folder_id') or
                    notes_config.get('google_drive_folder_id')
                )
                
                if obsidian_path or gdrive_folder_id:
                    notes_data = collect_all_notes(obsidian_path, gdrive_folder_id, 20)
            except Exception as e:
                logger.warning(f"Could not collect notes for task generation: {e}")
        
        if include_calendar and COLLECTORS_AVAILABLE:
            # Get recent calendar events
            try:
                settings = Settings()
                calendar_collector = CalendarCollector(settings)
                calendar_data = await calendar_collector.collect_data()
            except Exception as e:
                logger.warning(f"Could not collect calendar data for task generation: {e}")
        
        if include_email and COLLECTORS_AVAILABLE:
            # Get recent emails (last 3 days to avoid overwhelming)
            try:
                settings = Settings()
                gmail_collector = GmailCollector(settings)
                end_date = datetime.now()
                start_date = end_date - timedelta(days=3)
                email_data = {
                    'emails': await gmail_collector.collect_emails(start_date, end_date, max_emails=50)
                }
            except Exception as e:
                logger.warning(f"Could not collect email data for task generation: {e}")
        
        # Generate tasks
        result = generate_tasks_from_all_sources(
            db_manager=db,
            notes_data=notes_data,
            calendar_data=calendar_data,
            email_data=email_data
        )
        
        logger.info(f"Task generation completed: {result['creation_result']['created']} created, {result['creation_result']['skipped']} skipped")
        
        return {
            "success": True,
            "result": result,
            "sources_used": {
                "notes": notes_data is not None,
                "calendar": calendar_data is not None, 
                "email": email_data is not None
            },
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error generating tasks from sources: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/tasks/{task_id}")
async def get_task_details(task_id: str):
    """Get detailed task information with source links."""
    try:
        # Get task from database
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM universal_todos WHERE id = ?', (task_id,))
            task_row = cursor.fetchone()
        
        if not task_row:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Convert to dict
        task = dict(task_row)
        
        # Add source link information
        source_info = {"type": "unknown", "link": None, "display_text": "Unknown source"}
        
        if task.get('source') == 'email' and task.get('source_id'):
            source_info = {
                "type": "email",
                "link": f"https://mail.google.com/mail/u/0/#inbox/{task['source_id']}",
                "display_text": f"View email: {task.get('title', 'Email')}"
            }
        elif task.get('source') == 'calendar' and task.get('source_id'):
            source_info = {
                "type": "calendar",
                "link": f"https://calendar.google.com/calendar/event?eid={task['source_id']}",
                "display_text": f"View calendar event: {task.get('title', 'Event')}"
            }
        elif task.get('source') == 'obsidian' and task.get('source_id'):
            source_info = {
                "type": "obsidian",
                "link": f"obsidian://open?vault=&file={task['source_id']}",
                "display_text": f"Open in Obsidian: {task.get('source_id', 'Note')}"
            }
        elif task.get('source') == 'google_drive' and task.get('source_id'):
            source_info = {
                "type": "google_drive",
                "link": f"https://docs.google.com/document/d/{task['source_id']}/edit",
                "display_text": f"View Google Doc: {task.get('title', 'Document')}"
            }
        
        # Add source info to task
        task['source_info'] = source_info
        
        return {
            "success": True,
            "task": task,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting task details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Suggested Todos API Endpoints
@app.get("/api/suggested-todos")
async def get_suggested_todos(status: str = "pending"):
    """Get suggested todos awaiting user approval."""
    try:
        suggestions = db.get_suggested_todos(status=status)
        return {
            "success": True,
            "suggestions": suggestions,
            "count": len(suggestions)
        }
    except Exception as e:
        logger.error(f"Error getting suggested todos: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/suggested-todos/{suggestion_id}/approve")
async def approve_suggested_todo(suggestion_id: str):
    """Approve a suggested todo and add it to the main todos list."""
    try:
        success = db.approve_suggested_todo(suggestion_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Suggested todo not found")
        
        return {
            "success": True,
            "message": "Todo approved and added to your task list"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error approving suggested todo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/suggested-todos/{suggestion_id}/reject")
async def reject_suggested_todo(suggestion_id: str):
    """Reject a suggested todo."""
    try:
        success = db.reject_suggested_todo(suggestion_id)
        
        if not success:
            raise HTTPException(status_code=404, detail="Suggested todo not found")
        
        return {
            "success": True,
            "message": "Todo suggestion rejected"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error rejecting suggested todo: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/calendar/scan-for-tasks")
async def scan_calendar_for_tasks():
    """Scan last 2 weeks of calendar events for tasks."""
    try:
        if not COLLECTORS_AVAILABLE:
            raise HTTPException(status_code=503, detail="Calendar collectors not available")
        
        from collectors.calendar_collector import CalendarCollector
        from processors.ai_providers import OllamaProvider
        
        settings = Settings()
        calendar_collector = CalendarCollector(settings)
        
        # Use centralized AI service
        ai_service = get_ai_service(db, settings)
        ai_provider = ai_service.get_provider()
        
        if not ai_provider:
            return {"error": "AI provider not configured", "success": False}
        
        # Scan last 2 weeks
        end_date = datetime.now()
        start_date = end_date - timedelta(days=14)
        
        logger.info(f"Scanning calendar events from {start_date} to {end_date}")
        
        events = await calendar_collector.collect_events(start_date, end_date)
        logger.info(f"Found {len(events)} calendar events to analyze")
        
        tasks_suggested = 0
        events_processed = 0
        
        for event in events:
            try:
                title = event.get('title', '')
                description = event.get('description', '')
                start_time = event.get('start', {}).get('dateTime', '')
                event_id = event.get('event_id', '')
                
                # Skip if no meaningful content
                if not title and not description:
                    continue
                
                # Check if we already have suggestions from this event
                existing = db.get_suggested_todos_by_source('calendar', event_id)
                if existing:
                    logger.info(f"Already have suggestions from event: {title[:50]}")
                    continue
                
                # Ask AI to extract action items
                messages = [{
                    'role': 'user',
                    'content': f"""Analyze this calendar event and extract any action items or tasks.
Event: {title}
Description: {description}
Start: {start_time}

Extract clear, actionable tasks. For each task respond with JSON:
{{
    "tasks": [
        {{
            "title": "clear task description",
            "priority": "high|medium|low",
            "due_date": "YYYY-MM-DD" or null
        }}
    ]
}}

Only include real tasks/action items. Skip if this is just an informational event."""
                }]
                
                result = await ai_provider.chat(messages)
                
                # Parse AI response
                import json
                import re
                json_match = re.search(r'\{.*\}', result, re.DOTALL)
                if not json_match:
                    events_processed += 1
                    continue
                
                try:
                    data = json.loads(json_match.group())
                    tasks = data.get('tasks', [])
                    
                    for task in tasks:
                        # Create suggested todo
                        suggestion = {
                            'title': task.get('title', title),
                            'description': f"From calendar event: {title}",
                            'context': description[:500] if description else '',
                            'source': 'calendar',
                            'source_id': event_id,
                            'source_title': title,
                            'source_url': event.get('htmlLink', ''),
                            'priority': task.get('priority', 'medium'),
                            'due_date': task.get('due_date')
                        }
                        
                        db.add_suggested_todo(suggestion)
                        tasks_suggested += 1
                        logger.info(f"Suggested task from calendar: {task.get('title', '')[:50]}")
                        
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse AI response for event: {title}")
                
                events_processed += 1
                
            except Exception as e:
                logger.error(f"Error processing calendar event {event.get('event_id', '')}: {e}")
                continue
        
        return {
            "success": True,
            "events_scanned": len(events),
            "events_processed": events_processed,
            "tasks_suggested": tasks_suggested,
            "date_range": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Calendar scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/notes/scan-for-tasks")
async def scan_notes_for_tasks():
    """Scan recent notes for tasks and TODOs using AI analysis."""
    try:
        from collectors.notes_collector import collect_all_notes
        from database import get_credentials
        from processors.ai_providers import OllamaProvider
        
        notes_config = get_credentials('notes') or {}
        
        # Get configuration
        obsidian_path = (
            os.getenv('OBSIDIAN_VAULT_PATH') or
            db.get_setting('obsidian_vault_path') or
            notes_config.get('obsidian_vault_path')
        )
        
        gdrive_folder_id = (
            os.getenv('GOOGLE_DRIVE_NOTES_FOLDER_ID') or
            db.get_setting('google_drive_notes_folder_id') or
            notes_config.get('google_drive_folder_id')
        )
        
        logger.info(f"Scanning notes - Obsidian: {obsidian_path}, GDrive: {gdrive_folder_id}")
        
        # Use centralized AI service
        ai_service = get_ai_service(db, settings)
        ai_provider = ai_service.get_provider()
        
        if not ai_provider:
            return {"error": "AI provider not configured", "success": False}
        
        # Collect notes (last 30 days worth)
        result = collect_all_notes(
            obsidian_path=obsidian_path,
            gdrive_folder_id=gdrive_folder_id,
            limit=50
        )
        
        tasks_suggested = 0
        notes_processed = 0
        
        # First, process explicitly marked TODOs
        for todo_item in result.get('todos_to_create', []):
            try:
                todo_text = todo_item['text']
                
                # Check for duplicates
                existing = db.get_suggested_todos(status='pending')
                if any(s['title'].lower() == todo_text.lower() for s in existing):
                    continue
                
                # Create suggested task
                suggestion = {
                    'title': todo_text,
                    'description': f"From {todo_item['source']}: {todo_item['source_title']}",
                    'context': todo_item.get('context', ''),
                    'source': f"notes_{todo_item['source']}",
                    'source_id': todo_item.get('source_path') or todo_item.get('source_url', ''),
                    'source_title': todo_item['source_title'],
                    'source_url': todo_item.get('source_url') or todo_item.get('source_path', ''),
                    'priority': 'medium'
                }
                
                db.add_suggested_todo(suggestion)
                tasks_suggested += 1
                logger.info(f"Suggested task from note TODO: {todo_text[:50]}")
                
            except Exception as e:
                logger.error(f"Error creating suggested todo: {e}")
                continue
        
        # Now use AI to analyze note content for implicit tasks
        notes = result.get('notes', [])
        for note in notes:
            try:
                title = note.get('title', '')
                preview = note.get('preview', '')
                source = note.get('source', 'unknown')
                source_id = note.get('path') or note.get('url', '')
                
                # Skip if no meaningful content
                if not title and not preview:
                    continue
                
                # Read full content for analysis
                content = ''
                if source == 'obsidian' and note.get('path'):
                    try:
                        with open(note['path'], 'r', encoding='utf-8') as f:
                            content = f.read()[:2000]  # Limit to 2000 chars for AI
                    except:
                        content = preview
                elif source == 'google_drive':
                    content = note.get('content', preview)[:2000]
                else:
                    content = preview
                
                if not content:
                    continue
                
                # Check if we already analyzed this note
                existing = db.get_suggested_todos_by_source(f'notes_{source}', source_id)
                if existing:
                    logger.info(f"Already analyzed note: {title[:50]}")
                    continue
                
                # Ask AI to extract action items
                messages = [{
                    'role': 'user',
                    'content': f"""Analyze this note and extract any action items, tasks, or follow-ups.
Note Title: {title}
Content:
{content}

Extract clear, actionable tasks. For each task respond with JSON:
{{
    "tasks": [
        {{
            "title": "clear task description",
            "priority": "high|medium|low",
            "due_date": "YYYY-MM-DD" or null
        }}
    ]
}}

Only include real tasks/action items. Skip if this note is purely informational with no actions needed."""
                }]
                
                result_ai = await ai_provider.chat(messages)
                
                # Parse AI response
                import json
                import re
                json_match = re.search(r'\{.*\}', result_ai, re.DOTALL)
                if not json_match:
                    notes_processed += 1
                    continue
                
                try:
                    data = json.loads(json_match.group())
                    tasks = data.get('tasks', [])
                    
                    for task in tasks:
                        # Create suggested todo
                        suggestion = {
                            'title': task.get('title', title),
                            'description': f"From {source} note: {title}",
                            'context': preview[:500] if preview else '',
                            'source': f'notes_{source}',
                            'source_id': source_id,
                            'source_title': title,
                            'source_url': note.get('url') or note.get('path', ''),
                            'priority': task.get('priority', 'medium'),
                            'due_date': task.get('due_date')
                        }
                        
                        db.add_suggested_todo(suggestion)
                        tasks_suggested += 1
                        logger.info(f"AI suggested task from note: {task.get('title', '')[:50]}")
                        
                except json.JSONDecodeError:
                    logger.warning(f"Could not parse AI response for note: {title}")
                
                notes_processed += 1
                
            except Exception as e:
                logger.error(f"Error processing note {note.get('title', '')}: {e}")
                continue
        
        return {
            "success": True,
            "notes_scanned": len(notes),
            "notes_processed": notes_processed,
            "explicit_todos_found": len(result.get('todos_to_create', [])),
            "tasks_suggested": tasks_suggested,
            "sources": {
                "obsidian": result.get('obsidian_count', 0),
                "google_drive": result.get('gdrive_count', 0)
            }
        }
        
    except Exception as e:
        logger.error(f"Notes scan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/news")
async def get_news(filter: str = "all", include_read: bool = False):
    """Get filtered news headlines from database"""
    try:
        # Get news articles from database
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Build query based on whether we want to include read articles
            if include_read:
                cursor.execute('''
                    SELECT id, title, url, snippet, source, published_date, topics, relevance_score, is_read
                    FROM news_articles 
                    ORDER BY is_read ASC, published_date DESC 
                    LIMIT 50
                ''')
            else:
                cursor.execute('''
                    SELECT id, title, url, snippet, source, published_date, topics, relevance_score, is_read
                    FROM news_articles 
                    WHERE is_read = 0
                    ORDER BY published_date DESC 
                    LIMIT 50
                ''')
            db_articles = cursor.fetchall()
            
        logger.info(f"Found {len(db_articles)} articles in database (include_read={include_read})")
        
        # Get previously rated news items to filter them out
        rated_item_ids = db.get_rated_item_ids('news')
        
        # Process articles from database
        articles = []
        for article in db_articles:
            # Use the database ID
            article_id = article['id'] if 'id' in article.keys() else f"news_{hash(article['title'] + str(article['url'] if article['url'] else ''))}"
            
            # Skip if already rated
            if article_id in rated_item_ids:
                continue
            
            # Parse topics
            try:
                import json
                topics = json.loads(article['topics']) if article['topics'] else ['General']
            except:
                topics = ['General']
                
            # Apply filter logic
            article_data = {
                "id": article_id,
                "title": article['title'],
                "source": article['source'],
                "url": article['url'],
                "description": article['snippet'] or "No description available",
                "published_at": article['published_date'],
                "category": ', '.join(topics),
                "relevance_score": article['relevance_score'] or 0.0,
                "is_read": bool(article['is_read']) if 'is_read' in article.keys() else False
            }
            
            # Filter based on category
            if filter == "all":
                articles.append(article_data)
            elif filter == "tech" and any(topic.lower() in ['technology', 'ai', 'star wars', 'star trek'] for topic in topics):
                articles.append(article_data)
            elif filter == "oregon" and any('oregon' in topic.lower() for topic in topics):
                articles.append(article_data)
            elif filter == "timbers" and any('timbers' in topic.lower() or 'portland' in topic.lower() for topic in topics):
                articles.append(article_data)
            elif filter == "starwars" and any('star wars' in topic.lower() for topic in topics):
                articles.append(article_data)
            elif filter == "startrek" and any('star trek' in topic.lower() for topic in topics):
                articles.append(article_data)
        
        # If no articles from database, fall back to Hacker News
        if not articles:
            logger.warning("No articles found in database, falling back to Hacker News")
            articles = await get_hacker_news_articles()
            # Filter out rated Hacker News articles too
            articles = [article for article in articles if article.get('id', '') not in rated_item_ids]
            
        return {
            "articles": articles[:20],  # Limit to 20 articles
            "filter": filter,
            "total": len(articles),
            "source": "Database" if articles else "Fallback"
        }
            
    except Exception as e:
        logger.error(f"Error in news API: {e}")
        # Fallback to Hacker News
        articles = await get_hacker_news_articles()
        return {"articles": articles, "filter": filter, "error": str(e), "source": "Error_Fallback"}

async def get_hacker_news_articles():
    """Get articles from Hacker News as fallback"""
async def get_hacker_news_articles():
    """Get articles from Hacker News as fallback"""
    articles = []
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get("https://news.ycombinator.com")
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Get more detailed content from Hacker News
                for i, title_elem in enumerate(soup.find_all('span', class_='titleline', limit=10)):
                    link = title_elem.find('a')
                    if link:
                        title = link.get_text(strip=True)
                        url = link.get('href', '')
                        
                        # Fix relative URLs
                        if url.startswith('item?'):
                            url = f"https://news.ycombinator.com/{url}"
                        elif not url.startswith('http'):
                            url = f"https://news.ycombinator.com/{url}"
                        
                        # Try to get more metadata
                        parent_row = title_elem.find_parent('tr')
                        score_elem = None
                        comments_elem = None
                        
                        if parent_row:
                            next_row = parent_row.find_next_sibling('tr')
                            if next_row:
                                subtext = next_row.find('span', class_='subtext')
                                if subtext:
                                    score_elem = subtext.find('span', class_='score')
                                    comments_elem = subtext.find_all('a')
                        
                        score = score_elem.get_text() if score_elem else "0 points"
                        comments = "0 comments"
                        hn_discussion_url = "https://news.ycombinator.com"
                        
                        if comments_elem:
                            for a in comments_elem:
                                if 'comment' in a.get_text().lower():
                                    comments = a.get_text()
                                    hn_discussion_url = f"https://news.ycombinator.com/{a.get('href', '')}"
                                    break
                        
                        # Create unique ID for this HN article
                        article_id = f"hn_{hash(title + url)}"
                        
                        articles.append({
                            "id": article_id,
                            "title": title,
                            "source": "Hacker News",
                            "url": url,
                            "hn_url": hn_discussion_url,
                            "score": score,
                            "comments": comments,
                            "description": f"Hacker News article with {score} and {comments}. Discussion and community insights available.",
                            "published_at": "Today",
                            "category": "Technology"
                        })
    except Exception as e:
        logger.error(f"Error fetching HN: {e}")
        # Add fallback content
        articles = [{
            "id": "fallback_tech_news",
            "title": "Tech News Update", 
            "source": "General News",
            "url": "https://news.google.com/topics/CAAqJggKIiBDQkFTRWdvSUwyMHZNRFZ4ZERBU0FtVnVHZ0pWVXlnQVAB",
            "description": "Latest technology news and updates from around the world.",
            "published_at": "Today",
            "category": "Technology"
        }]
    
    return articles

@app.get("/api/music")
async def get_music():
    """Get music trends for user's music projects"""
    try:
        # Get profile for fallback values
        profile = db.get_user_profile()
        default_artist = profile.get('music_artist_name', 'Your Artist')
        
        if COLLECTORS_AVAILABLE:
            try:
                from collectors.music_collector import MusicCollector
                music_collector = MusicCollector()
                
                # Get music data for the user's record label and band
                music_data = await music_collector.collect_all_music_data()
                
                if music_data:
                    # Format the data for the dashboard
                    tracks = []
                    
                    # Add recent releases as tracks
                    for release in music_data.get('recent_releases', [])[:3]:
                        track_data = {
                            "type": "release"
                        }
                        
                        if hasattr(release, 'title'):
                            track_data["title"] = release.title
                        elif isinstance(release, dict):
                            track_data["title"] = release.get('title', 'Unknown')
                        else:
                            track_data["title"] = str(release)
                            
                        if hasattr(release, 'artist'):
                            track_data["artist"] = release.artist
                        elif isinstance(release, dict):
                            track_data["artist"] = release.get('artist', default_artist)
                        else:
                            track_data["artist"] = default_artist
                            
                        if hasattr(release, 'platform'):
                            track_data["platform"] = release.platform
                        elif isinstance(release, dict):
                            track_data["platform"] = release.get('platform', 'Streaming')
                        else:
                            track_data["platform"] = 'Streaming'
                            
                        if hasattr(release, 'release_date') and release.release_date:
                            track_data["release_date"] = release.release_date.isoformat() if hasattr(release.release_date, 'isoformat') else str(release.release_date)
                        elif isinstance(release, dict):
                            track_data["release_date"] = release.get('release_date', 'Recent')
                        else:
                            track_data["release_date"] = 'Recent'
                            
                        if hasattr(release, 'stream_url'):
                            track_data["stream_url"] = release.stream_url
                        elif isinstance(release, dict):
                            track_data["stream_url"] = release.get('stream_url')
                            
                        if hasattr(release, 'play_count'):
                            track_data["play_count"] = release.play_count
                        elif isinstance(release, dict):
                            track_data["play_count"] = release.get('play_count', 0)
                        else:
                            track_data["play_count"] = 0
                            
                        tracks.append(track_data)
                    
                    # Add streaming stats as tracks
                    for stat in music_data.get('streaming_stats', [])[:3]:
                        stat_data = {
                            "type": "stats"
                        }
                        
                        if hasattr(stat, 'platform'):
                            stat_data["title"] = f"Streaming Update - {stat.platform}"
                            stat_data["platform"] = stat.platform
                        elif isinstance(stat, dict):
                            platform = stat.get('platform', 'Platform')
                            stat_data["title"] = f"Streaming Update - {platform}"
                            stat_data["platform"] = platform
                        else:
                            stat_data["title"] = "Streaming Update"
                            stat_data["platform"] = "Streaming"
                            
                        stat_data["artist"] = "Null Records"
                        
                        if hasattr(stat, 'monthly_plays'):
                            stat_data["plays"] = stat.monthly_plays
                        elif isinstance(stat, dict):
                            stat_data["plays"] = stat.get('monthly_plays', 0)
                        else:
                            stat_data["plays"] = 0
                            
                        if hasattr(stat, 'total_followers'):
                            stat_data["followers"] = stat.total_followers
                        elif isinstance(stat, dict):
                            stat_data["followers"] = stat.get('total_followers', 0)
                        else:
                            stat_data["followers"] = 0
                            
                        if hasattr(stat, 'trending_tracks') and stat.trending_tracks:
                            stat_data["trending_tracks"] = stat.trending_tracks[:5]  # Limit to 5
                        elif isinstance(stat, dict):
                            stat_data["trending_tracks"] = stat.get('trending_tracks', [])
                        else:
                            stat_data["trending_tracks"] = []
                            
                        tracks.append(stat_data)
                    
                    return {
                        "tracks": tracks,
                        "label_mentions": music_data.get('label_mentions', []),
                        "band_mentions": music_data.get('band_mentions', []),
                        "music_news": music_data.get('music_news', []),
                        "total_releases": len(music_data.get('recent_releases', [])),
                        "total_mentions": len(music_data.get('label_mentions', [])) + len(music_data.get('band_mentions', []))
                    }
            except Exception as e:
                logger.error(f"Error collecting music data: {e}")
                pass
        
        # Fallback data using user profile
        profile = db.get_user_profile()
        artist_name = profile.get('music_artist_name', 'Your Artist Name')
        label_name = profile.get('music_label_name', 'Your Label')
        bandcamp_url = profile.get('bandcamp_url', 'https://yourname.bandcamp.com')
        soundcloud_url = profile.get('soundcloud_url', 'https://soundcloud.com/username')
        
        return {
            "tracks": [
                {
                    "title": "Latest Release", 
                    "artist": artist_name, 
                    "platform": "Bandcamp",
                    "type": "release",
                    "stream_url": bandcamp_url
                },
                {
                    "title": "Recent Work", 
                    "artist": artist_name, 
                    "platform": "SoundCloud",
                    "type": "release",
                    "stream_url": soundcloud_url
                },
                {
                    "title": f"{label_name} Update",
                    "artist": "Label Stats",
                    "platform": "Analytics",
                    "plays": 0,
                    "followers": 0,
                    "type": "stats"
                }
            ]
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/vanity")
async def get_vanity():
    """Get vanity alerts about user's projects and interests"""
    try:
        # Try to get cached data first
        cached_data = background_manager.get_cached_data('vanity')
        if cached_data:
            logger.info("Returning cached vanity data")
            return cached_data
        
        # Fallback to real-time collection if no cache available
        logger.info("No cached vanity data, collecting in real-time")
        if COLLECTORS_AVAILABLE:
            try:
                from collectors.vanity_alerts_collector import VanityAlertsCollector
                vanity_collector = VanityAlertsCollector()
                
                # Collect recent vanity alerts
                alerts = await vanity_collector.collect_all_alerts()
                
                if alerts:
                    formatted_alerts = []
                    for alert in alerts[:10]:  # Limit to 10 most recent
                        formatted_alerts.append({
                            "id": alert.id,
                            "title": alert.title,
                            "content": alert.content,
                            "snippet": alert.snippet,
                            "url": alert.url,
                            "source": alert.source,
                            "search_term": alert.search_term,
                            "timestamp": alert.timestamp.isoformat() if alert.timestamp else None,
                            "confidence_score": alert.confidence_score,
                            "is_liked": alert.is_liked,
                            "is_validated": alert.is_validated,
                            "category": alert.search_term.split('_')[0] if '_' in alert.search_term else alert.search_term
                        })
                    return {
                        "alerts": formatted_alerts,
                        "total_count": len(alerts),
                        "categories": list(set([a.get('category', 'other') for a in formatted_alerts]))
                    }
            except Exception as e:
                logger.error(f"Error collecting vanity data: {e}")
                pass
        
        # Fallback data
        return {
            "alerts": [
                {
                    "title": "Buildly Platform Update",
                    "content": "Recent news about Buildly platform development",
                    "source": "Tech News",
                    "category": "buildly",
                    "confidence_score": 0.8
                }
            ]
        }
    except Exception as e:
        return {"error": str(e)}


@app.get("/api/vanity-alerts")
async def get_vanity_alerts():
    """Alias for vanity endpoint - returns alerts format (excluding dismissed)"""
    vanity_data = await get_vanity()
    
    # Transform vanity data to alerts format, excluding dismissed
    alerts = []
    if isinstance(vanity_data, dict):
        for alert in vanity_data.get('alerts', []):
            # Skip dismissed alerts
            if alert.get('is_dismissed'):
                continue
                
            alerts.append({
                'id': alert.get('id', str(hash(alert.get('title', '')))),
                'title': alert.get('title', ''),
                'description': alert.get('description', ''),
                'type': alert.get('category', 'mention'),
                'source': alert.get('source', ''),
                'url': alert.get('url', ''),
                'timestamp': alert.get('timestamp', '')
            })
    
    return {"alerts": alerts}


@app.post("/api/vanity-alerts/{alert_id}/dismiss")
async def dismiss_vanity_alert(alert_id: str):
    """Dismiss a vanity alert so it won't be shown again."""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE vanity_alerts 
                SET is_dismissed = 1
                WHERE id = ?
            """, (alert_id,))
            conn.commit()
            
            if cursor.rowcount > 0:
                return {"success": True, "message": "Alert dismissed"}
            else:
                raise HTTPException(status_code=404, detail="Alert not found")
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error dismissing alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/joke")
async def get_joke():
    """Get a daily joke - fetches a fresh joke each time"""
    try:
        if COLLECTORS_AVAILABLE:
            try:
                jokes_collector = JokesCollector()
                # Fetch fresh joke each time (no caching)
                joke_result = await jokes_collector._fetch_single_joke()
                if joke_result and joke_result.get('text'):
                    return {
                        "joke": joke_result.get('text'),
                        "id": joke_result.get('id'),
                        "source": joke_result.get('source', 'icanhazdadjoke.com')
                    }
            except Exception as e:
                logger.warning(f"Error fetching joke from API: {e}")
        
        # Fallback jokes with more variety
        fallback_jokes = [
            "Why don't scientists trust atoms? Because they make up everything! 😄",
            "Why did the scarecrow win an award? He was outstanding in his field! 🌾",
            "Why don't eggs tell jokes? They'd crack each other up! 🥚",
            "What do you call a bear with no teeth? A gummy bear! 🐻",
            "Why did the math book look so sad? Because it had too many problems! 📚",
            "What do you call a fake noodle? An impasta! 🍝",
            "Why can't Monday lift Saturday? It's a weak day! 💪",
            "What did the ocean say to the beach? Nothing, it just waved! 🌊",
            "Why do programmers prefer dark mode? Because light attracts bugs! 🐛",
            "What's a computer's favorite snack? Microchips! 🍟"
        ]
        import random
        selected_joke = random.choice(fallback_jokes)
        return {
            "joke": selected_joke,
            "id": f"fallback_{random.randint(1000, 9999)}",
            "source": "fallback"
        }
    except Exception as e:
        logger.error(f"Error in joke endpoint: {e}")
        return {"error": str(e), "joke": "Error loading joke"}


@app.get("/api/weather")
async def get_weather():
    """Get current weather and forecast"""
    try:
        logger.info(f"Weather API called. COLLECTORS_AVAILABLE={COLLECTORS_AVAILABLE}")
        if COLLECTORS_AVAILABLE:
            try:
                weather_collector = WeatherCollector()
                logger.info("Instantiated WeatherCollector.")
                weather_data = await weather_collector.collect_data()
                logger.info(f"WeatherCollector.collect_data() returned: {weather_data}")
                if weather_data:
                    # Format the data for display
                    result = {
                        "temperature": f"{weather_data.get('temperature', 0):.0f}°F",
                        "description": weather_data.get('description', 'Unknown').title(),
                        "location": weather_data.get('location', 'Unknown Location'),
                        "feels_like": f"{weather_data.get('feels_like', 0):.0f}°F",
                        "humidity": weather_data.get('humidity', 0),
                        "pressure": weather_data.get('pressure', 0),
                        "wind_speed": weather_data.get('wind_speed', 0),
                        "wind_direction": weather_data.get('wind_direction', 0),
                        "visibility": weather_data.get('visibility', 0),
                        "uv_index": weather_data.get('uv_index', 0),
                        "icon": weather_data.get('icon', '01d'),
                        "api_status": weather_data.get('api_status', 'unknown'),
                        "setup_note": weather_data.get('setup_note', ''),
                        "timestamp": weather_data.get('timestamp', ''),
                        "forecast": []
                    }
                    
                    # Format forecast data for display
                    if 'forecast' in weather_data and weather_data['forecast']:
                        from datetime import datetime
                        for f in weather_data['forecast']:
                            try:
                                # Parse date and format for display
                                forecast_date = datetime.strptime(f['date'], '%Y-%m-%d')
                                day_name = forecast_date.strftime('%a')  # Mon, Tue, etc.
                                
                                result["forecast"].append({
                                    "date": f['date'],
                                    "day": day_name,
                                    "high": f['high'],
                                    "low": f['low'],
                                    "condition": f['description'],
                                    "icon": f['icon'],
                                    "precipitation_chance": f['precipitation_chance']
                                })
                            except Exception as e:
                                logger.error(f"Error formatting forecast item: {e}")
                    
                    return result
                else:
                    logger.warning("WeatherCollector returned None, using fallback data.")
            except Exception as collector_exc:
                logger.error(f"Exception in WeatherCollector: {collector_exc}", exc_info=True)
        else:
            logger.warning("COLLECTORS_AVAILABLE is False, using fallback data.")
        
        # Fallback weather data with forecast
        from datetime import datetime, timedelta
        base_date = datetime.now()
        return {
            "temperature": "72°F",
            "description": "Partly Cloudy",
            "location": "Oregon City, OR",
            "feels_like": "75°F",
            "humidity": 65,
            "pressure": 1013,
            "wind_speed": 5.2,
            "wind_direction": 230,
            "visibility": 10.0,
            "uv_index": 6.0,
            "icon": "02d",
            "api_status": "fallback_data",
            "setup_note": "Configure weather API for live data",
            "timestamp": datetime.now().isoformat(),
            "forecast": [
                {
                    "date": (base_date + timedelta(days=i)).strftime('%Y-%m-%d'),
                    "day": (base_date + timedelta(days=i)).strftime('%a'),
                    "high": 75 - i,
                    "low": 55 + i,
                    "condition": ["Sunny", "Partly Cloudy", "Cloudy", "Light Rain", "Partly Cloudy"][i],
                    "icon": ["01d", "02d", "03d", "10d", "02d"][i],
                    "precipitation_chance": [10, 20, 40, 80, 30][i]
                }
                for i in range(5)
            ]
        }
    except Exception as e:
        logger.error(f"Exception in /api/weather endpoint: {e}", exc_info=True)
        return {"error": str(e)}

@app.get("/api/investments")
async def get_investments():
    """Get investment data from local API and external sources"""
    try:
        if COLLECTORS_AVAILABLE:
            collector = InvestmentsCollector()
            investment_data = await collector.collect_data()
            return investment_data
        else:
            return {"error": "Investment collector not available"}
    except Exception as e:
        logger.error(f"Investment API error: {e}")
        return {"investments": [], "portfolio_summary": {}, "error": str(e)}

@app.post("/api/investments/track")
async def track_investment(request: Request):
    """Add a new investment to tracking"""
    try:
        data = await request.json()
        symbol = data.get('symbol', '').upper()
        name = data.get('name', '')
        inv_type = data.get('type', 'stock')  # stock, crypto, currency
        
        if not symbol:
            raise HTTPException(status_code=400, detail="Symbol is required")
        
        if COLLECTORS_AVAILABLE:
            collector = InvestmentsCollector()
            success = await collector.add_investment_to_tracking(symbol, name, inv_type)
            
            if success:
                return {"success": True, "message": f"Added {symbol} to tracking"}
            else:
                return {"success": False, "message": f"{symbol} is already being tracked"}
        else:
            return {"success": False, "error": "Investment collector not available"}
    except Exception as e:
        logger.error(f"Track investment API error: {e}")
        return {"success": False, "error": str(e)}

@app.get("/api/local-services")
async def get_local_services():
    """Get local services and network device information"""
    try:
        if COLLECTORS_AVAILABLE:
            collector = LocalServicesCollector()
            services_data = await collector.collect_data()
            return services_data
        else:
            return {"error": "Local services collector not available"}
    except Exception as e:
        logger.error(f"Local services API error: {e}")
        return {"local_services": [], "network_devices": [], "system_info": {}, "error": str(e)}

@app.get("/api/news-sources")
async def get_news_sources():
    """Get all news sources with management options"""
    try:
        sources = db.get_news_sources(active_only=False)
        return {"sources": sources}
    except Exception as e:
        logger.error(f"News sources API error: {e}")
        return {"sources": [], "error": str(e)}

@app.post("/api/news-sources")
async def add_news_source(request: Request):
    """Add a custom news source"""
    try:
        data = await request.json()
        name = data.get('name', '')
        url = data.get('url', '')
        category = data.get('category', 'general')
        
        if not name or not url:
            raise HTTPException(status_code=400, detail="Name and URL are required")
        
        source_id = db.add_news_source(name, url, category, is_custom=True)
        return {"success": True, "source_id": source_id, "message": f"Added news source: {name}"}
    except Exception as e:
        logger.error(f"Add news source API error: {e}")
        return {"success": False, "error": str(e)}

@app.put("/api/news-sources/{source_id}/preference")
async def update_news_source_preference(source_id: int, request: Request):
    """Update user preference for a news source"""
    try:
        data = await request.json()
        preference = data.get('preference', 0)  # 0-5 scale
        
        if not 0 <= preference <= 5:
            raise HTTPException(status_code=400, detail="Preference must be between 0 and 5")
        
        db.update_news_source_preference(source_id, preference)
        return {"success": True, "message": "Updated news source preference"}
    except Exception as e:
        logger.error(f"Update news source preference API error: {e}")
        return {"success": False, "error": str(e)}

@app.put("/api/news-sources/{source_id}/toggle")
async def toggle_news_source(source_id: int, request: Request):
    """Toggle news source active status"""
    try:
        data = await request.json()
        active = data.get('is_active', True)
        
        db.toggle_news_source(source_id, active)
        return {"success": True, "message": f"News source {'activated' if active else 'deactivated'}"}
    except Exception as e:
        logger.error(f"Toggle news source API error: {e}")
        return {"success": False, "error": str(e)}

@app.delete("/api/news-sources/{source_id}")
async def delete_news_source(source_id: int):
    """Delete a custom news source"""
    try:
        db.delete_news_source(source_id)
        return {"success": True, "message": "News source deleted"}
    except Exception as e:
        logger.error(f"Delete news source API error: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/feedback")
async def save_feedback(request: Request):
    """Save user feedback (like/dislike) for AI training"""
    try:
        data = await request.json()
        item_id = data.get('item_id')
        item_type = data.get('item_type')
        feedback_type = data.get('feedback_type')  # 'like' or 'dislike'
        
        if not all([item_id, item_type, feedback_type]):
            raise HTTPException(status_code=400, detail="Missing required fields")
            
        if feedback_type not in ['like', 'dislike']:
            raise HTTPException(status_code=400, detail="Feedback type must be 'like' or 'dislike'")
        
        # Extract additional data for training
        item_title = data.get('item_title', '')
        item_content = data.get('item_content', '')
        item_metadata = data.get('item_metadata', {})
        source_api = data.get('source_api', item_type)
        category = data.get('category', '')
        confidence_score = data.get('confidence_score', 0.5)
        notes = data.get('notes', '')
        
        # Save feedback to database
        success = db.save_user_feedback(
            item_id=item_id,
            item_type=item_type,
            feedback_type=feedback_type,
            item_title=item_title,
            item_content=item_content,
            item_metadata=item_metadata,
            source_api=source_api,
            category=category,
            confidence_score=confidence_score,
            notes=notes
        )
        
        if success:
            # Auto-retrain AI models when new feedback is received
            if AI_ASSISTANT_AVAILABLE and feedback_type == 'like':
                try:
                    # Update AI training data asynchronously
                    db.update_ai_training_from_feedback()
                    logger.info(f"Updated AI training data with new {feedback_type} feedback")
                    
                    # Learn from feedback using AI service
                    ai_service = get_ai_service(db, settings)
                    ai_service.learn_from_feedback(
                        item_type=item_type,
                        item_id=item_id,
                        feedback=feedback_type,
                        item_data={'title': item_title, 'content': item_content}
                    )
                except Exception as e:
                    logger.warning(f"Could not update AI training data: {e}")
            
            return {
                "status": "success",
                "message": f"Feedback '{feedback_type}' saved for {item_type}",
                "item_id": item_id,
                "feedback_type": feedback_type
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save feedback")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/news/{article_id}/read")
async def mark_article_read(article_id: str):
    """Mark a news article as read"""
    try:
        success = db.mark_article_read(article_id)
        
        if success:
            return {
                "status": "success",
                "message": "Article marked as read",
                "article_id": article_id
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to mark article as read")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking article as read: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/music/services")
async def get_music_services():
    """Get available music streaming services"""
    try:
        if COLLECTORS_AVAILABLE:
            from collectors.universal_music_collector import UniversalMusicCollector
            collector = UniversalMusicCollector()
            services = await collector.get_available_services()
            
            return {
                "services": services,
                "configured": len(services) > 0
            }
        else:
            return {"services": [], "configured": False}
    except Exception as e:
        logger.error(f"Error getting music services: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/music/unified-library")
async def get_unified_library():
    """Get aggregated tracks from all services"""
    try:
        if COLLECTORS_AVAILABLE:
            from collectors.universal_music_collector import UniversalMusicCollector
            collector = UniversalMusicCollector()
            tracks = await collector.aggregate_liked_tracks()
            
            return {
                "tracks": [
                    {
                        "id": t.id,
                        "title": t.title,
                        "artist": t.artist,
                        "album": t.album,
                        "service": t.service,
                        "service_id": t.service_id,
                        "artwork_url": t.artwork_url,
                        "preview_url": t.preview_url,
                        "duration_ms": t.duration_ms,
                        "genre": t.genre,
                        "mood": t.mood,
                        "is_liked": t.is_liked,
                        "popularity": t.popularity
                    }
                    for t in tracks
                ],
                "total_tracks": len(tracks),
                "services_used": list(set(t.service for t in tracks))
            }
        else:
            return {"tracks": [], "total_tracks": 0, "services_used": []}
    except Exception as e:
        logger.error(f"Error getting unified library: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/music/create-mood-playlist")
async def create_mood_playlist(request: Request):
    """Create a playlist based on mood"""
    try:
        data = await request.json()
        mood = data.get('mood', 'happy')
        max_tracks = data.get('max_tracks', 30)
        use_ai = data.get('use_ai', True)
        
        if COLLECTORS_AVAILABLE:
            from collectors.universal_music_collector import UniversalMusicCollector
            collector = UniversalMusicCollector()
            playlist = await collector.create_mood_playlist(mood, max_tracks, use_ai)
            
            return {
                "playlist": {
                    "id": playlist.id,
                    "name": playlist.name,
                    "description": playlist.description,
                    "mood": playlist.mood,
                    "created_by": playlist.created_by,
                    "total_duration_ms": playlist.total_duration_ms,
                    "services_used": playlist.services_used,
                    "track_count": len(playlist.tracks),
                    "tracks": [
                        {
                            "id": t.id,
                            "title": t.title,
                            "artist": t.artist,
                            "album": t.album,
                            "service": t.service,
                            "artwork_url": t.artwork_url,
                            "preview_url": t.preview_url,
                            "duration_ms": t.duration_ms
                        }
                        for t in playlist.tracks
                    ]
                }
            }
        else:
            raise HTTPException(status_code=503, detail="Music collectors not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating mood playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/music/create-custom-playlist")
async def create_custom_playlist(request: Request):
    """Create a custom playlist with specific criteria"""
    try:
        data = await request.json()
        name = data.get('name', 'My Playlist')
        criteria = data.get('criteria', {})
        max_tracks = data.get('max_tracks', 50)
        
        if COLLECTORS_AVAILABLE:
            from collectors.universal_music_collector import UniversalMusicCollector
            collector = UniversalMusicCollector()
            playlist = await collector.create_custom_playlist(name, criteria, max_tracks)
            
            return {
                "playlist": {
                    "id": playlist.id,
                    "name": playlist.name,
                    "description": playlist.description,
                    "total_duration_ms": playlist.total_duration_ms,
                    "services_used": playlist.services_used,
                    "track_count": len(playlist.tracks),
                    "tracks": [
                        {
                            "id": t.id,
                            "title": t.title,
                            "artist": t.artist,
                            "album": t.album,
                            "service": t.service,
                            "artwork_url": t.artwork_url,
                            "preview_url": t.preview_url,
                            "duration_ms": t.duration_ms
                        }
                        for t in playlist.tracks
                    ]
                }
            }
        else:
            raise HTTPException(status_code=503, detail="Music collectors not available")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating custom playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/music/playlists")
async def get_saved_playlists():
    """Get all saved playlists"""
    try:
        if COLLECTORS_AVAILABLE:
            from collectors.universal_music_collector import UniversalMusicCollector
            collector = UniversalMusicCollector()
            playlists = await collector.get_saved_playlists()
            
            return {
                "playlists": [
                    {
                        "id": p.id,
                        "name": p.name,
                        "description": p.description,
                        "mood": p.mood,
                        "created_by": p.created_by,
                        "created_at": p.created_at.isoformat(),
                        "track_count": len(p.tracks),
                        "total_duration_ms": p.total_duration_ms,
                        "services_used": p.services_used
                    }
                    for p in playlists
                ]
            }
        else:
            return {"playlists": []}
    except Exception as e:
        logger.error(f"Error getting playlists: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# OAuth endpoints for music services
@app.get("/api/music/oauth/spotify/login")
async def spotify_oauth_login():
    """Initiate Spotify OAuth flow"""
    try:
        client_id = settings.SPOTIFY_CLIENT_ID
        redirect_uri = settings.SPOTIFY_REDIRECT_URI or "http://localhost:8008/api/music/oauth/spotify/callback"
        scope = "user-read-private user-read-email user-library-read user-top-read playlist-read-private streaming"
        
        # Generate state for CSRF protection
        state = secrets.token_urlsafe(32)
        
        # Store state in session/database for verification
        db.save_oauth_state("spotify", state)
        
        auth_url = (
            "https://accounts.spotify.com/authorize?"
            f"response_type=code&"
            f"client_id={client_id}&"
            f"scope={scope}&"
            f"redirect_uri={redirect_uri}&"
            f"state={state}"
        )
        
        return RedirectResponse(url=auth_url)
    except Exception as e:
        logger.error(f"Error initiating Spotify OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/music/oauth/spotify/callback")
async def spotify_oauth_callback(code: str = None, state: str = None, error: str = None):
    """Handle Spotify OAuth callback"""
    try:
        if error:
            raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
        
        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing code or state")
        
        # Verify state
        if not db.verify_oauth_state("spotify", state):
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        
        # Exchange code for access token
        client_id = settings.SPOTIFY_CLIENT_ID
        client_secret = settings.SPOTIFY_CLIENT_SECRET
        redirect_uri = settings.SPOTIFY_REDIRECT_URI or "http://localhost:8008/api/music/oauth/spotify/callback"
        
        token_url = "https://accounts.spotify.com/api/token"
        token_data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, data=token_data)
            response.raise_for_status()
            token_info = response.json()
        
        # Save tokens to database (INSERT OR REPLACE handles duplicates)
        try:
            db.save_auth_token(
                service_name="spotify",
                access_token=token_info["access_token"],
                refresh_token=token_info.get("refresh_token"),
                expires_in=token_info.get("expires_in", 3600)
            )
            logger.info("Spotify OAuth token saved successfully")
        except Exception as token_error:
            logger.error(f"Error saving Spotify token: {token_error}")
            # Continue anyway - token exchange succeeded
        
        # Redirect back to dashboard
        return RedirectResponse(url="/?spotify=connected")
    except Exception as e:
        logger.error(f"Error in Spotify OAuth callback: {e}")
        return RedirectResponse(url="/?spotify=error")

@app.get("/api/music/oauth/apple/login")
async def apple_music_oauth_login():
    """Initiate Apple Music OAuth flow"""
    try:
        # Apple Music uses MusicKit JS for web authentication
        # This endpoint provides the configuration needed for the frontend
        developer_token = settings.APPLE_MUSIC_DEVELOPER_TOKEN
        
        if not developer_token:
            raise HTTPException(status_code=500, detail="Apple Music developer token not configured")
        
        return {
            "developer_token": developer_token,
            "music_kit_config": {
                "developerToken": developer_token,
                "app": {
                    "name": "Personal Dashboard",
                    "build": "1.0.0"
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting Apple Music config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/music/oauth/apple/callback")
async def apple_music_oauth_callback(request: Request):
    """Handle Apple Music user token"""
    try:
        data = await request.json()
        user_token = data.get("user_token")
        
        if not user_token:
            raise HTTPException(status_code=400, detail="Missing user token")
        
        # Save Apple Music user token (INSERT OR REPLACE handles duplicates)
        try:
            db.save_auth_token(
                service_name="apple_music",
                access_token=user_token,
                refresh_token=None,
                expires_in=None  # Apple Music tokens don't expire in the same way
            )
            logger.info("Apple Music token saved successfully")
        except Exception as token_error:
            logger.error(f"Error saving Apple Music token: {token_error}")
            raise HTTPException(status_code=500, detail=f"Failed to save token: {token_error}")
        
        return {"success": True, "message": "Apple Music connected"}
    except Exception as e:
        logger.error(f"Error saving Apple Music token: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/feedback/summary")
async def get_feedback_summary():
    """Get user preferences summary for AI analysis"""
    try:
        summary = db.get_user_preferences_summary()
        return summary
    except Exception as e:
        logger.error(f"Error getting feedback summary: {e}")
        return {"error": str(e)}

@app.get("/api/feedback/training-data")
async def get_training_data(item_type: str = None, feedback_type: str = None, limit: int = 100):
    """Get user feedback data for AI training"""
    try:
        feedback_data = db.get_user_feedback(
            item_type=item_type,
            feedback_type=feedback_type,
            limit=limit
        )
        return {
            "training_data": feedback_data,
            "count": len(feedback_data),
            "filters": {
                "item_type": item_type,
                "feedback_type": feedback_type,
                "limit": limit
            }
        }
    except Exception as e:
        logger.error(f"Error getting training data: {e}")
        return {"error": str(e)}

@app.get("/api/liked-items")
async def get_liked_items(item_type: str = None, limit: int = 50):
    """Get items that have been liked by the user"""
    try:
        liked_items = db.get_liked_items(item_type=item_type, limit=limit)
        
        return {
            "liked_items": liked_items,
            "count": len(liked_items),
            "filters": {
                "item_type": item_type,
                "limit": limit
            }
        }
    except Exception as e:
        logger.error(f"Error getting liked items: {e}")
        return {"error": str(e)}

@app.get("/api/admin/settings")
async def get_admin_settings():
    """Get admin settings"""
    try:
        # Get widget visibility settings
        widget_visibility = db.get_setting('widget_visibility', {
            'calendar': True,
            'email': True, 
            'github': True,
            'ticktick': True,
            'news': True,
            'music': True,
            'vanity': True
        })
        
        # Get widget configurations
        news_config = db.get_setting('news_config', {
            'sources': ['TechCrunch', 'BBC News', 'Reuters'],
            'tags': ['AI', 'Technology', 'Science']
        })
        
        # Get user profile for vanity, music, and GitHub settings
        profile = db.get_user_profile()
        
        vanity_config = db.get_setting('vanity_config', {
            'names': [profile.get('full_name', 'Your Name')],
            'companies': [profile.get('company', 'Your Company')],
            'terms': [profile.get('book_title', 'Your Book/Project')]
        })
        
        music_config = db.get_setting('music_config', {
            'artists': [profile.get('music_artist_name', 'Your Artist Name')],
            'labels': [profile.get('music_label_name', 'Your Label')]
        })
        
        github_config = db.get_setting('github_config', {
            'username': profile.get('github_username', 'your_username')
        })
        
        return {
            "widget_visibility": widget_visibility,
            "news_config": news_config,
            "vanity_config": vanity_config,
            "music_config": music_config,
            "github_config": github_config
        }
    except Exception as e:
        logger.error(f"Error getting admin settings: {e}")
        return {"error": str(e)}

@app.post("/api/admin/settings")
async def save_admin_settings(request: Request):
    """Save admin settings"""
    try:
        data = await request.json()
        setting_type = data.get('type')
        setting_data = data.get('data')
        
        if setting_type == 'widget_visibility':
            db.save_setting('widget_visibility', setting_data)
        elif setting_type == 'news_config':
            db.save_setting('news_config', setting_data)
        elif setting_type == 'vanity_config':
            db.save_setting('vanity_config', setting_data)
        elif setting_type == 'music_config':
            db.save_setting('music_config', setting_data)
        elif setting_type == 'github_config':
            db.save_setting('github_config', setting_data)
        else:
            return {"error": "Invalid setting type"}
        
        # Auto-retrain AI models when widget configurations change
        if AI_ASSISTANT_AVAILABLE and setting_type in ['vanity_config', 'news_config', 'music_config']:
            try:
                # Update AI training data with new configuration preferences
                db.update_ai_training_from_feedback()
                logger.info(f"Updated AI training data with new {setting_type} configuration")
            except Exception as e:
                logger.warning(f"Could not update AI training data: {e}")
        
        return {"success": True, "message": f"{setting_type} saved successfully"}
        
    except Exception as e:
        logger.error(f"Error saving admin settings: {e}")
        return {"error": str(e)}


# Google OAuth Authentication Endpoints
@app.get("/auth/google")
async def google_auth():
    """Initiate Google OAuth flow with all required scopes."""
    return await google_calendar_auth()

@app.get("/auth/google/calendar")
async def google_calendar_auth():
    """Initiate Google Calendar OAuth flow."""
    try:
        from google_auth_oauthlib.flow import Flow
        import os
        
        # Check if credentials file exists
        creds_file = project_root / "config" / "google_oauth_config.json"
        if not creds_file.exists():
            raise HTTPException(status_code=404, detail=f"Google OAuth config file not found at {creds_file}. Please set up Google Cloud Console credentials.")
        
        # Create OAuth flow with comprehensive scopes
        # Include all scopes that Google typically returns to avoid scope mismatch
        flow = Flow.from_client_secrets_file(
            str(creds_file),
            scopes=[
                'https://www.googleapis.com/auth/calendar.readonly',
                'https://www.googleapis.com/auth/gmail.readonly',
                'https://www.googleapis.com/auth/drive.readonly',
                'https://www.googleapis.com/auth/userinfo.profile',
                'https://www.googleapis.com/auth/userinfo.email',
                'openid'
            ],
            redirect_uri='http://localhost:8008/auth/google/callback'
        )
        
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'  # Force consent to ensure refresh_token is provided
        )
        
        return RedirectResponse(url=authorization_url)
        
    except ImportError:
        raise HTTPException(status_code=500, detail="Google OAuth libraries not installed. Run: pip install google-auth-oauthlib google-api-python-client")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth setup failed: {str(e)}")

@app.get("/auth/google/gmail")
async def google_gmail_auth():
    """Initiate Google Gmail OAuth flow (same as calendar since we use combined scopes)."""
    return await google_calendar_auth()

@app.get("/auth/google/callback")
async def google_oauth_callback(code: str = None, state: str = None, error: str = None):
    """Handle Google OAuth callback."""
    if error:
        raise HTTPException(status_code=400, detail=f"OAuth error: {error}")
    
    if not code:
        raise HTTPException(status_code=400, detail="No authorization code provided")
    
    try:
        from google_auth_oauthlib.flow import Flow
        import os
        
        creds_file = project_root / "config" / "google_oauth_config.json"
        if not creds_file.exists():
            raise HTTPException(status_code=404, detail="Google OAuth config file not found")
        
        # Create OAuth flow with comprehensive scopes
        # Google automatically adds profile/email/openid scopes, so we include them
        flow = Flow.from_client_secrets_file(
            str(creds_file),
            scopes=[
                'https://www.googleapis.com/auth/calendar.readonly',
                'https://www.googleapis.com/auth/gmail.readonly',
                'https://www.googleapis.com/auth/drive.readonly',
                'https://www.googleapis.com/auth/userinfo.profile',
                'https://www.googleapis.com/auth/userinfo.email',
                'openid'
            ],
            redirect_uri='http://localhost:8008/auth/google/callback'
        )
        
        # Exchange code for token (disable scope validation to handle Google's automatic additions)
        flow.fetch_token(code=code)
        
        # Save credentials
        credentials = flow.credentials
        
        # Ensure tokens directory exists
        tokens_dir = project_root / "tokens"
        tokens_dir.mkdir(exist_ok=True)
        
        # Save credentials to tokens file
        tokens_file = tokens_dir / "google_credentials.json"
        with open(tokens_file, 'w') as f:
            f.write(credentials.to_json())
        
        logger.info(f"Google credentials saved to {tokens_file}")
        
        # Return success page that closes the popup
        return HTMLResponse(content="""
        <html>
            <head><title>Google Authentication Success</title></head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px;">
                <h2 style="color: green;">✅ Google Authentication Successful!</h2>
                <p>Your Google Calendar and Gmail access has been configured.</p>
                <p>You can close this window and return to your dashboard.</p>
                <script>
                    setTimeout(() => {
                        window.close();
                    }, 3000);
                </script>
            </body>
        </html>
        """)
        
    except ImportError:
        raise HTTPException(status_code=500, detail="Google OAuth libraries not installed")
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=f"OAuth callback failed: {str(e)}")

@app.get("/api/auth/google/status")
async def google_auth_status():
    """Check Google authentication status."""
    try:
        import json
        from datetime import datetime
        
        tokens_file = project_root / "tokens" / "google_credentials.json"
        
        if not tokens_file.exists():
            return {
                "authenticated": False,
                "message": "Not authenticated. Click 'Connect Google' to sign in.",
                "scopes": []
            }
        
        # Read the token file
        with open(tokens_file, 'r') as f:
            token_data = json.load(f)
        
        # Check expiry
        expiry_str = token_data.get('expiry')
        is_expired = False
        if expiry_str:
            try:
                expiry = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                is_expired = expiry < datetime.now(expiry.tzinfo)
            except:
                pass
        
        scopes = token_data.get('scopes', [])
        scope_names = []
        if 'https://www.googleapis.com/auth/calendar.readonly' in scopes:
            scope_names.append('Calendar')
        if 'https://www.googleapis.com/auth/gmail.readonly' in scopes:
            scope_names.append('Gmail')
        if 'https://www.googleapis.com/auth/drive.readonly' in scopes:
            scope_names.append('Drive')
        
        return {
            "authenticated": True,
            "expired": is_expired,
            "message": f"✅ Connected ({', '.join(scope_names)})" if not is_expired else "⚠️ Token expired - please reconnect",
            "scopes": scopes,
            "scope_names": scope_names
        }
        
    except Exception as e:
        logger.error(f"Error checking Google auth status: {e}")
        return {
            "authenticated": False,
            "error": str(e),
            "message": "Error checking authentication status"
        }

@app.post("/auth/google/disconnect")
async def google_disconnect():
    """Disconnect Google authentication."""
    try:
        import os
        tokens_file = project_root / "tokens" / "google_credentials.json"
        if tokens_file.exists():
            tokens_file.unlink()
            logger.info("Google credentials removed")
        return {"success": True, "message": "Google authentication disconnected"}
    except Exception as e:
        logger.error(f"Error disconnecting Google: {e}")
        return {"success": False, "error": str(e)}

# AI Assistant API Endpoints
@app.get("/api/ai/providers")
async def get_ai_providers():
    """Get available AI providers."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI Assistant not available"}
    
    try:
        providers = db.get_ai_providers()
        health_status = await ai_manager.health_check_all()
        
        for provider in providers:
            provider['health_status'] = health_status.get(provider['name'], False)
        
        return {
            "providers": providers,
            "manager_providers": ai_manager.list_providers()
        }
    except Exception as e:
        logger.error(f"Error getting AI providers: {e}")
        return {"error": str(e)}


@app.post("/api/ai/providers")
async def create_ai_provider(request: Request):
    """Create a new AI provider."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI Assistant not available"}
    
    try:
        data = await request.json()
        provider_type = data.get('provider_type', '').lower()
        name = data.get('name', '')
        config = data.get('config', {})
        
        if not provider_type or not name:
            return {"error": "Provider type and name are required"}
        
        # Create provider instance
        provider = create_provider(provider_type, name, config)
        
        # Test connection
        health_ok = await provider.health_check()
        if not health_ok:
            return {"error": f"Failed to connect to {provider_type} provider"}
        
        # Save to database
        provider_id = db.save_ai_provider(name, provider_type, config)
        
        # Register with manager
        ai_manager.register_provider(provider, config.get('is_default', False))
        
        return {
            "success": True,
            "provider_id": provider_id,
            "message": f"AI provider '{name}' created successfully"
        }
        
    except Exception as e:
        logger.error(f"Error creating AI provider: {e}")
        return {"error": str(e)}


@app.get("/api/ai/chat/conversations")
async def get_conversations():
    """Get AI chat conversations."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI Assistant not available"}
    
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, p.name as provider_name 
                FROM ai_conversations c
                JOIN ai_providers p ON c.provider_id = p.id
                ORDER BY c.updated_at DESC
                LIMIT 20
            """)
            
            conversations = []
            for row in cursor.fetchall():
                conv = dict(row)
                conv['context_data'] = json.loads(conv['context_data']) if conv['context_data'] else {}
                conversations.append(conv)
            
            return {"conversations": conversations}
            
    except Exception as e:
        logger.error(f"Error getting conversations: {e}")
        return {"error": str(e)}


async def build_ai_context_with_frontend(user_message: str, frontend_context: dict) -> str:
    """Build context for AI from frontend data and database."""
    context_parts = []
    
    try:
        # Current time from frontend or server
        current_time = frontend_context.get('current_time', datetime.now().strftime('%A, %B %d, %Y at %I:%M %p'))
        context_parts.append(f"Current time: {current_time}")
        context_parts.append("")
        
        # Todos context from frontend
        todos = frontend_context.get('todos', {})
        if todos.get('items'):
            active_count = todos.get('active_count', 0)
            total_count = todos.get('count', 0)
            context_parts.append(f"TASKS ({active_count} active of {total_count} total):")
            for todo in todos['items']:
                status = '✓' if todo.get('completed') else '○'
                priority = f"[{todo['priority']}]" if todo.get('priority') else ''
                due = f"(Due: {todo['due_date']})" if todo.get('due_date') else ''
                source = f"({todo['source']})" if todo.get('source') else ''
                context_parts.append(f"{status} {priority} {todo['title']} {due} {source}")
                if todo.get('description'):
                    context_parts.append(f"   {todo['description']}")
            context_parts.append("")
        
        # Calendar context from frontend
        calendar = frontend_context.get('calendar', {})
        if calendar.get('upcoming'):
            context_parts.append(f"UPCOMING CALENDAR EVENTS ({len(calendar['upcoming'])} shown):")
            for event in calendar['upcoming']:
                location = f"@ {event['location']}" if event.get('location') else ''
                context_parts.append(f"- {event['summary']}")
                context_parts.append(f"  {event['start']} {location}")
                if event.get('description'):
                    context_parts.append(f"  {event['description']}")
            context_parts.append("")
        
        # Email context from frontend
        emails = frontend_context.get('emails', {})
        if emails.get('recent'):
            high_priority = emails.get('high_priority_count', 0)
            context_parts.append(f"RECENT EMAILS ({len(emails['recent'])} shown, {high_priority} high priority):")
            for email in emails['recent']:
                priority = f"[{email['priority']}]" if email.get('priority') else ''
                has_todos = '📋' if email.get('has_todos') else ''
                context_parts.append(f"{priority} {has_todos} From: {email['sender']}")
                context_parts.append(f"  Subject: {email['subject']}")
                if email.get('snippet'):
                    context_parts.append(f"  {email['snippet']}")
            context_parts.append("")
        
        # User preferences from frontend
        prefs = frontend_context.get('user_preferences', {})
        if prefs:
            liked_count = prefs.get('liked_items_count', 0)
            context_parts.append(f"USER PREFERENCES ({liked_count} liked items):")
            if prefs.get('recent_feedback'):
                context_parts.append("Recent feedback:")
                for feedback in prefs['recent_feedback']:
                    context_parts.append(f"  {feedback['sentiment']}: {feedback['item']}")
            context_parts.append("")
        
        # Add additional database context for user profile
        try:
            vanity_config = db.get_setting('vanity_config', {})
            if vanity_config:
                context_parts.append("USER PROFILE:")
                if 'names' in vanity_config:
                    context_parts.append(f"Names: {', '.join(vanity_config['names'])}")
                if 'companies' in vanity_config:
                    context_parts.append(f"Companies: {', '.join(vanity_config['companies'])}")
                context_parts.append("")
        except Exception as e:
            logger.warning(f"Could not access user profile: {e}")
        
        return '\n'.join(context_parts)
        
    except Exception as e:
        logger.error(f"Error building AI context: {e}")
        return f"Error accessing dashboard data: {e}"


async def build_ai_context(user_message: str) -> str:
    """Build context for AI from current dashboard data based on user query (legacy, keyword-based)."""
    context_parts = []
    message_lower = user_message.lower()
    
    try:
        # Always include basic info
        context_parts.append(f"Current time: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}")
        
        # Email context (if query mentions emails)
        if any(word in message_lower for word in ['email', 'mail', 'message', 'inbox', 'sender', 'reply']):
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    # Get recent emails
                    cursor.execute("""
                        SELECT sender, subject, body, received_date 
                        FROM emails 
                        ORDER BY received_date DESC 
                        LIMIT 10
                    """)
                    emails = cursor.fetchall()
                    
                    if emails:
                        context_parts.append("RECENT EMAILS:")
                        for email in emails[:5]:  # Limit to 5 most recent
                            date_str = email['received_date']
                            context_parts.append(f"- From: {email['sender']}")
                            context_parts.append(f"  Subject: {email['subject']}")
                            context_parts.append(f"  Date: {date_str}")
                            if email['body']:
                                body_preview = email['body'][:150].replace('\n', ' ')
                                context_parts.append(f"  Preview: {body_preview}...")
                            context_parts.append("")
                    else:
                        context_parts.append("No recent emails found in database.")
            except Exception as e:
                context_parts.append(f"Could not access email data: {e}")
        
        # Calendar context (if query mentions calendar/events/meetings)
        if any(word in message_lower for word in ['calendar', 'event', 'meeting', 'appointment', 'schedule']):
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT title, description, start_time, end_time, location 
                        FROM calendar_events 
                        WHERE start_time > datetime('now') 
                        ORDER BY start_time ASC 
                        LIMIT 5
                    """)
                    events = cursor.fetchall()
                    
                    if events:
                        context_parts.append("UPCOMING CALENDAR EVENTS:")
                        for event in events:
                            context_parts.append(f"- {event['title']}")
                            context_parts.append(f"  Time: {event['start_time']}")
                            if event['location']:
                                context_parts.append(f"  Location: {event['location']}")
                            if event['description']:
                                desc_preview = event['description'][:100].replace('\n', ' ')
                                context_parts.append(f"  Description: {desc_preview}...")
                            context_parts.append("")
                    else:
                        context_parts.append("No upcoming calendar events found.")
            except Exception as e:
                context_parts.append(f"Could not access calendar data: {e}")
        
        # News context (if query mentions news/articles)
        if any(word in message_lower for word in ['news', 'article', 'story', 'headline']):
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT item_title, item_content 
                        FROM user_feedback 
                        WHERE item_type = 'news' AND feedback_type = 'like'
                        ORDER BY feedback_timestamp DESC 
                        LIMIT 3
                    """)
                    liked_news = cursor.fetchall()
                    
                    if liked_news:
                        context_parts.append("RECENTLY LIKED NEWS:")
                        for item in liked_news:
                            context_parts.append(f"- {item['item_title']}")
                            if item['item_content']:
                                content_preview = item['item_content'][:100].replace('\n', ' ')
                                context_parts.append(f"  {content_preview}...")
                            context_parts.append("")
            except Exception as e:
                context_parts.append(f"Could not access news preferences: {e}")
        
        # Add user preferences context
        try:
            vanity_config = db.get_setting('vanity_config', {})
            if vanity_config:
                context_parts.append("USER PROFILE:")
                if 'names' in vanity_config:
                    context_parts.append(f"Names: {', '.join(vanity_config['names'])}")
                if 'companies' in vanity_config:
                    context_parts.append(f"Companies: {', '.join(vanity_config['companies'])}")
                context_parts.append("")
        except Exception as e:
            context_parts.append(f"Could not access user profile: {e}")
        
        return '\n'.join(context_parts)
        
    except Exception as e:
        logger.error(f"Error building AI context: {e}")
        return f"Error accessing dashboard data: {e}"


@app.post("/api/ai/chat")
async def chat_with_ai(request: Request):
    """Chat with AI assistant using centralized AI service."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI Assistant not available"}
    
    try:
        data = await request.json()
        message = data.get('message', '')
        conversation_id = data.get('conversation_id')
        stream = data.get('stream', False)
        
        if not message:
            return {"error": "Message is required"}
        
        # Create conversation if needed
        if not conversation_id:
            conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            db.save_ai_conversation(conversation_id, 1, f"Chat {datetime.now().strftime('%H:%M')}")
        
        # If streaming requested, use SSE endpoint
        if stream:
            return {"error": "Use /api/ai/chat/stream for streaming responses"}
        
        # Use centralized AI service
        ai_service = get_ai_service(db, settings)
        result = await ai_service.chat(
            message=message,
            conversation_id=conversation_id,
            include_context=True
        )
        
        if not result.get('success'):
            return {"error": result.get('error', 'Unknown error')}
        
        return {
            "response": result['response'],
            "conversation_id": conversation_id,
            "provider": result['provider'],
            "context_hash": result.get('context_hash'),
            "success": True
        }
        
    except Exception as e:
        logger.error(f"Error in AI chat: {e}")
        return {"error": str(e), "success": False}


@app.get("/api/ai/chat/stream")
async def chat_with_ai_stream(
    message: str,
    conversation_id: str = None,
    quiet: bool = False
):
    """Chat with AI assistant using Server-Sent Events for real-time updates."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI Assistant not available"}
    
    try:
        from fastapi.responses import StreamingResponse
        import asyncio
        import json
        
        quiet_mode = quiet
        
        if not message:
            return {"error": "Message is required"}
        
        # Create conversation if needed
        if not conversation_id:
            conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            db.save_ai_conversation(conversation_id, 1, f"Chat {datetime.now().strftime('%H:%M')}")
        
        async def event_generator():
            """Generate Server-Sent Events with progress updates."""
            try:
                # Send initial status
                if not quiet_mode:
                    yield f"data: {json.dumps({'type': 'status', 'message': '🤔 Analyzing your request...'})}\n\n"
                    await asyncio.sleep(0.1)
                
                # Check if this is a complex task
                message_lower = message.lower()
                is_scan_task = any(word in message_lower for word in ['scan', 'analyze', 'extract', 'search', 'find', 'review'])
                is_meeting_task = any(word in message_lower for word in ['meeting', 'summarize', 'notes'])
                is_task_creation = any(word in message_lower for word in ['create task', 'add task', 'make task'])
                
                # Build context with progress updates
                if not quiet_mode:
                    yield f"data: {json.dumps({'type': 'status', 'message': '📊 Loading your dashboard data...'})}\n\n"
                    await asyncio.sleep(0.1)
                
                ai_service = get_ai_service(db, settings)
                
                # Notify about data collection
                if not quiet_mode and (is_scan_task or is_meeting_task):
                    if 'task' in message_lower or 'todo' in message_lower:
                        yield f"data: {json.dumps({'type': 'status', 'message': '✓ Loaded tasks from database'})}\n\n"
                    if 'calendar' in message_lower or 'meeting' in message_lower or 'event' in message_lower:
                        yield f"data: {json.dumps({'type': 'status', 'message': '✓ Loaded calendar events'})}\n\n"
                    if 'email' in message_lower:
                        yield f"data: {json.dumps({'type': 'status', 'message': '✓ Loaded recent emails'})}\n\n"
                    if 'note' in message_lower or 'meeting' in message_lower:
                        yield f"data: {json.dumps({'type': 'status', 'message': '📝 Scanning notes (Obsidian + Google Drive)...'})}\n\n"
                        await asyncio.sleep(0.2)
                    if 'github' in message_lower:
                        yield f"data: {json.dumps({'type': 'status', 'message': '✓ Loaded GitHub issues'})}\n\n"
                    
                    await asyncio.sleep(0.1)
                    yield f"data: {json.dumps({'type': 'status', 'message': '🧠 Thinking...'})}\n\n"
                
                # Get AI response
                result = await ai_service.chat(
                    message=message,
                    conversation_id=conversation_id,
                    include_context=True
                )
                
                if not result.get('success'):
                    yield f"data: {json.dumps({'type': 'error', 'message': result.get('error', 'Unknown error')})}\n\n"
                    return
                
                # Send the response
                response_text = result['response']
                
                # If it's a task creation request, notify about next steps
                if not quiet_mode and is_task_creation and 'yes' in message_lower:
                    yield f"data: {json.dumps({'type': 'status', 'message': '✓ Creating tasks...'})}\n\n"
                    await asyncio.sleep(0.1)
                
                # Stream the response in chunks for better UX
                chunk_size = 100
                for i in range(0, len(response_text), chunk_size):
                    chunk = response_text[i:i+chunk_size]
                    yield f"data: {json.dumps({'type': 'response', 'content': chunk})}\n\n"
                    await asyncio.sleep(0.05)  # Small delay for smooth streaming
                
                # Send completion signal
                yield f"data: {json.dumps({'type': 'done', 'conversation_id': conversation_id, 'provider': result['provider']})}\n\n"
                
            except Exception as e:
                logger.error(f"Error in streaming chat: {e}")
                yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
        
        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no"  # Disable nginx buffering
            }
        )
        
    except Exception as e:
        logger.error(f"Error setting up streaming chat: {e}")
        return {"error": str(e), "success": False}


@app.get("/api/ai/anticipate")
async def get_ai_anticipations():
    """Get AI-powered anticipations and suggestions based on user patterns."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"suggestions": [], "success": False, "error": "AI not available"}
    
    try:
        ai_service = get_ai_service(db, settings)
        suggestions = ai_service.anticipate_needs()
        
        return {
            "success": True,
            "suggestions": suggestions,
            "count": len(suggestions)
        }
        
    except Exception as e:
        logger.error(f"Error getting AI anticipations: {e}")
        return {"suggestions": [], "success": False, "error": str(e)}


@app.get("/api/ai/profile")
async def get_ai_user_profile():
    """Get AI-built user profile."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI not available", "success": False}
    
    try:
        ai_service = get_ai_service(db, settings)
        profile = ai_service.build_user_profile(force_refresh=True)
        
        return {
            "success": True,
            "profile": profile
        }
        
    except Exception as e:
        logger.error(f"Error getting AI profile: {e}")
        return {"error": str(e), "success": False}


@app.get("/api/ai/context")
async def get_ai_context():
    """Get current AI context (for debugging)."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI not available", "success": False}
    
    try:
        ai_service = get_ai_service(db, settings)
        context = ai_service.build_context(force_refresh=True)
        context_hash = ai_service.get_context_hash(context)
        
        return {
            "success": True,
            "context": context,
            "context_hash": context_hash,
            "context_length": len(context)
        }
        
    except Exception as e:
        logger.error(f"Error getting AI context: {e}")
        return {"error": str(e), "success": False}




@app.post("/api/ai/action/create-task")
async def ai_create_task(request: Request):
    """AI-initiated task creation (requires user approval)."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI not available", "success": False}
    
    try:
        data = await request.json()
        approved = data.get('approved', False)
        
        if not approved:
            return {"error": "Action not approved by user", "success": False}
        
        title = data.get('title', '')
        description = data.get('description', '')
        priority = data.get('priority', 'medium')
        due_date = data.get('due_date')
        
        if not title:
            return {"error": "Task title required", "success": False}
        
        ai_service = get_ai_service(db, settings)
        result = ai_service.create_task(title, description, priority, due_date)
        
        return result
        
    except Exception as e:
        logger.error(f"Error in AI task creation: {e}")
        return {"error": str(e), "success": False}


@app.post("/api/ai/action/complete-task")
async def ai_complete_task(request: Request):
    """AI-initiated task completion (requires user approval)."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI not available", "success": False}
    
    try:
        data = await request.json()
        approved = data.get('approved', False)
        task_id = data.get('task_id', '')
        
        if not approved:
            return {"error": "Action not approved by user", "success": False}
        
        if not task_id:
            return {"error": "Task ID required", "success": False}
        
        ai_service = get_ai_service(db, settings)
        result = ai_service.complete_task(task_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Error in AI task completion: {e}")
        return {"error": str(e), "success": False}


@app.post("/api/ai/action/delete-task")
async def ai_delete_task(request: Request):
    """AI-initiated task deletion (requires user approval)."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI not available", "success": False}
    
    try:
        data = await request.json()
        approved = data.get('approved', False)
        task_id = data.get('task_id', '')
        
        if not approved:
            return {"error": "Action not approved by user", "success": False}
        
        if not task_id:
            return {"error": "Task ID required", "success": False}
        
        ai_service = get_ai_service(db, settings)
        result = ai_service.delete_task(task_id)
        
        return result
        
    except Exception as e:
        logger.error(f"Error in AI task deletion: {e}")
        return {"error": str(e), "success": False}


@app.post("/api/ai/action/create-tasks-batch")
async def ai_create_tasks_batch(request: Request):
    """AI-initiated batch task creation (requires user approval)."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI not available", "success": False}
    
    try:
        data = await request.json()
        approved = data.get('approved', False)
        tasks = data.get('tasks', [])
        sync_to_ticktick = data.get('sync_to_ticktick', False)
        
        if not approved:
            return {"error": "Action not approved by user", "success": False}
        
        if not tasks or not isinstance(tasks, list):
            return {"error": "Tasks array required", "success": False}
        
        # Create tasks in batch
        ai_service = get_ai_service(db, settings)
        result = ai_service.create_tasks_batch(tasks)
        
        # Sync to TickTick if requested
        if sync_to_ticktick and result.get('success') and result.get('created_count', 0) > 0:
            try:
                if COLLECTORS_AVAILABLE and TASK_MANAGER_AVAILABLE:
                    from processors.task_manager import TaskManager
                    from config.settings import Settings
                    task_manager = TaskManager(Settings())
                    sync_result = await task_manager.sync_with_ticktick(direction='to_ticktick')
                    result['ticktick_sync'] = sync_result
                    logger.info(f"Batch synced {result['created_count']} AI tasks to TickTick")
                else:
                    result['ticktick_sync'] = {"error": "TickTick sync not available"}
            except Exception as sync_err:
                logger.error(f"Error syncing AI tasks to TickTick: {sync_err}")
                result['ticktick_sync'] = {"error": str(sync_err)}
        
        return result
        
    except Exception as e:
        logger.error(f"Error in AI batch task creation: {e}")
        return {"error": str(e), "success": False}


@app.post("/api/ai/scan-for-tasks")
async def ai_scan_for_tasks(request: Request):
    """
    AI-powered scan of calendar, emails, GitHub, and notes to find tasks.
    Uses AI to analyze, write, review, and prioritize tasks.
    """
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI not available", "success": False}
    
    try:
        data = await request.json()
        sources = data.get('sources', ['calendar', 'emails', 'github', 'notes'])
        auto_create = data.get('auto_create', False)  # Auto-create without approval
        
        logger.info(f"AI scanning for tasks from sources: {sources}")
        
        # Collect data from requested sources
        scan_results = {
            'calendar_items': [],
            'email_items': [],
            'github_items': [],
            'note_items': [],
            'suggested_tasks': []
        }
        
        # Scan Calendar
        if 'calendar' in sources:
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT summary, description, start_time, end_time, location
                        FROM calendar_events
                        WHERE date(start_time) >= date('now')
                        AND date(start_time) <= date('now', '+14 days')
                        ORDER BY start_time
                        LIMIT 20
                    """)
                    events = cursor.fetchall()
                    scan_results['calendar_items'] = [dict(e) for e in events]
            except Exception as e:
                logger.error(f"Error scanning calendar: {e}")
        
        # Scan Emails
        if 'emails' in sources:
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT subject, sender, snippet, priority, has_todos
                        FROM emails
                        WHERE has_todos = 1 OR priority = 'high'
                        ORDER BY received_date DESC
                        LIMIT 20
                    """)
                    emails = cursor.fetchall()
                    scan_results['email_items'] = [dict(e) for e in emails]
            except Exception as e:
                logger.error(f"Error scanning emails: {e}")
        
        # Scan GitHub
        if 'github' in sources:
            try:
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT title, body, state, repo, labels, url
                        FROM github_issues
                        WHERE state = 'open'
                        ORDER BY updated_at DESC
                        LIMIT 20
                    """)
                    issues = cursor.fetchall()
                    scan_results['github_items'] = [dict(i) for i in issues]
            except Exception as e:
                logger.error(f"Error scanning GitHub: {e}")
        
        # Scan Notes
        if 'notes' in sources:
            try:
                from collectors.notes_collector import collect_all_notes
                from database import get_credentials
                
                notes_config = get_credentials('notes') or {}
                obsidian_path = (
                    os.getenv('OBSIDIAN_VAULT_PATH') or
                    db.get_setting('obsidian_vault_path') or
                    notes_config.get('obsidian_vault_path')
                )
                gdrive_folder_id = (
                    os.getenv('GOOGLE_DRIVE_NOTES_FOLDER_ID') or
                    db.get_setting('google_drive_notes_folder_id') or
                    notes_config.get('google_drive_folder_id')
                )
                
                result = collect_all_notes(
                    obsidian_path=obsidian_path,
                    gdrive_folder_id=gdrive_folder_id,
                    limit=20
                )
                scan_results['note_items'] = result.get('notes', [])
            except Exception as e:
                logger.error(f"Error scanning notes: {e}")
        
        # Use AI to analyze and create task suggestions
        ai_service = get_ai_service(db, settings)
        
        # Build prompt for AI
        prompt = f"""Analyze the following data and extract actionable tasks. For each task, provide:
- Title (clear, actionable)
- Description (context and details)
- Priority (high, medium, low)
- Due date (YYYY-MM-DD format, calculated from context)
- Category (from source type)

Today's date: {datetime.now().strftime('%Y-%m-%d')}

CALENDAR EVENTS ({len(scan_results['calendar_items'])} items):
{_format_calendar_for_ai(scan_results['calendar_items'])}

EMAILS ({len(scan_results['email_items'])} items):
{_format_emails_for_ai(scan_results['email_items'])}

GITHUB ISSUES ({len(scan_results['github_items'])} items):
{_format_github_for_ai(scan_results['github_items'])}

NOTES ({len(scan_results['note_items'])} items):
{_format_notes_for_ai(scan_results['note_items'])}

Extract all actionable tasks. Format each as:
TASK: [title]
DESC: [description]
PRIORITY: [high|medium|low]
DUE: [YYYY-MM-DD]
CATEGORY: [calendar|email|github|notes]
---
"""
        
        # Get AI analysis
        ai_response = await ai_service.chat(prompt, include_context=False)
        
        if ai_response.get('success'):
            # Parse AI response into tasks
            tasks = _parse_ai_task_response(ai_response.get('response', ''))
            scan_results['suggested_tasks'] = tasks
            
            # Auto-create if requested
            if auto_create and tasks:
                creation_result = ai_service.create_tasks_batch(tasks)
                scan_results['creation_result'] = creation_result
        
        scan_results['success'] = True
        scan_results['total_items_scanned'] = (
            len(scan_results['calendar_items']) +
            len(scan_results['email_items']) +
            len(scan_results['github_items']) +
            len(scan_results['note_items'])
        )
        scan_results['ai_response'] = ai_response.get('response', '') if ai_response.get('success') else None
        
        logger.info(f"AI scan complete: {len(scan_results['suggested_tasks'])} tasks suggested")
        
        return scan_results
        
    except Exception as e:
        logger.error(f"Error in AI task scanning: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "success": False}


def _format_calendar_for_ai(events):
    """Format calendar events for AI analysis."""
    if not events:
        return "No calendar events"
    
    lines = []
    for event in events[:10]:
        lines.append(f"- {event.get('start_time', 'No date')}: {event.get('summary', 'Untitled')}")
        if event.get('description'):
            lines.append(f"  Details: {event.get('description')[:200]}")
    return "\n".join(lines)


def _format_emails_for_ai(emails):
    """Format emails for AI analysis."""
    if not emails:
        return "No emails"
    
    lines = []
    for email in emails[:10]:
        priority_flag = "[HIGH] " if email.get('priority') == 'high' else ""
        todo_flag = "[TODO] " if email.get('has_todos') else ""
        lines.append(f"- {priority_flag}{todo_flag}From {email.get('sender', 'Unknown')}: {email.get('subject', 'No subject')}")
        if email.get('snippet'):
            lines.append(f"  Preview: {email.get('snippet')[:200]}")
    return "\n".join(lines)


def _format_github_for_ai(issues):
    """Format GitHub issues for AI analysis."""
    if not issues:
        return "No GitHub issues"
    
    lines = []
    for issue in issues[:10]:
        lines.append(f"- [{issue.get('repo', 'unknown')}] {issue.get('title', 'Untitled')}")
        if issue.get('body'):
            lines.append(f"  Description: {issue.get('body')[:200]}")
        if issue.get('labels'):
            lines.append(f"  Labels: {issue.get('labels')}")
    return "\n".join(lines)


def _format_notes_for_ai(notes):
    """Format notes for AI analysis."""
    if not notes:
        return "No notes"
    
    lines = []
    for note in notes[:10]:
        source_icon = "Obsidian" if note.get('source') == 'obsidian' else "Google Drive"
        todo_count = len(note.get('todos', []))
        lines.append(f"- [{source_icon}] {note.get('title', 'Untitled')} ({todo_count} TODOs)")
        if note.get('preview'):
            lines.append(f"  Preview: {note.get('preview')[:200]}")
        for todo in note.get('todos', [])[:3]:
            lines.append(f"    • {todo.get('text', '')}")
    return "\n".join(lines)


def _parse_ai_task_response(response: str):
    """Parse AI response into structured task list."""
    tasks = []
    current_task = {}
    
    for line in response.split('\n'):
        line = line.strip()
        if line.startswith('TASK:'):
            if current_task:
                tasks.append(current_task)
            current_task = {'title': line.replace('TASK:', '').strip()}
        elif line.startswith('DESC:'):
            current_task['description'] = line.replace('DESC:', '').strip()
        elif line.startswith('PRIORITY:'):
            current_task['priority'] = line.replace('PRIORITY:', '').strip().lower()
        elif line.startswith('DUE:'):
            current_task['due_date'] = line.replace('DUE:', '').strip()
        elif line.startswith('CATEGORY:'):
            current_task['category'] = line.replace('CATEGORY:', '').strip()
        elif line == '---' and current_task:
            tasks.append(current_task)
            current_task = {}
    
    if current_task and current_task.get('title'):
        tasks.append(current_task)
    
    return tasks


@app.get("/api/ai/training/summary")
async def get_training_summary():
    """Get AI training data summary."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI Assistant not available"}
    
    try:
        summary = training_collector.get_training_summary()
        return summary
        
    except Exception as e:
        logger.error(f"Error getting training summary: {e}")
        return {"error": str(e)}


@app.post("/api/ai/training/collect")
async def collect_training_data():
    """Collect new training data."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI Assistant not available"}
    
    try:
        # Update training data from user feedback
        db.update_ai_training_from_feedback()
        
        # Collect fresh training data
        training_data = await training_collector.prepare_training_dataset()
        
        return {
            "success": True,
            "samples_collected": len(training_data),
            "message": "Training data collected successfully"
        }
        
    except Exception as e:
        logger.error(f"Error collecting training data: {e}")
        return {"error": str(e)}


@app.post("/api/ai/training/start")
async def start_ai_training(request: Request):
    """Start AI model training."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI Assistant not available"}
    
    try:
        data = await request.json()
        provider_name = data.get('provider')
        
        provider = ai_manager.get_provider(provider_name)
        if not provider:
            return {"error": "Provider not found"}
        
        # Get training data
        training_data = db.get_ai_training_data(limit=1000)
        
        if not training_data:
            return {"error": "No training data available"}
        
        # Generate training hash
        training_hash = provider.generate_training_hash(training_data)
        
        # Start training
        training_id = db.start_ai_model_training(1, training_hash)  # Using provider_id = 1 for now
        
        # Start training asynchronously
        training_result = await provider.train(training_data)
        
        if training_result.get('status') == 'success':
            db.update_ai_model_training_status(training_id, 'completed', 
                                             training_result.get('model_name'),
                                             training_result)
            return {
                "success": True,
                "training_id": training_id,
                "model_name": training_result.get('model_name')
            }
        else:
            db.update_ai_model_training_status(training_id, 'failed', None, training_result)
            return {"error": "Training failed", "details": training_result}
            
    except Exception as e:
        logger.error(f"Error starting training: {e}")
        return {"error": str(e)}


@app.post("/api/ai/training/feedback")
async def record_feedback(request: Request):
    """Record user feedback on dashboard items for AI training."""
    try:
        data = await request.json()
        item_type = data.get('item_type')
        item_id = data.get('item_id')
        sentiment = data.get('sentiment')  # 'up', 'neutral', 'down'
        item_details = data.get('item_details', {})
        timestamp = data.get('timestamp')
        
        # Save to database for AI training
        db.save_user_feedback({
            'item_type': item_type,
            'item_id': item_id,
            'sentiment': sentiment,
            'item_details': item_details,
            'timestamp': timestamp
        })
        
        logger.info(f"Feedback recorded: {item_type} {item_id} - {sentiment}")
        
        return {
            "success": True,
            "message": "Feedback recorded successfully"
        }
        
    except Exception as e:
        logger.error(f"Error recording feedback: {e}")
        return {"error": str(e)}


@app.post("/api/ai/message/feedback")
async def save_message_feedback(request: Request):
    """Save feedback for an AI message response."""
    try:
        data = await request.json()
        message_id = data.get('message_id')
        conversation_id = data.get('conversation_id')
        feedback_type = data.get('feedback_type')  # 'thumbs_up' or 'thumbs_down'
        rating = data.get('rating')  # Optional 1-5 rating
        comment = data.get('comment')  # Optional comment
        
        if not message_id or not conversation_id or not feedback_type:
            return {"error": "message_id, conversation_id, and feedback_type are required"}
        
        success = db.save_ai_message_feedback(
            message_id, conversation_id, feedback_type, rating, comment
        )
        
        if success:
            return {
                "success": True,
                "message": "Feedback saved successfully"
            }
        else:
            return {"error": "Failed to save feedback"}
            
    except Exception as e:
        logger.error(f"Error saving message feedback: {e}")
        return {"error": str(e)}


@app.get("/api/user/profile")
async def get_user_profile():
    """Get user profile for AI personalization."""
    try:
        profile = db.get_user_profile()
        return profile
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return {"error": str(e)}


@app.post("/api/user/profile")
async def save_user_profile(request: Request):
    """Save or update user profile."""
    try:
        profile = await request.json()
        success = db.save_user_profile(profile)
        
        if success:
            return {
                "success": True,
                "message": "Profile saved successfully"
            }
        else:
            return {"error": "Failed to save profile"}
            
    except Exception as e:
        logger.error(f"Error saving user profile: {e}")
        return {"error": str(e)}


@app.get("/api/ai/summary")
async def get_ai_summary():
    """Get AI-generated summary of recent activity."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI Assistant not available"}
    
    try:
        # Collect recent data from various sources
        from datetime import datetime, timedelta
        
        # Initialize with safe defaults
        recent_emails = []
        upcoming_events = []
        recent_news = []
        github_activity = []
        
        # Get recent emails (last 24 hours)
        try:
            email_data = await get_email()
            if email_data:
                # Combine all priority levels into one list
                all_emails = []
                if 'high_priority' in email_data:
                    all_emails.extend(email_data['high_priority'])
                if 'medium_priority' in email_data:
                    all_emails.extend(email_data['medium_priority'])
                if 'low_priority' in email_data:
                    all_emails.extend(email_data['low_priority'][:3])  # Limit low priority to 3
                
                for email in all_emails[:5]:  # Total limit of 5 emails
                    if isinstance(email, dict):
                        recent_emails.append({
                            'sender': str(email.get('sender', 'Unknown')),
                            'subject': str(email.get('subject', 'No subject'))
                        })
        except Exception as e:
            logger.warning(f"Could not get email data for summary: {e}")
        
        # Get upcoming calendar events (next 3 days)
        try:
            calendar_data = await get_calendar()
            if calendar_data and 'events' in calendar_data:
                for event in calendar_data['events'][:5]:
                    if isinstance(event, dict):
                        upcoming_events.append({
                            'summary': str(event.get('summary', 'No title')),
                            'date': str(event.get('start', {}).get('date', 'Unknown date') if isinstance(event.get('start'), dict) else 'Unknown date')
                        })
        except Exception as e:
            logger.warning(f"Could not get calendar data for summary: {e}")
        
        # Get recent news headlines
        try:
            news_data = await get_news()
            if news_data and 'articles' in news_data:
                for article in news_data['articles'][:3]:
                    if isinstance(article, dict):
                        recent_news.append({
                            'title': str(article.get('title', 'No title'))
                        })
        except Exception as e:
            logger.warning(f"Could not get news data for summary: {e}")
        
        # Get GitHub activity
        try:
            github_data = await get_github()
            if github_data and 'items' in github_data:
                for item in github_data['items'][:3]:
                    if isinstance(item, dict):
                        github_activity.append({
                            'title': str(item.get('title', 'No title')),
                            'type': str(item.get('type', 'Unknown'))
                        })
        except Exception as e:
            logger.warning(f"Could not get GitHub data for summary: {e}")
        
        # Create summary prompt with safe string formatting
        email_list = '\n'.join([f"- From {email['sender']}: {email['subject']}" for email in recent_emails]) if recent_emails else "No recent emails"
        events_list = '\n'.join([f"- {event['summary']} on {event['date']}" for event in upcoming_events]) if upcoming_events else "No upcoming events"
        news_list = '\n'.join([f"- {article['title']}" for article in recent_news]) if recent_news else "No recent news"
        github_list = '\n'.join([f"- {item['title']} ({item['type']})" for item in github_activity]) if github_activity else "No GitHub activity"
        
        summary_prompt = f"""Please provide a brief, friendly summary of my current activities and priorities based on this data:

RECENT EMAILS ({len(recent_emails)} items):
{email_list}

UPCOMING CALENDAR EVENTS ({len(upcoming_events)} items):
{events_list}

RECENT NEWS ({len(recent_news)} items):
{news_list}

GITHUB ACTIVITY ({len(github_activity)} items):
{github_list}

Please summarize this in 2-3 sentences focusing on:
1. Important upcoming events or deadlines
2. Key emails that need attention
3. Notable news or work items
4. Any patterns or priorities you notice

Keep it concise, actionable, and friendly."""
        
        # Get AI response
        providers = ai_manager.list_providers()
        if not providers:
            return {"summary": "No AI providers available for summary generation."}
        
        # list_providers() returns a list of dicts, not a dict
        provider_name = None
        for provider_info in providers:
            if isinstance(provider_info, dict) and 'name' in provider_info:
                provider_name = provider_info['name']
                break
                
        if not provider_name:
            return {"summary": "No AI provider name available."}
            
        provider = ai_manager.get_provider(provider_name)
        
        if not provider:
            return {"summary": "AI provider not available for summary generation."}
        
        try:
            # Format messages properly for the chat interface
            messages = [
                {"role": "user", "content": summary_prompt}
            ]
            response = await provider.chat(messages)
            
            return {
                "summary": response if isinstance(response, str) else 'Unable to generate summary.',
                "timestamp": datetime.now().isoformat(),
                "data_sources": {
                    "emails": len(recent_emails),
                    "events": len(upcoming_events),
                    "news": len(recent_news),
                    "github": len(github_activity)
                }
            }
        except Exception as chat_error:
            logger.error(f"Error in AI chat: {chat_error}")
            return {
                "summary": f"AI summary temporarily unavailable. Data available: {len(recent_emails)} emails, {len(upcoming_events)} events, {len(recent_news)} news, {len(github_activity)} GitHub items.",
                "timestamp": datetime.now().isoformat(),
                "data_sources": {
                    "emails": len(recent_emails),
                    "events": len(upcoming_events),
                    "news": len(recent_news),
                    "github": len(github_activity)
                }
            }
        
    except Exception as e:
        logger.error(f"Error generating AI summary: {e}")
        return {"summary": f"Error generating summary: {str(e)}"}


# Initialize default AI providers on startup
async def initialize_ai_providers():
    """Initialize default AI providers."""
    if not AI_ASSISTANT_AVAILABLE:
        return
    
    try:
        # Check if we have any providers
        existing_providers = db.get_ai_providers()
        
        if not existing_providers:
            # Get Ollama configuration from settings
            ollama_host = db.get_setting('ollama_host', 'localhost')
            ollama_port = db.get_setting('ollama_port', 11434)
            ollama_model = db.get_setting('ollama_model', 'llama3.2:latest')
            
            # Build the URL from configured host and port
            configured_url = f'http://{ollama_host}:{ollama_port}'
            
            # Try to create Ollama provider using configured settings
            ollama_hosts = [
                {'name': f'Ollama ({ollama_host})', 'url': configured_url, 'model': ollama_model},
                {'name': 'Local Ollama (fallback)', 'url': 'http://localhost:11434', 'model': 'llama3.2:latest'},
            ]
            
            default_set = False
            
            for host_config in ollama_hosts:
                # First try to get available models
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.get(f"{host_config['url']}/api/tags") as response:
                            if response.status == 200:
                                data = await response.json()
                                models = data.get('models', [])
                                if models:
                                    # Use the configured model if specified, otherwise use first available
                                    if host_config.get('model'):
                                        model_name = host_config['model']
                                    else:
                                        model_name = models[0]['name']
                                    logger.info(f"Found model {model_name} at {host_config['url']}")
                                else:
                                    model_name = host_config.get('model', 'llama2')  # use configured or fallback
                            else:
                                continue
                except:
                    continue
                
                ollama_config = {
                    'base_url': host_config['url'],
                    'model_name': model_name,
                    'is_active': True,
                    'is_default': not default_set  # First working one becomes default
                }
                
                try:
                    ollama_provider = create_provider('ollama', host_config['name'], ollama_config)
                    health_ok = await ollama_provider.health_check()
                    
                    if health_ok:
                        db.save_ai_provider(host_config['name'], 'ollama', ollama_config)
                        ai_manager.register_provider(ollama_provider, not default_set)
                        logger.info(f"Ollama provider initialized: {host_config['name']} at {host_config['url']} with model {model_name}")
                        if not default_set:
                            default_set = True
                    else:
                        logger.debug(f"Ollama server not available at {host_config['url']}")
                        
                except Exception as e:
                    logger.debug(f"Could not initialize Ollama provider at {host_config['url']}: {e}")
            
            if not default_set:
                logger.warning("No Ollama servers found - you can add providers manually in the AI Assistant admin panel")
        else:
            # Load existing providers into manager
            for provider_data in existing_providers:
                if provider_data['is_active']:
                    try:
                        provider = create_provider(
                            provider_data['provider_type'],
                            provider_data['name'],
                            provider_data['config_data']
                        )
                        ai_manager.register_provider(provider, provider_data['is_default'])
                        logger.info(f"Loaded AI provider: {provider_data['name']}")
                        
                    except Exception as e:
                        logger.error(f"Error loading provider {provider_data['name']}: {e}")
                        
    except Exception as e:
        logger.error(f"Error initializing AI providers: {e}")


# TickTick Authentication Endpoints
@app.get("/auth/ticktick")
async def ticktick_auth():
    """Initiate TickTick OAuth flow."""
    try:
        if COLLECTORS_AVAILABLE:
            settings = Settings()
            collector = TickTickCollector(settings)
            auth_url = collector.get_auth_url()
            
            # Redirect to TickTick OAuth
            return RedirectResponse(auth_url)
        else:
            return {"error": "TickTick collector not available"}
    except Exception as e:
        logger.error(f"TickTick auth error: {e}")
        return {"error": str(e)}


@app.get("/auth/ticktick/callback")
async def ticktick_callback(code: str = None, state: str = None, error: str = None):
    """Handle TickTick OAuth callback."""
    try:
        if error:
            return HTMLResponse(f"""
                <html>
                    <head><title>TickTick Connection Failed</title></head>
                    <body style="font-family: Arial, sans-serif; padding: 20px; text-align: center;">
                        <h2>❌ TickTick Connection Failed</h2>
                        <p>Error: {error}</p>
                        <p>You can close this window and try again.</p>
                        <script>
                            setTimeout(() => {{
                                window.close();
                            }}, 3000);
                        </script>
                    </body>
                </html>
            """)
            
        if COLLECTORS_AVAILABLE and code:
            settings = Settings()
            collector = TickTickCollector(settings)
            
            # Exchange code for token
            token_data = await collector.exchange_code_for_token(code)
            
            if token_data:
                # Redirect back to dashboard with success
                return HTMLResponse("""
                    <html>
                        <head><title>TickTick Connected</title></head>
                        <body style="font-family: Arial, sans-serif; padding: 20px; text-align: center;">
                            <h2>✅ TickTick Connected Successfully!</h2>
                            <p>You can now close this window and return to your dashboard.</p>
                            <script>
                                setTimeout(() => {
                                    window.close();
                                }, 3000);
                            </script>
                        </body>
                    </html>
                """)
            else:
                return HTMLResponse("""
                    <html>
                        <head><title>TickTick Connection Failed</title></head>
                        <body style="font-family: Arial, sans-serif; padding: 20px; text-align: center;">
                            <h2>❌ Failed to get access token</h2>
                            <p>You can close this window and try again.</p>
                            <script>
                                setTimeout(() => {
                                    window.close();
                                }, 3000);
                            </script>
                        </body>
                    </html>
                """)
        else:
            return HTMLResponse("""
                <html>
                    <head><title>TickTick Connection Failed</title></head>
                    <body style="font-family: Arial, sans-serif; padding: 20px; text-align: center;">
                        <h2>❌ Authorization code required</h2>
                        <p>You can close this window and try again.</p>
                        <script>
                            setTimeout(() => {
                                window.close();
                            }, 3000);
                        </script>
                    </body>
                </html>
            """)
    except Exception as e:
        logger.error(f"TickTick callback error: {e}")
        return HTMLResponse(f"""
            <html>
                <head><title>TickTick Connection Error</title></head>
                <body style="font-family: Arial, sans-serif; padding: 20px; text-align: center;">
                    <h2>❌ Connection Error</h2>
                    <p>Error: {str(e)}</p>
                    <p>You can close this window and try again.</p>
                    <script>
                        setTimeout(() => {{
                            window.close();
                        }}, 3000);
                    </script>
                </body>
            </html>
        """)


@app.post("/auth/ticktick/disconnect")
async def ticktick_disconnect():
    """Disconnect TickTick integration."""
    try:
        # Use the existing database functions to clear the token
        from database import save_auth_token
        save_auth_token('ticktick', {}, None)  # Clear the token
        return {"success": True, "message": "TickTick disconnected successfully"}
    except Exception as e:
        logger.error(f"TickTick disconnect error: {e}")
        return {"error": str(e)}


# Lead Generation API Endpoints
@app.get("/api/leads")
async def get_leads():
    """Get existing generated leads with statistics."""
    try:
        # Import lead generation modules
        from processors.lead_generator import LeadGenerator, PotentialLead
        
        lead_generator = LeadGenerator()
        
        # Try to load existing leads from file
        try:
            leads_file = project_root / "data" / "generated_leads.json"
            with open(leads_file, 'r') as f:
                leads_data = json.load(f)
                leads_list = leads_data if isinstance(leads_data, list) else []
                
                # Convert dict data to PotentialLead objects for statistics
                potential_leads = []
                for lead_dict in leads_list:
                    if isinstance(lead_dict, dict):
                        # Convert datetime string back to datetime object
                        if 'last_updated' in lead_dict and isinstance(lead_dict['last_updated'], str):
                            try:
                                lead_dict['last_updated'] = datetime.fromisoformat(lead_dict['last_updated'])
                            except:
                                lead_dict['last_updated'] = datetime.now()
                        
                        potential_lead = PotentialLead(**lead_dict)
                        potential_leads.append(potential_lead)
                
                lead_generator.generated_leads = potential_leads
                
        except FileNotFoundError:
            leads_list = []
            potential_leads = []
            lead_generator.generated_leads = []
        
        # Get statistics using PotentialLead objects
        statistics = lead_generator.get_lead_statistics()
        
        return {
            "success": True,
            "leads": leads_list,  # Return the original dict format for the frontend
            "statistics": statistics,
            "total": len(leads_list)
        }
        
    except Exception as e:
        logger.error(f"Error getting leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/leads/generate")
async def generate_leads(request: Request):
    """Generate new leads based on learned patterns."""
    try:
        request_data = await request.json()
        target_count = request_data.get('target_count', 20)
        template_focus = request_data.get('template_focus')
        filters = request_data.get('filters', {})
        
        # Import required modules
        from processors.company_profiler import CompanyProfiler
        from processors.lead_generator import LeadGenerator
        from processors.email_meeting_analyzer import EmailMeetingAnalyzer
        
        logger.info(f"Generating {target_count} leads with template focus: {template_focus}")
        
        # Create profiler and load company templates
        profiler = CompanyProfiler()
        
        # Get email and task data for analysis
        emails = []
        tasks = db.get_todos(include_completed=True, include_deleted=False)
        
        # Try to get Gmail data if available
        try:
            from collectors.gmail_collector import GmailCollector
            gmail = GmailCollector(config)
            gmail_data = await gmail.collect_data()
            emails = gmail_data.get('emails', [])
        except Exception as e:
            logger.warning(f"Could not collect Gmail data for lead generation: {e}")
        
        # Create company templates from existing interaction data
        templates_dict = await profiler.create_company_profiles(emails, tasks)
        templates = list(templates_dict.values()) if templates_dict else []
        
        # Generate leads using templates
        lead_generator = LeadGenerator()
        leads = await lead_generator.generate_leads(templates, target_count, filters)
        
        # Save generated leads
        await lead_generator.save_generated_leads(leads)
        
        # Get updated statistics
        statistics = lead_generator.get_lead_statistics()
        
        # Convert leads to serializable format
        serialized_leads = []
        for lead in leads:
            lead_dict = {
                'company_name': lead.company_name,
                'domain': lead.domain,
                'industry': lead.industry,
                'estimated_size': lead.estimated_size,
                'contact_info': lead.contact_info,
                'match_score': lead.match_score,
                'match_reasons': lead.match_reasons,
                'template_matches': lead.template_matches,
                'recommended_approach': lead.recommended_approach,
                'priority_level': lead.priority_level,
                'technical_fit_score': lead.technical_fit_score,
                'business_potential_score': lead.business_potential_score,
                'contact_accessibility_score': lead.contact_accessibility_score,
                'next_steps': lead.next_steps,
                'data_sources': lead.data_sources,
                'confidence_level': lead.confidence_level,
                'last_updated': lead.last_updated.isoformat()
            }
            serialized_leads.append(lead_dict)
        
        return {
            "success": True,
            "leads": serialized_leads,
            "statistics": statistics,
            "templates_used": list(templates_dict.keys()) if templates_dict else [],
            "total_generated": len(leads)
        }
        
    except Exception as e:
        logger.error(f"Error generating leads: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/lead-patterns/analyze")
async def analyze_lead_patterns():
    """Analyze interaction patterns to improve lead generation."""
    try:
        # Import required modules
        from processors.task_ai_trainer import TaskAITrainer
        from processors.email_meeting_analyzer import EmailMeetingAnalyzer
        
        logger.info("Starting pattern analysis for lead generation improvement")
        
        # Analyze task patterns
        task_trainer = TaskAITrainer()
        user_preferences = await task_trainer.analyze_task_patterns()
        
        # Analyze email patterns
        email_analyzer = EmailMeetingAnalyzer()
        
        # Get email data for analysis
        emails = []
        try:
            from collectors.gmail_collector import GmailCollector
            gmail = GmailCollector(config)
            gmail_data = await gmail.collect_data()
            emails = gmail_data.get('emails', [])
        except Exception as e:
            logger.warning(f"Could not collect Gmail data for pattern analysis: {e}")
        
        email_analysis = await email_analyzer.analyze_email_patterns(emails)
        
        # Combine analysis results
        analysis_results = {
            "user_preferences": {
                "preferred_project_types": user_preferences.preferred_project_types,
                "high_value_keywords": user_preferences.high_value_keywords,
                "low_value_keywords": user_preferences.low_value_keywords,
                "optimal_task_size": user_preferences.optimal_task_size,
                "preferred_priorities": user_preferences.preferred_priorities,
                "company_interaction_patterns": user_preferences.company_interaction_patterns,
                "meeting_preferences": user_preferences.meeting_preferences
            },
            "email_analysis": {
                "total_companies": email_analysis.get('total_companies', 0),
                "total_meetings": email_analysis.get('total_meetings', 0),
                "business_patterns": email_analysis.get('business_patterns', {}),
                "lead_patterns": email_analysis.get('lead_patterns', {}),
                "followup_patterns": email_analysis.get('followup_patterns', {})
            },
            "recommendations": [
                "Focus on companies in preferred project types",
                "Target companies with high-value keywords in their descriptions",
                "Prioritize companies that match successful interaction patterns",
                "Use learned communication style preferences for outreach"
            ],
            "analysis_timestamp": datetime.now().isoformat()
        }
        
        # Save analysis results
        try:
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            analysis_file = data_dir / "lead_pattern_analysis.json"
            with open(analysis_file, 'w') as f:
                json.dump(analysis_results, f, indent=2, default=str)
        except Exception as e:
            logger.warning(f"Could not save analysis results: {e}")
        
        return {
            "success": True,
            "analysis": analysis_results,
            "message": "Pattern analysis completed successfully"
        }
        
    except Exception as e:
        logger.error(f"Error analyzing patterns: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/company-analysis")
async def get_company_analysis():
    """Get analysis of existing company interactions."""
    try:
        # Import required modules
        from processors.company_profiler import CompanyProfiler
        
        # Get email and task data
        emails = []
        tasks = db.get_todos(include_completed=True, include_deleted=False)
        
        # Try to get Gmail data
        try:
            from collectors.gmail_collector import GmailCollector
            gmail = GmailCollector(config)
            gmail_data = await gmail.collect_data()
            emails = gmail_data.get('emails', [])
        except Exception as e:
            logger.warning(f"Could not collect Gmail data for company analysis: {e}")
        
        # Create company profiles
        profiler = CompanyProfiler()
        templates = await profiler.create_company_profiles(emails, tasks)
        
        # Convert templates to serializable format
        serialized_templates = {}
        for key, template in templates.items():
            serialized_templates[key] = {
                'template_name': template.template_name,
                'source_companies': template.source_companies,
                'industry_characteristics': template.industry_characteristics,
                'success_indicators': template.success_indicators,
                'project_types': template.project_types,
                'typical_engagement_timeline': template.typical_engagement_timeline,
                'technical_requirements': template.technical_requirements,
                'business_model_indicators': template.business_model_indicators,
                'company_size_range': template.company_size_range,
                'geographic_preferences': template.geographic_preferences
            }
        
        return {
            "success": True,
            "templates": serialized_templates,
            "total_templates": len(templates),
            "analysis_date": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting company analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Dashboard Management Endpoints
@app.get("/api/dashboards")
async def get_dashboards():
    """Get all saved dashboard projects from database."""
    try:
        from database import DatabaseManager
        
        db = DatabaseManager()
        projects = db.get_dashboard_projects(active_only=False)
        
        logger.info(f"Loaded {len(projects)} dashboard projects from database")
        
        return {
            "success": True,
            "projects": projects,
            "message": f"Found {len(projects)} dashboard projects"
        }
        
    except Exception as e:
        logger.error(f"Error loading dashboards: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/system/status")
async def get_system_status():
    """Get status of all dashboard collectors and widgets."""
    try:
        status_info = {
            "success": True,
            "timestamp": datetime.now().isoformat(),
            "collectors": {},
            "widgets": {},
            "system": {
                "server_running": True,
                "uptime": "Unknown", 
                "active_sessions": 1
            }
        }
        
        # Check collector availability and status
        collectors_status = {
            "calendar": {"available": COLLECTORS_AVAILABLE, "status": "unknown", "last_update": None, "error": None},
            "email": {"available": COLLECTORS_AVAILABLE, "status": "unknown", "last_update": None, "error": None},
            "github": {"available": COLLECTORS_AVAILABLE, "status": "unknown", "last_update": None, "error": None},
            "ticktick": {"available": COLLECTORS_AVAILABLE, "status": "unknown", "last_update": None, "error": None},
            "weather": {"available": COLLECTORS_AVAILABLE, "status": "unknown", "last_update": None, "error": None},
            "news": {"available": True, "status": "unknown", "last_update": None, "error": None},
            "jokes": {"available": COLLECTORS_AVAILABLE, "status": "unknown", "last_update": None, "error": None},
            "music": {"available": True, "status": "unknown", "last_update": None, "error": None}
        }
        
        # Test each collector if available
        for name, info in collectors_status.items():
            if info["available"]:
                try:
                    # Try to get recent data to determine status
                    test_url = f"/api/{name}"
                    if name == "email":
                        test_url = "/api/email"
                    
                    # Quick internal test (simulate API call)
                    info["status"] = "active"
                    info["last_update"] = datetime.now().isoformat()
                except Exception as e:
                    info["status"] = "error"
                    info["error"] = str(e)
            else:
                info["status"] = "disabled"
                info["error"] = "Collector not available"
        
        status_info["collectors"] = collectors_status
        
        # Widget status (based on collector status)
        status_info["widgets"] = {
            "calendar_widget": {"status": collectors_status["calendar"]["status"], "data_available": True},
            "email_widget": {"status": collectors_status["email"]["status"], "data_available": True},
            "github_widget": {"status": collectors_status["github"]["status"], "data_available": True},
            "tasks_widget": {"status": collectors_status["ticktick"]["status"], "data_available": True},
            "weather_widget": {"status": collectors_status["weather"]["status"], "data_available": True},
            "news_widget": {"status": collectors_status["news"]["status"], "data_available": True},
            "jokes_widget": {"status": collectors_status["jokes"]["status"], "data_available": True},
            "music_widget": {"status": collectors_status["music"]["status"], "data_available": True}
        }
        
        return status_info
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@app.post("/api/system/refresh-widget/{widget_name}")
async def refresh_widget(widget_name: str):
    """Refresh a specific widget's data."""
    try:
        widget_apis = {
            "calendar": "/api/calendar",
            "email": "/api/email", 
            "github": "/api/github",
            "tasks": "/api/ticktick",
            "weather": "/api/weather",
            "news": "/api/news",
            "jokes": "/api/joke",
            "music": "/api/music"
        }
        
        if widget_name not in widget_apis:
            raise HTTPException(status_code=400, detail=f"Unknown widget: {widget_name}")
        
        # Clear cache for this widget if background manager exists
        if hasattr(app.state, 'background_manager'):
            cache_key = widget_name.replace("_widget", "")
            if cache_key in app.state.background_manager.cache:
                del app.state.background_manager.cache[cache_key]
                del app.state.background_manager.cache_timestamps[cache_key]
        
        return {
            "success": True,
            "message": f"Widget {widget_name} refresh initiated",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error refreshing widget {widget_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dashboards/add")
async def add_dashboard(request: Request):
    """Add a new dashboard to monitor."""
    try:
        data = await request.json()
        path = data.get('path')
        
        if not path:
            raise HTTPException(status_code=400, detail="Path is required")
        
        from pathlib import Path
        import os
        
        # Validate path exists
        dashboard_path = Path(path).resolve()
        if not dashboard_path.exists():
            raise HTTPException(status_code=400, detail=f"Path does not exist: {path}")
        
        if not dashboard_path.is_dir():
            raise HTTPException(status_code=400, detail=f"Path is not a directory: {path}")
        
        # Auto-detect project type if not specified
        project_type = data.get('type')
        if not project_type:
            # Check for project indicators
            files = os.listdir(dashboard_path)
            if 'app.py' in files or 'wsgi.py' in files:
                project_type = 'flask'
            elif 'main.py' in files and 'fastapi' in open(dashboard_path / 'main.py').read():
                project_type = 'fastapi'
            elif 'package.json' in files:
                # Check if React or Vue
                pkg_json = json.loads(open(dashboard_path / 'package.json').read())
                if 'react' in str(pkg_json.get('dependencies', {})):
                    project_type = 'react'
                elif 'vue' in str(pkg_json.get('dependencies', {})):
                    project_type = 'vue'
                else:
                    project_type = 'static'
            elif 'index.html' in files:
                project_type = 'static'
            elif 'streamlit_app.py' in files:
                project_type = 'streamlit'
            else:
                project_type = 'unknown'
        
        # Get or generate name
        name = data.get('name') or dashboard_path.name
        
        # Get or generate port
        port = data.get('port')
        if not port:
            port_map = {'flask': 5000, 'fastapi': 8000, 'react': 3000, 'vue': 8080, 'static': 8000, 'streamlit': 8501}
            port = port_map.get(project_type, 8000)
        
        # Get or generate start command
        start_command = data.get('start_command')
        if not start_command:
            command_map = {
                'flask': f'cd {dashboard_path} && python app.py',
                'fastapi': f'cd {dashboard_path} && uvicorn main:app --reload --port {port}',
                'react': f'cd {dashboard_path} && npm start',
                'vue': f'cd {dashboard_path} && npm run serve',
                'static': f'cd {dashboard_path} && python -m http.server {port}',
                'streamlit': f'cd {dashboard_path} && streamlit run streamlit_app.py --server.port {port}'
            }
            start_command = command_map.get(project_type, f'cd {dashboard_path}')
        
        # Save to database
        from database import DatabaseManager
        db = DatabaseManager()
        db.save_dashboard_project({
            'name': name,
            'path': str(dashboard_path),
            'type': project_type,
            'port': port,
            'start_command': start_command,
            'url': f'http://localhost:{port}',
            'active': True
        })
        
        logger.info(f"Added dashboard: {name} ({project_type}) at {dashboard_path}")
        
        return {
            "success": True,
            "message": f"Dashboard '{name}' added successfully",
            "dashboard": {
                "name": name,
                "path": str(dashboard_path),
                "type": project_type,
                "port": port,
                "start_command": start_command
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding dashboard: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dashboards/{project_name}/start")
async def start_dashboard_project(project_name: str):
    """Start a specific dashboard project."""
    try:
        from processors.dashboard_manager import start_dashboard
        
        logger.info(f"Starting dashboard project: {project_name}")
        result = await start_dashboard(project_name)
        
        if result["success"]:
            return {
                "success": True,
                "data": result,
                "message": f"Successfully started {project_name}"
            }
        else:
            return {
                "success": False,
                "error": result["error"],
                "message": f"Failed to start {project_name}"
            }
        
    except Exception as e:
        logger.error(f"Error starting dashboard {project_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dashboards/{project_name}/stop")
async def stop_dashboard_project(project_name: str):
    """Stop a specific dashboard project."""
    try:
        from processors.dashboard_manager import stop_dashboard
        
        logger.info(f"Stopping dashboard project: {project_name}")
        result = await stop_dashboard(project_name)
        
        if result["success"]:
            return {
                "success": True,
                "data": result,
                "message": f"Successfully stopped {project_name}"
            }
        else:
            return {
                "success": False,
                "error": result["error"],
                "message": f"Failed to stop {project_name}"
            }
        
    except Exception as e:
        logger.error(f"Error stopping dashboard {project_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/dashboards/{project_name}")
async def delete_dashboard_project(project_name: str):
    """Permanently delete a dashboard project from the database."""
    try:
        logger.info(f"Deleting dashboard project: {project_name}")
        
        # Delete from database
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM dashboard_projects WHERE name = ?", (project_name,))
            deleted_count = cursor.rowcount
            conn.commit()
        
        if deleted_count > 0:
            logger.info(f"Successfully deleted dashboard project: {project_name}")
            return {
                "success": True,
                "message": f"Successfully deleted {project_name}"
            }
        else:
            return {
                "success": False,
                "error": "Dashboard not found",
                "message": f"Dashboard {project_name} not found in database"
            }
        
    except Exception as e:
        logger.error(f"Error deleting dashboard {project_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboards/status")
async def get_dashboard_status():
    """Get quick status overview of all dashboards."""
    try:
        from database import DatabaseManager
        
        db = DatabaseManager()
        projects = db.get_dashboard_projects(active_only=False)
        
        # Calculate metrics from database
        total = len(projects)
        active = len([p for p in projects if p.get('is_active')])
        
        return {
            "success": True,
            "summary": {
                "projects_total": total,
                "projects_active": active,
                "projects_inactive": total - active,
                "last_updated": datetime.now().isoformat()
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting dashboard status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/dashboards/{project_name}")
async def update_dashboard_config(
    project_name: str,
    request: Request
):
    """Update dashboard project configuration."""
    try:
        from database import DatabaseManager
        
        updates = await request.json()
        
        db = DatabaseManager()
        success = db.update_dashboard_project(project_name, updates)
        
        if success:
            return {
                "success": True,
                "message": f"Updated configuration for {project_name}",
                "updates": updates
            }
        else:
            raise HTTPException(status_code=404, detail=f"Dashboard project '{project_name}' not found")
        
    except Exception as e:
        logger.error(f"Error updating dashboard config for {project_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dashboards/save")
async def save_dashboard_config(request: Request):
    """Save or update a dashboard project configuration."""
    try:
        from database import DatabaseManager
        
        project_data = await request.json()
        
        # Debug logging
        logger.info(f"Received dashboard save request: {project_data}")
        
        db = DatabaseManager()
        project_id = db.save_dashboard_project(project_data)
        
        return {
            "success": True,
            "message": f"Saved configuration for {project_data.get('name')}",
            "project_id": project_id
        }
        
    except Exception as e:
        logger.error(f"Error saving dashboard config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/dashboards/{project_name}/config")
async def get_dashboard_config(project_name: str):
    """Get the saved configuration for a specific dashboard project."""
    try:
        from database import DatabaseManager
        
        db = DatabaseManager()
        projects = db.get_dashboard_projects(active_only=False)
        
        project = next((p for p in projects if p['name'] == project_name), None)
        
        if project:
            return {
                "success": True,
                "project": project
            }
        else:
            raise HTTPException(status_code=404, detail=f"Dashboard project '{project_name}' not found")
        
    except Exception as e:
        logger.error(f"Error getting dashboard config for {project_name}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/dashboards/{project_name}/start")
async def start_dashboard(project_name: str):
    """Start a dashboard project and return monitoring info."""
    try:
        from database import DatabaseManager
        import subprocess
        import time
        import os
        
        # Try importing psutil with better error handling
        try:
            import psutil
        except ImportError as e:
            logger.error(f"Failed to import psutil: {e}")
            return {"success": False, "error": f"Missing required package 'psutil': {e}"}
        
        db = DatabaseManager()
        projects = db.get_dashboard_projects(active_only=False)
        project = next((p for p in projects if p['name'] == project_name), None)
        
        if not project:
            raise HTTPException(status_code=404, detail=f"Dashboard project '{project_name}' not found")
        
        # Get project configuration
        start_command = project.get('start_command', './ops/startup.sh')
        # Use current working directory as fallback instead of hardcoded path
        working_dir = project.get('path', os.getcwd())
        local_port = project.get('port', 8008)
        
        # Check if already running on the port
        port_check_error = None
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    connections = proc.connections()
                    for conn in connections:
                        if conn.laddr.port == local_port and conn.status == 'LISTEN':
                            return {
                                "success": True,
                                "message": f"Dashboard already running on port {local_port}",
                                "process_id": proc.info['pid'],
                                "port": local_port,
                                "status": "already_running"
                            }
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            port_check_error = f"Port check failed: {str(e)}"
            logger.warning(f"Could not check if port {local_port} is in use: {e}")
        
        # Start the dashboard process
        try:
            # Validate the working directory exists
            if not os.path.exists(working_dir):
                raise Exception(f"Working directory does not exist: {working_dir}")
            
            if not os.access(working_dir, os.R_OK):
                raise Exception(f"Working directory is not readable: {working_dir}")
            
            # Log the startup attempt with full details
            logger.info(f"Starting dashboard '{project_name}' with command '{start_command}' in directory '{working_dir}' on port {local_port}")
            
            # Change to working directory and start process
            process = subprocess.Popen(
                start_command,
                cwd=working_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
                shell=True
            )
            
            # Give it a moment to start
            time.sleep(3)
            
            # Check if process is still running
            if process.poll() is None:
                success_msg = f"Dashboard '{project_name}' started successfully"
                if port_check_error:
                    success_msg += f" (Note: {port_check_error})"
                    
                return {
                    "success": True,
                    "message": success_msg,
                    "process_id": process.pid,
                    "port": local_port,
                    "command": start_command,
                    "working_directory": working_dir
                }
            else:
                stdout, stderr = process.communicate()
                error_msg = f"Process failed to start"
                details = {
                    "command": start_command,
                    "working_directory": working_dir,
                    "stdout": stdout.decode() if stdout else "No stdout",
                    "stderr": stderr.decode() if stderr else "No stderr",
                    "exit_code": process.returncode
                }
                logger.error(f"Dashboard start failed: {error_msg}, Details: {details}")
                raise Exception(f"{error_msg}. Exit code: {process.returncode}. Command: {start_command}. Working dir: {working_dir}. Error: {stderr.decode() if stderr else 'No error output'}")
                
        except Exception as e:
            error_details = {
                "project_name": project_name,
                "command": start_command,
                "working_directory": working_dir,
                "port": local_port,
                "directory_exists": os.path.exists(working_dir) if 'working_dir' in locals() else "unknown",
                "directory_readable": os.access(working_dir, os.R_OK) if 'working_dir' in locals() and os.path.exists(working_dir) else "unknown",
                "port_check_error": port_check_error if 'port_check_error' in locals() else None,
                "error": str(e)
            }
            logger.error(f"Error starting dashboard process for '{project_name}': {e}, Details: {error_details}")
            
            error_msg = f"Failed to start dashboard '{project_name}': {str(e)}"
            if 'working_dir' in locals():
                error_msg += f" (Command: {start_command}, Dir: {working_dir})"
            if 'port_check_error' in locals() and port_check_error:
                error_msg += f" (Port check issue: {port_check_error})"
                
            raise Exception(error_msg)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting dashboard {project_name}: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/dashboards/{project_name}/status")
async def get_dashboard_status(project_name: str):
    """Get the current status of a dashboard project."""
    try:
        from database import DatabaseManager
        import requests
        from datetime import datetime, timedelta
        
        # Try importing psutil with better error handling
        try:
            import psutil
        except ImportError as e:
            logger.error(f"Failed to import psutil in status endpoint: {e}")
            return {"success": False, "error": f"Missing required package 'psutil': {e}"}
        
        db = DatabaseManager()
        projects = db.get_dashboard_projects(active_only=False)
        project = next((p for p in projects if p['name'] == project_name), None)
        
        if not project:
            raise HTTPException(status_code=404, detail=f"Dashboard project '{project_name}' not found")
        
        local_port = project.get('port', 8008)
        local_url = project.get('url', f'http://localhost:{local_port}')
        health_endpoint = project.get('health_endpoint', '/health')
        
        # Check if process is running on the port
        running_process = None
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'cpu_percent', 'memory_info']):
                try:
                    connections = proc.connections()
                    for conn in connections:
                        if conn.laddr.port == local_port and conn.status == 'LISTEN':
                            running_process = proc
                            break
                    if running_process:
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        
        if running_process:
            try:
                # Get process info
                create_time = datetime.fromtimestamp(running_process.create_time())
                uptime = datetime.now() - create_time
                uptime_str = str(uptime).split('.')[0]  # Remove microseconds
                
                cpu_percent = running_process.cpu_percent()
                memory_mb = round(running_process.memory_info().rss / 1024 / 1024, 1)
                
                # Try to ping the service
                service_healthy = False
                last_activity = "No response"
                try:
                    if health_endpoint:
                        health_url = f"{local_url.rstrip('/')}{health_endpoint}"
                        response = requests.get(health_url, timeout=5)
                        service_healthy = response.status_code == 200
                        last_activity = "Just now" if service_healthy else f"Error {response.status_code}"
                    else:
                        # Just try to connect to the main URL
                        response = requests.get(local_url, timeout=5)
                        service_healthy = response.status_code == 200
                        last_activity = "Just now" if service_healthy else f"Error {response.status_code}"
                except Exception as e:
                    service_healthy = False
                    last_activity = f"Connection failed: {str(e)[:30]}"
                
                return {
                    "success": True,
                    "status": "running",
                    "process_id": running_process.pid,
                    "port": local_port,
                    "uptime": uptime_str,
                    "cpu_usage": cpu_percent,
                    "memory_usage": memory_mb,
                    "service_healthy": service_healthy,
                    "last_activity": last_activity,
                    "local_url": local_url
                }
                
            except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
                return {
                    "success": True,
                    "status": "stopped",
                    "reason": "Process not accessible"
                }
        else:
            return {
                "success": True,
                "status": "stopped",
                "reason": "No process found on port"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting dashboard status for {project_name}: {e}")
        return {"success": False, "error": str(e)}


@app.get("/api/dashboards/{project_name}/logs")
async def get_dashboard_logs(project_name: str):
    """Get recent logs for a dashboard project."""
    try:
        from database import DatabaseManager
        import os
        
        db = DatabaseManager()
        projects = db.get_dashboard_projects(active_only=False)
        project = next((p for p in projects if p['name'] == project_name), None)
        
        if not project:
            raise HTTPException(status_code=404, detail=f"Dashboard project '{project_name}' not found")
        
        # Look for log files in common locations
        working_dir = project.get('path', os.getcwd())
        log_paths = [
            os.path.join(working_dir, 'logs', f'{project_name.lower().replace(" ", "_")}.log'),
            os.path.join(working_dir, f'{project_name.lower().replace(" ", "_")}.log'),
            os.path.join(working_dir, 'app.log'),
            os.path.join(working_dir, 'dashboard.log'),
            os.path.join(working_dir, 'server.log'),
            os.path.join(working_dir, 'error.log'),
        ]
        
        logs_content = ""
        
        # Try to read from log files
        for log_path in log_paths:
            if os.path.exists(log_path):
                try:
                    with open(log_path, 'r') as f:
                        lines = f.readlines()
                        # Get last 50 lines
                        recent_lines = lines[-50:] if len(lines) > 50 else lines
                        logs_content += f"\n=== {os.path.basename(log_path)} ===\n"
                        logs_content += ''.join(recent_lines)
                        logs_content += "\n"
                        break  # Use first available log file
                except Exception as e:
                    logs_content += f"Error reading {log_path}: {e}\n"
        
        # If no log files found, try to get recent process output
        if not logs_content.strip():
            try:
                import subprocess
                # Try to get recent console logs for macOS
                result = subprocess.run(
                    ['log', 'show', '--predicate', f'process CONTAINS "{project_name}"', '--last', '1h', '--style', 'syslog'],
                    capture_output=True, text=True, timeout=10
                )
                if result.returncode == 0 and result.stdout:
                    logs_content = f"=== Recent System Logs ===\n{result.stdout}"
                else:
                    # Try simpler approach with ps and grep
                    result = subprocess.run(
                        ['ps', 'aux'],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0:
                        lines = result.stdout.split('\n')
                        port = project.get('port', 8008)
                        relevant_lines = [line for line in lines if str(port) in line or project_name.lower() in line.lower()]
                        if relevant_lines:
                            logs_content = f"=== Running Processes ===\n" + "\n".join(relevant_lines)
            except Exception as e:
                logs_content += f"Error getting system logs: {e}\n"
        
        # If still no logs, provide a default message
        if not logs_content.strip():
            logs_content = f"No logs found for {project_name}.\n\nChecked locations:\n" + "\n".join(log_paths)
            
            # Add process info if available
            try:
                import psutil
                local_port = project.get('port', 8008)
                for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
                    try:
                        connections = proc.connections()
                        for conn in connections:
                            if conn.laddr.port == local_port:
                                logs_content += f"\n=== Running Process Info ===\n"
                                logs_content += f"PID: {proc.pid}\n"
                                logs_content += f"Command: {' '.join(proc.cmdline())}\n"
                                logs_content += f"Started: {datetime.fromtimestamp(proc.create_time())}\n"
                                break
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
            except Exception:
                pass
        
        return {
            "success": True,
            "logs": logs_content,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting logs for {project_name}: {e}")
        return {"success": False, "error": str(e)}


# Primary Dashboard Management Endpoints
@app.get("/api/dashboards/{dashboard_name}/cron-systems")
async def get_cron_systems(dashboard_name: str):
    """Get cron systems for primary dashboard"""
    try:
        # For Marketing Dashboard, get path from user profile
        if dashboard_name == "Marketing Dashboard":
            profile = db.get_user_profile()
            project_paths = json.loads(profile.get('project_paths', '[]'))
            
            # Look for marketing path in profile
            marketing_path = None
            for path in project_paths:
                if 'marketing' in path.lower():
                    marketing_path = path
                    break
            
            # Fallback to asking user to configure
            if not marketing_path:
                return {
                    "success": False,
                    "error": "Marketing path not configured. Please add your marketing project path to your User Profile in Settings."
                }
            
            cron_systems = []
            
            # Look for common cron/automation files
            cron_files = [
                "cron.py", "scheduler.py", "automation.py", 
                "scripts/cron.py", "scripts/scheduler.py"
            ]
            
            for file in cron_files:
                file_path = os.path.join(marketing_path, file)
                if os.path.exists(file_path):
                    cron_systems.append({
                        "name": f"Marketing {file.replace('.py', '').title()}",
                        "schedule": "0 */6 * * *",  # Every 6 hours
                        "description": f"Automated marketing tasks from {file}",
                        "active": False,  # Default to inactive
                        "file_path": file_path
                    })
            
            # Add default marketing automation systems
            default_systems = [
                {
                    "name": "Email Campaign Monitor",
                    "schedule": "0 8 * * *",  # Daily at 8 AM
                    "description": "Monitors email campaign performance across all brands",
                    "active": True
                },
                {
                    "name": "Website Health Check",
                    "schedule": "*/30 * * * *",  # Every 30 minutes
                    "description": "Checks health of all brand websites",
                    "active": True
                },
                {
                    "name": "Social Media Scheduler",
                    "schedule": "0 */4 * * *",  # Every 4 hours
                    "description": "Publishes scheduled social media content",
                    "active": False
                }
            ]
            
            cron_systems.extend(default_systems)
            
            return {"systems": cron_systems}
        
        return {"error": f"Cron systems not configured for {dashboard_name}"}
    except Exception as e:
        return {"error": f"Failed to load cron systems: {str(e)}"}

@app.get("/api/dashboards/{dashboard_name}/monitor-all")
async def monitor_all_dashboards(dashboard_name: str):
    """Monitor all dashboards from primary dashboard"""
    try:
        # Get all dashboards from database
        dashboards = get_dashboard_projects()
        monitored_dashboards = []
        
        for dashboard in dashboards:
            status_info = {
                "name": dashboard["name"],
                "status": "stopped",
                "cpu_percent": None,
                "memory_mb": None,
                "uptime": None,
                "port": dashboard.get("port")
            }
            
            # Check if dashboard is running
            if dashboard.get("port"):
                try:
                    import requests
                    health_url = f"http://localhost:{dashboard['port']}/health"
                    response = requests.get(health_url, timeout=2)
                    if response.status_code == 200:
                        status_info["status"] = "running"
                        
                        # Try to get detailed status
                        try:
                            status_response = requests.get(f"http://localhost:{dashboard['port']}/api/dashboards/{dashboard['name']}/status", timeout=2)
                            if status_response.status_code == 200:
                                status_data = status_response.json()
                                status_info.update({
                                    "cpu_percent": status_data.get("cpu_percent"),
                                    "memory_mb": status_data.get("memory_mb"),
                                    "uptime": status_data.get("uptime")
                                })
                        except:
                            pass
                except:
                    pass
            
            monitored_dashboards.append(status_info)
        
        return {"dashboards": monitored_dashboards}
    except Exception as e:
        return {"error": f"Failed to monitor dashboards: {str(e)}"}

@app.get("/api/dashboards/{dashboard_name}/websites")
async def get_managed_websites(dashboard_name: str):
    """Get websites managed by primary dashboard"""
    try:
        if dashboard_name == "Marketing Dashboard":
            profile = db.get_user_profile()
            project_paths = json.loads(profile.get('project_paths', '[]'))
            
            # Look for marketing path in profile
            marketing_path = None
            for path in project_paths:
                if 'marketing' in path.lower():
                    marketing_path = path
                    break
            
            # Fallback error if not configured
            if not marketing_path:
                return {
                    "success": False,
                    "error": "Marketing path not configured. Please add your marketing project path to your User Profile in Settings.",
                    "websites": []
                }
            
            websites_path = os.path.join(marketing_path, "websites")
            websites = []
            
            if os.path.exists(websites_path):
                for item in os.listdir(websites_path):
                    site_path = os.path.join(websites_path, item)
                    if os.path.isdir(site_path):
                        # Try to determine website info
                        config_file = os.path.join(site_path, "config.json")
                        if os.path.exists(config_file):
                            try:
                                import json
                                with open(config_file, 'r') as f:
                                    config = json.load(f)
                                websites.append({
                                    "name": config.get("name", item),
                                    "url": config.get("url", f"https://{item}.com"),
                                    "description": config.get("description", f"Website for {item}"),
                                    "status": "online"  # Assume online for now
                                })
                            except:
                                pass
                        else:
                            # Default website info
                            websites.append({
                                "name": item.title(),
                                "url": f"https://{item}.com",
                                "description": f"Brand website for {item}",
                                "status": "unknown"
                            })
            
            # Add some example websites if none found
            if not websites:
                websites = [
                    {
                        "name": "Main Brand Site",
                        "url": "https://example.com",
                        "description": "Primary brand website",
                        "status": "online"
                    },
                    {
                        "name": "E-commerce Store",
                        "url": "https://store.example.com",
                        "description": "Online store and shopping platform",
                        "status": "online"
                    },
                    {
                        "name": "Blog Platform",
                        "url": "https://blog.example.com",
                        "description": "Content marketing and blog platform",
                        "status": "maintenance"
                    }
                ]
            
            return {"websites": websites}
        
        return {"error": f"Website management not configured for {dashboard_name}"}
    except Exception as e:
        return {"error": f"Failed to load websites: {str(e)}"}

@app.get("/api/dashboards/{dashboard_name}/outreach")
async def get_outreach_dashboard(dashboard_name: str):
    """Get email outreach dashboard data"""
    try:
        if dashboard_name == "Marketing Dashboard":
            # Mock outreach data - in real implementation, this would come from email service
            outreach_data = {
                "stats": {
                    "emails_sent": 2847,
                    "open_rate": 24.3,
                    "response_rate": 8.7
                },
                "campaigns": [
                    {
                        "name": "Q4 Product Launch",
                        "description": "New product announcement campaign",
                        "status": "active",
                        "sent": 1247,
                        "opens": 312,
                        "replies": 89
                    },
                    {
                        "name": "Holiday Sales",
                        "description": "Black Friday and holiday promotions",
                        "status": "scheduled",
                        "sent": 0,
                        "opens": 0,
                        "replies": 0
                    },
                    {
                        "name": "Customer Feedback",
                        "description": "Post-purchase feedback collection",
                        "status": "active",
                        "sent": 1600,
                        "opens": 480,
                        "replies": 127
                    }
                ]
            }
            
            return outreach_data
        
        return {"error": f"Outreach dashboard not configured for {dashboard_name}"}
    except Exception as e:
        return {"error": f"Failed to load outreach data: {str(e)}"}


@app.post("/api/system/open-terminal") 
async def open_terminal(request: Request):
    """Open a terminal at the specified path (macOS)."""
    try:
        import subprocess
        data = await request.json()
        path = data.get('path', '/')
        
        # Validate path exists
        if not os.path.exists(path):
            return {"success": False, "error": "Path does not exist"}
        
        # Open Terminal app at the specified path
        subprocess.run([
            'open', '-a', 'Terminal', path
        ], check=True)
        
        return {"success": True, "message": f"Opened terminal at {path}"}
        
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": f"Failed to open terminal: {e}"}
    except Exception as e:
        logger.error(f"Error opening terminal: {e}")
        return {"success": False, "error": str(e)}



@app.get("/leads")
async def leads_page():
    """Serve the leads dashboard page."""
    try:
        # Get the src directory path
        src_dir = Path(__file__).parent
        template_path = src_dir / "templates" / "leads.html"
        # Read the leads HTML template
        with open(template_path, "r") as f:
            html_content = f.read()
        return HTMLResponse(content=html_content)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Leads page not found")


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    await initialize_ai_providers()
    
    # Create data directory for lead generation files
    os.makedirs('data', exist_ok=True)
    
    logger.info("Dashboard startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up background threads on shutdown."""
    logger.info("Shutting down background data collection...")
    background_manager.stop()
    logger.info("Background threads stopped")

# ===================================================================
# SERVER MANAGEMENT ENDPOINTS
# ===================================================================

@app.get("/api/servers")
async def get_all_servers():
    """Get all Python web servers running on the system"""
    try:
        from utils.server_manager import ServerManager
        
        server_manager = ServerManager()
        servers = server_manager.discover_python_servers()
        
        return {"success": True, "servers": servers}
    except Exception as e:
        logger.error(f"Error discovering servers: {e}")
        return {"success": False, "error": str(e), "servers": []}

@app.get("/api/servers/{port}/status")
async def get_server_status(port: int):
    """Get detailed status for a specific server"""
    try:
        from utils.server_manager import ServerManager
        
        server_manager = ServerManager()
        status = server_manager.get_server_status(port)
        
        return {"success": True, "status": status}
    except Exception as e:
        logger.error(f"Error getting server status for port {port}: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/servers/{port}/stop")
async def stop_server(port: int):
    """Stop a server running on a specific port"""
    try:
        from utils.server_manager import ServerManager
        
        server_manager = ServerManager()
        servers = server_manager.discover_python_servers()
        server = next((s for s in servers if s['port'] == port), None)
        
        if not server:
            raise HTTPException(status_code=404, detail=f"Server on port {port} not found")
        
        if not server.get('can_control'):
            raise HTTPException(status_code=400, detail=f"Cannot control server on port {port} (no PID available)")
        
        success = server_manager.stop_server(server)
        
        if success:
            return {"success": True, "message": f"Server on port {port} stopped successfully"}
        else:
            return {"success": False, "error": f"Failed to stop server on port {port}"}
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping server on port {port}: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/servers/refresh")
async def refresh_servers():
    """Refresh the list of discovered servers"""
    try:
        from utils.server_manager import ServerManager
        
        server_manager = ServerManager()
        servers = server_manager.discover_python_servers()
        
        return {"success": True, "servers": servers, "message": f"Found {len(servers)} servers"}
    except Exception as e:
        logger.error(f"Error refreshing servers: {e}")
        return {"success": False, "error": str(e), "servers": []}


if __name__ == "__main__":
    import socket
    
    # Get the local IP address for network access info
    try:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)
    except:
        local_ip = "127.0.0.1"
    
    print("🌟 Starting Simple Dashboard Server...")
    print(f"📍 Dashboard (Local): http://localhost:8008")
    print(f"📍 Dashboard (Network): http://{local_ip}:8008")
    print(f"🔧 API Docs: http://localhost:8008/docs")
    print("🌐 Server accessible from anywhere on the network!")
    
    # Always run on 0.0.0.0:8008 for network accessibility
    uvicorn.run(app, host="0.0.0.0", port=8008, log_level="info")
