# Dashboard AI Memory System

This folder contains critical information that ALL AI assistants must read before working on this project.

## 📚 Required Reading (in order):

### 1. [AI Instructions](ai-instructions.md) 🤖
**READ FIRST** - Critical rules, common mistakes to avoid, and working features

### 2. [Startup Protocol](startup-protocol.md) 🚀  
**MANDATORY** - How to properly start the dashboard (ALWAYS use `./startup.sh`)

### 3. [User Preferences](user-preferences.md) 👤
**IMPORTANT** - User requirements, behavior patterns, and expectations

### 4. [Project Status](project-status.md) 📊
**CURRENT STATE** - What's working, what's been cleaned up, system architecture

### 5. [Session Memory](session-memory.md) 💾
**HISTORY** - Previous sessions, user interactions, and preferences learned

## 🎯 Quick Reference:

**Start Dashboard:** `./startup.sh` (NEVER use `python3 main.py`)
**Health Check:** `curl http://localhost:8008/health`
**Working APIs:** `/api/vanity-alerts`, `/api/jokes/random`, `/api/email/analyze`
**User Wants:** All data visible with like/dislike functionality

## 🔄 Update Protocol:
When making changes, update relevant files in this folder to ensure future AI assistants have current information.

**This system ensures consistency across all AI assistants working on the dashboard project.**
