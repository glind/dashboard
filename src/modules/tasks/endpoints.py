"""
Task Collection API Endpoints
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from datetime import datetime, timedelta

from collectors.gmail_collector import GmailCollector
from collectors.calendar_collector import CalendarCollector
from collectors.notes_collector import collect_all_notes
from database import DatabaseManager, get_credentials
from processors.task_generator import TaskGenerator, generate_tasks_from_all_sources
from config.settings import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

# Initialize database and settings
db = DatabaseManager()
app_settings = Settings()


@router.post("/collect")
async def collect_tasks(
    days_back: int = Query(default=30, ge=1, le=90),
    sources: str = Query(default="email,calendar,notes", description="Comma-separated: email,calendar,notes")
):
    """
    Collect tasks from emails, calendar, and notes.
    
    Searches through your communications for actionable tasks like:
    - TODO items in notes
    - Action items from meeting notes
    - Follow-ups from emails
    - Calendar event tasks
    """
    try:
        start_time = datetime.now()
        source_list = [s.strip().lower() for s in sources.split(',')]
        
        results = {
            'started_at': start_time.isoformat(),
            'sources_requested': source_list,
            'sources_processed': [],
            'tasks_found': 0,
            'tasks_created': 0,
            'tasks_updated': 0,
            'tasks_skipped': 0,
            'by_source': {},
            'errors': []
        }
        
        # Collect data from sources
        notes_data = None
        calendar_data = None
        email_data = None
        
        # Collect from notes
        if 'notes' in source_list:
            try:
                logger.info("Collecting tasks from notes...")
                notes_config = get_credentials('notes') or {}
                
                import os
                obsidian_path = (
                    os.getenv('OBSIDIAN_VAULT_PATH') or
                    db.get_setting('obsidian_vault_path') or
                    notes_config.get('obsidian_vault_path')
                )
                
                gdrive_folder_id = (
                    os.getenv('GOOGLE_DRIVE_NOTES_FOLDER_ID') or
                    db.get_setting('google_drive_notes_folder_id') or
                    notes_config.get('google_drive_folder_id')
                )
                
                notes_result = collect_all_notes(
                    obsidian_path=obsidian_path,
                    gdrive_folder_id=gdrive_folder_id,
                    limit=100
                )
                
                notes_data = notes_result
                results['sources_processed'].append('notes')
                results['by_source']['notes'] = {
                    'notes_found': len(notes_result.get('notes', [])),
                    'obsidian': notes_result.get('obsidian_count', 0),
                    'google_drive': notes_result.get('gdrive_count', 0)
                }
                logger.info(f"Found {len(notes_result.get('notes', []))} notes")
                
            except Exception as e:
                logger.error(f"Error collecting from notes: {e}")
                results['errors'].append(f"Notes: {str(e)}")
        
        # Collect from calendar
        if 'calendar' in source_list:
            try:
                logger.info("Collecting tasks from calendar...")
                calendar_collector = CalendarCollector(app_settings)
                
                # Get calendar events from the past days_back
                start_date = datetime.now() - timedelta(days=days_back)
                end_date = datetime.now()
                
                events = await calendar_collector.collect_events(
                    start_date=start_date,
                    end_date=end_date
                )
                
                calendar_data = {'events': events}
                results['sources_processed'].append('calendar')
                results['by_source']['calendar'] = {
                    'events_found': len(events)
                }
                logger.info(f"Found {len(events)} calendar events")
                
            except Exception as e:
                logger.error(f"Error collecting from calendar: {e}")
                results['errors'].append(f"Calendar: {str(e)}")
        
        # Collect from emails
        if 'email' in source_list:
            try:
                logger.info("Collecting tasks from emails...")
                gmail_collector = GmailCollector(app_settings)
                
                # Get recent emails
                start_date = datetime.now() - timedelta(days=days_back)
                end_date = datetime.now()
                
                all_emails = await gmail_collector.collect_emails(
                    start_date=start_date,
                    end_date=end_date
                )
                
                # Filter for action-oriented emails
                action_keywords = [
                    'TODO', 'action item', 'follow up', 'next steps',
                    'please', 'need to', 'should', 'can you'
                ]
                
                emails = []
                for email_item in all_emails:
                    subject = email_item.get('subject', '').lower()
                    body = email_item.get('body', '').lower()
                    
                    # Check if any action keyword is in subject or body
                    if any(keyword.lower() in subject or keyword.lower() in body[:1000] for keyword in action_keywords):
                        emails.append(email_item)
                    
                    if len(emails) >= 50:  # Limit to prevent overload
                        break
                
                email_data = {'emails': emails}
                results['sources_processed'].append('email')
                results['by_source']['email'] = {
                    'emails_found': len(emails)
                }
                logger.info(f"Found {len(emails)} relevant emails")
                
            except Exception as e:
                logger.error(f"Error collecting from emails: {e}")
                results['errors'].append(f"Email: {str(e)}")
        
        # Generate tasks from all collected data
        if notes_data or calendar_data or email_data:
            logger.info("Generating tasks from collected data...")
            
            task_result = generate_tasks_from_all_sources(
                db_manager=db,
                notes_data=notes_data,
                calendar_data=calendar_data,
                email_data=email_data
            )
            
            results['tasks_found'] = task_result['tasks_found']
            results['tasks_created'] = task_result['creation_result']['created']
            results['tasks_updated'] = task_result['creation_result']['updated']
            results['tasks_skipped'] = task_result['creation_result']['skipped']
            
            # Update by_source counts
            for source, count in task_result['by_source'].items():
                if source in results['by_source']:
                    results['by_source'][source]['tasks_extracted'] = count
        
        # Calculate duration
        end_time = datetime.now()
        results['completed_at'] = end_time.isoformat()
        results['duration_seconds'] = (end_time - start_time).total_seconds()
        
        logger.info(f"Task collection complete: {results['tasks_found']} found, " +
                   f"{results['tasks_created']} created, {results['tasks_updated']} updated")
        
        return results
        
    except Exception as e:
        logger.error(f"Error in task collection: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats")
async def get_task_stats():
    """Get task statistics."""
    try:
        todos = db.get_todos()
        
        # Count by status
        by_status = {}
        by_priority = {}
        by_category = {}
        
        for todo in todos:
            status = todo.get('status', 'pending')
            priority = todo.get('priority', 'medium')
            category = todo.get('category', 'other')
            
            by_status[status] = by_status.get(status, 0) + 1
            by_priority[priority] = by_priority.get(priority, 0) + 1
            by_category[category] = by_category.get(category, 0) + 1
        
        return {
            'total': len(todos),
            'by_status': by_status,
            'by_priority': by_priority,
            'by_category': by_category
        }
        
    except Exception as e:
        logger.error(f"Error getting task stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))
