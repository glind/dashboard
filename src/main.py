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
    AI_ASSISTANT_AVAILABLE = True
except ImportError as e:
    print(f"Note: Could not import AI Assistant modules: {e}")
    AI_ASSISTANT_AVAILABLE = False

# Set up logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Simple Personal Dashboard")


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
                username = github_creds.get('username', 'glind')
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
    
    # Serve the modern template
    try:
        # Get the src directory path
        src_dir = Path(__file__).parent
        template_path = src_dir / "templates" / "dashboard_modern.html"
        if template_path.exists():
            with open(template_path, 'r') as f:
                return HTMLResponse(content=f.read())
    except Exception as e:
        logger.error(f"Error loading modern template: {e}")
    
    # Fallback to old embedded HTML if template fails
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Personal Dashboard</title>
    <link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📊</text></svg>">
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="/static/dashboard.css">
    <style>
        /* Custom scrollbar styles */
        .widget-content::-webkit-scrollbar {
            width: 8px;
        }
        .widget-content::-webkit-scrollbar-track {
            background: rgba(255,255,255,0.1);
            border-radius: 4px;
        }
        .widget-content::-webkit-scrollbar-thumb {
            background: rgba(255,255,255,0.3);
            border-radius: 4px;
        }
        .widget-content::-webkit-scrollbar-thumb:hover {
            background: rgba(255,255,255,0.5);
        }
        
        /* Calendar-specific styles */
        .calendar-day-divider {
            margin: 15px 0;
            padding: 8px 12px;
            background: rgba(255,255,255,0.15);
            border-radius: 8px;
            border-left: 4px solid #4fc3f7;
            font-weight: bold;
            font-size: 0.9em;
            color: #4fc3f7;
            position: sticky;
            top: 0;
            z-index: 10;
            backdrop-filter: blur(5px);
        }
        
        .calendar-current-time {
            position: relative;
            margin: 5px 0;
            height: 1px;
            background: linear-gradient(to right, transparent, #ff6b6b, transparent);
            box-shadow: 0 0 8px rgba(255, 107, 107, 0.6);
            animation: pulse 2s infinite;
        }
        
        .calendar-current-time::before {
            content: 'NOW';
            position: absolute;
            left: 50%;
            top: -8px;
            transform: translateX(-50%);
            background: #ff6b6b;
            color: white;
            padding: 2px 6px;
            border-radius: 3px;
            font-size: 0.7em;
            font-weight: bold;
            box-shadow: 0 2px 4px rgba(0,0,0,0.3);
        }
        
        .calendar-current-time::after {
            content: '';
            position: absolute;
            left: 50%;
            top: -3px;
            transform: translateX(-50%);
            width: 8px;
            height: 8px;
            background: #ff6b6b;
            border-radius: 50%;
            box-shadow: 0 0 10px rgba(255, 107, 107, 0.8);
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.7; }
        }
        
        .calendar-event {
            margin: 8px 0;
            padding: 0;
            border: none;
            background: none;
        }
        
        .calendar-event.past-event {
            opacity: 0.6;
        }
        
        .calendar-event.current-event {
            background: rgba(255, 107, 107, 0.1);
            border-left: 3px solid #ff6b6b;
            border-radius: 5px;
            padding: 8px;
            margin: 8px 0;
        }
        
        .calendar-event.upcoming-event {
            background: rgba(76, 195, 247, 0.1);
            border-left: 3px solid #4fc3f7;
            border-radius: 5px;
            padding: 8px;
            margin: 8px 0;
        }
        
        /* Essential utility styles */
        .loading { text-align: center; opacity: 0.7; }
        .error { color: #ff6b6b; text-align: center; }
        
        /* Item styles with proper Tailwind approach */
        .item { 
            background: rgba(255,255,255,0.1);
            margin: 8px 0;
            padding: 12px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.2s ease;
            border: 1px solid rgba(255,255,255,0.1);
        }
        
        .item:hover {
            background: rgba(255, 255, 255, 0.15);
            transform: translateY(-1px);
            border-color: rgba(255,255,255,0.2);
        }
        
        .item-title { 
            font-weight: bold; 
            margin-bottom: 5px; 
            color: white;
        }
        
        .item-meta { 
            font-size: 0.9em; 
            opacity: 0.8; 
            color: #e5e7eb;
        }
        
        .item-summary { 
            cursor: default; 
            margin-bottom: 12px;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.05);
        }
        
        .item-summary:hover { 
            background: rgba(255,255,255,0.05);
            transform: none; 
            border-color: rgba(255,255,255,0.05);
        }
        
        /* Widget admin gear positioning */
        .widget-admin-gear {
            position: absolute;
            top: 15px;
            right: 50px;
            background: rgba(255,255,255,0.2);
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            width: 30px;
            height: 30px;
            color: white;
            cursor: pointer;
            font-size: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0.7;
            transition: all 0.3s ease;
        }
        
        .widget-admin-gear:hover {
            opacity: 1;
            background: rgba(255,255,255,0.3);
        }
        
        /* Modal Styles */
        .modal {
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(5px);
        }
        
        .modal-content {
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            margin: 5% auto;
            padding: 0;
            border: none;
            border-radius: 15px;
            width: 90%;
            max-width: 700px;
            max-height: 80vh;
            overflow: hidden;
            box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
            animation: modalAppear 0.3s ease-out;
        }
        
        @keyframes modalAppear {
            from { opacity: 0; transform: translateY(-50px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        .modal-header {
            padding: 20px 25px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.2);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .modal-header h3 {
            margin: 0;
            font-size: 1.4em;
        }
        
        .close-btn {
            font-size: 28px;
            font-weight: bold;
            cursor: pointer;
            color: #fff;
            opacity: 0.7;
            transition: opacity 0.2s;
        }
        
        .close-btn:hover {
            opacity: 1;
        }
        
        .modal-body {
            padding: 25px;
            max-height: 60vh;
            overflow-y: auto;
        }
        
        .modal-navigation {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding: 10px 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }
        
        .modal-navigation button {
            background: rgba(255, 255, 255, 0.2);
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            color: white;
            cursor: pointer;
            transition: all 0.2s ease;
        }
        
        .modal-navigation button:hover:not(:disabled) {
            background: rgba(255, 255, 255, 0.3);
            transform: translateY(-1px);
        }
        
        .modal-navigation button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }
        
        #item-counter {
            font-size: 0.9em;
            opacity: 0.8;
        }
        
        #modal-content {
            line-height: 1.6;
        }
        
        #modal-content a {
            color: #4fc3f7;
            text-decoration: none;
        }
        
        #modal-content a:hover {
            text-decoration: underline;
        }
        
        .detail-section {
            margin-bottom: 20px;
        }
        
        .detail-section h4 {
            color: #4fc3f7;
            margin-bottom: 10px;
            font-size: 1.1em;
        }
        
        .detail-meta {
            background: rgba(255, 255, 255, 0.1);
            padding: 15px;
            border-radius: 10px;
            margin: 15px 0;
        }
        
        .detail-meta .meta-item {
            margin-bottom: 8px;
            display: flex;
            justify-content: space-between;
        }
        
        .detail-meta .meta-item:last-child {
            margin-bottom: 0;
        }
        
        .meta-label {
            font-weight: 600;
            opacity: 0.9;
        }
        
        .meta-value {
            opacity: 0.8;
        }
        
        /* Admin Panel Styles */
        .admin-panel {
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(5px);
            z-index: 2000;
        }
        
        .admin-content {
            position: relative;
            background: linear-gradient(135deg, #2a5298 0%, #1e3c72 100%);
            margin: 50px auto;
            padding: 30px;
            border-radius: 15px;
            max-width: 800px;
            max-height: 80vh;
            overflow-y: auto;
            border: 2px solid rgba(255,255,255,0.3);
        }
        
        .admin-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 25px;
        }
        
        .admin-close {
            background: none;
            border: none;
            color: white;
            font-size: 24px;
            cursor: pointer;
            opacity: 0.7;
            transition: opacity 0.3s ease;
        }
        
        .admin-close:hover {
            opacity: 1;
        }
        
        .admin-section {
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 20px;
            margin-bottom: 20px;
            border: 1px solid rgba(255,255,255,0.2);
        }
        
        #widget-admin {
            background: rgba(30, 30, 30, 0.95);
            border: 2px solid #4fc3f7;
            border-radius: 15px;
            padding: 20px;
            margin: 20px auto;
            min-height: 200px;
            max-width: 800px;
            width: 90%;
            position: fixed;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 10000;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }
        
        #widget-admin::before {
            content: '';
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            z-index: -1;
        }
        
        .admin-section h3 {
            margin-bottom: 15px;
            color: #4fc3f7;
        }
        
        .widget-toggle {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px 0;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }
        
        .widget-toggle:last-child {
            border-bottom: none;
        }
        
        .toggle-switch {
            position: relative;
            display: inline-block;
            width: 50px;
            height: 25px;
        }
        
        .toggle-switch input {
            opacity: 0;
            width: 0;
            height: 0;
        }
        
        .toggle-slider {
            position: absolute;
            cursor: pointer;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            background-color: rgba(255,255,255,0.3);
            transition: 0.4s;
            border-radius: 25px;
        }
        
        .toggle-slider:before {
            position: absolute;
            content: "";
            height: 19px;
            width: 19px;
            left: 3px;
            bottom: 3px;
            background-color: white;
            transition: 0.4s;
            border-radius: 50%;
        }
        
        input:checked + .toggle-slider {
            background-color: #4CAF50;
        }
        
        input:checked + .toggle-slider:before {
            transform: translateX(25px);
        }
        
        .widget-admin-gear {
            position: absolute;
            top: 15px;
            right: 50px;
            background: rgba(255,255,255,0.2);
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 50%;
            width: 30px;
            height: 30px;
            color: white;
            cursor: pointer;
            font-size: 12px;
            display: flex;
            align-items: center;
            justify-content: center;
            opacity: 0.7;
            transition: all 0.3s ease;
        }
        
        .widget-admin-gear:hover {
            opacity: 1;
            background: rgba(255,255,255,0.3);
        }
        
        .admin-form {
            margin-top: 15px;
        }
        
        .admin-input {
            width: 100%;
            padding: 10px;
            margin: 8px 0;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 5px;
            color: white;
            font-size: 14px;
        }
        
        .admin-input::placeholder {
            color: rgba(255,255,255,0.6);
        }
        
        .admin-btn {
            background: #4CAF50;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 5px;
            cursor: pointer;
            margin: 5px;
            transition: background 0.3s ease;
        }
        
        .admin-btn:hover {
            background: #45a049;
        }
        
        .admin-btn.danger {
            background: #f44336;
        }
        
        .admin-btn.danger:hover {
            background: #da190b;
        }
        
        .tag-list {
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            margin: 10px 0;
        }
        
        .tag-item {
            background: rgba(255,255,255,0.2);
            padding: 4px 8px;
            border-radius: 15px;
            font-size: 12px;
            display: flex;
            align-items: center;
            gap: 5px;
        }
        
        .tag-remove {
            cursor: pointer;
            color: #ff6b6b;
            font-weight: bold;
        }
        
        /* AI Chat Styles */
        .ai-chat-container {
            display: flex;
            flex-direction: column;
            height: 100%;
        }
        
        .chat-messages {
            flex: 1;
            overflow-y: auto;
            padding: 10px 0;
            margin-bottom: 10px;
        }
        
        .chat-message {
            margin: 10px 0;
            padding: 10px;
            border-radius: 12px;
            max-width: 85%;
            word-wrap: break-word;
        }
        
        .chat-message.user {
            background: rgba(74, 144, 226, 0.3);
            margin-left: auto;
            text-align: right;
        }
        
        .chat-message.assistant {
            background: rgba(255, 255, 255, 0.15);
            margin-right: auto;
        }
        
        .chat-message.system {
            background: rgba(255, 193, 7, 0.2);
            text-align: center;
            font-style: italic;
            max-width: 100%;
        }
        
        .chat-message-time {
            font-size: 0.7em;
            opacity: 0.6;
            margin-top: 5px;
        }
        
        .chat-input-container {
            flex-shrink: 0;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            padding: 10px;
        }
        
        .chat-provider-selector {
            margin-bottom: 8px;
        }
        
        .chat-provider-selector select {
            width: 100%;
            padding: 6px;
            border: none;
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            font-size: 0.9em;
        }
        
        .chat-provider-selector select option {
            background: #2a5298;
            color: white;
        }
        
        .chat-input-wrapper {
            display: flex;
            gap: 8px;
        }
        
        .chat-input-wrapper input {
            flex: 1;
            padding: 10px;
            border: none;
            border-radius: 6px;
            background: rgba(255, 255, 255, 0.2);
            color: white;
            font-size: 0.9em;
        }
        
        .chat-input-wrapper input::placeholder {
            color: rgba(255, 255, 255, 0.7);
        }
        
        .chat-input-wrapper button {
            padding: 10px 15px;
            border: none;
            border-radius: 6px;
            background: #4CAF50;
            color: white;
            cursor: pointer;
            font-size: 0.9em;
            transition: background 0.3s;
        }
        
        .chat-input-wrapper button:hover {
            background: #45a049;
        }
        
        .chat-input-wrapper button:disabled {
            background: rgba(255, 255, 255, 0.3);
            cursor: not-allowed;
        }
        
        .typing-indicator {
            display: none;
            padding: 10px;
            font-style: italic;
            opacity: 0.7;
            text-align: center;
        }

        /* ===================================================================
           SERVER CONTROL PANEL STYLES
           ================================================================= */
        
        .server-card {
            transition: all 0.3s ease;
        }
        
        .server-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        }
        
        .server-status-indicator {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            display: inline-block;
            position: relative;
        }
        
        .status-running {
            background: #10b981;
            animation: pulse-green 2s infinite;
        }
        
        .status-stopped {
            background: #ef4444;
            animation: pulse-red 2s infinite;
        }
        
        @keyframes pulse-green {
            0%, 100% {
                opacity: 1;
                transform: scale(1);
                box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.4);
            }
            50% {
                opacity: 0.8;
                transform: scale(1.1);
                box-shadow: 0 0 0 8px rgba(16, 185, 129, 0);
            }
        }
        
        @keyframes pulse-red {
            0%, 100% {
                opacity: 1;
                transform: scale(1);
                box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.4);
            }
            50% {
                opacity: 0.8;
                transform: scale(1.1);
                box-shadow: 0 0 0 8px rgba(239, 68, 68, 0);
            }
        }
        
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        
        .server-toggle-btn {
            transition: all 0.2s ease;
        }
        
        .server-toggle-btn:hover {
            transform: scale(1.05);
        }
        
        .server-toggle-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none !important;
        }
        
        #servers-container {
            max-height: 400px;
            overflow-y: auto;
        }
        
        #servers-container::-webkit-scrollbar {
            width: 6px;
        }
        
        #servers-container::-webkit-scrollbar-track {
            background: rgba(255,255,255,0.1);
            border-radius: 3px;
        }
        
        #servers-container::-webkit-scrollbar-thumb {
            background: rgba(255,255,255,0.3);
            border-radius: 3px;
        }
        
        #servers-container::-webkit-scrollbar-thumb:hover {
            background: rgba(255,255,255,0.5);
        }
    </style>
</head>
<body class="min-h-screen bg-gradient-to-br from-blue-900 via-blue-800 to-blue-900 text-white p-5 font-sans">
    <div class="max-w-7xl mx-auto">
        <div class="flex justify-between items-center mb-8">
            <div class="flex items-center space-x-4">
                <button onclick="window.location.href='/leads'" class="
                    bg-green-500 bg-opacity-80
                    border border-green-400 border-opacity-50
                    rounded-lg
                    px-4 py-2
                    text-white
                    cursor-pointer
                    text-sm font-semibold
                    transition-all duration-300
                    hover:bg-opacity-100 hover:scale-105
                    flex items-center space-x-2
                " title="AI-Powered Lead Generation Dashboard">
                    <span>🎯</span>
                    <span>Lead Generation</span>
                </button>
            </div>
            <h1 class="flex-1 text-center text-4xl font-bold m-0">📊 Personal Dashboard</h1>
            <div class="flex items-center space-x-4">
                <button id="admin-btn" onclick="openAdminPanel()" class="
                    bg-white bg-opacity-20 
                    border border-white border-opacity-30 
                    rounded-full 
                    w-10 h-10 
                    text-white 
                    cursor-pointer 
                    text-base
                    flex items-center justify-center
                    transition-all duration-300
                    hover:bg-opacity-30
                " onmouseover="this.style.background='rgba(255,255,255,0.3)'" onmouseout="this.style.background='rgba(255,255,255,0.2)'">
                    ⚙️
                </button>
            </div>
        </div>
        
        <!-- Server Control Panel -->
        <div id="server-control-panel" class="bg-white bg-opacity-10 rounded-xl p-4 backdrop-blur-sm border border-white border-opacity-20 mb-6">
            <div class="flex items-center justify-between mb-4">
                <h2 class="text-lg text-white font-semibold flex items-center gap-2">
                    🖥️ Python Web Servers
                </h2>
                <div class="flex items-center gap-2">
                    <span id="server-count" class="text-xs px-2 py-1 rounded bg-blue-600 text-white">0 servers</span>
                    <button onclick="refreshServers()" 
                            class="bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded text-xs flex items-center gap-1">
                        <span id="refresh-servers-icon">🔄</span> Refresh
                    </button>
                </div>
            </div>
            
            <div id="servers-container">
                <!-- Server cards will be populated here -->
                <div class="text-gray-300 text-sm flex items-center justify-center py-8">
                    <span class="animate-spin mr-2">⏳</span> Scanning for Python web servers...
                </div>
            </div>
            
            <!-- No servers message (hidden by default) -->
            <div id="no-servers-message" class="hidden text-center py-8 text-gray-300">
                <div class="text-4xl mb-2">🔍</div>
                <div class="text-lg mb-2">No Python web servers found</div>
                <div class="text-sm opacity-75">Start a Python web server and click refresh to see it here</div>
            </div>
        </div>
        
        <!-- Top Mini Widgets -->
        <div class="flex gap-5 mb-8 justify-center flex-wrap">
            <div class="bg-white bg-opacity-15 rounded-xl p-4 backdrop-blur-sm border border-white border-opacity-30 min-w-60 text-center">
                <div class="flex justify-between items-center mb-2">
                    <h3 class="text-lg text-white m-0">😄 Daily Joke</h3>
                    <div class="flex items-center gap-1">
                        <span id="jokes-status" class="text-xs px-2 py-1 rounded bg-gray-600 text-white">⚫</span>
                        <button class="btn-small bg-blue-500 hover:bg-blue-600 text-white px-2 py-1 rounded text-xs" 
                                onclick="refreshWidget('jokes')" title="New Joke">
                            🔄
                        </button>
                    </div>
                </div>
                <div id="joke-content" class="text-sm opacity-90 loading">Loading...</div>
            </div>
            
            <div class="bg-white bg-opacity-15 rounded-xl p-4 backdrop-blur-sm border border-white border-opacity-30 min-w-80 text-center">
                <div class="flex justify-between items-center mb-2">
                    <h3 class="text-lg text-white m-0">🌤️ Weather</h3>
                    <div class="flex items-center gap-2">
                        <span id="weather-status" class="text-xs px-2 py-1 rounded bg-gray-600 text-white">⚫</span>
                        <button class="btn-small bg-blue-500 hover:bg-blue-600 text-white px-2 py-1 rounded text-xs" 
                                onclick="refreshWidget('weather')" title="Refresh Weather">
                            🔄
                        </button>
                    </div>
                </div>
                <div id="weather-content" class="text-sm opacity-90 loading">Loading...</div>
            </div>

            <div class="bg-white bg-opacity-15 rounded-xl p-4 backdrop-blur-sm border border-white border-opacity-30 min-w-96 flex flex-col">
                <h3 class="mb-2 text-lg text-white text-center">🤖 AI Assistant 
                    <span class="widget-admin-gear" onclick="openWidgetAdmin('ai')" title="Configure AI Assistant">⚙️</span>
                    <button class="ml-2 px-2 py-1 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded" onclick="refreshAISummary()" title="Refresh AI Summary">🔄</button>
                </h3>
                <div class="flex-1 flex flex-col ai-chat-container">
                    <div id="ai-summary-content" class="text-sm opacity-90 mb-3 p-2 bg-white bg-opacity-10 rounded-lg min-h-16 loading">Loading AI summary...</div>
                    <div id="ai-chat-messages" class="chat-messages flex-1 max-h-32 overflow-y-auto"></div>
                    <div class="chat-input-container mt-2">
                        <div class="chat-provider-selector">
                            <select id="ai-provider-select">
                                <option value="">Loading providers...</option>
                            </select>
                        </div>
                        <div class="chat-input-wrapper">
                            <input type="text" id="ai-chat-input" placeholder="Ask your AI assistant..." onkeypress="handleChatKeyPress(event)">
                            <button id="ai-chat-send" onclick="sendChatMessage()">Send</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            <div class="bg-white bg-opacity-10 rounded-2xl p-5 backdrop-blur-sm border border-white border-opacity-20 h-[600px] flex flex-col relative">
                <button class="widget-admin-gear" onclick="openWidgetAdmin('calendar')" title="Configure Calendar">⚙️</button>
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-white shrink-0 m-0">📅 Calendar Events</h2>
                    <div class="flex items-center gap-2">
                        <span id="calendar-status" class="text-xs px-2 py-1 rounded bg-gray-600 text-white">⚫ Unknown</span>
                        <button class="btn-small bg-blue-500 hover:bg-blue-600 text-white px-2 py-1 rounded text-xs" 
                                onclick="refreshWidget('calendar')" title="Refresh Calendar Data">
                            🔄
                        </button>
                    </div>
                </div>
                <div class="flex-1 overflow-y-auto overflow-x-hidden">
                    <div id="calendar-content" class="loading">Loading...</div>
                </div>
            </div>
            
            <div class="bg-white bg-opacity-10 rounded-2xl p-5 backdrop-blur-sm border border-white border-opacity-20 h-[600px] flex flex-col relative">
                <button class="widget-admin-gear" onclick="openWidgetAdmin('email')" title="Configure Email">⚙️</button>
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-white shrink-0 m-0">📧 Email Summary</h2>
                    <div class="flex gap-2">
                        <button class="btn-small bg-blue-500 hover:bg-blue-600 text-white px-3 py-1 rounded text-sm" 
                                onclick="analyzeEmailTodos()" title="Analyze 6 months of emails for todos">
                            🔍 Analyze Todos
                        </button>
                        <button class="btn-small bg-green-500 hover:bg-green-600 text-white px-3 py-1 rounded text-sm" 
                                onclick="syncEmailToTickTick()" title="Sync email todos to TickTick">
                            📋 Sync to TickTick
                        </button>
                    </div>
                </div>
                <div class="flex-1 overflow-y-auto overflow-x-hidden">
                    <div id="email-content" class="loading">Loading...</div>
                    <div id="email-todo-analysis" style="display: none;" class="mt-4 p-4 bg-blue-900 bg-opacity-30 rounded-lg border border-blue-500">
                        <h3 class="text-white mb-2">📝 Email Todo Analysis</h3>
                        <div id="email-todo-results"></div>
                    </div>
                </div>
            </div>
            
            <div class="bg-white bg-opacity-10 rounded-2xl p-5 backdrop-blur-sm border border-white border-opacity-20 h-[600px] flex flex-col relative">
                <button class="widget-admin-gear" onclick="openWidgetAdmin('github')" title="Configure GitHub">⚙️</button>
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-white shrink-0 m-0">🐙 GitHub Activity</h2>
                    <div class="flex items-center gap-2">
                        <span id="github-status" class="text-xs px-2 py-1 rounded bg-gray-600 text-white">⚫ Unknown</span>
                        <button class="btn-small bg-blue-500 hover:bg-blue-600 text-white px-2 py-1 rounded text-xs" 
                                onclick="refreshWidget('github')" title="Refresh GitHub Data">
                            🔄
                        </button>
                    </div>
                </div>
                <div class="flex-1 overflow-y-auto overflow-x-hidden">
                    <div id="github-content" class="loading">Loading...</div>
                </div>
            </div>
            
            <div class="bg-white bg-opacity-10 rounded-2xl p-5 backdrop-blur-sm border border-white border-opacity-20 h-[600px] flex flex-col relative">
                <button class="widget-admin-gear" onclick="openWidgetAdmin('tasks')" title="Configure Tasks">⚙️</button>
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-white shrink-0 m-0">✅ Task Management</h2>
                    <div class="flex items-center gap-2">
                        <span id="tasks-status" class="text-xs px-2 py-1 rounded bg-gray-600 text-white">⚫ Unknown</span>
                        <button onclick="refreshWidget('tasks')" class="px-2 py-1 text-xs bg-blue-500 hover:bg-blue-600 text-white rounded" title="Refresh Tasks">🔄</button>
                        <button onclick="showCreateTaskModal()" class="px-2 py-1 text-xs bg-green-600 hover:bg-green-700 text-white rounded" title="Create New Task">+ New</button>
                        <button onclick="syncWithTickTick('both')" class="px-2 py-1 text-xs bg-purple-600 hover:bg-purple-700 text-white rounded" title="Sync with TickTick">🔄 Sync</button>
                    </div>
                </div>
                
                <!-- Task Statistics -->
                <div id="task-stats" class="mb-4"></div>
                
                <!-- Task Filters -->
                <div class="mb-4 space-y-2">
                    <!-- Status Filters -->
                    <div class="filter-group">
                        <label class="text-white text-xs font-medium block mb-1">Status:</label>
                        <div class="flex gap-1 flex-wrap">
                            <button class="task-filter-btn bg-blue-600 text-white px-2 py-1 text-xs rounded" data-filter-type="status" data-filter="all">All</button>
                            <button class="task-filter-btn bg-gray-200 text-gray-700 px-2 py-1 text-xs rounded" data-filter-type="status" data-filter="pending">Pending</button>
                            <button class="task-filter-btn bg-gray-200 text-gray-700 px-2 py-1 text-xs rounded" data-filter-type="status" data-filter="in_progress">In Progress</button>
                            <button class="task-filter-btn bg-gray-200 text-gray-700 px-2 py-1 text-xs rounded" data-filter-type="status" data-filter="completed">Completed</button>
                        </div>
                    </div>
                    
                    <!-- Priority Filters -->
                    <div class="filter-group">
                        <label class="text-white text-xs font-medium block mb-1">Priority:</label>
                        <div class="flex gap-1 flex-wrap">
                            <button class="task-filter-btn bg-blue-600 text-white px-2 py-1 text-xs rounded" data-filter-type="priority" data-filter="all">All</button>
                            <button class="task-filter-btn bg-gray-200 text-gray-700 px-2 py-1 text-xs rounded" data-filter-type="priority" data-filter="high">High</button>
                            <button class="task-filter-btn bg-gray-200 text-gray-700 px-2 py-1 text-xs rounded" data-filter-type="priority" data-filter="medium">Medium</button>
                            <button class="task-filter-btn bg-gray-200 text-gray-700 px-2 py-1 text-xs rounded" data-filter-type="priority" data-filter="low">Low</button>
                        </div>
                    </div>
                    
                    <!-- Category Filters -->
                    <div class="filter-group">
                        <label class="text-white text-xs font-medium block mb-1">Category:</label>
                        <div class="flex gap-1 flex-wrap">
                            <button class="task-filter-btn bg-blue-600 text-white px-2 py-1 text-xs rounded" data-filter-type="category" data-filter="all">All</button>
                            <button class="task-filter-btn bg-gray-200 text-gray-700 px-2 py-1 text-xs rounded" data-filter-type="category" data-filter="email">Email</button>
                            <button class="task-filter-btn bg-gray-200 text-gray-700 px-2 py-1 text-xs rounded" data-filter-type="category" data-filter="manual">Manual</button>
                            <button class="task-filter-btn bg-gray-200 text-gray-700 px-2 py-1 text-xs rounded" data-filter-type="category" data-filter="ticktick">TickTick</button>
                        </div>
                    </div>
                    
                    <!-- Include Completed Checkbox -->
                    <div class="flex items-center">
                        <input type="checkbox" id="include-completed-tasks" class="mr-2">
                        <label for="include-completed-tasks" class="text-white text-xs">Include completed tasks</label>
                    </div>
                </div>
                
                <div class="flex-1 overflow-y-auto overflow-x-hidden">
                    <div id="tasks-container" class="space-y-3">Loading...</div>
                </div>
            </div>
            
            <div class="bg-white bg-opacity-10 rounded-2xl p-5 backdrop-blur-sm border border-white border-opacity-20 h-[600px] flex flex-col relative">
                <button class="widget-admin-gear" onclick="openWidgetAdmin('notes')" title="Configure Notes">⚙️</button>
                <div class="flex justify-between items-center mb-4">
                    <h2 class="text-white shrink-0 m-0">📝 Notes & Knowledge</h2>
                    <div class="flex gap-2">
                        <button onclick="testNotesConnections()" class="px-2 py-1 text-xs bg-blue-600 hover:bg-blue-700 text-white rounded" title="Test Connections">🔍 Test</button>
                        <button onclick="generateTasksFromNotes()" class="px-2 py-1 text-xs bg-purple-600 hover:bg-purple-700 text-white rounded" title="Generate Tasks from Notes">📋 Extract Tasks</button>
                    </div>
                </div>
                
                <!-- Connection Status -->
                <div id="notes-connections" class="mb-3 text-xs space-y-1">
                    <div id="obsidian-status" class="flex items-center">
                        <span class="w-3 h-3 rounded-full bg-gray-500 mr-2" id="obsidian-indicator"></span>
                        <span>Obsidian: <span id="obsidian-status-text">Unknown</span></span>
                    </div>
                    <div id="gdrive-status" class="flex items-center">
                        <span class="w-3 h-3 rounded-full bg-gray-500 mr-2" id="gdrive-indicator"></span>
                        <span>Google Drive: <span id="gdrive-status-text">Unknown</span></span>
                    </div>
                </div>
                
                <!-- Notes Statistics -->
                <div id="notes-stats" class="mb-4"></div>
                
                <!-- Note Filters -->
                <div class="mb-4 space-y-2">
                    <div class="filter-group">
                        <label class="text-white text-xs font-medium block mb-1">Source:</label>
                        <div class="flex gap-1 flex-wrap">
                            <button class="notes-filter-btn bg-blue-600 text-white px-2 py-1 text-xs rounded" data-filter="all">All</button>
                            <button class="notes-filter-btn bg-gray-200 text-gray-700 px-2 py-1 text-xs rounded" data-filter="obsidian">Obsidian</button>
                            <button class="notes-filter-btn bg-gray-200 text-gray-700 px-2 py-1 text-xs rounded" data-filter="google_drive">Google Drive</button>
                        </div>
                    </div>
                    
                    <div class="flex items-center">
                        <input type="checkbox" id="notes-with-todos" class="mr-2">
                        <label for="notes-with-todos" class="text-white text-xs">Only notes with TODOs</label>
                    </div>
                </div>
                
                <div class="flex-1 overflow-y-auto overflow-x-hidden">
                    <div id="notes-content" class="loading">Loading...</div>
                </div>
            </div>
            
            <div class="bg-white bg-opacity-10 rounded-2xl p-5 backdrop-blur-sm border border-white border-opacity-20 h-[600px] flex flex-col relative">
                <button class="widget-admin-gear" onclick="openWidgetAdmin('news')" title="Configure News">⚙️</button>
                <h2 class="mb-4 text-white shrink-0">📰 News Headlines</h2>
                <div class="flex flex-wrap gap-1 mb-3 shrink-0">
                    <button onclick="filterNews('all')" class="bg-white bg-opacity-20 text-white border border-white border-opacity-30 rounded-2xl px-3 py-1 cursor-pointer text-xs transition-all duration-300 ease hover:bg-opacity-30 hover:border-opacity-50 filter-btn active" id="filter-all">All</button>
                    <button onclick="filterNews('tech')" class="bg-white bg-opacity-20 text-white border border-white border-opacity-30 rounded-2xl px-3 py-1 cursor-pointer text-xs transition-all duration-300 ease hover:bg-opacity-30 hover:border-opacity-50 filter-btn" id="filter-tech">Tech/AI</button>
                    <button onclick="filterNews('oregon')" class="bg-white bg-opacity-20 text-white border border-white border-opacity-30 rounded-2xl px-3 py-1 cursor-pointer text-xs transition-all duration-300 ease hover:bg-opacity-30 hover:border-opacity-50 filter-btn" id="filter-oregon">Oregon State</button>
                    <button onclick="filterNews('timbers')" class="bg-white bg-opacity-20 text-white border border-white border-opacity-30 rounded-2xl px-3 py-1 cursor-pointer text-xs transition-all duration-300 ease hover:bg-opacity-30 hover:border-opacity-50 filter-btn" id="filter-timbers">Timbers</button>
                    <button onclick="filterNews('starwars')" class="bg-white bg-opacity-20 text-white border border-white border-opacity-30 rounded-2xl px-3 py-1 cursor-pointer text-xs transition-all duration-300 ease hover:bg-opacity-30 hover:border-opacity-50 filter-btn" id="filter-starwars">Star Wars</button>
                    <button onclick="filterNews('startrek')" class="bg-white bg-opacity-20 text-white border border-white border-opacity-30 rounded-2xl px-3 py-1 cursor-pointer text-xs transition-all duration-300 ease hover:bg-opacity-30 hover:border-opacity-50 filter-btn" id="filter-startrek">Star Trek</button>
                </div>
                <div class="flex-1 overflow-y-auto overflow-x-hidden">
                    <div id="news-content" class="loading">Loading...</div>
                </div>
            </div>
            
            <div class="bg-white bg-opacity-10 rounded-2xl p-5 backdrop-blur-sm border border-white border-opacity-20 h-[600px] flex flex-col relative">
                <button class="widget-admin-gear" onclick="openWidgetAdmin('music')" title="Configure Music">⚙️</button>
                <h2 class="mb-4 text-white shrink-0">🎵 Music Trends</h2>
                <div class="flex-1 overflow-y-auto overflow-x-hidden">
                    <div id="music-content" class="loading">Loading...</div>
                </div>
            </div>
            
            <div class="bg-white bg-opacity-10 rounded-2xl p-5 backdrop-blur-sm border border-white border-opacity-20 h-[600px] flex flex-col relative">
                <button class="widget-admin-gear" onclick="openWidgetAdmin('vanity')" title="Configure Vanity Alerts">⚙️</button>
                <h2 class="mb-4 text-white shrink-0">👁️ Vanity Alerts</h2>
                <div class="flex-1 overflow-y-auto overflow-x-hidden">
                    <div id="vanity-content" class="loading">Loading...</div>
                </div>
            </div>
            
            <div class="bg-white bg-opacity-10 rounded-2xl p-5 backdrop-blur-sm border border-white border-opacity-20 h-[600px] flex flex-col relative">
                <h2 class="mb-4 text-white shrink-0">❤️ Liked Items</h2>
                <div class="flex-1 overflow-y-auto overflow-x-hidden">
                    <div id="liked-items-content" class="loading">Loading...</div>
                </div>
            </div>
            
            <!-- Dashboard Management Widget -->
            <div class="bg-white bg-opacity-10 rounded-2xl p-5 backdrop-blur-sm border border-white border-opacity-20 h-[600px] flex flex-col relative">
                <h2 class="mb-4 text-white shrink-0">🎯 Marketing Dashboards</h2>
                <div class="flex-1 overflow-y-auto overflow-x-hidden">
                    <div id="dashboard-overview"></div>
                    <div id="dashboards-grid" class="grid grid-cols-1 gap-3 mb-4"></div>
                    
                    <!-- Server Discovery Section -->
                    <div class="mt-6 pt-4 border-t border-white border-opacity-20">
                        <div class="flex items-center justify-between mb-3">
                            <h3 class="text-white text-sm font-semibold flex items-center gap-2">
                                🔍 Discovered Python Servers
                            </h3>
                            <button onclick="refreshDiscoveredServers()" 
                                    class="bg-blue-500 hover:bg-blue-600 text-white px-2 py-1 rounded text-xs flex items-center gap-1">
                                <span id="refresh-discovered-icon">🔄</span> Scan
                            </button>
                        </div>
                        <div id="discovered-servers-container" class="space-y-2">
                            <div class="text-gray-400 text-xs">Click Scan to discover running Python servers...</div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
    
    <!-- Widget-specific admin sections (positioned after main grid) -->
    <div id="widget-admin" style="display: none;">
        <!-- Dynamic content will be inserted here -->
    </div>
    
    <button class="fixed bottom-5 right-5 bg-green-500 text-white border-none rounded-full px-5 py-4 cursor-pointer text-base hover:bg-green-600 transition-colors duration-300" onclick="loadAllData()">🔄 Refresh</button>
    
    <!-- Detail Popover Modal -->
    <div id="detail-modal" class="modal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 id="modal-title">Item Details</h3>
                <span class="close-btn">&times;</span>
            </div>
            <div class="modal-body">
                <div class="modal-navigation">
                    <button id="prev-item">← Previous</button>
                    <span id="item-counter">1 of 5</span>
                    <button id="next-item">Next →</button>
                </div>
                <div id="modal-content"></div>
            </div>
        </div>
    </div>
    
    <!-- Admin Panel -->
    <div id="admin-panel" class="admin-panel">
        <div class="admin-content">
            <div class="admin-header">
                <h2>⚙️ Dashboard Administration</h2>
                <button class="admin-close" onclick="closeAdminPanel()">×</button>
            </div>
            
            <div class="admin-section">
                <h3>🔧 Widget Visibility</h3>
                <div class="widget-toggle">
                    <span>📅 Calendar Events</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="toggle-calendar" checked onchange="toggleWidget('calendar')">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                <div class="widget-toggle">
                    <span>📧 Email Summary</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="toggle-email" checked onchange="toggleWidget('email')">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                <div class="widget-toggle">
                    <span>🐙 GitHub Activity</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="toggle-github" checked onchange="toggleWidget('github')">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                <div class="widget-toggle">
                    <span>✅ TickTick Tasks</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="toggle-ticktick" checked onchange="toggleWidget('ticktick')">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                <div class="widget-toggle">
                    <span>� Notes & Knowledge</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="toggle-notes" checked onchange="toggleWidget('notes')">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                <div class="widget-toggle">
                    <span>�📰 News Headlines</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="toggle-news" checked onchange="toggleWidget('news')">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                <div class="widget-toggle">
                    <span>🎵 Music Trends</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="toggle-music" checked onchange="toggleWidget('music')">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
                <div class="widget-toggle">
                    <span>👁️ Vanity Alerts</span>
                    <label class="toggle-switch">
                        <input type="checkbox" id="toggle-vanity" checked onchange="toggleWidget('vanity')">
                        <span class="toggle-slider"></span>
                    </label>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // Global state for modal
        let currentItems = [];
        let currentIndex = 0;
        let currentCategory = '';
        
        // News filtering
        let currentNewsFilter = 'all';
        
        // Format calendar events with day dividers and current time indicator
        function formatCalendarEvents(events) {
            if (!events || events.length === 0) {
                return '<p class="text-gray-300 text-sm">No upcoming events</p>';
            }
            
            const now = new Date();
            const today = now.toDateString();
            
            // Group events by date
            const eventsByDate = {};
            events.forEach(event => {
                // Handle both direct date strings and nested dateTime objects
                const startDate = event.start?.dateTime || event.start;
                const eventDate = new Date(startDate).toDateString();
                if (!eventsByDate[eventDate]) {
                    eventsByDate[eventDate] = [];
                }
                eventsByDate[eventDate].push(event);
            });
            
            let html = '';
            const sortedDates = Object.keys(eventsByDate).sort((a, b) => new Date(a) - new Date(b));
            
            sortedDates.forEach((dateStr, dateIndex) => {
                const date = new Date(dateStr);
                const isToday = dateStr === today;
                const dayName = date.toLocaleDateString('en-US', { weekday: 'long' });
                const monthDay = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
                
                // Add day divider
                html += `<div class="calendar-day-divider">
                    ${isToday ? '🔥 TODAY' : dayName} - ${monthDay}
                </div>`;
                
                // Sort events by time within the day
                const dayEvents = eventsByDate[dateStr].sort((a, b) => {
                    const aStart = new Date(a.start?.dateTime || a.start);
                    const bStart = new Date(b.start?.dateTime || b.start);
                    return aStart - bStart;
                });
                
                let addedCurrentTime = false;
                
                dayEvents.forEach((event, eventIndex) => {
                    // Handle both direct date strings and nested dateTime objects
                    const startDate = event.start?.dateTime || event.start;
                    const endDate = event.end?.dateTime || event.end;
                    
                    const eventStart = new Date(startDate);
                    const eventEnd = endDate ? new Date(endDate) : eventStart;
                    
                    // Add current time indicator for today
                    if (isToday && !addedCurrentTime && now < eventStart) {
                        html += '<div class="calendar-current-time"></div>';
                        addedCurrentTime = true;
                    }
                    
                    // Determine event status
                    let eventClass = 'calendar-event';
                    if (isToday) {
                        if (now >= eventStart && now <= eventEnd) {
                            eventClass += ' current-event';
                        } else if (now > eventEnd) {
                            eventClass += ' past-event';
                        } else {
                            eventClass += ' upcoming-event';
                        }
                    } else if (date < now) {
                        eventClass += ' past-event';
                    } else {
                        eventClass += ' upcoming-event';
                    }
                    
                    const startTime = eventStart.toLocaleTimeString('en-US', { 
                        hour: 'numeric', 
                        minute: '2-digit',
                        hour12: true 
                    });
                    
                    const endTime = event.end ? eventEnd.toLocaleTimeString('en-US', { 
                        hour: 'numeric', 
                        minute: '2-digit',
                        hour12: true 
                    }) : '';
                    
                    const timeStr = endTime ? `${startTime} - ${endTime}` : startTime;
                    
                    html += `<div class="${eventClass}">
                        <div class="font-semibold text-white text-sm">${event.summary || 'Untitled Event'}</div>
                        <div class="text-gray-300 text-xs">${timeStr}</div>
                        ${event.location ? `<div class="text-gray-400 text-xs">📍 ${event.location}</div>` : ''}
                    </div>`;
                });
                
                // Add current time indicator at the end of today if no events are left
                if (isToday && !addedCurrentTime) {
                    html += '<div class="calendar-current-time"></div>';
                }
            });
            
            return html;
        }
        
        // Admin helper functions for server-side settings
        async function saveWidgetSettings(widgetName, isVisible) {
            try {
                const response = await fetch('/api/admin/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        type: 'widget_visibility',
                        data: {
                            [widgetName]: isVisible
                        }
                    }),
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const result = await response.json();
                console.log('Widget settings saved:', result);
            } catch (error) {
                console.error('Error saving widget settings:', error);
            }
        }
        
        async function saveNewsConfig(config) {
            try {
                const response = await fetch('/api/admin/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        type: 'news_config',
                        data: config
                    }),
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const result = await response.json();
                console.log('News config saved:', result);
            } catch (error) {
                console.error('Error saving news config:', error);
            }
        }
        
        async function saveVanityConfig(config) {
            try {
                const response = await fetch('/api/admin/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        type: 'vanity_config',
                        data: config
                    }),
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const result = await response.json();
                console.log('Vanity config saved:', result);
            } catch (error) {
                console.error('Error saving vanity config:', error);
            }
        }
        
        async function saveMusicConfig(config) {
            try {
                const response = await fetch('/api/admin/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        type: 'music_config',
                        data: config
                    }),
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const result = await response.json();
                console.log('Music config saved:', result);
            } catch (error) {
                console.error('Error saving music config:', error);
            }
        }
        
        async function saveGithubConfig(config) {
            try {
                const response = await fetch('/api/admin/settings', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        type: 'github_config',
                        data: config
                    }),
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const result = await response.json();
                console.log('GitHub config saved:', result);
            } catch (error) {
                console.error('Error saving GitHub config:', error);
            }
        }
        
        function filterNews(filter) {
            currentNewsFilter = filter;
            
            // Update button states
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            document.getElementById(`filter-${filter}`).classList.add('active');
            
            // Reload news with new filter
            loadData('/api/news', 'news-content');
        }
        
        // Simple data loading
        async function loadData(endpoint, elementId) {
            const element = document.getElementById(elementId);
            try {
                // Add filter parameter for news
                let url = endpoint;
                if (endpoint === '/api/news') {
                    url += `?filter=${currentNewsFilter}`;
                }
                
                const response = await fetch(url);
                if (!response.ok) throw new Error(`HTTP ${response.status}`);
                const data = await response.json();
                
                if (data.error) {
                    element.innerHTML = `<div class="error">❌ ${data.error}</div>`;
                    return;
                }
                
                // Store data globally for modal access
                const sectionName = elementId.replace('-content', '');
                let sectionData = [];
                
                // Format data based on type
                if (elementId === 'calendar-content') {
                    sectionData = data.events || [];
                    if (data.events && data.events.length > 0) {
                        element.innerHTML = formatCalendarEvents(data.events);
                    } else {
                        element.innerHTML = '<div class="item">No events this week</div>';
                    }
                }
                else if (elementId === 'email-content') {
                    sectionData = data.emails || [];
                    element.innerHTML = `
                        <div class="item-summary">
                            <div class="item-title">📨 Unread: ${data.unread || 0}</div>
                            <div class="item-meta">Total: ${data.emails ? data.emails.length : 0}</div>
                        </div>
                        ${data.emails && data.emails.length > 0 ? data.emails.slice(0, 5).map(email => 
                            `<div class="item">
                                <div class="item-title">${email.subject || 'No Subject'}</div>
                                <div class="item-meta">From: ${email.sender || 'Unknown'}</div>
                                <div class="item-meta">${email.timestamp ? new Date(email.timestamp).toLocaleDateString() : ''}</div>
                            </div>`
                        ).join('') : '<div class="item">No emails found</div>'}
                    `;
                }
                else if (elementId === 'github-content') {
                    if (data.items) {
                        sectionData = data.items;
                        element.innerHTML = data.items.map(item => 
                            `<div class="item">
                                <div class="item-title">${item.title}</div>
                                <div class="item-meta">
                                    <span style="color: ${item.type === 'Review Requested' ? '#ff9800' : item.type === 'Issue Assigned' ? '#2196f3' : '#4caf50'}">
                                        ${item.type}
                                    </span>
                                    • ${item.repo} #${item.number}
                                </div>
                            </div>`
                        ).join('');
                    } else if (data.repos) {
                        sectionData = data.repos;
                        element.innerHTML = data.repos.map(repo => 
                            `<div class="item">
                                <div class="item-title">${repo.name}</div>
                                <div class="item-meta">⭐ ${repo.stars} | Issues: ${repo.issues}</div>
                            </div>`
                        ).join('');
                    } else {
                        element.innerHTML = '<div class="item">No GitHub activity found</div>';
                    }
                }
                else if (elementId === 'ticktick-content') {
                    if (data.authenticated === false) {
                        element.innerHTML = `
                            <div class="item">
                                <div class="item-title">🔗 TickTick Not Connected</div>
                                <div class="item-meta">
                                    <a href="${data.auth_url}" style="color: #4CAF50; text-decoration: none;">
                                        Click here to connect TickTick →
                                    </a>
                                </div>
                            </div>
                        `;
                    } else {
                        sectionData = data.tasks || [];
                        element.innerHTML = data.tasks ? data.tasks.map(task => 
                            `<div class="item">
                                <div class="item-title">${task.title}</div>
                                <div class="item-meta">Due: ${task.due || 'No due date'}</div>
                            </div>`
                        ).join('') : '<div class="item">No tasks found</div>';
                    }
                }
                else if (elementId === 'news-content') {
                    sectionData = data.articles || [];
                    element.innerHTML = data.articles ? data.articles.map(article => 
                        `<div class="item">
                            <div class="item-title">${article.title}</div>
                            <div class="item-meta">${article.source}</div>
                        </div>`
                    ).join('') : '<div class="item">No news available</div>';
                }
                else if (elementId === 'music-content') {
                    sectionData = data.tracks || [];
                    element.innerHTML = data.tracks ? data.tracks.map(track => 
                        `<div class="item">
                            <div class="item-title">${track.title}</div>
                            <div class="item-meta">${track.artist} - ${track.platform || 'Streaming'}</div>
                        </div>`
                    ).join('') : '<div class="item">No music data available</div>';
                }
                else if (elementId === 'vanity-content') {
                    sectionData = data.alerts || [];
                    if (data.alerts && data.alerts.length > 0) {
                        element.innerHTML = data.alerts.map(alert => 
                            `<div class="item">
                                <div class="item-title">${alert.title}</div>
                                <div class="item-meta">
                                    <span style="color: ${alert.category === 'buildly' ? '#4CAF50' : alert.category === 'music' ? '#9C27B0' : alert.category === 'book' ? '#FF9800' : '#2196F3'}">
                                        ${alert.source}
                                    </span>
                                    • ${alert.search_term || alert.category}
                                    ${alert.confidence_score ? ` • ${Math.round(alert.confidence_score * 100)}% match` : ''}
                                </div>
                            </div>`
                        ).join('');
                    } else {
                        element.innerHTML = '<div class="item">No vanity alerts found</div>';
                    }
                }
                else if (elementId === 'liked-items-content') {
                    sectionData = data.liked_items || [];
                    if (data.liked_items && data.liked_items.length > 0) {
                        element.innerHTML = data.liked_items.map(item => 
                            `<div class="item">
                                <div class="item-title">${item.title}</div>
                                <div class="item-meta">
                                    <span style="color: ${item.type === 'jokes' ? '#FFD700' : item.type === 'news' ? '#2196F3' : item.type === 'vanity' ? '#4CAF50' : '#9C27B0'}">
                                        ${item.source || item.type}
                                    </span>
                                    • Liked on ${new Date(item.liked_at).toLocaleDateString()}
                                </div>
                            </div>`
                        ).join('');
                    } else {
                        element.innerHTML = '<div class="item">No liked items yet - start liking content!</div>';
                    }
                }
                
                // Store section data globally
                window.dashboardData[sectionName] = sectionData;
                
            } catch (error) {
                console.error(`Error loading ${endpoint}:`, error);
                element.innerHTML = `<div class="error">❌ Failed to load data</div>`;
            }
        }
        
                // Load all data
        async function loadAllData() {
            await Promise.all([
                loadJoke(),
                loadWeather(),
                loadAISummary(),
                loadData('/api/calendar', 'calendar-content'),
                loadData('/api/email', 'email-content'),
                loadData('/api/github', 'github-content'),
                window.taskManagement ? window.taskManagement.loadTasks() : Promise.resolve(),
                loadNotes(),
                loadData('/api/news', 'news-content'),
                loadData('/api/music', 'music-content'),
                loadData('/api/vanity', 'vanity-content'),
                loadData('/api/liked-items', 'liked-items-content'),
                loadDashboardProjects(),
                refreshDiscoveredServers()
            ]);
            
            // Make items clickable after all data is loaded
            setTimeout(makeItemsClickable, 100);
            
            // Update widget statuses after loading
            updateAllWidgetStatus();
        }
        
        // Refresh individual widget
        async function refreshWidget(widgetName) {
            console.log(`Refreshing widget: ${widgetName}`);
            
            // Update status to refreshing
            const statusElement = document.getElementById(`${widgetName}-status`);
            if (statusElement) {
                statusElement.className = 'text-xs px-2 py-1 rounded bg-yellow-600 text-white';
                statusElement.textContent = '🔄 Refreshing...';
            }
            
            try {
                // Call backend refresh endpoint
                const response = await fetch(`/api/system/refresh-widget/${widgetName}`, {
                    method: 'POST'
                });
                const result = await response.json();
                
                if (result.success) {
                    // Reload the specific widget data
                    await reloadWidgetData(widgetName);
                    
                    // Update status to success
                    if (statusElement) {
                        statusElement.className = 'text-xs px-2 py-1 rounded bg-green-600 text-white';
                        statusElement.textContent = '🟢 Active';
                    }
                } else {
                    throw new Error(result.error || 'Refresh failed');
                }
            } catch (error) {
                console.error(`Error refreshing widget ${widgetName}:`, error);
                
                // Update status to error
                if (statusElement) {
                    statusElement.className = 'text-xs px-2 py-1 rounded bg-red-600 text-white';
                    statusElement.textContent = '🔴 Error';
                }
            }
        }
        
        // Reload specific widget data
        async function reloadWidgetData(widgetName) {
            switch(widgetName) {
                case 'calendar':
                    await loadData('/api/calendar', 'calendar-content');
                    break;
                case 'email':
                    await loadData('/api/email', 'email-content');
                    break;
                case 'github':
                    await loadData('/api/github', 'github-content');
                    break;
                case 'tasks':
                    if (window.taskManagement) {
                        await window.taskManagement.loadTasks();
                    }
                    break;
                case 'weather':
                    await loadWeather();
                    break;
                case 'jokes':
                    await loadJoke();
                    break;
                case 'news':
                    await loadData('/api/news', 'news-content');
                    break;
                case 'music':
                    await loadData('/api/music', 'music-content');
                    break;
                default:
                    console.log(`No reload function for widget: ${widgetName}`);
            }
        }
        
        // Check system status and update widget indicators
        async function updateAllWidgetStatus() {
            try {
                const response = await fetch('/api/system/status');
                const status = await response.json();
                
                if (status.success && status.widgets) {
                    // Update each widget status indicator
                    Object.entries(status.widgets).forEach(([widgetKey, widgetInfo]) => {
                        const widgetName = widgetKey.replace('_widget', '');
                        const statusElement = document.getElementById(`${widgetName}-status`);
                        
                        if (statusElement && widgetInfo.status) {
                            let statusClass, statusText;
                            
                            switch(widgetInfo.status) {
                                case 'active':
                                    statusClass = 'bg-green-600';
                                    statusText = '🟢 Active';
                                    break;
                                case 'error':
                                    statusClass = 'bg-red-600';
                                    statusText = '🔴 Error';
                                    break;
                                case 'disabled':
                                    statusClass = 'bg-gray-600';
                                    statusText = '⚫ Disabled';
                                    break;
                                default:
                                    statusClass = 'bg-yellow-600';
                                    statusText = '🟡 Unknown';
                            }
                            
                            statusElement.className = `text-xs px-2 py-1 rounded ${statusClass} text-white`;
                            statusElement.textContent = statusText;
                        }
                    });
                }
            } catch (error) {
                console.error('Error updating widget status:', error);
            }
        }
        
        // Auto-refresh status every 2 minutes
        setInterval(updateAllWidgetStatus, 120000);
        
        // Load marketing dashboard projects
        async function loadDashboardProjects() {
            const overviewElement = document.getElementById('dashboard-overview');
            const projectsElement = document.getElementById('dashboard-projects');
            
            if (!projectsElement) {
                console.error('Dashboard projects element not found');
                return;
            }
            
            try {
                const response = await fetch('/api/dashboards');
                const data = await response.json();
                
                if (data.error) {
                    projectsElement.innerHTML = `<div class="error">❌ ${data.error}</div>`;
                    return;
                }
                
                const projects = data.projects || [];
                
                // Separate primary and regular dashboards
                const primaryDashboards = projects.filter(p => p.type === 'primary_dashboard');
                const regularDashboards = projects.filter(p => p.type !== 'primary_dashboard');
                
                // Update overview stats
                if (overviewElement) {
                    const activeCount = projects.filter(p => p.is_active).length;
                    const primaryCount = primaryDashboards.length;
                    overviewElement.innerHTML = `
                        <div class="flex justify-between items-center mb-3 text-sm">
                            <span class="text-white opacity-75">Total: ${projects.length} (${primaryCount} Primary)</span>
                            <span class="text-green-400">Active: ${activeCount}</span>
                        </div>
                    `;
                }
                
                // Display projects
                if (projects.length === 0) {
                    projectsElement.innerHTML = `
                        <div class="item text-center">
                            <div class="item-title">No dashboards found</div>
                            <div class="item-meta">Add a dashboard to get started</div>
                        </div>
                    `;
                } else {
                    // Combine primary dashboards first, then regular ones
                    const sortedProjects = [...primaryDashboards, ...regularDashboards];
                    
                    projectsElement.innerHTML = sortedProjects.map(project => {
                        const isActive = project.is_active;
                        const isPrimary = project.type === 'primary_dashboard';
                        const statusColor = isActive ? 'text-green-400' : 'text-gray-400';
                        const statusIcon = isActive ? '🟢' : '⚫';
                        const localUrl = project.url || `http://localhost:${project.port || 8000}`;
                        const productionUrl = project.custom_domain ? `https://${project.custom_domain}` : project.github_pages_url;
                        
                        // Special styling for primary dashboards
                        const cardClass = isPrimary ? 
                            'bg-gradient-to-r from-purple-900/20 to-blue-900/20 border-purple-500/30' : 
                            'bg-white bg-opacity-5 border-white border-opacity-10';
                        
                        const primaryBadge = isPrimary ? `
                            <div class="absolute top-2 right-2">
                                <span class="px-2 py-1 text-xs font-bold bg-purple-600 text-white rounded-full">
                                    👑 PRIMARY
                                </span>
                            </div>
                        ` : '';
                        
                        const primaryFeatures = isPrimary ? `
                            <!-- Primary Dashboard Features -->
                            <div class="mt-3 pt-3 border-t border-purple-500/30">
                                <div class="flex gap-2 mb-2 flex-wrap">
                                    <button onclick="manageCronSystems('${project.name}')" 
                                            class="px-2 py-1 bg-orange-600 hover:bg-orange-700 text-white text-xs rounded flex items-center gap-1" 
                                            title="Manage Cron Systems">
                                        ⏰ Cron
                                    </button>
                                    <button onclick="monitorAllDashboards('${project.name}')" 
                                            class="px-2 py-1 bg-indigo-600 hover:bg-indigo-700 text-white text-xs rounded flex items-center gap-1" 
                                            title="Monitor All Dashboards">
                                        📊 Monitor All
                                    </button>
                                    <button onclick="manageWebsites('${project.name}')" 
                                            class="px-2 py-1 bg-cyan-600 hover:bg-cyan-700 text-white text-xs rounded flex items-center gap-1" 
                                            title="Manage Websites">
                                        🌐 Websites
                                    </button>
                                    <button onclick="viewOutreachDashboard('${project.name}')" 
                                            class="px-2 py-1 bg-pink-600 hover:bg-pink-700 text-white text-xs rounded flex items-center gap-1" 
                                            title="Email Outreach">
                                        📧 Outreach
                                    </button>
                                </div>
                            </div>
                        ` : '';
                        
                        return `
                            <div class="relative ${cardClass} rounded-lg p-4 border">
                                ${primaryBadge}
                                <div class="flex justify-between items-start mb-3">
                                    <div class="flex-1 ${isPrimary ? 'pr-16' : ''}">
                                        <h3 class="text-white font-medium text-sm mb-1">${project.name}</h3>
                                        <div class="flex items-center gap-2 mb-2">
                                            <span class="${statusColor} text-xs">${statusIcon} ${isActive ? 'Active' : 'Inactive'}</span>
                                            <span class="text-xs ${isPrimary ? 'text-purple-300' : 'text-gray-300'}">${project.type?.replace('_', ' ') || 'dashboard'}</span>
                                            ${project.brand ? `<span class="text-xs text-blue-300">${project.brand}</span>` : ''}
                                        </div>
                                        <p class="text-xs text-gray-400 line-clamp-2">${project.description || 'No description'}</p>
                                    </div>
                                </div>
                                
                                <!-- Project Links -->
                                <div class="flex gap-2 mb-3 flex-wrap">
                                    ${localUrl ? `
                                    <a href="${localUrl}" target="_blank" 
                                       class="px-2 py-1 ${isPrimary ? 'bg-purple-600 hover:bg-purple-700' : 'bg-blue-600 hover:bg-blue-700'} text-white text-xs rounded flex items-center gap-1">
                                        🏠 Local
                                    </a>` : ''}
                                    ${productionUrl ? `
                                    <a href="${productionUrl}" target="_blank" 
                                       class="px-2 py-1 bg-green-600 hover:bg-green-700 text-white text-xs rounded flex items-center gap-1">
                                        🌐 Live
                                    </a>` : ''}
                                    ${project.path ? `
                                    <button onclick="openInTerminal('${project.path}')" 
                                            class="px-2 py-1 bg-gray-600 hover:bg-gray-700 text-white text-xs rounded flex items-center gap-1">
                                        📁 Folder
                                    </button>` : ''}
                                </div>
                                
                                <!-- Action Buttons -->
                                <div class="flex gap-2 justify-between items-center">
                                    <button onclick="startDashboard('${project.name}')" 
                                            class="px-3 py-1 ${isPrimary ? 'bg-purple-600 hover:bg-purple-700' : 'bg-purple-600 hover:bg-purple-700'} text-white text-xs rounded flex items-center gap-1"
                                            id="start-btn-${project.name.replace(/\s+/g, '-').toLowerCase()}" 
                                            title="Start/Monitor Dashboard">
                                        <span class="status-icon">▶️</span>
                                        <span class="status-text">Start</span>
                                    </button>
                                    
                                    <div class="flex gap-1">
                                        <button onclick="checkDashboardStatus('${project.name}')" 
                                                class="px-2 py-1 bg-yellow-600 hover:bg-yellow-700 text-white text-xs rounded" 
                                                title="Check Status">
                                            📊
                                        </button>
                                        <button onclick="showDashboardLogs('${project.name}')" 
                                                class="px-2 py-1 bg-indigo-600 hover:bg-indigo-700 text-white text-xs rounded" 
                                                title="View Logs">
                                            📝
                                        </button>
                                    </div>
                                </div>
                                
                                ${primaryFeatures}
                                
                                <!-- Status Display -->
                                <div id="status-${project.name.replace(/\s+/g, '-').toLowerCase()}" 
                                     class="mt-2 text-xs" style="display: none;"></div>
                            </div>
                        `;
                    }).join('');
                }
                
                // Store dashboard data globally
                window.dashboardData.dashboards = projects;
                
            } catch (error) {
                console.error('Error loading dashboard projects:', error);
                projectsElement.innerHTML = `<div class="error">❌ Failed to load dashboards</div>`;
            }
        }
        
        // Open a directory in Terminal (macOS)
        async function openInTerminal(path) {
            try {
                const response = await fetch('/api/system/open-terminal', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ path: path })
                });
                
                if (!response.ok) {
                    // Fallback: try to open with file manager
                    window.open(`file://${path}`, '_blank');
                }
            } catch (error) {
                console.error('Error opening terminal:', error);
                // Fallback: show path in alert
                alert(`Project path: ${path}`);
            }
        }
        
        // Primary Dashboard Management Functions
        async function manageCronSystems(dashboardName) {
            try {
                const response = await fetch(`/api/dashboards/${dashboardName}/cron-systems`);
                const data = await response.json();
                
                const modal = document.createElement('div');
                modal.className = 'modal-overlay';
                modal.innerHTML = `
                    <div class="modal-content w-4/5 max-w-4xl">
                        <div class="flex justify-between items-center mb-4">
                            <h3 class="text-lg font-semibold text-white">Cron Systems - ${dashboardName}</h3>
                            <button onclick="this.closest('.modal-overlay').remove()" class="text-white hover:text-red-400">✕</button>
                        </div>
                        <div id="cron-systems-content" class="space-y-4">
                            ${data.error ? `<div class="text-red-400">❌ ${data.error}</div>` : 
                              (data.systems || []).map(system => `
                                <div class="bg-gray-800 rounded-lg p-4">
                                    <div class="flex justify-between items-start mb-2">
                                        <h4 class="text-white font-medium">${system.name}</h4>
                                        <span class="px-2 py-1 text-xs rounded ${system.active ? 'bg-green-600 text-white' : 'bg-gray-600 text-white'}">
                                            ${system.active ? '🟢 Active' : '⚫ Inactive'}
                                        </span>
                                    </div>
                                    <p class="text-gray-400 text-sm mb-2">${system.schedule}</p>
                                    <p class="text-gray-300 text-sm mb-3">${system.description}</p>
                                    <div class="flex gap-2">
                                        <button onclick="toggleCronSystem('${system.name}', ${!system.active})" 
                                                class="px-3 py-1 ${system.active ? 'bg-red-600 hover:bg-red-700' : 'bg-green-600 hover:bg-green-700'} text-white text-sm rounded">
                                            ${system.active ? 'Stop' : 'Start'}
                                        </button>
                                        <button onclick="viewCronLogs('${system.name}')" 
                                                class="px-3 py-1 bg-blue-600 hover:bg-blue-700 text-white text-sm rounded">
                                            Logs
                                        </button>
                                    </div>
                                </div>
                              `).join('')}
                        </div>
                    </div>
                `;
                document.body.appendChild(modal);
            } catch (error) {
                console.error('Error loading cron systems:', error);
            }
        }

        async function monitorAllDashboards(primaryDashboard) {
            try {
                const response = await fetch(`/api/dashboards/${primaryDashboard}/monitor-all`);
                const data = await response.json();
                
                const modal = document.createElement('div');
                modal.className = 'modal-overlay';
                modal.innerHTML = `
                    <div class="modal-content w-4/5 max-w-6xl">
                        <div class="flex justify-between items-center mb-4">
                            <h3 class="text-lg font-semibold text-white">All Dashboards Monitor</h3>
                            <button onclick="this.closest('.modal-overlay').remove()" class="text-white hover:text-red-400">✕</button>
                        </div>
                        <div id="all-dashboard-status" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            ${data.error ? `<div class="text-red-400 col-span-full">❌ ${data.error}</div>` : 
                              (data.dashboards || []).map(dashboard => `
                                <div class="bg-gray-800 rounded-lg p-4">
                                    <div class="flex justify-between items-start mb-2">
                                        <h4 class="text-white font-medium text-sm">${dashboard.name}</h4>
                                        <span class="px-2 py-1 text-xs rounded ${dashboard.status === 'running' ? 'bg-green-600' : 'bg-red-600'} text-white">
                                            ${dashboard.status === 'running' ? '🟢' : '🔴'} ${dashboard.status}
                                        </span>
                                    </div>
                                    <div class="space-y-1 text-xs text-gray-300">
                                        <div>CPU: ${dashboard.cpu_percent || 'N/A'}%</div>
                                        <div>Memory: ${dashboard.memory_mb || 'N/A'}MB</div>
                                        <div>Uptime: ${dashboard.uptime || 'N/A'}</div>
                                        <div>Port: ${dashboard.port || 'N/A'}</div>
                                    </div>
                                    <div class="flex gap-1 mt-3">
                                        <button onclick="quickStartDashboard('${dashboard.name}')" 
                                                class="px-2 py-1 bg-green-600 hover:bg-green-700 text-white text-xs rounded">
                                            Start
                                        </button>
                                        <button onclick="quickRestartDashboard('${dashboard.name}')" 
                                                class="px-2 py-1 bg-yellow-600 hover:bg-yellow-700 text-white text-xs rounded">
                                            Restart
                                        </button>
                                    </div>
                                </div>
                              `).join('')}
                        </div>
                        <div class="mt-4 text-center">
                            <button onclick="refreshAllDashboards()" 
                                    class="px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded">
                                🔄 Refresh All
                            </button>
                        </div>
                    </div>
                `;
                document.body.appendChild(modal);
            } catch (error) {
                console.error('Error loading all dashboard status:', error);
            }
        }

        async function manageWebsites(dashboardName) {
            try {
                const response = await fetch(`/api/dashboards/${dashboardName}/websites`);
                const data = await response.json();
                
                const modal = document.createElement('div');
                modal.className = 'modal-overlay';
                modal.innerHTML = `
                    <div class="modal-content w-4/5 max-w-5xl">
                        <div class="flex justify-between items-center mb-4">
                            <h3 class="text-lg font-semibold text-white">Website Management - ${dashboardName}</h3>
                            <button onclick="this.closest('.modal-overlay').remove()" class="text-white hover:text-red-400">✕</button>
                        </div>
                        <div id="websites-content" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            ${data.error ? `<div class="text-red-400 col-span-full">❌ ${data.error}</div>` : 
                              (data.websites || []).map(site => `
                                <div class="bg-gray-800 rounded-lg p-4">
                                    <div class="flex justify-between items-start mb-2">
                                        <h4 class="text-white font-medium">${site.name}</h4>
                                        <span class="px-2 py-1 text-xs rounded ${site.status === 'online' ? 'bg-green-600' : 'bg-red-600'} text-white">
                                            ${site.status === 'online' ? '🟢' : '🔴'} ${site.status}
                                        </span>
                                    </div>
                                    <p class="text-gray-400 text-sm mb-2">${site.url}</p>
                                    <p class="text-gray-300 text-sm mb-3">${site.description}</p>
                                    <div class="flex gap-2 flex-wrap">
                                        <a href="${site.url}" target="_blank" 
                                           class="px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded">
                                            🌐 Visit
                                        </a>
                                        <button onclick="deployWebsite('${site.name}')" 
                                                class="px-2 py-1 bg-green-600 hover:bg-green-700 text-white text-xs rounded">
                                            🚀 Deploy
                                        </button>
                                        <button onclick="viewWebsiteLogs('${site.name}')" 
                                                class="px-2 py-1 bg-indigo-600 hover:bg-indigo-700 text-white text-xs rounded">
                                            📝 Logs
                                        </button>
                                    </div>
                                </div>
                              `).join('')}
                        </div>
                    </div>
                `;
                document.body.appendChild(modal);
            } catch (error) {
                console.error('Error loading websites:', error);
            }
        }

        async function viewOutreachDashboard(dashboardName) {
            try {
                const response = await fetch(`/api/dashboards/${dashboardName}/outreach`);
                const data = await response.json();
                
                const modal = document.createElement('div');
                modal.className = 'modal-overlay';
                modal.innerHTML = `
                    <div class="modal-content w-4/5 max-w-4xl">
                        <div class="flex justify-between items-center mb-4">
                            <h3 class="text-lg font-semibold text-white">Email Outreach Dashboard</h3>
                            <button onclick="this.closest('.modal-overlay').remove()" class="text-white hover:text-red-400">✕</button>
                        </div>
                        <div id="outreach-content" class="space-y-4">
                            ${data.error ? `<div class="text-red-400">❌ ${data.error}</div>` : `
                                <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                                    <div class="bg-gray-800 rounded-lg p-4 text-center">
                                        <div class="text-2xl font-bold text-green-400">${data.stats?.emails_sent || 0}</div>
                                        <div class="text-gray-300 text-sm">Emails Sent</div>
                                    </div>
                                    <div class="bg-gray-800 rounded-lg p-4 text-center">
                                        <div class="text-2xl font-bold text-blue-400">${data.stats?.open_rate || 0}%</div>
                                        <div class="text-gray-300 text-sm">Open Rate</div>
                                    </div>
                                    <div class="bg-gray-800 rounded-lg p-4 text-center">
                                        <div class="text-2xl font-bold text-purple-400">${data.stats?.response_rate || 0}%</div>
                                        <div class="text-gray-300 text-sm">Response Rate</div>
                                    </div>
                                </div>
                                <div class="space-y-3">
                                    ${(data.campaigns || []).map(campaign => `
                                        <div class="bg-gray-800 rounded-lg p-4">
                                            <div class="flex justify-between items-start mb-2">
                                                <h4 class="text-white font-medium">${campaign.name}</h4>
                                                <span class="px-2 py-1 text-xs rounded ${campaign.status === 'active' ? 'bg-green-600' : 'bg-gray-600'} text-white">
                                                    ${campaign.status}
                                                </span>
                                            </div>
                                            <p class="text-gray-400 text-sm mb-2">${campaign.description}</p>
                                            <div class="grid grid-cols-3 gap-4 text-sm text-gray-300">
                                                <div>Sent: ${campaign.sent || 0}</div>
                                                <div>Opens: ${campaign.opens || 0}</div>
                                                <div>Replies: ${campaign.replies || 0}</div>
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            `}
                        </div>
                    </div>
                `;
                document.body.appendChild(modal);
            } catch (error) {
                console.error('Error loading outreach dashboard:', error);
            }
        }

        // Quick action functions
        async function quickStartDashboard(dashboardName) {
            await startDashboard(dashboardName);
        }

        async function quickRestartDashboard(dashboardName) {
            // Implementation for restart
            console.log(`Restarting ${dashboardName}`);
        }

        async function refreshAllDashboards() {
            location.reload();
        }

        async function toggleCronSystem(systemName, enable) {
            console.log(`${enable ? 'Enabling' : 'Disabling'} cron system: ${systemName}`);
        }

        async function viewCronLogs(systemName) {
            console.log(`Viewing logs for cron system: ${systemName}`);
        }

        async function deployWebsite(siteName) {
            console.log(`Deploying website: ${siteName}`);
        }

        async function viewWebsiteLogs(siteName) {
            console.log(`Viewing logs for website: ${siteName}`);
        }
        
        // ===================================================================
        // SERVER DISCOVERY FUNCTIONS
        // ===================================================================
        
        async function refreshDiscoveredServers() {
            const container = document.getElementById('discovered-servers-container');
            const refreshIcon = document.getElementById('refresh-discovered-icon');
            
            if (!container) return;
            
            // Animate refresh icon
            if (refreshIcon) {
                refreshIcon.style.animation = 'spin 1s linear infinite';
            }
            
            container.innerHTML = '<div class="text-gray-400 text-xs">🔍 Scanning for Python servers...</div>';
            
            try {
                // Get all running servers
                const serversResponse = await fetch('/api/servers');
                const serversData = await serversResponse.json();
                
                // Get known dashboards
                const dashboardsResponse = await fetch('/api/dashboards');
                const dashboardsData = await dashboardsResponse.json();
                
                if (!serversData.success) {
                    container.innerHTML = `<div class="text-red-400 text-xs">❌ ${serversData.error || 'Failed to discover servers'}</div>`;
                    return;
                }
                
                const servers = serversData.servers || [];
                const knownDashboards = dashboardsData.projects || [];
                
                // Filter out servers that are already mapped to dashboards
                const knownPorts = new Set(knownDashboards.map(d => d.port).filter(p => p));
                const unmappedServers = servers.filter(server => !knownPorts.has(server.port));
                
                if (unmappedServers.length === 0) {
                    container.innerHTML = '<div class="text-gray-400 text-xs">✅ No unmapped servers found. All servers are tracked.</div>';
                    return;
                }
                
                // Display unmapped servers
                container.innerHTML = unmappedServers.map(server => {
                    const statusColor = server.status === 'running' ? 'bg-green-500' : 'bg-red-500';
                    const canControl = server.can_control;
                    const uptime = server.start_time ? formatUptime(Date.now() / 1000 - server.start_time) : 'Unknown';
                    
                    return `
                        <div class="bg-white bg-opacity-5 rounded-lg p-3 border border-white border-opacity-10">
                            <div class="flex items-start justify-between gap-2">
                                <div class="flex-1 min-w-0">
                                    <div class="flex items-center gap-2 mb-1">
                                        <span class="${statusColor} w-2 h-2 rounded-full animate-pulse"></span>
                                        <span class="text-white text-xs font-semibold">${server.name}</span>
                                        <span class="text-gray-400 text-xs">${server.type}</span>
                                    </div>
                                    
                                    <div class="text-xs text-gray-400 mb-2 space-y-1">
                                        <div class="flex items-center gap-2">
                                            <span class="text-gray-500">Port:</span>
                                            <span class="text-blue-300 font-mono">${server.port}</span>
                                        </div>
                                        ${server.cmdline ? `
                                        <div class="flex items-start gap-2">
                                            <span class="text-gray-500 shrink-0">Path:</span>
                                            <span class="text-gray-300 font-mono text-xs break-all">${extractPath(server.cmdline)}</span>
                                        </div>
                                        ` : ''}
                                        ${server.pid ? `
                                        <div class="flex items-center gap-2">
                                            <span class="text-gray-500">PID:</span>
                                            <span class="text-gray-300 font-mono">${server.pid}</span>
                                        </div>
                                        ` : ''}
                                        <div class="flex items-center gap-2">
                                            <span class="text-gray-500">Uptime:</span>
                                            <span class="text-gray-300">${uptime}</span>
                                        </div>
                                        <div class="flex items-center gap-2">
                                            <span class="text-gray-500">Memory:</span>
                                            <span class="text-gray-300">${server.memory_mb.toFixed(1)} MB</span>
                                        </div>
                                    </div>
                                </div>
                                
                                <div class="flex flex-col gap-1 shrink-0">
                                    <a href="${server.url}" target="_blank" 
                                       class="px-2 py-1 bg-blue-600 hover:bg-blue-700 text-white text-xs rounded whitespace-nowrap flex items-center gap-1"
                                       title="Open in browser">
                                        🌐 Open
                                    </a>
                                    ${canControl ? `
                                    <button onclick="stopDiscoveredServer(${server.port}, '${server.name}')" 
                                            class="px-2 py-1 bg-red-600 hover:bg-red-700 text-white text-xs rounded whitespace-nowrap flex items-center gap-1"
                                            title="Stop server">
                                        ⏹️ Stop
                                    </button>
                                    ` : `
                                    <button disabled 
                                            class="px-2 py-1 bg-gray-600 text-gray-400 text-xs rounded whitespace-nowrap cursor-not-allowed"
                                            title="Cannot control (no PID)">
                                        🔒 Locked
                                    </button>
                                    `}
                                    <button onclick="mapServerToDashboard(${server.port}, '${server.name}', '${extractPath(server.cmdline)}')" 
                                            class="px-2 py-1 bg-green-600 hover:bg-green-700 text-white text-xs rounded whitespace-nowrap flex items-center gap-1"
                                            title="Add to dashboards">
                                        ➕ Map
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');
                
            } catch (error) {
                console.error('Error discovering servers:', error);
                container.innerHTML = `<div class="text-red-400 text-xs">❌ Error: ${error.message}</div>`;
            } finally {
                if (refreshIcon) {
                    refreshIcon.style.animation = '';
                }
            }
        }
        
        function extractPath(cmdline) {
            if (!cmdline) return 'Unknown';
            
            // Try to find a .py file path
            const pyMatch = cmdline.match(/([^\s]+\.py)/);
            if (pyMatch) {
                const fullPath = pyMatch[1];
                // Get the directory containing the .py file
                const parts = fullPath.split('/');
                if (parts.length > 1) {
                    return parts.slice(0, -1).join('/') || '/';
                }
                return fullPath;
            }
            
            // Try to find a directory path
            const pathMatch = cmdline.match(/(?:cd\s+)?([/~][^\s]+)/);
            if (pathMatch) {
                return pathMatch[1];
            }
            
            return cmdline.substring(0, 60) + (cmdline.length > 60 ? '...' : '');
        }
        
        function formatUptime(seconds) {
            if (seconds < 60) return `${Math.floor(seconds)}s`;
            if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
            if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
            return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`;
        }
        
        async function stopDiscoveredServer(port, name) {
            if (!confirm(`Stop server "${name}" on port ${port}?`)) {
                return;
            }
            
            try {
                const response = await fetch(`/api/servers/${port}/stop`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert(`✅ Server stopped successfully!`);
                    // Refresh the list
                    await refreshDiscoveredServers();
                } else {
                    alert(`❌ Failed to stop server: ${data.error || 'Unknown error'}`);
                }
            } catch (error) {
                console.error('Error stopping server:', error);
                alert(`❌ Error: ${error.message}`);
            }
        }
        
        async function mapServerToDashboard(port, name, path) {
            // Create a modal to map the server
            const modal = document.createElement('div');
            modal.className = 'modal-overlay';
            modal.innerHTML = `
                <div class="modal-content max-w-md">
                    <div class="flex justify-between items-center mb-4">
                        <h3 class="text-lg font-semibold text-white">Map Server to Dashboard</h3>
                        <button onclick="this.closest('.modal-overlay').remove()" class="text-white hover:text-red-400">✕</button>
                    </div>
                    <form id="map-server-form" class="space-y-3">
                        <div>
                            <label class="block text-white text-sm mb-1">Dashboard Name:</label>
                            <input type="text" id="map-name" value="${name}" 
                                   class="w-full px-3 py-2 bg-gray-800 text-white rounded border border-gray-600 focus:border-blue-500" required>
                        </div>
                        <div>
                            <label class="block text-white text-sm mb-1">Port:</label>
                            <input type="number" id="map-port" value="${port}" 
                                   class="w-full px-3 py-2 bg-gray-800 text-white rounded border border-gray-600 focus:border-blue-500" required>
                        </div>
                        <div>
                            <label class="block text-white text-sm mb-1">Path:</label>
                            <input type="text" id="map-path" value="${path}" 
                                   class="w-full px-3 py-2 bg-gray-800 text-white rounded border border-gray-600 focus:border-blue-500" required>
                        </div>
                        <div>
                            <label class="block text-white text-sm mb-1">Type:</label>
                            <select id="map-type" class="w-full px-3 py-2 bg-gray-800 text-white rounded border border-gray-600 focus:border-blue-500">
                                <option value="dashboard">Regular Dashboard</option>
                                <option value="api">API Server</option>
                                <option value="web_app">Web Application</option>
                                <option value="microservice">Microservice</option>
                            </select>
                        </div>
                        <div>
                            <label class="block text-white text-sm mb-1">Description (optional):</label>
                            <textarea id="map-description" rows="2"
                                      class="w-full px-3 py-2 bg-gray-800 text-white rounded border border-gray-600 focus:border-blue-500"
                                      placeholder="Brief description of this server..."></textarea>
                        </div>
                        <div class="flex gap-2 pt-2">
                            <button type="submit" class="flex-1 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded">
                                ➕ Add to Dashboards
                            </button>
                            <button type="button" onclick="this.closest('.modal-overlay').remove()" 
                                    class="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded">
                                Cancel
                            </button>
                        </div>
                    </form>
                </div>
            `;
            
            document.body.appendChild(modal);
            
            // Handle form submission
            document.getElementById('map-server-form').addEventListener('submit', async (e) => {
                e.preventDefault();
                
                const formData = {
                    name: document.getElementById('map-name').value,
                    port: parseInt(document.getElementById('map-port').value),
                    path: document.getElementById('map-path').value,
                    type: document.getElementById('map-type').value,
                    description: document.getElementById('map-description').value,
                    url: `http://localhost:${document.getElementById('map-port').value}`,
                    is_active: true
                };
                
                try {
                    const response = await fetch('/api/dashboards/add', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(formData)
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        alert(`✅ Server mapped to dashboard successfully!`);
                        modal.remove();
                        // Refresh both lists
                        await refreshDiscoveredServers();
                        await loadDashboardProjects();
                    } else {
                        alert(`❌ Failed to map server: ${data.error || 'Unknown error'}`);
                    }
                } catch (error) {
                    console.error('Error mapping server:', error);
                    alert(`❌ Error: ${error.message}`);
                }
            });
        }
        
        // Start a dashboard and monitor its status
        async function startDashboard(projectName) {
            const buttonId = `start-btn-${projectName.replace(/\s+/g, '-').toLowerCase()}`;
            const statusId = `status-${projectName.replace(/\s+/g, '-').toLowerCase()}`;
            const button = document.getElementById(buttonId);
            const statusDiv = document.getElementById(statusId);
            
            if (!button || !statusDiv) {
                console.error('Dashboard control elements not found');
                return;
            }
            
            try {
                // Update button to show starting state
                button.innerHTML = '<span class="status-icon">⏳</span><span class="status-text">Starting...</span>';
                button.disabled = true;
                
                // Show status area
                statusDiv.style.display = 'block';
                statusDiv.innerHTML = '<div class="text-yellow-400">🚀 Starting dashboard...</div>';
                
                // Start the dashboard
                const startResponse = await fetch(`/api/dashboards/${encodeURIComponent(projectName)}/start`, {
                    method: 'POST'
                });
                const startResult = await startResponse.json();
                
                if (startResult.success) {
                    // Update button to monitoring state
                    button.innerHTML = '<span class="status-icon">👁️</span><span class="status-text">Monitor</span>';
                    button.disabled = false;
                    
                    // Show success status
                    statusDiv.innerHTML = `
                        <div class="text-green-400">✅ Dashboard started successfully</div>
                        ${startResult.process_id ? `<div class="text-gray-400">Process ID: ${startResult.process_id}</div>` : ''}
                        ${startResult.port ? `<div class="text-blue-400">Port: ${startResult.port}</div>` : ''}
                    `;
                    
                    // Start monitoring
                    monitorDashboard(projectName, buttonId, statusId);
                    
                } else {
                    throw new Error(startResult.error || 'Failed to start dashboard');
                }
                
            } catch (error) {
                console.error(`Error starting dashboard ${projectName}:`, error);
                
                // Reset button
                button.innerHTML = '<span class="status-icon">▶️</span><span class="status-text">Start</span>';
                button.disabled = false;
                
                // Show error status
                statusDiv.innerHTML = `<div class="text-red-400">❌ Error: ${error.message}</div>`;
            }
        }
        
        // Monitor dashboard status with periodic checks
        async function monitorDashboard(projectName, buttonId, statusId) {
            const button = document.getElementById(buttonId);
            const statusDiv = document.getElementById(statusId);
            
            if (!button || !statusDiv) return;
            
            try {
                const response = await fetch(`/api/dashboards/${encodeURIComponent(projectName)}/status`);
                const status = await response.json();
                
                if (status.success) {
                    const isRunning = status.status === 'running';
                    
                    // Update button based on status
                    if (isRunning) {
                        button.innerHTML = '<span class="status-icon">🔄</span><span class="status-text">Running</span>';
                        button.style.backgroundColor = '#059669'; // green-600
                        
                        // Show running status with metrics
                        statusDiv.innerHTML = `
                            <div class="text-green-400">🟢 Running (${status.uptime || '0s'})</div>
                            ${status.cpu_usage ? `<div class="text-blue-400">CPU: ${status.cpu_usage}%</div>` : ''}
                            ${status.memory_usage ? `<div class="text-purple-400">Memory: ${status.memory_usage}MB</div>` : ''}
                            ${status.last_activity ? `<div class="text-gray-400">Last Activity: ${status.last_activity}</div>` : ''}
                        `;
                        
                        // Continue monitoring every 30 seconds
                        setTimeout(() => monitorDashboard(projectName, buttonId, statusId), 30000);
                        
                    } else {
                        // Dashboard stopped
                        button.innerHTML = '<span class="status-icon">▶️</span><span class="status-text">Start</span>';
                        button.style.backgroundColor = '#7c3aed'; // purple-600
                        
                        statusDiv.innerHTML = `
                            <div class="text-yellow-400">⏹️ Stopped</div>
                            ${status.reason ? `<div class="text-gray-400">Reason: ${status.reason}</div>` : ''}
                        `;
                    }
                } else {
                    // Error getting status
                    statusDiv.innerHTML = `<div class="text-red-400">❌ Status check failed: ${status.error}</div>`;
                }
                
            } catch (error) {
                console.error(`Error monitoring dashboard ${projectName}:`, error);
                statusDiv.innerHTML = `<div class="text-red-400">❌ Monitoring error: ${error.message}</div>`;
            }
        }
        
        // Check dashboard status manually
        async function checkDashboardStatus(projectName) {
            const statusId = `status-${projectName.replace(/\s+/g, '-').toLowerCase()}`;
            const statusDiv = document.getElementById(statusId);
            
            if (!statusDiv) return;
            
            statusDiv.style.display = 'block';
            statusDiv.innerHTML = '<div class="text-yellow-400">🔍 Checking status...</div>';
            
            try {
                const response = await fetch(`/api/dashboards/${encodeURIComponent(projectName)}/status`);
                const status = await response.json();
                
                if (status.success) {
                    const isRunning = status.status === 'running';
                    const statusColor = isRunning ? 'text-green-400' : 'text-red-400';
                    const statusIcon = isRunning ? '🟢' : '🔴';
                    
                    statusDiv.innerHTML = `
                        <div class="${statusColor}">${statusIcon} ${status.status || 'unknown'}</div>
                        ${status.uptime ? `<div class="text-gray-400">Uptime: ${status.uptime}</div>` : ''}
                        ${status.port ? `<div class="text-blue-400">Port: ${status.port}</div>` : ''}
                        ${status.process_id ? `<div class="text-gray-400">PID: ${status.process_id}</div>` : ''}
                    `;
                } else {
                    statusDiv.innerHTML = `<div class="text-red-400">❌ ${status.error}</div>`;
                }
                
            } catch (error) {
                console.error(`Error checking dashboard status:`, error);
                statusDiv.innerHTML = `<div class="text-red-400">❌ Status check failed</div>`;
            }
        }
        
        // Show dashboard logs
        async function showDashboardLogs(projectName) {
            try {
                const response = await fetch(`/api/dashboards/${encodeURIComponent(projectName)}/logs`);
                const logsData = await response.json();
                
                if (logsData.success) {
                    // Create modal to show logs
                    const modal = document.createElement('div');
                    modal.style.cssText = `
                        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
                        background: rgba(0,0,0,0.8); display: flex; align-items: center; 
                        justify-content: center; z-index: 1000;
                    `;
                    
                    modal.innerHTML = `
                        <div style="background: #1a1a1a; border-radius: 10px; padding: 20px; 
                                    max-width: 80vw; max-height: 80vh; overflow: auto; color: white;">
                            <div style="display: flex; justify-content: between; items: center; margin-bottom: 15px;">
                                <h3 style="margin: 0; color: #4fc3f7;">📝 ${projectName} Logs</h3>
                                <button onclick="this.parentElement.parentElement.parentElement.remove()" 
                                        style="background: #f44336; color: white; border: none; 
                                               border-radius: 5px; padding: 5px 10px; cursor: pointer; float: right;">
                                    ✕ Close
                                </button>
                            </div>
                            <div style="background: #000; padding: 15px; border-radius: 5px; 
                                        font-family: monospace; font-size: 12px; white-space: pre-wrap; 
                                        max-height: 400px; overflow-y: auto;">
${logsData.logs || 'No logs available'}
                            </div>
                            <div style="margin-top: 10px; text-align: right; font-size: 12px; color: #888;">
                                Last updated: ${new Date().toLocaleTimeString()}
                            </div>
                        </div>
                    `;
                    
                    document.body.appendChild(modal);
                    
                    // Close modal on background click
                    modal.addEventListener('click', (e) => {
                        if (e.target === modal) {
                            modal.remove();
                        }
                    });
                    
                } else {
                    alert(`Error getting logs: ${logsData.error}`);
                }
                
            } catch (error) {
                console.error(`Error showing logs for ${projectName}:`, error);
                alert('Failed to load logs');
            }
        }
        
        // Load joke data
        async function loadJoke() {
            const element = document.getElementById('joke-content');
            if (!element) {
                console.error('Joke content element not found');
                return;
            }
            
            try {
                const response = await fetch('/api/joke');
                const data = await response.json();
                
                if (data.error) {
                    element.innerHTML = `<div class="error">❌ ${data.error}</div>`;
                } else {
                    // Store joke data globally with unique ID
                    const jokeId = `joke_${Date.now()}`;
                    window.dashboardData.jokes = [data];
                    window.dashboardData.currentJoke = data;
                    window.dashboardData.currentJokeId = jokeId;
                    
                    // Create joke content with feedback buttons
                    element.innerHTML = `
                        <div style="margin-bottom: 15px;">
                            ${data.joke || 'No joke available'}
                        </div>
                        <div style="display: flex; gap: 10px; justify-content: center; align-items: center;">
                            <button onclick="handleJokeFeedback('like', this)" 
                                   style="background: #4CAF50; color: white; padding: 8px 12px; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; display: flex; align-items: center; gap: 4px;">
                                👍 Like
                            </button>
                            <button onclick="handleJokeFeedback('dislike', this)" 
                                   style="background: #f44336; color: white; padding: 8px 12px; border: none; border-radius: 6px; cursor: pointer; font-size: 12px; display: flex; align-items: center; gap: 4px;">
                                👎 Dislike
                            </button>
                            <button onclick="loadNewJoke()" 
                                   style="background: #2196F3; color: white; padding: 8px 12px; border: none; border-radius: 6px; cursor: pointer; font-size: 12px;">
                                🔄 New Joke
                            </button>
                        </div>
                    `;
                }
            } catch (error) {
                console.error('Error loading joke:', error);
                element.innerHTML = `<div class="error">❌ Failed to load joke</div>`;
            }
        }
        
        // Load weather data
        async function loadWeather() {
            const element = document.getElementById('weather-content');
            try {
                const response = await fetch('/api/weather');
                const data = await response.json();
                
                if (data.error) {
                    element.innerHTML = `<div class="error">❌ ${data.error}</div>`;
                } else {
                    // Store weather data globally
                    window.dashboardData.weather = [data];
                    
                    // Create forecast preview (next 3 days)
                    let forecastHtml = '';
                    if (data.forecast && data.forecast.length > 0) {
                        const nextThreeDays = data.forecast.slice(0, 3);
                        forecastHtml = `
                            <div style="display: flex; gap: 8px; margin-top: 8px; font-size: 11px;">
                                ${nextThreeDays.map(f => `
                                    <div style="text-align: center; flex: 1; background: rgba(255,255,255,0.1); padding: 4px; border-radius: 4px;">
                                        <div style="font-weight: bold;">${f.day}</div>
                                        <div style="margin: 2px 0;">🌤️</div>
                                        <div>${f.high}°/${f.low}°</div>
                                        ${f.precipitation_chance > 30 ? `<div style="color: #87ceeb;">☔ ${f.precipitation_chance}%</div>` : ''}
                                    </div>
                                `).join('')}
                            </div>
                        `;
                    }
                    
                    element.innerHTML = `
                        <div style="text-align: center;">
                            <div style="font-size: 16px; font-weight: bold;">${data.temperature}</div>
                            <div style="font-size: 12px; margin: 2px 0;">${data.description}</div>
                            <div style="font-size: 10px; opacity: 0.8;">${data.location}</div>
                            ${forecastHtml}
                        </div>
                    `;
                }
            } catch (error) {
                console.error('Error loading weather:', error);
                element.innerHTML = `<div class="error">❌ Failed to load weather</div>`;
            }
        }
        
        // Load AI summary
        async function loadAISummary() {
            const element = document.getElementById('ai-summary-content');
            if (!element) {
                console.log('AI summary element not found');
                return;
            }
            
            try {
                const response = await fetch('/api/ai/summary');
                const data = await response.json();
                
                if (data.error || data.summary.startsWith('Error')) {
                    element.innerHTML = `<div class="error text-xs">❌ ${data.error || data.summary}</div>`;
                } else if (data.summary && data.data_sources) {
                    // Store AI summary data globally
                    window.dashboardData.aiSummary = data;
                    
                    const timestamp = data.timestamp ? new Date(data.timestamp).toLocaleTimeString() : 'Unknown';
                    const dataSourcesInfo = `📊 Sources: ${data.data_sources.emails || 0} emails, ${data.data_sources.events || 0} events, ${data.data_sources.news || 0} news, ${data.data_sources.github || 0} GitHub`;
                    
                    element.innerHTML = `
                        <div class="text-xs text-left">
                            <div class="font-semibold mb-1">📝 5-Minute AI Summary</div>
                            <div class="mb-2">${data.summary}</div>
                            <div class="text-xs opacity-75">${dataSourcesInfo}</div>
                            <div class="text-xs opacity-50">Updated: ${timestamp}</div>
                        </div>
                    `;
                } else {
                    element.innerHTML = `<div class="text-xs">📝 AI summary unavailable</div>`;
                }
            } catch (error) {
                console.error('Error loading AI summary:', error);
                element.innerHTML = `<div class="error text-xs">❌ Failed to load AI summary</div>`;
            }
        }
        
        // Refresh AI summary manually
        async function refreshAISummary() {
            const element = document.getElementById('ai-summary-content');
            if (element) {
                element.classList.add('loading');
                element.innerHTML = 'Refreshing AI summary...';
                await loadAISummary();
                element.classList.remove('loading');
            }
        }
        
        // Load data on page load
        loadAllData();
        
        // Auto-refresh every 5 minutes
        setInterval(loadAllData, 5 * 60 * 1000);
        
        // AI Summary refresh every 5 minutes (separate from main data refresh)
        setInterval(loadAISummary, 5 * 60 * 1000);

        // Modal system for detailed item views
        function showModal(item, items, index, category) {
            const modal = document.getElementById('detail-modal');
            const title = document.getElementById('modal-title');
            const content = document.getElementById('modal-content');
            const counter = document.getElementById('item-counter');
            const prevBtn = document.getElementById('prev-item');
            const nextBtn = document.getElementById('next-item');
            
            if (!modal || !title || !content || !counter || !prevBtn || !nextBtn) {
                console.error('Modal elements not found:', {
                    modal: !!modal,
                    title: !!title, 
                    content: !!content,
                    counter: !!counter,
                    prevBtn: !!prevBtn,
                    nextBtn: !!nextBtn
                });
                return;
            }
            
            // Update global state
            currentItems = items;
            currentIndex = index;
            currentCategory = category;
            
            // Update modal content
            title.textContent = getItemTitle(item, category);
            content.innerHTML = getDetailedItemContent(item, category);
            counter.textContent = `${index + 1} of ${items.length}`;
            
            // Update navigation buttons
            prevBtn.disabled = index === 0;
            nextBtn.disabled = index === items.length - 1;
            
            // Show modal
            modal.style.display = 'block';
        }
        
        function closeModal() {
            const modal = document.getElementById('detail-modal');
            if (modal) {
                modal.style.display = 'none';
            }
        }
        
        function showPreviousItem() {
            if (currentIndex > 0) {
                currentIndex--;
                showModal(currentItems[currentIndex], currentItems, currentIndex, currentCategory);
            }
        }
        
        function showNextItem() {
            if (currentIndex < currentItems.length - 1) {
                currentIndex++;
                showModal(currentItems[currentIndex], currentItems, currentIndex, currentCategory);
            }
        }
        
        function getItemTitle(item, category) {
            switch (category) {
                case 'calendar':
                    return item.summary || item.title || 'Calendar Event';
                case 'email':
                    return item.subject || 'Email';
                case 'github':
                    return item.title || 'GitHub Issue';
                case 'news':
                    return item.title || 'News Article';
                case 'weather':
                    return 'Weather Details';
                case 'jokes':
                    return 'Daily Joke';
                case 'music':
                    return item.title || 'Music Track';
                case 'vanity':
                    return item.title || 'Vanity Alert';
                case 'liked_items':
                    return `❤️ ${item.title || 'Liked Item'}`;
                default:
                    return 'Details';
            }
        }
        
        function getDetailedItemContent(item, category) {
            let content = '';
            
            switch (category) {
                case 'calendar':
                    content = `
                        <div class="detail-section">
                            <h4>Event Details</h4>
                            <div class="detail-meta">
                                <div class="meta-item">
                                    <span class="meta-label">Title:</span>
                                    <span class="meta-value">${item.summary || item.title || 'No title'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Time:</span>
                                    <span class="meta-value">${item.time || formatDateTime(item.start) + ' - ' + formatDateTime(item.end)}</span>
                                </div>
                                ${item.location ? `<div class="meta-item">
                                    <span class="meta-label">Location:</span>
                                    <span class="meta-value">${item.location}</span>
                                </div>` : ''}
                                ${item.organizer ? `<div class="meta-item">
                                    <span class="meta-label">Organizer:</span>
                                    <span class="meta-value">${item.organizer}</span>
                                </div>` : ''}
                                <div class="meta-item">
                                    <span class="meta-label">Status:</span>
                                    <span class="meta-value">${item.status || 'Confirmed'}</span>
                                </div>
                                ${item.is_all_day ? `<div class="meta-item">
                                    <span class="meta-label">Duration:</span>
                                    <span class="meta-value">All Day Event</span>
                                </div>` : ''}
                            </div>
                            ${item.description ? `<h4>Description</h4>
                            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin: 10px 0; line-height: 1.6;">
                                ${item.description}
                            </div>` : ''}
                            ${item.attendees && item.attendees.length > 0 ? `
                                <h4>Attendees (${item.attendees.length})</h4>
                                <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin: 10px 0;">
                                    ${item.attendees.join(', ')}
                                </div>
                            ` : ''}
                            <div style="margin-top: 20px; display: flex; gap: 10px; flex-wrap: wrap;">
                                <a href="${item.html_link || item.calendar_url || 'https://calendar.google.com/calendar'}" target="_blank" 
                                   style="background: #4285f4; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   📅 Open in Google Calendar
                                </a>
                                ${item.location ? `
                                <a href="https://maps.google.com/maps?q=${encodeURIComponent(item.location)}" target="_blank"
                                   style="background: #34a853; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   🗺️ View Location
                                </a>` : ''}
                                ${item.organizer ? `
                                <a href="mailto:${item.organizer}?subject=Re: ${item.title || item.summary || ''}" 
                                   style="background: #fbbc04; color: black; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   ✉️ Email Organizer
                                </a>` : ''}
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'email':
                    content = `
                        <div class="detail-section">
                            <div class="detail-meta">
                                <div class="meta-item">
                                    <span class="meta-label">From:</span>
                                    <span class="meta-value">${item.from || item.sender || 'Unknown'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Subject:</span>
                                    <span class="meta-value">${item.subject || 'No subject'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Date:</span>
                                    <span class="meta-value">${item.date || 'Unknown'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Status:</span>
                                    <span class="meta-value">${item.read ? 'Read' : 'Unread'}</span>
                                </div>
                                ${item.labels && item.labels.length > 0 ? `
                                <div class="meta-item">
                                    <span class="meta-label">Labels:</span>
                                    <span class="meta-value">${item.labels.join(', ')}</span>
                                </div>` : ''}
                            </div>
                            <h4>Email Content</h4>
                            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin: 10px 0; line-height: 1.6;">
                                ${item.body || item.snippet || 'No content available'}
                            </div>
                            ${item.attachments && item.attachments.length > 0 ? `
                                <h4>Attachments (${item.attachments.length})</h4>
                                <div>${item.attachments.join(', ')}</div>
                            ` : ''}
                            <div style="margin-top: 20px; display: flex; gap: 10px;">
                                <a href="${item.gmail_url || 'https://mail.google.com/mail/u/0/#inbox'}" target="_blank" 
                                   style="background: #4285f4; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   📧 Open in Gmail
                                </a>
                                <a href="mailto:${item.from || item.sender || ''}?subject=Re: ${item.subject || ''}" 
                                   style="background: #34a853; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   ↩️ Reply
                                </a>
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'github':
                    content = `
                        <div class="detail-section">
                            <div class="detail-meta">
                                <div class="meta-item">
                                    <span class="meta-label">Repository:</span>
                                    <span class="meta-value">${item.repository || 'Unknown'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Type:</span>
                                    <span class="meta-value" style="color: ${item.type === 'Review Requested' ? '#ff9800' : '#2196f3'}">
                                        ${item.type || 'Issue'} #${item.number || ''}
                                    </span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">State:</span>
                                    <span class="meta-value">${item.state || 'open'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Author:</span>
                                    <span class="meta-value">${item.user || 'Unknown'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Created:</span>
                                    <span class="meta-value">${formatDateTime(item.created_at) || 'Unknown'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Updated:</span>
                                    <span class="meta-value">${formatDateTime(item.updated_at) || 'Unknown'}</span>
                                </div>
                                ${item.labels && item.labels.length > 0 ? `
                                <div class="meta-item">
                                    <span class="meta-label">Labels:</span>
                                    <span class="meta-value">${item.labels.join(', ')}</span>
                                </div>` : ''}
                                ${item.assignees && item.assignees.length > 0 ? `
                                <div class="meta-item">
                                    <span class="meta-label">Assignees:</span>
                                    <span class="meta-value">${item.assignees.join(', ')}</span>
                                </div>` : ''}
                            </div>
                            <h4>${item.type === 'Review Requested' ? 'Pull Request' : 'Issue'} Description</h4>
                            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin: 10px 0; line-height: 1.6;">
                                ${item.body || 'No description available'}
                            </div>
                            <div style="margin-top: 20px; display: flex; gap: 10px; flex-wrap: wrap;">
                                <a href="${item.html_url || item.github_url || '#'}" target="_blank" 
                                   style="background: #24292e; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   <svg height="16" width="16" style="fill: currentColor; vertical-align: middle; margin-right: 8px;" viewBox="0 0 16 16">
                                       <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0016 8c0-4.42-3.58-8-8-8z"></path>
                                   </svg>
                                   View on GitHub
                                </a>
                                ${item.repository ? `
                                <a href="https://github.com/${item.repository}" target="_blank"
                                   style="background: #0366d6; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   📁 Repository
                                </a>` : ''}
                                ${item.user ? `
                                <a href="https://github.com/${item.user}" target="_blank"
                                   style="background: #28a745; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   👤 Author Profile
                                </a>` : ''}
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'news':
                    content = `
                        <div class="detail-section">
                            <div class="detail-meta">
                                <div class="meta-item">
                                    <span class="meta-label">Source:</span>
                                    <span class="meta-value">${item.source || 'Unknown'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Published:</span>
                                    <span class="meta-value">${item.published_at || item.pubDate || 'Unknown'}</span>
                                </div>
                                ${item.category ? `<div class="meta-item">
                                    <span class="meta-label">Category:</span>
                                    <span class="meta-value">${item.category}</span>
                                </div>` : ''}
                                ${item.score ? `<div class="meta-item">
                                    <span class="meta-label">Score:</span>
                                    <span class="meta-value">${item.score}</span>
                                </div>` : ''}
                                ${item.comments ? `<div class="meta-item">
                                    <span class="meta-label">Discussion:</span>
                                    <span class="meta-value">${item.comments}</span>
                                </div>` : ''}
                            </div>
                            <h4>Article Summary</h4>
                            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin: 10px 0; line-height: 1.6;">
                                ${item.description || item.summary || 'No description available'}
                            </div>
                            <div style="margin-top: 20px; display: flex; gap: 10px; flex-wrap: wrap;">
                                ${item.url || item.link ? `
                                <a href="${item.url || item.link}" target="_blank" 
                                   style="background: #ff6600; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   📰 Read Full Article
                                </a>` : ''}
                                ${item.hn_url && item.hn_url !== 'https://news.ycombinator.com' ? `
                                <a href="${item.hn_url}" target="_blank"
                                   style="background: #ff6600; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   💬 HN Discussion
                                </a>` : ''}
                                ${item.source === 'Hacker News' ? `
                                <a href="https://news.ycombinator.com" target="_blank"
                                   style="background: #828282; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   🏠 Hacker News Home
                                </a>` : ''}
                                <a href="https://news.google.com/search?q=${encodeURIComponent(item.title || '')}" target="_blank"
                                   style="background: #4285f4; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   🔍 Google News Search
                                </a>
                            </div>
                            <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                                <h5 style="margin-bottom: 10px; color: #e0e0e0;">Help Train Our AI Assistant:</h5>
                                <div style="display: flex; gap: 10px; justify-content: center;">
                                    <button onclick="saveFeedback(${JSON.stringify(item).replace(/"/g, '&quot;')}, 'news', 'like', this)" 
                                           style="background: #4CAF50; color: white; padding: 12px 20px; border: none; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 8px; font-size: 14px; transition: all 0.3s ease;">
                                        👍 Like
                                    </button>
                                    <button onclick="saveFeedback(${JSON.stringify(item).replace(/"/g, '&quot;')}, 'news', 'dislike', this)" 
                                           style="background: #f44336; color: white; padding: 12px 20px; border: none; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 8px; font-size: 14px; transition: all 0.3s ease;">
                                        👎 Dislike
                                    </button>
                                </div>
                                <p style="font-size: 12px; color: #999; text-align: center; margin-top: 8px; margin-bottom: 0;">
                                    Your feedback helps personalize content and train the Ollama AI assistant
                                </p>
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'weather':
                    content = `
                        <div class="detail-section">
                            <div class="detail-meta">
                                <div class="meta-item">
                                    <span class="meta-label">Location:</span>
                                    <span class="meta-value">${item.location || 'Unknown'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Temperature:</span>
                                    <span class="meta-value">${item.temperature || 'Unknown'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Condition:</span>
                                    <span class="meta-value">${item.condition || item.description || 'Unknown'}</span>
                                </div>
                                ${item.humidity ? `<div class="meta-item">
                                    <span class="meta-label">Humidity:</span>
                                    <span class="meta-value">${item.humidity}${item.humidity.toString().includes('%') ? '' : '%'}</span>
                                </div>` : ''}
                                ${item.wind_speed ? `<div class="meta-item">
                                    <span class="meta-label">Wind:</span>
                                    <span class="meta-value">${item.wind_speed}</span>
                                </div>` : ''}
                                ${item.pressure ? `<div class="meta-item">
                                    <span class="meta-label">Pressure:</span>
                                    <span class="meta-value">${item.pressure}</span>
                                </div>` : ''}
                                ${item.visibility ? `<div class="meta-item">
                                    <span class="meta-label">Visibility:</span>
                                    <span class="meta-value">${item.visibility}</span>
                                </div>` : ''}
                                ${item.uv_index ? `<div class="meta-item">
                                    <span class="meta-label">UV Index:</span>
                                    <span class="meta-value">${item.uv_index}</span>
                                </div>` : ''}
                            </div>
                            ${item.forecast && item.forecast.length > 0 ? `
                                <h4>5-Day Weather Forecast</h4>
                                <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin: 10px 0;">
                                    ${item.forecast.map(f => `
                                        <div style="display: flex; justify-content: space-between; align-items: center; padding: 8px 0; border-bottom: 1px solid rgba(255,255,255,0.1);">
                                            <div style="flex: 1;">
                                                <strong>${f.day}</strong>
                                                <div style="font-size: 12px; color: #ccc;">${f.date}</div>
                                            </div>
                                            <div style="flex: 2; text-align: center;">
                                                <div style="font-size: 14px;">${f.condition}</div>
                                                ${f.precipitation_chance > 0 ? `<div style="font-size: 12px; color: #87ceeb;">☔ ${f.precipitation_chance}% chance</div>` : ''}
                                            </div>
                                            <div style="flex: 1; text-align: right;">
                                                <span style="font-weight: bold;">${f.high}°</span>/<span style="color: #ccc;">${f.low}°</span>
                                            </div>
                                        </div>
                                    `).join('')}
                                </div>
                            ` : ''}
                            <div style="margin-top: 20px; display: flex; gap: 10px; flex-wrap: wrap;">
                                <a href="https://weather.com/weather/today/l/${encodeURIComponent(item.location || 'current location')}" target="_blank" 
                                   style="background: #0077be; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   🌤️ Weather.com
                                </a>
                                <a href="https://www.accuweather.com" target="_blank"
                                   style="background: #ef8f00; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   🌡️ AccuWeather
                                </a>
                                <a href="https://www.weather.gov" target="_blank"
                                   style="background: #1e3d59; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   🏛️ National Weather Service
                                </a>
                                <a href="https://weather.apple.com" target="_blank"
                                   style="background: #007aff; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   🍎 Apple Weather
                                </a>
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'jokes':
                    content = `
                        <div class="detail-section">
                            <div style="text-align: center; padding: 20px; background: rgba(255,255,255,0.05); border-radius: 15px; margin: 15px 0;">
                                <h4 style="color: #ffd700; margin-bottom: 20px;">😄 Today's Joke</h4>
                                <div style="font-size: 1.2em; line-height: 1.8; margin-bottom: 15px;">
                                    ${item.joke || item.setup || 'No joke available'}
                                    ${item.punchline ? `<br><br><strong style="color: #4fc3f7;">${item.punchline}</strong>` : ''}
                                </div>
                            </div>
                            ${item.category || item.type ? `
                                <div class="detail-meta">
                                    ${item.category ? `<div class="meta-item">
                                        <span class="meta-label">Category:</span>
                                        <span class="meta-value">${item.category}</span>
                                    </div>` : ''}
                                    ${item.type ? `<div class="meta-item">
                                        <span class="meta-label">Type:</span>
                                        <span class="meta-value">${item.type}</span>
                                    </div>` : ''}
                                    ${item.safe !== undefined ? `<div class="meta-item">
                                        <span class="meta-label">Content:</span>
                                        <span class="meta-value">${item.safe ? 'Family Friendly' : 'Adult Humor'}</span>
                                    </div>` : ''}
                                </div>
                            ` : ''}
                            <div style="margin-top: 20px; display: flex; gap: 10px; flex-wrap: wrap; justify-content: center;">
                                <button onclick="location.reload()" 
                                   style="background: #4CAF50; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer;">
                                   🔄 Get New Joke
                                </button>
                                <a href="https://www.reddit.com/r/jokes" target="_blank"
                                   style="background: #ff4500; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   😂 More Jokes (Reddit)
                                </a>
                                <a href="https://www.goodreads.com/quotes/tag/humor" target="_blank"
                                   style="background: #553c1a; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   📚 Funny Quotes
                                </a>
                                <button onclick="navigator.share ? navigator.share({title: 'Funny Joke', text: '${(item.joke || item.setup || '').replace(/'/g, '\\\'')}'}) : alert('Joke copied to memory!')" 
                                   style="background: #2196F3; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer;">
                                   📤 Share Joke
                                </button>
                            </div>
                            <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                                <h5 style="margin-bottom: 10px; color: #e0e0e0;">Help Train Our AI Assistant:</h5>
                                <div style="display: flex; gap: 10px; justify-content: center;">
                                    <button onclick="saveFeedback(${JSON.stringify(item).replace(/"/g, '&quot;')}, 'jokes', 'like', this)" 
                                           style="background: #4CAF50; color: white; padding: 12px 20px; border: none; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 8px; font-size: 14px; transition: all 0.3s ease;">
                                        👍 Like
                                    </button>
                                    <button onclick="saveFeedback(${JSON.stringify(item).replace(/"/g, '&quot;')}, 'jokes', 'dislike', this)" 
                                           style="background: #f44336; color: white; padding: 12px 20px; border: none; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 8px; font-size: 14px; transition: all 0.3s ease;">
                                        👎 Dislike
                                    </button>
                                </div>
                                <p style="font-size: 12px; color: #999; text-align: center; margin-top: 8px; margin-bottom: 0;">
                                    Your feedback helps personalize content and train the Ollama AI assistant
                                </p>
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'music':
                    content = `
                        <div class="detail-section">
                            <div class="detail-meta">
                                <div class="meta-item">
                                    <span class="meta-label">Track:</span>
                                    <span class="meta-value">${item.title || 'Unknown Track'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Artist:</span>
                                    <span class="meta-value">${item.artist || 'Unknown Artist'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Platform:</span>
                                    <span class="meta-value">${item.platform || 'Streaming'}</span>
                                </div>
                                ${item.release_date ? `<div class="meta-item">
                                    <span class="meta-label">Release Date:</span>
                                    <span class="meta-value">${item.release_date}</span>
                                </div>` : ''}
                                ${item.play_count ? `<div class="meta-item">
                                    <span class="meta-label">Play Count:</span>
                                    <span class="meta-value">${item.play_count.toLocaleString()}</span>
                                </div>` : ''}
                                ${item.plays ? `<div class="meta-item">
                                    <span class="meta-label">Monthly Plays:</span>
                                    <span class="meta-value">${item.plays.toLocaleString()}</span>
                                </div>` : ''}
                                ${item.followers ? `<div class="meta-item">
                                    <span class="meta-label">Followers:</span>
                                    <span class="meta-value">${item.followers.toLocaleString()}</span>
                                </div>` : ''}
                                <div class="meta-item">
                                    <span class="meta-label">Type:</span>
                                    <span class="meta-value">${item.type === 'release' ? 'New Release' : 'Streaming Stats'}</span>
                                </div>
                            </div>
                            ${item.type === 'release' ? `
                                <h4>Release Information</h4>
                                <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin: 10px 0;">
                                    Track from ${item.artist} available on ${item.platform}
                                    ${item.release_date ? ` - Released ${item.release_date}` : ''}
                                </div>
                            ` : `
                                <h4>Streaming Analytics</h4>
                                <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin: 10px 0;">
                                    Platform performance metrics for Null Records and My Evil Robot Army
                                </div>
                            `}
                            <div style="margin-top: 20px; display: flex; gap: 10px; flex-wrap: wrap;">
                                ${item.stream_url ? `
                                <a href="${item.stream_url}" target="_blank" 
                                   style="background: #1db954; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   🎵 Listen Now
                                </a>` : ''}
                                <a href="https://nullrecords.bandcamp.com" target="_blank"
                                   style="background: #629aa0; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   🏷️ Null Records
                                </a>
                                <a href="https://soundcloud.com/myevilrobotarmy" target="_blank"
                                   style="background: #ff5500; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   🤖 My Evil Robot Army
                                </a>
                                <a href="https://open.spotify.com/search/My%20Evil%20Robot%20Army" target="_blank"
                                   style="background: #1db954; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   🎧 Spotify Search
                                </a>
                            </div>
                            <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                                <h5 style="margin-bottom: 10px; color: #e0e0e0;">Help Train Our AI Assistant:</h5>
                                <div style="display: flex; gap: 10px; justify-content: center;">
                                    <button onclick="saveFeedback(${JSON.stringify(item).replace(/"/g, '&quot;')}, 'music', 'like', this)" 
                                           style="background: #4CAF50; color: white; padding: 12px 20px; border: none; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 8px; font-size: 14px; transition: all 0.3s ease;">
                                        👍 Like
                                    </button>
                                    <button onclick="saveFeedback(${JSON.stringify(item).replace(/"/g, '&quot;')}, 'music', 'dislike', this)" 
                                           style="background: #f44336; color: white; padding: 12px 20px; border: none; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 8px; font-size: 14px; transition: all 0.3s ease;">
                                        👎 Dislike
                                    </button>
                                </div>
                                <p style="font-size: 12px; color: #999; text-align: center; margin-top: 8px; margin-bottom: 0;">
                                    Your feedback helps personalize content and train the Ollama AI assistant
                                </p>
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'vanity':
                    content = `
                        <div class="detail-section">
                            <div class="detail-meta">
                                <div class="meta-item">
                                    <span class="meta-label">Source:</span>
                                    <span class="meta-value">${item.source || 'Unknown'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Category:</span>
                                    <span class="meta-value" style="color: ${item.category === 'buildly' ? '#4CAF50' : item.category === 'music' ? '#9C27B0' : item.category === 'book' ? '#FF9800' : '#2196F3'}">
                                        ${item.category || item.search_term || 'General'}
                                    </span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Search Term:</span>
                                    <span class="meta-value">${item.search_term || 'N/A'}</span>
                                </div>
                                ${item.confidence_score ? `<div class="meta-item">
                                    <span class="meta-label">Relevance:</span>
                                    <span class="meta-value">${Math.round(item.confidence_score * 100)}% match</span>
                                </div>` : ''}
                                ${item.timestamp ? `<div class="meta-item">
                                    <span class="meta-label">Found:</span>
                                    <span class="meta-value">${formatDateTime(item.timestamp)}</span>
                                </div>` : ''}
                                ${item.is_validated !== undefined ? `<div class="meta-item">
                                    <span class="meta-label">Status:</span>
                                    <span class="meta-value">${item.is_validated ? 'Validated' : 'Pending Review'}</span>
                                </div>` : ''}
                            </div>
                            <h4>Content Preview</h4>
                            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin: 10px 0; line-height: 1.6;">
                                ${item.content || item.snippet || 'No content preview available'}
                            </div>
                            ${item.category ? `
                                <h4>About This Category</h4>
                                <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin: 10px 0;">
                                    ${item.category === 'buildly' ? 'Mentions of Buildly platform and related projects' :
                                      item.category === 'music' ? 'References to Null Records, My Evil Robot Army, or Gregory Lind music' :
                                      item.category === 'book' ? 'Mentions of "Radical Therapy for Software Teams" book' :
                                      item.category === 'gregory_lind' ? 'General mentions of Gregory Lind' :
                                      'General vanity monitoring results'}
                                </div>
                            ` : ''}
                            <div style="margin-top: 20px; display: flex; gap: 10px; flex-wrap: wrap;">
                                ${item.url ? `
                                <a href="${item.url}" target="_blank" 
                                   style="background: #2196F3; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   🔗 View Original
                                </a>` : ''}
                                ${item.category === 'buildly' ? `
                                <a href="https://buildly.io" target="_blank"
                                   style="background: #4CAF50; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   🏢 Buildly.io
                                </a>` : ''}
                                ${item.category === 'music' ? `
                                <a href="https://nullrecords.bandcamp.com" target="_blank"
                                   style="background: #9C27B0; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   🎵 Null Records
                                </a>` : ''}
                                ${item.category === 'book' ? `
                                <a href="https://www.amazon.com/s?k=Radical+Therapy+Software+Teams" target="_blank"
                                   style="background: #FF9800; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   📚 Find Book
                                </a>` : ''}
                                <a href="https://www.google.com/search?q=${encodeURIComponent(item.search_term || item.title || '')}" target="_blank"
                                   style="background: #4285f4; color: white; padding: 10px 20px; border-radius: 5px; text-decoration: none; display: inline-block;">
                                   🔍 Google Search
                                </a>
                            </div>
                            <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.1);">
                                <h5 style="margin-bottom: 10px; color: #e0e0e0;">Help Train Our AI Assistant:</h5>
                                <div style="display: flex; gap: 10px; justify-content: center;">
                                    <button onclick="saveFeedback(${JSON.stringify(item).replace(/"/g, '&quot;')}, 'vanity', 'like', this)" 
                                           style="background: #4CAF50; color: white; padding: 12px 20px; border: none; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 8px; font-size: 14px; transition: all 0.3s ease;">
                                        👍 Like
                                    </button>
                                    <button onclick="saveFeedback(${JSON.stringify(item).replace(/"/g, '&quot;')}, 'vanity', 'dislike', this)" 
                                           style="background: #f44336; color: white; padding: 12px 20px; border: none; border-radius: 8px; cursor: pointer; display: flex; align-items: center; gap: 8px; font-size: 14px; transition: all 0.3s ease;">
                                        👎 Dislike
                                    </button>
                                </div>
                                <p style="font-size: 12px; color: #999; text-align: center; margin-top: 8px; margin-bottom: 0;">
                                    Your feedback helps personalize content and train the Ollama AI assistant
                                </p>
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'liked_items':
                    content = `
                        <div class="detail-section">
                            <div class="detail-meta">
                                <div class="meta-item">
                                    <span class="meta-label">Type:</span>
                                    <span class="meta-value">${item.type || 'Unknown'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Source:</span>
                                    <span class="meta-value">${item.source || 'Unknown'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Category:</span>
                                    <span class="meta-value">${item.category || 'General'}</span>
                                </div>
                                <div class="meta-item">
                                    <span class="meta-label">Liked:</span>
                                    <span class="meta-value">${formatDateTime(item.liked_at)}</span>
                                </div>
                            </div>
                            <h4>Content</h4>
                            <div style="background: rgba(255,255,255,0.05); padding: 15px; border-radius: 8px; margin: 10px 0; line-height: 1.6;">
                                ${item.content || 'No content available'}
                            </div>
                            ${item.metadata && item.metadata.original_item ? `
                                <h4>Original Data</h4>
                                <div style="background: rgba(255,255,255,0.02); padding: 10px; border-radius: 8px; margin: 10px 0; font-family: monospace; font-size: 12px; max-height: 200px; overflow-y: auto;">
                                    <pre>${JSON.stringify(item.metadata.original_item, null, 2)}</pre>
                                </div>
                            ` : ''}
                            <div style="margin-top: 20px; text-align: center;">
                                <p style="color: #4CAF50; font-weight: bold;">❤️ You liked this item!</p>
                                <p style="font-size: 12px; color: #999;">
                                    This item was marked as liked and won't appear in future feeds.
                                </p>
                            </div>
                        </div>
                    `;
                    break;
                    
                default:
                    content = `
                        <div class="detail-section">
                            <pre>${JSON.stringify(item, null, 2)}</pre>
                        </div>
                    `;
            }
            
            return content;
        }
        
        async function saveFeedback(item, category, feedbackType, buttonElement) {
            try {
                const itemId = item.id || item.title || `${category}_${Date.now()}`;
                const feedbackData = {
                    item_id: itemId,
                    item_type: category,
                    feedback_type: feedbackType,
                    item_title: item.title || item.headline || item.track || item.joke || '',
                    item_content: item.content || item.description || item.snippet || item.setup || '',
                    item_metadata: {
                        timestamp: new Date().toISOString(),
                        original_item: item
                    },
                    source_api: category,
                    category: item.category || item.source || '',
                    confidence_score: item.confidence_score || 0.5,
                    notes: `User ${feedbackType} via dashboard modal`
                };
                
                const response = await fetch('/api/feedback', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(feedbackData)
                });
                
                if (response.ok) {
                    const result = await response.json();
                    // Visual feedback
                    const originalText = buttonElement.innerHTML;
                    buttonElement.innerHTML = feedbackType === 'like' ? '✅ Liked!' : '❌ Disliked!';
                    buttonElement.style.opacity = '0.7';
                    
                    // Close modal first
                    const modal = document.querySelector('.modal-overlay');
                    if (modal) {
                        modal.remove();
                    }
                    
                    // Refresh the appropriate content section to show new items
                    setTimeout(async () => {
                        const refreshMap = {
                            'news': 'news-content',
                            'music': 'music-content', 
                            'vanity': 'vanity-content',
                            'jokes': 'joke-content'
                        };
                        
                        const contentId = refreshMap[category];
                        if (contentId) {
                            const element = document.getElementById(contentId);
                            if (element) {
                                element.innerHTML = '<div class="loading">Loading new content...</div>';
                                
                                // Reload the specific API
                                if (category === 'news') {
                                    await loadData('/api/news', 'news-content');
                                } else if (category === 'music') {
                                    await loadData('/api/music', 'music-content');
                                } else if (category === 'vanity') {
                                    await loadData('/api/vanity', 'vanity-content');
                                } else if (category === 'jokes') {
                                    await loadJoke();
                                }
                            }
                        }
                        
                        // Always refresh liked items to show the new like
                        if (feedbackType === 'like') {
                            const likedElement = document.getElementById('liked-items-content');
                            if (likedElement) {
                                likedElement.innerHTML = '<div class="loading">Loading liked items...</div>';
                                await loadData('/api/liked-items', 'liked-items-content');
                            }
                        }
                        
                        // Re-enable click handlers
                        setTimeout(makeItemsClickable, 100);
                    }, 1000);
                    
                    console.log('Feedback saved for AI training:', result);
                } else {
                    throw new Error('Failed to save feedback');
                }
            } catch (error) {
                console.error('Error saving feedback:', error);
                alert('Error saving feedback. Please try again.');
            }
        }
        
        // Joke-specific feedback handler that loads new joke after feedback
        async function handleJokeFeedback(feedbackType, buttonElement) {
            try {
                const jokeData = window.dashboardData.currentJoke;
                if (!jokeData) {
                    console.error('No current joke data found');
                    return;
                }
                
                // Save the feedback first
                await saveFeedback(jokeData, 'jokes', feedbackType, buttonElement);
                
                // Wait a moment for visual feedback, then load new joke
                setTimeout(async () => {
                    const jokeElement = document.getElementById('joke-content');
                    if (jokeElement) {
                        jokeElement.innerHTML = '<div class="loading">Loading new joke...</div>';
                        await loadJoke();
                    }
                }, 2500);
                
            } catch (error) {
                console.error('Error handling joke feedback:', error);
                alert('Error processing joke feedback. Please try again.');
            }
        }
        
        // Load a new joke manually
        async function loadNewJoke() {
            const jokeElement = document.getElementById('joke-content');
            if (jokeElement) {
                jokeElement.innerHTML = '<div class="loading">Loading new joke...</div>';
                await loadJoke();
            }
        }
        
        function formatDateTime(dateTime) {
            if (!dateTime) return 'Unknown';
            try {
                const date = new Date(dateTime.dateTime || dateTime);
                return date.toLocaleString();
            } catch (e) {
                return dateTime.toString();
            }
        }
        
        function makeItemsClickable() {
            // Add click handlers to all items
            const sections = [
                { contentId: 'calendar-content', sectionName: 'calendar' },
                { contentId: 'email-content', sectionName: 'email' },
                { contentId: 'github-content', sectionName: 'github' },
                { contentId: 'news-content', sectionName: 'news' },
                { contentId: 'weather-content', sectionName: 'weather' },
                { contentId: 'joke-content', sectionName: 'jokes' },
                { contentId: 'music-content', sectionName: 'music' },
                { contentId: 'vanity-content', sectionName: 'vanity' },
                { contentId: 'liked-items-content', sectionName: 'liked_items' }
            ];
            
            sections.forEach(section => {
                const container = document.getElementById(section.contentId);
                if (!container) {
                    console.warn(`Container not found: ${section.contentId}`);
                    return;
                }
                
                const items = container.querySelectorAll('.item');
                items.forEach((itemElement, index) => {
                    itemElement.addEventListener('click', () => {
                        // Get the data for this section
                        const sectionData = window.dashboardData?.[section.sectionName] || [];
                        if (sectionData.length > index) {
                            showModal(sectionData[index], sectionData, index, section.sectionName);
                        }
                    });
                });
            });
        }
        
        // Modal event handlers
        document.addEventListener('DOMContentLoaded', () => {
            const modal = document.getElementById('detail-modal');
            const closeBtn = document.querySelector('.close-btn');
            const prevBtn = document.getElementById('prev-item');
            const nextBtn = document.getElementById('next-item');
            
            if (!modal) {
                console.error('Modal element not found');
                return;
            }
            
            // Close modal events
            if (closeBtn) {
                closeBtn.addEventListener('click', closeModal);
            }
            
            modal.addEventListener('click', (e) => {
                if (e.target === modal) {
                    closeModal();
                }
            });
            
            // Navigation events
            if (prevBtn) {
                prevBtn.addEventListener('click', showPreviousItem);
            }
            if (nextBtn) {
                nextBtn.addEventListener('click', showNextItem);
            }
            
            // Keyboard navigation
            document.addEventListener('keydown', (e) => {
                if (modal.style.display === 'block') {
                    switch (e.key) {
                        case 'Escape':
                            closeModal();
                            break;
                        case 'ArrowLeft':
                            showPreviousItem();
                            break;
                        case 'ArrowRight':
                            showNextItem();
                            break;
                    }
                }
            });
        });
        
        // Store dashboard data globally for modal access
        window.dashboardData = {};
        
        // Admin Panel Functions
        function openAdminPanel() {
            document.getElementById('admin-panel').style.display = 'block';
        }
        
        function closeAdminPanel() {
            document.getElementById('admin-panel').style.display = 'none';
            document.getElementById('widget-admin').style.display = 'none';
        }
        
        async function toggleWidget(widgetName) {
            const widget = document.querySelector(`[id*="${widgetName}-content"]`).closest('.widget');
            const toggle = document.getElementById(`toggle-${widgetName}`);
            
            if (toggle.checked) {
                widget.style.display = 'flex';
            } else {
                widget.style.display = 'none';
            }
            
            // Save widget preferences to server
            await saveWidgetSettings(widgetName, toggle.checked);
        }
        
        async function loadWidgetPreferences() {
            try {
                const response = await fetch('/api/admin/settings');
                const settings = await response.json();
                const preferences = settings.widget_visibility || {};
                
                Object.keys(preferences).forEach(widgetName => {
                    const toggle = document.getElementById(`toggle-${widgetName}`);
                    const widget = document.querySelector(`[id*="${widgetName}-content"]`).closest('.widget');
                    
                    if (toggle && widget) {
                        toggle.checked = preferences[widgetName];
                        widget.style.display = preferences[widgetName] ? 'flex' : 'none';
                    }
                });
            } catch (error) {
                console.error('Error loading widget preferences:', error);
            }
        }
        
        function openWidgetAdmin(widgetType) {
            const adminSection = document.getElementById('widget-admin');
            
            if (!adminSection) {
                console.error('widget-admin element not found!');
                return;
            }
            
            let adminContent = `
                <div class="modal-header" style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; border-bottom: 1px solid rgba(255,255,255,0.2); padding-bottom: 10px;">
                    <h2 style="margin: 0; color: #4fc3f7;">Configure ${widgetType.charAt(0).toUpperCase() + widgetType.slice(1)}</h2>
                    <button onclick="closeWidgetAdmin()" style="background: none; border: none; color: #ff6b6b; font-size: 24px; cursor: pointer; padding: 5px; border-radius: 50%; width: 35px; height: 35px; display: flex; align-items: center; justify-content: center;" onmouseover="this.style.background='rgba(255,107,107,0.2)'" onmouseout="this.style.background='none'">&times;</button>
                </div>
            `;
            
            switch(widgetType) {
                case 'calendar':
                    adminContent += `
                        <div class="admin-section">
                            <h3>📅 Google Calendar Integration</h3>
                            <div class="admin-form">
                                <div style="padding: 15px; background: rgba(255,255,255,0.1); border-radius: 10px; margin-bottom: 15px;">
                                    <strong>Connection Status:</strong> <span id="calendar-status">Checking...</span><br>
                                    <strong>Account:</strong> <span id="calendar-account">Loading...</span><br><br>
                                    <button class="admin-btn" onclick="connectGoogleCalendar()">Connect Google Calendar</button>
                                    <button class="admin-btn danger" onclick="disconnectGoogleCalendar()" style="margin-left: 10px;">Disconnect</button>
                                </div>
                                <p style="color: #ccc; font-size: 0.9em;">
                                    Connect your Google Calendar to see upcoming events and meetings in your dashboard.
                                </p>
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'email':
                    adminContent += `
                        <div class="admin-section">
                            <h3>📧 Gmail Integration</h3>
                            <div class="admin-form">
                                <div style="padding: 15px; background: rgba(255,255,255,0.1); border-radius: 10px; margin-bottom: 15px;">
                                    <strong>Connection Status:</strong> <span id="email-status">Checking...</span><br>
                                    <strong>Account:</strong> <span id="email-account">Loading...</span><br><br>
                                    <button class="admin-btn" onclick="connectGmail()">Connect Gmail</button>
                                    <button class="admin-btn danger" onclick="disconnectGmail()" style="margin-left: 10px;">Disconnect</button>
                                </div>
                                <p style="color: #ccc; font-size: 0.9em;">
                                    Connect your Gmail to see unread messages and important emails in your dashboard.
                                </p>
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'news':
                    adminContent += `
                        <div class="admin-section">
                            <h3>📰 News Configuration</h3>
                            <div class="admin-form">
                                <label for="news-source">Add News Source:</label>
                                <input type="text" class="admin-input" id="news-source" placeholder="e.g., TechCrunch, BBC News">
                                <button class="admin-btn" onclick="addNewsSource()">Add Source</button>
                                
                                <label for="news-tag">Add News Tags:</label>
                                <input type="text" class="admin-input" id="news-tag" placeholder="e.g., AI, Machine Learning">
                                <button class="admin-btn" onclick="addNewsTag()">Add Tag</button>
                                
                                <div class="tag-list" id="news-tags">
                                    <!-- Current tags will be loaded here -->
                                </div>
                                
                                <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.2); text-align: right;">
                                    <button class="admin-btn" onclick="closeWidgetAdmin()" style="background: #666; margin-right: 10px;">Cancel</button>
                                    <button class="admin-btn" onclick="saveAndCloseWidget()">Save & Close</button>
                                </div>
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'vanity':
                    adminContent = `
                        <div class="admin-section">
                            <h3>👁️ Vanity Alerts Configuration</h3>
                            <div class="admin-form">
                                <label for="vanity-name">Add Name/Person:</label>
                                <input type="text" class="admin-input" id="vanity-name" placeholder="e.g., Gregory Lind">
                                <button class="admin-btn" onclick="addVanityTerm('name')">Add Name</button>
                                
                                <label for="vanity-company">Add Company/Organization:</label>
                                <input type="text" class="admin-input" id="vanity-company" placeholder="e.g., Buildly Labs">
                                <button class="admin-btn" onclick="addVanityTerm('company')">Add Company</button>
                                
                                <label for="vanity-term">Add Search Term:</label>
                                <input type="text" class="admin-input" id="vanity-term" placeholder="e.g., Radical Therapy for Software Teams">
                                <button class="admin-btn" onclick="addVanityTerm('term')">Add Term</button>
                                
                                <div class="tag-list" id="vanity-terms">
                                    <!-- Current terms will be loaded here -->
                                </div>
                                
                                <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.2); text-align: right;">
                                    <button class="admin-btn" onclick="closeWidgetAdmin()" style="background: #666; margin-right: 10px;">Cancel</button>
                                    <button class="admin-btn" onclick="saveAndCloseWidget()">Save & Close</button>
                                </div>
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'music':
                    adminContent = `
                        <div class="admin-section">
                            <h3>🎵 Music Configuration</h3>
                            <div class="admin-form">
                                <label for="music-artist">Add Band/Artist:</label>
                                <input type="text" class="admin-input" id="music-artist" placeholder="e.g., My Evil Robot Army">
                                <button class="admin-btn" onclick="addMusicTerm('artist')">Add Artist</button>
                                
                                <label for="music-label">Add Record Label:</label>
                                <input type="text" class="admin-input" id="music-label" placeholder="e.g., Null Records">
                                <button class="admin-btn" onclick="addMusicTerm('label')">Add Label</button>
                                
                                <div class="tag-list" id="music-terms">
                                    <!-- Current terms will be loaded here -->
                                </div>
                                
                                <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.2); text-align: right;">
                                    <button class="admin-btn" onclick="closeWidgetAdmin()" style="background: #666; margin-right: 10px;">Cancel</button>
                                    <button class="admin-btn" onclick="saveAndCloseWidget()">Save & Close</button>
                                </div>
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'github':
                    adminContent = `
                        <div class="admin-section">
                            <h3>🐙 GitHub Configuration</h3>
                            <div class="admin-form">
                                <label for="github-username">GitHub Username:</label>
                                <input type="text" class="admin-input" id="github-username" placeholder="e.g., glind">
                                <button class="admin-btn" onclick="updateGitHubSettings()">Update Username</button>
                                
                                <div style="margin-top: 15px; padding: 10px; background: rgba(255,255,255,0.1); border-radius: 5px;">
                                    <strong>Current Token:</strong> ${getCurrentGitHubToken()}
                                </div>
                                
                                <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid rgba(255,255,255,0.2); text-align: right;">
                                    <button class="admin-btn" onclick="closeWidgetAdmin()" style="background: #666; margin-right: 10px;">Cancel</button>
                                    <button class="admin-btn" onclick="saveAndCloseWidget()">Save & Close</button>
                                </div>
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'ticktick':
                    adminContent = `
                        <div class="admin-section">
                            <h3>✅ TickTick Configuration</h3>
                            <div style="padding: 10px; background: rgba(255,255,255,0.1); border-radius: 5px;">
                                <strong>Current Status:</strong> Connected<br>
                                <strong>Username:</strong> ${getCurrentTickTickUser()}<br>
                                <strong>Token Status:</strong> Active
                                <br><br>
                                <button class="admin-btn danger" onclick="disconnectTickTick()">Disconnect TickTick</button>
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'ai':
                    adminContent += `
                        <div class="admin-section">
                            <h3>🤖 AI Assistant Configuration</h3>
                            <div class="admin-form">
                                <div style="padding: 15px; background: rgba(255,255,255,0.1); border-radius: 10px; margin-bottom: 15px;">
                                    <h4>Provider Management</h4>
                                    <div id="ai-providers-list">Loading providers...</div>
                                    <br>
                                    <button class="admin-btn" onclick="addAIProvider()">Add New Provider</button>
                                    <button class="admin-btn" onclick="addNetworkOllama()">Quick: Add Network Ollama</button>
                                    <button class="admin-btn" onclick="detectOllamaModels()">Detect Models</button>
                                    <button class="admin-btn" onclick="loadAIProviders()">Refresh Providers</button>
                                </div>
                                
                                <div style="padding: 15px; background: rgba(255,255,255,0.1); border-radius: 10px; margin-bottom: 15px;">
                                    <h4>Training Data Management</h4>
                                    <div id="ai-training-summary">Loading training summary...</div>
                                    <br>
                                    <button class="admin-btn" onclick="collectAITrainingData()">Collect Training Data</button>
                                    <button class="admin-btn" onclick="startAITraining()">Start Training</button>
                                    <button class="admin-btn" onclick="getTrainingSummary()">View Summary</button>
                                </div>
                                
                                <div style="padding: 15px; background: rgba(255,255,255,0.1); border-radius: 10px;">
                                    <h4>Quick Setup</h4>
                                    <p style="color: #ccc; font-size: 0.9em;">
                                        <strong>Ollama (Local):</strong> http://localhost:11434 (default)<br>
                                        <strong>Ollama (Network):</strong> http://hostname.local:11434 (e.g., pop-os.local:11434)<br>
                                        <strong>OpenAI:</strong> Requires API key from OpenAI<br>
                                        <strong>Gemini:</strong> Requires API key from Google AI Studio
                                    </p>
                                    <div style="margin-top: 10px; padding: 10px; background: rgba(255,193,7,0.2); border-radius: 5px;">
                                        <strong>💡 Network Ollama Setup:</strong><br>
                                        <span style="font-size: 0.8em;">
                                        • Use hostname.local:11434 for network instances<br>
                                        • Example: http://pop-os.local:11434<br>
                                        • Ensure Ollama server allows external connections
                                        </span>
                                    </div>
                                </div>
                                
                                <div class="save-close-buttons">
                                    <button class="admin-btn" onclick="saveAndCloseWidget('ai')">Save & Close</button>
                                    <button class="admin-btn" onclick="closeWidgetAdmin()">Cancel</button>
                                </div>
                            </div>
                        </div>
                    `;
                    break;
                    
                case 'notes':
                    adminContent += `
                        <div class="admin-section">
                            <h3>📝 Notes & Knowledge Configuration</h3>
                            <div class="admin-form">
                                <div style="margin-bottom: 20px;">
                                    <label for="obsidian-vault-path">Obsidian Vault Path:</label>
                                    <input type="text" class="admin-input" id="obsidian-vault-path" placeholder="/Users/yourusername/Documents/ObsidianVault">
                                    <button class="admin-btn" onclick="testObsidianVault()" style="margin-left: 10px; background: #ff9800;">🔍 Test Connection</button>
                                    <p style="color: #ccc; font-size: 0.8em; margin-top: 5px;">
                                        Full path to your Obsidian vault directory (e.g., /Users/username/Documents/MyVault)
                                    </p>
                                </div>
                                
                                <div style="margin-bottom: 20px;">
                                    <label for="gdrive-folder-id">Google Drive Meeting Notes Folder ID:</label>
                                    <input type="text" class="admin-input" id="gdrive-folder-id" placeholder="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms">
                                    <button class="admin-btn" onclick="testGoogleDriveFolder()" style="margin-left: 10px; background: #ff9800;">🔍 Test Connection</button>
                                    <p style="color: #ccc; font-size: 0.8em; margin-top: 5px;">
                                        Google Drive folder ID for meeting notes (find in URL after /folders/)
                                    </p>
                                </div>
                                
                                <div style="margin-bottom: 20px;">
                                    <label>
                                        <input type="checkbox" id="auto-create-tasks" style="margin-right: 10px;">
                                        Automatically create tasks from note TODOs
                                    </label>
                                    <p style="color: #ccc; font-size: 0.8em; margin-top: 5px;">
                                        When enabled, the system will automatically create tasks from TODO items found in notes
                                    </p>
                                </div>
                                
                                <div style="padding: 15px; background: rgba(255,255,255,0.1); border-radius: 10px; margin-bottom: 15px;">
                                    <h4>Connection Status</h4>
                                    <div id="notes-test-results">
                                        <div style="display: flex; align-items: center; margin-bottom: 5px;">
                                            <span class="w-3 h-3 rounded-full bg-gray-500 mr-2" id="test-obsidian-indicator"></span>
                                            <span>Obsidian: <span id="test-obsidian-status">Not tested</span></span>
                                        </div>
                                        <div style="display: flex; align-items: center;">
                                            <span class="w-3 h-3 rounded-full bg-gray-500 mr-2" id="test-gdrive-indicator"></span>
                                            <span>Google Drive: <span id="test-gdrive-status">Not tested</span></span>
                                        </div>
                                    </div>
                                    <button class="admin-btn" onclick="testAllNotesConnections()" style="margin-top: 10px;">🔍 Test All Connections</button>
                                </div>
                                
                                <div style="padding: 15px; background: rgba(255,255,255,0.1); border-radius: 10px; margin-bottom: 15px;">
                                    <h4>Quick Actions</h4>
                                    <button class="admin-btn" onclick="generateTasksFromAllSources()" style="background: #9c27b0;">📋 Extract Tasks from Notes</button>
                                    <button class="admin-btn" onclick="refreshNotesData()" style="background: #2196f3; margin-left: 10px;">🔄 Refresh Notes</button>
                                    <p style="color: #ccc; font-size: 0.8em; margin-top: 10px;">
                                        Extract tasks will scan notes and calendar events for TODO items and create tasks automatically
                                    </p>
                                </div>
                                
                                <div style="padding: 15px; background: rgba(255,235,59,0.1); border-radius: 10px; margin-bottom: 15px;">
                                    <h4>💡 Setup Help</h4>
                                    <p style="color: #ccc; font-size: 0.8em;">
                                        <strong>Obsidian:</strong> Navigate to your vault in Finder/Explorer and copy the full path<br>
                                        <strong>Google Drive:</strong> Open the folder in Google Drive, copy the ID from the URL<br>
                                        <strong>Example:</strong> https://drive.google.com/drive/folders/<span style="color: #ffeb3b;">1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74</span>
                                    </p>
                                </div>
                                
                                <div class="save-close-buttons">
                                    <button class="admin-btn" onclick="saveNotesSettings()">💾 Save Settings</button>
                                    <button class="admin-btn" onclick="closeWidgetAdmin()" style="background: #666; margin-left: 10px;">Cancel</button>
                                </div>
                            </div>
                        </div>
                    `;
                    break;
                    
                default:
                    adminContent = `
                        <div class="admin-section">
                            <h3>Configuration for ${widgetType}</h3>
                            <p>Configuration options coming soon...</p>
                        </div>
                    `;
            }
            
            adminSection.innerHTML = adminContent;
            adminSection.style.display = 'block';
            
            // Add ESC key listener
            document.addEventListener('keydown', handleEscapeKey);
            
            // Add click-outside-to-close
            adminSection.onclick = function(event) {
                if (event.target === adminSection) {
                    closeWidgetAdmin();
                }
            };
            
            // Load current settings
            loadCurrentSettings(widgetType);
            
            // Special loading for AI widget
            if (widgetType === 'ai') {
                setTimeout(() => loadAIAdminData(), 100);
            }
        }
        
        async function addNewsSource() {
            const input = document.getElementById('news-source');
            if (input.value.trim()) {
                try {
                    console.log('Adding news source:', input.value.trim());
                    // Get current settings
                    const response = await fetch('/api/admin/settings');
                    const settings = await response.json();
                    const newsConfig = settings.news_config || { sources: [], tags: [] };
                    
                    // Add new source
                    if (!newsConfig.sources.includes(input.value.trim())) {
                        newsConfig.sources.push(input.value.trim());
                        console.log('Updated news config:', newsConfig);
                        await saveNewsConfig(newsConfig);
                        await loadCurrentSettings('news');
                        input.value = '';
                        console.log('News source added successfully');
                    } else {
                        console.log('News source already exists');
                    }
                } catch (error) {
                    console.error('Error adding news source:', error);
                }
            }
        }
        
        async function addNewsTag() {
            const input = document.getElementById('news-tag');
            if (input.value.trim()) {
                try {
                    console.log('Adding news tag:', input.value.trim());
                    // Get current settings
                    const response = await fetch('/api/admin/settings');
                    const settings = await response.json();
                    const newsConfig = settings.news_config || { sources: [], tags: [] };
                    
                    // Add new tag
                    if (!newsConfig.tags.includes(input.value.trim())) {
                        newsConfig.tags.push(input.value.trim());
                        console.log('Updated news config:', newsConfig);
                        await saveNewsConfig(newsConfig);
                        await loadCurrentSettings('news');
                        input.value = '';
                        console.log('News tag added successfully');
                    } else {
                        console.log('News tag already exists');
                    }
                } catch (error) {
                    console.error('Error adding news tag:', error);
                }
            }
        }
        
        async function addVanityTerm(type) {
            const input = document.getElementById(`vanity-${type}`);
            if (input.value.trim()) {
                try {
                    // Get current settings
                    const response = await fetch('/api/admin/settings');
                    const settings = await response.json();
                    const vanityConfig = settings.vanity_config || { names: [], companies: [], terms: [] };
                    
                    // Add new term to appropriate array
                    const termValue = input.value.trim();
                    let arrayKey = type === 'name' ? 'names' : type === 'company' ? 'companies' : 'terms';
                    
                    if (!vanityConfig[arrayKey].includes(termValue)) {
                        vanityConfig[arrayKey].push(termValue);
                        await saveVanityConfig(vanityConfig);
                        loadCurrentSettings('vanity');
                        input.value = '';
                    }
                } catch (error) {
                    console.error(`Error adding vanity ${type}:`, error);
                }
            }
        }
        
        async function addMusicTerm(type) {
            const input = document.getElementById(`music-${type}`);
            if (input.value.trim()) {
                try {
                    // Get current settings
                    const response = await fetch('/api/admin/settings');
                    const settings = await response.json();
                    const musicConfig = settings.music_config || { artists: [], labels: [] };
                    
                    // Add new term to appropriate array
                    const termValue = input.value.trim();
                    let arrayKey = type === 'artist' ? 'artists' : 'labels';
                    
                    if (!musicConfig[arrayKey].includes(termValue)) {
                        musicConfig[arrayKey].push(termValue);
                        await saveMusicConfig(musicConfig);
                        loadCurrentSettings('music');
                        input.value = '';
                    }
                } catch (error) {
                    console.error(`Error adding music ${type}:`, error);
                }
            }
        }
        
        function getCurrentGitHubToken() {
            // This would need to be implemented with proper API call
            return 'GitHub Token (Configured)';
        }
        
        function getCurrentTickTickUser() {
            return 'Connected User';
        }
        
        async function updateGitHubSettings() {
            const username = document.getElementById('github-username').value;
            if (username.trim()) {
                try {
                    await saveGithubConfig({ username: username.trim() });
                    console.log('GitHub username updated:', username);
                } catch (error) {
                    console.error('Error updating GitHub settings:', error);
                }
            }
        }
        
        function disconnectTickTick() {
            if (confirm('Are you sure you want to disconnect TickTick?')) {
                console.log('Disconnecting TickTick');
                // Implementation for disconnecting TickTick
            }
        }
        
        function closeWidgetAdmin() {
            const adminSection = document.getElementById('widget-admin');
            if (adminSection) {
                adminSection.style.display = 'none';
            }
            // Remove ESC key listener
            document.removeEventListener('keydown', handleEscapeKey);
        }
        
        function saveAndCloseWidget() {
            // Settings are auto-saved when items are added, so just close
            closeWidgetAdmin();
        }
        
        function handleEscapeKey(event) {
            if (event.key === 'Escape') {
                closeWidgetAdmin();
            }
        }
        
        function connectGoogleCalendar() {
            window.open('/auth/google/calendar', '_blank');
        }
        
        function disconnectGoogleCalendar() {
            if (confirm('Are you sure you want to disconnect Google Calendar?')) {
                fetch('/auth/google/disconnect', { method: 'POST' })
                    .then(() => location.reload());
            }
        }
        
        function connectGmail() {
            window.open('/auth/google/gmail', '_blank');
        }
        
        function disconnectGmail() {
            if (confirm('Are you sure you want to disconnect Gmail?')) {
                fetch('/auth/google/disconnect', { method: 'POST' })
                    .then(() => location.reload());
            }
        }
        
        async function loadCurrentSettings(widgetType) {
            try {
                const response = await fetch('/api/admin/settings');
                const settings = await response.json();
                
                switch(widgetType) {
                    case 'news':
                        const newsConfig = settings.news_config || { sources: [], tags: [] };
                        const tagsContainer = document.getElementById('news-tags');
                        if (tagsContainer) {
                            tagsContainer.innerHTML = `
                                <div><strong>Sources:</strong> ${newsConfig.sources.join(', ')}</div>
                                <div><strong>Tags:</strong> ${newsConfig.tags.join(', ')}</div>
                            `;
                        }
                        break;
                        
                    case 'vanity':
                        const vanityConfig = settings.vanity_config || { names: [], companies: [], terms: [] };
                        const vanityContainer = document.getElementById('vanity-terms');
                        if (vanityContainer) {
                            vanityContainer.innerHTML = `
                                <div><strong>Names:</strong> ${vanityConfig.names.join(', ')}</div>
                                <div><strong>Companies:</strong> ${vanityConfig.companies.join(', ')}</div>
                                <div><strong>Terms:</strong> ${vanityConfig.terms.join(', ')}</div>
                            `;
                        }
                        break;
                        
                    case 'music':
                        const musicConfig = settings.music_config || { artists: [], labels: [] };
                        const musicContainer = document.getElementById('music-terms');
                        if (musicContainer) {
                            musicContainer.innerHTML = `
                                <div><strong>Artists:</strong> ${musicConfig.artists.join(', ')}</div>
                                <div><strong>Labels:</strong> ${musicConfig.labels.join(', ')}</div>
                            `;
                        }
                        break;
                        
                    case 'github':
                        const githubConfig = settings.github_config || { username: 'glind' };
                        const usernameInput = document.getElementById('github-username');
                        if (usernameInput) {
                            usernameInput.value = githubConfig.username;
                        }
                        break;
                        
                    case 'notes':
                        // Load notes settings using dedicated function
                        await loadNotesSettings();
                        break;
                }
            } catch (error) {
                console.error('Error loading current settings:', error);
            }
        }
        
        // Load widget preferences on page load
        document.addEventListener('DOMContentLoaded', function() {
            loadWidgetPreferences();
            loadAIProviders();
        });
        
        // AI Chat functionality
        let currentConversation = null;
        let aiProviders = [];
        
        async function loadAIProviders() {
            try {
                const response = await fetch('/api/ai/providers');
                const data = await response.json();
                
                if (data.error) {
                    console.log('AI Assistant not available:', data.error);
                    document.getElementById('ai-provider-select').innerHTML = '<option value="">AI Not Available</option>';
                    return;
                }
                
                aiProviders = data.providers || [];
                const select = document.getElementById('ai-provider-select');
                select.innerHTML = '';
                
                if (aiProviders.length === 0) {
                    select.innerHTML = '<option value="">No providers configured</option>';
                } else {
                    aiProviders.forEach(provider => {
                        const option = document.createElement('option');
                        option.value = provider.name;
                        option.textContent = `${provider.name} (${provider.provider_type}) ${provider.health_status ? '✅' : '❌'}`;
                        if (provider.is_default) {
                            option.selected = true;
                        }
                        select.appendChild(option);
                    });
                }
            } catch (error) {
                console.error('Error loading AI providers:', error);
                document.getElementById('ai-provider-select').innerHTML = '<option value="">Error loading providers</option>';
            }
        }
        
        function handleChatKeyPress(event) {
            if (event.key === 'Enter' && !event.shiftKey) {
                event.preventDefault();
                sendChatMessage();
            }
        }
        
        async function sendChatMessage() {
            const input = document.getElementById('ai-chat-input');
            const message = input.value.trim();
            const provider = document.getElementById('ai-provider-select').value;
            
            if (!message) return;
            if (!provider) {
                alert('Please select an AI provider first');
                return;
            }
            
            // Clear input and disable button
            input.value = '';
            const sendBtn = document.getElementById('ai-chat-send');
            sendBtn.disabled = true;
            sendBtn.textContent = 'Sending...';
            
            // Add user message to chat
            addChatMessage('user', message);
            
            // Show typing indicator
            showTypingIndicator();
            
            try {
                const response = await fetch('/api/ai/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        message: message,
                        conversation_id: currentConversation,
                        provider: provider
                    })
                });
                
                const data = await response.json();
                
                if (data.error) {
                    addChatMessage('system', `Error: ${data.error}`);
                } else {
                    currentConversation = data.conversation_id;
                    addChatMessage('assistant', data.response);
                }
                
            } catch (error) {
                console.error('Chat error:', error);
                addChatMessage('system', 'Error: Could not send message');
            } finally {
                hideTypingIndicator();
                sendBtn.disabled = false;
                sendBtn.textContent = 'Send';
                input.focus();
            }
        }
        
        function addChatMessage(role, content) {
            const messagesContainer = document.getElementById('ai-chat-messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = `chat-message ${role}`;
            
            const contentDiv = document.createElement('div');
            contentDiv.textContent = content;
            
            const timeDiv = document.createElement('div');
            timeDiv.className = 'chat-message-time';
            timeDiv.textContent = new Date().toLocaleTimeString();
            
            messageDiv.appendChild(contentDiv);
            messageDiv.appendChild(timeDiv);
            messagesContainer.appendChild(messageDiv);
            
            // Scroll to bottom
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        }
        
        function showTypingIndicator() {
            const indicator = document.createElement('div');
            indicator.className = 'typing-indicator';
            indicator.id = 'typing-indicator';
            indicator.textContent = 'AI is typing...';
            document.getElementById('ai-chat-messages').appendChild(indicator);
            document.getElementById('ai-chat-messages').scrollTop = document.getElementById('ai-chat-messages').scrollHeight;
        }
        
        function hideTypingIndicator() {
            const indicator = document.getElementById('typing-indicator');
            if (indicator) {
                indicator.remove();
            }
        }
        
        async function collectAITrainingData() {
            try {
                const response = await fetch('/api/ai/training/collect', {
                    method: 'POST'
                });
                const data = await response.json();
                
                if (data.success) {
                    alert(`Training data collected: ${data.samples_collected} samples`);
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (error) {
                console.error('Error collecting training data:', error);
                alert('Error collecting training data');
            }
        }
        
        async function startAITraining() {
            const provider = document.getElementById('ai-provider-select').value;
            
            if (!provider) {
                alert('Please select an AI provider first');
                return;
            }
            
            if (!confirm('Start AI model training? This may take some time.')) {
                return;
            }
            
            try {
                const response = await fetch('/api/ai/training/start', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        provider: provider
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert(`Training started: ${data.training_id}\\nResult: ${data.result.status}`);
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (error) {
                console.error('Error starting training:', error);
                alert('Error starting AI training');
            }
        }
        
        async function addAIProvider() {
            const name = prompt('Provider name:');
            if (!name) return;
            
            const type = prompt('Provider type (ollama, openai, gemini):');
            if (!type) return;
            
            let config = {};
            
            if (type.toLowerCase() === 'ollama') {
                const baseUrl = prompt('Ollama base URL:', 'http://localhost:11434');
                const modelName = prompt('Model name:', 'llama2');
                if (!baseUrl) {
                    alert('Base URL is required for Ollama');
                    return;
                }
                config = {
                    base_url: baseUrl,
                    model_name: modelName,
                    is_active: true,
                    is_default: false
                };
            } else if (type.toLowerCase() === 'openai') {
                const apiKey = prompt('OpenAI API Key:');
                const modelName = prompt('Model name:', 'gpt-3.5-turbo');
                if (!apiKey) {
                    alert('API Key is required for OpenAI');
                    return;
                }
                config = {
                    api_key: apiKey,
                    model_name: modelName,
                    is_active: true,
                    is_default: false
                };
            } else if (type.toLowerCase() === 'gemini') {
                const apiKey = prompt('Gemini API Key:');
                const modelName = prompt('Model name:', 'gemini-pro');
                if (!apiKey) {
                    alert('API Key is required for Gemini');
                    return;
                }
                config = {
                    api_key: apiKey,
                    model_name: modelName,
                    is_active: true,
                    is_default: false
                };
            } else {
                alert('Unknown provider type');
                return;
            }
            
            try {
                const response = await fetch('/api/ai/providers', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name: name,
                        provider_type: type,
                        config: config
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert(`Provider '${name}' added successfully!`);
                    loadAIProviders();
                    displayAIProviders();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (error) {
                console.error('Error adding AI provider:', error);
                alert('Error adding AI provider');
            }
        }
        
        async function addNetworkOllama() {
            const hostname = prompt('Enter hostname (e.g., pop-os.local, ubuntu.local):');
            if (!hostname) return;
            
            const port = prompt('Port (default 11434):', '11434');
            const modelName = prompt('Model name:', 'llama2');
            
            const baseUrl = `http://${hostname}:${port}`;
            const name = `Ollama (${hostname})`;
            
            const config = {
                base_url: baseUrl,
                model_name: modelName,
                is_active: true,
                is_default: false
            };
            
            try {
                const response = await fetch('/api/ai/providers', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        name: name,
                        provider_type: 'ollama',
                        config: config
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    alert(`Network Ollama provider '${name}' added successfully!\\nURL: ${baseUrl}`);
                    loadAIProviders();
                    displayAIProviders();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (error) {
                console.error('Error adding network Ollama provider:', error);
                alert('Error adding network Ollama provider');
            }
        }
        
        async function detectOllamaModels() {
            const hostname = prompt('Enter Ollama hostname (e.g., pop-os.local, localhost):');
            if (!hostname) return;
            
            const port = prompt('Port (default 11434):', '11434');
            const baseUrl = `http://${hostname}:${port}`;
            
            try {
                const response = await fetch(`${baseUrl}/api/tags`);
                if (response.ok) {
                    const data = await response.json();
                    const models = data.models || [];
                    
                    if (models.length === 0) {
                        alert('No models found on this Ollama server');
                        return;
                    }
                    
                    let modelList = 'Available models:\\n';
                    models.forEach((model, index) => {
                        modelList += `${index + 1}. ${model.name}\\n`;
                    });
                    
                    const selectedIndex = prompt(`${modelList}\\nSelect model number (1-${models.length}):`);
                    const modelIndex = parseInt(selectedIndex) - 1;
                    
                    if (modelIndex >= 0 && modelIndex < models.length) {
                        const selectedModel = models[modelIndex];
                        const providerName = `Ollama (${hostname}) - ${selectedModel.name}`;
                        
                        const config = {
                            base_url: baseUrl,
                            model_name: selectedModel.name,
                            is_active: true,
                            is_default: false
                        };
                        
                        const createResponse = await fetch('/api/ai/providers', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({
                                name: providerName,
                                provider_type: 'ollama',
                                config: config
                            })
                        });
                        
                        const createData = await createResponse.json();
                        
                        if (createData.success) {
                            alert(`Successfully added provider '${providerName}'`);
                            loadAIProviders();
                            displayAIProviders();
                        } else {
                            alert(`Error: ${createData.error}`);
                        }
                    } else {
                        alert('Invalid selection');
                    }
                } else {
                    alert(`Could not connect to Ollama server at ${baseUrl}`);
                }
            } catch (error) {
                console.error('Error detecting Ollama models:', error);
                alert(`Error connecting to ${baseUrl}: ${error.message}`);
            }
        }
        
        async function displayAIProviders() {
            const container = document.getElementById('ai-providers-list');
            if (!container) return;
            
            try {
                const response = await fetch('/api/ai/providers');
                const data = await response.json();
                
                if (data.error) {
                    container.innerHTML = `<span style="color: #ff6b6b;">Error: ${data.error}</span>`;
                    return;
                }
                
                const providers = data.providers || [];
                
                if (providers.length === 0) {
                    container.innerHTML = '<span style="color: #ccc;">No providers configured</span>';
                    return;
                }
                
                let html = '<table style="width: 100%; border-collapse: collapse;">';
                html += '<tr><th style="text-align: left; padding: 5px; border-bottom: 1px solid rgba(255,255,255,0.3);">Name</th><th style="text-align: left; padding: 5px; border-bottom: 1px solid rgba(255,255,255,0.3);">Type</th><th style="text-align: left; padding: 5px; border-bottom: 1px solid rgba(255,255,255,0.3);">Status</th><th style="text-align: left; padding: 5px; border-bottom: 1px solid rgba(255,255,255,0.3);">Default</th></tr>';
                
                providers.forEach(provider => {
                    const status = provider.health_status ? '✅ Online' : '❌ Offline';
                    const defaultMark = provider.is_default ? '⭐' : '';
                    html += `<tr>
                        <td style="padding: 5px;">${provider.name}</td>
                        <td style="padding: 5px;">${provider.provider_type}</td>
                        <td style="padding: 5px;">${status}</td>
                        <td style="padding: 5px;">${defaultMark}</td>
                    </tr>`;
                });
                
                html += '</table>';
                container.innerHTML = html;
                
            } catch (error) {
                console.error('Error displaying AI providers:', error);
                container.innerHTML = '<span style="color: #ff6b6b;">Error loading providers</span>';
            }
        }
        
        async function getTrainingSummary() {
            const container = document.getElementById('ai-training-summary');
            if (!container) return;
            
            try {
                const response = await fetch('/api/ai/training/summary');
                const data = await response.json();
                
                if (data.error) {
                    container.innerHTML = `<span style="color: #ff6b6b;">Error: ${data.error}</span>`;
                    return;
                }
                
                let html = `
                    <strong>Total Samples:</strong> ${data.total_samples}<br>
                    <strong>Average Relevance:</strong> ${(data.avg_relevance * 100).toFixed(1)}%<br>
                `;
                
                if (data.by_type && Object.keys(data.by_type).length > 0) {
                    html += '<strong>By Type:</strong><br>';
                    for (const [type, count] of Object.entries(data.by_type)) {
                        html += `&nbsp;&nbsp;${type}: ${count}<br>`;
                    }
                }
                
                if (data.date_range && data.date_range.earliest) {
                    html += `<strong>Date Range:</strong> ${data.date_range.earliest} to ${data.date_range.latest}`;
                }
                
                container.innerHTML = html;
                
            } catch (error) {
                console.error('Error getting training summary:', error);
                container.innerHTML = '<span style="color: #ff6b6b;">Error loading summary</span>';
            }
        }
        
        // Load AI admin data when opening AI widget admin
        function loadAIAdminData() {
            displayAIProviders();
            getTrainingSummary();
        }

        // Email Todo Analysis Functions
        async function analyzeEmailTodos() {
            const button = event.target;
            const originalText = button.textContent;
            button.textContent = '⏳ Analyzing...';
            button.disabled = true;
            
            const analysisDiv = document.getElementById('email-todo-analysis');
            const resultsDiv = document.getElementById('email-todo-results');
            
            try {
                const response = await fetch('/api/email/todo-analysis');
                const data = await response.json();
                
                if (data.success && data.analysis) {
                    const analysis = data.analysis;
                    
                    resultsDiv.innerHTML = `
                        <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                            <div class="bg-green-900 bg-opacity-30 p-3 rounded border border-green-500">
                                <h4 class="text-green-300 font-semibold mb-2">📝 Potential Todos</h4>
                                <p class="text-white text-sm mb-2">Found: ${analysis.potential_todos ? analysis.potential_todos.length : 0}</p>
                                ${analysis.potential_todos && analysis.potential_todos.length > 0 ? 
                                    analysis.potential_todos.slice(0, 3).map(todo => `
                                        <div class="bg-black bg-opacity-20 p-2 mb-2 rounded text-xs">
                                            <div class="text-white font-medium">${todo.subject || 'No Subject'}</div>
                                            <div class="text-gray-300">From: ${todo.sender || 'Unknown'}</div>
                                            <div class="text-green-300">Priority: ${todo.priority || 'Medium'}</div>
                                            <a href="${todo.gmail_link || '#'}" target="_blank" class="text-blue-300 hover:underline">📧 View Email</a>
                                        </div>
                                    `).join('') + (analysis.potential_todos.length > 3 ? `<p class="text-gray-300 text-xs">... and ${analysis.potential_todos.length - 3} more</p>` : '')
                                    : '<p class="text-gray-400 text-sm">No todos found</p>'
                                }
                            </div>
                            <div class="bg-orange-900 bg-opacity-30 p-3 rounded border border-orange-500">
                                <h4 class="text-orange-300 font-semibold mb-2">📧 Need Reply</h4>
                                <p class="text-white text-sm mb-2">Found: ${analysis.unreplied_emails ? analysis.unreplied_emails.length : 0}</p>
                                ${analysis.unreplied_emails && analysis.unreplied_emails.length > 0 ? 
                                    analysis.unreplied_emails.slice(0, 3).map(email => `
                                        <div class="bg-black bg-opacity-20 p-2 mb-2 rounded text-xs">
                                            <div class="text-white font-medium">${email.subject || 'No Subject'}</div>
                                            <div class="text-gray-300">From: ${email.sender || 'Unknown'}</div>
                                            <div class="text-orange-300">${email.days_since_received || 0} days ago</div>
                                            <a href="${email.gmail_link || '#'}" target="_blank" class="text-blue-300 hover:underline">📧 View Email</a>
                                        </div>
                                    `).join('') + (analysis.unreplied_emails.length > 3 ? `<p class="text-gray-300 text-xs">... and ${analysis.unreplied_emails.length - 3} more</p>` : '')
                                    : '<p class="text-gray-400 text-sm">No unreplied emails found</p>'
                                }
                            </div>
                        </div>
                        <div class="mt-4 p-3 bg-blue-900 bg-opacity-20 rounded border border-blue-400">
                            <h4 class="text-blue-300 font-semibold mb-2">📊 Analysis Summary</h4>
                            <div class="grid grid-cols-2 gap-4 text-sm">
                                <div>
                                    <span class="text-gray-300">Period:</span>
                                    <span class="text-white ml-2">${analysis.period || 'Unknown'}</span>
                                </div>
                                <div>
                                    <span class="text-gray-300">Emails Analyzed:</span>
                                    <span class="text-white ml-2">${analysis.total_emails_analyzed || 0}</span>
                                </div>
                            </div>
                        </div>
                    `;
                    
                    analysisDiv.style.display = 'block';
                } else {
                    resultsDiv.innerHTML = `<div class="text-red-300">Error: ${data.error || 'Unknown error'}</div>`;
                    analysisDiv.style.display = 'block';
                }
                
            } catch (error) {
                console.error('Email analysis error:', error);
                resultsDiv.innerHTML = `<div class="text-red-300">Error: ${error.message}</div>`;
                analysisDiv.style.display = 'block';
            } finally {
                button.textContent = originalText;
                button.disabled = false;
            }
        }

        async function syncEmailToTickTick() {
            const button = event.target;
            const originalText = button.textContent;
            button.textContent = '⏳ Syncing...';
            button.disabled = true;
            
            const analysisDiv = document.getElementById('email-todo-analysis');
            const resultsDiv = document.getElementById('email-todo-results');
            
            try {
                const response = await fetch('/api/email/sync-to-ticktick', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
                const data = await response.json();
                
                if (data.success && data.sync_result) {
                    const summary = data.summary;
                    const sync = data.sync_result;
                    
                    resultsDiv.innerHTML = `
                        <div class="bg-green-900 bg-opacity-30 p-4 rounded border border-green-500">
                            <h4 class="text-green-300 font-semibold mb-3">✅ TickTick Sync Complete</h4>
                            
                            <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
                                <div class="text-center">
                                    <div class="text-2xl font-bold text-white">${summary.tasks_created_count || 0}</div>
                                    <div class="text-green-300 text-sm">Tasks Created</div>
                                </div>
                                <div class="text-center">
                                    <div class="text-2xl font-bold text-yellow-300">${summary.tasks_skipped_count || 0}</div>
                                    <div class="text-yellow-300 text-sm">Skipped (Duplicates)</div>
                                </div>
                                <div class="text-center">
                                    <div class="text-2xl font-bold text-red-300">${summary.errors_count || 0}</div>
                                    <div class="text-red-300 text-sm">Errors</div>
                                </div>
                            </div>
                            
                            ${sync.tasks_created && sync.tasks_created.length > 0 ? `
                                <div class="mb-4">
                                    <h5 class="text-white font-medium mb-2">🎉 Created Tasks:</h5>
                                    <div class="max-h-32 overflow-y-auto">
                                        ${sync.tasks_created.slice(0, 5).map(task => `
                                            <div class="bg-black bg-opacity-20 p-2 mb-1 rounded text-xs">
                                                <div class="text-white">${task.title || 'Untitled Task'}</div>
                                                <div class="text-gray-300">Priority: ${task.priority || 'Medium'}</div>
                                            </div>
                                        `).join('')}
                                        ${sync.tasks_created.length > 5 ? `<p class="text-gray-300 text-xs mt-2">... and ${sync.tasks_created.length - 5} more tasks</p>` : ''}
                                    </div>
                                </div>
                            ` : ''}
                            
                            ${sync.errors && sync.errors.length > 0 ? `
                                <div class="bg-red-900 bg-opacity-30 p-3 rounded border border-red-500">
                                    <h5 class="text-red-300 font-medium mb-2">⚠️ Errors:</h5>
                                    <div class="max-h-24 overflow-y-auto text-xs text-gray-300">
                                        ${sync.errors.slice(0, 3).map(error => `<div>• ${error}</div>`).join('')}
                                        ${sync.errors.length > 3 ? `<div>... and ${sync.errors.length - 3} more errors</div>` : ''}
                                    </div>
                                </div>
                            ` : ''}
                            
                            <div class="mt-3 text-center">
                                <a href="https://ticktick.com" target="_blank" class="inline-block bg-blue-500 hover:bg-blue-600 text-white px-4 py-2 rounded text-sm">
                                    📋 Open TickTick
                                </a>
                            </div>
                        </div>
                    `;
                    
                    analysisDiv.style.display = 'block';
                    
                    // Refresh TickTick data to show new tasks
                    setTimeout(() => {
                        loadData('ticktick', 'ticktick-content');
                    }, 1000);
                    
                } else {
                    resultsDiv.innerHTML = `
                        <div class="bg-red-900 bg-opacity-30 p-4 rounded border border-red-500">
                            <h4 class="text-red-300 font-semibold">❌ Sync Failed</h4>
                            <p class="text-gray-300 text-sm mt-2">${data.error || 'Unknown error occurred'}</p>
                        </div>
                    `;
                    analysisDiv.style.display = 'block';
                }
                
            } catch (error) {
                console.error('Email sync error:', error);
                resultsDiv.innerHTML = `
                    <div class="bg-red-900 bg-opacity-30 p-4 rounded border border-red-500">
                        <h4 class="text-red-300 font-semibold">❌ Sync Error</h4>
                        <p class="text-gray-300 text-sm mt-2">${error.message}</p>
                    </div>
                `;
                analysisDiv.style.display = 'block';
            } finally {
                button.textContent = originalText;
                button.disabled = false;
            }
        }

        // Task Management Modal Functions
        function showCreateTaskModal() {
            const modal = document.getElementById('create-task-modal');
            if (modal) {
                modal.style.display = 'block';
            }
        }

        function hideCreateTaskModal() {
            const modal = document.getElementById('create-task-modal');
            if (modal) {
                modal.style.display = 'none';
                document.getElementById('new-task-form').reset();
            }
        }

        // Close modals when clicking outside
        window.onclick = function(event) {
            const createTaskModal = document.getElementById('create-task-modal');
            if (event.target == createTaskModal) {
                hideCreateTaskModal();
            }
        }

        // Notes Management Functions
        let notesData = {};
        let currentNotesFilter = 'all';

        async function loadNotes() {
            const element = document.getElementById('notes-content');
            const statsElement = document.getElementById('notes-stats');
            
            if (!element) return;
            
            try {
                element.innerHTML = '<div class="loading">Loading notes...</div>';
                
                const response = await fetch('/api/notes');
                const data = await response.json();
                
                if (data.success) {
                    notesData = data;
                    
                    // Update statistics
                    if (statsElement) {
                        statsElement.innerHTML = `
                            <div class="text-xs space-y-1">
                                <div>📚 Total: ${data.notes.length}</div>
                                <div>📂 Obsidian: ${data.obsidian_count}</div>
                                <div>☁️ Google Drive: ${data.gdrive_count}</div>
                                <div>📋 TODOs found: ${data.total_todos_found}</div>
                                ${data.tasks_created ? `<div>✅ Tasks created: ${data.tasks_created}</div>` : ''}
                            </div>
                        `;
                    }
                    
                    renderNotes(data.notes);
                    
                    // Auto-check connection status
                    updateNotesConnectionStatus();
                    
                } else {
                    element.innerHTML = `<div class="error">❌ ${data.error}</div>`;
                }
                
            } catch (error) {
                console.error('Error loading notes:', error);
                element.innerHTML = `<div class="error">❌ Error loading notes: ${error.message}</div>`;
            }
        }

        function renderNotes(notes) {
            const element = document.getElementById('notes-content');
            
            // Filter notes
            const filteredNotes = notes.filter(note => {
                if (currentNotesFilter === 'all') return true;
                return note.source === currentNotesFilter;
            });
            
            // Filter by TODOs if checkbox is checked
            const withTodosOnly = document.getElementById('notes-with-todos').checked;
            const finalNotes = withTodosOnly ? filteredNotes.filter(note => note.has_todos) : filteredNotes;
            
            if (finalNotes.length === 0) {
                element.innerHTML = '<div class="text-center text-gray-300 py-8">📝 No notes found</div>';
                return;
            }
            
            element.innerHTML = finalNotes.map(note => `
                <div class="note-item bg-white bg-opacity-5 rounded-lg p-3 border border-white border-opacity-20 hover:bg-opacity-10 transition-all cursor-pointer" 
                     onclick="openNoteDetail('${note.source}', '${note.title}', this)"
                     data-note='${JSON.stringify(note).replace(/'/g, "&apos;")}'>
                    <div class="flex items-start justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <span class="source-icon text-xs">
                                ${note.source === 'obsidian' ? '📝' : '☁️'}
                            </span>
                            <h4 class="font-medium text-sm text-white truncate">${note.title}</h4>
                        </div>
                        <div class="text-xs text-gray-300 shrink-0 ml-2">
                            ${new Date(note.modified_at).toLocaleDateString()}
                        </div>
                    </div>
                    <p class="text-xs text-gray-300 line-clamp-2 mb-2">${note.preview || 'No preview available'}</p>
                    <div class="flex items-center justify-between text-xs">
                        <div class="flex items-center gap-3">
                            <span class="text-gray-400">${note.word_count || 0} words</span>
                            ${note.has_todos ? '<span class="text-yellow-400">📋 TODOs</span>' : ''}
                            ${note.tags && note.tags.length ? `<span class="text-blue-400">🏷️ ${note.tags.length}</span>` : ''}
                        </div>
                        <div class="text-gray-400">
                            ${note.source === 'obsidian' ? 'Obsidian' : 'Google Drive'}
                        </div>
                    </div>
                </div>
            `).join('');
        }

        function openNoteDetail(source, title, element) {
            const noteData = JSON.parse(element.dataset.note.replace(/&apos;/g, "'"));
            
            const modal = document.getElementById('detail-modal');
            const modalTitle = document.getElementById('modal-title');
            const modalContent = document.getElementById('modal-content');
            
            modalTitle.textContent = `📝 ${title}`;
            
            let sourceLink = '';
            if (source === 'obsidian' && noteData.relative_path) {
                sourceLink = `<a href="obsidian://open?vault=&file=${encodeURIComponent(noteData.relative_path)}" class="text-blue-400 hover:text-blue-300">🔗 Open in Obsidian</a>`;
            } else if (source === 'google_drive' && noteData.url) {
                sourceLink = `<a href="${noteData.url}" target="_blank" class="text-blue-400 hover:text-blue-300">🔗 Open in Google Drive</a>`;
            }
            
            modalContent.innerHTML = `
                <div class="detail-section">
                    <h4>📄 Note Information</h4>
                    <div class="detail-meta">
                        <div class="meta-item">
                            <span class="meta-label">Title:</span>
                            <span class="meta-value">${noteData.title}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Source:</span>
                            <span class="meta-value">${source === 'obsidian' ? 'Obsidian' : 'Google Drive'}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Modified:</span>
                            <span class="meta-value">${new Date(noteData.modified_at).toLocaleString()}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Size:</span>
                            <span class="meta-value">${noteData.word_count || 0} words</span>
                        </div>
                        ${sourceLink ? `<div class="meta-item">${sourceLink}</div>` : ''}
                    </div>
                </div>
                
                ${noteData.preview ? `
                    <div class="detail-section">
                        <h4>📝 Preview</h4>
                        <div class="bg-white bg-opacity-5 p-3 rounded border border-white border-opacity-20">
                            <pre class="whitespace-pre-wrap text-sm">${noteData.preview}</pre>
                        </div>
                    </div>
                ` : ''}
                
                ${noteData.todos && noteData.todos.length ? `
                    <div class="detail-section">
                        <h4>📋 Found TODOs (${noteData.todos.length})</h4>
                        <div class="space-y-2">
                            ${noteData.todos.map(todo => `
                                <div class="bg-yellow-900 bg-opacity-30 p-3 rounded border border-yellow-500 border-opacity-50">
                                    <div class="text-yellow-200 font-medium text-sm">${todo.text}</div>
                                    ${todo.context ? `<div class="text-xs text-gray-300 mt-1 italic">${todo.context.substring(0, 100)}...</div>` : ''}
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
                
                ${noteData.tags && noteData.tags.length ? `
                    <div class="detail-section">
                        <h4>🏷️ Tags</h4>
                        <div class="flex flex-wrap gap-1">
                            ${noteData.tags.map(tag => `<span class="bg-blue-500 bg-opacity-30 text-blue-200 px-2 py-1 rounded text-xs">#${tag}</span>`).join('')}
                        </div>
                    </div>
                ` : ''}
            `;
            
            modal.style.display = 'block';
        }

        async function testNotesConnections() {
            const obsidianIndicator = document.getElementById('obsidian-indicator');
            const obsidianStatus = document.getElementById('obsidian-status-text');
            const gdriveIndicator = document.getElementById('gdrive-indicator');
            const gdriveStatus = document.getElementById('gdrive-status-text');
            
            // Reset to loading state
            obsidianIndicator.className = 'w-3 h-3 rounded-full bg-yellow-500 mr-2 animate-pulse';
            obsidianStatus.textContent = 'Testing...';
            gdriveIndicator.className = 'w-3 h-3 rounded-full bg-yellow-500 mr-2 animate-pulse';
            gdriveStatus.textContent = 'Testing...';
            
            try {
                // Get settings first
                const settingsResponse = await fetch('/api/settings/notes');
                const settingsData = await settingsResponse.json();
                
                if (!settingsData.success) {
                    throw new Error('Failed to get notes settings');
                }
                
                const settings = settingsData.settings;
                
                // Test Obsidian connection
                if (settings.obsidian_vault_path && settings.obsidian_vault_path.value) {
                    try {
                        const obsidianResponse = await fetch('/api/notes/test-obsidian', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({vault_path: settings.obsidian_vault_path.value})
                        });
                        const obsidianResult = await obsidianResponse.json();
                        
                        if (obsidianResult.success) {
                            obsidianIndicator.className = 'w-3 h-3 rounded-full bg-green-500 mr-2';
                            obsidianStatus.textContent = `Connected (${obsidianResult.details.markdown_files} files)`;
                        } else {
                            obsidianIndicator.className = 'w-3 h-3 rounded-full bg-red-500 mr-2';
                            obsidianStatus.textContent = `Error: ${obsidianResult.error}`;
                        }
                    } catch (error) {
                        obsidianIndicator.className = 'w-3 h-3 rounded-full bg-red-500 mr-2';
                        obsidianStatus.textContent = `Error: ${error.message}`;
                    }
                } else {
                    obsidianIndicator.className = 'w-3 h-3 rounded-full bg-gray-500 mr-2';
                    obsidianStatus.textContent = 'Not configured';
                }
                
                // Test Google Drive connection
                if (settings.google_drive_notes_folder_id && settings.google_drive_notes_folder_id.value) {
                    try {
                        const gdriveResponse = await fetch('/api/notes/test-gdrive', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({folder_id: settings.google_drive_notes_folder_id.value})
                        });
                        const gdriveResult = await gdriveResponse.json();
                        
                        if (gdriveResult.success) {
                            gdriveIndicator.className = 'w-3 h-3 rounded-full bg-green-500 mr-2';
                            gdriveStatus.textContent = `Connected (${gdriveResult.details.document_count} docs)`;
                        } else {
                            gdriveIndicator.className = 'w-3 h-3 rounded-full bg-red-500 mr-2';
                            gdriveStatus.textContent = `Error: ${gdriveResult.error}`;
                        }
                    } catch (error) {
                        gdriveIndicator.className = 'w-3 h-3 rounded-full bg-red-500 mr-2';
                        gdriveStatus.textContent = `Error: ${error.message}`;
                    }
                } else {
                    gdriveIndicator.className = 'w-3 h-3 rounded-full bg-gray-500 mr-2';
                    gdriveStatus.textContent = 'Not configured';
                }
                
            } catch (error) {
                console.error('Error testing notes connections:', error);
                obsidianIndicator.className = 'w-3 h-3 rounded-full bg-red-500 mr-2';
                obsidianStatus.textContent = 'Test failed';
                gdriveIndicator.className = 'w-3 h-3 rounded-full bg-red-500 mr-2';
                gdriveStatus.textContent = 'Test failed';
            }
        }

        async function updateNotesConnectionStatus() {
            // Simplified status check without full testing
            try {
                const settingsResponse = await fetch('/api/settings/notes');
                const settingsData = await settingsResponse.json();
                
                if (settingsData.success) {
                    const settings = settingsData.settings;
                    
                    const obsidianIndicator = document.getElementById('obsidian-indicator');
                    const obsidianStatus = document.getElementById('obsidian-status-text');
                    const gdriveIndicator = document.getElementById('gdrive-indicator');
                    const gdriveStatus = document.getElementById('gdrive-status-text');
                    
                    // Update Obsidian status
                    if (settings.obsidian_vault_path && settings.obsidian_vault_path.value) {
                        obsidianIndicator.className = 'w-3 h-3 rounded-full bg-blue-500 mr-2';
                        obsidianStatus.textContent = 'Configured';
                    } else {
                        obsidianIndicator.className = 'w-3 h-3 rounded-full bg-gray-500 mr-2';
                        obsidianStatus.textContent = 'Not configured';
                    }
                    
                    // Update Google Drive status
                    if (settings.google_drive_notes_folder_id && settings.google_drive_notes_folder_id.value) {
                        gdriveIndicator.className = 'w-3 h-3 rounded-full bg-blue-500 mr-2';
                        gdriveStatus.textContent = 'Configured';
                    } else {
                        gdriveIndicator.className = 'w-3 h-3 rounded-full bg-gray-500 mr-2';
                        gdriveStatus.textContent = 'Not configured';
                    }
                }
            } catch (error) {
                console.error('Error updating notes connection status:', error);
            }
        }

        async function generateTasksFromNotes() {
            const button = event.target;
            const originalText = button.textContent;
            
            try {
                button.textContent = 'Generating...';
                button.disabled = true;
                
                const response = await fetch('/api/tasks/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        include_notes: true,
                        include_calendar: true,
                        include_email: false  // Keep email off by default
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    const result = data.result;
                    alert(`Task generation completed!\n\nTasks found: ${result.tasks_found}\n- From notes: ${result.by_source.notes}\n- From calendar: ${result.by_source.calendar}\n\nTasks created: ${result.creation_result.created}\nTasks skipped (duplicates): ${result.creation_result.skipped}`);
                    
                    // Refresh tasks and notes
                    if (window.taskManagement) {
                        window.taskManagement.loadTasks();
                    }
                    loadNotes();
                } else {
                    alert(`Error generating tasks: ${data.error}`);
                }
                
            } catch (error) {
                console.error('Error generating tasks from notes:', error);
                alert(`Error: ${error.message}`);
            } finally {
                button.textContent = originalText;
                button.disabled = false;
            }
        }

        // Note filter functions
        document.addEventListener('DOMContentLoaded', function() {
            // Add event listeners for note filters
            const notesFilterButtons = document.querySelectorAll('.notes-filter-btn');
            notesFilterButtons.forEach(button => {
                button.addEventListener('click', function() {
                    const filter = this.dataset.filter;
                    
                    // Update active button
                    notesFilterButtons.forEach(btn => {
                        btn.className = 'notes-filter-btn bg-gray-200 text-gray-700 px-2 py-1 text-xs rounded';
                    });
                    this.className = 'notes-filter-btn bg-blue-600 text-white px-2 py-1 text-xs rounded';
                    
                    // Apply filter
                    currentNotesFilter = filter;
                    if (notesData.notes) {
                        renderNotes(notesData.notes);
                    }
                });
            });
            
            // Add event listener for TODO filter checkbox
            const todosCheckbox = document.getElementById('notes-with-todos');
            if (todosCheckbox) {
                todosCheckbox.addEventListener('change', function() {
                    if (notesData.notes) {
                        renderNotes(notesData.notes);
                    }
                });
            }
        });
        
        // Notes Admin Functions
        async function testObsidianVault() {
            const vaultPath = document.getElementById('obsidian-vault-path').value;
            const indicator = document.getElementById('test-obsidian-indicator');
            const status = document.getElementById('test-obsidian-status');
            
            if (!vaultPath.trim()) {
                alert('Please enter an Obsidian vault path');
                return;
            }
            
            indicator.style.background = '#ffc107';
            indicator.classList.add('animate-pulse');
            status.textContent = 'Testing...';
            
            try {
                const response = await fetch('/api/notes/test-obsidian', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({vault_path: vaultPath})
                });
                const result = await response.json();
                
                if (result.success) {
                    indicator.style.background = '#4caf50';
                    status.textContent = `Connected (${result.details.markdown_files} files)`;
                } else {
                    indicator.style.background = '#f44336';
                    status.textContent = `Error: ${result.error}`;
                }
            } catch (error) {
                indicator.style.background = '#f44336';
                status.textContent = `Error: ${error.message}`;
            } finally {
                indicator.classList.remove('animate-pulse');
            }
        }
        
        async function testGoogleDriveFolder() {
            const folderId = document.getElementById('gdrive-folder-id').value;
            const indicator = document.getElementById('test-gdrive-indicator');
            const status = document.getElementById('test-gdrive-status');
            
            if (!folderId.trim()) {
                alert('Please enter a Google Drive folder ID');
                return;
            }
            
            indicator.style.background = '#ffc107';
            indicator.classList.add('animate-pulse');
            status.textContent = 'Testing...';
            
            try {
                const response = await fetch('/api/notes/test-gdrive', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({folder_id: folderId})
                });
                const result = await response.json();
                
                if (result.success) {
                    indicator.style.background = '#4caf50';
                    status.textContent = `Connected (${result.details.document_count} docs)`;
                } else {
                    indicator.style.background = '#f44336';
                    status.textContent = `Error: ${result.error}`;
                }
            } catch (error) {
                indicator.style.background = '#f44336';
                status.textContent = `Error: ${error.message}`;
            } finally {
                indicator.classList.remove('animate-pulse');
            }
        }
        
        async function testAllNotesConnections() {
            await Promise.all([
                testObsidianVault(),
                testGoogleDriveFolder()
            ]);
        }
        
        async function saveNotesSettings() {
            const settings = {
                obsidian_vault_path: document.getElementById('obsidian-vault-path').value,
                google_drive_notes_folder_id: document.getElementById('gdrive-folder-id').value,
                auto_create_tasks: document.getElementById('auto-create-tasks').checked
            };
            
            try {
                const response = await fetch('/api/settings/notes', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(settings)
                });
                const result = await response.json();
                
                if (result.success) {
                    alert('Notes settings saved successfully!');
                    // Refresh the notes widget
                    loadNotes();
                    closeWidgetAdmin();
                } else {
                    alert(`Error saving settings: ${result.error}`);
                }
            } catch (error) {
                alert(`Error: ${error.message}`);
            }
        }
        
        async function generateTasksFromAllSources() {
            try {
                const response = await fetch('/api/tasks/generate', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({
                        include_notes: true,
                        include_calendar: true,
                        include_email: false
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    const result = data.result;
                    alert(`Task generation completed!\n\nTasks found: ${result.tasks_found}\n- From notes: ${result.by_source.notes}\n- From calendar: ${result.by_source.calendar}\n\nTasks created: ${result.creation_result.created}\nTasks skipped: ${result.creation_result.skipped}`);
                    
                    // Refresh tasks and notes
                    if (window.taskManagement) {
                        window.taskManagement.loadTasks();
                    }
                    loadNotes();
                } else {
                    alert(`Error generating tasks: ${data.error}`);
                }
            } catch (error) {
                alert(`Error: ${error.message}`);
            }
        }
        
        async function refreshNotesData() {
            loadNotes();
            alert('Notes data refreshed!');
        }
        
        // Load notes settings into admin form
        async function loadNotesSettings() {
            try {
                const response = await fetch('/api/settings/notes');
                const data = await response.json();
                
                if (data.success) {
                    const settings = data.settings;
                    
                    const obsidianPath = document.getElementById('obsidian-vault-path');
                    const gdriveId = document.getElementById('gdrive-folder-id');
                    const autoCreate = document.getElementById('auto-create-tasks');
                    
                    if (obsidianPath) obsidianPath.value = settings.obsidian_vault_path?.value || '';
                    if (gdriveId) gdriveId.value = settings.google_drive_notes_folder_id?.value || '';
                    if (autoCreate) autoCreate.checked = settings.auto_create_tasks?.value || false;
                }
            } catch (error) {
                console.error('Error loading notes settings:', error);
            }
        }

        // ===================================================================
        // SERVER MANAGEMENT FUNCTIONS
        // ===================================================================
        
        let serversData = [];
        
        async function refreshServers() {
            try {
                const refreshIcon = document.getElementById('refresh-servers-icon');
                refreshIcon.style.animation = 'spin 1s linear infinite';
                
                const response = await fetch('/api/servers');
                const result = await response.json();
                
                if (result.success) {
                    serversData = result.servers;
                    renderServers();
                    updateServerCount(result.servers.length);
                } else {
                    console.error('Failed to refresh servers:', result.error);
                }
            } catch (error) {
                console.error('Error refreshing servers:', error);
            } finally {
                const refreshIcon = document.getElementById('refresh-servers-icon');
                refreshIcon.style.animation = '';
            }
        }
        
        function renderServers() {
            const container = document.getElementById('servers-container');
            
            if (serversData.length === 0) {
                container.innerHTML = '<div class="text-gray-300 text-sm">No Python servers detected</div>';
                return;
            }
            
            const serversHtml = serversData.map(server => `
                <div class="server-card bg-white bg-opacity-20 rounded-lg p-3 border border-white border-opacity-30 min-w-80">
                    <div class="flex items-center justify-between mb-2">
                        <div class="flex items-center gap-2">
                            <span class="server-status-indicator ${server.status === 'running' ? 'status-running' : 'status-stopped'}" 
                                  title="Server Status"></span>
                            <h4 class="text-white font-medium text-sm">${server.name}</h4>
                            <span class="text-xs px-2 py-1 rounded bg-gray-600 text-white">${server.type}</span>
                        </div>
                        <div class="flex items-center gap-1">
                            <button onclick="openServerUrl('${server.url}')" 
                                    class="bg-green-500 hover:bg-green-600 text-white px-2 py-1 rounded text-xs"
                                    title="Open in browser">
                                🌐
                            </button>
                            <button onclick="toggleServer(${server.port}, '${server.status}')" 
                                    class="server-toggle-btn ${server.status === 'running' ? 'bg-red-500 hover:bg-red-600' : 'bg-green-500 hover:bg-green-600'} 
                                           text-white px-2 py-1 rounded text-xs"
                                    ${!server.can_control ? 'disabled' : ''}>
                                ${server.status === 'running' ? '⏹️ Stop' : '▶️ Start'}
                            </button>
                        </div>
                    </div>
                    
                    <div class="text-xs text-gray-300 mb-2">
                        <div class="flex items-center justify-between">
                            <span>Port: ${server.port}</span>
                            <span>PID: ${server.pid || 'Unknown'}</span>
                        </div>
                        ${server.cmdline ? `<div class="mt-1 truncate" title="${server.cmdline}">Path: ${extractPath(server.cmdline)}</div>` : ''}
                    </div>
                    
                    <div class="flex items-center justify-between text-xs text-gray-400">
                        <div class="flex items-center gap-3">
                            <span>CPU: ${server.cpu_percent?.toFixed(1) || 0}%</span>
                            <span>RAM: ${server.memory_mb?.toFixed(0) || 0}MB</span>
                        </div>
                        <button onclick="mapToDashboard('${server.name}', ${server.port})" 
                                class="bg-blue-500 hover:bg-blue-600 text-white px-2 py-1 rounded text-xs"
                                title="Map to dashboard">
                            📋 Map
                        </button>
                    </div>
                </div>
            `).join('');
            
            container.innerHTML = serversHtml;
        }
        
        function extractPath(cmdline) {
            // Extract the working directory or script path from command line
            const parts = cmdline.split(' ');
            for (let part of parts) {
                if (part.includes('/') && !part.startsWith('-')) {
                    // Found a path-like argument
                    if (part.includes('.py')) {
                        // Return the directory of the Python file
                        return part.substring(0, part.lastIndexOf('/')) || part;
                    }
                    return part;
                }
            }
            return 'Unknown';
        }
        
        async function toggleServer(port, currentStatus) {
            try {
                if (currentStatus === 'running') {
                    // Stop the server
                    const response = await fetch(`/api/servers/${port}/stop`, {
                        method: 'POST'
                    });
                    const result = await response.json();
                    
                    if (result.success) {
                        console.log(`Server on port ${port} stopped`);
                        // Wait a moment then refresh
                        setTimeout(refreshServers, 1000);
                    } else {
                        alert(`Failed to stop server: ${result.error}`);
                    }
                } else {
                    // For starting servers, we'd need the start command
                    alert('Server starting not yet implemented. Use the dashboard start functionality.');
                }
            } catch (error) {
                console.error('Error toggling server:', error);
                alert('Error controlling server');
            }
        }
        
        function openServerUrl(url) {
            window.open(url, '_blank');
        }
        
        function mapToDashboard(serverName, port) {
            // Open the add dashboard modal with pre-filled info
            const modal = document.getElementById('add-dashboard-modal');
            const nameField = document.getElementById('dashboard-name');
            const urlField = document.getElementById('dashboard-local-url');
            const typeField = document.getElementById('dashboard-type');
            
            if (nameField) nameField.value = serverName;
            if (urlField) urlField.value = `http://localhost:${port}`;
            if (typeField) typeField.value = 'web_app';
            
            modal.style.display = 'block';
        }
        
        function updateServerCount(count) {
            const countElement = document.getElementById('server-count');
            countElement.textContent = `${count} server${count !== 1 ? 's' : ''}`;
        }
        
        // Auto-refresh servers periodically
        setInterval(refreshServers, 10000); // Refresh every 10 seconds
        
        // Load servers on page load
        document.addEventListener('DOMContentLoaded', function() {
            refreshServers();
        });
    </script>

    <!-- Create Task Modal -->
    <div id="create-task-modal" class="modal" style="display: none;">
        <div class="modal-content" style="max-width: 500px;">
            <div class="modal-header">
                <h3>Create New Task</h3>
                <span class="close-btn" onclick="hideCreateTaskModal()">&times;</span>
            </div>
            <div class="modal-body">
                <form id="new-task-form">
                    <div style="margin-bottom: 15px;">
                        <label for="task-title" style="display: block; margin-bottom: 5px; color: #333; font-weight: bold;">Title *</label>
                        <input type="text" id="task-title" name="title" required 
                               style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
                    </div>
                    
                    <div style="margin-bottom: 15px;">
                        <label for="task-description" style="display: block; margin-bottom: 5px; color: #333; font-weight: bold;">Description</label>
                        <textarea id="task-description" name="description" rows="3"
                                  style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;"></textarea>
                    </div>
                    
                    <div style="display: flex; gap: 15px; margin-bottom: 15px;">
                        <div style="flex: 1;">
                            <label for="task-priority" style="display: block; margin-bottom: 5px; color: #333; font-weight: bold;">Priority</label>
                            <select id="task-priority" name="priority" 
                                    style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
                                <option value="low">Low</option>
                                <option value="medium" selected>Medium</option>
                                <option value="high">High</option>
                            </select>
                        </div>
                        
                        <div style="flex: 1;">
                            <label for="task-category" style="display: block; margin-bottom: 5px; color: #333; font-weight: bold;">Category</label>
                            <select id="task-category" name="category" 
                                    style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
                                <option value="general">General</option>
                                <option value="work">Work</option>
                                <option value="personal">Personal</option>
                                <option value="email">Email</option>
                                <option value="follow-up">Follow-up</option>
                            </select>
                        </div>
                    </div>
                    
                    <div style="margin-bottom: 15px;">
                        <label for="task-due-date" style="display: block; margin-bottom: 5px; color: #333; font-weight: bold;">Due Date</label>
                        <input type="datetime-local" id="task-due-date" name="due_date" 
                               style="width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px;">
                    </div>
                    
                    <div style="margin-bottom: 15px;">
                        <label style="display: flex; align-items: center; color: #333;">
                            <input type="checkbox" id="task-sync-ticktick" name="sync_to_ticktick" checked
                                   style="margin-right: 8px;">
                            Sync to TickTick
                        </label>
                    </div>
                    
                    <div style="text-align: right; padding-top: 15px; border-top: 1px solid #eee;">
                        <button type="button" onclick="hideCreateTaskModal()" 
                                style="padding: 8px 16px; margin-right: 10px; border: 1px solid #ddd; background: #f5f5f5; border-radius: 4px; cursor: pointer;">
                            Cancel
                        </button>
                        <button type="submit" 
                                style="padding: 8px 16px; border: none; background: #007cba; color: white; border-radius: 4px; cursor: pointer;">
                            Create Task
                        </button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Add/Edit Dashboard Modal -->
    <div id="add-dashboard-modal" class="hidden fixed inset-0 bg-black bg-opacity-50 z-50 items-center justify-center">
        <div class="bg-white rounded-lg shadow-xl max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div class="p-6 border-b border-gray-200">
                <div class="flex justify-between items-center">
                    <h2 class="text-2xl font-bold text-gray-800">
                        <span id="modal-title-text">Add Marketing Dashboard / Website</span>
                    </h2>
                    <button onclick="closeAddDashboardModal()" class="text-gray-400 hover:text-gray-600">
                        <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                </div>
                <p class="text-sm text-gray-600 mt-2">
                    Monitor ForgeWeb or ForgeMarket sites from 
                    <a href="https://collab.buildly.io/marketplace/app/forgeweb/" target="_blank" class="text-blue-600 hover:underline">
                        Buildly Forge Marketplace →
                    </a>
                </p>
            </div>
            
            <form id="add-dashboard-form" class="p-6 space-y-4">
                <input type="hidden" id="dashboard-id" value="">
                
                <!-- Project Name -->
                <div>
                    <label for="dashboard-name" class="block text-sm font-medium text-gray-700 mb-1">
                        Project/Brand Name *
                    </label>
                    <input type="text" id="dashboard-name" required
                           class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                           placeholder="e.g., My Awesome Brand">
                    <p class="text-xs text-gray-500 mt-1">The name of your website or marketing project</p>
                </div>
                
                <!-- Project Path -->
                <div>
                    <label for="dashboard-path" class="block text-sm font-medium text-gray-700 mb-1">
                        Project Directory Path *
                    </label>
                    <div class="flex gap-2">
                        <input type="text" id="dashboard-path" required
                               class="flex-1 px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                               placeholder="/Users/greglind/Projects/me/marketing/websites/brand-name">
                        <button type="button" onclick="browseDirectory()" 
                                class="px-4 py-2 bg-gray-100 hover:bg-gray-200 border border-gray-300 rounded-md text-sm">
                            Browse...
                        </button>
                    </div>
                    <p class="text-xs text-gray-500 mt-1">
                        For ForgeWeb sites, point to your website directory (e.g., ~/marketing/websites/mybrand)
                    </p>
                </div>
                
                <!-- Project Type -->
                <div>
                    <label for="dashboard-type" class="block text-sm font-medium text-gray-700 mb-1">
                        Project Type
                    </label>
                    <select id="dashboard-type" onchange="updateProjectTypeDefaults()"
                            class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500">
                        <option value="forgeweb">ForgeWeb Site (Static HTML/CSS/JS)</option>
                        <option value="forgemarket">ForgeMarket Site (E-commerce)</option>
                        <option value="flask">Flask Application</option>
                        <option value="fastapi">FastAPI Application</option>
                        <option value="react">React Application</option>
                        <option value="vue">Vue.js Application</option>
                        <option value="static">Static Website (HTML)</option>
                        <option value="streamlit">Streamlit App</option>
                        <option value="custom">Custom Configuration</option>
                    </select>
                </div>
                
                <!-- Local Port -->
                <div>
                    <label for="dashboard-port" class="block text-sm font-medium text-gray-700 mb-1">
                        Local Development Port
                    </label>
                    <input type="number" id="dashboard-port" 
                           class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                           placeholder="8000">
                    <p class="text-xs text-gray-500 mt-1">Port for local development server</p>
                </div>
                
                <!-- Startup Command -->
                <div>
                    <label for="dashboard-command" class="block text-sm font-medium text-gray-700 mb-1">
                        Startup Command
                    </label>
                    <textarea id="dashboard-command" rows="2"
                              class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500 font-mono text-sm"
                              placeholder="python -m http.server 8000"></textarea>
                    <p class="text-xs text-gray-500 mt-1">Command to start the local development server</p>
                </div>
                
                <!-- Production URL -->
                <div>
                    <label for="dashboard-production-url" class="block text-sm font-medium text-gray-700 mb-1">
                        Production/Live URL
                    </label>
                    <input type="url" id="dashboard-production-url"
                           class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                           placeholder="https://mybrand.com">
                    <p class="text-xs text-gray-500 mt-1">Your live website URL (if deployed)</p>
                </div>
                
                <!-- Dashboard API URL -->
                <div>
                    <label for="dashboard-api-url" class="block text-sm font-medium text-gray-700 mb-1">
                        Dashboard API URL (Optional)
                    </label>
                    <input type="url" id="dashboard-api-url"
                           class="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-blue-500 focus:border-blue-500"
                           placeholder="https://api.mybrand.com/dashboard/stats">
                    <p class="text-xs text-gray-500 mt-1">API endpoint for monitoring analytics, metrics, or dashboard data</p>
                </div>
                
                <!-- Active Toggle -->
                <div class="flex items-center">
                    <input type="checkbox" id="dashboard-active" checked
                           class="w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500">
                    <label for="dashboard-active" class="ml-2 text-sm text-gray-700">
                        Monitor this dashboard (active)
                    </label>
                </div>
                
                <!-- Form Actions -->
                <div class="flex justify-end gap-3 pt-4 border-t border-gray-200">
                    <button type="button" onclick="closeAddDashboardModal()"
                            class="px-4 py-2 border border-gray-300 rounded-md text-gray-700 hover:bg-gray-50">
                        Cancel
                    </button>
                    <button type="button" onclick="saveDashboard()"
                            class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700">
                        <span id="save-btn-text">Add Dashboard</span>
                    </button>
                </div>
            </form>
        </div>
    </div>

    <script src="/static/tasks.js?v=2"></script>
    <script src="/static/dashboards_modern.js?v=4"></script>
    <script>
        // Initialize dashboard manager when page loads
        document.addEventListener('DOMContentLoaded', function() {
            if (typeof dashboardManager !== 'undefined') {
                dashboardManager.init();
            }
        });
    </script>
</body>
</html>
    """

# Keep all the existing API endpoints from the working version...
# [API endpoints will be added here]

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


@app.get("/api/notes")
async def get_notes():
    """Get recent notes from Obsidian and Google Drive."""
    try:
        from collectors.notes_collector import collect_all_notes
        from database import get_credentials, DatabaseManager
        
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
        
        # Collect notes from all sources
        result = collect_all_notes(
            obsidian_path=obsidian_path,
            gdrive_folder_id=gdrive_folder_id,
            limit=limit
        )
        
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
        
        # Auto-create tasks from TODOs if enabled
        if auto_create and result['todos_to_create']:
            from database import DatabaseManager
            db = DatabaseManager()
            created_count = 0
            
            for todo_item in result['todos_to_create']:
                try:
                    # Check if task already exists (avoid duplicates)
                    existing_tasks = db.get_todos()
                    todo_text = todo_item['text']
                    
                    # Skip if similar task exists
                    if any(task.get('title', '').lower() == todo_text.lower() for task in existing_tasks):
                        continue
                    
                    # Create task
                    task_data = {
                        'title': todo_text,
                        'description': f"From {todo_item['source']}: {todo_item['source_title']}\n\n{todo_item.get('context', '')}",
                        'source': f"notes_{todo_item['source']}",
                        'source_url': todo_item.get('source_url') or todo_item.get('source_path'),
                        'priority': 'medium',
                        'status': 'pending'
                    }
                    
                    db.add_todo(task_data)
                    created_count += 1
                    logger.info(f"Auto-created task from note: {todo_text[:50]}...")
                    
                except Exception as e:
                    logger.error(f"Error auto-creating task: {e}")
                    continue
            
            result['tasks_created'] = created_count
        
        return {
            "success": True,
            "notes": result['notes'],
            "obsidian_count": result['obsidian_count'],
            "gdrive_count": result['gdrive_count'],
            "total_todos_found": result['total_todos_found'],
            "tasks_created": result.get('tasks_created', 0)
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
                    username = github_creds.get('username', 'glind')
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
    """Get music trends for Null Records and My Evil Robot Army"""
    try:
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
                            track_data["artist"] = release.get('artist', 'My Evil Robot Army')
                        else:
                            track_data["artist"] = 'My Evil Robot Army'
                            
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
        
        # Fallback data
        return {
            "tracks": [
                {
                    "title": "Electronic Synthesis Vol. 1", 
                    "artist": "My Evil Robot Army", 
                    "platform": "Bandcamp",
                    "type": "release",
                    "stream_url": "https://nullrecords.bandcamp.com"
                },
                {
                    "title": "Ambient Experiments", 
                    "artist": "Gregory Lind", 
                    "platform": "SoundCloud",
                    "type": "release",
                    "stream_url": "https://soundcloud.com/gregory-lind"
                },
                {
                    "title": "Null Records Update",
                    "artist": "Label Stats",
                    "platform": "Analytics",
                    "plays": 1250,
                    "followers": 89,
                    "type": "stats"
                }
            ]
        }
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/vanity")
async def get_vanity():
    """Get vanity alerts about Buildly, Gregory Lind, music, and book"""
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
    """Alias for vanity endpoint - returns alerts format"""
    vanity_data = await get_vanity()
    
    # Transform vanity data to alerts format
    alerts = []
    if isinstance(vanity_data, dict):
        for alert in vanity_data.get('alerts', []):
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
        
        # Save tokens to database
        db.save_auth_token(
            service_name="spotify",
            access_token=token_info["access_token"],
            refresh_token=token_info.get("refresh_token"),
            expires_in=token_info.get("expires_in", 3600)
        )
        
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
        
        # Save Apple Music user token
        db.save_auth_token(
            service_name="apple_music",
            access_token=user_token,
            refresh_token=None,
            expires_in=None  # Apple Music tokens don't expire in the same way
        )
        
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
        
        vanity_config = db.get_setting('vanity_config', {
            'names': ['Gregory Lind'],
            'companies': ['Buildly Labs'],
            'terms': ['Radical Therapy for Software Teams']
        })
        
        music_config = db.get_setting('music_config', {
            'artists': ['My Evil Robot Army'],
            'labels': ['Null Records']
        })
        
        github_config = db.get_setting('github_config', {
            'username': 'glind'
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
    """Chat with AI assistant."""
    if not AI_ASSISTANT_AVAILABLE:
        return {"error": "AI Assistant not available"}
    
    try:
        data = await request.json()
        message = data.get('message', '')
        conversation_id = data.get('conversation_id')
        provider_name = data.get('provider')
        frontend_context = data.get('context', {})
        
        if not message:
            return {"error": "Message is required"}
        
        # Get provider
        provider = ai_manager.get_provider(provider_name)
        if not provider:
            return {"error": "No AI provider available"}
        
        # Create conversation if needed
        if not conversation_id:
            conversation_id = f"conv_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            db.save_ai_conversation(conversation_id, 1, f"Chat {datetime.now().strftime('%H:%M')}")
        
        # Get conversation history
        messages = db.get_ai_conversation_history(conversation_id, limit=10)
        
        # Get user profile for personalization
        user_profile = db.get_user_profile()
        
        # Build context from frontend data and database
        context_data = await build_ai_context_with_frontend(message, frontend_context)
        
        # Build user profile context
        profile_context = ""
        if user_profile:
            profile_context = f"""
USER PROFILE:
- Name: {user_profile.get('preferred_name') or user_profile.get('full_name', 'User')}
- Role: {user_profile.get('role', 'N/A')} at {user_profile.get('company', 'N/A')}
- Focus: {user_profile.get('work_focus', 'N/A')}
- Interests: {user_profile.get('interests', 'N/A')}
- Communication Style: {user_profile.get('communication_style', 'Professional and friendly')}
- Work Hours: {user_profile.get('work_hours', 'N/A')}
- Priorities: {user_profile.get('priorities', 'N/A')}
"""
        
        # Convert to provider format with enhanced context
        chat_messages = []
        
        # Add enhanced system message with current data context
        system_message = f"""You are a personal AI assistant with DIRECT ACCESS to the user's dashboard data. 

{profile_context}

Current Context:
{context_data}

CRITICAL INSTRUCTIONS:
1. You CAN SEE all the user's tasks, calendar events, and emails listed above - USE THEM!
2. When asked about tasks, calendar, or emails, reference the SPECIFIC items shown above by title/subject
3. Do NOT say "I need more information" or "tell me about your tasks" - you already have the data
4. Be proactive: suggest priorities, identify conflicts, highlight important deadlines
5. Reference specific task titles, event names, email subjects when answering
6. If the context shows no data for something, then say "I don't see any [tasks/events/emails] in your dashboard"

Provide helpful, accurate responses based on this real data. Always use the actual data shown above rather than asking for it."""
        
        chat_messages.append({
            'role': 'system',
            'content': system_message
        })
        
        # Add conversation history
        for msg in messages:
            if msg['role'] != 'system':  # Avoid duplicate system messages
                chat_messages.append({
                    'role': msg['role'],
                    'content': msg['content']
                })
        
        # Add current message
        chat_messages.append({
            'role': 'user',
            'content': message
        })
        
        # Get AI response
        response = await provider.chat(chat_messages)
        
        # Save messages
        user_msg_id = f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_user"
        ai_msg_id = f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_ai"
        
        db.save_ai_message(user_msg_id, conversation_id, 'user', message)
        db.save_ai_message(ai_msg_id, conversation_id, 'assistant', response)
        
        return {
            "response": response,
            "conversation_id": conversation_id,
            "provider": provider.name
        }
        
    except Exception as e:
        logger.error(f"Error in AI chat: {e}")
        return {"error": f"Chat error: {str(e)}"}
        return {"error": str(e)}


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
            # Try to create default Ollama providers (local and common network hosts)
            ollama_hosts = [
                {'name': 'Local Ollama', 'url': 'http://localhost:11434'},
                {'name': 'Network Ollama (pop-os.local)', 'url': 'http://pop-os.local:11434'},
                {'name': 'Network Ollama (ubuntu.local)', 'url': 'http://ubuntu.local:11434'}
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
                                    # Use the first available model
                                    model_name = models[0]['name']
                                    logger.info(f"Found model {model_name} at {host_config['url']}")
                                else:
                                    model_name = 'llama2'  # fallback
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
        working_dir = project.get('path', '/Users/greglind/Projects/me/dashboard')
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
        working_dir = project.get('path', '/Users/greglind/Projects/me/dashboard')
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
        # For Marketing Dashboard, scan the marketing directory for cron jobs
        if dashboard_name == "Marketing Dashboard":
            marketing_path = "/Users/greglind/Projects/me/marketing"
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
            marketing_path = "/Users/greglind/Projects/me/marketing"
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
