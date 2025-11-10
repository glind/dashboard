#!/usr/bin/env python3
"""
Enhanced Task Generator
======================
Extracts and creates tasks from notes, calendar events, and emails with proper linking.
"""

import re
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class TaskGenerator:
    """Enhanced task generation with cross-source linking."""
    
    def __init__(self, db_manager):
        """Initialize with database manager."""
        self.db = db_manager
    
    def extract_tasks_from_notes(self, notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract tasks from note content with enhanced patterns."""
        tasks = []
        
        for note in notes:
            note_tasks = self._extract_todos_from_text(
                content=note.get('preview', '') or '',
                source=note['source'],
                source_title=note['title'],
                source_url=note.get('url') or note.get('path'),
                source_id=note.get('doc_id') or note.get('relative_path')
            )
            tasks.extend(note_tasks)
        
        return tasks
    
    def extract_tasks_from_calendar_events(self, events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract tasks from calendar events (action items, follow-ups)."""
        tasks = []
        
        for event in events:
            # Extract from event description/summary
            description = event.get('description', '') or event.get('summary', '')
            
            if description:
                event_tasks = self._extract_todos_from_text(
                    content=description,
                    source='calendar',
                    source_title=f"Meeting: {event.get('summary', 'Untitled')}",
                    source_url=event.get('htmlLink'),
                    source_id=event.get('id'),
                    due_context=event.get('start', {}).get('dateTime')
                )
                tasks.extend(event_tasks)
            
            # Extract tasks based on meeting patterns
            meeting_tasks = self._extract_meeting_follow_ups(event)
            tasks.extend(meeting_tasks)
        
        return tasks
    
    def extract_tasks_from_emails(self, emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract tasks from email content."""
        tasks = []
        
        for email in emails:
            # Extract from email body
            body = email.get('body', '') or email.get('snippet', '')
            
            if body:
                email_tasks = self._extract_todos_from_text(
                    content=body,
                    source='email',
                    source_title=f"Email: {email.get('subject', 'No Subject')}",
                    source_url=f"https://mail.google.com/mail/u/0/#inbox/{email.get('id')}",
                    source_id=email.get('id')
                )
                tasks.extend(email_tasks)
        
        return tasks
    
    def _extract_todos_from_text(self, content: str, source: str, source_title: str,
                                 source_url: Optional[str] = None, source_id: Optional[str] = None,
                                 due_context: Optional[str] = None) -> List[Dict[str, Any]]:
        """Enhanced TODO extraction with multiple patterns."""
        tasks = []
        
        # Enhanced patterns for task detection
        patterns = [
            # Checkbox patterns
            (r'- \[ \]\s+(.+)', 'checkbox'),
            (r'☐\s+(.+)', 'checkbox'),
            
            # Action patterns
            (r'(?i)(?:^|\n)\s*(?:TODO|To-?Do):\s*(.+)', 'todo'),
            (r'(?i)(?:^|\n)\s*Action\s*(?:Item)?:\s*(.+)', 'action'),
            (r'(?i)(?:^|\n)\s*Next\s*Step:\s*(.+)', 'next_step'),
            (r'(?i)(?:^|\n)\s*Follow\s*up:\s*(.+)', 'follow_up'),
            
            # Assignment patterns
            (r'(?i)@(\w+):\s*(.+)', 'assignment'),
            (r'(?i)assigned\s+to\s+(\w+):\s*(.+)', 'assignment'),
            
            # Deadline patterns with date context
            (r'(?i)due\s+(.+?):\s*(.+)', 'due_task'),
            (r'(?i)deadline\s+(.+?):\s*(.+)', 'deadline_task'),
            (r'(?i)by\s+(\w+day|\d{1,2}/\d{1,2}|\w+\s+\d{1,2}):\s*(.+)', 'dated_task'),
        ]
        
        for pattern, task_type in patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            
            for match in matches:
                try:
                    # Extract task text and metadata
                    if task_type == 'assignment':
                        assignee = match.group(1)
                        task_text = match.group(2).strip()
                        priority = 'high' if assignee.lower() in ['me', 'myself'] else 'medium'
                    elif task_type in ['due_task', 'deadline_task', 'dated_task']:
                        date_part = match.group(1)
                        task_text = match.group(2).strip()
                        priority = 'high'
                        # TODO: Parse date_part for actual due date
                    else:
                        task_text = match.group(1).strip()
                        priority = self._determine_priority(task_text, task_type)
                    
                    # Skip very short or generic tasks
                    if len(task_text) < 5 or task_text.lower() in ['test', 'todo', 'action']:
                        continue
                    
                    # Get context around the match
                    context_start = max(0, match.start() - 150)
                    context_end = min(len(content), match.end() + 150)
                    context = content[context_start:context_end].strip()
                    
                    # Create task
                    task = {
                        'id': str(uuid.uuid4()),
                        'title': task_text,
                        'description': f"From {source}: {source_title}\\n\\nContext: {context}",
                        'source': source,
                        'source_id': source_id,
                        'source_url': source_url,
                        'priority': priority,
                        'status': 'pending',
                        'category': self._categorize_task(task_text, source),
                        'pattern_type': task_type,
                        'raw_context': context
                    }
                    
                    # Add due date context if available
                    if due_context:
                        try:
                            # Parse due date from calendar event or other source
                            if isinstance(due_context, str):
                                # Parse ISO datetime
                                due_date = datetime.fromisoformat(due_context.replace('Z', '+00:00'))
                                task['due_date'] = due_date.isoformat()
                        except Exception:
                            pass
                    
                    tasks.append(task)
                    
                except Exception as e:
                    logger.warning(f"Error extracting task from pattern {task_type}: {e}")
                    continue
        
        return tasks
    
    def _extract_meeting_follow_ups(self, event: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract follow-up tasks from meeting patterns."""
        tasks = []
        
        summary = event.get('summary', '').lower()
        
        # Patterns that suggest follow-up tasks needed
        follow_up_patterns = [
            'review', 'follow up', 'follow-up', 'check in', 'status update',
            'decision', 'approval', 'sign-off', 'demo', 'presentation',
            'planning', 'strategy', 'retrospective', 'post-mortem'
        ]
        
        if any(pattern in summary for pattern in follow_up_patterns):
            # Create a general follow-up task
            task_id = str(uuid.uuid4())
            
            # Determine due date (usually a few days after the meeting)
            meeting_time = event.get('start', {}).get('dateTime')
            due_date = None
            
            if meeting_time:
                try:
                    meeting_dt = datetime.fromisoformat(meeting_time.replace('Z', '+00:00'))
                    # Follow up 2-3 days after meeting
                    due_date = (meeting_dt + timedelta(days=2)).isoformat()
                except Exception:
                    pass
            
            task = {
                'id': task_id,
                'title': f"Follow up on: {event.get('summary', 'Meeting')}",
                'description': f"Follow-up actions from meeting: {event.get('summary', 'Untitled')}\\n\\nMeeting time: {meeting_time}\\n\\nDescription: {event.get('description', 'No description')}",
                'source': 'calendar',
                'source_id': event.get('id'),
                'source_url': event.get('htmlLink'),
                'priority': 'medium',
                'status': 'pending',
                'category': 'meeting_follow_up',
                'due_date': due_date
            }
            
            tasks.append(task)
        
        return tasks
    
    def _determine_priority(self, task_text: str, task_type: str) -> str:
        """Determine task priority based on text and type."""
        text_lower = task_text.lower()
        
        # High priority indicators
        high_indicators = ['urgent', 'asap', 'immediately', 'critical', 'important', '!']
        if any(indicator in text_lower for indicator in high_indicators):
            return 'high'
        
        # Low priority indicators
        low_indicators = ['maybe', 'consider', 'eventually', 'nice to have']
        if any(indicator in text_lower for indicator in low_indicators):
            return 'low'
        
        # Task type based priority
        if task_type in ['follow_up', 'action', 'due_task']:
            return 'high'
        elif task_type == 'checkbox':
            return 'medium'
        
        return 'medium'
    
    def _categorize_task(self, task_text: str, source: str) -> str:
        """Categorize task based on content and source."""
        text_lower = task_text.lower()
        
        # Technical categories
        if any(word in text_lower for word in ['code', 'bug', 'fix', 'deploy', 'test', 'review']):
            return 'technical'
        
        # Communication categories
        if any(word in text_lower for word in ['email', 'call', 'meeting', 'discuss', 'contact']):
            return 'communication'
        
        # Administrative categories
        if any(word in text_lower for word in ['schedule', 'book', 'order', 'purchase', 'paperwork']):
            return 'administrative'
        
        # Research categories
        if any(word in text_lower for word in ['research', 'investigate', 'analyze', 'study']):
            return 'research'
        
        # Source-based categorization
        if source == 'calendar':
            return 'meeting_related'
        elif source == 'email':
            return 'email_related'
        elif source in ['obsidian', 'google_drive']:
            return 'notes_related'
        
        return 'general'
    
    def create_tasks_if_not_exist(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create tasks in database if they don't already exist."""
        created_count = 0
        updated_count = 0
        skipped_count = 0
        
        existing_tasks = self.db.get_todos()
        
        for task in tasks:
            try:
                # Check for duplicates based on title and source
                is_duplicate = False
                
                for existing in existing_tasks:
                    # Similar title from same source
                    if (existing.get('title', '').lower().strip() == task['title'].lower().strip() and
                        existing.get('source') == task['source']):
                        is_duplicate = True
                        break
                    
                    # Same source_id (exact match)
                    if (task.get('source_id') and existing.get('source_id') and
                        task['source_id'] == existing.get('source_id')):
                        is_duplicate = True
                        break
                
                if is_duplicate:
                    skipped_count += 1
                    continue
                
                # Create the task
                self.db.add_todo(task)
                created_count += 1
                logger.info(f"Created task from {task['source']}: {task['title'][:50]}...")
                
            except Exception as e:
                logger.error(f"Error creating task: {e}")
                continue
        
        return {
            'created': created_count,
            'updated': updated_count,
            'skipped': skipped_count,
            'total_processed': len(tasks)
        }


def generate_tasks_from_all_sources(db_manager, notes_data=None, calendar_data=None, email_data=None) -> Dict[str, Any]:
    """Generate tasks from all available sources."""
    generator = TaskGenerator(db_manager)
    all_tasks = []
    
    # Extract from notes
    if notes_data:
        notes_tasks = generator.extract_tasks_from_notes(notes_data.get('notes', []))
        all_tasks.extend(notes_tasks)
    
    # Extract from calendar events
    if calendar_data:
        calendar_tasks = generator.extract_tasks_from_calendar_events(calendar_data.get('events', []))
        all_tasks.extend(calendar_tasks)
    
    # Extract from emails
    if email_data:
        email_tasks = generator.extract_tasks_from_emails(email_data.get('emails', []))
        all_tasks.extend(email_tasks)
    
    # Create tasks in database
    result = generator.create_tasks_if_not_exist(all_tasks)
    
    return {
        'tasks_found': len(all_tasks),
        'by_source': {
            'notes': len([t for t in all_tasks if t['source'] in ['obsidian', 'google_drive']]),
            'calendar': len([t for t in all_tasks if t['source'] == 'calendar']),
            'email': len([t for t in all_tasks if t['source'] == 'email'])
        },
        'creation_result': result,
        'sample_tasks': all_tasks[:5]  # First 5 for preview
    }