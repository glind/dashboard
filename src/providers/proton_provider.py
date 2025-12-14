"""
Proton Provider - supports ProtonMail via Bridge.
Note: Proton requires Bridge application for API access.
"""

import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import imaplib
import email
from email.header import decode_header

from .base import BaseProvider, ProviderCapability

logger = logging.getLogger(__name__)


class ProtonProvider(BaseProvider):
    """
    Proton provider implementation using IMAP Bridge.
    
    Note: Proton does not have a public REST API for email access.
    Users must install and run Proton Bridge locally to access emails via IMAP.
    See: https://proton.me/mail/bridge
    """
    
    def __init__(self, provider_id: str, settings: Any, db_manager: Any):
        """Initialize Proton provider."""
        super().__init__(provider_id, settings, db_manager)
        self.imap_connection = None
        
        # Proton Bridge IMAP settings (default localhost)
        self.imap_host = getattr(settings, 'proton_imap_host', 'localhost')
        self.imap_port = getattr(settings, 'proton_imap_port', 1143)  # Proton Bridge default
        self.username = getattr(settings, 'proton_username', None)
        self.password = getattr(settings, 'proton_password', None)  # Bridge password
    
    @property
    def provider_name(self) -> str:
        return "proton"
    
    @property
    def capabilities(self) -> List[ProviderCapability]:
        # Proton only supports email via Bridge
        return [ProviderCapability.EMAIL]
    
    async def authenticate(self) -> bool:
        """Authenticate with Proton Bridge via IMAP."""
        try:
            if not self.username or not self.password:
                logger.error("Proton credentials not configured")
                return False
            
            # Connect to Proton Bridge IMAP
            self.imap_connection = imaplib.IMAP4(self.imap_host, self.imap_port)
            self.imap_connection.login(self.username, self.password)
            
            logger.info(f"✅ Proton provider {self.provider_id} authenticated via Bridge")
            return True
            
        except Exception as e:
            logger.error(f"Error authenticating with Proton Bridge: {e}")
            logger.info("Make sure Proton Bridge is running and credentials are correct")
            return False
    
    async def is_authenticated(self) -> bool:
        """Check if authenticated."""
        if not self.imap_connection:
            return await self.authenticate()
        
        try:
            # Test connection with NOOP command
            self.imap_connection.noop()
            return True
        except:
            # Try to reconnect
            return await self.authenticate()
    
    async def get_auth_url(self) -> Optional[str]:
        """Get auth URL (N/A for Proton - uses Bridge)."""
        return None
    
    async def handle_callback(self, code: str, state: str) -> bool:
        """Handle OAuth callback (N/A for Proton)."""
        return False
    
    async def collect_emails(
        self,
        start_date: datetime,
        end_date: datetime,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Collect emails from ProtonMail via Bridge."""
        if not await self.is_authenticated():
            logger.error("Not authenticated with Proton Bridge")
            return []
        
        try:
            # Select inbox
            self.imap_connection.select('INBOX')
            
            # Build IMAP date search criteria
            start_str = start_date.strftime('%d-%b-%Y')
            end_str = end_date.strftime('%d-%b-%Y')
            
            # Search for emails in date range
            status, message_ids = self.imap_connection.search(
                None,
                f'(SINCE {start_str} BEFORE {end_str})'
            )
            
            if status != 'OK':
                logger.error("Failed to search Proton emails")
                return []
            
            # Get message IDs
            email_ids = message_ids[0].split()
            
            # Limit to max_results
            email_ids = email_ids[-max_results:] if len(email_ids) > max_results else email_ids
            
            emails = []
            
            for email_id in email_ids:
                try:
                    # Fetch email
                    status, msg_data = self.imap_connection.fetch(email_id, '(RFC822)')
                    
                    if status != 'OK':
                        continue
                    
                    # Parse email
                    raw_email = msg_data[0][1]
                    msg = email.message_from_bytes(raw_email)
                    
                    # Extract fields
                    subject = self._decode_header(msg['Subject'])
                    sender = self._decode_header(msg['From'])
                    recipient = self._decode_header(msg['To'])
                    date_str = msg['Date']
                    
                    # Get body
                    body = self._get_email_body(msg)
                    
                    # Check flags
                    status, flag_data = self.imap_connection.fetch(email_id, '(FLAGS)')
                    flags = flag_data[0].decode() if flag_data else ''
                    is_read = '\\Seen' in flags
                    is_important = '\\Flagged' in flags
                    
                    email_data = {
                        'id': email_id.decode(),
                        'subject': subject,
                        'sender': sender,
                        'recipient': recipient,
                        'body': body,
                        'snippet': body[:200] if body else '',
                        'received_date': date_str,
                        'read': is_read,
                        'labels': [],
                        'has_attachments': self._has_attachments(msg),
                        'is_important': is_important
                    }
                    
                    normalized = self._normalize_email(email_data)
                    emails.append(normalized)
                    
                except Exception as e:
                    logger.error(f"Error processing Proton email {email_id}: {e}")
                    continue
            
            logger.info(f"Collected {len(emails)} emails from Proton")
            return emails
            
        except Exception as e:
            logger.error(f"Error collecting emails from Proton: {e}")
            return []
    
    def _decode_header(self, header: str) -> str:
        """Decode email header."""
        if not header:
            return ''
        
        decoded = decode_header(header)
        parts = []
        
        for content, charset in decoded:
            if isinstance(content, bytes):
                try:
                    parts.append(content.decode(charset or 'utf-8', errors='ignore'))
                except:
                    parts.append(content.decode('utf-8', errors='ignore'))
            else:
                parts.append(content)
        
        return ' '.join(parts)
    
    def _get_email_body(self, msg: email.message.Message) -> str:
        """Extract email body from message."""
        body = ""
        
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                if content_type == 'text/plain':
                    try:
                        body = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                        break
                    except:
                        pass
        else:
            try:
                body = msg.get_payload(decode=True).decode('utf-8', errors='ignore')
            except:
                body = str(msg.get_payload())
        
        return body
    
    def _has_attachments(self, msg: email.message.Message) -> bool:
        """Check if email has attachments."""
        if msg.is_multipart():
            for part in msg.walk():
                if part.get_content_disposition() == 'attachment':
                    return True
        return False
    
    async def collect_calendar_events(
        self,
        start_date: datetime,
        end_date: datetime,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Calendar not supported by Proton Bridge."""
        raise NotImplementedError("Proton does not support calendar via Bridge")
    
    async def collect_notes(
        self,
        folder_id: Optional[str] = None,
        max_results: int = 100
    ) -> List[Dict[str, Any]]:
        """Notes not supported by Proton Bridge."""
        raise NotImplementedError("Proton does not support notes via Bridge")
