"""
Email-TickTick integration module for syncing email todos and follow-ups.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from collectors.gmail_collector import GmailCollector
from collectors.ticktick_collector import TickTickCollector
from database import DatabaseManager

logger = logging.getLogger(__name__)


class EmailTickTickSync:
    """Handles syncing email todos and follow-ups with TickTick."""
    
    def __init__(self, settings=None):
        """Initialize the sync service."""
        self.settings = settings
        self.gmail_collector = GmailCollector(settings)
        self.ticktick_collector = TickTickCollector(settings)
        self.db_manager = DatabaseManager()
    
    async def analyze_and_sync_six_months(self, create_tasks: bool = False) -> Dict[str, Any]:
        """
        Analyze 6 months of emails for todos and sync with TickTick.
        
        Args:
            create_tasks: If True, actually create tasks in TickTick. If False, just analyze.
        
        Returns:
            Analysis results and sync status
        """
        try:
            logger.info("Starting 6-month email analysis and TickTick sync")
            
            # Get email analysis
            email_analysis = await self.gmail_collector.analyze_six_months_for_todos_and_followups()
            
            # Check TickTick authentication
            ticktick_authenticated = await self.ticktick_collector.is_authenticated()
            
            sync_results = {
                'email_analysis': email_analysis,
                'ticktick_authenticated': ticktick_authenticated,
                'tasks_created': [],
                'tasks_skipped': [],
                'errors': [],
                'summary': {
                    'total_potential_todos': len(email_analysis.get('potential_todos', [])),
                    'total_unreplied_emails': len(email_analysis.get('unreplied_emails', [])),
                    'tasks_created_count': 0,
                    'tasks_skipped_count': 0,
                    'errors_count': 0
                }
            }
            
            if not ticktick_authenticated:
                error_msg = "TickTick not authenticated - cannot create tasks"
                logger.warning(error_msg)
                sync_results['errors'].append(error_msg)
                return sync_results
            
            if not create_tasks:
                logger.info("Analysis only mode - not creating TickTick tasks")
                return sync_results
            
            # Get existing TickTick task titles to avoid duplicates
            existing_task_titles = await self.ticktick_collector.get_existing_task_titles()
            
            # Process potential todos
            for todo_item in email_analysis.get('potential_todos', []):
                try:
                    suggested_title = todo_item.get('suggested_title', '').lower()
                    
                    # Check if similar task already exists
                    if any(suggested_title in existing_title for existing_title in existing_task_titles):
                        skip_reason = f"Similar task already exists in TickTick"
                        sync_results['tasks_skipped'].append({
                            'email_id': todo_item.get('email_id'),
                            'title': todo_item.get('suggested_title'),
                            'reason': skip_reason
                        })
                        sync_results['summary']['tasks_skipped_count'] += 1
                        continue
                    
                    # Determine priority level for TickTick (0=None, 1=Low, 3=Medium, 5=High)
                    priority_map = {'low': 1, 'medium': 3, 'high': 5}
                    ticktick_priority = priority_map.get(todo_item.get('priority', 'medium'), 3)
                    
                    # Calculate due date if available
                    due_date = None
                    if todo_item.get('due_date'):
                        try:
                            due_date = datetime.fromisoformat(todo_item['due_date'].replace('Z', '+00:00'))
                        except:
                            # Default to 1 week from now if parsing fails
                            due_date = datetime.now() + timedelta(days=7)
                    else:
                        # Default to 1 week from now for todos
                        due_date = datetime.now() + timedelta(days=7)
                    
                    # Create comprehensive task content with email details and link
                    email_snippet = todo_item.get('snippet', '')[:500]  # First 500 chars
                    gmail_link = todo_item.get('gmail_link', '')
                    
                    task_content = f"""{todo_item.get('suggested_content', '')}

📧 Email Details:
From: {todo_item.get('sender', 'Unknown')}
Subject: {todo_item.get('subject', 'No subject')}

{email_snippet}

🔗 Open in Gmail: {gmail_link}
"""
                    
                    # Create task in TickTick
                    created_task = await self.ticktick_collector.create_task(
                        title=todo_item.get('suggested_title', ''),
                        content=task_content,
                        due_date=due_date,
                        priority=ticktick_priority,
                        tags=['email-todo', 'dashboard-sync']
                    )
                    
                    if created_task:
                        sync_results['tasks_created'].append({
                            'email_id': todo_item.get('email_id'),
                            'title': todo_item.get('suggested_title'),
                            'ticktick_id': created_task.get('id'),
                            'priority': todo_item.get('priority'),
                            'due_date': due_date.isoformat() if due_date else None
                        })
                        sync_results['summary']['tasks_created_count'] += 1
                        
                        # Add to existing titles to avoid creating duplicates in this session
                        existing_task_titles.add(suggested_title)
                        
                        logger.info(f"Created TickTick task: {todo_item.get('suggested_title')}")
                    else:
                        error_msg = f"Failed to create TickTick task: {todo_item.get('suggested_title')}"
                        sync_results['errors'].append(error_msg)
                        sync_results['summary']['errors_count'] += 1
                        
                except Exception as e:
                    error_msg = f"Error processing todo item {todo_item.get('email_id', '')}: {str(e)}"
                    logger.error(error_msg)
                    sync_results['errors'].append(error_msg)
                    sync_results['summary']['errors_count'] += 1
            
            # Process unreplied emails
            for unreplied_item in email_analysis.get('unreplied_emails', []):
                try:
                    suggested_title = unreplied_item.get('suggested_title', '').lower()
                    
                    # Check if similar task already exists
                    if any(suggested_title in existing_title for existing_title in existing_task_titles):
                        skip_reason = f"Similar reply task already exists in TickTick"
                        sync_results['tasks_skipped'].append({
                            'email_id': unreplied_item.get('email_id'),
                            'title': unreplied_item.get('suggested_title'),
                            'reason': skip_reason
                        })
                        sync_results['summary']['tasks_skipped_count'] += 1
                        continue
                    
                    # Determine priority - higher for older unreplied emails
                    days_since = unreplied_item.get('days_since_received', 0)
                    if days_since > 14:
                        ticktick_priority = 5  # High
                    elif days_since > 7:
                        ticktick_priority = 3  # Medium
                    else:
                        ticktick_priority = 1  # Low
                    
                    # Due date should be soon for unreplied emails
                    due_date = datetime.now() + timedelta(days=2)
                    
                    # Create comprehensive task content with email details and link
                    email_snippet = unreplied_item.get('snippet', '')[:500]  # First 500 chars
                    gmail_link = unreplied_item.get('gmail_link', '')
                    
                    task_content = f"""{unreplied_item.get('suggested_content', '')}

📧 Email Details:
From: {unreplied_item.get('sender', 'Unknown')}
Subject: {unreplied_item.get('subject', 'No subject')}
Days waiting: {unreplied_item.get('days_waiting', 'Unknown')}

{email_snippet}

🔗 Open in Gmail: {gmail_link}
"""
                    
                    # Create task in TickTick
                    created_task = await self.ticktick_collector.create_task(
                        title=unreplied_item.get('suggested_title', ''),
                        content=task_content,
                        due_date=due_date,
                        priority=ticktick_priority,
                        tags=['email-reply', 'dashboard-sync']
                    )
                    
                    if created_task:
                        sync_results['tasks_created'].append({
                            'email_id': unreplied_item.get('email_id'),
                            'title': unreplied_item.get('suggested_title'),
                            'ticktick_id': created_task.get('id'),
                            'type': 'reply',
                            'priority': unreplied_item.get('priority'),
                            'days_since_received': days_since,
                            'due_date': due_date.isoformat()
                        })
                        sync_results['summary']['tasks_created_count'] += 1
                        
                        # Add to existing titles to avoid creating duplicates in this session
                        existing_task_titles.add(suggested_title)
                        
                        logger.info(f"Created TickTick reply task: {unreplied_item.get('suggested_title')}")
                    else:
                        error_msg = f"Failed to create TickTick reply task: {unreplied_item.get('suggested_title')}"
                        sync_results['errors'].append(error_msg)
                        sync_results['summary']['errors_count'] += 1
                        
                except Exception as e:
                    error_msg = f"Error processing unreplied email {unreplied_item.get('email_id', '')}: {str(e)}"
                    logger.error(error_msg)
                    sync_results['errors'].append(error_msg)
                    sync_results['summary']['errors_count'] += 1
            
            logger.info(f"Email-TickTick sync complete: {sync_results['summary']['tasks_created_count']} tasks created, "
                       f"{sync_results['summary']['tasks_skipped_count']} skipped, "
                       f"{sync_results['summary']['errors_count']} errors")
            
            return sync_results
            
        except Exception as e:
            error_msg = f"Error in email-TickTick sync: {str(e)}"
            logger.error(error_msg)
            return {
                'email_analysis': {},
                'ticktick_authenticated': False,
                'tasks_created': [],
                'tasks_skipped': [],
                'errors': [error_msg],
                'summary': {
                    'total_potential_todos': 0,
                    'total_unreplied_emails': 0,
                    'tasks_created_count': 0,
                    'tasks_skipped_count': 0,
                    'errors_count': 1
                }
            }
    
    async def get_email_todo_analysis_only(self) -> Dict[str, Any]:
        """Get email todo analysis without creating TickTick tasks."""
        return await self.analyze_and_sync_six_months(create_tasks=False)
    
    async def sync_email_todos_to_ticktick(self) -> Dict[str, Any]:
        """Analyze emails and create TickTick tasks."""
        return await self.analyze_and_sync_six_months(create_tasks=True)