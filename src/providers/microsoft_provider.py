"""
Microsoft Office 365 Provider - supports Outlook, Office 365 Calendar, and OneNote.
Implements Microsoft Graph API integration.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import requests

from .base import BaseProvider, ProviderCapability

logger = logging.getLogger(__name__)


class MicrosoftProvider(BaseProvider):
    """Microsoft Office 365 provider implementation using Graph API."""
    
    # Microsoft Graph API endpoints
    GRAPH_API_ENDPOINT = "https://graph.microsoft.com/v1.0"
    AUTH_ENDPOINT = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
    TOKEN_ENDPOINT = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
    
    # Required scopes
    SCOPES = [
        "https://graph.microsoft.com/Mail.Read",
        "https://graph.microsoft.com/Calendars.Read",
        "https://graph.microsoft.com/Notes.Read",
        "offline_access"  # For refresh tokens
    ]
    
    def __init__(self, provider_id: str, settings: Any, db_manager: Any):
        """Initialize Microsoft provider."""
        super().__init__(provider_id, settings, db_manager)
        self.access_token = None
        self.refresh_token = None
        self.token_expires_at = None
        
        # Get Microsoft OAuth config from settings
        self.client_id = getattr(settings, 'microsoft_client_id', None)
        self.client_secret = getattr(settings, 'microsoft_client_secret', None)
        self.redirect_uri = getattr(settings, 'microsoft_redirect_uri', 'http://localhost:8008/auth/microsoft/callback')
    
    @property
    def provider_name(self) -> str:
        return "microsoft"
    
    @property
    def capabilities(self) -> List[ProviderCapability]:
        return [
            ProviderCapability.EMAIL,
            ProviderCapability.CALENDAR,
            ProviderCapability.NOTES
        ]
    
    async def authenticate(self) -> bool:
        """Authenticate with Microsoft using stored tokens."""
        try:
            # Try to load tokens from database
            tokens = await self._load_tokens()
            if not tokens:
                logger.warning("No Microsoft tokens found")
                return False
            
            self.access_token = tokens.get('access_token')
            self.refresh_token = tokens.get('refresh_token')
            self.token_expires_at = tokens.get('expires_at')
            
            # Check if token is expired
            if self.token_expires_at:
                from datetime import datetime
                expires_at = datetime.fromisoformat(self.token_expires_at)
                if datetime.now() >= expires_at:
                    # Try to refresh
                    return await self._refresh_access_token()
            
            logger.info(f"✅ Microsoft provider {self.provider_id} authenticated")
            return True
            
        except Exception as e:
            logger.error(f"Error authenticating Microsoft provider: {e}")
            return False
    
    async def is_authenticated(self) -> bool:
        """Check if authenticated."""
        if not self.access_token:
            return await self.authenticate()
        
        # Check if token is expired
        if self.token_expires_at:
            from datetime import datetime
            expires_at = datetime.fromisoformat(self.token_expires_at)
            if datetime.now() >= expires_at:
                return await self._refresh_access_token()
        
        return True
    
    async def get_auth_url(self) -> Optional[str]:
        """Get OAuth authorization URL."""
        if not self.client_id:
            logger.error("Microsoft client ID not configured")
            return None
        
        import urllib.parse
        
        params = {
            'client_id': self.client_id,
            'response_type': 'code',
            'redirect_uri': self.redirect_uri,
            'scope': ' '.join(self.SCOPES),
            'response_mode': 'query',
            'state': self.provider_id  # Use provider_id as state
        }
        
        auth_url = f"{self.AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"
        return auth_url
    
    async def handle_callback(self, code: str, state: str) -> bool:
        """Handle OAuth callback with authorization code."""
        try:
            if not self.client_id or not self.client_secret:
                logger.error("Microsoft OAuth credentials not configured")
                return False
            
            # Exchange code for tokens
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'code': code,
                'redirect_uri': self.redirect_uri,
                'grant_type': 'authorization_code'
            }
            
            response = requests.post(self.TOKEN_ENDPOINT, data=data)
            response.raise_for_status()
            
            tokens = response.json()
            
            # Save tokens
            from datetime import timedelta
            expires_in = tokens.get('expires_in', 3600)
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            await self._save_tokens(
                access_token=tokens['access_token'],
                refresh_token=tokens.get('refresh_token'),
                expires_at=expires_at.isoformat()
            )
            
            self.access_token = tokens['access_token']
            self.refresh_token = tokens.get('refresh_token')
            self.token_expires_at = expires_at.isoformat()
            
            logger.info(f"✅ Microsoft OAuth callback handled for {self.provider_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error handling Microsoft callback: {e}")
            return False
    
    async def _refresh_access_token(self) -> bool:
        """Refresh the access token using refresh token."""
        try:
            if not self.refresh_token:
                logger.error("No refresh token available")
                return False
            
            data = {
                'client_id': self.client_id,
                'client_secret': self.client_secret,
                'refresh_token': self.refresh_token,
                'grant_type': 'refresh_token'
            }
            
            response = requests.post(self.TOKEN_ENDPOINT, data=data)
            response.raise_for_status()
            
            tokens = response.json()
            
            # Save new tokens
            from datetime import timedelta
            expires_in = tokens.get('expires_in', 3600)
            expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            await self._save_tokens(
                access_token=tokens['access_token'],
                refresh_token=tokens.get('refresh_token', self.refresh_token),
                expires_at=expires_at.isoformat()
            )
            
            self.access_token = tokens['access_token']
            if 'refresh_token' in tokens:
                self.refresh_token = tokens['refresh_token']
            self.token_expires_at = expires_at.isoformat()
            
            logger.info("Refreshed Microsoft access token")
            return True
            
        except Exception as e:
            logger.error(f"Error refreshing Microsoft token: {e}")
            return False
    
    async def _load_tokens(self) -> Optional[Dict[str, str]]:
        """Load tokens from database."""
        try:
            # Use comms_auth table from auth.py pattern
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT access_token, refresh_token, expires_at FROM comms_auth WHERE platform = ?",
                    (f"microsoft_{self.provider_id}",)
                )
                row = cursor.fetchone()
                
                if row:
                    return {
                        'access_token': row[0],
                        'refresh_token': row[1],
                        'expires_at': row[2]
                    }
                return None
        except Exception as e:
            logger.error(f"Error loading Microsoft tokens: {e}")
            return None
    
    async def _save_tokens(self, access_token: str, refresh_token: Optional[str], expires_at: str):
        """Save tokens to database."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                
                cursor.execute("""
                    INSERT INTO comms_auth 
                    (platform, access_token, refresh_token, expires_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(platform) DO UPDATE SET
                        access_token = excluded.access_token,
                        refresh_token = excluded.refresh_token,
                        expires_at = excluded.expires_at,
                        updated_at = excluded.updated_at
                """, (
                    f"microsoft_{self.provider_id}",
                    access_token,
                    refresh_token,
                    expires_at,
                    now,
                    now
                ))
                
                conn.commit()
                logger.info(f"Saved Microsoft tokens for {self.provider_id}")
        except Exception as e:
            logger.error(f"Error saving Microsoft tokens: {e}")
    
    def _make_graph_request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated request to Microsoft Graph API."""
        try:
            headers = {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
            
            url = f"{self.GRAPH_API_ENDPOINT}{endpoint}"
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Error making Graph API request to {endpoint}: {e}")
            return None
    
    async def collect_emails(
        self,
        start_date: datetime,
        end_date: datetime,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Collect emails from Outlook."""
        if not await self.is_authenticated():
            logger.error("Not authenticated with Microsoft")
            return []
        
        try:
            # Build filter for date range
            start_str = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            end_str = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            params = {
                '$filter': f"receivedDateTime ge {start_str} and receivedDateTime le {end_str}",
                '$top': max_results,
                '$orderby': 'receivedDateTime desc',
                '$select': 'id,subject,from,toRecipients,bodyPreview,body,receivedDateTime,isRead,hasAttachments,importance'
            }
            
            result = self._make_graph_request('/me/messages', params)
            if not result:
                return []
            
            messages = result.get('value', [])
            emails = []
            
            for message in messages:
                try:
                    email_data = {
                        'id': message['id'],
                        'subject': message.get('subject', 'No Subject'),
                        'sender': message.get('from', {}).get('emailAddress', {}).get('address', 'Unknown'),
                        'recipient': ', '.join([r.get('emailAddress', {}).get('address', '') for r in message.get('toRecipients', [])]),
                        'body': message.get('body', {}).get('content', ''),
                        'snippet': message.get('bodyPreview', ''),
                        'received_date': message.get('receivedDateTime', ''),
                        'read': message.get('isRead', False),
                        'labels': [],
                        'has_attachments': message.get('hasAttachments', False),
                        'is_important': message.get('importance', 'normal') == 'high'
                    }
                    
                    normalized = self._normalize_email(email_data)
                    emails.append(normalized)
                    
                except Exception as e:
                    logger.error(f"Error processing Outlook message {message.get('id')}: {e}")
                    continue
            
            logger.info(f"Collected {len(emails)} emails from Microsoft Outlook")
            return emails
            
        except Exception as e:
            logger.error(f"Error collecting emails from Microsoft: {e}")
            return []
    
    async def collect_calendar_events(
        self,
        start_date: datetime,
        end_date: datetime,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Collect calendar events from Office 365 Calendar."""
        if not await self.is_authenticated():
            logger.error("Not authenticated with Microsoft")
            return []
        
        try:
            # Build filter for date range
            start_str = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            end_str = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
            
            params = {
                '$filter': f"start/dateTime ge '{start_str}' and end/dateTime le '{end_str}'",
                '$top': max_results,
                '$orderby': 'start/dateTime',
                '$select': 'id,subject,body,start,end,location,attendees,organizer,isAllDay'
            }
            
            result = self._make_graph_request('/me/calendar/events', params)
            if not result:
                return []
            
            events = result.get('value', [])
            normalized_events = []
            
            for event in events:
                try:
                    event_data = {
                        'id': event['id'],
                        'title': event.get('subject', 'Untitled Event'),
                        'description': event.get('body', {}).get('content', ''),
                        'start_time': event.get('start', {}).get('dateTime', ''),
                        'end_time': event.get('end', {}).get('dateTime', ''),
                        'all_day': event.get('isAllDay', False),
                        'location': event.get('location', {}).get('displayName', ''),
                        'attendees': [a.get('emailAddress', {}).get('address', '') for a in event.get('attendees', [])],
                        'organizer': event.get('organizer', {}).get('emailAddress', {}).get('address', '')
                    }
                    
                    normalized = self._normalize_calendar_event(event_data)
                    normalized_events.append(normalized)
                    
                except Exception as e:
                    logger.error(f"Error processing calendar event {event.get('id')}: {e}")
                    continue
            
            logger.info(f"Collected {len(normalized_events)} events from Microsoft Calendar")
            return normalized_events
            
        except Exception as e:
            logger.error(f"Error collecting calendar events from Microsoft: {e}")
            return []
    
    async def collect_notes(
        self,
        folder_id: Optional[str] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Collect notes from OneNote."""
        if not await self.is_authenticated():
            logger.error("Not authenticated with Microsoft")
            return []
        
        try:
            # Get pages from OneNote
            endpoint = '/me/onenote/pages' if not folder_id else f'/me/onenote/sections/{folder_id}/pages'
            
            params = {
                '$top': max_results,
                '$orderby': 'lastModifiedDateTime desc',
                '$select': 'id,title,content,createdDateTime,lastModifiedDateTime'
            }
            
            result = self._make_graph_request(endpoint, params)
            if not result:
                return []
            
            pages = result.get('value', [])
            notes = []
            
            for page in pages:
                try:
                    # Get page content
                    content_url = page.get('contentUrl', '')
                    content = ""
                    if content_url:
                        # This would need additional request to get full content
                        # For now, use title as content placeholder
                        content = page.get('title', '')
                    
                    note_data = {
                        'id': page['id'],
                        'title': page.get('title', 'Untitled Note'),
                        'content': content,
                        'created_date': page.get('createdDateTime', ''),
                        'modified_date': page.get('lastModifiedDateTime', ''),
                        'tags': [],
                        'folder': folder_id or 'default'
                    }
                    
                    normalized = self._normalize_note(note_data)
                    notes.append(normalized)
                    
                except Exception as e:
                    logger.error(f"Error processing OneNote page {page.get('id')}: {e}")
                    continue
            
            logger.info(f"Collected {len(notes)} notes from Microsoft OneNote")
            return notes
            
        except Exception as e:
            logger.error(f"Error collecting notes from Microsoft: {e}")
            return []
