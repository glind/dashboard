"""
Centralized AI Service - Single source of truth for all AI interactions.
Manages user profile, context building, and AI provider connections.
"""

import json
import gzip
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class AIService:
    """
    Centralized AI service that:
    - Manages a single AI provider connection (configured in settings)
    - Builds and maintains user profile from dashboard data
    - Creates compressed context for each AI request
    - Learns from user interactions (likes, dislikes, todos)
    """
    
    def __init__(self, db, settings=None):
        """Initialize AI service with database connection."""
        self.db = db
        self.settings = settings
        self._provider = None
        self._context_cache = None
        self._context_cache_time = None
        self._user_profile_cache = None
        self._profile_cache_time = None
        self.cache_duration = timedelta(minutes=5)
        
    def get_provider(self):
        """Get or create the configured AI provider (singleton pattern)."""
        if self._provider is None:
            self._initialize_provider()
        return self._provider
    
    def reset_provider(self):
        """Reset the provider (called when settings change)."""
        self._provider = None
        logger.info("AI provider reset - will reinitialize on next use")
    
    def _initialize_provider(self):
        """Initialize AI provider from settings."""
        try:
            from processors.ai_providers import create_provider, ai_manager
            
            # Try to get from ai_manager first
            provider = ai_manager.get_provider()
            if provider:
                self._provider = provider
                logger.info(f"Using existing AI provider: {provider.name}")
                return
            
            # Otherwise create from settings
            ai_provider_type = self.db.get_setting('ai_provider', 'ollama')
            
            if ai_provider_type == 'ollama':
                ollama_host = self.db.get_setting('ollama_host', 'localhost')
                ollama_port = self.db.get_setting('ollama_port', 11434)
                ollama_model = self.db.get_setting('ollama_model', 'llama3.2:latest')
                
                config = {
                    'base_url': f'http://{ollama_host}:{ollama_port}',
                    'model_name': ollama_model
                }
                
                self._provider = create_provider('ollama', 'configured-ollama', config)
                ai_manager.register_provider(self._provider, is_default=True)
                logger.info(f"Initialized Ollama provider: {ollama_host}:{ollama_port} with {ollama_model}")
                
            elif ai_provider_type == 'openai':
                api_key = self.db.get_credentials('openai', {}).get('api_key')
                model = self.db.get_setting('openai_model', 'gpt-3.5-turbo')
                
                config = {
                    'api_key': api_key,
                    'model_name': model
                }
                
                self._provider = create_provider('openai', 'configured-openai', config)
                ai_manager.register_provider(self._provider, is_default=True)
                logger.info(f"Initialized OpenAI provider with {model}")
                
        except Exception as e:
            logger.error(f"Failed to initialize AI provider: {e}")
            self._provider = None
    
    def build_user_profile(self, force_refresh: bool = False) -> Dict[str, Any]:
        """
        Build comprehensive user profile from all dashboard data.
        Cached for performance.
        """
        # Return cached profile if recent
        if not force_refresh and self._user_profile_cache and self._profile_cache_time:
            if datetime.now() - self._profile_cache_time < self.cache_duration:
                return self._user_profile_cache
        
        try:
            profile = {
                'generated_at': datetime.now().isoformat(),
                'user_info': self._get_user_info(),
                'preferences': self._get_user_preferences(),
                'patterns': self._get_user_patterns(),
                'interests': self._get_user_interests(),
                'work_style': self._get_work_style(),
                'communication_preferences': self._get_communication_preferences()
            }
            
            # Cache the profile
            self._user_profile_cache = profile
            self._profile_cache_time = datetime.now()
            
            return profile
            
        except Exception as e:
            logger.error(f"Error building user profile: {e}")
            return {}
    
    def _get_user_info(self) -> Dict[str, Any]:
        """Get basic user information."""
        try:
            user_profile = self.db.get_user_profile()
            if user_profile:
                return {
                    'name': user_profile.get('preferred_name') or user_profile.get('full_name', 'User'),
                    'company': user_profile.get('company'),
                    'role': user_profile.get('role'),
                    'work_focus': user_profile.get('work_focus'),
                    'timezone': user_profile.get('timezone', 'America/Los_Angeles')
                }
        except:
            pass
        
        return {'name': 'User', 'timezone': 'America/Los_Angeles'}
    
    def _get_user_preferences(self) -> Dict[str, Any]:
        """Analyze likes/dislikes to understand preferences."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get liked items by type
                cursor.execute("""
                    SELECT item_type, COUNT(*) as count,
                           GROUP_CONCAT(item_title, '|||') as titles
                    FROM user_feedback
                    WHERE feedback_type = 'like'
                    GROUP BY item_type
                """)
                
                preferences = {}
                for row in cursor.fetchall():
                    item_type = row['item_type']
                    count = row['count']
                    titles = row['titles'].split('|||') if row['titles'] else []
                    
                    preferences[item_type] = {
                        'count': count,
                        'examples': titles[:5]  # Top 5 examples
                    }
                
                return preferences
                
        except Exception as e:
            logger.error(f"Error getting preferences: {e}")
            return {}
    
    def _get_user_patterns(self) -> Dict[str, Any]:
        """Analyze patterns from todos, calendar, and emails."""
        try:
            patterns = {
                'task_patterns': self._analyze_task_patterns(),
                'calendar_patterns': self._analyze_calendar_patterns(),
                'email_patterns': self._analyze_email_patterns()
            }
            return patterns
        except Exception as e:
            logger.error(f"Error analyzing patterns: {e}")
            return {}
    
    def _analyze_task_patterns(self) -> Dict[str, Any]:
        """Analyze task completion patterns."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get task statistics
                cursor.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                        priority,
                        category
                    FROM todos
                    WHERE created_at > datetime('now', '-30 days')
                    GROUP BY priority, category
                """)
                
                stats = []
                for row in cursor.fetchall():
                    stats.append(dict(row))
                
                return {
                    'recent_task_stats': stats,
                    'most_common_categories': [s['category'] for s in stats if s['category']][:3]
                }
        except:
            return {}
    
    def _analyze_calendar_patterns(self) -> Dict[str, Any]:
        """Analyze calendar patterns."""
        # TODO: Implement based on calendar data
        return {}
    
    def _analyze_email_patterns(self) -> Dict[str, Any]:
        """Analyze email patterns."""
        # TODO: Implement based on email data
        return {}
    
    def _get_user_interests(self) -> Dict[str, Any]:
        """Extract user interests from various sources."""
        try:
            interests = {
                'topics': [],
                'sources': []
            }
            
            # Get from news preferences
            news_config = self.db.get_setting('news_config', {})
            if isinstance(news_config, dict):
                sources = news_config.get('sources', [])
                interests['sources'] = sources[:10]
            
            # Get from liked news
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT item_title
                    FROM user_feedback
                    WHERE item_type = 'news' AND feedback_type = 'like'
                    ORDER BY feedback_timestamp DESC
                    LIMIT 10
                """)
                
                liked_news = [row['item_title'] for row in cursor.fetchall()]
                if liked_news:
                    interests['liked_topics'] = liked_news
            
            return interests
            
        except Exception as e:
            logger.error(f"Error getting interests: {e}")
            return {}
    
    def _get_work_style(self) -> Dict[str, Any]:
        """Analyze work style from task and calendar patterns."""
        try:
            user_profile = self.db.get_user_profile()
            if user_profile:
                return {
                    'work_hours': user_profile.get('work_hours', '9am-5pm'),
                    'priorities': user_profile.get('priorities', '').split(',') if user_profile.get('priorities') else []
                }
        except:
            pass
        
        return {}
    
    def _get_communication_preferences(self) -> Dict[str, Any]:
        """Get communication style preferences."""
        try:
            user_profile = self.db.get_user_profile()
            if user_profile:
                return {
                    'style': user_profile.get('communication_style', 'Professional and friendly'),
                    'tone': user_profile.get('preferred_tone', 'Helpful and concise')
                }
        except:
            pass
        
        return {'style': 'Professional and friendly', 'tone': 'Helpful and concise'}
    
    def build_context(self, user_message: str = "", force_refresh: bool = False) -> str:
        """
        Build comprehensive context for AI requests.
        Includes user profile, recent data, and relevant information.
        """
        # Return cached context if recent and no specific message
        if not force_refresh and not user_message and self._context_cache and self._context_cache_time:
            if datetime.now() - self._context_cache_time < self.cache_duration:
                return self._context_cache
        
        try:
            context_parts = []
            
            # 1. User Profile
            profile = self.build_user_profile()
            context_parts.append("=== USER PROFILE ===")
            context_parts.append(f"Name: {profile.get('user_info', {}).get('name', 'User')}")
            
            user_info = profile.get('user_info', {})
            if user_info.get('company'):
                context_parts.append(f"Company: {user_info['company']}")
            if user_info.get('role'):
                context_parts.append(f"Role: {user_info['role']}")
            
            # 2. Current Time Context
            now = datetime.now()
            context_parts.append(f"\n=== CURRENT CONTEXT ===")
            context_parts.append(f"Current Time: {now.strftime('%A, %B %d, %Y at %I:%M %p')}")
            
            # 3. Active Tasks (top priority)
            context_parts.append(f"\n=== ACTIVE TASKS ===")
            todos = self.db.get_todos(include_completed=False, include_deleted=False)
            if todos:
                high_priority = [t for t in todos if t.get('priority') == 'high']
                medium_priority = [t for t in todos if t.get('priority') == 'medium']
                
                if high_priority:
                    context_parts.append("High Priority:")
                    for todo in high_priority[:5]:
                        due = todo.get('due_date', 'no date')
                        context_parts.append(f"  - [{todo['id']}] {todo['title']} (due: {due})")
                
                if medium_priority:
                    context_parts.append("Medium Priority:")
                    for todo in medium_priority[:5]:
                        due = todo.get('due_date', 'no date')
                        context_parts.append(f"  - [{todo['id']}] {todo['title']} (due: {due})")
                
                context_parts.append(f"Total active tasks: {len(todos)}")
            else:
                context_parts.append("No active tasks")
            
            # 4. Today's Calendar Events
            context_parts.append(f"\n=== TODAY'S SCHEDULE ===")
            try:
                # Get today's events from database
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT summary, start_time, end_time, location, description
                        FROM calendar_events
                        WHERE date(start_time) = date('now')
                        ORDER BY start_time
                        LIMIT 10
                    """)
                    
                    events = cursor.fetchall()
                    if events:
                        for event in events:
                            time_str = event['start_time'].split('T')[1][:5] if 'T' in event['start_time'] else ''
                            context_parts.append(f"  - {time_str} {event['summary']}")
                            if event.get('location'):
                                context_parts.append(f"    Location: {event['location']}")
                    else:
                        context_parts.append("No events scheduled for today")
            except:
                context_parts.append("(Calendar data not available)")
            
            # 5. Recent Emails (important/unread)
            context_parts.append(f"\n=== RECENT IMPORTANT EMAILS (You have full access to these) ===")
            try:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    # Get both high priority and recent emails
                    cursor.execute("""
                        SELECT subject, sender, snippet, priority, has_todos, received_at
                        FROM emails
                        WHERE priority = 'high' OR has_todos = 1 OR received_at >= date('now', '-2 days')
                        ORDER BY received_at DESC
                        LIMIT 10
                    """)
                    
                    emails = cursor.fetchall()
                    if emails:
                        context_parts.append(f"You have access to {len(emails)} recent/important emails:")
                        for email in emails:
                            flags = []
                            if email.get('priority') == 'high':
                                flags.append('HIGH')
                            if email.get('has_todos'):
                                flags.append('TODO')
                            flag_str = f"[{','.join(flags)}]" if flags else ""
                            
                            context_parts.append(f"  {flag_str} From: {email['sender']}")
                            context_parts.append(f"    Subject: {email['subject']}")
                            if email.get('snippet'):
                                snippet = email['snippet'][:100]
                                context_parts.append(f"    Preview: {snippet}...")
                    else:
                        context_parts.append("No recent emails found in database (may need to collect)")
            except Exception as e:
                context_parts.append(f"(Email data not available: {str(e)})")
            
            # 6. GitHub Activity
            context_parts.append(f"\n=== GITHUB ACTIVITY ===")
            try:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT title, state, repo, url
                        FROM github_issues
                        WHERE state = 'open'
                        ORDER BY updated_at DESC
                        LIMIT 5
                    """)
                    
                    issues = cursor.fetchall()
                    if issues:
                        context_parts.append(f"Open Issues ({len(issues)}):")
                        for issue in issues:
                            context_parts.append(f"  - {issue['repo']}: {issue['title']}")
                    else:
                        context_parts.append("No open GitHub issues")
            except:
                context_parts.append("(GitHub data not available)")
            
            # 7. Recent News (liked topics)
            context_parts.append(f"\n=== RECENT NEWS ===")
            try:
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        SELECT title, source
                        FROM news_items
                        ORDER BY published_at DESC
                        LIMIT 5
                    """)
                    
                    news = cursor.fetchall()
                    if news:
                        for item in news:
                            context_parts.append(f"  - [{item['source']}] {item['title']}")
                    else:
                        context_parts.append("No recent news")
            except:
                context_parts.append("(News data not available)")
            
            # 8. Weather
            context_parts.append(f"\n=== WEATHER ===")
            try:
                weather_data = self.db.get_setting('last_weather', {})
                if isinstance(weather_data, dict) and weather_data.get('current'):
                    current = weather_data['current']
                    context_parts.append(f"Current: {current.get('temp', 'N/A')}°F, {current.get('condition', 'N/A')}")
                else:
                    context_parts.append("Weather data not available")
            except:
                context_parts.append("(Weather data not available)")
            
            # 9. Recent Notes (from Obsidian and Google Drive)
            context_parts.append(f"\n=== RECENT NOTES & MEETINGS ===")
            try:
                from collectors.notes_collector import collect_all_notes
                from database import get_credentials
                
                notes_config = get_credentials('notes') or {}
                obsidian_path = self.db.get_setting('obsidian_vault_path') or notes_config.get('obsidian_vault_path')
                gdrive_folder_id = self.db.get_setting('google_drive_notes_folder_id') or notes_config.get('google_drive_folder_id')
                
                result = collect_all_notes(
                    obsidian_path=obsidian_path,
                    gdrive_folder_id=gdrive_folder_id,
                    limit=10
                )
                
                notes = result.get('notes', [])
                if notes:
                    context_parts.append(f"Recent notes ({len(notes)} available):")
                    for i, note in enumerate(notes[:5], 1):
                        source_icon = "📝" if note['source'] == 'obsidian' else "☁️"
                        todo_count = len(note.get('todos', []))
                        todo_str = f" ({todo_count} TODOs)" if todo_count > 0 else ""
                        context_parts.append(f"  {i}. {source_icon} {note['title']}{todo_str}")
                        context_parts.append(f"     Modified: {note.get('modified_at', 'Unknown')[:10]}")
                        if note.get('preview'):
                            context_parts.append(f"     Preview: {note['preview'][:100]}...")
                    
                    context_parts.append(f"\nNote: User can ask to 'summarize meeting with X' or 'extract tasks from note Y'")
                else:
                    context_parts.append("No recent notes available")
            except Exception as e:
                logger.error(f"Error loading notes for context: {e}")
                context_parts.append("(Notes data not available)")
            
            # 10. User Preferences (what they like)
            preferences = profile.get('preferences', {})
            if preferences:
                context_parts.append(f"\n=== USER PREFERENCES (Learned from Likes) ===")
                for pref_type, pref_data in preferences.items():
                    if pref_data.get('count', 0) > 0:
                        context_parts.append(f"{pref_type.title()}: {pref_data['count']} items liked")
                        if pref_data.get('examples'):
                            context_parts.append(f"  Recent: {', '.join(pref_data['examples'][:2])}")
            
            # 11. Communication Style
            comm_prefs = profile.get('communication_preferences', {})
            context_parts.append(f"\n=== COMMUNICATION PREFERENCES ===")
            context_parts.append(f"Style: {comm_prefs.get('style', 'Professional and friendly')}")
            
            # 8. AI Capabilities
            context_parts.append(f"\n=== YOUR CAPABILITIES ===")
            context_parts.append("You can help with:")
            context_parts.append("  - View and analyze tasks, calendar, emails, GitHub issues, news, weather")
            context_parts.append("  - Suggest creating new tasks (you'll ask for user approval)")
            context_parts.append("  - Suggest deleting/completing tasks (you'll ask for user approval)")
            context_parts.append("  - Prioritize and organize information")
            context_parts.append("  - Learn from user preferences to improve suggestions")
            
            context = "\n".join(context_parts)
            
            # Cache the context
            if not user_message:  # Only cache general context, not message-specific
                self._context_cache = context
                self._context_cache_time = datetime.now()
            
            return context
            
        except Exception as e:
            logger.error(f"Error building context: {e}")
            return f"Current Time: {datetime.now().strftime('%A, %B %d, %Y at %I:%M %p')}"
    
    def compress_context(self, context: str) -> bytes:
        """Compress context for efficient transmission."""
        try:
            context_bytes = context.encode('utf-8')
            compressed = gzip.compress(context_bytes, compresslevel=9)
            
            # Log compression ratio
            original_size = len(context_bytes)
            compressed_size = len(compressed)
            ratio = (1 - compressed_size / original_size) * 100
            logger.debug(f"Context compressed: {original_size} -> {compressed_size} bytes ({ratio:.1f}% reduction)")
            
            return compressed
            
        except Exception as e:
            logger.error(f"Error compressing context: {e}")
            return context.encode('utf-8')
    
    def get_context_hash(self, context: str) -> str:
        """Generate hash of context for change detection."""
        return hashlib.sha256(context.encode('utf-8')).hexdigest()
    
    async def chat(self, message: str, conversation_id: str = None, include_context: bool = True) -> Dict[str, Any]:
        """
        Main chat interface - uses configured provider with full context.
        
        Args:
            message: User's message
            conversation_id: Optional conversation ID for history
            include_context: Whether to include full user context
        
        Returns:
            Dict with response, context info, and metadata
        """
        try:
            provider = self.get_provider()
            if not provider:
                return {
                    'error': 'No AI provider configured',
                    'success': False
                }
            
            # Build context
            context = self.build_context(message) if include_context else ""
            
            # Build messages for chat
            messages = []
            
            # System message with context
            if context:
                # Use string concatenation to avoid f-string issues with curly braces in context
                system_message = "You are a personal AI assistant with direct access to the user's dashboard data.\n\n"
                system_message += context
                system_message += f"""

=== YOUR CORE CAPABILITIES ===

**TASK MANAGEMENT:**
- Search existing tasks by keyword, status, priority, or due date
- Create single or multiple tasks from conversations, notes, or meetings
- Update task status (complete, pending, etc.)
- Suggest task priorities based on deadlines and importance

**EMAIL & CALENDAR ACCESS:**
- You HAVE FULL ACCESS to the user's emails shown in the context above
- Review email subjects, senders, and snippets provided
- Identify action items and follow-ups from emails
- Suggest responses or actions based on email content
- View calendar events and identify scheduling conflicts
- ALL EMAIL AND CALENDAR DATA IS IN THE CONTEXT - USE IT!

**NOTE & MEETING ANALYSIS:**
- Summarize meeting transcripts and notes
- Extract action items and decisions from notes
- Identify participants, key topics, and follow-up items
- Connect meeting outcomes to existing tasks

**INSTRUCTIONS:**
- Use the specific information provided in the context above
- You have DIRECT ACCESS to emails, calendar, tasks, GitHub, and notes data
- Reference actual task IDs like [task_123] when discussing tasks
- Reference actual email subjects and senders when discussing emails
- Be proactive: suggest priorities, identify conflicts, highlight important items
- When asked about tasks/schedule/emails/github/news, use the actual data provided
- NEVER say "I don't have access" - the data is in your context!

=== TASK OPERATIONS ===

**SEARCHING TASKS:**
When user asks "what tasks do I have about X" or "find tasks related to Y":
1. Look through the task list in the context above
2. Match by keywords in title/description
3. Present results with task IDs, priorities, and due dates
Example: "I found 3 tasks related to 'Buildly':
- [task_001] Review Buildly architecture (High, due Dec 15)
- [task_002] Update Buildly documentation (Medium, due Dec 20)
- [task_003] Demo Buildly to client (High, due Dec 18)"

**CREATING TASKS FROM NOTES:**
When user asks to "extract tasks from my meeting with X" or "create tasks from note Y":
1. Identify all action items in the note/meeting
2. Parse each into: title, description, priority, due date
3. Present as numbered list for approval
4. Ask if user wants to create them

Example workflow:
User: "Extract tasks from my meeting with Crispin"
You: "I found 8 action items in your Dec 3rd meeting with Crispin Courtenay. Here are the tasks:

1. **Schedule follow-up meeting** - Review Buildly's product management workflow and demonstrate AI-enabled MCP/server visualization (High priority, due within 2 weeks - Dec 23)

2. **Prepare demo walkthrough** - Product metrics and commit/process visualization showing AI agents and guardrails integration (Medium priority, due before follow-up meeting - Dec 20)

3. **Send LLM hosting recommendations** - Cost-effective options, multi-agent orchestration, on-prem/GPU-lite approaches (Medium priority, due within 1 week - Dec 16)

4. **Draft AI guardrails workflow** - Template for developer + AI guardrails with coding agents, documentation agents, MCP coordination (High priority, due within 3 weeks - Dec 30)

5. **Experiment with Google Code Wiki** - Test on small repo and report findings on multi-repo coverage and doc quality (Medium priority, due before follow-up - Dec 20)

6. **Read multi-agent white papers** - Anthropic/Google papers, summarize architectural patterns for safe multi-agent integration (Medium priority, due within 2 weeks - Dec 23)

7. **Prepare authentication module description** - Document ephemeral-token design, integration points, security assumptions (Medium priority, ASAP - Dec 12)

8. **Assess Q1 hiring plan** - Options: freelancers, direct hires, or independent developer network (High priority, due before follow-up - Dec 20)

Would you like me to create all 8 tasks? (Type 'yes' to create them all, or specify which ones you want)"

**BATCH TASK CREATION FORMAT:**
When creating multiple tasks, use this JSON structure internally:
{{
  "approved": true,
  "sync_to_ticktick": false,
  "tasks": [
    {{
      "title": "Clear, actionable title",
      "description": "Full context and details",
      "priority": "high|medium|low",
      "due_date": "YYYY-MM-DD"
    }}
  ]
}}

**SUMMARIZING MEETINGS:**
When user asks to "summarize my meeting with X":
1. Identify the note/transcript
2. Extract: participants, date, main topics, decisions, action items, next steps
3. Present in clear sections

Example:
"**Meeting Summary: Crispin Courtenay - Dec 3, 2025**

**Participants:** Greg Lind (CEO, Buildly), Crispin Courtenay

**Main Topics:**
- Product management workflow and AI-enabled visualization
- MCP server integration and multi-agent orchestration
- Cost-effective LLM hosting options
- Developer workflow with AI guardrails

**Key Decisions:**
- Will schedule follow-up meeting within 2 weeks
- Focus on demonstrating product metrics and commit visualization
- Explore Canadian LLM providers for cost savings

**Action Items:** (8 total - see above for full list)

**Next Steps:**
- Greg to send follow-up meeting invite
- Prepare demo walkthrough before meeting
- Research and share LLM hosting recommendations"

=== IMPORTANT RULES ===

✅ DO:
- Search context data before saying "no tasks found"
- Extract specific due dates from phrases like "within 2 weeks", "before meeting", "ASAP"
- Calculate actual dates (today is {datetime.now().strftime('%B %d, %Y')})
- Present tasks with clear titles, priorities, and due dates
- Ask for confirmation before creating tasks

❌ DON'T:
- Create tasks without user approval
- Guess or make up task information
- Sync to TickTick directly (explain user needs to use sync button)
- Ignore existing tasks when user asks to create similar ones

When user approves task creation, call the batch creation endpoint and report success."""
                messages.append({'role': 'system', 'content': system_message})
            
            # Add conversation history if available
            if conversation_id:
                history = self.db.get_ai_conversation_history(conversation_id, limit=5)
                for msg in history:
                    if msg['role'] != 'system':  # Avoid duplicate system messages
                        messages.append({
                            'role': msg['role'],
                            'content': msg['content']
                        })
            
            # Add current message
            messages.append({'role': 'user', 'content': message})
            
            # Get AI response
            response = await provider.chat(messages, stream=False)
            
            # Save to conversation history
            if conversation_id:
                user_msg_id = f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_user"
                ai_msg_id = f"msg_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}_ai"
                
                self.db.save_ai_message(user_msg_id, conversation_id, 'user', message)
                self.db.save_ai_message(ai_msg_id, conversation_id, 'assistant', response)
            
            return {
                'success': True,
                'response': response,
                'provider': provider.name,
                'conversation_id': conversation_id,
                'context_included': include_context,
                'context_hash': self.get_context_hash(context) if context else None
            }
            
        except Exception as e:
            logger.error(f"Error in AI chat: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def learn_from_feedback(self, item_type: str, item_id: str, feedback: str, item_data: Dict[str, Any] = None):
        """
        Learn from user feedback to improve future suggestions.
        
        Args:
            item_type: Type of item (news, task, email, etc.)
            item_id: ID of the item
            feedback: 'like' or 'dislike'
            item_data: Additional data about the item
        """
        try:
            # Save feedback to database (already handled elsewhere)
            # Here we could do additional learning/analysis
            
            # Invalidate caches to pick up new preferences
            self._user_profile_cache = None
            self._profile_cache_time = None
            self._context_cache = None
            self._context_cache_time = None
            
            logger.info(f"Learned from {feedback} on {item_type}: {item_id}")
            
        except Exception as e:
            logger.error(f"Error learning from feedback: {e}")
    
    def anticipate_needs(self) -> List[Dict[str, Any]]:
        """
        Anticipate user needs based on patterns and context.
        Returns suggested actions/reminders.
        """
        suggestions = []
        
        try:
            profile = self.build_user_profile()
            now = datetime.now()
            
            # Check for overdue tasks
            todos = self.db.get_todos(include_completed=False, include_deleted=False)
            overdue = [t for t in todos if t.get('due_date') and 
                      datetime.fromisoformat(t['due_date'].replace('Z', '+00:00')) < now]
            
            if overdue:
                suggestions.append({
                    'type': 'overdue_tasks',
                    'priority': 'high',
                    'message': f"You have {len(overdue)} overdue tasks",
                    'action': 'review_tasks',
                    'items': [t['title'] for t in overdue[:3]]
                })
            
            # Check for tasks due soon
            soon = [t for t in todos if t.get('due_date') and 
                   datetime.fromisoformat(t['due_date'].replace('Z', '+00:00')) < now + timedelta(hours=24)]
            
            if soon:
                suggestions.append({
                    'type': 'upcoming_tasks',
                    'priority': 'medium',
                    'message': f"{len(soon)} tasks due in the next 24 hours",
                    'action': 'prepare_tasks',
                    'items': [t['title'] for t in soon[:3]]
                })
            
            # More anticipation logic can be added here
            # - Meeting prep suggestions
            # - Follow-up reminders based on emails
            # - Pattern-based suggestions
            
        except Exception as e:
            logger.error(f"Error anticipating needs: {e}")
        
        return suggestions


# Action methods for AI to interact with dashboard
    def create_task(self, title: str, description: str = "", priority: str = "medium", due_date: str = None, category: str = "ai-suggested", sync_to_ticktick: bool = False) -> Dict[str, Any]:
        """
        Create a new task (to be called by AI with user approval).
        
        Args:
            title: Task title
            description: Task description
            priority: Task priority (low, medium, high)
            due_date: Due date (ISO format string)
            category: Task category
            sync_to_ticktick: Whether to sync to TickTick immediately
        
        Returns dict with task_id and success status.
        """
        try:
            task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            
            # Prepare todo data dictionary (save_todo expects a dict)
            todo_data = {
                'id': task_id,
                'title': title,
                'description': description,
                'priority': priority,
                'due_date': due_date,
                'source': 'ai-assistant',
                'category': category,
                'status': 'pending'
            }
            
            success = self.db.save_todo(todo_data)
            
            if success:
                logger.info(f"AI created task: {title}")
                return {
                    'success': True,
                    'task_id': task_id,
                    'title': title,
                    'message': f'Task "{title}" created successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to create task'
                }
                
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def complete_task(self, task_id: str) -> Dict[str, Any]:
        """Mark a task as completed."""
        try:
            success = self.db.update_todo_status(task_id, 'completed')
            
            if success:
                logger.info(f"AI completed task: {task_id}")
                return {
                    'success': True,
                    'task_id': task_id,
                    'message': 'Task marked as completed'
                }
            else:
                return {
                    'success': False,
                    'error': 'Task not found or already completed'
                }
                
        except Exception as e:
            logger.error(f"Error completing task: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_task(self, task_id: str) -> Dict[str, Any]:
        """Delete a task."""
        try:
            success = self.db.delete_todo(task_id)
            
            if success:
                logger.info(f"AI deleted task: {task_id}")
                return {
                    'success': True,
                    'task_id': task_id,
                    'message': 'Task deleted successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'Task not found'
                }
                
        except Exception as e:
            logger.error(f"Error deleting task: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def create_tasks_batch(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Create multiple tasks at once (for AI batch operations).
        
        Args:
            tasks: List of task dictionaries with title, description, priority, due_date
        
        Returns dict with created tasks count and IDs.
        """
        try:
            created_tasks = []
            failed_tasks = []
            
            for i, task_data in enumerate(tasks, 1):
                # Add microsecond-level unique ID
                task_id = f"task_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i:03d}"
                
                # Prepare todo data dictionary
                todo_dict = {
                    'id': task_id,
                    'title': task_data.get('title', ''),
                    'description': task_data.get('description', ''),
                    'priority': task_data.get('priority', 'medium'),
                    'due_date': task_data.get('due_date'),
                    'source': 'ai-assistant',
                    'category': task_data.get('category', 'ai-suggested'),
                    'status': 'pending'
                }
                
                success = self.db.save_todo(todo_dict)
                
                if success:
                    created_tasks.append({
                        'task_id': task_id,
                        'title': task_data.get('title', '')
                    })
                    logger.info(f"AI created task ({i}/{len(tasks)}): {task_data.get('title', '')}")
                else:
                    failed_tasks.append({
                        'title': task_data.get('title', ''),
                        'error': 'Failed to save to database'
                    })
            
            return {
                'success': True,
                'created_count': len(created_tasks),
                'failed_count': len(failed_tasks),
                'created_tasks': created_tasks,
                'failed_tasks': failed_tasks,
                'message': f'Created {len(created_tasks)} of {len(tasks)} tasks'
            }
            
        except Exception as e:
            logger.error(f"Error creating tasks batch: {e}")
            return {
                'success': False,
                'error': str(e),
                'created_count': 0
            }
    
    def search_tasks(self, query: str, status: str = None, priority: str = None) -> List[Dict[str, Any]]:
        """
        Search tasks by keywords, status, and priority.
        
        Args:
            query: Search keywords (searches title and description)
            status: Filter by status (pending, completed, etc.)
            priority: Filter by priority (low, medium, high)
        
        Returns:
            List of matching tasks
        """
        try:
            # Get all tasks
            all_tasks = self.db.get_todos(include_completed=(status == 'completed'))
            
            # Filter by status if specified
            if status:
                all_tasks = [t for t in all_tasks if t.get('status') == status]
            
            # Filter by priority if specified
            if priority:
                all_tasks = [t for t in all_tasks if t.get('priority') == priority]
            
            # Search by query keywords
            if query:
                query_lower = query.lower()
                matching_tasks = []
                for task in all_tasks:
                    title = task.get('title', '').lower()
                    description = task.get('description', '').lower()
                    if query_lower in title or query_lower in description:
                        matching_tasks.append(task)
                return matching_tasks
            
            return all_tasks
            
        except Exception as e:
            logger.error(f"Error searching tasks: {e}")
            return []
    
    def get_note_by_title(self, title_query: str) -> Dict[str, Any]:
        """
        Search for a note by title (from Obsidian or Google Drive).
        
        Args:
            title_query: Search query for note title
        
        Returns:
            Note data if found, None otherwise
        """
        try:
            from collectors.notes_collector import collect_all_notes
            from database import get_credentials
            
            # Get notes configuration
            notes_config = get_credentials('notes') or {}
            obsidian_path = self.db.get_setting('obsidian_vault_path') or notes_config.get('obsidian_vault_path')
            gdrive_folder_id = self.db.get_setting('google_drive_notes_folder_id') or notes_config.get('google_drive_folder_id')
            
            # Collect recent notes
            result = collect_all_notes(
                obsidian_path=obsidian_path,
                gdrive_folder_id=gdrive_folder_id,
                limit=50  # Get more notes for searching
            )
            
            # Search by title
            query_lower = title_query.lower()
            for note in result.get('notes', []):
                if query_lower in note.get('title', '').lower():
                    return note
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting note: {e}")
            return None
    
    def summarize_note(self, note_title: str) -> str:
        """
        Get a detailed summary of a specific note for the AI context.
        
        Args:
            note_title: Title of the note to summarize
        
        Returns:
            Formatted summary string
        """
        try:
            note = self.get_note_by_title(note_title)
            if not note:
                return f"Note '{note_title}' not found"
            
            summary_parts = []
            summary_parts.append(f"=== NOTE: {note['title']} ===")
            summary_parts.append(f"Source: {note['source']}")
            summary_parts.append(f"Modified: {note.get('modified_at', 'Unknown')}")
            
            if note.get('preview'):
                summary_parts.append(f"\nPreview:\n{note['preview'][:500]}")
            
            if note.get('todos'):
                summary_parts.append(f"\nAction Items Found: {len(note['todos'])}")
                for i, todo in enumerate(note['todos'][:10], 1):
                    summary_parts.append(f"  {i}. {todo['text']}")
            
            return "\n".join(summary_parts)
            
        except Exception as e:
            logger.error(f"Error summarizing note: {e}")
            return f"Error summarizing note: {str(e)}"


# Global singleton instance
_ai_service_instance = None


def get_ai_service(db, settings=None):
    """Get or create the global AI service instance."""
    global _ai_service_instance
    
    if _ai_service_instance is None:
        _ai_service_instance = AIService(db, settings)
    
    return _ai_service_instance
