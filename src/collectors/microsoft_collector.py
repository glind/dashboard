"""
Microsoft Outlook/Office365 Email Collector for multi-account dashboard.
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

try:
    import msal
    import requests
    MICROSOFT_AVAILABLE = True
except ImportError:
    MICROSOFT_AVAILABLE = False

logger = logging.getLogger(__name__)

class MicrosoftCollector:
    """Collects emails from Microsoft Outlook/Office365 using Graph API."""
    def __init__(self, account_config: Dict[str, Any]):
        self.account = account_config
        self.token = None
        self.session = None

    def authenticate(self):
        if not MICROSOFT_AVAILABLE:
            logger.warning("MSAL or requests not installed.")
            return False
        app = msal.ConfidentialClientApplication(
            client_id=self.account['client_id'],
            client_credential=self.account['client_secret'],
            authority=f"https://login.microsoftonline.com/{self.account['tenant_id']}"
        )
        scopes = self.account.get('scopes', ["https://graph.microsoft.com/.default"])
        result = app.acquire_token_for_client(scopes=scopes)
        if "access_token" in result:
            self.token = result["access_token"]
            self.session = requests.Session()
            self.session.headers.update({"Authorization": f"Bearer {self.token}"})
            logger.info(f"Authenticated Microsoft account: {self.account['name']}")
            return True
        logger.error(f"Failed to authenticate Microsoft account: {self.account['name']}")
        return False

    def collect_emails(self, max_results: int = 100) -> List[Dict[str, Any]]:
        if not self.session:
            if not self.authenticate():
                return []
        url = "https://graph.microsoft.com/v1.0/me/mailFolders/inbox/messages"
        params = {"$top": max_results}
        resp = self.session.get(url, params=params)
        if resp.status_code == 200:
            data = resp.json()
            emails = []
            for msg in data.get('value', []):
                emails.append({
                    'id': msg.get('id'),
                    'subject': msg.get('subject'),
                    'sender': msg.get('from', {}).get('emailAddress', {}).get('address'),
                    'recipient': msg.get('toRecipients', [{}])[0].get('emailAddress', {}).get('address'),
                    'date': msg.get('receivedDateTime'),
                    'body': msg.get('body', {}).get('content'),
                    'is_read': msg.get('isRead'),
                    'importance': msg.get('importance'),
                    'web_link': msg.get('webLink'),
                })
            logger.info(f"Collected {len(emails)} emails from Microsoft account: {self.account['name']}")
            return emails
        logger.error(f"Failed to fetch emails for Microsoft account: {self.account['name']}")
        return []
