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

# Add the project root to the path so we can import our collectors
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import database manager
from database import db

# Configure logging
logger = logging.getLogger(__name__)

# Try to import our existing collectors
try:
    from collectors.calendar_collector import CalendarCollector
    from collectors.gmail_collector import GmailCollector
    from collectors.github_collector import GitHubCollector
    from collectors.ticktick_collector import TickTickCollector
    from collectors.jokes_collector import JokesCollector
    from collectors.weather_collector import WeatherCollector
    from config.settings import Settings
    COLLECTORS_AVAILABLE = True
except ImportError as e:
    print(f"Note: Could not import collectors: {e}")
    COLLECTORS_AVAILABLE = False

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
            height: 600px;
            display: flex;
            flex-direction: column;
            position: relative;
        }
        .widget h2 { 
            margin-bottom: 15px; 
            color: #fff; 
            flex-shrink: 0;
        }
        .widget-content {
            flex: 1;
            overflow-y: auto;
            overflow-x: hidden;
        }
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
            flex-shrink: 0;
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
        .top-widgets {
            display: flex;
            gap: 20px;
            margin-bottom: 30px;
            justify-content: center;
            flex-wrap: wrap;
        }
        .mini-widget {
            background: rgba(255,255,255,0.15);
            border-radius: 10px;
            padding: 15px 20px;
            backdrop-filter: blur(10px);
            border: 1px solid rgba(255,255,255,0.3);
            min-width: 300px;
            text-align: center;
        }
        .mini-widget h3 {
            margin-bottom: 8px;
            font-size: 1.1em;
            color: #fff;
        }
        .mini-content {
            font-size: 0.95em;
            opacity: 0.9;
        }
        
        /* Make items clickable */
        .item {
            cursor: pointer;
            transition: all 0.2s ease;
        }
        .item:hover {
            background: rgba(255, 255, 255, 0.1);
            border-radius: 8px;
            transform: translateY(-1px);
        }
        
        .item-summary {
            cursor: default;
            margin-bottom: 10px;
        }
        .item-summary:hover {
            background: none;
            transform: none;
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
    </style>
</head>
<body>
    <div class="container">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
            <h1 style="margin: 0; flex: 1; text-align: center;">📊 Personal Dashboard</h1>
            <button id="admin-btn" onclick="openAdminPanel()" style="
                background: rgba(255,255,255,0.2); 
                border: 1px solid rgba(255,255,255,0.3); 
                border-radius: 50%; 
                width: 40px; 
                height: 40px; 
                color: white; 
                cursor: pointer; 
                font-size: 16px;
                display: flex;
                align-items: center;
                justify-content: center;
                transition: all 0.3s ease;
            " onmouseover="this.style.background='rgba(255,255,255,0.3)'" onmouseout="this.style.background='rgba(255,255,255,0.2)'">
                ⚙️
            </button>
        </div>
        
        <!-- Top Mini Widgets -->
        <div class="top-widgets">
            <div class="mini-widget">
                <h3>😄 Daily Joke</h3>
                <div id="joke-content" class="mini-content loading">Loading...</div>
            </div>
            
            <div class="mini-widget">
                <h3>🌤️ Weather</h3>
                <div id="weather-content" class="mini-content loading">Loading...</div>
            </div>
        </div>
        
        <div class="grid">
            <div class="widget">
                <button class="widget-admin-gear" onclick="openWidgetAdmin('calendar')" title="Configure Calendar">⚙️</button>
                <h2>📅 Calendar Events</h2>
                <div class="widget-content">
                    <div id="calendar-content" class="loading">Loading...</div>
                </div>
            </div>
            
            <div class="widget">
                <button class="widget-admin-gear" onclick="openWidgetAdmin('email')" title="Configure Email">⚙️</button>
                <h2>📧 Email Summary</h2>
                <div class="widget-content">
                    <div id="email-content" class="loading">Loading...</div>
                </div>
            </div>
            
            <div class="widget">
                <button class="widget-admin-gear" onclick="openWidgetAdmin('github')" title="Configure GitHub">⚙️</button>
                <h2>🐙 GitHub Activity</h2>
                <div class="widget-content">
                    <div id="github-content" class="loading">Loading...</div>
                </div>
            </div>
            
            <div class="widget">
                <button class="widget-admin-gear" onclick="openWidgetAdmin('ticktick')" title="Configure TickTick">⚙️</button>
                <h2>✅ TickTick Tasks</h2>
                <div class="widget-content">
                    <div id="ticktick-content" class="loading">Loading...</div>
                </div>
            </div>
            
            <div class="widget">
                <button class="widget-admin-gear" onclick="openWidgetAdmin('news')" title="Configure News">⚙️</button>
                <h2>📰 News Headlines</h2>
                <div class="filter-buttons">
                    <button onclick="filterNews('all')" class="filter-btn active" id="filter-all">All</button>
                    <button onclick="filterNews('tech')" class="filter-btn" id="filter-tech">Tech/AI</button>
                    <button onclick="filterNews('oregon')" class="filter-btn" id="filter-oregon">Oregon State</button>
                    <button onclick="filterNews('timbers')" class="filter-btn" id="filter-timbers">Timbers</button>
                    <button onclick="filterNews('starwars')" class="filter-btn" id="filter-starwars">Star Wars</button>
                    <button onclick="filterNews('startrek')" class="filter-btn" id="filter-startrek">Star Trek</button>
                </div>
                <div class="widget-content">
                    <div id="news-content" class="loading">Loading...</div>
                </div>
            </div>
            
            <div class="widget">
                <button class="widget-admin-gear" onclick="openWidgetAdmin('music')" title="Configure Music">⚙️</button>
                <h2>🎵 Music Trends</h2>
                <div class="widget-content">
                    <div id="music-content" class="loading">Loading...</div>
                </div>
            </div>
            
            <div class="widget">
                <button class="widget-admin-gear" onclick="openWidgetAdmin('vanity')" title="Configure Vanity Alerts">⚙️</button>
                <h2>👁️ Vanity Alerts</h2>
                <div class="widget-content">
                    <div id="vanity-content" class="loading">Loading...</div>
                </div>
            </div>
            
            <div class="widget">
                <h2>❤️ Liked Items</h2>
                <div class="widget-content">
                    <div id="liked-items-content" class="loading">Loading...</div>
                </div>
            </div>
            
            <div class="widget">
                <h2>🤖 AI Assistant 
                    <span class="widget-admin-gear" onclick="openWidgetAdmin('ai')" title="Configure AI Assistant">⚙️</span>
                </h2>
                <div class="widget-content ai-chat-container">
                    <div id="ai-chat-messages" class="chat-messages"></div>
                    <div class="chat-input-container">
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
    </div>
    
    <!-- Widget-specific admin sections (positioned after main grid) -->
    <div id="widget-admin" style="display: none;">
        <!-- Dynamic content will be inserted here -->
    </div>
    
    <button class="refresh-btn" onclick="loadAllData()">🔄 Refresh</button>
    
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
                    <span>📰 News Headlines</span>
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
                    element.innerHTML = data.events ? data.events.map(event => 
                        `<div class="item">
                            <div class="item-title">${event.title}</div>
                            <div class="item-meta">${event.time}</div>
                        </div>`
                    ).join('') : '<div class="item">No events today</div>';
                }
                else if (elementId === 'email-content') {
                    sectionData = data.recent || [];
                    element.innerHTML = `
                        <div class="item-summary">
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
                loadData('/api/calendar', 'calendar-content'),
                loadData('/api/email', 'email-content'),
                loadData('/api/github', 'github-content'),
                loadData('/api/ticktick', 'ticktick-content'),
                loadData('/api/news', 'news-content'),
                loadData('/api/music', 'music-content'),
                loadData('/api/vanity', 'vanity-content'),
                loadData('/api/liked-items', 'liked-items-content')
            ]);
            
            // Make items clickable after all data is loaded
            setTimeout(makeItemsClickable, 100);
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
        
        // Load data on page load
        loadAllData();
        
        // Auto-refresh every 5 minutes
        setInterval(loadAllData, 5 * 60 * 1000);

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
            return 'GitHub Token (Configured)' if get_credentials('github') else 'Not configured';
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
                        # Extract email content and metadata
                        email_body = email.get('body', email.get('snippet', 'No content available'))
                        thread_id = email.get('thread_id', '')
                        message_id = email.get('message_id', '')
                        
                        recent_emails.append({
                            "subject": email.get('subject', 'No Subject'),
                            "sender": email.get('sender', 'Unknown Sender'),
                            "from": email.get('from', email.get('sender', 'Unknown Sender')),
                            "date": email.get('date', email.get('timestamp', 'Unknown date')),
                            "body": email_body,
                            "snippet": email.get('snippet', ''),
                            "read": email.get('read', True),
                            "thread_id": thread_id,
                            "message_id": message_id,
                            "gmail_url": f"https://mail.google.com/mail/u/0/#inbox/{thread_id}" if thread_id else "https://mail.google.com/mail/u/0/#inbox",
                            "labels": email.get('labels', []),
                            "attachments": email.get('attachments', [])
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
                        issues_response = await client.get(f'https://api.github.com/search/issues?q=assignee:{username}+is:open', headers=headers)
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
                    
                    if github_items:
                        return {"items": github_items}
            except Exception as e:
                print(f"GitHub API error: {e}")
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
    """Get filtered news headlines using the NewsCollector"""
    try:
        if COLLECTORS_AVAILABLE:
            from collectors.news_collector import NewsCollector
            collector = NewsCollector()
            news_data = await collector.collect_data()
            
            # Get previously rated news items to filter them out
            rated_item_ids = db.get_rated_item_ids('news')
            
            # Filter articles based on the filter parameter and exclude rated items
            articles = []
            if news_data and 'articles' in news_data:
                for article in news_data['articles']:
                    # Create a unique ID for this article
                    article_id = f"news_{article.get('id', '')}" or f"news_{hash(article['title'] + article.get('url', ''))}"
                    
                    # Skip if already rated
                    if article_id in rated_item_ids:
                        continue
                        
                    # Apply filter logic
                    article_data = {
                        "id": article_id,  # Add ID for tracking
                        "title": article['title'],
                        "source": article['source'],
                        "url": article['url'],
                        "description": article['snippet'] or "No description available",
                        "published_at": article.get('published_date', 'Unknown'),
                        "category": ', '.join(article.get('topics', ['General'])),
                        "relevance_score": article.get('relevance_score', 0.0)
                    }
                    
                    if filter == "all":
                        articles.append(article_data)
                    elif filter == "tech" and any(topic.lower() in ['star wars', 'star trek'] for topic in article.get('topics', [])):
                        articles.append(article_data)
                    elif filter == "oregon" and any('oregon' in topic.lower() for topic in article.get('topics', [])):
                        articles.append(article_data)
                    elif filter == "timbers" and any('timbers' in topic.lower() or 'portland' in topic.lower() for topic in article.get('topics', [])):
                        articles.append(article_data)
            
            # If no articles from collector, fall back to Hacker News
            if not articles:
                articles = await get_hacker_news_articles()
                # Filter out rated Hacker News articles too
                articles = [article for article in articles if article.get('id', '') not in rated_item_ids]
                
            return {
                "articles": articles[:20],  # Limit to 20 articles
                "filter": filter,
                "total": len(articles),
                "source": "NewsCollector" if articles else "Fallback"
            }
        else:
            # Fallback when collectors not available
            articles = await get_hacker_news_articles()
            return {"articles": articles, "filter": filter, "source": "Fallback"}
            
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

@app.get("/api/joke")
async def get_joke():
    """Get a daily joke"""
    try:
        if COLLECTORS_AVAILABLE:
            try:
                jokes_collector = JokesCollector()
                joke_result = await jokes_collector._fetch_single_joke()
                if joke_result:
                    return {"joke": joke_result.get('text', 'No joke available')}
            except:
                pass
        
        # Fallback jokes
        fallback_jokes = [
            "Why don't scientists trust atoms? Because they make up everything! 😄",
            "Why did the scarecrow win an award? He was outstanding in his field! 🌾",
            "Why don't eggs tell jokes? They'd crack each other up! 🥚",
            "What do you call a bear with no teeth? A gummy bear! 🐻",
            "Why did the math book look so sad? Because it had too many problems! 📚"
        ]
        import random
        return {"joke": random.choice(fallback_jokes)}
    except Exception as e:
        return {"error": str(e)}

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
        
        # Convert to provider format
        chat_messages = []
        for msg in messages:
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
        else:
            db.update_ai_model_training_status(training_id, 'failed', 
                                             error_log=training_result.get('error'))
        
        return {
            "success": True,
            "training_id": training_id,
            "result": training_result
        }
        
    except Exception as e:
        logger.error(f"Error starting AI training: {e}")
        return {"error": str(e)}


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


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    await initialize_ai_providers()
    logger.info("Dashboard startup complete")


if __name__ == "__main__":
    print("🌟 Starting Simple Dashboard Server...")
    print("📍 Dashboard: http://localhost:8008")
    print("🔧 API Docs: http://localhost:8008/docs")
    uvicorn.run(app, host="0.0.0.0", port=8008, log_level="info")
