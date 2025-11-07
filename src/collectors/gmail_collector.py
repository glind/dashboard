"""
Gmail data collector using Google Gmail API.
"""

import os
import logging
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pathlib import Path
import base64
import email
from email.mime.text import MIMEText
import sys

# Add parent directory to path for processor imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from processors.email_risk_checker import EmailRiskChecker

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

# Import database functions
try:
    from database import DatabaseManager
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

logger = logging.getLogger(__name__)


class GmailCollector:
    """Collects emails from Gmail using Google API."""
    
    def __init__(self, settings):
        """Initialize Gmail collector with settings."""
        self.settings = settings
        self.service = None
        
    async def collect_emails(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Collect emails from Gmail within the specified date range."""
        if not GOOGLE_AVAILABLE:
            logger.warning("Google API libraries not available. Install google-api-python-client.")
            return []
        
        try:
            await self._authenticate()
            
            if not self.service:
                logger.error("Authentication failed - no Gmail service available")
                return []
            
            # Format dates for Gmail query
            start_query = start_date.strftime('%Y/%m/%d')
            end_query = end_date.strftime('%Y/%m/%d')
            
            # Build Gmail query
            query = f'after:{start_query} before:{end_query}'
            
            # Get message list
            result = self.service.users().messages().list(
                userId='me',
                q=query,
                maxResults=500
            ).execute()
            
            messages = result.get('messages', [])
            
            emails = []
            for message in messages[:100]:  # Limit to 100 most recent
                email_data = await self._get_email_details(message['id'])
                if email_data:
                    emails.append(email_data)
            
            logger.info(f"Collected {len(emails)} emails from Gmail")
            return emails
            
        except Exception as e:
            logger.error(f"Error analyzing email for todos: {e}")
            return []
    
    async def collect_data(self) -> Dict[str, Any]:
        """Collect email data for the dashboard - simplified version that just gets 100 most recent emails."""
        try:
            logger.info("Collecting 100 most recent emails from Gmail")
            
            await self._authenticate()
            
            if not self.service:
                logger.error("Authentication failed - no Gmail service available")
                return {
                    "emails": [],
                    "total_count": 0,
                    "unread_count": 0,
                    "authenticated": False,
                    "error": "Authentication failed"
                }
            
            # Initialize risk checker
            risk_checker = EmailRiskChecker()
            
            # Get 100 most recent emails - no date filtering, no priority analysis
            # Just get them fresh every time
            result = self.service.users().messages().list(
                userId='me',
                maxResults=100
            ).execute()
            
            messages = result.get('messages', [])
            logger.info(f"Found {len(messages)} recent emails")
            
            formatted_emails = []
            for message in messages:
                try:
                    # Get full email details including labels
                    email_data = await self._get_email_details(message['id'])
                    if not email_data:
                        continue
                    
                    # Check if email has UNREAD label
                    labels = email_data.get('labels', [])
                    is_unread = 'UNREAD' in labels
                    
                    # Analyze email for security/spam risk
                    risk_analysis = risk_checker.analyze_email(email_data)
                    
                    formatted_email = {
                        'id': email_data.get('id', ''),
                        'subject': email_data.get('subject', 'No Subject'),
                        'sender': email_data.get('sender', 'Unknown'),
                        'from': email_data.get('sender', 'Unknown'),
                        'recipient': email_data.get('recipient', ''),
                        'date': email_data.get('received_date', ''),
                        'received_date': email_data.get('received_date', ''),
                        'body': email_data.get('body', ''),
                        'snippet': email_data.get('snippet', ''),
                        'read': not is_unread,  # True if email does NOT have UNREAD label
                        'labels': labels,
                        'gmail_url': f"https://mail.google.com/mail/u/0/#inbox/{email_data.get('id', '')}",
                        'is_important': email_data.get('is_important', False),
                        'has_attachments': email_data.get('has_attachments', False),
                        # Risk scoring fields
                        'risk_score': risk_analysis.get('risk_score', 1),
                        'risk_level': risk_analysis.get('risk_level', 'safe'),
                        'risk_flags': risk_analysis.get('flags', []),
                        'should_create_task': risk_analysis.get('should_create_task', True),
                        'recommended_action': risk_analysis.get('recommended_action', 'none'),
                        'is_whitelisted': risk_analysis.get('is_whitelisted', False)
                    }
                    formatted_emails.append(formatted_email)
                    
                except Exception as e:
                    logger.error(f"Error processing email {message['id']}: {e}")
                    continue
            
            # Calculate unread count and risk statistics
            unread_count = sum(1 for email in formatted_emails if not email.get('read', True))
            high_risk_count = sum(1 for email in formatted_emails if email.get('risk_score', 0) >= 7)
            
            logger.info(f"Collected {len(formatted_emails)} emails, {unread_count} unread, {high_risk_count} high-risk")
            
            return {
                "emails": formatted_emails,
                "total_count": len(formatted_emails),
                "unread_count": unread_count,
                "high_risk_count": high_risk_count,
                "authenticated": True,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error collecting email data: {e}")
            return {
                "emails": [],
                "total_count": 0,
                "unread_count": 0,
                "authenticated": False,
                "error": str(e)
            }
    
    async def _authenticate(self):
        """Authenticate with Google Gmail API."""
        logger.info("Starting Google Gmail authentication")
        creds = None
        
        # Get project root (two levels up from collectors/)
        project_root = Path(__file__).parent.parent.parent
        
        # Try to load from the tokens file (our OAuth flow stores credentials here)
        # Check both absolute and relative paths
        token_paths = [
            project_root / "tokens" / "google_credentials.json",
            Path(os.path.expanduser('~/Projects/me/dashboard/tokens/google_credentials.json')),
            Path(self.settings.google.credentials_file) if hasattr(self.settings, 'google') and hasattr(self.settings.google, 'credentials_file') and self.settings.google.credentials_file else None
        ]
        
        for token_file in token_paths:
            if token_file and token_file.exists():
                try:
                    # Get scopes from settings or use default
                    scopes = None
                    if hasattr(self.settings, 'google') and hasattr(self.settings.google, 'scopes'):
                        scopes = self.settings.google.scopes
                    else:
                        # Default scopes for Gmail and Calendar
                        scopes = [
                            'https://www.googleapis.com/auth/gmail.readonly',
                            'https://www.googleapis.com/auth/calendar.readonly'
                        ]
                    
                    creds = Credentials.from_authorized_user_file(
                        token_file,
                        scopes
                    )
                    logger.info(f"Loaded credentials from {token_file}")
                    break
                except Exception as e:
                    logger.warning(f"Could not load credentials from {token_file}: {e}")
                    continue
        
        if not creds:
            logger.error("No Google credentials file found")
            return
        
        # If credentials are expired, try to refresh
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
                logger.info("Refreshed expired credentials")
            except Exception as e:
                logger.error(f"Failed to refresh credentials: {e}")
                creds = None
        
        if not creds or not creds.valid:
            logger.error("No valid Google credentials available. Please authenticate via the web interface.")
            return
        
        self.service = build('gmail', 'v1', credentials=creds)
        logger.info("Successfully authenticated with Google Gmail API")
    
    async def _get_email_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific email."""
        try:
            message = self.service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            headers = message['payload'].get('headers', [])
            
            # Extract timestamp first
            timestamp = datetime.fromtimestamp(int(message['internalDate']) / 1000)
            
            # Extract key information
            email_data = {
                'id': message_id,
                'thread_id': message.get('threadId'),
                'snippet': message.get('snippet', ''),
                'timestamp': timestamp,
                'received_date': timestamp.isoformat(),  # Add ISO format string for API
                'labels': message.get('labelIds', []),
                'subject': '',
                'sender': '',
                'recipient': '',
                'body': '',
                'has_attachments': False,
                'importance': 'normal'
            }
            
            # Parse headers
            for header in headers:
                name = header['name'].lower()
                value = header['value']
                
                if name == 'subject':
                    email_data['subject'] = value
                elif name == 'from':
                    email_data['sender'] = value
                elif name == 'to':
                    email_data['recipient'] = value
                elif name == 'importance':
                    email_data['importance'] = value.lower()
            
            # Extract body
            email_data['body'] = self._extract_body(message['payload'])
            
            # Check for attachments
            email_data['has_attachments'] = self._has_attachments(message['payload'])
            
            # Determine if email is important based on various factors
            email_data['is_important'] = self._is_important_email(email_data)
            
            return email_data
            
        except Exception as e:
            logger.error(f"Error getting email details for {message_id}: {e}")
            return None
    
    def _extract_body(self, payload: Dict[str, Any]) -> str:
        """Extract email body from payload."""
        body = ''
        
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    data = part['body'].get('data')
                    if data:
                        body = base64.urlsafe_b64decode(data).decode('utf-8')
                        break
        elif payload['mimeType'] == 'text/plain':
            data = payload['body'].get('data')
            if data:
                body = base64.urlsafe_b64decode(data).decode('utf-8')
        
        return body[:1000]  # Limit body length
    
    def _has_attachments(self, payload: Dict[str, Any]) -> bool:
        """Check if email has attachments."""
        if 'parts' in payload:
            for part in payload['parts']:
                if part.get('filename'):
                    return True
        return False
    
    def _is_important_email(self, email_data: Dict[str, Any]) -> bool:
        """Determine if email is important based on content and metadata."""
        # Check labels for importance
        important_labels = ['IMPORTANT', 'STARRED']
        if any(label in email_data['labels'] for label in important_labels):
            return True
        
        # Check subject for important keywords
        subject = email_data['subject'].lower()
        important_keywords = [
            'urgent', 'asap', 'important', 'critical', 'deadline',
            'meeting', 'follow up', 'action required', 'response needed'
        ]
        
        if any(keyword in subject for keyword in important_keywords):
            return True
        
        # Check if from important domains/people
        sender = email_data['sender'].lower()
        important_domains = ['@company.com', '@client.com']  # Configure as needed
        
        if any(domain in sender for domain in important_domains):
            return True
        
        return False

    async def get_email_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get email summary statistics for the last specified number of days."""
        try:
            await self._authenticate()
            
            if not self.service:
                logger.error("Authentication failed - no Gmail service available")
                return {
                    "total_emails": 0,
                    "unread_emails": 0,
                    "important_emails": 0,
                    "error": "Authentication failed"
                }
            
            # Get inbox summary
            profile = self.service.users().getProfile(userId='me').execute()
            
            # Get unread messages count
            unread_results = self.service.users().messages().list(
                userId='me',
                q='is:unread',
                maxResults=500
            ).execute()
            unread_count = len(unread_results.get('messages', []))
            
            # Get important/starred messages
            important_results = self.service.users().messages().list(
                userId='me',
                q='is:starred OR is:important',
                maxResults=100
            ).execute()
            important_count = len(important_results.get('messages', []))
            
            # Get recent messages (last 7 days)
            recent_results = self.service.users().messages().list(
                userId='me',
                q='newer_than:7d',
                maxResults=500
            ).execute()
            recent_count = len(recent_results.get('messages', []))
            
            logger.info(f"Gmail summary: {recent_count} recent, {unread_count} unread, {important_count} important")
            
            return {
                "total_emails": profile.get('messagesTotal', 0),
                "unread_emails": unread_count,
                "important_emails": important_count,
                "recent_emails": recent_count,
                "email_address": profile.get('emailAddress', 'Unknown')
            }
            
        except Exception as e:
            logger.error(f"Error getting Gmail summary: {e}")
            return {
                "total_emails": 0,
                "unread_emails": 0,
                "important_emails": 0,
                "recent_emails": 0,
                "error": str(e)
            }

    async def analyze_six_months_for_todos_and_followups(self) -> Dict[str, Any]:
        """
        Analyze last 6 months of emails to find todos and emails requiring follow-up/replies.
        Returns analysis results with potential tasks for TickTick integration.
        """
        try:
            from database import DatabaseManager
            from processors.email_analyzer import EmailAnalyzer
            
            # Calculate date range (6 months back)
            end_date = datetime.now()
            start_date = end_date - timedelta(days=180)  # 6 months
            
            logger.info(f"Analyzing 6 months of emails from {start_date.date()} to {end_date.date()}")
            
            # Initialize components
            db_manager = DatabaseManager()
            email_analyzer = EmailAnalyzer()
            
            # Check if Ollama is connected
            ollama_connected = await email_analyzer.test_connection()
            if not ollama_connected:
                logger.warning("Ollama not available - using basic keyword analysis")
            
            # Collect emails from the 6-month period
            emails = await self.collect_emails(start_date, end_date)
            
            analysis_results = {
                'total_emails_analyzed': len(emails),
                'period': f"{start_date.date()} to {end_date.date()}",
                'potential_todos': [],
                'unreplied_emails': [],
                'follow_up_required': [],
                'analysis_stats': {
                    'todo_keywords_found': 0,
                    'unreplied_count': 0,
                    'follow_up_count': 0,
                    'ollama_analyzed': 0
                }
            }
            
            # Keywords that suggest todos or action items
            todo_keywords = [
                'todo', 'to do', 'action item', 'task', 'follow up', 'follow-up',
                'deadline', 'due date', 'complete by', 'finish by', 'need to',
                'should', 'must', 'required', 'action required', 'please',
                'can you', 'could you', 'would you', 'reminder', 'urgent'
            ]
            
            # Keywords that suggest emails need replies
            reply_keywords = [
                'please respond', 'let me know', 'waiting for', 'need response',
                'please confirm', 'please reply', 'thoughts?', 'feedback',
                'what do you think', 'your opinion', 'decision needed'
            ]
            
            for email_data in emails:
                try:
                    email_id = email_data.get('id', '')
                    subject = email_data.get('subject', '').lower()
                    body = email_data.get('body', '').lower()
                    sender = email_data.get('sender', '')
                    received_date = email_data.get('received_date')
                    
                    combined_text = f"{subject} {body}"
                    
                    # Check for todo keywords
                    found_todo_keywords = [kw for kw in todo_keywords if kw in combined_text]
                    if found_todo_keywords:
                        analysis_results['analysis_stats']['todo_keywords_found'] += 1
                        
                        # Create Gmail link
                        gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{email_id}"
                        
                        todo_item = {
                            'email_id': email_id,
                            'subject': email_data.get('subject', ''),
                            'sender': sender,
                            'received_date': received_date,
                            'keywords_found': found_todo_keywords,
                            'gmail_link': gmail_link,
                            'priority': 'medium',
                            'suggested_title': f"Follow up: {email_data.get('subject', '')[:50]}...",
                            'suggested_content': f"Email from {sender}\nKeywords: {', '.join(found_todo_keywords)}\n\nOriginal subject: {email_data.get('subject', '')}"
                        }
                        
                        # Use Ollama for better analysis if available
                        if ollama_connected:
                            try:
                                ollama_analysis = await email_analyzer.analyze_email_for_todos(
                                    email_data.get('subject', ''),
                                    email_data.get('body', ''),
                                    sender
                                )
                                if ollama_analysis:
                                    analysis_results['analysis_stats']['ollama_analyzed'] += 1
                                    # Use first todo from Ollama analysis
                                    first_todo = ollama_analysis[0]
                                    todo_item.update({
                                        'priority': first_todo.get('priority', 'medium'),
                                        'suggested_title': first_todo.get('task', todo_item['suggested_title']),
                                        'due_date': first_todo.get('deadline'),
                                        'ollama_analyzed': True
                                    })
                            except Exception as e:
                                logger.error(f"Ollama analysis failed for email {email_id}: {e}")
                        
                        analysis_results['potential_todos'].append(todo_item)
                    
                    # Check for emails that might need replies
                    found_reply_keywords = [kw for kw in reply_keywords if kw in combined_text]
                    
                    # Also check if it's been a while since the email was received (>7 days)
                    if received_date:
                        try:
                            email_datetime = datetime.fromisoformat(received_date.replace('Z', '+00:00'))
                            days_since = (datetime.now(email_datetime.tzinfo) - email_datetime).days
                        except:
                            days_since = 0
                    else:
                        days_since = 0
                    
                    if found_reply_keywords or days_since > 7:
                        analysis_results['analysis_stats']['unreplied_count'] += 1
                        
                        gmail_link = f"https://mail.google.com/mail/u/0/#inbox/{email_id}"
                        
                        unreplied_item = {
                            'email_id': email_id,
                            'subject': email_data.get('subject', ''),
                            'sender': sender,
                            'received_date': received_date,
                            'days_since_received': days_since,
                            'reply_keywords_found': found_reply_keywords,
                            'gmail_link': gmail_link,
                            'suggested_title': f"Reply to: {email_data.get('subject', '')[:50]}...",
                            'suggested_content': f"Reply needed for email from {sender}\nReceived: {received_date}\nDays ago: {days_since}"
                        }
                        
                        if days_since > 14:
                            unreplied_item['priority'] = 'high'
                        elif days_since > 7 or found_reply_keywords:
                            unreplied_item['priority'] = 'medium'
                        else:
                            unreplied_item['priority'] = 'low'
                        
                        analysis_results['unreplied_emails'].append(unreplied_item)
                    
                except Exception as e:
                    logger.error(f"Error analyzing email {email_id}: {e}")
                    continue
            
            # Sort results by priority and date
            analysis_results['potential_todos'].sort(
                key=lambda x: (
                    {'high': 0, 'medium': 1, 'low': 2}.get(x.get('priority', 'low'), 2),
                    x.get('received_date', '')
                ),
                reverse=True
            )
            
            analysis_results['unreplied_emails'].sort(
                key=lambda x: (
                    {'high': 0, 'medium': 1, 'low': 2}.get(x.get('priority', 'low'), 2),
                    -x.get('days_since_received', 0)
                )
            )
            
            logger.info(f"6-month email analysis complete: {len(analysis_results['potential_todos'])} potential todos, "
                       f"{len(analysis_results['unreplied_emails'])} unreplied emails")
            
            return analysis_results
            
        except Exception as e:
            logger.error(f"Error in 6-month email analysis: {e}")
            return {
                'total_emails_analyzed': 0,
                'period': 'Error',
                'potential_todos': [],
                'unreplied_emails': [],
                'follow_up_required': [],
                'analysis_stats': {'error': str(e)}
            }

    async def collect_and_analyze_emails(self, days_back: int = 14) -> Dict[str, Any]:
        """
        Collect and analyze recent emails for todos and priority.
        Returns analyzed emails with priority classification and extracted todos.
        """
        logger.info(f"Starting email collection and analysis for last {days_back} days...")
        
        try:
            # Initialize components
            db_manager = DatabaseManager()
            
            # Import email analyzer
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from processors.email_analyzer import EmailAnalyzer
            
            email_analyzer = EmailAnalyzer()
            
            # Test Ollama connection
            ollama_connected = await email_analyzer.test_connection()
            if not ollama_connected:
                logger.warning("Ollama not connected - emails will be collected but not analyzed")
            
            # Get recent emails
            start_date = datetime.now() - timedelta(days=days_back)
            end_date = datetime.now()
            
            emails = await self.collect_emails(start_date, end_date)
            
            analyzed_emails = {
                'high_priority': [],
                'medium_priority': [],
                'low_priority': [],
                'total_todos': [],
                'analysis_stats': {
                    'total_emails': len(emails),
                    'analyzed_count': 0,
                    'ollama_connected': ollama_connected,
                    'todos_extracted': 0
                }
            }
            
            # Process each email
            for email_data in emails[:100]:  # Limit to 100 most recent (increased from 50)
                try:
                    # Generate unique email ID
                    email_id = hashlib.md5(
                        f"{email_data.get('sender', '')}{email_data.get('subject', '')}{email_data.get('received_date', '')}".encode()
                    ).hexdigest()
                    
                    email_data['id'] = email_id
                    
                    # Determine initial priority based on email characteristics
                    initial_priority = self._determine_email_priority(email_data)
                    email_data['priority'] = initial_priority
                    
                    # Analyze with both Ollama and keyword detection
                    ollama_priority = None
                    todos = []
                    
                    # Always do keyword-based todo detection first
                    keyword_todos = self._extract_keyword_based_todos(email_data)
                    todos.extend(keyword_todos)
                    
                    if ollama_connected:
                        # Extract additional todos using Ollama
                        ollama_todos = await email_analyzer.analyze_email_for_todos(
                            email_data.get('subject', ''),
                            email_data.get('body', ''),
                            email_data.get('sender', '')
                        )
                        
                        # Merge Ollama todos with keyword todos (avoid duplicates)
                        existing_todo_texts = [todo.get('task', '').lower() for todo in todos]
                        for ollama_todo in ollama_todos:
                            todo_text = ollama_todo.get('task', '').lower()
                            if todo_text not in existing_todo_texts:
                                todos.append(ollama_todo)
                        
                        # Determine Ollama priority based on email content
                        if todos:
                            # If todos found, increase priority
                            if any(todo.get('priority') == 'high' for todo in todos):
                                ollama_priority = 'high'
                            elif any(todo.get('priority') == 'medium' for todo in todos):
                                ollama_priority = 'medium'
                            else:
                                ollama_priority = 'low'
                        else:
                            ollama_priority = initial_priority
                        
                        analyzed_emails['analysis_stats']['analyzed_count'] += 1
                    else:
                        # If Ollama not available, use initial priority but boost if todos found
                        if todos:
                            ollama_priority = 'medium'  # Boost priority if keyword todos found
                        else:
                            ollama_priority = initial_priority
                    
                    # Save email to database
                    email_db_data = {
                        'id': email_id,
                        'subject': email_data.get('subject', ''),
                        'sender': email_data.get('sender', ''),
                        'recipient': email_data.get('recipient', ''),
                        'body': email_data.get('body', '')[:5000],  # Limit body size
                        'received_date': email_data.get('received_date'),
                        'priority': initial_priority,
                        'is_analyzed': ollama_connected,
                        'ollama_priority': ollama_priority,
                        'has_todos': len(todos) > 0
                    }
                    
                    db_manager.save_email(email_db_data)
                    
                    # Save todos to database (only if they don't already exist)
                    for todo in todos:
                        todo_id = hashlib.md5(
                            f"{email_id}{todo.get('task', '')}{todo.get('deadline', '')}".encode()
                        ).hexdigest()
                        
                        # Check if this todo already exists
                        existing_todos = db_manager.get_todos_by_source('email', None)
                        existing_todo = next((t for t in existing_todos if t['id'] == todo_id), None)
                        
                        if existing_todo:
                            # Todo already exists - don't recreate it
                            # But add it to our analysis results if it's not deleted
                            if existing_todo['status'] != 'deleted':
                                analyzed_emails['total_todos'].append(existing_todo)
                            continue
                        
                        # Create new todo only if it doesn't exist
                        todo_db_data = {
                            'id': todo_id,
                            'title': todo.get('task', ''),
                            'description': todo.get('task', ''),
                            'due_date': todo.get('deadline'),
                            'priority': todo.get('priority', 'medium'),
                            'category': todo.get('category', 'email'),
                            'source': 'email',
                            'source_id': email_id,
                            'status': 'pending',
                            'requires_response': todo.get('requires_response', False),
                            'email_id': email_id
                        }
                        
                        db_manager.save_todo(todo_db_data)
                        analyzed_emails['total_todos'].append(todo_db_data)
                    
                    # Categorize by final priority (use Ollama priority if available)
                    final_priority = ollama_priority or initial_priority
                    email_data['final_priority'] = final_priority
                    email_data['todos'] = todos
                    
                    if final_priority == 'high':
                        analyzed_emails['high_priority'].append(email_data)
                    elif final_priority == 'medium':
                        analyzed_emails['medium_priority'].append(email_data)
                    else:
                        analyzed_emails['low_priority'].append(email_data)
                    
                except Exception as e:
                    logger.error(f"Error processing email: {e}")
                    continue
            
            # Update stats
            analyzed_emails['analysis_stats']['todos_extracted'] = len(analyzed_emails['total_todos'])
            
            logger.info(f"Email analysis complete: {analyzed_emails['analysis_stats']['analyzed_count']} emails analyzed, "
                       f"{len(analyzed_emails['high_priority'])} high priority, "
                       f"{len(analyzed_emails['medium_priority'])} medium priority, "
                       f"{len(analyzed_emails['low_priority'])} low priority, "
                       f"{analyzed_emails['analysis_stats']['todos_extracted']} todos extracted")
            
            return analyzed_emails
            
        except Exception as e:
            logger.error(f"Error in email collection and analysis: {e}")
            return {
                'high_priority': [],
                'medium_priority': [],
                'low_priority': [],
                'total_todos': [],
                'analysis_stats': {
                    'total_emails': 0,
                    'analyzed_count': 0,
                    'ollama_connected': False,
                    'todos_extracted': 0
                },
                'error': str(e)
            }
    
    def _determine_email_priority(self, email_data: Dict[str, Any]) -> str:
        """Determine initial email priority based on characteristics."""
        subject = email_data.get('subject', '').lower()
        sender = email_data.get('sender', '').lower()
        
        # High priority indicators
        high_priority_keywords = [
            'urgent', 'asap', 'immediate', 'critical', 'important',
            'deadline', 'meeting', 'call', 'response required',
            'action required', 'follow up', 'reminder'
        ]
        
        # VIP senders (you can customize this)
        vip_domains = ['buildlylabs.com', 'important-client.com']
        
        # Check for high priority
        if any(keyword in subject for keyword in high_priority_keywords):
            return 'high'
        
        if any(domain in sender for domain in vip_domains):
            return 'high'
        
        # Medium priority indicators
        medium_priority_keywords = [
            'review', 'feedback', 'update', 'information',
            'question', 'discuss', 'schedule'
        ]
        
        if any(keyword in subject for keyword in medium_priority_keywords):
            return 'medium'
        
        # Default to low priority
        return 'low'
    
    def _extract_keyword_based_todos(self, email_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract potential todos using keyword-based analysis."""
        todos = []
        
        try:
            subject = email_data.get('subject', '').lower()
            body = email_data.get('body', '').lower()
            sender = email_data.get('sender', '')
            
            # Todo keywords that suggest action items
            todo_keywords = [
                'todo', 'to do', 'action item', 'task', 'follow up', 'follow-up',
                'deadline', 'due date', 'complete by', 'finish by', 'need to',
                'should', 'must', 'required', 'action required', 'please',
                'can you', 'could you', 'would you', 'reminder', 'urgent',
                'review', 'approve', 'sign', 'submit', 'send', 'update',
                'schedule', 'meeting', 'call', 'respond', 'reply'
            ]
            
            # Check if any todo keywords are present
            found_keywords = []
            for keyword in todo_keywords:
                if keyword in subject or keyword in body:
                    found_keywords.append(keyword)
            
            if found_keywords:
                # Extract potential todo text from subject or body
                todo_text = email_data.get('subject', 'Email requires action')
                
                # Determine priority based on urgency keywords
                priority = 'low'
                urgent_keywords = ['urgent', 'asap', 'immediately', 'deadline', 'due', 'required']
                high_keywords = ['important', 'critical', 'must', 'action required']
                
                text_to_check = subject + ' ' + body
                if any(keyword in text_to_check for keyword in urgent_keywords):
                    priority = 'high'
                elif any(keyword in text_to_check for keyword in high_keywords):
                    priority = 'medium'
                
                # Create todo item
                todo = {
                    'task': todo_text,
                    'description': f"Email from {sender}: {todo_text}",
                    'priority': priority,
                    'category': 'email',
                    'deadline': None,
                    'requires_response': any(keyword in text_to_check for keyword in [
                        'please respond', 'let me know', 'need response', 
                        'please confirm', 'please reply'
                    ]),
                    'keywords_found': found_keywords
                }
                
                todos.append(todo)
            
            return todos
            
        except Exception as e:
            logger.error(f"Error in keyword-based todo extraction: {e}")
            return []
