# AI Context Enhancement

## Problem
The AI assistant was responding generically, saying things like "I need to know more about your current projects" instead of using the actual calendar, todos, and email data that was already loaded in the dashboard.

## Root Cause
1. **Frontend**: `sendAIMessage()` in `dashboard.js` was only sending basic counts:
   ```javascript
   context: {
       todos_count: this.todos.length,
       emails_count: this.emails.length,
       has_high_priority: this.emails.some(e => e.priority === 'high')
   }
   ```

2. **Backend**: The AI system message didn't explicitly instruct the model to use the provided context data.

## Solution

### Frontend Changes (`static/dashboard.js`)
Enhanced `sendAIMessage()` to send comprehensive context with actual data:

```javascript
const context = {
    current_time: new Date().toLocaleString(),
    todos: {
        count: this.todos.length,
        active_count: this.todos.filter(t => !t.completed).length,
        items: this.todos.slice(0, 10).map(t => ({
            title: t.title,
            priority: t.priority,
            due_date: t.due_date,
            source: t.source,
            completed: t.completed,
            description: t.description ? t.description.substring(0, 100) : null
        }))
    },
    calendar: {
        count: this.calendar.length,
        upcoming: this.calendar
            .filter(e => new Date(e.start) > new Date())
            .slice(0, 5)
            .map(e => ({
                summary: e.summary,
                start: e.start,
                location: e.location,
                description: e.description ? e.description.substring(0, 100) : null
            }))
    },
    emails: {
        count: this.emails.length,
        high_priority_count: this.emails.filter(e => e.priority === 'high').length,
        recent: this.emails.slice(0, 5).map(e => ({
            subject: e.subject,
            sender: e.sender,
            priority: e.priority,
            has_todos: e.has_todos,
            snippet: e.snippet ? e.snippet.substring(0, 100) : null
        }))
    },
    user_preferences: {
        liked_items_count: Object.keys(this.feedbackData).filter(
            k => this.feedbackData[k] === 'like'
        ).length,
        recent_feedback: Object.entries(this.feedbackData)
            .slice(-5)
            .map(([key, value]) => ({ item: key, sentiment: value }))
    }
};
```

**Now sends**: Actual task titles, calendar event summaries, email subjects, and user feedback preferences.

### Backend Changes (`main.py`)

#### New Function: `build_ai_context_with_frontend()`
Created a new context builder that accepts frontend data and formats it for the AI:

```python
async def build_ai_context_with_frontend(user_message: str, frontend_context: dict) -> str:
    """Build context for AI from frontend data and database."""
    context_parts = []
    
    # Formats todos with status, priority, due dates
    # Formats calendar events with times and locations
    # Formats emails with senders, subjects, priorities
    # Includes user preferences and feedback patterns
    # Adds user profile from database (vanity_config)
    
    return '\n'.join(context_parts)
```

**Output format example**:
```
Current time: Wednesday, January 15, 2025 at 2:30 PM

TASKS (3 active of 5 total):
○ [high] Complete dashboard AI enhancements (Due: 2025-01-16) (GitHub)
   Fix AI context awareness issue
✓ [medium] Update documentation
○ Fix email rendering bug (TickTick)

UPCOMING CALENDAR EVENTS (2 shown):
- Team Standup
  2025-01-16T09:00:00 @ Zoom
- Client Review Meeting
  2025-01-16T14:00:00 @ Conference Room A
  Quarterly review with stakeholders

RECENT EMAILS (5 shown, 2 high priority):
[high] 📋 From: boss@company.com
  Subject: Urgent: Q1 Report needed by Friday
  Need the quarterly metrics compiled...
```

#### Enhanced System Prompt
Updated the AI system message with explicit instructions:

```python
system_message = f"""You are a personal AI assistant with DIRECT ACCESS to the user's dashboard data. 

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
```

## Impact

### Before
User: "What should I work on today?"
AI: "I'm happy to help you with your task list! However, I need to know more about your current projects and priorities."

### After
User: "What should I work on today?"
AI: "Based on your dashboard, I recommend prioritizing:
1. **Complete dashboard AI enhancements** (high priority, due tomorrow) - This appears urgent
2. **Fix email rendering bug** from TickTick
3. You also have a Team Standup at 9am and Client Review at 2pm tomorrow, so plan accordingly"

## Benefits
1. ✅ AI now has full visibility into user's actual data
2. ✅ Responses are specific and actionable
3. ✅ No more generic "tell me more" responses
4. ✅ AI can suggest priorities based on due dates and priorities
5. ✅ AI can identify schedule conflicts
6. ✅ User preferences from feedback system are included
7. ✅ Context includes up to 10 tasks, 5 calendar events, 5 emails per request

## Technical Details

### Data Flow
1. User types message in AI chat
2. Frontend `sendAIMessage()` gathers current dashboard data from loaded arrays
3. Context payload sent to `/api/ai/chat` endpoint
4. Backend `build_ai_context_with_frontend()` formats context into readable text
5. System prompt + context + conversation history sent to AI provider (Ollama/OpenRouter)
6. AI response references actual data from context
7. Response displayed and optionally spoken via TTS

### Performance
- Context size: ~2-5KB typical (compressed summary of top items)
- No additional database queries needed (uses already-loaded frontend data)
- Context rebuilt fresh for each message (always current)

### Fallback
- Legacy `build_ai_context()` function retained for backwards compatibility
- If frontend sends no context, backend falls back to keyword-based database queries

## Testing
To test the enhancement:
1. Load dashboard with tasks, calendar, emails visible
2. Open AI Assistant section
3. Ask: "What should I work on?" or "What's on my calendar?" or "Any important emails?"
4. AI should reference specific items by name/title

## Future Enhancements
- [ ] Include GitHub issues in context
- [ ] Include news articles user has liked
- [ ] Include vanity alerts (brand mentions)
- [ ] Add weather context for outdoor events
- [ ] Use feedback data to personalize tone and suggestions
- [ ] Implement context summarization for very long lists
