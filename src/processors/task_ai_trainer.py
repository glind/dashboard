"""
Task AI Trainer - Learns from user task behaviors to understand priorities and preferences.

This module analyzes:
- Completed vs deleted tasks to learn preferences
- Task priority patterns and completion rates  
- Project types and categories that get attention
- Keywords and patterns in tasks that succeed vs fail
"""

import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from collections import defaultdict, Counter
from pathlib import Path
import json
import re

from database import DatabaseManager

logger = logging.getLogger(__name__)


@dataclass
class TaskPattern:
    """Represents a learned pattern from task behavior."""
    keywords: List[str]
    category: str
    priority_preference: str
    completion_rate: float
    average_completion_days: float
    confidence_score: float
    examples: List[str]


@dataclass
class UserPreferences:
    """User's learned preferences from task analysis."""
    preferred_project_types: List[str]
    high_value_keywords: List[str]
    low_value_keywords: List[str]  # Often deleted/ignored
    optimal_task_size: str  # small, medium, large based on completion patterns
    preferred_priorities: List[str]
    company_interaction_patterns: Dict[str, Any]
    meeting_preferences: Dict[str, Any]


class TaskAITrainer:
    """Analyzes task completion patterns to train AI preferences."""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.patterns = []
        self.user_preferences = None
        
    async def analyze_task_patterns(self) -> UserPreferences:
        """Analyze all task data to extract user behavior patterns."""
        try:
            logger.info("Analyzing task patterns for AI training...")
            
            # Get all task data from database
            all_tasks = await self._get_all_task_data()
            
            if not all_tasks:
                logger.warning("No task data found for analysis")
                return self._default_preferences()
            
            # Analyze different aspects of task behavior
            completion_patterns = self._analyze_completion_patterns(all_tasks)
            priority_patterns = self._analyze_priority_patterns(all_tasks)
            keyword_patterns = self._analyze_keyword_patterns(all_tasks)
            category_patterns = self._analyze_category_patterns(all_tasks)
            deletion_patterns = self._analyze_deletion_patterns(all_tasks)
            
            # Extract company and meeting preferences from task content
            company_patterns = self._extract_company_patterns(all_tasks)
            meeting_patterns = self._extract_meeting_patterns(all_tasks)
            
            # Combine into user preferences
            preferences = UserPreferences(
                preferred_project_types=self._get_preferred_project_types(category_patterns),
                high_value_keywords=keyword_patterns['high_value'],
                low_value_keywords=keyword_patterns['low_value'],
                optimal_task_size=self._determine_optimal_task_size(completion_patterns),
                preferred_priorities=priority_patterns['preferred'],
                company_interaction_patterns=company_patterns,
                meeting_preferences=meeting_patterns
            )
            
            self.user_preferences = preferences
            
            # Save patterns for future use
            await self._save_learned_patterns(preferences)
            
            logger.info("Task pattern analysis completed successfully")
            return preferences
            
        except Exception as e:
            logger.error(f"Error analyzing task patterns: {e}")
            return self._default_preferences()
    
    async def _get_all_task_data(self) -> List[Dict[str, Any]]:
        """Retrieve all task data including deleted tasks for pattern analysis."""
        try:
            # Get completed tasks
            completed_tasks = self.db.get_todos(include_completed=True, include_deleted=False)
            
            # Get deleted tasks for negative pattern learning
            deleted_tasks = self.db.get_todos(include_completed=True, include_deleted=True)
            deleted_only = [task for task in deleted_tasks if task.get('status') == 'deleted']
            
            all_tasks = []
            
            # Process completed tasks
            for task in completed_tasks:
                task_data = {
                    'id': task.get('id'),
                    'title': task.get('title', ''),
                    'description': task.get('description', ''),
                    'priority': task.get('priority', 'medium'),
                    'category': task.get('category', 'general'),
                    'status': task.get('status', 'pending'),
                    'created_at': task.get('created_at'),
                    'completed_at': task.get('completed_at'),
                    'source': task.get('source', 'user'),
                    'behavior_type': 'completed' if task.get('status') == 'completed' else 'active'
                }
                all_tasks.append(task_data)
            
            # Process deleted tasks
            for task in deleted_only:
                task_data = {
                    'id': task.get('id'),
                    'title': task.get('title', ''),
                    'description': task.get('description', ''),
                    'priority': task.get('priority', 'medium'),
                    'category': task.get('category', 'general'),
                    'status': task.get('status', 'deleted'),
                    'created_at': task.get('created_at'),
                    'completed_at': None,
                    'source': task.get('source', 'user'),
                    'behavior_type': 'deleted'
                }
                all_tasks.append(task_data)
            
            logger.info(f"Retrieved {len(all_tasks)} tasks for pattern analysis")
            return all_tasks
            
        except Exception as e:
            logger.error(f"Error retrieving task data: {e}")
            return []
    
    def _analyze_completion_patterns(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze which types of tasks get completed vs abandoned."""
        completed_tasks = [t for t in tasks if t['behavior_type'] == 'completed']
        deleted_tasks = [t for t in tasks if t['behavior_type'] == 'deleted']
        
        completion_patterns = {
            'total_completed': len(completed_tasks),
            'total_deleted': len(deleted_tasks),
            'completion_rate': len(completed_tasks) / len(tasks) if tasks else 0,
            'avg_completion_time': self._calculate_avg_completion_time(completed_tasks),
            'completion_by_priority': self._group_completion_by_field(tasks, 'priority'),
            'completion_by_category': self._group_completion_by_field(tasks, 'category'),
            'completion_by_source': self._group_completion_by_field(tasks, 'source')
        }
        
        return completion_patterns
    
    def _analyze_priority_patterns(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze priority assignment and completion patterns."""
        priority_stats = defaultdict(lambda: {'completed': 0, 'deleted': 0, 'total': 0})
        
        for task in tasks:
            priority = task['priority']
            priority_stats[priority]['total'] += 1
            
            if task['behavior_type'] == 'completed':
                priority_stats[priority]['completed'] += 1
            elif task['behavior_type'] == 'deleted':
                priority_stats[priority]['deleted'] += 1
        
        # Calculate completion rates by priority
        priority_completion_rates = {}
        for priority, stats in priority_stats.items():
            if stats['total'] > 0:
                priority_completion_rates[priority] = stats['completed'] / stats['total']
        
        # Sort by completion rate to find preferred priorities
        preferred_priorities = sorted(priority_completion_rates.keys(), 
                                    key=lambda p: priority_completion_rates[p], 
                                    reverse=True)
        
        return {
            'preferred': preferred_priorities,
            'completion_rates': priority_completion_rates,
            'stats': dict(priority_stats)
        }
    
    def _analyze_keyword_patterns(self, tasks: List[Dict[str, Any]]) -> Dict[str, List[str]]:
        """Extract keywords that correlate with completion vs deletion."""
        completed_tasks = [t for t in tasks if t['behavior_type'] == 'completed']
        deleted_tasks = [t for t in tasks if t['behavior_type'] == 'deleted']
        
        # Extract keywords from completed tasks
        completed_keywords = self._extract_keywords_from_tasks(completed_tasks)
        deleted_keywords = self._extract_keywords_from_tasks(deleted_tasks)
        
        # Find keywords that appear more in completed vs deleted tasks
        high_value_keywords = []
        low_value_keywords = []
        
        all_keywords = set(completed_keywords.keys()) | set(deleted_keywords.keys())
        
        for keyword in all_keywords:
            completed_count = completed_keywords.get(keyword, 0)
            deleted_count = deleted_keywords.get(keyword, 0)
            total_count = completed_count + deleted_count
            
            if total_count >= 2:  # Only consider keywords that appear multiple times
                completion_ratio = completed_count / total_count
                
                if completion_ratio >= 0.7:  # 70% or more completion rate
                    high_value_keywords.append(keyword)
                elif completion_ratio <= 0.3:  # 30% or less completion rate
                    low_value_keywords.append(keyword)
        
        # Sort by frequency
        high_value_keywords = sorted(high_value_keywords, 
                                   key=lambda k: completed_keywords.get(k, 0), 
                                   reverse=True)[:20]
        low_value_keywords = sorted(low_value_keywords, 
                                  key=lambda k: deleted_keywords.get(k, 0), 
                                  reverse=True)[:20]
        
        return {
            'high_value': high_value_keywords,
            'low_value': low_value_keywords
        }
    
    def _extract_keywords_from_tasks(self, tasks: List[Dict[str, Any]]) -> Counter:
        """Extract meaningful keywords from task titles and descriptions."""
        keywords = Counter()
        
        # Common stop words to ignore
        stop_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before',
            'after', 'above', 'below', 'between', 'among', 'until', 'while',
            'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
            'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'should'
        }
        
        for task in tasks:
            text = f"{task['title']} {task['description']}".lower()
            
            # Extract words (alphanumeric, allow hyphens)
            words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9-]*\b', text)
            
            for word in words:
                if len(word) >= 3 and word not in stop_words:
                    keywords[word] += 1
        
        return keywords
    
    def _analyze_category_patterns(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze which categories get most attention and completion."""
        category_stats = defaultdict(lambda: {'completed': 0, 'deleted': 0, 'total': 0})
        
        for task in tasks:
            category = task['category']
            category_stats[category]['total'] += 1
            
            if task['behavior_type'] == 'completed':
                category_stats[category]['completed'] += 1
            elif task['behavior_type'] == 'deleted':
                category_stats[category]['deleted'] += 1
        
        # Calculate engagement scores (completion rate * total volume)
        category_scores = {}
        for category, stats in category_stats.items():
            if stats['total'] > 0:
                completion_rate = stats['completed'] / stats['total']
                volume_score = min(stats['total'] / 10, 1.0)  # Normalize volume
                category_scores[category] = completion_rate * volume_score
        
        return {
            'stats': dict(category_stats),
            'scores': category_scores
        }
    
    def _analyze_deletion_patterns(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze patterns in deleted tasks to understand what to avoid."""
        deleted_tasks = [t for t in tasks if t['behavior_type'] == 'deleted']
        
        if not deleted_tasks:
            return {'patterns': [], 'keywords': []}
        
        # Analyze common patterns in deleted tasks
        deletion_keywords = self._extract_keywords_from_tasks(deleted_tasks)
        common_deletion_priorities = Counter([t['priority'] for t in deleted_tasks])
        common_deletion_categories = Counter([t['category'] for t in deleted_tasks])
        
        return {
            'keywords': list(deletion_keywords.most_common(10)),
            'priorities': dict(common_deletion_priorities),
            'categories': dict(common_deletion_categories),
            'total_deleted': len(deleted_tasks)
        }
    
    def _extract_company_patterns(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract company interaction patterns from task content."""
        company_keywords = [
            'buildly', 'open build', 'oregon software', 'meeting', 'call', 'demo',
            'proposal', 'contract', 'client', 'customer', 'lead', 'prospect'
        ]
        
        company_tasks = []
        for task in tasks:
            text = f"{task['title']} {task['description']}".lower()
            if any(keyword in text for keyword in company_keywords):
                company_tasks.append(task)
        
        # Analyze completion rates for company-related tasks
        completed_company_tasks = [t for t in company_tasks if t['behavior_type'] == 'completed']
        
        return {
            'total_company_tasks': len(company_tasks),
            'completed_company_tasks': len(completed_company_tasks),
            'company_completion_rate': len(completed_company_tasks) / len(company_tasks) if company_tasks else 0,
            'preferred_company_priorities': self._get_company_priority_preferences(company_tasks),
            'company_interaction_keywords': self._extract_keywords_from_tasks(completed_company_tasks)
        }
    
    def _extract_meeting_patterns(self, tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract meeting and scheduling patterns from tasks."""
        meeting_keywords = ['meeting', 'call', 'demo', 'presentation', 'sync', 'standup']
        
        meeting_tasks = []
        for task in tasks:
            text = f"{task['title']} {task['description']}".lower()
            if any(keyword in text for keyword in meeting_keywords):
                meeting_tasks.append(task)
        
        return {
            'total_meeting_tasks': len(meeting_tasks),
            'meeting_completion_rate': len([t for t in meeting_tasks if t['behavior_type'] == 'completed']) / len(meeting_tasks) if meeting_tasks else 0,
            'preferred_meeting_times': self._analyze_meeting_timing(meeting_tasks),
            'meeting_types': self._categorize_meeting_types(meeting_tasks)
        }
    
    def _get_preferred_project_types(self, category_patterns: Dict[str, Any]) -> List[str]:
        """Determine preferred project types based on category engagement."""
        category_scores = category_patterns['scores']
        
        # Sort categories by engagement score
        sorted_categories = sorted(category_scores.items(), key=lambda x: x[1], reverse=True)
        
        # Return top categories that have significant engagement
        return [cat for cat, score in sorted_categories if score > 0.3][:5]
    
    def _determine_optimal_task_size(self, completion_patterns: Dict[str, Any]) -> str:
        """Determine optimal task size based on completion patterns."""
        # This is a simplified heuristic - could be enhanced with NLP analysis
        avg_completion_time = completion_patterns.get('avg_completion_time', 0)
        
        if avg_completion_time <= 1:
            return 'small'
        elif avg_completion_time <= 7:
            return 'medium'
        else:
            return 'large'
    
    def _calculate_avg_completion_time(self, completed_tasks: List[Dict[str, Any]]) -> float:
        """Calculate average days to complete tasks."""
        completion_times = []
        
        for task in completed_tasks:
            if task['created_at'] and task['completed_at']:
                try:
                    created = datetime.fromisoformat(task['created_at'].replace('Z', '+00:00'))
                    completed = datetime.fromisoformat(task['completed_at'].replace('Z', '+00:00'))
                    days = (completed - created).days
                    if days >= 0:  # Sanity check
                        completion_times.append(days)
                except Exception:
                    continue
        
        return sum(completion_times) / len(completion_times) if completion_times else 0
    
    def _group_completion_by_field(self, tasks: List[Dict[str, Any]], field: str) -> Dict[str, float]:
        """Group completion rates by a specific field."""
        field_stats = defaultdict(lambda: {'completed': 0, 'total': 0})
        
        for task in tasks:
            field_value = task.get(field, 'unknown')
            field_stats[field_value]['total'] += 1
            
            if task['behavior_type'] == 'completed':
                field_stats[field_value]['completed'] += 1
        
        # Calculate completion rates
        completion_rates = {}
        for field_value, stats in field_stats.items():
            if stats['total'] > 0:
                completion_rates[field_value] = stats['completed'] / stats['total']
        
        return completion_rates
    
    def _get_company_priority_preferences(self, company_tasks: List[Dict[str, Any]]) -> List[str]:
        """Get priority preferences for company-related tasks."""
        completed_company_tasks = [t for t in company_tasks if t['behavior_type'] == 'completed']
        
        if not completed_company_tasks:
            return ['high', 'medium']  # Default assumption
        
        priority_counts = Counter([t['priority'] for t in completed_company_tasks])
        return [priority for priority, count in priority_counts.most_common()]
    
    def _analyze_meeting_timing(self, meeting_tasks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze timing patterns in meeting tasks."""
        # This would be enhanced with actual calendar integration
        return {
            'preferred_days': ['Tuesday', 'Wednesday', 'Thursday'],
            'preferred_times': ['10:00-12:00', '14:00-16:00'],
            'meeting_duration_preference': 'medium'
        }
    
    def _categorize_meeting_types(self, meeting_tasks: List[Dict[str, Any]]) -> Dict[str, int]:
        """Categorize different types of meetings from task content."""
        meeting_types = defaultdict(int)
        
        for task in meeting_tasks:
            text = f"{task['title']} {task['description']}".lower()
            
            if any(word in text for word in ['demo', 'presentation', 'showcase']):
                meeting_types['demo'] += 1
            elif any(word in text for word in ['sync', 'standup', 'check-in']):
                meeting_types['sync'] += 1
            elif any(word in text for word in ['sales', 'proposal', 'contract']):
                meeting_types['sales'] += 1
            elif any(word in text for word in ['technical', 'architecture', 'development']):
                meeting_types['technical'] += 1
            else:
                meeting_types['general'] += 1
        
        return dict(meeting_types)
    
    async def _save_learned_patterns(self, preferences: UserPreferences) -> None:
        """Save learned patterns to database for future reference."""
        try:
            # Convert preferences to JSON for storage
            preferences_data = {
                'preferred_project_types': preferences.preferred_project_types,
                'high_value_keywords': preferences.high_value_keywords,
                'low_value_keywords': preferences.low_value_keywords,
                'optimal_task_size': preferences.optimal_task_size,
                'preferred_priorities': preferences.preferred_priorities,
                'company_interaction_patterns': preferences.company_interaction_patterns,
                'meeting_preferences': preferences.meeting_preferences,
                'last_updated': datetime.now().isoformat()
            }
            
            # Get project root (two levels up from processors/)
            project_root = Path(__file__).parent.parent.parent
            data_dir = project_root / "data"
            data_dir.mkdir(exist_ok=True)
            
            # Save to a simple JSON file for now
            # In production, this could be stored in a dedicated preferences table
            patterns_file = data_dir / "learned_task_patterns.json"
            with open(patterns_file, 'w') as f:
                json.dump(preferences_data, f, indent=2, default=str)
            
            logger.info("Learned patterns saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving learned patterns: {e}")
    
    def _default_preferences(self) -> UserPreferences:
        """Return default preferences when no task data is available."""
        return UserPreferences(
            preferred_project_types=['development', 'business', 'client-work'],
            high_value_keywords=['important', 'urgent', 'client', 'revenue'],
            low_value_keywords=['maybe', 'someday', 'nice-to-have'],
            optimal_task_size='medium',
            preferred_priorities=['high', 'medium'],
            company_interaction_patterns={
                'total_company_tasks': 0,
                'company_completion_rate': 0.8,  # Assume high completion for business tasks
                'preferred_company_priorities': ['high', 'medium']
            },
            meeting_preferences={
                'preferred_days': ['Tuesday', 'Wednesday', 'Thursday'],
                'preferred_times': ['10:00-12:00', '14:00-16:00']
            }
        )

    async def get_task_recommendations(self, task_content: str) -> Dict[str, Any]:
        """Provide recommendations for a new task based on learned patterns."""
        if not self.user_preferences:
            self.user_preferences = await self.analyze_task_patterns()
        
        recommendations = {}
        
        # Analyze task content for keywords
        content_lower = task_content.lower()
        
        # Check for high-value keywords
        matching_high_value = [kw for kw in self.user_preferences.high_value_keywords if kw in content_lower]
        matching_low_value = [kw for kw in self.user_preferences.low_value_keywords if kw in content_lower]
        
        # Recommend priority based on keyword analysis
        if matching_high_value:
            recommendations['suggested_priority'] = 'high'
            recommendations['priority_reason'] = f"Contains high-value keywords: {', '.join(matching_high_value)}"
        elif matching_low_value:
            recommendations['suggested_priority'] = 'low'
            recommendations['priority_reason'] = f"Contains low-value keywords: {', '.join(matching_low_value)}"
        else:
            recommendations['suggested_priority'] = self.user_preferences.preferred_priorities[0] if self.user_preferences.preferred_priorities else 'medium'
            recommendations['priority_reason'] = "Based on your typical priority preferences"
        
        # Check if it's company-related
        company_keywords = ['buildly', 'open build', 'oregon software', 'client', 'meeting', 'demo']
        if any(kw in content_lower for kw in company_keywords):
            recommendations['is_company_related'] = True
            recommendations['suggested_category'] = 'business'
        else:
            recommendations['is_company_related'] = False
            recommendations['suggested_category'] = self.user_preferences.preferred_project_types[0] if self.user_preferences.preferred_project_types else 'general'
        
        # Estimate completion likelihood
        completion_score = 0.5  # Base score
        completion_score += 0.2 * len(matching_high_value)  # Boost for high-value keywords
        completion_score -= 0.1 * len(matching_low_value)  # Penalty for low-value keywords
        
        recommendations['estimated_completion_likelihood'] = min(max(completion_score, 0.1), 0.9)
        
        return recommendations