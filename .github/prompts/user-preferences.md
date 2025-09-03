# User Preferences & Memory System

## Core User Requirements
- **Data Display**: User wants ALL data displayed on screen with like/dislike functionality
- **Learning System**: Liked content should be stored in long-term memory, disliked content hidden
- **No Hidden Data**: Everything should be visible and interactive
- **Preference Learning**: System should learn from user interactions

## User Behavior Patterns
- Prefers consolidated, single-system approaches over multiple fragmented solutions
- Values clean, working implementations over complex multi-file structures
- Wants immediate visual feedback on all dashboard interactions
- Expects like/dislike functionality on ALL content types

## Technical Preferences
- **Server**: Uses unified server approach (dashboard/server.py)
- **Database**: SQLite with preference tracking
- **Startup**: ALWAYS use ./startup.sh (see startup-protocol.md)
- **Architecture**: Consolidated collectors, unified APIs

## Memory Files to Check
- `LONG_TERM_MEMORY.md` - User preferences and session history
- `.github/prompts/` - All AI assistant instructions
- `.github/copilot-instructions.md` - VS Code Copilot specific

## Update Protocol
When user preferences change:
1. Update this file
2. Update LONG_TERM_MEMORY.md
3. Document in .github/copilot-instructions.md
4. Test the changes work as expected
