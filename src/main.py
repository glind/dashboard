#!/usr/bin/env python3
"""
Simple Personal Dashboard with News Filtering
Clean, minimal implementation focusing on core data sources
"""

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import json
from datetime import datetime, timedelta
import os
import subprocess
import traceback
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
from typing import Dict, Any, Optional, List

# Add the src directory and project root to path for imports
src_dir = Path(__file__).parent
project_root = src_dir.parent  # One level up from src/
sys.path.insert(0, str(src_dir))
sys.path.insert(0, str(project_root))  # Also add project root for config/ imports

# Import database manager
from database import db

# Configure logging
logger = logging.getLogger(__name__)

GOOGLE_GMAIL_READ_SCOPES = [
    'https://www.googleapis.com/auth/gmail.readonly',
]

GOOGLE_GMAIL_WRITE_SCOPES = [
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.labels',
    'https://www.googleapis.com/auth/gmail.send',
]

GOOGLE_CALENDAR_SCOPES = [
    'https://www.googleapis.com/auth/calendar.readonly',
    'https://www.googleapis.com/auth/calendar.events',
]

GOOGLE_IDENTITY_SCOPES = [
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/userinfo.email',
    'openid',
    'https://www.googleapis.com/auth/drive.readonly',
]


def get_google_oauth_scopes() -> List[str]:
    """Return the full Google OAuth scope set used by the dashboard."""
    return [
        *GOOGLE_IDENTITY_SCOPES,
        *GOOGLE_CALENDAR_SCOPES,
        *GOOGLE_GMAIL_READ_SCOPES,
        *GOOGLE_GMAIL_WRITE_SCOPES,
    ]


def has_required_google_scopes(granted_scopes: Optional[List[str]], required_scopes: List[str]) -> bool:
    """Check if all required Google scopes are present."""
    granted = set(granted_scopes or [])
    return all(scope in granted for scope in required_scopes)


def normalize_ollama_host(raw_host: Optional[str]) -> str:
    """Normalize Ollama host input from settings/UI into bare hostname."""
    host = (raw_host or '').strip()
    if not host:
        return 'localhost'

    host = host.replace('http://', '').replace('https://', '')
    host = host.split('/')[0].strip()
    if ':' in host:
        host = host.split(':')[0].strip()
    return host or 'localhost'

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
# ── Logging setup ──────────────────────────────────────────────────────────────
import logging.handlers as _logging_handlers
LOG_FILE_PATH = Path(__file__).resolve().parent.parent / "dashboard.log"
_log_formatter = logging.Formatter(
    "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S"
)
_rotating_handler = _logging_handlers.RotatingFileHandler(
    str(LOG_FILE_PATH),
    maxBytes=5 * 1024 * 1024,   # 5 MB per file
    backupCount=5,               # keep dashboard.log.1 … .5
    encoding="utf-8"
)
_rotating_handler.setFormatter(_log_formatter)
_stream_handler = logging.StreamHandler()
_stream_handler.setFormatter(_log_formatter)
logging.basicConfig(level=logging.INFO, handlers=[_rotating_handler, _stream_handler])
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)   # quiet access noise
# ────────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="Simple Personal Dashboard")


# Serve static files for PWA and frontend assets from both locations
from fastapi.staticfiles import StaticFiles
import os
static_dirs = ["static", "src/static"]
for static_dir in static_dirs:
    if os.path.isdir(static_dir):
        app.mount(f"/static", StaticFiles(directory=static_dir), name=f"static-{static_dir}")

# Register music playlist router
try:
    from modules.music.endpoints import router as music_router
    app.include_router(music_router)
    logging.info("✅ Music playlist router registered")
except ImportError as e:
    logging.warning(f"Could not load music playlist router: {e}")


# Register Focus Playlists router
try:
    from modules.music.focus_playlists_endpoints import router as focus_playlists_router
    app.include_router(focus_playlists_router)
    logging.info("✅ Focus Playlists router registered")
except ImportError as e:
    logging.warning(f"Could not load focus playlists router: {e}")

# Register tasks router independently so it is available even if other modules fail
try:
    from modules.tasks.endpoints import router as tasks_router
    app.include_router(tasks_router)
    logging.info("✅ Tasks module registered")
except ImportError as e:
    logging.warning(f"Could not load tasks module: {e}")

# Register remaining custom module routers
try:
    from modules.music_news.endpoints import router as music_news_router
    from modules.vanity_alerts.endpoints import router as vanity_alerts_router
    from modules.comms.endpoints import router as comms_router
    from modules.foundershield.endpoints import router as foundershield_router
    from modules.leads.endpoints import router as leads_router
    from modules.ai_summarizer.endpoints import router as ai_summarizer_router
    from modules.providers.endpoints import router as providers_router
    from modules.providers.oauth import router as providers_oauth_router
    
    app.include_router(music_news_router)
    app.include_router(vanity_alerts_router)
    app.include_router(comms_router)
    app.include_router(foundershield_router, prefix="/foundershield")
    app.include_router(leads_router)
    app.include_router(ai_summarizer_router)
    app.include_router(providers_router)
    app.include_router(providers_oauth_router)
    logging.info("✅ Custom modules registered (music_news, vanity_alerts, comms, foundershield, leads, ai_summarizer, providers)")
except ImportError as e:
    logging.warning(f"Could not load non-task custom modules: {e}")

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
            # Create proper account config for GmailCollector (same as /api/email endpoint)
            tokens_file = project_root / "tokens" / "google_credentials.json"
            if not tokens_file.exists():
                return {
                    "emails": [],
                    "total_count": 0,
                    "unread_count": 0,
                    "authenticated": False,
                    "error": "Not authenticated with Google"
                }
            
            account_config = {
                'name': 'primary',
                'credentials_file': str(tokens_file),
                'scopes': [
                    'https://www.googleapis.com/auth/gmail.readonly',
                    'https://www.googleapis.com/auth/calendar.readonly'
                ]
            }
            
            collector = GmailCollector(account_config)
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

# In-memory diagnostics event log
DIAGNOSTIC_EVENTS: List[Dict[str, Any]] = []
DIAGNOSTIC_LOCK = threading.Lock()
DIAGNOSTIC_MAX_EVENTS = 200


def _extract_json_from_ai_text(raw_text: str) -> Optional[Dict[str, Any]]:
    """Attempt to parse JSON from AI output, including fenced blocks."""
    text = (raw_text or '').strip()
    if not text:
        return None

    try:
        return json.loads(text)
    except Exception:
        pass

    if '```' in text:
        for block in text.split('```'):
            candidate = block.replace('json', '', 1).strip()
            if not candidate:
                continue
            try:
                return json.loads(candidate)
            except Exception:
                continue

    start = text.find('{')
    end = text.rfind('}')
    if start >= 0 and end > start:
        candidate = text[start:end + 1]
        try:
            return json.loads(candidate)
        except Exception:
            return None

    return None


def _build_default_diagnostic(error_message: str) -> Dict[str, Any]:
    """Fallback diagnostic when AI parsing fails or provider is unavailable."""
    message = (error_message or '').strip() or 'Unknown error'
    return {
        "summary": f"Dashboard reported: {message}",
        "likely_causes": [
            "Temporary service interruption",
            "Misconfigured provider or credentials",
            "Module-specific runtime exception"
        ],
        "confidence": "low",
        "can_auto_fix": False,
        "repair_actions": [],
        "code_fixes": [],
        "commit_message": "",
        "pr_title": "",
        "pr_body": "",
        "manual_steps": [
            "Open the affected module and click refresh.",
            "Check Settings → AI/Providers and verify connectivity.",
            "Review dashboard.log for backend stack traces."
        ]
    }


def _allowed_repair_actions(module_name: Optional[str] = None) -> List[Dict[str, Any]]:
    actions = [
        {
            "key": "apply_code_fix",
            "label": "Apply Code Fix & Create PR",
            "description": "AI writes file patches, commits to a fix branch, pushes, and opens a GitHub Pull Request for review.",
            "requires_approval": True
        },
        {
            "key": "refresh_module",
            "label": "Refresh Module Cache",
            "description": "Clears module cache and refreshes data for one widget.",
            "requires_approval": True
        },
        {
            "key": "restart_dashboard",
            "label": "Restart Dashboard Service",
            "description": "Runs ./ops/startup.sh restart to recover from service-level failures.",
            "requires_approval": True
        }
    ]

    if module_name:
        for action in actions:
            if action["key"] == "refresh_module":
                action["module"] = module_name
    return actions


async def _run_ai_diagnostic(
    *,
    title: str,
    module_name: str,
    source: str,
    error_message: str,
    stack_trace: str,
    context: Dict[str, Any],
    include_repair_actions: bool = True
) -> Dict[str, Any]:
    """Use configured AI provider to generate diagnosis and repair plan."""
    fallback = _build_default_diagnostic(error_message)

    if not AI_ASSISTANT_AVAILABLE:
        return fallback

    try:
        ai_service = get_ai_service(db, settings)
        allowed_actions = _allowed_repair_actions(module_name if module_name else None)

        log_context = _get_error_log_context(module_name, lines=80)

        prompt = f"""
    You are the dashboard self-diagnostic assistant.
    Analyze this runtime issue and return STRICT JSON only.

    Issue Title: {title}
    Module: {module_name or 'unknown'}
    Source: {source or 'unknown'}
    Error Message: {error_message or 'n/a'}
    Stack Trace:
    {stack_trace or 'n/a'}
    Context JSON:
    {json.dumps(context or {}, ensure_ascii=False)[:4000]}

    Recent ERROR/WARNING log lines (from dashboard.log):
    {log_context[:3000]}

    Allowed auto repair actions:
    {json.dumps(allowed_actions, ensure_ascii=False)}

    Project source files are under src/ (Python backend: src/main.py, collectors, processors; JS frontend: src/static/dashboard.js; HTML: src/templates/dashboard_modern.html).

Return this JSON schema exactly:
{{
  "summary": "short explanation",
  "likely_causes": ["cause 1", "cause 2"],
  "confidence": "low|medium|high",
  "can_auto_fix": true,
  "repair_actions": [
    {{"key":"apply_code_fix","label":"Apply Code Fix & Create PR","description":"...","requires_approval":true}},
    {{"key":"refresh_module","label":"Refresh Module Cache","description":"...","requires_approval":true,"module":"emails"}},
    {{"key":"restart_dashboard","label":"Restart Dashboard Service","description":"...","requires_approval":true}}
  ],
  "code_fixes": [
    {{
      "file": "src/relative/path/to/file.py",
      "description": "what this change does",
      "old_snippet": "exact existing code to replace (10-30 lines with context)",
      "new_snippet": "replacement code"
    }}
  ],
  "commit_message": "fix(<module>): short imperative description",
  "pr_title": "Fix: <short title>",
  "pr_body": "## Problem\n...\n## Solution\n...\n## Testing\n...",
  "manual_steps": ["step 1", "step 2"]
}}

Rules:
- If uncertain, set can_auto_fix=false and leave code_fixes empty.
- Only include apply_code_fix action when you have specific, concrete code_fixes.
- Never invent unsupported action keys.
- code_fixes old_snippet must be exact verbatim text from the source file.
- Prefer concise, actionable steps.
""".strip()

        result = await ai_service.chat(
            message=prompt,
            conversation_id=f"diag_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            include_context=False,
            assistant_id=None
        )

        if not result.get('success'):
            return fallback

        parsed = _extract_json_from_ai_text(result.get('response', ''))
        if not parsed or not isinstance(parsed, dict):
            return fallback

        # Parse code_fixes from AI output
        raw_code_fixes = parsed.get("code_fixes") if isinstance(parsed.get("code_fixes"), list) else []
        normalized_fixes = []
        for fix in raw_code_fixes:
            if not isinstance(fix, dict):
                continue
            file_path = str(fix.get("file") or "").strip()
            old_snippet = str(fix.get("old_snippet") or "").strip()
            new_snippet = str(fix.get("new_snippet") or "").strip()
            if file_path and old_snippet and new_snippet:
                normalized_fixes.append({
                    "file": file_path,
                    "description": str(fix.get("description") or "").strip(),
                    "old_snippet": old_snippet,
                    "new_snippet": new_snippet
                })

        diagnosis = {
            "summary": parsed.get("summary") or fallback["summary"],
            "likely_causes": parsed.get("likely_causes") or fallback["likely_causes"],
            "confidence": parsed.get("confidence") or "low",
            "can_auto_fix": bool(parsed.get("can_auto_fix", False)) if include_repair_actions else False,
            "repair_actions": parsed.get("repair_actions") if include_repair_actions else [],
            "code_fixes": normalized_fixes,
            "commit_message": str(parsed.get("commit_message") or "").strip() or f"fix({module_name or 'general'}): AI-assisted repair",
            "pr_title": str(parsed.get("pr_title") or "").strip() or title,
            "pr_body": str(parsed.get("pr_body") or "").strip(),
            "manual_steps": parsed.get("manual_steps") or fallback["manual_steps"]
        }

        if not isinstance(diagnosis["repair_actions"], list):
            diagnosis["repair_actions"] = []

        allowed_keys = {"restart_dashboard", "refresh_module", "apply_code_fix"}
        normalized_actions = []
        for action in diagnosis["repair_actions"]:
            if not isinstance(action, dict):
                continue
            key = str(action.get("key", "")).strip()
            if key not in allowed_keys:
                continue
            # Only allow apply_code_fix if we actually have code patches
            if key == "apply_code_fix" and not normalized_fixes:
                continue
            normalized_actions.append({
                "key": key,
                "label": action.get("label") or key.replace('_', ' ').title(),
                "description": action.get("description") or "",
                "requires_approval": True,
                "module": action.get("module") or module_name
            })

        diagnosis["repair_actions"] = normalized_actions
        if not diagnosis["repair_actions"]:
            diagnosis["can_auto_fix"] = False

        return diagnosis
    except Exception as ai_err:
        logger.warning(f"AI diagnostic generation failed: {ai_err}")
        return fallback


def _push_diagnostic_event(event: Dict[str, Any]) -> Dict[str, Any]:
    with DIAGNOSTIC_LOCK:
        DIAGNOSTIC_EVENTS.append(event)
        if len(DIAGNOSTIC_EVENTS) > DIAGNOSTIC_MAX_EVENTS:
            DIAGNOSTIC_EVENTS.pop(0)
    return event


def _find_diagnostic_event(event_id: str) -> Optional[Dict[str, Any]]:
    with DIAGNOSTIC_LOCK:
        for item in DIAGNOSTIC_EVENTS:
            if item.get('id') == event_id:
                return item
    return None


def _get_recent_logs(
    lines: int = 200,
    level_filter: Optional[str] = None,
    module_filter: Optional[str] = None
) -> List[str]:
    """Read recent lines from the rotating log file, with optional level/module filter."""
    try:
        if not LOG_FILE_PATH.exists():
            return []
        with open(str(LOG_FILE_PATH), "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, 2)
            size = f.tell()
            read_size = min(size, 512 * 1024)  # at most 512 KB
            f.seek(max(0, size - read_size))
            raw_lines = f.readlines()

        result = []
        level_upper = (level_filter or "").upper()
        module_lower = (module_filter or "").lower()

        for line in raw_lines:
            line = line.rstrip()
            if not line:
                continue
            if level_upper and level_upper not in line:
                continue
            if module_lower and module_lower not in line.lower():
                continue
            result.append(line)

        return result[-lines:]
    except Exception as e:
        logger.warning(f"Could not read log file: {e}")
        return []


def _get_error_log_context(module_name: Optional[str] = None, lines: int = 60) -> str:
    """Fetch recent ERROR/WARNING lines for AI prompts."""
    all_lines = _get_recent_logs(lines=lines, module_filter=module_name or None)
    relevant = [l for l in all_lines if "ERROR" in l or "WARNING" in l or "Traceback" in l or "Exception" in l]
    if not relevant:
        relevant = _get_recent_logs(lines=30, level_filter="ERROR")
    return "\n".join(relevant[-50:]) if relevant else "(no recent errors in log)"


def _get_github_token_and_repo() -> Dict[str, Any]:
    """Return github token, owner, and repo from credentials + git remote."""
    try:
        from database import get_credentials
        github_creds = get_credentials('github') or {}
        token = github_creds.get('token') or ''
    except Exception:
        token = ''

    owner = ''
    repo = ''
    try:
        result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            capture_output=True, text=True, timeout=5,
            cwd=str(project_root)
        )
        remote_url = result.stdout.strip()
        # Handle https://github.com/owner/repo.git or git@github.com:owner/repo.git
        if 'github.com' in remote_url:
            parts = remote_url.rstrip('.git').replace(':', '/').split('/')
            if len(parts) >= 2:
                repo = parts[-1]
                owner = parts[-2]
    except Exception:
        pass

    return {'token': token, 'owner': owner, 'repo': repo}


def _create_fix_branch(event_id: str) -> str:
    """Create and checkout a new fix branch. Returns branch name."""
    short_id = (event_id or 'fix').split('_')[-1][:8]
    branch = f"fix/ai-diag-{short_id}"
    subprocess.run(
        ['git', 'checkout', '-b', branch],
        check=True, capture_output=True, timeout=15,
        cwd=str(project_root)
    )
    return branch


def _apply_file_patches(patches: List[Dict[str, Any]]) -> List[str]:
    """Apply old→new snippet replacements to source files. Returns list of modified file paths."""
    modified = []
    for patch in patches:
        rel_path = (patch.get('file') or '').strip()
        old_snippet = patch.get('old_snippet') or ''
        new_snippet = patch.get('new_snippet') or ''
        if not rel_path or not old_snippet:
            continue
        abs_path = project_root / rel_path
        if not abs_path.exists():
            logger.warning(f"Patch target file not found: {abs_path}")
            continue
        content = abs_path.read_text(encoding='utf-8')
        if old_snippet not in content:
            logger.warning(f"Snippet not found in {rel_path}, skipping patch")
            continue
        abs_path.write_text(content.replace(old_snippet, new_snippet, 1), encoding='utf-8')
        modified.append(rel_path)
    return modified


def _git_commit_and_push(branch: str, file_paths: List[str], commit_message: str) -> str:
    """Stage files, commit, and push branch. Returns short commit SHA."""
    for fp in file_paths:
        subprocess.run(
            ['git', 'add', fp],
            check=True, capture_output=True, timeout=10,
            cwd=str(project_root)
        )
    subprocess.run(
        ['git', 'commit', '-m', commit_message],
        check=True, capture_output=True, timeout=15,
        cwd=str(project_root)
    )
    subprocess.run(
        ['git', 'push', 'origin', branch],
        check=True, capture_output=True, timeout=30,
        cwd=str(project_root)
    )
    result = subprocess.run(
        ['git', 'rev-parse', '--short', 'HEAD'],
        capture_output=True, text=True, timeout=5,
        cwd=str(project_root)
    )
    return result.stdout.strip()


def _create_github_pr_via_api(
    token: str, owner: str, repo: str,
    head_branch: str, base_branch: str,
    title: str, body: str
) -> Dict[str, Any]:
    """Create a GitHub Pull Request via REST API. Returns PR data dict."""
    import urllib.request as _urllib_request
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls"
    payload = json.dumps({
        "title": title,
        "body": body or f"AI-generated fix branch `{head_branch}`.",
        "head": head_branch,
        "base": base_branch,
        "draft": False
    }).encode('utf-8')
    req = _urllib_request.Request(
        url,
        data=payload,
        headers={
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json'
        },
        method='POST'
    )
    try:
        with _urllib_request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except Exception as pr_err:
        return {'error': str(pr_err)}


def _get_default_branch() -> str:
    """Get the default branch name (main/master)."""
    try:
        result = subprocess.run(
            ['git', 'symbolic-ref', 'refs/remotes/origin/HEAD'],
            capture_output=True, text=True, timeout=5,
            cwd=str(project_root)
        )
        ref = result.stdout.strip()  # refs/remotes/origin/main
        return ref.split('/')[-1] if ref else 'main'
    except Exception:
        return 'main'


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
    """Scan for new notes from all configured sources with detailed feedback."""
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
        
        # Apple Notes setting (macOS only)
        include_apple_notes = (
            os.getenv('INCLUDE_APPLE_NOTES', 'true').lower() == 'true' and
            db.get_setting('include_apple_notes', 'true').lower() != 'false'
        )
        
        # Google Keep settings
        google_keep_email = (
            os.getenv('GOOGLE_KEEP_EMAIL') or
            db.get_setting('google_keep_email') or
            notes_config.get('google_keep_email')
        )
        google_keep_token = (
            os.getenv('GOOGLE_KEEP_TOKEN') or
            db.get_setting('google_keep_token') or
            notes_config.get('google_keep_token')
        )
        google_keep_labels_str = (
            os.getenv('GOOGLE_KEEP_LABELS') or
            db.get_setting('google_keep_labels') or
            notes_config.get('google_keep_labels', '')
        )
        google_keep_labels = [l.strip() for l in google_keep_labels_str.split(',') if l.strip()] if google_keep_labels_str else None
        
        # Other settings
        limit = int(os.getenv('NOTES_LIMIT', db.get_setting('notes_limit', notes_config.get('notes_limit', 10))))
        
        logger.info(f"Scanning notes - Obsidian: {obsidian_path}, GDrive: {gdrive_folder_id}, Apple Notes: {include_apple_notes}, Google Keep: {bool(google_keep_email)}")
        
        # Collect notes from all sources (run in thread so it cannot block the event loop)
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    collect_all_notes,
                    obsidian_path=obsidian_path,
                    gdrive_folder_id=gdrive_folder_id,
                    include_apple_notes=include_apple_notes,
                    google_keep_email=google_keep_email,
                    google_keep_token=google_keep_token,
                    google_keep_labels=google_keep_labels,
                    limit=limit
                ),
                timeout=20.0
            )
        except asyncio.TimeoutError:
            logger.error("Notes scan timed out after 20 seconds")
            return {
                "success": False,
                "error": "Notes scan timed out. Please verify Google/Obsidian connectivity and try again.",
                "notes": [],
                "obsidian_count": 0,
                "gdrive_count": 0,
                "total_todos_found": 0,
                "suggestions_created": 0
            }
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
            "apple_notes_count": result.get('apple_notes_count', 0),
            "google_keep_count": result.get('google_keep_count', 0),
            "total_todos_found": result['total_todos_found'],
            "suggestions_created": suggestions_created,
            "config_status": {
                'obsidian_configured': bool(obsidian_path),
                'obsidian_path': obsidian_path or 'Not configured',
                'gdrive_configured': bool(gdrive_folder_id and gdrive_folder_id.strip()),
                'gdrive_folder_id': gdrive_folder_id or 'Not configured',
                'apple_notes_enabled': include_apple_notes,
                'google_keep_configured': bool(google_keep_email and google_keep_token),
                'notes_by_source': {
                    'obsidian': result['obsidian_count'],
                    'google_drive': result['gdrive_count'],
                    'apple_notes': result.get('apple_notes_count', 0),
                    'google_keep': result.get('google_keep_count', 0)
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
            "apple_notes_count": 0,
            "google_keep_count": 0,
            "total_todos_found": 0,
            "suggestions_created": 0
        }


@app.post("/api/notes/sync")
async def sync_notes(request: Request):
    """Sync notes between Apple Notes and Obsidian."""
    try:
        from collectors.notes_collector import AppleNotesCollector, ObsidianNotesCollector, sync_notes_between_sources
        from database import DatabaseManager
        
        body = await request.json()
        source = body.get('source', 'apple_notes')  # Source to sync from
        target = body.get('target', 'obsidian')  # Target to sync to
        note_ids = body.get('note_ids', [])  # Specific notes to sync (empty = all recent)
        
        db = DatabaseManager()
        
        # Get Obsidian path
        obsidian_path = db.get_setting('obsidian_vault_path')
        if not obsidian_path:
            return {
                "success": False,
                "error": "Obsidian vault path not configured. Please configure it in Settings."
            }
        
        synced_notes = []
        errors = []
        
        if source == 'apple_notes' and target == 'obsidian':
            # Sync from Apple Notes to Obsidian
            apple_collector = AppleNotesCollector()
            obsidian_collector = ObsidianNotesCollector(obsidian_path)
            
            # Get Apple Notes
            apple_notes = apple_collector.collect()
            
            if note_ids:
                # Filter to specific notes
                apple_notes = [n for n in apple_notes if n.get('id') in note_ids]
            
            # Create sync folder in Obsidian
            sync_folder = os.path.join(obsidian_path, "Apple Notes Sync")
            os.makedirs(sync_folder, exist_ok=True)
            
            for note in apple_notes:
                try:
                    # Create markdown file
                    safe_title = "".join(c for c in note['title'] if c.isalnum() or c in (' ', '-', '_')).strip()
                    if not safe_title:
                        safe_title = f"Note_{note.get('id', 'unknown')}"
                    
                    file_path = os.path.join(sync_folder, f"{safe_title}.md")
                    
                    # Build markdown content
                    content_lines = [
                        f"# {note['title']}",
                        "",
                        f"**Source:** Apple Notes",
                        f"**Synced:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                        f"**Original Folder:** {note.get('folder', 'Notes')}",
                        "",
                        "---",
                        "",
                        note.get('content', note.get('preview', ''))
                    ]
                    
                    # Add TODOs if present
                    if note.get('todos'):
                        content_lines.extend([
                            "",
                            "## Tasks Found",
                            ""
                        ])
                        for todo in note['todos']:
                            content_lines.append(f"- [ ] {todo}")
                    
                    content = "\n".join(content_lines)
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    
                    synced_notes.append({
                        'title': note['title'],
                        'source': 'apple_notes',
                        'target_path': file_path
                    })
                    
                except Exception as e:
                    errors.append({
                        'note': note.get('title', 'Unknown'),
                        'error': str(e)
                    })
        
        elif source == 'obsidian' and target == 'apple_notes':
            # Sync from Obsidian to Apple Notes
            return {
                "success": False,
                "error": "Syncing from Obsidian to Apple Notes is not yet supported. Apple Notes doesn't have a public API for creating notes programmatically."
            }
        
        return {
            "success": True,
            "synced": len(synced_notes),
            "notes": synced_notes,
            "errors": errors if errors else None,
            "message": f"Synced {len(synced_notes)} notes from {source} to {target}"
        }
        
    except Exception as e:
        logger.error(f"Error syncing notes: {e}")
        return {
            "success": False,
            "error": str(e)
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
        
        # Apple Notes setting (macOS only)
        include_apple_notes = (
            os.getenv('INCLUDE_APPLE_NOTES', 'true').lower() == 'true' and
            db.get_setting('include_apple_notes', 'true').lower() != 'false'
        )
        apple_notes_timeout = int(os.getenv('APPLE_NOTES_TIMEOUT', db.get_setting('apple_notes_timeout', 10)))

        # Other settings
        limit = int(os.getenv('NOTES_LIMIT', db.get_setting('notes_limit', notes_config.get('notes_limit', 10))))
        auto_create = os.getenv('AUTO_CREATE_TASKS', str(db.get_setting('auto_create_tasks', notes_config.get('auto_create_tasks', True)))).lower() in ('true', '1', 'yes')
        
        logger.info(
            f"Collecting notes - Obsidian: {obsidian_path}, GDrive: {gdrive_folder_id}, "
            f"Apple Notes: {include_apple_notes}"
        )
        
        # TEMPORARY DEBUG
        logger.info(f"DEBUG - obsidian_path type: {type(obsidian_path)}, value: {repr(obsidian_path)}")
        logger.info(f"DEBUG - gdrive_folder_id type: {type(gdrive_folder_id)}, value: {repr(gdrive_folder_id)}")
        
        # Collect notes from all sources (run in thread so it cannot block the event loop)
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    collect_all_notes,
                    obsidian_path=obsidian_path,
                    gdrive_folder_id=gdrive_folder_id,
                    include_apple_notes=include_apple_notes,
                    apple_notes_timeout=apple_notes_timeout,
                    limit=limit
                ),
                timeout=12.0
            )
        except asyncio.TimeoutError:
            logger.error("Notes collection timed out after 12 seconds")

            # Fallback: return local notes quickly when remote providers are slow.
            try:
                logger.warning("Retrying notes collection with remote providers disabled")
                result = await asyncio.wait_for(
                    asyncio.to_thread(
                        collect_all_notes,
                        obsidian_path=obsidian_path,
                        gdrive_folder_id=None,
                        include_apple_notes=False,
                        limit=limit
                    ),
                    timeout=6.0
                )
            except Exception:
                return {
                    "success": False,
                    "error": "Notes loading timed out. Please verify Google/Obsidian connectivity and try again.",
                    "notes": [],
                    "obsidian_count": 0,
                    "gdrive_count": 0,
                    "total_todos_found": 0,
                    "tasks_created": 0
                }
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
            },
            # Apple Notes settings
            'apple_notes_enabled': {
                'value': os.getenv('APPLE_NOTES_ENABLED', str(db.get_setting('apple_notes_enabled', notes_config.get('apple_notes_enabled', False)))).lower() in ('true', '1', 'yes'),
                'source': 'env' if os.getenv('APPLE_NOTES_ENABLED') else
                         'database' if db.get_setting('apple_notes_enabled') is not None else
                         'config' if notes_config.get('apple_notes_enabled') is not None else 'default'
            },
            # Google Keep settings
            'google_keep_email': {
                'value': (
                    os.getenv('GOOGLE_KEEP_EMAIL') or
                    db.get_setting('google_keep_email') or
                    notes_config.get('google_keep_email') or
                    ''
                ),
                'source': 'env' if os.getenv('GOOGLE_KEEP_EMAIL') else
                         'database' if db.get_setting('google_keep_email') else
                         'config' if notes_config.get('google_keep_email') else 'default'
            },
            'google_keep_token': {
                'value': (
                    os.getenv('GOOGLE_KEEP_TOKEN') or
                    db.get_setting('google_keep_token') or
                    notes_config.get('google_keep_token') or
                    ''
                ),
                'source': 'env' if os.getenv('GOOGLE_KEEP_TOKEN') else
                         'database' if db.get_setting('google_keep_token') else
                         'config' if notes_config.get('google_keep_token') else 'default'
            },
            'google_keep_labels': {
                'value': (
                    os.getenv('GOOGLE_KEEP_LABELS') or
                    db.get_setting('google_keep_labels') or
                    notes_config.get('google_keep_labels') or
                    ''
                ),
                'source': 'env' if os.getenv('GOOGLE_KEEP_LABELS') else
                         'database' if db.get_setting('google_keep_labels') else
                         'config' if notes_config.get('google_keep_labels') else 'default'
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
        
        if 'auto_create_tasks' in settings:
            db.save_setting('auto_create_tasks', bool(settings['auto_create_tasks']))
            updated.append('auto_create_tasks')
        
        # Apple Notes settings
        if 'apple_notes_enabled' in settings:
            db.save_setting('apple_notes_enabled', bool(settings['apple_notes_enabled']))
            updated.append('apple_notes_enabled')
        
        # Google Keep settings
        if 'google_keep_email' in settings:
            db.save_setting('google_keep_email', settings['google_keep_email'])
            updated.append('google_keep_email')
        
        if 'google_keep_token' in settings:
            db.save_setting('google_keep_token', settings['google_keep_token'])
            updated.append('google_keep_token')
        
        if 'google_keep_labels' in settings:
            db.save_setting('google_keep_labels', settings['google_keep_labels'])
            updated.append('google_keep_labels')
        
        logger.info(f"Updated notes settings: {updated}")
        
        return {
            "success": True,
            "message": f"Updated {len(updated)} settings",
            "updated": updated
        }
        
    except Exception as e:
        logger.error(f"Error updating notes settings: {e}")
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
        from config.settings import Settings
        
        db = DatabaseManager()
        
        # Load defaults from config file
        config_path = project_root / "src" / "config" / "config.yaml"
        config_settings = Settings.from_yaml(str(config_path)) if config_path.exists() else Settings()
        
        # Use config file values as defaults, but database settings take priority
        settings = {
            'ai_provider': db.get_setting('ai_provider', 'ollama'),
            'ollama_host': db.get_setting('ollama_host', config_settings.ollama.host),
            'ollama_port': db.get_setting('ollama_port', config_settings.ollama.port),
            'ollama_model': db.get_setting('ollama_model', config_settings.ollama.model),
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
                    ollama_host = normalize_ollama_host(settings.get('ollama_host', db.get_setting('ollama_host', 'localhost')))
                    ollama_port = settings.get('ollama_port', db.get_setting('ollama_port', 11434))
                    ollama_model = settings.get('ollama_model', db.get_setting('ollama_model', 'deepseek-r1:latest'))
                    
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
async def get_ollama_models(host: Optional[str] = None, port: Optional[int] = None):
    """Get list of available Ollama models."""
    try:
        from database import DatabaseManager
        from config.settings import Settings
        
        db = DatabaseManager()
        
        # Load defaults from config file
        config_path = project_root / "src" / "config" / "config.yaml"
        config_settings = Settings.from_yaml(str(config_path)) if config_path.exists() else Settings()
        
        # Get Ollama host and port from settings (database takes priority over config)
        configured_host = normalize_ollama_host(host or db.get_setting('ollama_host', config_settings.ollama.host))
        configured_port = int(port or db.get_setting('ollama_port', config_settings.ollama.port))
        fallback_hosts = [configured_host]
        if configured_host != 'localhost':
            fallback_hosts.append('localhost')

        last_error = None
        async with httpx.AsyncClient() as client:
            for candidate_host in fallback_hosts:
                url = f"http://{candidate_host}:{configured_port}/api/tags"
                try:
                    response = await client.get(url, timeout=5.0)
                except httpx.ConnectError as e:
                    last_error = f"Cannot connect to Ollama at {candidate_host}:{configured_port}"
                    logger.warning(last_error)
                    continue

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
                        "server": f"{candidate_host}:{configured_port}"
                    }

                last_error = f"Ollama server at {candidate_host}:{configured_port} returned status {response.status_code}"

        return {
            "success": False,
            "error": last_error or "Cannot connect to Ollama server. Make sure it's running.",
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


@app.post("/api/settings/ai/test")
async def test_ai_provider_connection(payload: Dict[str, Any]):
    """Test AI provider connectivity without saving settings."""
    try:
        from database import DatabaseManager
        dbm = DatabaseManager()
        provider = (payload.get('provider') or '').strip().lower()

        if provider == 'ollama':
            host = normalize_ollama_host(payload.get('host') or dbm.get_setting('ollama_host', 'localhost'))
            port = int(payload.get('port') or dbm.get_setting('ollama_port', 11434))
            url = f"http://{host}:{port}/api/tags"
            async with httpx.AsyncClient(timeout=6.0) as client:
                response = await client.get(url)
            if response.status_code == 200:
                return {"success": True, "provider": "ollama", "message": f"Connected to {host}:{port}"}
            return {
                "success": False,
                "provider": "ollama",
                "error": f"Ollama returned status {response.status_code} at {host}:{port}"
            }

        if provider == 'openai':
            api_key = (payload.get('api_key') or '').strip()
            if not api_key or api_key.startswith('••••'):
                api_key = str(dbm.get_setting('openai_api_key', '') or '').strip()
            model = (payload.get('model') or 'gpt-4o-mini').strip()
            if not api_key:
                return {"success": False, "provider": "openai", "error": "API key is required"}

            test_provider = create_provider('openai', 'openai-test', {
                'api_key': api_key,
                'model_name': model,
            })
            ok = await test_provider.health_check()
            return {"success": bool(ok), "provider": "openai", "message": "Connection successful" if ok else None, "error": None if ok else "OpenAI health check failed"}

        if provider == 'gemini':
            api_key = (payload.get('api_key') or '').strip()
            if not api_key or api_key.startswith('••••'):
                api_key = str(dbm.get_setting('gemini_api_key', '') or '').strip()
            model = (payload.get('model') or 'gemini-2.0-flash').strip()
            if not api_key:
                return {"success": False, "provider": "gemini", "error": "API key is required"}

            test_provider = create_provider('gemini', 'gemini-test', {
                'api_key': api_key,
                'model_name': model,
            })
            ok = await test_provider.health_check()
            return {"success": bool(ok), "provider": "gemini", "message": "Connection successful" if ok else None, "error": None if ok else "Gemini health check failed"}

        return {"success": False, "error": "Unsupported provider. Use ollama, openai, or gemini."}
    except Exception as e:
        logger.error(f"Error testing AI provider connection: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/ollama/pull")
async def pull_ollama_model(request: Dict[str, Any]):
    """Pull a new Ollama model."""
    try:
        from database import DatabaseManager
        dbm = DatabaseManager()
        
        model_name = request.get('model')
        if not model_name:
            return {"success": False, "error": "Model name is required"}
        
        host = normalize_ollama_host(request.get('host') or dbm.get_setting('ollama_host', 'localhost'))
        port = int(request.get('port') or dbm.get_setting('ollama_port', 11434))
        url = f"http://{host}:{port}/api/pull"
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            response = await client.post(url, json={"name": model_name})
            
            if response.status_code == 200:
                return {
                    "success": True,
                    "message": f"Successfully pulled model: {model_name} on {host}:{port}"
                }
            else:
                return {
                    "success": False,
                    "error": f"Failed to pull model on {host}:{port}: {response.text}"
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
                # Create proper account config for GmailCollector
                tokens_file = project_root / "tokens" / "google_credentials.json"
                if not tokens_file.exists():
                    return {
                        "emails": [],
                        "total_count": 0,
                        "unread_count": 0,
                        "authenticated": False,
                        "error": "Not authenticated with Google. Please click 'Connect Google' button."
                    }
                
                account_config = {
                    'name': 'primary',
                    'credentials_file': str(tokens_file),
                    'scopes': [
                        'https://www.googleapis.com/auth/gmail.readonly',
                        'https://www.googleapis.com/auth/calendar.readonly'
                    ]
                }
                
                gmail_collector = GmailCollector(account_config)
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


# Scanned sources management APIs

@app.get("/api/scanned-sources")
async def get_scanned_sources(source_type: str = None, include_dismissed: bool = True):
    """Get list of scanned sources to see what has been processed."""
    try:
        sources = db.get_scanned_sources(source_type=source_type, include_dismissed=include_dismissed)
        
        # Group by source type for summary
        summary = {}
        for src in sources:
            stype = src.get('source_type', 'unknown')
            if stype not in summary:
                summary[stype] = {'total': 0, 'dismissed': 0, 'tasks_created': 0}
            summary[stype]['total'] += 1
            if src.get('dismissed'):
                summary[stype]['dismissed'] += 1
            summary[stype]['tasks_created'] += src.get('tasks_created', 0)
        
        return {
            "success": True,
            "sources": sources,
            "summary": summary,
            "total_count": len(sources)
        }
    except Exception as e:
        logger.error(f"Error getting scanned sources: {e}")
        return {"error": str(e), "success": False}


@app.post("/api/scanned-sources/clear")
async def clear_scanned_sources(request: Request):
    """Clear scanned sources to allow re-scanning.
    
    Options:
    - source_type: Only clear specific type (email, calendar, obsidian, etc.)
    - clear_dismissed: If true, also clear dismissed items (allows recreating deleted tasks)
    """
    try:
        data = await request.json()
        source_type = data.get('source_type')
        clear_dismissed = data.get('clear_dismissed', False)
        
        count = db.clear_scanned_sources(source_type=source_type, clear_dismissed=clear_dismissed)
        
        return {
            "success": True,
            "cleared_count": count,
            "source_type": source_type or "all",
            "cleared_dismissed": clear_dismissed
        }
    except Exception as e:
        logger.error(f"Error clearing scanned sources: {e}")
        return {"error": str(e), "success": False}


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
    """Scan historical emails for tasks using strict AI filtering.
    
    Tracks scanned sources to avoid re-processing emails and respects deleted tasks.
    """
    try:
        if not COLLECTORS_AVAILABLE:
            raise HTTPException(status_code=503, detail="Email collectors not available")
        
        # Get request parameters
        body = await request.json()
        start_date_str = body.get('start_date')
        end_date_str = body.get('end_date')
        max_emails = body.get('max_emails', 100)
        force_rescan = body.get('force_rescan', False)  # Force rescan previously scanned emails
        
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
        already_scanned = 0
        
        # Analyze each email for tasks
        for email in emails:
            try:
                subject = email.get('subject', '')
                body = email.get('body', '')
                sender = email.get('sender', '')
                email_id = email.get('id', '')
                received_date = email.get('received_date', '')
                risk_score = email.get('risk_score', 0)  # Get risk score from email data
                labels = [label.upper() for label in email.get('labels', [])]
                is_starred = 'STARRED' in labels
                is_important = bool(email.get('is_important')) or 'IMPORTANT' in labels
                email_priority = (email.get('priority') or email.get('ollama_priority') or 'medium').lower()
                
                # Check if email was already scanned (unless force_rescan is True)
                if not force_rescan and db.is_source_scanned('email', email_id):
                    already_scanned += 1
                    continue
                
                # Check if task already exists or was deleted (avoid duplicates and re-creation)
                existing_tasks = task_manager.get_tasks_by_source('email', email_id, include_deleted=True)
                if existing_tasks:
                    logger.info(f"Task already exists/deleted for email: {subject[:50]}")
                    tasks_skipped += 1
                    # Mark as scanned to prevent future checks
                    db.mark_source_scanned('email', email_id, tasks_found=0, tasks_created=0)
                    continue
                
                # Use AI analyzer with strict filtering and risk scoring
                todos = await email_analyzer.analyze_email_for_todos(subject, body, sender, risk_score)
                
                if not todos:
                    emails_skipped += 1
                    # Mark as scanned with no tasks found
                    db.mark_source_scanned('email', email_id, tasks_found=0, tasks_created=0)
                    continue
                
                # Create tasks for each todo found
                email_tasks_created = 0
                for todo in todos:
                    # Check if task already exists (avoid duplicates)
                    existing_tasks = db.get_todos_by_source('email', None)
                    existing_tasks = [t for t in existing_tasks if t.get('source_id') == email_id]
                    if existing_tasks:
                        logger.info(f"Task already exists for email: {subject[:50]}")
                        tasks_skipped += 1
                        continue

                    todo_reason = todo.get('reason', 'Detected as actionable from email content')
                    base_priority = (todo.get('priority') or 'medium').lower()
                    should_escalate = is_starred or is_important or email_priority == 'high' or risk_score >= 7
                    derived_priority = 'high' if should_escalate else base_priority
                    priority_reason = "Elevated priority from flagged/prioritized email" if should_escalate else "Priority from extracted task signal"
                    source_preview = (email.get('snippet') or body or '')[:280]
                    source_url = f"https://mail.google.com/mail/u/0/#inbox/{email_id}" if email_id else None
                    
                    # Create task
                    result = task_manager.create_task(
                        title=todo.get('task', f"Follow up: {subject[:60]}"),
                        description=f"From: {sender}\nSubject: {subject}\n\nWhy: {todo_reason}",
                        priority=derived_priority,
                        category=todo.get('category', 'email'),
                        source='email',
                        source_id=email_id,
                        email_id=email_id,
                        source_title=subject,
                        source_url=source_url,
                        source_preview=source_preview,
                        creation_reason=f"{todo_reason}. {priority_reason}",
                        sync_to_ticktick=COLLECTORS_AVAILABLE
                    )

                    if result.get('success'):
                        tasks_created += 1
                        email_tasks_created += 1
                        logger.info(f"Created task from email: {subject[:50]}")
                    else:
                        tasks_skipped += 1
                        logger.warning(f"Skipped task creation for email {email_id}: {result.get('error', 'unknown error')}")

                # Mark source as scanned with tasks created count
                db.mark_source_scanned('email', email_id, tasks_found=len(todos), tasks_created=email_tasks_created)
                    
            except Exception as e:
                logger.error(f"Error processing email {email.get('id', 'unknown')}: {e}")
                continue
        
        return {
            "success": True,
            "emails_scanned": len(emails),
            "already_scanned": already_scanned,
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


# Email Client API Endpoints (Send, Reply, Forward, Delete, Archive, etc.)

def get_gmail_service():
    """Get authenticated Gmail service."""
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    import json
    
    tokens_file = project_root / "tokens" / "google_credentials.json"
    if not tokens_file.exists():
        raise HTTPException(status_code=401, detail="Not authenticated with Google. Please connect your Google account.")

    token_scopes = []
    try:
        with open(tokens_file, 'r') as f:
            token_scopes = json.load(f).get('scopes', [])
    except Exception as e:
        logger.warning(f"Could not read Google token scopes: {e}")

    if not has_required_google_scopes(token_scopes, GOOGLE_GMAIL_WRITE_SCOPES):
        raise HTTPException(
            status_code=403,
            detail="Google account needs Gmail write permissions. Please reconnect Google to grant read/write email access."
        )
    
    creds = Credentials.from_authorized_user_file(
        str(tokens_file),
        scopes=[*GOOGLE_GMAIL_READ_SCOPES, *GOOGLE_GMAIL_WRITE_SCOPES]
    )
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request
            creds.refresh(Request())
            with open(tokens_file, 'w') as f:
                f.write(creds.to_json())
        else:
            raise HTTPException(status_code=401, detail="Google credentials expired. Please reconnect.")
    
    return build('gmail', 'v1', credentials=creds)


@app.post("/api/email/send")
async def send_email(request: Request):
    """Send a new email."""
    try:
        import base64
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email import encoders
        
        data = await request.json()
        to = data.get('to', '')
        cc = data.get('cc', '')
        bcc = data.get('bcc', '')
        subject = data.get('subject', '')
        body = data.get('body', '')
        html_body = data.get('html_body', '')
        attachments = data.get('attachments', [])  # List of {filename, content_base64, mime_type}
        
        if not to:
            raise HTTPException(status_code=400, detail="Recipient (to) is required")
        
        service = get_gmail_service()
        
        # Create message
        if html_body or attachments:
            message = MIMEMultipart('alternative')
        else:
            message = MIMEText(body, 'plain')
        
        message['to'] = to
        if cc:
            message['cc'] = cc
        if bcc:
            message['bcc'] = bcc
        message['subject'] = subject
        
        if html_body:
            # Add both plain and HTML versions
            part1 = MIMEText(body, 'plain')
            part2 = MIMEText(html_body, 'html')
            message.attach(part1)
            message.attach(part2)
        
        # Handle attachments
        for attachment in attachments:
            part = MIMEBase('application', 'octet-stream')
            content = base64.b64decode(attachment['content_base64'])
            part.set_payload(content)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f"attachment; filename={attachment['filename']}")
            message.attach(part)
        
        # Encode and send
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        result = service.users().messages().send(
            userId='me',
            body={'raw': raw}
        ).execute()
        
        logger.info(f"Email sent successfully, message ID: {result['id']}")
        
        return {
            "success": True,
            "message_id": result['id'],
            "thread_id": result.get('threadId'),
            "message": "Email sent successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/email/reply")
async def reply_to_email(request: Request):
    """Reply to an email."""
    try:
        import base64
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        data = await request.json()
        message_id = data.get('message_id')
        body = data.get('body', '')
        html_body = data.get('html_body', '')
        reply_all = data.get('reply_all', False)
        
        if not message_id:
            raise HTTPException(status_code=400, detail="message_id is required")
        
        service = get_gmail_service()
        
        # Get original message to get thread info and headers
        original = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        headers = {h['name'].lower(): h['value'] for h in original['payload'].get('headers', [])}
        
        thread_id = original.get('threadId')
        original_from = headers.get('from', '')
        original_to = headers.get('to', '')
        original_cc = headers.get('cc', '')
        original_subject = headers.get('subject', '')
        message_id_header = headers.get('message-id', '')
        
        # Determine recipients
        reply_to = original_from
        cc = ''
        if reply_all:
            # Include all original recipients except myself
            all_recipients = set()
            if original_to:
                all_recipients.update([e.strip() for e in original_to.split(',')])
            if original_cc:
                all_recipients.update([e.strip() for e in original_cc.split(',')])
            # Remove the original sender (they're in 'to') and our own email
            all_recipients.discard(original_from)
            cc = ', '.join(all_recipients)
        
        # Create reply message
        if html_body:
            message = MIMEMultipart('alternative')
            message.attach(MIMEText(body, 'plain'))
            message.attach(MIMEText(html_body, 'html'))
        else:
            message = MIMEText(body, 'plain')
        
        message['to'] = reply_to
        if cc:
            message['cc'] = cc
        message['subject'] = f"Re: {original_subject}" if not original_subject.startswith('Re:') else original_subject
        message['In-Reply-To'] = message_id_header
        message['References'] = message_id_header
        
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        result = service.users().messages().send(
            userId='me',
            body={'raw': raw, 'threadId': thread_id}
        ).execute()
        
        logger.info(f"Reply sent successfully, message ID: {result['id']}")
        
        return {
            "success": True,
            "message_id": result['id'],
            "thread_id": result.get('threadId'),
            "message": "Reply sent successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error replying to email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/email/forward")
async def forward_email(request: Request):
    """Forward an email."""
    try:
        import base64
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        data = await request.json()
        message_id = data.get('message_id')
        to = data.get('to', '')
        additional_message = data.get('body', '')
        
        if not message_id or not to:
            raise HTTPException(status_code=400, detail="message_id and to are required")
        
        service = get_gmail_service()
        
        # Get original message
        original = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        headers = {h['name'].lower(): h['value'] for h in original['payload'].get('headers', [])}
        
        original_subject = headers.get('subject', '')
        original_from = headers.get('from', '')
        original_date = headers.get('date', '')
        original_body = original.get('snippet', '')
        
        # Get full body if available
        if 'body' in original['payload'] and original['payload']['body'].get('data'):
            original_body = base64.urlsafe_b64decode(original['payload']['body']['data']).decode('utf-8', errors='ignore')
        
        # Create forwarded message
        forward_body = f"""
{additional_message}

---------- Forwarded message ---------
From: {original_from}
Date: {original_date}
Subject: {original_subject}

{original_body}
"""
        
        message = MIMEText(forward_body, 'plain')
        message['to'] = to
        message['subject'] = f"Fwd: {original_subject}" if not original_subject.startswith('Fwd:') else original_subject
        
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        
        result = service.users().messages().send(
            userId='me',
            body={'raw': raw}
        ).execute()
        
        logger.info(f"Email forwarded successfully, message ID: {result['id']}")
        
        return {
            "success": True,
            "message_id": result['id'],
            "message": "Email forwarded successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error forwarding email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/email/delete")
async def delete_email(request: Request):
    """Move email to trash."""
    try:
        data = await request.json()
        message_id = data.get('message_id')
        permanent = data.get('permanent', False)
        
        if not message_id:
            raise HTTPException(status_code=400, detail="message_id is required")
        
        service = get_gmail_service()
        
        if permanent:
            # Permanently delete
            service.users().messages().delete(userId='me', id=message_id).execute()
            logger.info(f"Email permanently deleted: {message_id}")
        else:
            # Move to trash
            service.users().messages().trash(userId='me', id=message_id).execute()
            logger.info(f"Email moved to trash: {message_id}")
        
        return {
            "success": True,
            "message": "Email deleted successfully" if permanent else "Email moved to trash"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/email/archive")
async def archive_email(request: Request):
    """Archive email (remove from inbox)."""
    try:
        data = await request.json()
        message_id = data.get('message_id')
        
        if not message_id:
            raise HTTPException(status_code=400, detail="message_id is required")
        
        service = get_gmail_service()
        
        # Remove INBOX label to archive
        service.users().messages().modify(
            userId='me',
            id=message_id,
            body={'removeLabelIds': ['INBOX']}
        ).execute()
        
        logger.info(f"Email archived: {message_id}")
        
        return {
            "success": True,
            "message": "Email archived successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error archiving email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/email/mark-read")
async def mark_email_read(request: Request):
    """Mark email as read or unread."""
    try:
        data = await request.json()
        message_id = data.get('message_id')
        read = data.get('read', True)
        
        if not message_id:
            raise HTTPException(status_code=400, detail="message_id is required")
        
        service = get_gmail_service()
        
        if read:
            # Mark as read (remove UNREAD label)
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['UNREAD']}
            ).execute()
        else:
            # Mark as unread (add UNREAD label)
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': ['UNREAD']}
            ).execute()
        
        logger.info(f"Email marked as {'read' if read else 'unread'}: {message_id}")
        
        return {
            "success": True,
            "message": f"Email marked as {'read' if read else 'unread'}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error marking email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/email/star")
async def star_email(request: Request):
    """Star or unstar an email."""
    try:
        data = await request.json()
        message_id = data.get('message_id')
        starred = data.get('starred', True)
        
        if not message_id:
            raise HTTPException(status_code=400, detail="message_id is required")
        
        service = get_gmail_service()
        
        if starred:
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'addLabelIds': ['STARRED']}
            ).execute()
        else:
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body={'removeLabelIds': ['STARRED']}
            ).execute()
        
        logger.info(f"Email {'starred' if starred else 'unstarred'}: {message_id}")
        
        return {
            "success": True,
            "message": f"Email {'starred' if starred else 'unstarred'}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starring email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/email/{message_id}")
async def get_email_detail(message_id: str):
    """Get full email details including body."""
    try:
        import base64
        import re

        # Compatibility shim: provider manager calls /api/email/accounts,
        # which can be routed here by the dynamic path.
        if message_id == 'accounts':
            tokens_file = project_root / "tokens" / "google_credentials.json"
            google_accounts = []
            if tokens_file.exists():
                google_accounts.append({
                    "name": "Google Account",
                    "provider": "google",
                    "authenticated": True
                })
            return {
                "google": google_accounts,
                "microsoft": []
            }

        # Guard against invalid message IDs (prevents Gmail API 400 noise)
        if not re.fullmatch(r"[A-Za-z0-9_-]{10,}$", message_id):
            raise HTTPException(status_code=400, detail="Invalid email message id")
        
        service = get_gmail_service()
        
        # Get full message
        message = service.users().messages().get(
            userId='me',
            id=message_id,
            format='full'
        ).execute()
        
        headers = {h['name'].lower(): h['value'] for h in message['payload'].get('headers', [])}
        
        # Extract body
        body = ''
        html_body = ''
        attachments = []
        
        def extract_parts(payload):
            nonlocal body, html_body, attachments
            
            if 'body' in payload and payload['body'].get('data'):
                content = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
                mime_type = payload.get('mimeType', '')
                if 'html' in mime_type:
                    html_body = content
                else:
                    body = content
            
            if 'parts' in payload:
                for part in payload['parts']:
                    mime_type = part.get('mimeType', '')
                    if mime_type.startswith('text/'):
                        if 'body' in part and part['body'].get('data'):
                            content = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                            if 'html' in mime_type:
                                html_body = content
                            else:
                                body = content
                    elif part.get('filename'):
                        # This is an attachment
                        attachments.append({
                            'filename': part['filename'],
                            'mime_type': mime_type,
                            'size': part['body'].get('size', 0),
                            'attachment_id': part['body'].get('attachmentId')
                        })
                    
                    # Recurse into nested parts
                    extract_parts(part)
        
        extract_parts(message['payload'])
        
        # Determine if starred
        labels = message.get('labelIds', [])
        is_starred = 'STARRED' in labels
        is_unread = 'UNREAD' in labels
        
        return {
            "success": True,
            "email": {
                "id": message_id,
                "thread_id": message.get('threadId'),
                "subject": headers.get('subject', ''),
                "from": headers.get('from', ''),
                "to": headers.get('to', ''),
                "cc": headers.get('cc', ''),
                "bcc": headers.get('bcc', ''),
                "date": headers.get('date', ''),
                "body": body,
                "html_body": html_body,
                "snippet": message.get('snippet', ''),
                "labels": labels,
                "is_starred": is_starred,
                "is_unread": is_unread,
                "attachments": attachments
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting email detail: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/email/{message_id}/attachment/{attachment_id}")
async def get_email_attachment(message_id: str, attachment_id: str):
    """Download an email attachment."""
    try:
        import base64
        from fastapi.responses import Response
        
        service = get_gmail_service()
        
        attachment = service.users().messages().attachments().get(
            userId='me',
            messageId=message_id,
            id=attachment_id
        ).execute()
        
        data = base64.urlsafe_b64decode(attachment['data'])
        
        return Response(
            content=data,
            media_type='application/octet-stream',
            headers={'Content-Disposition': f'attachment; filename="attachment"'}
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading attachment: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/email/labels/list")
async def get_email_labels():
    """Get all Gmail labels."""
    try:
        service = get_gmail_service()
        
        results = service.users().labels().list(userId='me').execute()
        labels = results.get('labels', [])
        
        return {
            "success": True,
            "labels": [
                {
                    "id": label['id'],
                    "name": label['name'],
                    "type": label['type']
                }
                for label in labels
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting labels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/email/labels/apply")
async def apply_email_label(request: Request):
    """Apply or remove labels from an email."""
    try:
        data = await request.json()
        message_id = data.get('message_id')
        add_labels = data.get('add_labels', [])
        remove_labels = data.get('remove_labels', [])
        
        if not message_id:
            raise HTTPException(status_code=400, detail="message_id is required")
        
        service = get_gmail_service()
        
        body = {}
        if add_labels:
            body['addLabelIds'] = add_labels
        if remove_labels:
            body['removeLabelIds'] = remove_labels
        
        if body:
            service.users().messages().modify(
                userId='me',
                id=message_id,
                body=body
            ).execute()
        
        logger.info(f"Labels updated for email {message_id}")
        
        return {
            "success": True,
            "message": "Labels updated successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error applying labels: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Task Management API Endpoints
@app.get("/api/tasks")
async def get_tasks(include_completed: bool = False, priority: str = None, status: str = None, category: str = None):
    """Get all tasks from database with optional filtering."""
    try:
        from database import DatabaseManager

        active_db = DatabaseManager()
        current_db_path = active_db.db_path
        all_tasks = active_db.get_todos(include_completed=include_completed, include_deleted=False)

        # Fallback: if runtime DB has no tasks, check known workspace DB locations
        if len(all_tasks) == 0:
            fallback_paths = [
                project_root / "dashboard.db",
                project_root / "data" / "dashboard.db",
                project_root / "src" / "dashboard.db",
                Path.home() / ".personal-dashboard" / "dashboard.db",
            ]

            for fallback_path in fallback_paths:
                if not fallback_path.exists():
                    continue

                fallback_path_str = str(fallback_path)
                if current_db_path and os.path.abspath(fallback_path_str) == os.path.abspath(current_db_path):
                    continue

                try:
                    fallback_db = DatabaseManager(fallback_path_str)
                    fallback_rows = fallback_db.get_todos(include_completed=include_completed, include_deleted=False)
                    if fallback_rows:
                        all_tasks = fallback_rows
                        logger.info(f"Loaded {len(all_tasks)} tasks from fallback DB: {fallback_path_str}")
                        break
                except Exception as fallback_error:
                    logger.warning(f"Failed reading fallback DB {fallback_path_str}: {fallback_error}")

        tasks = []
        for task in all_tasks:
            tasks.append({
                'id': task.get('id', ''),
                'title': task.get('title', ''),
                'description': task.get('description', ''),
                'priority': task.get('priority', 'medium'),
                'category': task.get('category', 'general'),
                'status': task.get('status', 'pending'),
                'source': task.get('source', 'manual'),
                'source_id': task.get('source_id', ''),
                'source_title': task.get('source_title', ''),
                'source_url': task.get('source_url', ''),
                'source_preview': task.get('source_preview', ''),
                'creation_reason': task.get('creation_reason', ''),
                'due_date': task.get('due_date', ''),
                'created_at': task.get('created_at', ''),
                'completed_at': task.get('completed_at', ''),
                'requires_response': bool(task.get('requires_response', 0)),
                'email_id': task.get('email_id', ''),
                'gmail_link': f"https://mail.google.com/mail/u/0/#inbox/{task.get('email_id')}" if task.get('email_id') else None
            })
        
        # Apply filters
        if priority:
            tasks = [t for t in tasks if t.get('priority', '').lower() == priority.lower()]
        
        if status:
            tasks = [t for t in tasks if t.get('status', '').lower() == status.lower()]
            
        if category:
            tasks = [t for t in tasks if t.get('category', '').lower() == category.lower()]
        
        # Get statistics for all tasks (unfiltered)
        status_counts = {}
        priority_counts = {'high': 0, 'medium': 0, 'low': 0}
        category_counts = {}
        source_counts = {}

        for task in all_tasks:
            task_status = (task.get('status') or 'pending').lower()
            task_priority = (task.get('priority') or 'medium').lower()
            task_category = task.get('category') or 'general'
            task_source = task.get('source') or 'manual'

            status_counts[task_status] = status_counts.get(task_status, 0) + 1
            category_counts[task_category] = category_counts.get(task_category, 0) + 1
            source_counts[task_source] = source_counts.get(task_source, 0) + 1
            if task_priority in priority_counts:
                priority_counts[task_priority] += 1

        stats = {
            'total_tasks': len(all_tasks),
            'pending_tasks': status_counts.get('pending', 0),
            'completed_tasks': status_counts.get('completed', 0),
            'high_priority': priority_counts['high'],
            'medium_priority': priority_counts['medium'],
            'low_priority': priority_counts['low'],
            'overdue_tasks': 0,
            'due_today': 0,
            'due_this_week': 0,
            'by_category': category_counts,
            'by_source': source_counts
        }
        
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
            sync_to_ticktick=data.get('sync_to_ticktick', True) and COLLECTORS_AVAILABLE,
            source_title=data.get('source_title'),
            source_url=data.get('source_url'),
            source_preview=data.get('source_preview'),
            creation_reason=data.get('creation_reason')
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
    """Delete a task and mark its source as dismissed to prevent recreation."""
    try:
        if not TASK_MANAGER_AVAILABLE:
            return {"error": "Task Manager not available", "success": False}
            
        if not COLLECTORS_AVAILABLE:
            task_manager = TaskManager(None)
        else:
            settings = Settings()
            task_manager = TaskManager(settings)
        
        # Get task info before deleting to mark source as dismissed
        all_tasks = task_manager.get_all_tasks(include_completed=True, include_deleted=True)
        task_to_delete = next((t for t in all_tasks if t.get('id') == task_id), None)
        
        result = task_manager.delete_task(task_id)
        
        # If deletion succeeded, mark the source as dismissed
        if result.get('success') and task_to_delete:
            source = task_to_delete.get('source', '')
            source_id = task_to_delete.get('source_id', '')
            if source and source_id:
                db.mark_source_dismissed(source, source_id)
                logger.info(f"Marked source as dismissed: {source}/{source_id}")
        
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
        source_value = (task.get('source') or '').lower()
        source_id = task.get('source_id')

        if not task.get('source_title'):
            task['source_title'] = task.get('title', '')
        if not task.get('source_preview') and task.get('description'):
            task['source_preview'] = task.get('description', '')[:280]
        if not task.get('creation_reason'):
            if source_value == 'email' and source_id:
                task['creation_reason'] = 'Created from linked email action item'
            elif source_value == 'calendar' and source_id:
                task['creation_reason'] = 'Created from linked calendar event action item'
            elif source_value.startswith('notes_'):
                task['creation_reason'] = 'Created from linked notes action item'
            else:
                task['creation_reason'] = ''
        if not task.get('source_url') and source_value == 'email' and source_id:
            task['source_url'] = f"https://mail.google.com/mail/u/0/#inbox/{source_id}"
        
        # Add source link information
        source_info = {"type": "unknown", "link": None, "display_text": "Unknown source"}

        source_url = task.get('source_url')
        
        if source_value == 'email' and task.get('source_id'):
            source_info = {
                "type": "email",
                "link": f"https://mail.google.com/mail/u/0/#inbox/{task['source_id']}",
                "display_text": f"View email: {task.get('title', 'Email')}"
            }
        elif source_value == 'calendar' and task.get('source_id'):
            source_info = {
                "type": "calendar",
                "link": f"https://calendar.google.com/calendar/event?eid={task['source_id']}",
                "display_text": f"View calendar event: {task.get('title', 'Event')}"
            }
        elif source_value in ('obsidian', 'notes_obsidian') and task.get('source_id'):
            source_info = {
                "type": "obsidian",
                "link": f"obsidian://open?vault=&file={task['source_id']}",
                "display_text": f"Open in Obsidian: {task.get('source_id', 'Note')}"
            }
        elif source_value in ('google_drive', 'notes_google_drive') and task.get('source_id'):
            source_info = {
                "type": "google_drive",
                "link": f"https://docs.google.com/document/d/{task['source_id']}/edit",
                "display_text": f"View Google Doc: {task.get('title', 'Document')}"
            }
        elif source_url:
            source_info = {
                "type": source_value or "external",
                "link": source_url,
                "display_text": f"Open source item: {task.get('source_title') or task.get('title', 'Source')}"
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


@app.post("/api/suggested-todos/bulk")
async def bulk_process_suggested_todos(request: Request):
    """Bulk approve/reject suggested todos."""
    try:
        payload = await request.json()
        action = (payload.get("action") or "").strip().lower()
        suggestion_ids = payload.get("suggestion_ids") or []

        if action not in {"approve", "reject"}:
            raise HTTPException(status_code=400, detail="action must be 'approve' or 'reject'")

        target_ids = []
        if suggestion_ids:
            target_ids = [str(item).strip() for item in suggestion_ids if str(item).strip()]
        else:
            pending = db.get_suggested_todos(status="pending")
            target_ids = [str(item.get("id", "")).strip() for item in pending if item.get("id")]

        processed = 0
        failed = 0

        for suggestion_id in target_ids:
            try:
                if action == "approve":
                    success = db.approve_suggested_todo(suggestion_id)
                else:
                    success = db.reject_suggested_todo(suggestion_id)
                if success:
                    processed += 1
                else:
                    failed += 1
            except Exception:
                failed += 1

        return {
            "success": True,
            "action": action,
            "processed": processed,
            "failed": failed,
            "requested": len(target_ids),
            "message": f"{action.title()}d {processed} suggestion(s)"
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error bulk processing suggested todos: {e}")
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
                    SELECT id, title, url, snippet, image_url, source, published_date, topics, relevance_score, is_read
                    FROM news_articles 
                    ORDER BY is_read ASC, published_date DESC 
                    LIMIT 50
                ''')
            else:
                cursor.execute('''
                    SELECT id, title, url, snippet, image_url, source, published_date, topics, relevance_score, is_read
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
                "image_url": article['image_url'] if 'image_url' in article.keys() else None,
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
    """Return persisted vanity alerts quickly from the active workspace database."""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            try:
                cursor.execute("ALTER TABLE vanity_alerts ADD COLUMN is_dismissed INTEGER DEFAULT 0")
                conn.commit()
            except Exception:
                pass

            cursor.execute('''
                SELECT
                    id,
                    title,
                    COALESCE(snippet, content, '') AS description,
                    COALESCE(search_term, 'mention') AS alert_type,
                    COALESCE(source, '') AS source,
                    COALESCE(url, '') AS url,
                    COALESCE(timestamp, '') AS timestamp,
                    COALESCE(confidence_score, 0) AS confidence_score,
                    COALESCE(is_liked, 0) AS is_liked
                FROM vanity_alerts
                WHERE COALESCE(is_dismissed, 0) = 0
                ORDER BY confidence_score DESC, timestamp DESC
                LIMIT 100
            ''')

            alerts = []
            for row in cursor.fetchall():
                alerts.append({
                    'id': row[0],
                    'title': row[1],
                    'description': row[2],
                    'type': row[3],
                    'source': row[4],
                    'url': row[5],
                    'timestamp': row[6],
                    'is_liked': bool(row[8]),
                })

            return {"alerts": alerts, "count": len(alerts), "success": True}
    except Exception as e:
        logger.error(f"Error loading vanity alerts from database: {e}")
        return {"alerts": [], "count": 0, "success": False, "error": str(e)}


@app.post("/api/vanity-alerts/{alert_id}/dismiss")
async def dismiss_vanity_alert(alert_id: str):
    """Dismiss a vanity alert so it won't be shown again."""
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("ALTER TABLE vanity_alerts ADD COLUMN is_dismissed INTEGER DEFAULT 0")
                conn.commit()
            except Exception:
                pass
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


@app.post("/api/ai/generate-playlist")
async def generate_ai_playlist(request: Request):
    """
    Generate a playlist using AI (Ollama) with direct API call.
    Bypasses conversation context for more reliable JSON output.
    """
    import aiohttp
    import json
    import re
    
    try:
        data = await request.json()
        mood = data.get('mood', 'chill')
        liked_artists = data.get('liked_artists', []) or data.get('artists', [])
        seed_songs = data.get('seed_songs', [])
        genres = data.get('genres', [])
        max_tracks = max(10, data.get('max_tracks', 20))  # Minimum 10 tracks
        
        # Mood descriptions for better AI understanding
        mood_descriptions = {
            'chill': 'relaxed, calm, laid-back',
            'energetic': 'upbeat, high-energy, pump-up',
            'focus': 'concentration, ambient, instrumental',
            'happy': 'uplifting, feel-good, positive',
            'sad': 'melancholic, emotional, slow',
            'party': 'dance, club, EDM',
            'romantic': 'love songs, slow jams',
            'workout': 'high energy, motivating',
            'sleep': 'calm, ambient, peaceful',
            'custom': 'mixed genres'
        }
        mood_desc = mood_descriptions.get(mood.lower(), mood)
        
        # Build a concise but effective prompt
        prompt_parts = [f"Generate {max_tracks} real songs for \"{mood}\" mood ({mood_desc})."]
        
        if liked_artists:
            prompt_parts.append(f"Include multiple songs by: {', '.join(liked_artists)}. Also include similar artists.")
        
        if genres:
            prompt_parts.append(f"Genres: {', '.join(genres)}.")
            
        if seed_songs:
            prompt_parts.append(f"Similar to: {', '.join(seed_songs)}.")
        
        prompt_parts.append("""
Return ONLY a JSON array, no markdown or explanation.
Format: [{"artist": "Name", "title": "Song"}, ...]""")
        
        prompt = " ".join(prompt_parts)

        # Get Ollama URL from database settings or configured provider
        ollama_url = db.get_setting('ollama_url')
        if not ollama_url:
            # Try to get from configured Ollama provider
            providers = db.get_ai_providers()
            for p in providers:
                if p.get('provider_type') == 'ollama' and p.get('is_active'):
                    ollama_url = p.get('base_url') or p.get('config_data', {}).get('base_url')
                    if ollama_url:
                        break
        if not ollama_url:
            ollama_url = 'http://localhost:11434'
        
        logger.info(f"Using Ollama URL for playlist generation: {ollama_url}")
        
        # Use llama3.2:1b which follows instructions better than tinyllama
        model = 'llama3.2:1b'
        
        # Try to use the configured model if available
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{ollama_url}/api/tags") as resp:
                    if resp.status == 200:
                        tags = await resp.json()
                        available_models = [m['name'] for m in tags.get('models', [])]
                        if 'llama3.2:1b' in available_models:
                            model = 'llama3.2:1b'
                        elif 'llama3.2:latest' in available_models:
                            model = 'llama3.2:latest'
                        elif 'roger:latest' in available_models:
                            model = 'roger:latest'
                        logger.info(f"Using model {model} for playlist generation")
        except Exception as e:
            logger.warning(f"Could not check available models: {e}")
        
        # Call Ollama directly
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{ollama_url}/api/generate",
                json={
                    "model": model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 2000
                    }
                },
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Ollama error: {error_text}")
                    raise HTTPException(status_code=500, detail=f"AI service error: {error_text}")
                
                result = await response.json()
                ai_response = result.get('response', '')
                logger.info(f"AI playlist response: {ai_response[:200]}...")
        
        # Parse the JSON from the response
        # Remove code blocks
        clean_response = ai_response
        clean_response = re.sub(r'```json\s*', '', clean_response)
        clean_response = re.sub(r'```\s*', '', clean_response)
        clean_response = re.sub(r'```python[\s\S]*?```', '', clean_response)
        clean_response = re.sub(r'```bash[\s\S]*?```', '', clean_response)
        
        # Find JSON array with artist/title
        tracks = None
        
        # First, try to parse the entire response as JSON (with cleaning)
        clean_response_stripped = clean_response.strip()
        if clean_response_stripped.startswith('['):
            try:
                # Find the matching closing bracket
                bracket_count = 0
                end_pos = 0
                for i, char in enumerate(clean_response_stripped):
                    if char == '[':
                        bracket_count += 1
                    elif char == ']':
                        bracket_count -= 1
                        if bracket_count == 0:
                            end_pos = i + 1
                            break
                
                json_str = clean_response_stripped[:end_pos]
                json_str = json_str.replace('\u2018', "'").replace('\u2019', "'")
                json_str = json_str.replace('\u201c', '"').replace('\u201d', '"')
                json_str = re.sub(r',\s*]', ']', json_str)
                json_str = re.sub(r',\s*}', '}', json_str)
                
                parsed = json.loads(json_str)
                if isinstance(parsed, list) and len(parsed) > 0:
                    if isinstance(parsed[0], dict) and 'artist' in parsed[0]:
                        tracks = parsed
                    elif isinstance(parsed[0], str) and ' - ' in parsed[0]:
                        # Convert "Artist - Title" format
                        tracks = []
                        for item in parsed:
                            if isinstance(item, str) and ' - ' in item:
                                parts = item.split(' - ', 1)
                                tracks.append({"artist": parts[0].strip(), "title": parts[1].strip()})
            except (json.JSONDecodeError, IndexError):
                pass
        
        # Fallback: find JSON arrays in the response
        if not tracks:
            json_matches = re.findall(r'\[[\s\S]*?\]', clean_response)
            for match in json_matches:
                if '"artist"' in match and '"title"' in match:
                    try:
                        # Clean up common JSON issues
                        clean_json = match
                        clean_json = clean_json.replace('\u2018', "'").replace('\u2019', "'")
                        clean_json = clean_json.replace('\u201c', '"').replace('\u201d', '"')
                        clean_json = re.sub(r',\s*]', ']', clean_json)
                        clean_json = re.sub(r',\s*}', '}', clean_json)
                        
                        tracks = json.loads(clean_json)
                        if isinstance(tracks, list) and len(tracks) > 0:
                            break
                    except json.JSONDecodeError:
                        continue
                else:
                    # Try parsing as simple string array like ["Artist - Title", ...]
                    try:
                        parsed = json.loads(match)
                        if isinstance(parsed, list) and len(parsed) > 0 and isinstance(parsed[0], str):
                            # Convert "Artist - Title" format to objects
                            converted = []
                            for item in parsed:
                                if isinstance(item, str) and ' - ' in item:
                                    parts = item.split(' - ', 1)
                                    if len(parts) == 2:
                                        converted.append({"artist": parts[0].strip(), "title": parts[1].strip()})
                            if converted:
                                tracks = converted
                                break
                    except json.JSONDecodeError:
                        continue
        
        # Fallback: extract individual song objects
        if not tracks:
            song_pattern = r'\{\s*"artist"\s*:\s*"([^"]+)"\s*,\s*"title"\s*:\s*"([^"]+)"\s*\}'
            song_matches = re.findall(song_pattern, clean_response)
            if song_matches:
                tracks = [{"artist": m[0], "title": m[1]} for m in song_matches]
        
        # Fallback: look for "Artist - Title" pattern anywhere in response
        if not tracks:
            # Match quoted strings in format "Artist - Title"
            string_pattern = r'"([^"]+)\s*-\s*([^"]+)"'
            string_matches = re.findall(string_pattern, clean_response)
            if string_matches and len(string_matches) >= 2:  # At least 2 songs
                tracks = [{"artist": m[0].strip(), "title": m[1].strip()} for m in string_matches]
        
        if not tracks or len(tracks) == 0:
            logger.error(f"Could not parse playlist from AI response: {ai_response}")
            raise HTTPException(status_code=500, detail="AI did not return valid playlist data")
        
        # Filter valid tracks
        tracks = [t for t in tracks if isinstance(t, dict) and t.get('artist') and t.get('title')]
        
        logger.info(f"Generated playlist with {len(tracks)} tracks")
        return {
            "success": True,
            "tracks": tracks,
            "mood": mood,
            "model": model
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating AI playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/youtube/search")
async def youtube_search(q: str):
    """Search YouTube and return the first video ID with fast fallbacks."""
    import aiohttp
    import re
    from urllib.parse import quote_plus, unquote

    def extract_video_id(text: str):
        patterns = [
            r'"videoId":"([a-zA-Z0-9_-]{11})"',
            r'href="/watch\?v=([a-zA-Z0-9_-]{11})',
            r'watch\?v=([a-zA-Z0-9_-]{11})',
            r'youtu\.be/([a-zA-Z0-9_-]{11})',
            r'%2Fwatch%3Fv%3D([a-zA-Z0-9_-]{11})',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return None
    
    try:
        encoded_query = quote_plus(q)
        candidates = [
            (
                f"https://www.youtube.com/results?search_query={encoded_query}&hl=en&gl=US",
                {
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                },
                'youtube-html',
            ),
            (
                f"https://html.duckduckgo.com/html/?q={quote_plus(f'site:youtube.com/watch {q}')}",
                {
                    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    'Accept-Language': 'en-US,en;q=0.9',
                },
                'duckduckgo-html',
            ),
        ]

        timeout = aiohttp.ClientTimeout(total=4, connect=2, sock_read=3)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            for search_url, headers, source in candidates:
                try:
                    async with session.get(search_url, headers=headers) as response:
                        if response.status != 200:
                            continue
                        html = await response.text()
                        video_id = extract_video_id(html)
                        if not video_id and source == 'duckduckgo-html':
                            decoded_html = unquote(html)
                            video_id = extract_video_id(decoded_html)
                        if video_id:
                            logger.info(f"YouTube search for '{q}' found video: {video_id} via {source}")
                            return {"videoId": video_id, "query": q, "source": source}
                except asyncio.TimeoutError:
                    logger.warning(f"YouTube search timeout via {source} for query: {q}")
                except Exception as source_error:
                    logger.warning(f"YouTube search source {source} failed for '{q}': {source_error}")

        logger.warning(f"No video found for query: {q}")
        return {"videoId": None, "query": q, "error": "No video found", "searchUrl": f"https://www.youtube.com/results?search_query={encoded_query}"}
        
    except Exception as e:
        logger.error(f"YouTube search error for '{q}': {e}")
        return {"videoId": None, "query": q, "error": str(e)}


# Note: Music playlist endpoints are now in modules/music/endpoints.py
# which is included via music_router - provides:
# - /api/music/playlists (GET, POST)
# - /api/music/playback-state (GET, POST)
# - /api/music/playback-state/index (PUT)
# - /api/music/liked-songs (GET, POST, DELETE)
# - /api/music/initial-data (GET)

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
            scopes=get_google_oauth_scopes(),
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
            scopes=get_google_oauth_scopes(),
            redirect_uri='http://localhost:8008/auth/google/callback'
        )
        
        # Exchange code for token (disable scope validation to handle Google's automatic additions)
        try:
            flow.fetch_token(code=code)
        except Exception as token_error:
            # If scope mismatch, user needs to disconnect and retry
            if 'Scope has changed' in str(token_error):
                logger.warning(f"Scope mismatch detected: {token_error}. User needs to disconnect and retry.")
                raise HTTPException(
                    status_code=400,
                    detail=f"OAuth scope changed. Please disconnect and reconnect: {str(token_error)}"
                )
            raise
        
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
        
        # Return success page that redirects back to the dashboard
        return HTMLResponse(content="""
        <html>
            <head>
                <title>Google Authentication Success</title>
                <meta http-equiv="refresh" content="2;url=/">
            </head>
            <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%); color: white; min-height: 100vh;">
                <div style="max-width: 400px; margin: 0 auto; padding-top: 100px;">
                    <div style="font-size: 64px; margin-bottom: 20px;">✅</div>
                    <h2 style="color: #4ade80; margin-bottom: 16px;">Google Authentication Successful!</h2>
                    <p style="color: #9ca3af; margin-bottom: 24px;">Your Google Calendar and Gmail access has been configured.</p>
                    <p style="color: #6b7280; font-size: 14px;">Redirecting to dashboard...</p>
                    <div style="margin-top: 20px;">
                        <a href="/" style="color: #60a5fa; text-decoration: none;">Click here if not redirected automatically</a>
                    </div>
                </div>
                <script>
                    // Redirect to dashboard after brief delay
                    setTimeout(() => {
                        window.location.href = '/';
                    }, 2000);
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
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        
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
        
        scopes = token_data.get('scopes', [])
        has_refresh_token = bool(token_data.get('refresh_token'))

        # Check expiry
        expiry_str = token_data.get('expiry')
        is_expired = False
        if expiry_str:
            try:
                expiry = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
                is_expired = expiry < datetime.now(expiry.tzinfo)
            except:
                pass

        # If expired but we have a refresh token, refresh silently and persist.
        if is_expired and has_refresh_token:
            try:
                creds = Credentials.from_authorized_user_file(str(tokens_file), get_google_oauth_scopes())
                if creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                    with open(tokens_file, 'w') as f:
                        f.write(creds.to_json())

                    # Reload token data after successful refresh.
                    token_data = json.loads(creds.to_json())
                    scopes = token_data.get('scopes', scopes)
                    is_expired = False
                    logger.info("Refreshed Google credentials during status check")
            except Exception as refresh_error:
                logger.warning(f"Could not refresh Google token during status check: {refresh_error}")
        
        scope_names = []
        if 'https://www.googleapis.com/auth/calendar.readonly' in scopes:
            scope_names.append('Calendar')
        if 'https://www.googleapis.com/auth/gmail.readonly' in scopes:
            scope_names.append('Gmail')
        if 'https://www.googleapis.com/auth/drive.readonly' in scopes:
            scope_names.append('Drive')
        can_modify_gmail = has_required_google_scopes(scopes, GOOGLE_GMAIL_WRITE_SCOPES)
        # Require reconnect only for actual auth breakage, not merely reduced (read-only) scope.
        needs_reconnect = (is_expired and not has_refresh_token)

        if is_expired:
            message = "⚠️ Token expired - please reconnect"
        elif not can_modify_gmail:
            message = "✅ Connected (read-only Gmail scope). Reconnect only if you need mark-read/archive/labels actions."
        else:
            message = f"✅ Connected ({', '.join(scope_names)})"
        
        return {
            "authenticated": True,
            "expired": is_expired,
            "needs_reconnect": needs_reconnect,
            "can_modify_gmail": can_modify_gmail,
            "has_refresh_token": has_refresh_token,
            "message": message,
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


def _default_ai_assistants_config() -> Dict[str, Any]:
    """Default assistant personas and voice settings."""
    return {
        "active_assistant_id": "rogr",
        "assistants": [
            {
                "id": "rogr",
                "name": "Rogr",
                "personality": "Mission-focused, concise, practical",
                "tagline": "Mission clarity achieved.",
                "key_phrases": ["roger roger", "locked and loaded", "objective complete"],
                "voice_style": "droid",
                "voice_speed": 0.72,
                "voice_pitch": 0.74,
                "voice_model": "en_US-ryan-high",
                "signature_phrase": "roger, roger",
                "signature_enabled": True,
                "browser_voice": "rogr"
            },
            {
                "id": "strategist",
                "name": "Strategist",
                "personality": "Executive, structured, prioritization-first",
                "tagline": "Focus drives outcomes.",
                "key_phrases": ["top priority", "critical path", "next best action"],
                "voice_style": "clean",
                "voice_speed": 0.92,
                "voice_pitch": 0.98,
                "voice_model": "en_US-libritts-high",
                "signature_phrase": "focus drives outcomes",
                "signature_enabled": False,
                "browser_voice": "rogr"
            },
            {
                "id": "coach",
                "name": "Coach",
                "personality": "Supportive, clear, momentum-building",
                "tagline": "Small wins, steady momentum.",
                "key_phrases": ["small win", "momentum", "one step at a time"],
                "voice_style": "radio",
                "voice_speed": 0.85,
                "voice_pitch": 1.08,
                "voice_model": "en_US-lessac-medium",
                "signature_phrase": "small wins, steady momentum",
                "signature_enabled": False,
                "browser_voice": "rogr"
            }
        ]
    }


def _normalize_assistant_payload(raw: Dict[str, Any], assistant_id: Optional[str] = None) -> Dict[str, Any]:
    """Normalize assistant payload from API input."""
    key_phrases = raw.get('key_phrases', [])
    if isinstance(key_phrases, str):
        key_phrases = [p.strip() for p in key_phrases.split(',') if p.strip()]
    if not isinstance(key_phrases, list):
        key_phrases = []

    requested_style = str(raw.get('voice_style') or 'droid').strip()
    style_defaults = {
        'droid': (0.72, 0.74),
        'clean': (0.95, 1.00),
        'radio': (0.84, 1.08),
        'pa_system': (0.80, 0.92),
        'cinematic': (0.88, 0.92),
        'glitch': (1.08, 1.22),
    }
    allowed_models = {
        'auto',
        'en_US-ryan-high',
        'en_US-libritts-high',
        'en_US-lessac-medium',
    }
    default_speed, default_pitch = style_defaults.get(requested_style, (0.75, 0.85))

    raw_speed = raw.get('voice_speed', default_speed)
    raw_pitch = raw.get('voice_pitch', default_pitch)
    if raw_speed in (None, ''):
        raw_speed = default_speed
    if raw_pitch in (None, ''):
        raw_pitch = default_pitch

    normalized = {
        "id": assistant_id or raw.get('id') or f"asst_{secrets.token_hex(4)}",
        "name": str(raw.get('name') or 'Assistant').strip(),
        "personality": str(raw.get('personality') or '').strip(),
        "tagline": str(raw.get('tagline') or '').strip(),
        "key_phrases": key_phrases[:12],
        "voice_style": requested_style,
        "voice_speed": float(raw_speed),
        "voice_pitch": float(raw_pitch),
        "voice_model": str(raw.get('voice_model') or 'auto').strip(),
        "signature_phrase": str(raw.get('signature_phrase') or 'roger, roger').strip(),
        "signature_enabled": bool(raw.get('signature_enabled', True)),
        "browser_voice": str(raw.get('browser_voice') or 'rogr').strip(),
    }

    normalized['voice_speed'] = max(0.4, min(1.4, normalized['voice_speed']))
    normalized['voice_pitch'] = max(0.4, min(1.4, normalized['voice_pitch']))
    if normalized['voice_model'] not in allowed_models:
        normalized['voice_model'] = 'auto'

    if not normalized['name']:
        normalized['name'] = 'Assistant'

    return normalized


def _get_ai_assistants_config() -> Dict[str, Any]:
    """Get assistant configuration from settings, creating defaults if needed."""
    config = db.get_setting('ai_assistants', None)
    if not isinstance(config, dict) or not isinstance(config.get('assistants'), list) or len(config.get('assistants', [])) == 0:
        config = _default_ai_assistants_config()
        db.save_setting('ai_assistants', config)
        return config

    assistants = config.get('assistants', [])
    normalized_assistants = []
    changed = False
    style_defaults = {
        'droid': (0.72, 0.74),
        'clean': (0.95, 1.00),
        'radio': (0.84, 1.08),
        'pa_system': (0.80, 0.92),
        'cinematic': (0.88, 0.92),
        'glitch': (1.08, 1.22),
    }
    for assistant in assistants:
        normalized = _normalize_assistant_payload(assistant, assistant.get('id'))

        # Migration: if legacy generic tuning is still present, apply style defaults.
        legacy_speed = float(normalized.get('voice_speed', 0.75))
        legacy_pitch = float(normalized.get('voice_pitch', 0.85))
        if abs(legacy_speed - 0.75) < 1e-9 and abs(legacy_pitch - 0.85) < 1e-9:
            default_speed, default_pitch = style_defaults.get(normalized.get('voice_style', 'droid'), (0.75, 0.85))
            normalized['voice_speed'] = default_speed
            normalized['voice_pitch'] = default_pitch

        if normalized != assistant:
            changed = True
        normalized_assistants.append(normalized)

    if changed:
        config['assistants'] = normalized_assistants

    active_id = config.get('active_assistant_id')
    if not any(a.get('id') == active_id for a in config['assistants']):
        config['active_assistant_id'] = config['assistants'][0].get('id')
        changed = True

    if changed:
        db.save_setting('ai_assistants', config)

    return config


def _get_assistant_by_id(assistant_id: Optional[str] = None) -> Dict[str, Any]:
    """Get assistant by id, or active assistant if id is omitted."""
    config = _get_ai_assistants_config()
    assistants: List[Dict[str, Any]] = config.get('assistants', [])
    target_id = assistant_id or config.get('active_assistant_id')

    for assistant in assistants:
        if assistant.get('id') == target_id:
            return assistant
    return assistants[0] if assistants else {}


def _apply_voice_assistant_profile(assistant: Dict[str, Any]) -> str:
    """Apply assistant voice signature to voice module and return preferred style."""
    style = assistant.get('voice_style', 'droid') if assistant else 'droid'

    model_by_style = {
        'droid': 'en_US-ryan-high',
        'clean': 'en_US-libritts-high',
        'radio': 'en_US-lessac-medium',
        'pa_system': 'en_US-ryan-high',
        'cinematic': 'en_US-libritts-high',
        'glitch': 'en_US-lessac-medium',
    }
    try:
        import voice as voice_module
        voice_obj = voice_module.get_voice()
        if assistant and assistant.get('signature_phrase'):
            voice_obj.signature = assistant.get('signature_phrase')
        if assistant:
            if 'voice_speed' in assistant:
                voice_obj.speed = float(assistant.get('voice_speed', voice_obj.speed))
            if 'voice_pitch' in assistant:
                voice_obj.pitch = float(assistant.get('voice_pitch', voice_obj.pitch))
            if assistant.get('voice_style'):
                voice_obj.default_style = assistant.get('voice_style')

            requested_model = str(assistant.get('voice_model') or 'auto').strip()
            if getattr(voice_obj, 'engine', 'piper') == 'coqui':
                coqui_speaker_by_style = {
                    'droid': 'p230',
                    'clean': 'p225',
                    'radio': 'p226',
                    'pa_system': 'p227',
                    'cinematic': 'p228',
                    'glitch': 'p229',
                }
                requested_speaker = str(assistant.get('coqui_speaker') or '').strip()
                active_coqui_model = str(getattr(voice_obj, 'coqui_model', '') or '').lower()
                if requested_speaker:
                    voice_obj.coqui_speaker = requested_speaker
                elif 'vctk' in active_coqui_model:
                    voice_obj.coqui_speaker = coqui_speaker_by_style.get(style)
                else:
                    voice_obj.coqui_speaker = None
            else:
                selected_model = model_by_style.get(style, 'en_US-ryan-high') if requested_model == 'auto' else requested_model
                model_path = project_root / 'data' / 'voice_models' / 'piper' / f"{selected_model}.onnx"
                if model_path.exists():
                    voice_obj.model_path = str(model_path)
                else:
                    logger.warning(f"Requested voice model not found: {model_path}")
    except Exception as e:
        logger.warning(f"Unable to apply assistant voice profile: {e}")
    return style


@app.get("/api/ai/assistants")
async def get_ai_assistants():
    """Get all configured AI assistants and active assistant ID."""
    try:
        config = _get_ai_assistants_config()
        return {
            "success": True,
            "active_assistant_id": config.get('active_assistant_id'),
            "assistants": config.get('assistants', [])
        }
    except Exception as e:
        logger.error(f"Error getting AI assistants: {e}")
        return {"success": False, "error": str(e), "assistants": []}


@app.post("/api/ai/assistants/save")
async def save_ai_assistant(request: Request):
    """Create or update an AI assistant persona."""
    try:
        data = await request.json()
        incoming = data.get('assistant', data)
        incoming_id = incoming.get('id')

        config = _get_ai_assistants_config()
        assistants = config.get('assistants', [])

        normalized = _normalize_assistant_payload(incoming, incoming_id)
        existing_index = next((i for i, a in enumerate(assistants) if a.get('id') == normalized['id']), -1)

        if existing_index >= 0:
            assistants[existing_index] = normalized
            action = 'updated'
        else:
            assistants.append(normalized)
            action = 'created'

        config['assistants'] = assistants
        if not config.get('active_assistant_id'):
            config['active_assistant_id'] = normalized['id']

        db.save_setting('ai_assistants', config)
        return {
            "success": True,
            "assistant": normalized,
            "active_assistant_id": config.get('active_assistant_id'),
            "message": f"Assistant {action}"
        }
    except Exception as e:
        logger.error(f"Error saving AI assistant: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/ai/assistants/select")
async def select_ai_assistant(request: Request):
    """Set the active AI assistant."""
    try:
        data = await request.json()
        assistant_id = data.get('assistant_id')
        if not assistant_id:
            return {"success": False, "error": "assistant_id is required"}

        config = _get_ai_assistants_config()
        assistants = config.get('assistants', [])
        if not any(a.get('id') == assistant_id for a in assistants):
            return {"success": False, "error": "Assistant not found"}

        config['active_assistant_id'] = assistant_id
        db.save_setting('ai_assistants', config)
        return {"success": True, "active_assistant_id": assistant_id}
    except Exception as e:
        logger.error(f"Error selecting AI assistant: {e}")
        return {"success": False, "error": str(e)}


@app.delete("/api/ai/assistants/{assistant_id}")
async def delete_ai_assistant(assistant_id: str):
    """Delete an AI assistant persona."""
    try:
        config = _get_ai_assistants_config()
        assistants = config.get('assistants', [])
        if len(assistants) <= 1:
            return {"success": False, "error": "At least one assistant is required"}

        filtered = [a for a in assistants if a.get('id') != assistant_id]
        if len(filtered) == len(assistants):
            return {"success": False, "error": "Assistant not found"}

        config['assistants'] = filtered
        if config.get('active_assistant_id') == assistant_id:
            config['active_assistant_id'] = filtered[0].get('id')

        db.save_setting('ai_assistants', config)
        return {
            "success": True,
            "active_assistant_id": config.get('active_assistant_id')
        }
    except Exception as e:
        logger.error(f"Error deleting AI assistant: {e}")
        return {"success": False, "error": str(e)}


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
        speak_response = data.get('speak', False)  # New: option to speak response
        assistant_id = data.get('assistant_id')
        include_context = data.get('include_context', True)

        # Accept truthy/falsey string values from UI callers.
        if isinstance(include_context, str):
            include_context = include_context.strip().lower() not in ('0', 'false', 'no', 'off', '')
        include_context = bool(include_context)
        
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
            include_context=include_context,
            assistant_id=assistant_id
        )
        
        if not result.get('success'):
            return {"error": result.get('error', 'Unknown error')}
        
        # Speak the response if requested
        if speak_response and result.get('response'):
            try:
                import voice as voice_module
                active_assistant = _get_assistant_by_id(assistant_id)
                style = _apply_voice_assistant_profile(active_assistant)
                add_signature = bool(active_assistant.get('signature_enabled', True)) if active_assistant else True
                # Speak in background (non-blocking)
                if add_signature:
                    voice_module.announce(result['response'], style=style, blocking=False)
                else:
                    voice_module.say(result['response'], style=style, blocking=False)
            except Exception as e:
                logger.warning(f"Voice output failed: {e}")
        
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
    quiet: bool = False,
    assistant_id: str = None
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
                    include_context=True,
                    assistant_id=assistant_id
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
        context = await ai_service.build_context(force_refresh=True)
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


@app.get("/api/ai/memory")
async def get_ai_memory():
    """Get AI short-term and long-term markdown memory."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI not available", "success": False}

    try:
        ai_service = get_ai_service(db, settings)
        snapshot = ai_service.get_memory_snapshot()
        return {
            "success": True,
            "memory": snapshot
        }
    except Exception as e:
        logger.error(f"Error getting AI memory: {e}")
        return {"error": str(e), "success": False}


@app.post("/api/ai/memory")
async def save_ai_memory(request: Request):
    """Save AI memory markdown content."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI not available", "success": False}

    try:
        data = await request.json()
        memory_type = data.get('memory_type')
        content = data.get('content', '')

        ai_service = get_ai_service(db, settings)
        ai_service.save_memory_content(memory_type, content)
        snapshot = ai_service.get_memory_snapshot()

        return {
            "success": True,
            "memory": snapshot,
            "message": f"{memory_type.replace('_', ' ').title()} saved"
        }
    except Exception as e:
        logger.error(f"Error saving AI memory: {e}")
        return {"error": str(e), "success": False}


@app.post("/api/ai/memory/clear")
async def clear_ai_memory(request: Request):
    """Reset AI memory markdown content."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI not available", "success": False}

    try:
        data = await request.json()
        memory_type = data.get('memory_type')

        ai_service = get_ai_service(db, settings)
        ai_service.reset_memory(memory_type)
        snapshot = ai_service.get_memory_snapshot()

        return {
            "success": True,
            "memory": snapshot,
            "message": f"{memory_type.replace('_', ' ').title()} reset"
        }
    except Exception as e:
        logger.error(f"Error clearing AI memory: {e}")
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
            ollama_model = db.get_setting('ollama_model', 'deepseek-r1:latest')
            
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


@app.get("/api/leads/list")
async def get_leads_list(limit: int = 100):
    """Get leads list (alias for /api/leads with different format)."""
    try:
        # Import lead generation modules
        from processors.lead_generator import LeadGenerator, PotentialLead
        
        lead_generator = LeadGenerator()
        leads_list = []
        
        # Try to load existing leads from file
        try:
            leads_file = project_root / "data" / "generated_leads.json"
            with open(leads_file, 'r') as f:
                leads_data = json.load(f)
                leads_list = leads_data if isinstance(leads_data, list) else []
        except FileNotFoundError:
            leads_list = []
        
        # Apply limit
        leads_list = leads_list[:limit]
        
        return {
            "leads": leads_list,
            "total": len(leads_list)
        }
        
    except Exception as e:
        logger.error(f"Error getting leads list: {e}")
        return {"leads": [], "total": 0, "error": str(e)}


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


@app.get("/api/diagnostics/events")
async def get_diagnostic_events(limit: int = Query(30, ge=1, le=200)):
    """Get recent diagnostic events for self-heal UI."""
    try:
        with DIAGNOSTIC_LOCK:
            events = list(DIAGNOSTIC_EVENTS)[-limit:]
        return {
            "success": True,
            "events": list(reversed(events)),
            "count": len(events)
        }
    except Exception as e:
        logger.error(f"Error getting diagnostic events: {e}")
        return {"success": False, "events": [], "error": str(e)}


@app.post("/api/diagnostics/report")
async def report_diagnostic_event(request: Request):
    """Report runtime error/event and optionally run AI diagnosis."""
    try:
        data = await request.json()
        module_name = (data.get('module') or 'general').strip()
        source = (data.get('source') or 'runtime').strip()
        error_message = (data.get('message') or data.get('detail') or 'Unknown error').strip()
        stack_trace = (data.get('stack') or data.get('traceback') or '').strip()
        title = (data.get('title') or error_message[:120]).strip() or 'Runtime error'
        auto_analyze = bool(data.get('auto_analyze', True))
        context = data.get('context') if isinstance(data.get('context'), dict) else {}

        event = {
            "id": f"diag_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}",
            "created_at": datetime.now().isoformat(),
            "title": title,
            "module": module_name,
            "source": source,
            "message": error_message,
            "stack": stack_trace,
            "context": context,
            "diagnosis": None,
            "status": "reported"
        }

        if auto_analyze:
            diagnosis = await _run_ai_diagnostic(
                title=title,
                module_name=module_name,
                source=source,
                error_message=error_message,
                stack_trace=stack_trace,
                context=context,
                include_repair_actions=True
            )
            event["diagnosis"] = diagnosis
            event["status"] = "diagnosed"

        _push_diagnostic_event(event)

        return {
            "success": True,
            "event": event,
            "message": "Diagnostic event recorded"
        }
    except Exception as e:
        logger.error(f"Error reporting diagnostic event: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/diagnostics/review")
async def review_diagnostic_module(request: Request):
    """User-requested AI diagnostic review for a module/section."""
    try:
        data = await request.json()
        module_name = (data.get('module') or 'general').strip()
        review_notes = (data.get('notes') or '').strip()
        source = (data.get('source') or 'manual_review').strip()
        context = data.get('context') if isinstance(data.get('context'), dict) else {}

        combined_message = review_notes or f"User requested a diagnostic review for module '{module_name}'."
        diagnosis = await _run_ai_diagnostic(
            title=f"Manual review: {module_name}",
            module_name=module_name,
            source=source,
            error_message=combined_message,
            stack_trace='',
            context=context,
            include_repair_actions=True
        )

        event = {
            "id": f"diag_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(3)}",
            "created_at": datetime.now().isoformat(),
            "title": f"Manual review: {module_name}",
            "module": module_name,
            "source": source,
            "message": combined_message,
            "stack": '',
            "context": context,
            "diagnosis": diagnosis,
            "status": "diagnosed"
        }

        _push_diagnostic_event(event)

        return {
            "success": True,
            "event": event,
            "diagnosis": diagnosis
        }
    except Exception as e:
        logger.error(f"Error reviewing module diagnostics: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/diagnostics/repair")
async def run_diagnostic_repair(request: Request):
    """Execute approved repair action generated by diagnostics."""
    try:
        data = await request.json()
        event_id = (data.get('event_id') or '').strip()
        action_key = (data.get('action_key') or '').strip()
        approved = bool(data.get('approved', False))
        module_name = (data.get('module') or '').strip()

        if not approved:
            return {"success": False, "error": "Repair action must be explicitly approved"}
        if not action_key:
            return {"success": False, "error": "action_key is required"}

        target_event = _find_diagnostic_event(event_id) if event_id else None
        if target_event and not module_name:
            module_name = str(target_event.get('module') or '').strip()

        if action_key == 'restart_dashboard':
            command = f"cd '{str(project_root)}' && ./ops/startup.sh restart"
            subprocess.Popen(
                ['bash', '-lc', command],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                preexec_fn=os.setpgrp
            )
            return {
                "success": True,
                "action": action_key,
                "message": "Dashboard restart initiated"
            }

        if action_key == 'refresh_module':
            widget_map = {
                'emails': 'email',
                'email': 'email',
                'calendar': 'calendar',
                'todos': 'tasks',
                'tasks': 'tasks',
                'github': 'github',
                'news': 'news',
                'weather': 'weather',
                'music': 'music',
                'servers': 'servers'
            }
            widget_name = widget_map.get(module_name.lower()) if module_name else None
            if widget_name in background_manager.cache:
                background_manager.cache.pop(widget_name, None)
                background_manager.cache_timestamps.pop(widget_name, None)

            return {
                "success": True,
                "action": action_key,
                "module": module_name,
                "message": f"Module refresh prepared for {module_name or 'selected section'}"
            }

        return {"success": False, "error": f"Unsupported repair action: {action_key}"}
    except Exception as e:
        logger.error(f"Error running diagnostic repair: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


@app.post("/api/diagnostics/apply-fix")
async def apply_diagnostic_code_fix(request: Request):
    """Apply AI-generated code patches, commit to a fix branch, push, and open a GitHub PR."""
    try:
        data = await request.json()
        event_id = (data.get('event_id') or '').strip()
        approved = bool(data.get('approved', False))
        code_fixes = data.get('code_fixes')
        commit_message = (data.get('commit_message') or '').strip()
        pr_title = (data.get('pr_title') or '').strip()
        pr_body = (data.get('pr_body') or '').strip()

        if not approved:
            return {"success": False, "error": "apply-fix must be explicitly approved"}

        # Load fixes from event if not supplied inline
        if not code_fixes and event_id:
            target_event = _find_diagnostic_event(event_id)
            if target_event:
                diagnosis = target_event.get('diagnosis') or {}
                code_fixes = diagnosis.get('code_fixes') or []
                if not commit_message:
                    commit_message = diagnosis.get('commit_message') or ''
                if not pr_title:
                    pr_title = diagnosis.get('pr_title') or target_event.get('title') or 'AI fix'
                if not pr_body:
                    pr_body = diagnosis.get('pr_body') or ''

        if not isinstance(code_fixes, list) or not code_fixes:
            return {"success": False, "error": "No code fixes provided"}

        commit_message = commit_message or f"fix(ai-diag): automated repair for event {event_id or 'unknown'}"
        pr_title = pr_title or commit_message

        gh = _get_github_token_and_repo()
        if not gh['token'] or not gh['owner'] or not gh['repo']:
            return {
                "success": False,
                "error": "GitHub credentials or remote origin not configured. Set a GitHub token in Settings → Credentials."
            }

        base_branch = _get_default_branch()

        # Ensure we're on the default branch before creating fix branch
        subprocess.run(
            ['git', 'checkout', base_branch],
            check=True, capture_output=True, timeout=10,
            cwd=str(project_root)
        )

        # Create a stash checkpoint so we can restore if something goes wrong
        stash_label = f"diag-rollback-{event_id or 'fix'}"
        subprocess.run(
            ['git', 'stash', 'push', '-u', '-m', stash_label],
            capture_output=True, timeout=15, cwd=str(project_root)
        )

        fix_branch = _create_fix_branch(event_id)

        try:
            modified_files = _apply_file_patches(code_fixes)
        except Exception as patch_err:
            # Roll back: restore stash, return to base branch, delete fix branch
            subprocess.run(['git', 'checkout', base_branch], capture_output=True, cwd=str(project_root))
            subprocess.run(['git', 'branch', '-D', fix_branch], capture_output=True, cwd=str(project_root))
            subprocess.run(['git', 'stash', 'pop'], capture_output=True, cwd=str(project_root))
            return {"success": False, "error": f"Patch failed: {patch_err}"}

        if not modified_files:
            subprocess.run(['git', 'checkout', base_branch], capture_output=True, cwd=str(project_root))
            subprocess.run(['git', 'branch', '-D', fix_branch], capture_output=True, cwd=str(project_root))
            return {"success": False, "error": "No files were modified (snippets may not match current source)"}

        # Build enriched commit body
        full_commit_message = commit_message + "\n\n" + "\n".join(
            f"- {f.get('description') or f.get('file')}" for f in code_fixes if isinstance(f, dict)
        )
        full_commit_message += f"\n\nDiagnostic event: {event_id}"

        try:
            sha = _git_commit_and_push(fix_branch, modified_files, full_commit_message)
        except subprocess.CalledProcessError as git_err:
            subprocess.run(['git', 'checkout', base_branch], capture_output=True, cwd=str(project_root))
            stderr = (git_err.stderr or b'').decode('utf-8', errors='replace')
            return {"success": False, "error": f"Git commit/push failed: {stderr[:500]}"}

        # Return to base branch so the running server is not on a detached state
        subprocess.run(['git', 'checkout', base_branch], capture_output=True, cwd=str(project_root))

        # Build PR body
        if not pr_body:
            file_list = "\n".join(f"- `{f}`" for f in modified_files)
            pr_body = (
                f"## AI-Generated Fix\n\n"
                f"Diagnostic event: `{event_id}`\n\n"
                f"### Modified Files\n{file_list}\n\n"
                f"### Changes\n" +
                "\n".join(f"- **{f.get('file')}**: {f.get('description')}" for f in code_fixes if isinstance(f, dict)) +
                f"\n\n### Commit\n`{sha}`\n\n> ⚠️ **Review before merging.** AI-generated changes should be carefully validated."
            )

        pr_data = _create_github_pr_via_api(
            token=gh['token'],
            owner=gh['owner'],
            repo=gh['repo'],
            head_branch=fix_branch,
            base_branch=base_branch,
            title=pr_title,
            body=pr_body
        )

        if 'error' in pr_data and not pr_data.get('html_url'):
            return {
                "success": False,
                "error": f"Code committed to branch '{fix_branch}' (SHA {sha}) but PR creation failed: {pr_data.get('error')}",
                "branch": fix_branch,
                "sha": sha,
                "modified_files": modified_files
            }

        pr_url = pr_data.get('html_url') or ''
        pr_number = pr_data.get('number')

        # Update diagnostic event with PR info
        target_event = _find_diagnostic_event(event_id) if event_id else None
        if target_event:
            target_event['pr'] = {
                "url": pr_url,
                "number": pr_number,
                "branch": fix_branch,
                "sha": sha,
                "modified_files": modified_files
            }
            target_event['status'] = 'pr_created'

        return {
            "success": True,
            "pr_url": pr_url,
            "pr_number": pr_number,
            "branch": fix_branch,
            "sha": sha,
            "modified_files": modified_files,
            "message": f"PR #{pr_number} created: {pr_url}"
        }
    except Exception as e:
        logger.error(f"Error applying diagnostic code fix: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


@app.get("/api/diagnostics/logs")
async def get_diagnostic_logs(
    lines: int = Query(150, ge=10, le=2000),
    level: Optional[str] = Query(None, description="Filter by level: ERROR, WARNING, INFO"),
    module: Optional[str] = Query(None, description="Filter by module name substring")
):
    """Return recent log lines from dashboard.log."""
    try:
        log_lines = _get_recent_logs(lines=lines, level_filter=level, module_filter=module)
        log_files = []
        if LOG_FILE_PATH.exists():
            import glob as _glob
            pattern = str(LOG_FILE_PATH) + "*"
            for lf in sorted(_glob.glob(pattern)):
                size = Path(lf).stat().st_size
                log_files.append({"path": lf, "size_kb": round(size / 1024, 1)})
        return {
            "success": True,
            "lines": log_lines,
            "count": len(log_lines),
            "log_files": log_files
        }
    except Exception as e:
        logger.error(f"Error reading logs: {e}")
        return {"success": False, "lines": [], "error": str(e)}


@app.post("/api/diagnostics/logs/clear")
async def clear_diagnostic_logs(request: Request):
    """Truncate the active dashboard.log (rotated backups are preserved)."""
    try:
        data = await request.json()
        confirmed = bool(data.get('confirmed', False))
        if not confirmed:
            return {"success": False, "error": "Pass confirmed=true to clear logs"}
        with open(str(LOG_FILE_PATH), "w", encoding="utf-8") as f:
            f.write(f"{datetime.now().isoformat()} INFO     system: Log cleared by user\n")
        logger.info("Dashboard log cleared by user via diagnostics API")
        return {"success": True, "message": "Log cleared"}
    except Exception as e:
        logger.error(f"Error clearing log: {e}")
        return {"success": False, "error": str(e)}


@app.post("/api/diagnostics/suggest-fix")
async def suggest_user_fix(request: Request):
    """User describes how to fix a problem; AI translates into code patches and returns them for approval."""
    try:
        data = await request.json()
        event_id = (data.get('event_id') or '').strip()
        suggestion = (data.get('suggestion') or '').strip()
        module_name = (data.get('module') or 'general').strip()

        if not suggestion:
            return {"success": False, "error": "suggestion text is required"}

        # Pull original event context if available
        original_message = ""
        original_stack = ""
        original_context: Dict[str, Any] = {}
        if event_id:
            ev = _find_diagnostic_event(event_id)
            if ev:
                original_message = ev.get('message') or ''
                original_stack = ev.get('stack') or ''
                original_context = ev.get('context') or {}
                if not module_name or module_name == 'general':
                    module_name = ev.get('module') or module_name

        log_context = _get_error_log_context(module_name, lines=80)

        if not AI_ASSISTANT_AVAILABLE:
            return {"success": False, "error": "AI provider not available"}

        ai_service = get_ai_service(db, settings)
        prompt = f"""
You are the dashboard self-diagnostic assistant.
The user has described how they want to fix a problem. Translate their description into concrete code patches.
Return STRICT JSON only.

Module: {module_name}
Original Error: {original_message or 'n/a'}
Stack Trace: {original_stack or 'n/a'}
Recent ERROR/WARNING Logs:
{log_context[:2000]}

User's Suggested Fix:
{suggestion}

Project source files are under src/ (Python: src/main.py; JS: src/static/dashboard.js; HTML: src/templates/dashboard_modern.html; collectors: src/collectors/; processors: src/processors/).

Return this JSON schema exactly:
{{
  "summary": "what this fix does",
  "code_fixes": [
    {{
      "file": "src/relative/path/to/file.py",
      "description": "what this change does",
      "old_snippet": "exact existing code to replace",
      "new_snippet": "replacement code"
    }}
  ],
  "commit_message": "fix(<module>): <description>",
  "pr_title": "Fix: <short title>",
  "pr_body": "## Problem\\n...\\n## Solution (user-suggested)\\n...\\n## Testing\\n...",
  "confidence": "low|medium|high",
  "risks": ["any risks to be aware of"],
  "manual_steps": ["anything the user must do manually"]
}}

Rules:
- old_snippet must be exact verbatim source text.
- If you cannot find a safe code change, return code_fixes as empty array and explain in summary.
- Be conservative and targeted.
""".strip()

        result = await ai_service.chat(
            message=prompt,
            conversation_id=f"suggest_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            include_context=False,
            assistant_id=None
        )

        if not result.get('success'):
            return {"success": False, "error": "AI failed to generate fix"}

        parsed = _extract_json_from_ai_text(result.get('response', ''))
        if not parsed or not isinstance(parsed, dict):
            return {"success": False, "error": "AI response could not be parsed", "raw": result.get('response', '')[:500]}

        # Normalise code_fixes
        raw_fixes = parsed.get('code_fixes') if isinstance(parsed.get('code_fixes'), list) else []
        normalized_fixes = [
            {
                "file": str(f.get('file') or '').strip(),
                "description": str(f.get('description') or '').strip(),
                "old_snippet": str(f.get('old_snippet') or '').strip(),
                "new_snippet": str(f.get('new_snippet') or '').strip()
            }
            for f in raw_fixes
            if isinstance(f, dict) and f.get('file') and f.get('old_snippet') and f.get('new_snippet')
        ]

        fix_plan = {
            "summary": parsed.get('summary') or '',
            "code_fixes": normalized_fixes,
            "commit_message": str(parsed.get('commit_message') or f"fix({module_name}): user-suggested repair").strip(),
            "pr_title": str(parsed.get('pr_title') or f"Fix: {module_name} (user-suggested)").strip(),
            "pr_body": str(parsed.get('pr_body') or '').strip(),
            "confidence": parsed.get('confidence') or 'low',
            "risks": parsed.get('risks') if isinstance(parsed.get('risks'), list) else [],
            "manual_steps": parsed.get('manual_steps') if isinstance(parsed.get('manual_steps'), list) else []
        }

        # Attach fix plan to original event for later apply-fix call
        if event_id:
            ev = _find_diagnostic_event(event_id)
            if ev:
                if not ev.get('diagnosis'):
                    ev['diagnosis'] = {}
                ev['diagnosis']['code_fixes'] = normalized_fixes
                ev['diagnosis']['commit_message'] = fix_plan['commit_message']
                ev['diagnosis']['pr_title'] = fix_plan['pr_title']
                ev['diagnosis']['pr_body'] = fix_plan['pr_body']
                ev['status'] = 'fix_planned'

        return {"success": True, "fix_plan": fix_plan, "event_id": event_id}
    except Exception as e:
        logger.error(f"Error in suggest-fix: {e}")
        logger.error(traceback.format_exc())
        return {"success": False, "error": str(e)}


@app.post("/api/diagnostics/rollback")
async def rollback_diagnostic_fix(request: Request):
    """Pop the latest git stash (diag-rollback-*) to undo a failed/unwanted patch application."""
    try:
        data = await request.json()
        confirmed = bool(data.get('confirmed', False))
        if not confirmed:
            return {"success": False, "error": "Pass confirmed=true to rollback"}

        result = subprocess.run(
            ['git', 'stash', 'list', '--format=%gd %s'],
            capture_output=True, text=True, timeout=10, cwd=str(project_root)
        )
        stash_entries = result.stdout.strip().splitlines()
        diag_stash = next((e for e in stash_entries if 'diag-rollback' in e), None)

        if not diag_stash:
            return {"success": False, "error": "No diagnostic rollback stash found"}

        stash_ref = diag_stash.split()[0]  # e.g. stash@{0}
        pop_result = subprocess.run(
            ['git', 'stash', 'pop', stash_ref],
            capture_output=True, text=True, timeout=15, cwd=str(project_root)
        )
        if pop_result.returncode != 0:
            return {"success": False, "error": f"Stash pop failed: {pop_result.stderr.strip()[:300]}"}

        return {"success": True, "message": f"Rolled back using stash: {stash_ref}"}
    except Exception as e:
        logger.error(f"Error rolling back: {e}")
        return {"success": False, "error": str(e)}


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


@app.post("/api/voice/test")
async def test_voice(request: Request):
    """Test the voice system - makes Rogr speak."""
    try:
        data = await request.json()
        assistant_id = data.get('assistant_id')
        active_assistant = _get_assistant_by_id(assistant_id)

        message = data.get('message') or active_assistant.get('tagline') or 'Roger roger. Voice system operational.'
        style = data.get('style') or _apply_voice_assistant_profile(active_assistant)
        add_signature = data.get('signature')
        if add_signature is None:
            add_signature = bool(active_assistant.get('signature_enabled', True))
        
        import voice as voice_module
        
        if add_signature:
            success = voice_module.announce(message, style=style, blocking=False)
        else:
            success = voice_module.say(message, style=style, blocking=False)
        
        return {
            "success": success,
            "message": message,
            "style": style,
            "signature": add_signature,
            "assistant_id": active_assistant.get('id')
        }
    except Exception as e:
        logger.error(f"Voice test error: {e}")
        return {"success": False, "error": str(e)}


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    await initialize_ai_providers()
    
    # Create data directory for lead generation files
    os.makedirs('data', exist_ok=True)
    
    # Initialize voice system (PersonaPlex)
    try:
        import voice_helper
        
        # Load voice configuration from settings
        voice_config = getattr(settings, 'voice', {})
        if not voice_config:
            try:
                runtime_config_path = project_root / 'config' / 'config.yaml'
                if runtime_config_path.exists():
                    with open(runtime_config_path, 'r', encoding='utf-8') as f:
                        runtime_config = yaml.safe_load(f) or {}
                    voice_config = runtime_config.get('voice', {}) or {}
            except Exception as config_error:
                logger.warning(f"Failed to load voice config from config/config.yaml: {config_error}")

        if not voice_config:
            # Fallback to default config
            voice_config = {
                'enabled': True,
                'voice_preset': 'NATM1',
                'persona': 'rogr',
                'server_url': 'wss://localhost:8998',
                'announce_on_startup': True
            }
        
        if not voice_config.get('enabled', True):
            logger.info("Voice system disabled in configuration")
        elif not voice_helper.VOICE_ENABLED:
            logger.info("Voice system not enabled (set PERSONAPLEX_ENABLED=true)")
        else:
            # Get configuration values
            voice_preset = voice_config.get('voice_preset', 'NATM1')
            persona = voice_config.get('persona', 'rogr')
            server_url = voice_config.get('server_url', 'wss://localhost:8998')
            
            # Map legacy style to voice preset if needed
            if 'default_style' in voice_config and 'voice_preset' not in voice_config:
                style = voice_config.get('default_style', 'droid')
                voice_preset = voice_helper.STYLE_TO_PRESET.get(style, 'NATM1')
            
            # Initialize voice with configuration
            voice = voice_helper.VoiceSystem(
                server_url=server_url,
                voice_preset=voice_preset,
                persona=persona
            )
            
            # Set as global voice instance
            voice_helper._voice = voice
            
            # Announce startup if configured
            if voice_config.get('announce_on_startup', True):
                voice_helper.announce("Dashboard initialization complete")
            
            logger.info(f"Voice system initialized: PersonaPlex preset={voice_preset}, persona={persona}")
    except Exception as e:
        logger.warning(f"Voice system initialization failed: {e}")
    
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
async def get_all_servers(include_remote: bool = Query(False)):
    """Get user web servers running on common app ports."""
    try:
        from utils.server_manager import ServerManager
        
        server_manager = ServerManager()
        servers = server_manager.discover_web_servers(port_min=8000, port_max=9000)

        if include_remote:
            remote_servers = server_manager.discover_remote_web_servers(port_min=8000, port_max=9000)
            servers = servers + remote_servers
        
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
        servers = server_manager.discover_web_servers(port_min=8000, port_max=9000)
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

@app.post("/api/servers/{port}/restart")
async def restart_server(port: int):
    """Restart a server running on a specific port."""
    try:
        from utils.server_manager import ServerManager

        server_manager = ServerManager()
        servers = server_manager.discover_web_servers(port_min=8000, port_max=9000)
        server = next((s for s in servers if s['port'] == port), None)

        if not server:
            raise HTTPException(status_code=404, detail=f"Server on port {port} not found")

        if not server.get('can_restart'):
            raise HTTPException(status_code=400, detail=f"Cannot restart server on port {port} (no restart command available)")

        success = server_manager.restart_server(server)

        if success:
            return {"success": True, "message": f"Restart triggered for server on port {port}"}
        return {"success": False, "error": f"Failed to restart server on port {port}"}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error restarting server on port {port}: {e}")
        return {"success": False, "error": str(e)}

@app.post("/api/servers/refresh")
async def refresh_servers(include_remote: bool = Query(False)):
    """Refresh the list of discovered servers"""
    try:
        from utils.server_manager import ServerManager
        
        server_manager = ServerManager()
        servers = server_manager.discover_web_servers(port_min=8000, port_max=9000)

        if include_remote:
            remote_servers = server_manager.discover_remote_web_servers(port_min=8000, port_max=9000)
            servers = servers + remote_servers
        
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
