"""
Base provider interface for multi-provider authentication and data collection.
All provider implementations must inherit from BaseProvider.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Any, List, Optional
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ProviderCapability(Enum):
    """Capabilities that a provider can support."""
    EMAIL = "email"
    CALENDAR = "calendar"
    NOTES = "notes"
    CONTACTS = "contacts"
    TASKS = "tasks"


class BaseProvider(ABC):
    """Base class for all provider implementations."""
    
    def __init__(self, provider_id: str, settings: Any, db_manager: Any):
        """
        Initialize provider.
        
        Args:
            provider_id: Unique identifier for this provider instance (e.g., "google_work", "google_personal")
            settings: Application settings
            db_manager: Database manager instance
        """
        self.provider_id = provider_id
        self.settings = settings
        self.db = db_manager
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the provider name (e.g., 'google', 'microsoft', 'proton')."""
        pass
    
    @property
    @abstractmethod
    def capabilities(self) -> List[ProviderCapability]:
        """Return list of capabilities this provider supports."""
        pass
    
    @abstractmethod
    async def authenticate(self) -> bool:
        """
        Authenticate with the provider.
        
        Returns:
            True if authentication successful, False otherwise
        """
        pass
    
    @abstractmethod
    async def is_authenticated(self) -> bool:
        """
        Check if currently authenticated.
        
        Returns:
            True if valid credentials exist, False otherwise
        """
        pass
    
    @abstractmethod
    async def get_auth_url(self) -> Optional[str]:
        """
        Get OAuth authorization URL for this provider.
        
        Returns:
            Authorization URL or None if not applicable
        """
        pass
    
    @abstractmethod
    async def handle_callback(self, code: str, state: str) -> bool:
        """
        Handle OAuth callback with authorization code.
        
        Args:
            code: Authorization code from OAuth provider
            state: State parameter for CSRF protection
            
        Returns:
            True if callback handled successfully, False otherwise
        """
        pass
    
    # Email methods
    async def collect_emails(
        self,
        start_date: datetime,
        end_date: datetime,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Collect emails from provider.
        
        Args:
            start_date: Start date for email collection
            end_date: End date for email collection
            max_results: Maximum number of emails to return
            
        Returns:
            List of email dictionaries
        """
        if ProviderCapability.EMAIL not in self.capabilities:
            raise NotImplementedError(f"{self.provider_name} does not support email")
        raise NotImplementedError("Email collection not implemented")
    
    async def get_email_details(self, email_id: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed information for a specific email.
        
        Args:
            email_id: Email identifier
            
        Returns:
            Email details dictionary or None if not found
        """
        if ProviderCapability.EMAIL not in self.capabilities:
            raise NotImplementedError(f"{self.provider_name} does not support email")
        raise NotImplementedError("Email details not implemented")
    
    # Calendar methods
    async def collect_calendar_events(
        self,
        start_date: datetime,
        end_date: datetime,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Collect calendar events from provider.
        
        Args:
            start_date: Start date for event collection
            end_date: End date for event collection
            max_results: Maximum number of events to return
            
        Returns:
            List of event dictionaries
        """
        if ProviderCapability.CALENDAR not in self.capabilities:
            raise NotImplementedError(f"{self.provider_name} does not support calendar")
        raise NotImplementedError("Calendar collection not implemented")
    
    # Notes methods
    async def collect_notes(
        self,
        folder_id: Optional[str] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Collect notes/documents from provider.
        
        Args:
            folder_id: Optional folder ID to limit search
            max_results: Maximum number of notes to return
            
        Returns:
            List of note dictionaries
        """
        if ProviderCapability.NOTES not in self.capabilities:
            raise NotImplementedError(f"{self.provider_name} does not support notes")
        raise NotImplementedError("Notes collection not implemented")
    
    # Utility methods
    def _normalize_email(self, raw_email: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize email data to standard format.
        
        Args:
            raw_email: Provider-specific email data
            
        Returns:
            Normalized email dictionary with standard fields
        """
        return {
            'id': raw_email.get('id', ''),
            'provider': self.provider_name,
            'provider_id': self.provider_id,
            'subject': raw_email.get('subject', 'No Subject'),
            'sender': raw_email.get('sender', 'Unknown'),
            'recipient': raw_email.get('recipient', ''),
            'body': raw_email.get('body', ''),
            'snippet': raw_email.get('snippet', ''),
            'received_date': raw_email.get('received_date', ''),
            'read': raw_email.get('read', False),
            'labels': raw_email.get('labels', []),
            'has_attachments': raw_email.get('has_attachments', False),
            'is_important': raw_email.get('is_important', False),
            'raw_data': raw_email  # Keep original data for provider-specific features
        }
    
    def _normalize_calendar_event(self, raw_event: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize calendar event to standard format.
        
        Args:
            raw_event: Provider-specific event data
            
        Returns:
            Normalized event dictionary with standard fields
        """
        return {
            'id': raw_event.get('id', ''),
            'provider': self.provider_name,
            'provider_id': self.provider_id,
            'title': raw_event.get('title', 'Untitled Event'),
            'description': raw_event.get('description', ''),
            'start_time': raw_event.get('start_time', ''),
            'end_time': raw_event.get('end_time', ''),
            'all_day': raw_event.get('all_day', False),
            'location': raw_event.get('location', ''),
            'attendees': raw_event.get('attendees', []),
            'organizer': raw_event.get('organizer', ''),
            'raw_data': raw_event
        }
    
    def _normalize_note(self, raw_note: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize note/document to standard format.
        
        Args:
            raw_note: Provider-specific note data
            
        Returns:
            Normalized note dictionary with standard fields
        """
        return {
            'id': raw_note.get('id', ''),
            'provider': self.provider_name,
            'provider_id': self.provider_id,
            'title': raw_note.get('title', 'Untitled Note'),
            'content': raw_note.get('content', ''),
            'created_date': raw_note.get('created_date', ''),
            'modified_date': raw_note.get('modified_date', ''),
            'tags': raw_note.get('tags', []),
            'folder': raw_note.get('folder', ''),
            'raw_data': raw_note
        }
