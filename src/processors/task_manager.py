"""
Task Management System - Central task handling with optional TickTick sync
"""

import logging
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from database import DatabaseManager
from collectors.ticktick_collector import TickTickCollector

logger = logging.getLogger(__name__)


class TaskManager:
    """Central task management system with database storage and optional TickTick sync."""
    
    def __init__(self, settings=None):
        """Initialize the task manager."""
        self.settings = settings
        self.db = DatabaseManager()
        self.ticktick = TickTickCollector(settings)
        
    def create_task(self, title: str, description: str = "", priority: str = "medium",
                   category: str = "general", due_date: datetime = None, 
                   source: str = "manual", source_id: str = None, 
                   email_id: str = None, sync_to_ticktick: bool = True) -> Dict[str, Any]:
        """Create a new task in the database."""
        try:
            # Generate task ID
            task_id = hashlib.md5(f"{title}{datetime.now().isoformat()}".encode()).hexdigest()
            
            # Create task data
            task_data = {
                'id': task_id,
                'title': title,
                'description': description,
                'due_date': due_date.isoformat() if due_date else None,
                'priority': priority,
                'category': category,
                'source': source,
                'source_id': source_id,
                'status': 'pending',
                'requires_response': 1 if 'reply' in category.lower() or 'email' in source.lower() else 0,
                'email_id': email_id
            }
            
            # Save to database
            success = self.db.save_todo(task_data)
            
            if success:
                logger.info(f"Task created successfully: {title}")
                
                # Optionally sync to TickTick (skip for now if sync_to_ticktick is True)
                # Note: TickTick sync needs to be done separately via the async sync endpoint
                if sync_to_ticktick and self.settings:
                    task_data['sync_to_ticktick'] = True
                else:
                    task_data['sync_to_ticktick'] = False
                
                return {
                    'success': True,
                    'task_id': task_id,
                    'task': task_data,
                    'message': 'Task created successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to save task to database'
                }
                
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def get_all_tasks(self, include_completed: bool = False, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """Get all tasks from database."""
        try:
            # Get tasks from database (exclude deleted by default)
            db_tasks = self.db.get_todos(include_completed=include_completed, include_deleted=include_deleted)
            
            # Transform to consistent format
            formatted_tasks = []
            for task in db_tasks:
                formatted_task = {
                    'id': task.get('id', ''),
                    'title': task.get('title', ''),
                    'description': task.get('description', ''),
                    'priority': task.get('priority', 'medium'),
                    'category': task.get('category', 'general'),
                    'status': task.get('status', 'pending'),
                    'source': task.get('source', 'manual'),
                    'source_id': task.get('source_id', ''),
                    'due_date': task.get('due_date', ''),
                    'created_at': task.get('created_at', ''),
                    'completed_at': task.get('completed_at', ''),
                    'requires_response': bool(task.get('requires_response', 0)),
                    'email_id': task.get('email_id', ''),
                    'gmail_link': f"https://mail.google.com/mail/u/0/#inbox/{task.get('email_id')}" if task.get('email_id') else None
                }
                formatted_tasks.append(formatted_task)
            
            return formatted_tasks
            
        except Exception as e:
            logger.error(f"Error getting tasks: {e}")
            return []
    
    def update_task_status(self, task_id: str, status: str) -> Dict[str, Any]:
        """Update task status (pending, in_progress, completed, cancelled)."""
        try:
            success = self.db.update_todo_status(task_id, status)
            
            if success:
                return {
                    'success': True,
                    'message': f'Task status updated to {status}'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to update task status'
                }
                
        except Exception as e:
            logger.error(f"Error updating task status: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    def delete_task(self, task_id: str) -> Dict[str, Any]:
        """Delete a task from the database."""
        try:
            success = self.db.delete_todo(task_id)
            
            if success:
                return {
                    'success': True,
                    'message': 'Task deleted successfully'
                }
            else:
                return {
                    'success': False,
                    'error': 'Failed to delete task'
                }
                
        except Exception as e:
            logger.error(f"Error deleting task: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def sync_with_ticktick(self, direction: str = "both") -> Dict[str, Any]:
        """
        Synchronize tasks with TickTick.
        
        Args:
            direction: "to_ticktick", "from_ticktick", or "both"
        """
        try:
            # Check TickTick authentication
            ticktick_authenticated = await self.ticktick.is_authenticated()
            
            if not ticktick_authenticated:
                return {
                    'success': False,
                    'error': 'TickTick not authenticated',
                    'auth_url': '/auth/ticktick'
                }
            
            sync_results = {
                'success': True,
                'direction': direction,
                'tasks_pushed_to_ticktick': 0,
                'tasks_pulled_from_ticktick': 0,
                'tasks_updated': 0,
                'errors': []
            }
            
            # Push tasks to TickTick
            if direction in ["to_ticktick", "both"]:
                push_result = await self._push_tasks_to_ticktick()
                sync_results.update(push_result)
            
            # Pull tasks from TickTick
            if direction in ["from_ticktick", "both"]:
                pull_result = await self._pull_tasks_from_ticktick()
                sync_results.update(pull_result)
            
            return sync_results
            
        except Exception as e:
            logger.error(f"Error syncing with TickTick: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def _push_tasks_to_ticktick(self) -> Dict[str, Any]:
        """Push database tasks to TickTick."""
        try:
            # Get unsynced tasks from database
            db_tasks = self.get_all_tasks(include_completed=False)
            
            # Get existing TickTick task titles to avoid duplicates
            existing_titles = await self.ticktick.get_existing_task_titles()
            
            pushed_count = 0
            errors = []
            
            for task in db_tasks:
                try:
                    # Skip if already exists in TickTick
                    if task['title'].lower() in existing_titles:
                        continue
                    
                    # Convert priority to TickTick format
                    priority_map = {'low': 1, 'medium': 3, 'high': 5}
                    ticktick_priority = priority_map.get(task['priority'], 3)
                    
                    # Convert due date
                    due_date = None
                    if task['due_date']:
                        try:
                            due_date = datetime.fromisoformat(task['due_date'].replace('Z', '+00:00'))
                        except:
                            pass
                    
                    # Create task in TickTick
                    created_task = await self.ticktick.create_task(
                        title=task['title'],
                        content=task['description'],
                        due_date=due_date,
                        priority=ticktick_priority,
                        tags=['dashboard-sync', task['category']]
                    )
                    
                    if created_task:
                        # Update database with TickTick ID
                        self.db.update_todo_source_id(task['id'], created_task.get('id', ''))
                        pushed_count += 1
                    else:
                        errors.append(f"Failed to create TickTick task: {task['title']}")
                        
                except Exception as e:
                    errors.append(f"Error pushing task '{task.get('title', 'Unknown')}': {str(e)}")
            
            return {
                'tasks_pushed_to_ticktick': pushed_count,
                'push_errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error pushing tasks to TickTick: {e}")
            return {
                'tasks_pushed_to_ticktick': 0,
                'push_errors': [str(e)]
            }
    
    async def _pull_tasks_from_ticktick(self) -> Dict[str, Any]:
        """Pull tasks from TickTick to database."""
        try:
            # Get TickTick tasks
            ticktick_data = await self.ticktick.collect_data()
            
            if not ticktick_data.get('authenticated'):
                return {
                    'tasks_pulled_from_ticktick': 0,
                    'pull_errors': ['TickTick not authenticated']
                }
            
            ticktick_tasks = ticktick_data.get('tasks', [])
            existing_db_tasks = {task['source_id']: task for task in self.get_all_tasks(include_completed=True) 
                                if task['source'] == 'ticktick' and task['source_id']}
            
            pulled_count = 0
            updated_count = 0
            errors = []
            
            for tt_task in ticktick_tasks:
                try:
                    tt_id = tt_task.get('id', '')
                    
                    # Convert TickTick task to our format
                    task_data = {
                        'title': tt_task.get('title', ''),
                        'description': tt_task.get('content', ''),
                        'priority': self._convert_ticktick_priority(tt_task.get('priority', 0)),
                        'category': 'ticktick',
                        'source': 'ticktick',
                        'source_id': tt_id,
                        'status': 'completed' if tt_task.get('status') == 2 else 'pending',
                        'due_date': tt_task.get('due_date'),
                        'requires_response': 0
                    }
                    
                    if tt_id in existing_db_tasks:
                        # Update existing task
                        db_task = existing_db_tasks[tt_id]
                        if db_task['status'] != task_data['status']:
                            self.update_task_status(db_task['id'], task_data['status'])
                            updated_count += 1
                    else:
                        # Create new task
                        result = self.create_task(
                            title=task_data['title'],
                            description=task_data['description'],
                            priority=task_data['priority'],
                            category=task_data['category'],
                            due_date=datetime.fromisoformat(task_data['due_date']) if task_data['due_date'] else None,
                            source='ticktick',
                            source_id=tt_id,
                            sync_to_ticktick=False  # Already from TickTick
                        )
                        if result.get('success'):
                            pulled_count += 1
                        else:
                            errors.append(f"Failed to create task from TickTick: {task_data['title']}")
                            
                except Exception as e:
                    errors.append(f"Error processing TickTick task: {str(e)}")
            
            return {
                'tasks_pulled_from_ticktick': pulled_count,
                'tasks_updated': updated_count,
                'pull_errors': errors
            }
            
        except Exception as e:
            logger.error(f"Error pulling tasks from TickTick: {e}")
            return {
                'tasks_pulled_from_ticktick': 0,
                'tasks_updated': 0,
                'pull_errors': [str(e)]
            }
    
    def _convert_ticktick_priority(self, tt_priority: int) -> str:
        """Convert TickTick priority (0,1,3,5) to our format (low,medium,high)."""
        if tt_priority >= 5:
            return 'high'
        elif tt_priority >= 3:
            return 'medium'
        else:
            return 'low'
    
    def _sync_task_to_ticktick_sync(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sync a single task to TickTick (synchronous version for create_task)."""
        try:
            # For now, just return success without actually syncing
            # This prevents blocking during task creation
            # The actual sync can happen via the async sync endpoint
            return {'success': True, 'note': 'Task queued for TickTick sync'}
                
        except Exception as e:
            logger.error(f"Error queuing task for TickTick sync: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _sync_task_to_ticktick(self, task_data: Dict[str, Any]) -> Dict[str, Any]:
        """Sync a single task to TickTick."""
        try:
            if not await self.ticktick.is_authenticated():
                return {'success': False, 'error': 'TickTick not authenticated'}
            
            # Convert priority
            priority_map = {'low': 1, 'medium': 3, 'high': 5}
            ticktick_priority = priority_map.get(task_data.get('priority', 'medium'), 3)
            
            # Convert due date
            due_date = None
            if task_data.get('due_date'):
                try:
                    due_date = datetime.fromisoformat(task_data['due_date'])
                except:
                    pass
            
            # Create in TickTick
            created_task = await self.ticktick.create_task(
                title=task_data['title'],
                content=task_data.get('description', ''),
                due_date=due_date,
                priority=ticktick_priority,
                tags=['dashboard-sync', task_data.get('category', 'general')]
            )
            
            if created_task:
                # Update database with TickTick ID
                self.db.update_todo_source_id(task_data['id'], created_task.get('id', ''))
                return {'success': True, 'ticktick_id': created_task.get('id')}
            else:
                return {'success': False, 'error': 'Failed to create TickTick task'}
                
        except Exception as e:
            logger.error(f"Error syncing task to TickTick: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_task_statistics(self) -> Dict[str, Any]:
        """Get task statistics for dashboard display."""
        try:
            all_tasks = self.get_all_tasks(include_completed=True)
            
            stats = {
                'total_tasks': len(all_tasks),
                'pending_tasks': len([t for t in all_tasks if t['status'] == 'pending']),
                'completed_tasks': len([t for t in all_tasks if t['status'] == 'completed']),
                'high_priority': len([t for t in all_tasks if t['priority'] == 'high' and t['status'] == 'pending']),
                'medium_priority': len([t for t in all_tasks if t['priority'] == 'medium' and t['status'] == 'pending']),
                'low_priority': len([t for t in all_tasks if t['priority'] == 'low' and t['status'] == 'pending']),
                'overdue_tasks': 0,
                'due_today': 0,
                'due_this_week': 0,
                'by_category': {},
                'by_source': {}
            }
            
            # Calculate date-based stats
            today = datetime.now().date()
            week_end = today + timedelta(days=7)
            
            for task in all_tasks:
                if task['status'] != 'pending':
                    continue
                    
                # Due date calculations
                if task['due_date']:
                    try:
                        due_date = datetime.fromisoformat(task['due_date'].replace('Z', '+00:00')).date()
                        if due_date < today:
                            stats['overdue_tasks'] += 1
                        elif due_date == today:
                            stats['due_today'] += 1
                        elif due_date <= week_end:
                            stats['due_this_week'] += 1
                    except:
                        pass
                
                # Category stats
                category = task.get('category', 'general')
                stats['by_category'][category] = stats['by_category'].get(category, 0) + 1
                
                # Source stats
                source = task.get('source', 'manual')
                stats['by_source'][source] = stats['by_source'].get(source, 0) + 1
            
            return stats
            
        except Exception as e:
            logger.error(f"Error getting task statistics: {e}")
            return {
                'total_tasks': 0,
                'pending_tasks': 0,
                'completed_tasks': 0,
                'high_priority': 0,
                'medium_priority': 0,
                'low_priority': 0,
                'overdue_tasks': 0,
                'due_today': 0,
                'due_this_week': 0,
                'by_category': {},
                'by_source': {}
            }