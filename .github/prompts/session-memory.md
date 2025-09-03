# Dashboard Long-Term Memory & Preferences

## � **ABSOLUTE CRITICAL STARTUP PROTOCOL** 🚨
### ⚠️ **READ THIS FIRST - EVERY TIME** ⚠️

**🔴 MANDATORY: ALWAYS use `./startup.sh` to start the dashboard server**
**🔴 FORBIDDEN: NEVER use direct uvicorn, python main.py, or other methods**

**Why this matters:**
- startup.sh handles virtual environment activation
- Sets up proper database connections  
- Installs/updates dependencies
- Validates configuration
- Uses correct Python interpreter

### Quick Start Commands:
```bash
cd /home/glind/Projects/mine/dashboard
./startup.sh  # ← THIS IS THE ONLY WAY TO START
```

**❌ Do NOT use:**
- `python main.py`
- `python3 main.py` 
- `uvicorn dashboard.server:app`
- Direct FastAPI calls

**✅ Always use:**
- `./startup.sh` (for starting)
- `./dev.sh` (for development)

---

## 🎯 **USER INTERACTION PREFERENCES**

### Data Display & Interaction Pattern:
1. **ALWAYS display data on screen first** 
2. **User likes/dislikes items to train the system**
3. **Liked items → saved to database for long-term memory**
4. **Disliked items → hidden and never shown again**

### Like/Dislike Functionality Requirements:
- **Jokes**: Like button saves to preferences, loads new joke automatically
- **Vanity Alerts**: Like saves to database, dislike hides forever
- **Email Analysis**: User can like insights to remember them
- **Calendar Events**: User can mark events as important
- **News Articles**: Like saves to reading list, dislike filters out similar content
- **Network Devices**: Like saves as "known good" devices
- **Weather**: User preferences for display format/details

## 🔧 **TECHNICAL IMPLEMENTATION NOTES**

### Database Schema for Preferences:
```sql
- user_preferences (item_type, item_id, is_liked, timestamp)
- saved_content (content_type, content_data, user_rating, save_date)
- hidden_content (content_type, content_id, hide_reason, hide_date)
```

### API Endpoints Required:
- `/api/{service}/like` - Save user preference
- `/api/{service}/dislike` - Hide content
- `/api/preferences/get` - Get user preferences
- `/api/content/saved` - Get saved content
- `/api/content/hidden` - Get hidden content list

### Data Collection Strategy:
1. Always show fresh data first
2. Apply user preferences as filters
3. Learn from user interactions
4. Improve recommendations over time

## 🚀 **CURRENT FEATURES STATUS**

### ✅ Working:
- Tab navigation with proper CSS
- Joke widget with like/dislike (saves preferences)
- Network map showing all devices
- Fresh joke fetching per request

### 🔧 Fixed in Latest Update:
- Fresh joke API endpoint (no more repeated jokes)
- Vanity alerts collection button functionality
- Email analysis with loading states
- Calendar events "View All" functionality
- Enhanced vanity alerts with like/dislike buttons

### 📋 Implementation Pattern:
Each data widget should follow this pattern:
1. Load and display raw data
2. Show like/dislike buttons
3. Apply user preferences to filter
4. Save interactions to database
5. Use ML/AI to improve recommendations

## 🎨 **UI/UX Guidelines**
- Green thumb-up = Like & Save
- Red thumb-down = Hide Forever  
- Always show visual feedback on interaction
- Loading states during processing
- Modal popups for detailed views
- Responsive design for all screen sizes

This system creates a learning dashboard that gets better over time based on user preferences.
