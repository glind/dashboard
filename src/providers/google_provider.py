"""
Google Provider - supports Gmail, Google Calendar, and Google Drive (notes).
Wraps existing Google collectors with the provider interface.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from .base import BaseProvider, ProviderCapability

logger = logging.getLogger(__name__)

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    logger.warning("Google API libraries not available")


class GoogleProvider(BaseProvider):
    """Google provider implementation."""
    
    def __init__(self, provider_id: str, settings: Any, db_manager: Any):
        """Initialize Google provider."""
        super().__init__(provider_id, settings, db_manager)
        self.gmail_service = None
        self.calendar_service = None
        self.drive_service = None
        self.credentials = None
    
    @property
    def provider_name(self) -> str:
        return "google"
    
    @property
    def capabilities(self) -> List[ProviderCapability]:
        return [
            ProviderCapability.EMAIL,
            ProviderCapability.CALENDAR,
            ProviderCapability.NOTES
        ]
    
    async def authenticate(self) -> bool:
        """Authenticate with Google using OAuth2."""
        if not GOOGLE_AVAILABLE:
            logger.error("Google API libraries not installed")
            return False
        
        try:
            creds = None
            project_root = Path(__file__).parent.parent.parent
            
            # Try to load existing credentials
            token_paths = [
                project_root / "tokens" / "google_credentials.json",
                project_root / "tokens" / f"google_{self.provider_id}.json"
            ]
            
            for token_file in token_paths:
                if token_file.exists():
                    try:
                        scopes = [
                            'https://www.googleapis.com/auth/gmail.readonly',
                            'https://www.googleapis.com/auth/calendar.readonly',
                            'https://www.googleapis.com/auth/drive.readonly'
                        ]
                        
                        creds = Credentials.from_authorized_user_file(str(token_file), scopes)
                        logger.info(f"Loaded Google credentials from {token_file}")
                        break
                    except Exception as e:
                        logger.warning(f"Could not load credentials from {token_file}: {e}")
                        continue
            
            if not creds:
                logger.warning("No Google credentials found")
                return False
            
            # Refresh if expired
            if creds.expired and creds.refresh_token:
                try:
                    creds.refresh(Request())
                    logger.info("Refreshed expired Google credentials")
                    
                    # Save refreshed credentials
                    if token_file.exists():
                        with open(token_file, 'w') as f:
                            f.write(creds.to_json())
                except Exception as e:
                    logger.error(f"Failed to refresh credentials: {e}")
                    return False
            
            if not creds.valid:
                logger.error("Google credentials are not valid")
                return False
            
            # Build services
            self.credentials = creds
            self.gmail_service = build('gmail', 'v1', credentials=creds)
            self.calendar_service = build('calendar', 'v3', credentials=creds)
            self.drive_service = build('drive', 'v3', credentials=creds)
            
            logger.info(f"✅ Google provider {self.provider_id} authenticated")
            return True
            
        except Exception as e:
            logger.error(f"Error authenticating Google provider: {e}")
            return False
    
    async def is_authenticated(self) -> bool:
        """Check if authenticated."""
        if not self.credentials:
            # Try to authenticate
            return await self.authenticate()
        return self.credentials.valid
    
    async def get_auth_url(self) -> Optional[str]:
        """Get OAuth URL for authentication."""
        # This should be handled by the OAuth flow endpoints
        # Return None as we use the existing OAuth flow
        return None
    
    async def handle_callback(self, code: str, state: str) -> bool:
        """Handle OAuth callback."""
        # OAuth callback is handled by existing endpoints
        # After callback completes, credentials will be saved
        return await self.authenticate()
    
    async def collect_emails(
        self,
        start_date: datetime,
        end_date: datetime,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Collect emails from Gmail."""
        if not await self.is_authenticated():
            logger.error("Not authenticated with Google")
            return []
        
        try:
            # Format dates for Gmail query
            start_query = start_date.strftime('%Y/%m/%d')
            end_query = end_date.strftime('%Y/%m/%d')
            
            # Build Gmail query
            query = f'after:{start_query} before:{end_query}'
            
            # Get message list
            result = self.gmail_service.users().messages().list(
                userId='me',
                q=query,
                maxResults=max_results
            ).execute()
            
            messages = result.get('messages', [])
            emails = []
            
            for message in messages:
                try:
                    email_data = await self._get_email_details(message['id'])
                    if email_data:
                        normalized = self._normalize_email(email_data)
                        emails.append(normalized)
                except Exception as e:
                    logger.error(f"Error processing email {message['id']}: {e}")
                    continue
            
            logger.info(f"Collected {len(emails)} emails from Google")
            return emails
            
        except Exception as e:
            logger.error(f"Error collecting emails from Google: {e}")
            return []
    
    async def get_email_details(self, email_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a specific email."""
        if not await self.is_authenticated():
            return None
        
        try:
            email_data = await self._get_email_details(email_id)
            if email_data:
                return self._normalize_email(email_data)
            return None
        except Exception as e:
            logger.error(f"Error getting email details: {e}")
            return None
    
    async def _get_email_details(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information for a Gmail message."""
        try:
            message = self.gmail_service.users().messages().get(
                userId='me',
                id=message_id,
                format='full'
            ).execute()
            
            headers = message['payload'].get('headers', [])
            timestamp = datetime.fromtimestamp(int(message['internalDate']) / 1000)
            
            # Extract headers
            subject = next((h['value'] for h in headers if h['name'].lower() == 'subject'), '')
            sender = next((h['value'] for h in headers if h['name'].lower() == 'from'), '')
            recipient = next((h['value'] for h in headers if h['name'].lower() == 'to'), '')
            
            # Extract body
            body = self._extract_body(message['payload'])
            
            # Check for attachments
            has_attachments = self._has_attachments(message['payload'])
            
            # Get labels
            labels = message.get('labelIds', [])
            is_unread = 'UNREAD' in labels
            is_important = 'IMPORTANT' in labels or 'STARRED' in labels
            
            return {
                'id': message_id,
                'subject': subject,
                'sender': sender,
                'recipient': recipient,
                'body': body,
                'snippet': message.get('snippet', ''),
                'received_date': timestamp.isoformat(),
                'read': not is_unread,
                'labels': labels,
                'has_attachments': has_attachments,
                'is_important': is_important
            }
            
        except Exception as e:
            logger.error(f"Error getting Gmail message details: {e}")
            return None
    
    def _extract_body(self, payload: Dict[str, Any]) -> str:
        """Extract email body from Gmail payload."""
        import base64
        
        body = ""
        if 'parts' in payload:
            for part in payload['parts']:
                if part['mimeType'] == 'text/plain':
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
                        break
                elif part['mimeType'] == 'text/html' and not body:
                    if 'data' in part['body']:
                        body = base64.urlsafe_b64decode(part['body']['data']).decode('utf-8', errors='ignore')
        elif 'body' in payload and 'data' in payload['body']:
            body = base64.urlsafe_b64decode(payload['body']['data']).decode('utf-8', errors='ignore')
        
        return body
    
    def _has_attachments(self, payload: Dict[str, Any]) -> bool:
        """Check if email has attachments."""
        if 'parts' in payload:
            for part in payload['parts']:
                if 'filename' in part and part['filename']:
                    return True
                if 'parts' in part:
                    if self._has_attachments(part):
                        return True
        return False
    
    async def collect_calendar_events(
        self,
        start_date: datetime,
        end_date: datetime,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Collect calendar events from Google Calendar."""
        if not await self.is_authenticated():
            logger.error("Not authenticated with Google")
            return []
        
        try:
            # Call the Calendar API
            events_result = self.calendar_service.events().list(
                calendarId='primary',
                timeMin=start_date.isoformat() + 'Z',
                timeMax=end_date.isoformat() + 'Z',
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            normalized_events = []
            
            for event in events:
                try:
                    # Handle all-day vs timed events
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    end = event['end'].get('dateTime', event['end'].get('date'))
                    all_day = 'date' in event['start']
                    
                    event_data = {
                        'id': event['id'],
                        'title': event.get('summary', 'Untitled Event'),
                        'description': event.get('description', ''),
                        'start_time': start,
                        'end_time': end,
                        'all_day': all_day,
                        'location': event.get('location', ''),
                        'attendees': [a.get('email', '') for a in event.get('attendees', [])],
                        'organizer': event.get('organizer', {}).get('email', '')
                    }
                    
                    normalized = self._normalize_calendar_event(event_data)
                    normalized_events.append(normalized)
                    
                except Exception as e:
                    logger.error(f"Error processing event {event.get('id')}: {e}")
                    continue
            
            logger.info(f"Collected {len(normalized_events)} events from Google Calendar")
            return normalized_events
            
        except Exception as e:
            logger.error(f"Error collecting calendar events from Google: {e}")
            return []
    
    async def collect_notes(
        self,
        folder_id: Optional[str] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Collect notes from Google Drive."""
        if not await self.is_authenticated():
            logger.error("Not authenticated with Google")
            return []
        
        try:
            # Query for Google Docs in specified folder or all folders
            query = "mimeType='application/vnd.google-apps.document'"
            if folder_id:
                query += f" and '{folder_id}' in parents"
            
            results = self.drive_service.files().list(
                q=query,
                pageSize=max_results,
                fields="files(id, name, createdTime, modifiedTime, description)"
            ).execute()
            
            files = results.get('files', [])
            notes = []
            
            for file in files:
                try:
                    # Get document content
                    content = ""
                    try:
                        export_result = self.drive_service.files().export(
                            fileId=file['id'],
                            mimeType='text/plain'
                        ).execute()
                        content = export_result.decode('utf-8', errors='ignore')
                    except:
                        pass
                    
                    note_data = {
                        'id': file['id'],
                        'title': file.get('name', 'Untitled Document'),
                        'content': content,
                        'created_date': file.get('createdTime', ''),
                        'modified_date': file.get('modifiedTime', ''),
                        'tags': [],
                        'folder': folder_id or 'root'
                    }
                    
                    normalized = self._normalize_note(note_data)
                    notes.append(normalized)
                    
                except Exception as e:
                    logger.error(f"Error processing document {file.get('id')}: {e}")
                    continue
            
            logger.info(f"Collected {len(notes)} notes from Google Drive")
            return notes
            
        except Exception as e:
            logger.error(f"Error collecting notes from Google Drive: {e}")
            return []
