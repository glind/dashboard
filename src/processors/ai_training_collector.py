"""
AI Training Data Collector - Gathers training data from user interactions and preferences.
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional

from database import db

logger = logging.getLogger(__name__)


class AITrainingDataCollector:
    """Collects and prepares training data for AI models."""
    
    def __init__(self):
        self.data_types = [
            'liked_news',
            'liked_music', 
            'liked_vanity',
            'liked_jokes',
            'email_patterns',
            'calendar_patterns',
            'widget_preferences',
            'search_queries'
        ]
    
    async def collect_all_training_data(self) -> Dict[str, List[Dict[str, Any]]]:
        """Collect all available training data."""
        training_data = {}
        
        # Collect liked content
        training_data['liked_content'] = await self.collect_liked_content()
        
        # Collect email patterns
        training_data['email_patterns'] = await self.collect_email_patterns()
        
        # Collect calendar patterns  
        training_data['calendar_patterns'] = await self.collect_calendar_patterns()
        
        # Collect widget preferences
        training_data['widget_preferences'] = await self.collect_widget_preferences()
        
        # Collect interaction patterns
        training_data['interaction_patterns'] = await self.collect_interaction_patterns()
        
        return training_data
    
    async def collect_liked_content(self) -> List[Dict[str, Any]]:
        """Collect liked content for training."""
        try:
            liked_items = db.get_liked_items(limit=500)
            training_samples = []
            
            for item in liked_items:
                content = f"Title: {item['item_title']}"
                if item['item_content']:
                    content += f"\nContent: {item['item_content']}"
                
                # Parse metadata for additional context
                metadata = {}
                if item['item_metadata']:
                    try:
                        metadata = json.loads(item['item_metadata'])
                    except:
                        metadata = {'raw_metadata': item['item_metadata']}
                
                # Create training sample
                sample = {
                    'data_type': f"liked_{item['item_type']}",
                    'content': content,
                    'context': f"User liked this {item['item_type']} content",
                    'metadata': metadata,
                    'category': item.get('category', 'general'),
                    'timestamp': item['feedback_timestamp'],
                    'relevance_score': 0.8  # High relevance for liked content
                }
                
                training_samples.append(sample)
                
            logger.info(f"Collected {len(training_samples)} liked content samples")
            return training_samples
            
        except Exception as e:
            logger.error(f"Error collecting liked content: {e}")
            return []
    
    async def collect_email_patterns(self) -> List[Dict[str, Any]]:
        """Collect email patterns for AI training."""
        try:
            training_samples = []
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get email patterns from recent emails
                cursor.execute("""
                    SELECT sender, subject, snippet, priority, category, 
                           received_date, requires_response, is_important
                    FROM emails 
                    WHERE received_date > datetime('now', '-60 days')
                    ORDER BY received_date DESC
                    LIMIT 200
                """)
                
                emails = cursor.fetchall()
                
                for email in emails:
                    content = f"From: {email['sender']}\nSubject: {email['subject']}"
                    if email['snippet']:
                        content += f"\nSnippet: {email['snippet'][:200]}"
                    
                    context_parts = []
                    if email['priority'] and email['priority'] != 'normal':
                        context_parts.append(f"Priority: {email['priority']}")
                    if email['category']:
                        context_parts.append(f"Category: {email['category']}")
                    if email['requires_response']:
                        context_parts.append("Requires response")
                    if email['is_important']:
                        context_parts.append("Marked as important")
                    
                    sample = {
                        'data_type': 'email_patterns',
                        'content': content,
                        'context': '; '.join(context_parts) if context_parts else 'Regular email',
                        'metadata': {
                            'sender': email['sender'],
                            'priority': email['priority'],
                            'category': email['category'],
                            'requires_response': bool(email['requires_response']),
                            'is_important': bool(email['is_important'])
                        },
                        'timestamp': email['received_date'],
                        'relevance_score': 0.6
                    }
                    
                    training_samples.append(sample)
            
            logger.info(f"Collected {len(training_samples)} email pattern samples")
            return training_samples
            
        except Exception as e:
            logger.error(f"Error collecting email patterns: {e}")
            return []
    
    async def collect_calendar_patterns(self) -> List[Dict[str, Any]]:
        """Collect calendar patterns for AI training."""
        try:
            training_samples = []
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get calendar events
                cursor.execute("""
                    SELECT title, description, location, start_time, end_time, 
                           organizer, attendees, category
                    FROM calendar_events 
                    WHERE start_time > datetime('now', '-30 days')
                    ORDER BY start_time DESC
                    LIMIT 100
                """)
                
                events = cursor.fetchall()
                
                for event in events:
                    content = f"Event: {event['title']}"
                    if event['description']:
                        content += f"\nDescription: {event['description'][:200]}"
                    if event['location']:
                        content += f"\nLocation: {event['location']}"
                    
                    # Calculate event duration
                    start_time = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(event['end_time'].replace('Z', '+00:00'))
                    duration = (end_time - start_time).total_seconds() / 3600  # hours
                    
                    context_parts = [f"Duration: {duration:.1f} hours"]
                    if event['organizer']:
                        context_parts.append(f"Organized by: {event['organizer']}")
                    if event['category']:
                        context_parts.append(f"Category: {event['category']}")
                    
                    sample = {
                        'data_type': 'calendar_patterns',
                        'content': content,
                        'context': '; '.join(context_parts),
                        'metadata': {
                            'organizer': event['organizer'],
                            'location': event['location'],
                            'duration_hours': duration,
                            'category': event['category'],
                            'attendee_count': len(event['attendees'].split(',')) if event['attendees'] else 0
                        },
                        'timestamp': event['start_time'],
                        'relevance_score': 0.5
                    }
                    
                    training_samples.append(sample)
            
            logger.info(f"Collected {len(training_samples)} calendar pattern samples")
            return training_samples
            
        except Exception as e:
            logger.error(f"Error collecting calendar patterns: {e}")
            return []
    
    async def collect_widget_preferences(self) -> List[Dict[str, Any]]:
        """Collect widget configuration preferences."""
        try:
            training_samples = []
            
            # Get admin settings
            admin_settings = db.get_setting('admin_settings', {})
            widget_config = admin_settings.get('widgets', {})
            
            for widget_name, config in widget_config.items():
                if config.get('enabled', True):
                    content = f"Widget: {widget_name}"
                    if 'position' in config:
                        content += f"\nPosition: {config['position']}"
                    
                    context_parts = [f"Enabled widget: {widget_name}"]
                    if 'refresh_interval' in config:
                        context_parts.append(f"Refresh interval: {config['refresh_interval']}")
                    
                    sample = {
                        'data_type': 'widget_preferences',
                        'content': content,
                        'context': '; '.join(context_parts),
                        'metadata': config,
                        'timestamp': datetime.now().isoformat(),
                        'relevance_score': 0.4
                    }
                    
                    training_samples.append(sample)
            
            # Get specific widget configurations
            vanity_config = db.get_setting('vanity_config', {})
            if vanity_config:
                content = "Vanity search configuration:\n"
                if 'names' in vanity_config:
                    content += f"Names: {', '.join(vanity_config['names'])}\n"
                if 'companies' in vanity_config:
                    content += f"Companies: {', '.join(vanity_config['companies'])}\n"
                if 'terms' in vanity_config:
                    content += f"Search terms: {', '.join(vanity_config['terms'])}"
                
                sample = {
                    'data_type': 'widget_preferences',
                    'content': content,
                    'context': 'User configured vanity search terms',
                    'metadata': vanity_config,
                    'timestamp': datetime.now().isoformat(),
                    'relevance_score': 0.7
                }
                training_samples.append(sample)
            
            logger.info(f"Collected {len(training_samples)} widget preference samples")
            return training_samples
            
        except Exception as e:
            logger.error(f"Error collecting widget preferences: {e}")
            return []
    
    async def collect_interaction_patterns(self) -> List[Dict[str, Any]]:
        """Collect user interaction patterns."""
        try:
            training_samples = []
            
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get feedback patterns
                cursor.execute("""
                    SELECT feedback_type, item_type, category, 
                           COUNT(*) as count,
                           MAX(feedback_timestamp) as last_feedback
                    FROM user_feedback 
                    WHERE feedback_timestamp > datetime('now', '-30 days')
                    GROUP BY feedback_type, item_type, category
                    ORDER BY count DESC
                """)
                
                patterns = cursor.fetchall()
                
                for pattern in patterns:
                    content = f"User interaction pattern: {pattern['feedback_type']} on {pattern['item_type']}"
                    if pattern['category']:
                        content += f" in {pattern['category']} category"
                    content += f"\nFrequency: {pattern['count']} times in last 30 days"
                    
                    context = f"User frequently gives {pattern['feedback_type']} feedback on {pattern['item_type']} content"
                    
                    sample = {
                        'data_type': 'interaction_patterns',
                        'content': content,
                        'context': context,
                        'metadata': {
                            'feedback_type': pattern['feedback_type'],
                            'item_type': pattern['item_type'],
                            'category': pattern['category'],
                            'frequency': pattern['count']
                        },
                        'timestamp': pattern['last_feedback'],
                        'relevance_score': min(0.9, pattern['count'] / 10.0)  # Higher frequency = higher relevance
                    }
                    
                    training_samples.append(sample)
            
            logger.info(f"Collected {len(training_samples)} interaction pattern samples")
            return training_samples
            
        except Exception as e:
            logger.error(f"Error collecting interaction patterns: {e}")
            return []
    
    async def prepare_training_dataset(self, data_types: List[str] = None) -> List[Dict[str, Any]]:
        """Prepare complete training dataset."""
        if data_types is None:
            data_types = self.data_types
        
        all_data = await self.collect_all_training_data()
        training_dataset = []
        
        for data_type, samples in all_data.items():
            if data_type in data_types or not data_types:
                training_dataset.extend(samples)
        
        # Sort by relevance score and timestamp
        training_dataset.sort(key=lambda x: (x['relevance_score'], x['timestamp']), reverse=True)
        
        # Save to database
        for sample in training_dataset:
            db.save_ai_training_data(
                data_type=sample['data_type'],
                content=sample['content'],
                context=sample['context'],
                source_table=sample.get('source_table'),
                source_id=sample.get('source_id'),
                relevance_score=sample['relevance_score']
            )
        
        logger.info(f"Prepared training dataset with {len(training_dataset)} samples")
        return training_dataset
    
    def get_training_summary(self) -> Dict[str, Any]:
        """Get summary of available training data."""
        training_data = db.get_ai_training_data(limit=10000)
        
        summary = {
            'total_samples': len(training_data),
            'by_type': {},
            'date_range': {
                'earliest': None,
                'latest': None
            },
            'avg_relevance': 0.0
        }
        
        if training_data:
            # Count by type
            for item in training_data:
                data_type = item['data_type']
                summary['by_type'][data_type] = summary['by_type'].get(data_type, 0) + 1
            
            # Date range
            dates = [item['created_at'] for item in training_data if item['created_at']]
            if dates:
                summary['date_range']['earliest'] = min(dates)
                summary['date_range']['latest'] = max(dates)
            
            # Average relevance
            relevance_scores = [item['relevance_score'] for item in training_data if item['relevance_score']]
            if relevance_scores:
                summary['avg_relevance'] = sum(relevance_scores) / len(relevance_scores)
        
        return summary


# Global training data collector instance
training_collector = AITrainingDataCollector()
