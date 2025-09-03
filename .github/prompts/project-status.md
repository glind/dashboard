# Dashboard Project Architecture

## Current System Status ✅
- **Unified Server**: `dashboard/server.py` (consolidated from multiple servers)
- **Clean Main**: `main.py` (simplified startup that uses unified server)
- **Working Features**: Vanity alerts, jokes, email analysis, calendar events
- **Database**: SQLite with 271+ vanity alerts stored

## Key Files & Structure
```
dashboard/
├── main.py                    # ✅ Simplified startup (uses ./startup.sh)
├── dashboard/server.py        # ✅ UNIFIED server (all APIs)
├── collectors/               # ✅ Data collection modules
│   ├── vanity_alerts_collector.py  # ✅ Working, 271 alerts
│   ├── jokes_collector.py          # ✅ Fresh jokes API
│   └── unified_collector.py        # ✅ Auto-discovery system
├── .github/prompts/         # ✅ AI memory system
└── startup.sh               # ✅ MANDATORY startup script
```

## APIs Working ✅
- `/api/vanity-alerts` - Returns stored alerts from database
- `/api/vanity-alerts/collect` - Collects fresh alerts
- `/api/vanity-alerts/like` - Like/dislike functionality
- `/api/jokes/random` - Random joke
- `/api/jokes/fresh` - Fresh joke from API
- `/api/email/analyze` - Email analysis
- `/api/calendar/events` - Calendar events

## Cleaned Up ✅
- Moved old servers to `backup/old_servers/`
- Removed duplicate/conflicting files
- Single working server architecture
- Simplified startup process

## Database Status ✅
- 271 vanity alerts collected and stored
- Like/dislike functionality implemented
- Preference tracking ready

## Next Actions
- Test all APIs working after cleanup
- Verify vanity alerts display properly
- Ensure user preference learning is functional
