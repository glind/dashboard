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
    
    async def analyze_email_for_todos(self, subject: str, body: str, sender: str, risk_score: int = 0) -> List[Dict[str, Any]]:
        """Analyze email content for todo items and action items - STRICT filtering with risk scoring.
        
        Args:
            subject: Email subject
            body: Email body content
            sender: Email sender address
            risk_score: Risk score from EmailRiskChecker (1-10, where 10 is highest risk)
        
        Returns:
            List of todo items if email is legitimate and actionable, empty list otherwise
        """
        try:
            todos = []
            combined_text = f"{subject} {body}".lower()
            
            # FIRST CHECK: Risk score filter - skip high-risk emails
            # Only create tasks for low-medium risk emails (score < 5)
            if risk_score >= 5:
                logger.info(f"Skipping task creation for email from {sender} - risk score too high ({risk_score}/10)")
                return []
            
            # SECOND CHECK: Check deleted tasks history - don't recreate similar tasks user deleted
            if self.db:
                # Check if user has deleted similar tasks from this sender
                deleted_tasks = self.db.get_todos_by_source('email', status='deleted')
                similar_deleted = [t for t in deleted_tasks if sender.lower() in t.get('description', '').lower()]
                if len(similar_deleted) >= 3:
                    # User has deleted 3+ tasks from this sender - likely doesn't want tasks from them
                    logger.info(f"Skipping task creation from {sender} - user has deleted {len(similar_deleted)} similar tasks")
                    return []
                
                # Check if there's a deleted task with very similar subject
                for deleted in deleted_tasks:
                    deleted_title = deleted.get('title', '').lower()
                    # Calculate simple similarity (common words)
                    subject_words = set(subject.lower().split())
                    deleted_words = set(deleted_title.split())
                    if len(subject_words & deleted_words) >= 3:  # 3+ common words
                        logger.info(f"Skipping task - user deleted similar task: {deleted_title[:50]}")
                        return []
                
                # THIRD CHECK: User personality profile - check if sender is preferred
                personality = self.db.get_personality_profile()
                if personality and 'disliked_senders' in personality:
                    # Extract domain from sender email
                    sender_domain = sender.split('@')[-1].lower() if '@' in sender else sender.lower()
                    disliked_domains = personality.get('disliked_senders', [])
                    if any(domain.lower() in sender_domain for domain in disliked_domains):
                        logger.info(f"Skipping task from {sender} - sender domain in user's disliked list")
                        return []
            
            # ENHANCED SPAM/NEWSLETTER DETECTION - exclude these immediately
            spam_indicators = [
                # Unsubscribe and list management
                'unsubscribe', 'click here to unsubscribe', 'update your preferences', 
                'manage subscriptions', 'email preferences', 'opt out', 'remove me',
                
                # Marketing language
                'buy now', 'limited time', 'offer expires', 'act now', 'order now', 
                'shop now', 'don\'t miss', 'last chance', 'hurry', 'expires soon',
                
                # Sales and promotions
                'newsletter', 'promo', 'promotional', 'discount', 'sale', 'save up to', 
                '%off', 'percent off', 'free shipping', 'special offer', 'exclusive offer',
                'deal of the day', 'flash sale', 'clearance', 'save now', 'limited offer',
                
                # Email marketing patterns
                'view in browser', 'view online', 'see full message', 'read online',
                'subscribe now', 'join our', 'follow us', 'download now', 'get started',
                
                # Marketing sender patterns
                'noreply@', 'no-reply@', 'donotreply@', 'marketing@', 'news@', 
                'newsletter@', 'notifications@', 'updates@', 'info@', 'hello@',
                'support@' + ' (automated)', 'team@' + ' (bulk)',
                
                # Content patterns
                'this email was sent to', 'you received this email', 'sent to you by',
                'if you no longer wish', 'add us to your address book', 'whitelist',
                
                # Call-to-action spam
                'click to view', 'tap to open', 'open in app', 'get the app',
                'download our app', 'join thousands', 'millions of users'
            ]
            
            # Additional patterns to check in sender
            spam_sender_patterns = [
                'newsletter', 'marketing', 'promo', 'news', 'notifications',
                'noreply', 'no-reply', 'donotreply', 'updates', 'alerts'
            ]
            
            # Check for spam indicators in text
            spam_score = sum(1 for indicator in spam_indicators if indicator in combined_text)
            
            # Check sender email for spam patterns
            sender_spam_score = sum(1 for pattern in spam_sender_patterns if pattern in sender.lower())
            
            # Combined spam detection with lower threshold
            total_spam_score = spam_score + (sender_spam_score * 2)  # Weight sender patterns more heavily
            
            if spam_score >= 3 or sender_spam_score >= 2 or total_spam_score >= 4:
                logger.info(f"Skipping email from {sender} - detected as newsletter/marketing (text:{spam_score}, sender:{sender_spam_score})")
                return []
            
            # Additional check: If subject looks like marketing
            marketing_subject_patterns = [
                r'\d+%\s*off', r'save\s*\$\d+', r'free\s*shipping', r'limited\s*time',
                r'exclusive\s*offer', r'special\s*deal', r'flash\s*sale', r'new\s*arrival',
                r'weekly\s*update', r'monthly\s*newsletter', r'\[.*\s*sale.*\]'
            ]
            
            subject_lower = subject.lower()
            if any(re.search(pattern, subject_lower) for pattern in marketing_subject_patterns):
                logger.info(f"Skipping email - marketing subject pattern detected: {subject}")
                return []
            
            # AUTOMATED EMAIL DETECTION - skip automated notifications
            automated_indicators = [
                'this is an automated', 'do not reply', 'automated notification',
                'system notification', 'auto-generated', 'automated message'
            ]
            if any(indicator in combined_text for indicator in automated_indicators):
                logger.info(f"Skipping automated email from {sender}")
                return []
            
            # STRICT ACTION-REQUIRED KEYWORDS - must have at least ONE of these
            strong_action_keywords = [
                'action required', 'action needed', 'requires action',
                'please review', 'needs approval', 'approve', 'approval needed',
                'decision needed', 'your input', 'awaiting your',
                'deadline', 'due by', 'due date', 'complete by',
                'meeting request', 'schedule a', 'confirm your',
                'rsvp', 'respond by', 'reply needed', 'response required'
            ]
            
            has_strong_action = any(kw in combined_text for kw in strong_action_keywords)
            
            # DIRECT PERSONAL REQUEST - addressed to you specifically
            personal_requests = [
                'can you', 'could you', 'would you', 'will you',
                'please send', 'please provide', 'please update',
                'need your', 'need you to', 'waiting for you',
                'i need', 'we need', 'could you please'
            ]
            
            has_personal_request = any(kw in combined_text for kw in personal_requests)
            
            # QUESTIONS THAT NEED ANSWERS
            has_direct_question = bool(re.search(r'[?]\s*(?:what|when|where|who|why|how|can|could|would|should)', combined_text))
            
            # MUCH STRICTER: Require BOTH strong action AND personal request/question
            # OR explicit deadline with personal request
            create_task = False
            if has_strong_action and (has_personal_request or has_direct_question):
                create_task = True
            elif 'deadline' in combined_text and has_personal_request:
                create_task = True
            
            if create_task:
                # Extract potential deadline information
                deadline_patterns = [
                    r'by\s+(\w+day|\d{1,2}[/-]\d{1,2}[/-]?\d{0,4})',
                    r'due\s+(\w+day|\d{1,2}[/-]\d{1,2}[/-]?\d{0,4})',
                    r'deadline\s+(\w+day|\d{1,2}[/-]\d{1,2}[/-]?\d{0,4})',
                    r'before\s+(\w+day|\d{1,2}[/-]\d{1,2}[/-]?\d{0,4})'
                ]
                
                deadline = None
                for pattern in deadline_patterns:
                    match = re.search(pattern, combined_text, re.IGNORECASE)
                    if match:
                        deadline = match.group(1)
                        break
                
                # Determine priority based on keywords and urgency
                priority = 'medium'  # default
                if any(urgent_word in combined_text for urgent_word in ['urgent', 'asap', 'immediately', 'critical', 'high priority']):
                    priority = 'high'
                elif any(low_word in combined_text for low_word in ['whenever', 'no rush', 'low priority', 'when you can']):
                    priority = 'low'
                
                # Determine category
                category = 'email'
                if 'meeting' in combined_text or 'calendar' in combined_text:
                    category = 'meeting'
                elif any(work_word in combined_text for work_word in ['project', 'deliverable', 'report', 'document']):
                    category = 'work'
                
                # Check if it requires a response
                requires_response = any(resp_word in combined_text for resp_word in [
                    'reply', 'respond', 'let me know', 'thoughts', 'feedback', 'what do you think',
                    'response required', 'please confirm'
                ])
                
                # Create todo item with clear indication of why it was created
                reason = []
                if has_strong_action:
                    reason.append('action required')
                if has_personal_request:
                    reason.append('personal request')
                if has_direct_question:
                    reason.append('needs answer')
                
                # Create todo item
                todo_item = {
                    'task': f"Follow up: {subject[:50]}..." if len(subject) > 50 else f"Follow up: {subject}",
                    'priority': priority,
                    'deadline': deadline,
                    'category': category,
                    'requires_response': requires_response,
                    'reason': ', '.join(reason),
                    'sender': sender
                }
                
                todos.append(todo_item)
                logger.info(f"Created todo for email from {sender}: {reason}")
            else:
                logger.debug(f"Skipping email from {sender} - insufficient action signals (strong_action={has_strong_action}, personal={has_personal_request}, question={has_direct_question})")
            
            return todos
            
        except Exception as e:
            logger.error(f"Error analyzing email for todos: {e}")
            return []
