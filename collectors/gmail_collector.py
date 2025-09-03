"""
Gmail data collector using Google Gmail API.
"""

import os
import logging
import hashlib
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import base64
import email
from email.mime.text import MIMEText

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
            logger.error(f"Error collecting Gmail emails: {e}")
            return []
    
    async def _authenticate(self):
        """Authenticate with Google Gmail API."""
        logger.info("Starting Google Gmail authentication")
        creds = None
        
        # Try to load from the tokens file (our OAuth flow stores credentials here)
        # Check both absolute and relative paths
        token_paths = [
            '/home/glind/Projects/mine/dashboard/tokens/google_credentials.json',
            'tokens/google_credentials.json',
            self.settings.google.credentials_file if hasattr(self.settings, 'google') and hasattr(self.settings.google, 'credentials_file') else None
        ]
        
        for token_file in token_paths:
            if token_file and os.path.exists(token_file):
                try:
                    creds = Credentials.from_authorized_user_file(
                        token_file,
                        self.settings.google.scopes
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
            
            # Extract key information
            email_data = {
                'id': message_id,
                'thread_id': message.get('threadId'),
                'snippet': message.get('snippet', ''),
                'timestamp': datetime.fromtimestamp(int(message['internalDate']) / 1000),
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

    async def collect_data(self, days: int = 14) -> Dict[str, Any]:
        """
        Collect and analyze recent emails for todos and priority.
        Returns analyzed emails with priority classification and extracted todos.
        """
        logger.info(f"Starting email collection and analysis for last {days} days...")
        
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
            start_date = datetime.now() - timedelta(days=days)
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
            for email_data in emails[:50]:  # Limit to 50 most recent
                try:
                    # Generate unique email ID
                    email_id = hashlib.md5(
                        f"{email_data.get('sender', '')}{email_data.get('subject', '')}{email_data.get('received_date', '')}".encode()
                    ).hexdigest()
                    
                    email_data['id'] = email_id
                    
                    # Determine initial priority based on email characteristics
                    initial_priority = self._determine_email_priority(email_data)
                    email_data['priority'] = initial_priority
                    
                    # Analyze with Ollama if available
                    ollama_priority = None
                    todos = []
                    
                    if ollama_connected:
                        # Extract todos using Ollama
                        todos = await email_analyzer.analyze_email_for_todos(
                            email_data.get('subject', ''),
                            email_data.get('body', ''),
                            email_data.get('sender', '')
                        )
                        
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
                    
                    # Save todos to database
                    for todo in todos:
                        todo_id = hashlib.md5(
                            f"{email_id}{todo.get('task', '')}{todo.get('deadline', '')}".encode()
                        ).hexdigest()
                        
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
