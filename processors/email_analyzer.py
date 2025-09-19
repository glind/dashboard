"""
Email analysis processor for extracting insights from email content.
"""

import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
import re

logger = logging.getLogger(__name__)


class EmailAnalyzer:
    """Analyzes email content for insights and priorities."""
    
    def __init__(self):
        """Initialize the email analyzer."""
        self.priority_keywords = [
            'urgent', 'asap', 'deadline', 'priority', 'important',
            'meeting', 'call', 'schedule', 'confirm', 'approve',
            'review', 'feedback', 'response', 'action required'
        ]
        
        self.question_patterns = [
            r'\?',
            r'\bcan you\b',
            r'\bcould you\b',
            r'\bwould you\b',
            r'\bwill you\b',
            r'\bplease\b.*\?'
        ]
    
    async def test_connection(self) -> bool:
        """Test if AI services are available for email analysis."""
        try:
            # Simple test - for now just return False since we're not using Ollama for basic analysis
            # This could be enhanced to test actual AI providers in the future
            return False
        except Exception as e:
            logger.error(f"Error testing AI connection: {e}")
            return False
    
    def analyze_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single email for insights."""
        try:
            subject = email_data.get('subject', '').lower()
            body = email_data.get('body', '').lower()
            sender = email_data.get('sender', '')
            
            analysis = {
                'priority_score': self._calculate_priority_score(subject, body),
                'has_questions': self._has_questions(subject, body),
                'action_required': self._requires_action(subject, body),
                'meeting_related': self._is_meeting_related(subject, body),
                'sender': sender,
                'subject': email_data.get('subject', ''),
                'timestamp': email_data.get('timestamp', datetime.now().isoformat())
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analyzing email: {e}")
            return {
                'priority_score': 0,
                'has_questions': False,
                'action_required': False,
                'meeting_related': False,
                'sender': email_data.get('sender', ''),
                'subject': email_data.get('subject', ''),
                'timestamp': email_data.get('timestamp', datetime.now().isoformat())
            }
    
    def analyze_batch(self, emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze a batch of emails and provide summary insights."""
        if not emails:
            return {
                'total_emails': 0,
                'high_priority': 0,
                'action_required': 0,
                'meetings': 0,
                'questions': 0,
                'top_senders': [],
                'insights': []
            }
        
        analyzed_emails = [self.analyze_email(email) for email in emails]
        
        # Calculate summary statistics
        total = len(analyzed_emails)
        high_priority = sum(1 for email in analyzed_emails if email['priority_score'] >= 3)
        action_required = sum(1 for email in analyzed_emails if email['action_required'])
        meetings = sum(1 for email in analyzed_emails if email['meeting_related'])
        questions = sum(1 for email in analyzed_emails if email['has_questions'])
        
        # Get top senders
        sender_counts = {}
        for email in analyzed_emails:
            sender = email['sender']
            sender_counts[sender] = sender_counts.get(sender, 0) + 1
        
        top_senders = sorted(sender_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        
        # Generate insights
        insights = self._generate_insights(analyzed_emails)
        
        return {
            'total_emails': total,
            'high_priority': high_priority,
            'action_required': action_required,
            'meetings': meetings,
            'questions': questions,
            'top_senders': top_senders,
            'insights': insights,
            'analyzed_emails': analyzed_emails
        }
    
    def _calculate_priority_score(self, subject: str, body: str) -> int:
        """Calculate priority score from 0-5."""
        score = 0
        text = f"{subject} {body}"
        
        for keyword in self.priority_keywords:
            if keyword in text:
                score += 1
        
        # Boost score for certain patterns
        if 'urgent' in text or 'asap' in text:
            score += 2
        if 'deadline' in text:
            score += 1
        if re.search(r'\btoday\b|\bthis week\b', text):
            score += 1
            
        return min(score, 5)  # Cap at 5
    
    def _has_questions(self, subject: str, body: str) -> bool:
        """Check if email contains questions."""
        text = f"{subject} {body}"
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in self.question_patterns)
    
    def _requires_action(self, subject: str, body: str) -> bool:
        """Check if email requires action."""
        action_keywords = [
            'please', 'can you', 'could you', 'would you', 'need', 'require',
            'action required', 'response needed', 'reply', 'confirm', 'approve'
        ]
        text = f"{subject} {body}"
        return any(keyword in text for keyword in action_keywords)
    
    def _is_meeting_related(self, subject: str, body: str) -> bool:
        """Check if email is meeting related."""
        meeting_keywords = [
            'meeting', 'call', 'zoom', 'teams', 'conference', 'schedule',
            'calendar', 'appointment', 'invite', 'agenda'
        ]
        text = f"{subject} {body}"
        return any(keyword in text for keyword in meeting_keywords)
    
    def _generate_insights(self, analyzed_emails: List[Dict[str, Any]]) -> List[str]:
        """Generate insights from analyzed emails."""
        insights = []
        
        if not analyzed_emails:
            return insights
        
        high_priority = [e for e in analyzed_emails if e['priority_score'] >= 3]
        if high_priority:
            insights.append(f"{len(high_priority)} high priority emails need attention")
        
        action_emails = [e for e in analyzed_emails if e['action_required']]
        if action_emails:
            insights.append(f"{len(action_emails)} emails require your response")
        
        meeting_emails = [e for e in analyzed_emails if e['meeting_related']]
        if meeting_emails:
            insights.append(f"{len(meeting_emails)} meeting-related emails")
        
        question_emails = [e for e in analyzed_emails if e['has_questions']]
        if question_emails:
            insights.append(f"{len(question_emails)} emails contain questions")
        
        return insights
