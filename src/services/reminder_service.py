"""
Reminder Service - Scans tasks, emails, and calendar for incomplete items
Runs every 15 minutes to identify high-priority reminders and notify the user
"""

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from pathlib import Path
import sys

logger = logging.getLogger(__name__)

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from database import DatabaseManager


class ReminderService:
    """Service to identify and track pending reminders."""
    
    def __init__(self, db: DatabaseManager = None):
        """Initialize the reminder service."""
        self.db = db or DatabaseManager()
        self.high_priority_keywords = [
            'urgent', 'asap', 'critical', 'deadline', 'important',
            'high priority', 'action required', 'needs response', 'review',
            'approve', 'sign', 'confirm', 'overdue'
        ]
        self.meeting_keywords = [
            'meeting', 'call', 'standup', 'sync', 'discussion',
            'review', 'presentation', 'workshop', 'conference'
        ]
    
    def scan_incomplete_tasks(self) -> List[Dict[str, Any]]:
        """Get all incomplete tasks that haven't been recently reminded."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get incomplete tasks
                cursor.execute("""
                    SELECT
                        id,
                        title,
                        description,
                        priority,
                        due_date,
                        source,
                        created_at,
                        CASE
                            WHEN priority = 'high' THEN 1
                            WHEN priority = 'medium' THEN 2
                            WHEN priority = 'low' THEN 3
                            ELSE 4
                        END as priority_level
                    FROM universal_todos
                    WHERE
                        status NOT IN ('completed', 'archived', 'cancelled')
                        AND (last_reminded_at IS NULL OR datetime(last_reminded_at) < datetime('now', '-15 minutes'))
                    ORDER BY priority_level, due_date ASC, created_at DESC
                    LIMIT 50
                """)
                
                tasks = []
                for row in cursor.fetchall():
                    task = {
                        'id': row[0],
                        'title': row[1],
                        'description': row[2],
                        'priority': row[3],
                        'due_date': row[4],
                        'source': row[5],
                        'type': 'task',
                        'reason': self._get_task_reason(row[1], row[3], row[4]),
                        'icon': self._get_priority_icon(row[3]),
                        'priority_score': row[7],
                        'is_overdue': self._is_overdue(row[4])
                    }
                    tasks.append(task)
                
                logger.info(f"Found {len(tasks)} incomplete tasks for reminders")
                return tasks
                
        except Exception as e:
            logger.error(f"Error scanning incomplete tasks: {e}")
            return []
    
    def scan_emails_for_action_items(self) -> List[Dict[str, Any]]:
        """Scan emails for action items that need responses or follow-ups."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get high-priority or unanswered emails
                cursor.execute("""
                    SELECT
                        id,
                        subject,
                        sender,
                        received_date,
                        priority,
                        (CASE
                            WHEN subject LIKE '%urgent%' OR subject LIKE '%important%' THEN 1
                            WHEN priority = 'high' THEN 2
                            WHEN ollama_priority = 'high' THEN 2
                            WHEN priority = 'medium' THEN 3
                            ELSE 4
                        END) as priority_level
                    FROM emails
                    WHERE
                        (is_analyzed = 0 OR has_todos = 1)
                        AND (priority = 'high' OR ollama_priority = 'high' OR subject LIKE '%urgent%' OR subject LIKE '%important%')
                        AND (last_reminded_at IS NULL OR datetime(last_reminded_at) < datetime('now', '-15 minutes'))
                    ORDER BY priority_level, received_date DESC
                    LIMIT 20
                """)
                
                emails = []
                for row in cursor.fetchall():
                    email = {
                        'id': row[0],
                        'title': row[1][:80],  # Truncate long subjects
                        'description': f"From: {row[2]}",
                        'priority': row[4],
                        'type': 'email',
                        'reason': f"Action required: {row[1]}",
                        'icon': '📧',
                        'priority_score': row[5],
                        'is_overdue': False
                    }
                    emails.append(email)
                
                logger.info(f"Found {len(emails)} action items in emails")
                return emails
                
        except Exception as e:
            logger.error(f"Error scanning emails for action items: {e}")
            return []
    
    def scan_calendar_for_meetings(self) -> List[Dict[str, Any]]:
        """Scan calendar for upcoming meetings and action items from meeting notes."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get upcoming meetings (next 24 hours) and meeting notes with action items
                cursor.execute("""
                    SELECT
                        id,
                        title,
                        description,
                        start_time,
                        end_time,
                        (CASE
                            WHEN datetime(start_time) < datetime('now', '+1 hour') THEN 1
                            WHEN datetime(start_time) < datetime('now', '+1 day') THEN 2
                            ELSE 3
                        END) as priority_level
                    FROM calendar_events
                    WHERE
                        deletion_status IS NULL
                        AND start_time > datetime('now')
                        AND start_time < datetime('now', '+1 day')
                        AND (last_reminded_at IS NULL OR datetime(last_reminded_at) < datetime('now', '-15 minutes'))
                    ORDER BY priority_level, start_time ASC
                    LIMIT 20
                """)
                
                meetings = []
                for row in cursor.fetchall():
                    meeting = {
                        'id': row[0],
                        'title': row[1],
                        'description': row[2] or f"Upcoming meeting: {row[1]}",
                        'type': 'meeting',
                        'due_date': row[3],
                        'reason': self._get_meeting_reminder_reason(row[1], row[3]),
                        'icon': '📅',
                        'priority_score': row[5],
                        'is_overdue': False
                    }
                    meetings.append(meeting)
                
                logger.info(f"Found {len(meetings)} upcoming meetings")
                return meetings
                
        except Exception as e:
            logger.error(f"Error scanning calendar for meetings: {e}")
            return []
    
    def scan_notes_for_action_items(self) -> List[Dict[str, Any]]:
        """Scan meeting notes for action items and follow-ups."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Look for recently created or updated notes with action items
                cursor.execute("""
                    SELECT
                        id,
                        title,
                        content,
                        created_at,
                        updated_at,
                        (CASE
                            WHEN content LIKE '%action%' OR content LIKE '%TODO%' THEN 1
                            WHEN content LIKE '%follow%' OR content LIKE '%next step%' THEN 2
                            ELSE 3
                        END) as priority_level
                    FROM notes
                    WHERE
                        (content LIKE '%action%' OR content LIKE '%TODO%' OR content LIKE '%follow%' OR content LIKE '%next step%')
                        AND updated_at > datetime('now', '-24 hours')
                        AND (last_reminded_at IS NULL OR datetime(last_reminded_at) < datetime('now', '-15 minutes'))
                    ORDER BY priority_level, updated_at DESC
                    LIMIT 15
                """)
                
                notes = []
                for row in cursor.fetchall():
                    # Extract action items from content
                    actions = self._extract_action_items(row[2] or '')
                    if actions:
                        note = {
                            'id': row[0],
                            'title': row[1],
                            'description': f"Actions in notes: {actions[0]}",
                            'type': 'note',
                            'due_date': row[4],
                            'reason': f"Follow-up needed: {row[1]}",
                            'icon': '📝',
                            'priority_score': row[5],
                            'is_overdue': False
                        }
                        notes.append(note)
                
                logger.info(f"Found {len(notes)} action items in notes")
                return notes
                
        except Exception as e:
            logger.error(f"Error scanning notes for action items: {e}")
            return []
    
    def get_all_pending_reminders(self) -> Dict[str, Any]:
        """Get all pending reminders across all sources."""
        reminders = {
            'tasks': self.scan_incomplete_tasks(),
            'emails': self.scan_emails_for_action_items(),
            'meetings': self.scan_calendar_for_meetings(),
            'notes': self.scan_notes_for_action_items(),
            'total': 0,
            'high_priority_count': 0,
            'scan_timestamp': datetime.now().isoformat()
        }
        
        all_reminders = reminders['tasks'] + reminders['emails'] + reminders['meetings'] + reminders['notes']
        reminders['total'] = len(all_reminders)
        reminders['high_priority_count'] = len([r for r in all_reminders if r.get('priority_score', 5) <= 2])
        
        return reminders
    
    def mark_reminded(self, reminder_type: str, reminder_id: str) -> bool:
        """Mark a reminder as having been shown to the user."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                table_map = {
                    'task': 'universal_todos',
                    'email': 'emails',
                    'meeting': 'calendar_events',
                    'note': 'notes'
                }
                
                table = table_map.get(reminder_type)
                if not table:
                    logger.warning(f"Unknown reminder type: {reminder_type}")
                    return False
                
                cursor.execute(f"""
                    UPDATE {table}
                    SET last_reminded_at = ?
                    WHERE id = ?
                """, (datetime.now().isoformat(), reminder_id))
                
                conn.commit()
                logger.info(f"Marked {reminder_type} {reminder_id} as reminded")
                return True
                
        except Exception as e:
            logger.error(f"Error marking reminder as shown: {e}")
            return False
    
    # Helper methods
    
    def _get_task_reason(self, title: str, priority: str, due_date: Optional[str]) -> str:
        """Generate a friendly reminder reason for a task."""
        if due_date:
            due_dt = datetime.fromisoformat(due_date.replace('Z', '+00:00')) if 'Z' in str(due_date) else datetime.fromisoformat(str(due_date))
            days_until = (due_dt.date() - datetime.now().date()).days
            if days_until < 0:
                return f"⚠️ Overdue: {title}"
            elif days_until == 0:
                return f"📌 Due today: {title}"
            elif days_until == 1:
                return f"📌 Due tomorrow: {title}"
            else:
                return f"📌 Due in {days_until} days: {title}"
        return f"📌 Pending: {title}"
    
    def _get_priority_icon(self, priority: str) -> str:
        """Get emoji icon for task priority."""
        if priority == 'high':
            return '🔴'
        elif priority == 'medium':
            return '🟡'
        elif priority == 'low':
            return '🟢'
        else:
            return '⚪'
    
    def _is_overdue(self, due_date: Optional[str]) -> bool:
        """Check if a task is overdue."""
        if not due_date:
            return False
        try:
            due_dt = datetime.fromisoformat(due_date.replace('Z', '+00:00')) if 'Z' in str(due_date) else datetime.fromisoformat(str(due_date))
            return due_dt < datetime.now()
        except Exception:
            return False
    
    def _get_meeting_reminder_reason(self, title: str, start_time: str) -> str:
        """Generate a friendly reminder reason for a meeting."""
        try:
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00')) if 'Z' in str(start_time) else datetime.fromisoformat(str(start_time))
            minutes_until = int((start_dt - datetime.now()).total_seconds() / 60)
            if minutes_until < 0:
                return f"🚨 Meeting in progress: {title}"
            elif minutes_until < 15:
                return f"🚨 Meeting starting soon: {title}"
            elif minutes_until < 60:
                return f"⏰ Meeting in {minutes_until} minutes: {title}"
            else:
                hours_until = minutes_until // 60
                return f"⏰ Meeting in {hours_until} hour(s): {title}"
        except Exception:
            return f"📅 Upcoming meeting: {title}"
    
    def _extract_action_items(self, content: str) -> List[str]:
        """Extract action items from text content."""
        actions = []
        lines = content.split('\n')
        for line in lines:
            if any(keyword in line.lower() for keyword in ['action', 'todo', 'follow', 'next step']):
                actions.append(line.strip()[:100])
        return actions[:3]  # Return max 3 actions


# Global reminder service instance
_reminder_service = None

def get_reminder_service(db: DatabaseManager = None) -> ReminderService:
    """Get or create the global reminder service instance."""
    global _reminder_service
    if _reminder_service is None:
        _reminder_service = ReminderService(db)
    return _reminder_service
