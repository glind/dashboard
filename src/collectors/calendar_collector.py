"""
Google Calendar data collector using Google Calendar API.
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path
import pytz

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

# Import database functions
try:
    from database import get_credentials, get_auth_token
    DATABASE_AVAILABLE = True
except ImportError:
    DATABASE_AVAILABLE = False

logger = logging.getLogger(__name__)


class CalendarCollector:
    """Collects calendar events from Google Calendar."""
    
    def __init__(self, settings):
        """Initialize Calendar collector with settings."""
        self.settings = settings
        self.service = None
    
    async def collect_events(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Collect calendar events within the specified date range."""
        if not GOOGLE_AVAILABLE:
            logger.warning("Google API libraries not available.")
            return []
            
        logger.info(f"Calendar collector settings check - credentials_file: {getattr(self.settings.google, 'credentials_file', 'NOT SET')}")
        
        # Skip the credentials_file check since we handle this in _authenticate
        try:
            await self._authenticate()
            
            if not self.service:
                logger.error("Authentication failed - no service available")
                return []
            
            # Convert dates to RFC3339 format
            start_time = start_date.isoformat() + 'Z'
            end_time = end_date.isoformat() + 'Z'
            
            logger.info(f"Fetching calendar events from {start_time} to {end_time}")
            
            # Get events from primary calendar
            events_result = self.service.events().list(
                calendarId='primary',
                timeMin=start_time,
                timeMax=end_time,
                maxResults=500,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            processed_events = []
            for event in events:
                event_data = self._process_event(event)
                if event_data:
                    processed_events.append(event_data)
            
            logger.info(f"Collected {len(processed_events)} calendar events")
            return processed_events
            
        except Exception as e:
            logger.error(f"Error collecting calendar events: {e}")
            return []
    
    async def _authenticate(self):
        """Authenticate with Google Calendar API."""
        logger.info("Starting Google Calendar authentication")
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
                    creds = Credentials.from_authorized_user_file(
                        str(token_file),
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
        
        self.service = build('calendar', 'v3', credentials=creds)
        logger.info("Successfully authenticated with Google Calendar API")
    
    def _process_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        """Process a calendar event into our standard format."""
        try:
            # Set up Pacific timezone
            pacific_tz = pytz.timezone('US/Pacific')
            utc_tz = pytz.UTC
            
            start = event['start'].get('dateTime', event['start'].get('date'))
            end = event['end'].get('dateTime', event['end'].get('date'))
            
            # Parse start and end times
            if 'T' in start:  # DateTime format
                start_dt = datetime.fromisoformat(start.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end.replace('Z', '+00:00'))
                
                # Convert to Pacific timezone if they have timezone info
                if start_dt.tzinfo is not None:
                    start_dt = start_dt.astimezone(pacific_tz)
                    end_dt = end_dt.astimezone(pacific_tz)
                else:
                    # Assume UTC if no timezone info
                    start_dt = utc_tz.localize(start_dt).astimezone(pacific_tz)
                    end_dt = utc_tz.localize(end_dt).astimezone(pacific_tz)
            else:  # Date format (all-day event)
                start_dt = datetime.fromisoformat(start + 'T00:00:00')
                end_dt = datetime.fromisoformat(end + 'T00:00:00')
                # Localize all-day events to Pacific timezone
                start_dt = pacific_tz.localize(start_dt)
                end_dt = pacific_tz.localize(end_dt)
            
            event_data = {
                'id': event['id'],
                'summary': event.get('summary', 'No Title'),
                'description': event.get('description', ''),
                'start_time': start_dt,
                'end_time': end_dt,
                'location': event.get('location', ''),
                'attendees': self._extract_attendees(event),
                'creator': event.get('creator', {}).get('email', ''),
                'organizer': event.get('organizer', {}).get('email', ''),
                'status': event.get('status', 'confirmed'),
                'is_all_day': 'date' in event['start'],
                'duration_minutes': self._calculate_duration(start_dt, end_dt),
                'is_meeting': self._is_meeting(event),
                'is_important': self._is_important_event(event)
            }
            
            return event_data
            
        except Exception as e:
            logger.error(f"Error processing event: {e}")
            return None
    
    def _extract_attendees(self, event: Dict[str, Any]) -> List[str]:
        """Extract attendee emails from event."""
        attendees = event.get('attendees', [])
        return [attendee.get('email', '') for attendee in attendees if attendee.get('email')]
    
    def _calculate_duration(self, start_dt: datetime, end_dt: datetime) -> int:
        """Calculate event duration in minutes."""
        duration = end_dt - start_dt
        return int(duration.total_seconds() / 60)
    
    def _is_meeting(self, event: Dict[str, Any]) -> bool:
        """Determine if event is a meeting."""
        # Check if there are multiple attendees
        attendees = event.get('attendees', [])
        if len(attendees) > 1:
            return True
        
        # Check summary for meeting keywords
        summary = event.get('summary', '').lower()
        meeting_keywords = [
            'meeting', 'call', 'standup', 'sync', 'review',
            'discussion', 'planning', 'retrospective'
        ]
        
        return any(keyword in summary for keyword in meeting_keywords)
    
    def _is_important_event(self, event: Dict[str, Any]) -> bool:
        """Determine if event is important."""
        summary = event.get('summary', '').lower()
        description = event.get('description', '').lower()
        
        # Important keywords
        important_keywords = [
            'important', 'critical', 'urgent', 'deadline',
            'presentation', 'demo', 'interview', 'client'
        ]
        
        text_to_check = f"{summary} {description}"
        return any(keyword in text_to_check for keyword in important_keywords)

    async def get_upcoming_events(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get upcoming calendar events for the next specified number of days."""
        from datetime import datetime, timedelta
        
        start_date = datetime.now()
        end_date = start_date + timedelta(days=days)
        
        return await self.collect_events(start_date, end_date)
