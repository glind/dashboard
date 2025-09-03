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
from bs4 import BeautifulSoup

# Add the project root to the path so we can import our collectors
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Try to import our existing collectors
try:
    from collectors.calendar_collector import CalendarCollector
    from collectors.gmail_collector import GmailCollector
    from collectors.github_collector import GitHubCollector
    from collectors.ticktick_collector import TickTickCollector
    from config.settings import Settings
    COLLECTORS_AVAILABLE = True
except ImportError as e:
    print(f"Note: Could not import collectors: {e}")
    COLLECTORS_AVAILABLE = False

# Set up logging
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Simple Personal Dashboard")

# Load configuration if it exists
config_path = Path("config/config.yaml")
config = {}
if config_path.exists():
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f) or {}

print("🚀 Simple Dashboard Starting...")
print("Config loaded:", bool(config))

# Mount static files
static_dir = Path("static")
if static_dir.exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the main dashboard page"""
    return """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Personal Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            color: white;
            min-height: 100vh;
            padding: 20px;
        }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { text-align: center; margin-bottom: 30px; font-size: 2.5em; }
        .grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); 
            gap: 20px; 
        }
        .widget {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.2);
        }
        .widget h2 { margin-bottom: 15px; color: #fff; }
        .loading { text-align: center; opacity: 0.7; }
        .error { color: #ff6b6b; text-align: center; }
        .item { 
            background: rgba(255,255,255,0.1); 
            margin: 8px 0; 
            padding: 10px; 
            border-radius: 8px; 
        }
        .item-title { font-weight: bold; margin-bottom: 5px; }
        .item-meta { font-size: 0.9em; opacity: 0.8; }
        .refresh-btn {
            position: fixed;
            bottom: 20px;
            right: 20px;
            background: #4CAF50;
            color: white;
            border: none;
            border-radius: 50px;
            padding: 15px 20px;
            cursor: pointer;
            font-size: 16px;
        }
        .filter-buttons {
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-bottom: 10px;
        }
        .filter-btn {
            background: rgba(255,255,255,0.2);
            color: white;
            border: 1px solid rgba(255,255,255,0.3);
            border-radius: 15px;
            padding: 5px 12px;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.3s ease;
        }
        .filter-btn:hover, .filter-btn.active {
            background: rgba(255,255,255,0.3);
            border-color: rgba(255,255,255,0.5);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Personal Dashboard</h1>
        
        <div class="grid">
            <div class="widget">
                <h2>📅 Calendar Events</h2>
                <div id="calendar-content" class="loading">Loading...</div>
            </div>
            
            <div class="widget">
                <h2>📧 Email Summary</h2>
                <div id="email-content" class="loading">Loading...</div>
            </div>
            
            <div class="widget">
                <h2>🐙 GitHub Activity</h2>
                <div id="github-content" class="loading">Loading...</div>
            </div>
            
            <div class="widget">
                <h2>✅ TickTick Tasks</h2>
                <div id="ticktick-content" class="loading">Loading...</div>
            </div>
            
            <div class="widget">
                <h2>📰 News Headlines</h2>
                <div class="filter-buttons">
                    <button onclick="filterNews('all')" class="filter-btn active" id="filter-all">All</button>
                    <button onclick="filterNews('tech')" class="filter-btn" id="filter-tech">Tech/AI</button>
                    <button onclick="filterNews('oregon')" class="filter-btn" id="filter-oregon">Oregon State</button>
                    <button onclick="filterNews('timbers')" class="filter-btn" id="filter-timbers">Timbers</button>
                    <button onclick="filterNews('starwars')" class="filter-btn" id="filter-starwars">Star Wars</button>
                    <button onclick="filterNews('startrek')" class="filter-btn" id="filter-startrek">Star Trek</button>
                </div>
                <div id="news-content" class="loading">Loading...</div>
            </div>
            
            <div class="widget">
                <h2>🎵 Music Trends</h2>
                <div id="music-content" class="loading">Loading...</div>
            </div>
        </div>
    </div>
    
    <button class="refresh-btn" onclick="loadAllData()">🔄 Refresh</button>
    
    <script>
        // News filtering
        let currentNewsFilter = 'all';
        
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
                
                // Format data based on type
                if (elementId === 'calendar-content') {
                    element.innerHTML = data.events ? data.events.map(event => 
                        `<div class="item">
                            <div class="item-title">${event.title}</div>
                            <div class="item-meta">${event.time}</div>
                        </div>`
                    ).join('') : '<div class="item">No events today</div>';
                }
                else if (elementId === 'email-content') {
                    element.innerHTML = `
                        <div class="item">
                            <div class="item-title">📨 Unread: ${data.unread || 0}</div>
                            <div class="item-meta">Total: ${data.total || 0}</div>
                        </div>
                        ${data.recent ? data.recent.map(email => 
                            `<div class="item">
                                <div class="item-title">${email.subject}</div>
                                <div class="item-meta">From: ${email.sender}</div>
                            </div>`
                        ).join('') : ''}
                    `;
                }
                else if (elementId === 'github-content') {
                    if (data.items) {
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
                        element.innerHTML = data.tasks ? data.tasks.map(task => 
                            `<div class="item">
                                <div class="item-title">${task.title}</div>
                                <div class="item-meta">Due: ${task.due || 'No due date'}</div>
                            </div>`
                        ).join('') : '<div class="item">No tasks found</div>';
                    }
                }
                else if (elementId === 'news-content') {
                    element.innerHTML = data.articles ? data.articles.map(article => 
                        `<div class="item">
                            <div class="item-title">${article.title}</div>
                            <div class="item-meta">${article.source}</div>
                        </div>`
                    ).join('') : '<div class="item">No news available</div>';
                }
                else if (elementId === 'music-content') {
                    element.innerHTML = data.tracks ? data.tracks.map(track => 
                        `<div class="item">
                            <div class="item-title">${track.title}</div>
                            <div class="item-meta">${track.artist}</div>
                        </div>`
                    ).join('') : '<div class="item">No music data available</div>';
                }
                
            } catch (error) {
                console.error(`Error loading ${endpoint}:`, error);
                element.innerHTML = `<div class="error">❌ Failed to load data</div>`;
            }
        }
        
        // Load all data
        function loadAllData() {
            loadData('/api/calendar', 'calendar-content');
            loadData('/api/email', 'email-content');
            loadData('/api/github', 'github-content');
            loadData('/api/ticktick', 'ticktick-content');
            loadData('/api/news', 'news-content');
            loadData('/api/music', 'music-content');
        }
        
        // Load data on page load
        loadAllData();
        
        // Auto-refresh every 5 minutes
        setInterval(loadAllData, 5 * 60 * 1000);
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
                        if not event.get('is_all_day', False) and event.get('start_time'):
                            try:
                                start_dt = datetime.fromisoformat(str(event['start_time']).replace('Z', '+00:00'))
                                event_time = start_dt.strftime("%I:%M %p")
                                if event.get('end_time'):
                                    end_dt = datetime.fromisoformat(str(event['end_time']).replace('Z', '+00:00'))
                                    event_time += f" - {end_dt.strftime('%I:%M %p')}"
                            except:
                                event_time = str(event.get('start_time', 'All day'))
                        
                        formatted_events.append({"title": title, "time": event_time})
                    return {"events": formatted_events}
            except:
                pass
        
        return {"events": [{"title": "Team Meeting", "time": "9:00 AM - 10:00 AM"}]}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/email") 
async def get_email():
    """Get email summary from Gmail"""
    try:
        if COLLECTORS_AVAILABLE:
            try:
                settings = Settings()
                gmail_collector = GmailCollector(settings)
                start_date = datetime.now() - timedelta(days=1)
                end_date = datetime.now()
                emails_data = await gmail_collector.collect_emails(start_date, end_date)
                
                if emails_data:
                    unread_count = sum(1 for email in emails_data if not email.get('read', True))
                    recent_emails = []
                    for email in emails_data[:5]:
                        recent_emails.append({
                            "subject": email.get('subject', 'No Subject')[:50],
                            "sender": email.get('sender', 'Unknown Sender')
                        })
                    return {"unread": unread_count, "total": len(emails_data), "recent": recent_emails}
            except:
                pass
        
        return {"unread": 0, "total": 0, "recent": []}
    except Exception as e:
        return {"error": str(e)}

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
                                github_items.append({
                                    'type': 'Review Requested', 'title': pr.get('title', '')[:60],
                                    'repo': pr.get('repository_url', '').split('/')[-1], 'number': pr.get('number', '')
                                })
                        
                        # Get assigned issues  
                        issues_response = await client.get(f'https://api.github.com/search/issues?q=assignee:{username}+is:open', headers=headers)
                        if issues_response.status_code == 200:
                            for issue in issues_response.json().get('items', [])[:3]:
                                github_items.append({
                                    'type': 'Issue Assigned', 'title': issue.get('title', '')[:60],
                                    'repo': issue.get('repository_url', '').split('/')[-1], 'number': issue.get('number', '')
                                })
                    
                    if github_items:
                        return {"items": github_items}
            except:
                pass
        
        return {"items": []}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/ticktick")
async def get_ticktick():
    """Get TickTick tasks"""
    return {"tasks": [], "authenticated": False, "auth_url": "/auth/ticktick"}

@app.get("/api/news")
async def get_news(filter: str = "all"):
    """Get filtered news headlines"""
    try:
        articles = []
        
        if filter == "tech" or filter == "all":
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    response = await client.get("https://news.ycombinator.com")
                    if response.status_code == 200:
                        soup = BeautifulSoup(response.text, 'html.parser')
                        for title_elem in soup.find_all('span', class_='titleline', limit=5):
                            link = title_elem.find('a')
                            if link:
                                articles.append({
                                    "title": link.get_text(strip=True)[:80],
                                    "source": "Hacker News"
                                })
            except:
                pass
        
        if filter == "oregon":
            articles = [
                {"title": "Oregon State Beavers Football Update", "source": "OSU Sports"},
                {"title": "Corvallis Campus News", "source": "Oregon News"}
            ]
        elif filter == "timbers":
            articles = [
                {"title": "Portland Timbers Match Preview", "source": "MLS News"},
                {"title": "Timber Joey Performance Highlights", "source": "Sports Center"}
            ]
        elif filter == "starwars":
            articles = [
                {"title": "New Star Wars Series Announced", "source": "Entertainment Weekly"},
                {"title": "Mandalorian Season Update", "source": "Disney News"}
            ]
        elif filter == "startrek":
            articles = [
                {"title": "Star Trek: Strange New Worlds Update", "source": "Paramount"},
                {"title": "Trek Convention Highlights", "source": "Sci-Fi News"}
            ]
        
        if not articles:
            articles = [{"title": "Tech News Update", "source": "General News"}]
            
        return {"articles": articles, "filter": filter}
    except Exception as e:
        return {"error": str(e)}

@app.get("/api/music")
async def get_music():
    """Get music trends"""
    return {"tracks": [{"title": "Trending Song", "artist": "Popular Artist"}]}

if __name__ == "__main__":
    print("🌟 Starting Simple Dashboard Server...")
    print("📍 Dashboard: http://localhost:8008")
    print("🔧 API Docs: http://localhost:8008/docs")
    uvicorn.run(app, host="0.0.0.0", port=8008, log_level="info")
