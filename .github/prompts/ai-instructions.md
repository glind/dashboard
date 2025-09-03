# AI Assistant Instructions

## BEFORE STARTING ANY WORK:
1. **READ**: `.github/prompts/startup-protocol.md` - MANDATORY startup process
2. **READ**: `.github/prompts/user-preferences.md` - User requirements 
3. **READ**: `.github/prompts/project-status.md` - Current system state
4. **CHECK**: `LONG_TERM_MEMORY.md` - Session history and preferences

## CRITICAL RULES:
- 🚨 **ALWAYS use `./startup.sh`** - Never start server any other way
- 🔍 **Check existing systems** before creating new ones
- 🧹 **Consolidate, don't fragment** - User prefers unified solutions
- 📊 **Show everything** - User wants all data visible with like/dislike
- 💾 **Update memory** - Document changes in memory files

## Working Features (DO NOT BREAK):
- Unified server at `dashboard/server.py`
- Vanity alerts with 271+ entries in database
- Like/dislike functionality
- Fresh jokes API
- Email analysis
- Calendar events

## Common Mistakes to AVOID:
- Starting server with `python3 main.py` directly
- Creating multiple servers instead of using unified one
- Not checking what's already working
- Breaking existing functionality while adding new features

## When Making Changes:
1. Test existing functionality first
2. Make incremental changes
3. Update memory files
4. Verify nothing is broken
5. Document what was changed

## Emergency Recovery:
If something breaks:
```bash
pkill -f "main.py"
./startup.sh
curl http://localhost:8008/health
```
