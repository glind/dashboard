"""
OAuth and Authentication Manager for Communications Module
Handles login flows for LinkedIn, Slack, and Discord
"""

import logging
import secrets
from typing import Dict, Optional, Any
from datetime import datetime, timedelta
from fastapi import HTTPException
import requests

logger = logging.getLogger(__name__)


class CommsAuthManager:
    """Manages OAuth flows and token storage for communication platforms."""
    
    def __init__(self, db_manager):
        """Initialize with database manager."""
        self.db = db_manager
        self._ensure_auth_table()
    
    def _ensure_auth_table(self):
        """Create auth tokens table if it doesn't exist."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS comms_auth (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        platform TEXT NOT NULL,
                        user_identifier TEXT,
                        access_token TEXT NOT NULL,
                        refresh_token TEXT,
                        token_type TEXT,
                        expires_at TEXT,
                        scope TEXT,
                        metadata TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        UNIQUE(platform)
                    )
                """)
                conn.commit()
                logger.info("✅ Comms auth table ready")
        except Exception as e:
            logger.error(f"Error creating auth table: {e}")
    
    def get_credentials(self, platform: str) -> Optional[Dict[str, Any]]:
        """Get stored credentials for a platform."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT access_token, refresh_token, expires_at, metadata FROM comms_auth WHERE platform = ?",
                    (platform,)
                )
                row = cursor.fetchone()
                
                if row:
                    import json
                    metadata = json.loads(row[3]) if row[3] else {}
                    return {
                        'access_token': row[0],
                        'refresh_token': row[1],
                        'expires_at': row[2],
                        'user_info': metadata
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting credentials for {platform}: {e}")
            return None
    
    def save_credentials(
        self,
        platform: str,
        access_token: str,
        refresh_token: Optional[str] = None,
        expires_in: Optional[int] = None,
        user_info: Optional[Dict] = None,
        scope: Optional[str] = None
    ):
        """Save credentials to database."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                expires_at = None
                
                if expires_in:
                    expires_at = (datetime.now() + timedelta(seconds=expires_in)).isoformat()
                
                import json
                metadata = json.dumps(user_info) if user_info else None
                user_identifier = None
                
                if user_info:
                    user_identifier = (
                        user_info.get('id') or
                        user_info.get('user_id') or
                        user_info.get('sub') or
                        user_info.get('email')
                    )
                
                cursor.execute("""
                    INSERT INTO comms_auth 
                    (platform, user_identifier, access_token, refresh_token, expires_at, scope, metadata, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(platform) DO UPDATE SET
                        access_token = excluded.access_token,
                        refresh_token = excluded.refresh_token,
                        expires_at = excluded.expires_at,
                        scope = excluded.scope,
                        metadata = excluded.metadata,
                        updated_at = excluded.updated_at,
                        user_identifier = excluded.user_identifier
                """, (
                    platform,
                    user_identifier,
                    access_token,
                    refresh_token,
                    expires_at,
                    scope,
                    metadata,
                    now,
                    now
                ))
                
                conn.commit()
                logger.info(f"✅ Saved credentials for {platform}")
                return True
            
        except Exception as e:
            logger.error(f"Error saving credentials for {platform}: {e}")
            return False
    
    def delete_credentials(self, platform: str):
        """Delete stored credentials."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM comms_auth WHERE platform = ?", (platform,))
                conn.commit()
                logger.info(f"Deleted credentials for {platform}")
                return True
        except Exception as e:
            logger.error(f"Error deleting credentials for {platform}: {e}")
            return False
    
    def get_all_connected_platforms(self) -> list:
        """Get list of all connected platforms."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT platform, user_identifier, expires_at, created_at 
                    FROM comms_auth 
                    ORDER BY created_at DESC
                """)
                
                platforms = []
                for row in cursor.fetchall():
                    platforms.append({
                        'platform': row[0],
                        'user_identifier': row[1],
                        'expires_at': row[2],
                        'connected_at': row[3],
                        'is_expired': self._is_expired(row[2]) if row[2] else False
                    })
                
                return platforms
            
        except Exception as e:
            logger.error(f"Error getting connected platforms: {e}")
            return []
    
    def _is_expired(self, expires_at: str) -> bool:
        """Check if token is expired."""
        try:
            expiry = datetime.fromisoformat(expires_at)
            return datetime.now() > expiry
        except:
            return False
    
    async def refresh_token_if_needed(self, platform: str) -> bool:
        """Refresh token if expired (for platforms that support it)."""
        creds = self.get_credentials(platform)
        if not creds or not creds.get('refresh_token'):
            return False
        
        if creds.get('expires_at') and not self._is_expired(creds['expires_at']):
            return True  # Token still valid
        
        # Implement refresh logic per platform
        if platform == 'slack':
            return await self._refresh_slack_token(creds['refresh_token'])
        elif platform == 'linkedin':
            return await self._refresh_linkedin_token(creds['refresh_token'])
        
        return False
    
    async def _refresh_slack_token(self, refresh_token: str) -> bool:
        """Refresh Slack token."""
        # Slack doesn't use refresh tokens for user tokens
        # They're long-lived by default
        return False
    
    async def _refresh_linkedin_token(self, refresh_token: str) -> bool:
        """Refresh LinkedIn token."""
        try:
            # Would need client_id and client_secret from config
            # LinkedIn tokens typically need manual renewal
            logger.warning("LinkedIn token refresh not implemented - tokens expire after 60 days")
            return False
        except Exception as e:
            logger.error(f"Error refreshing LinkedIn token: {e}")
            return False


class OAuthFlowManager:
    """Manages OAuth authorization flows."""
    
    def __init__(self):
        self.state_tokens = {}  # In-memory store for OAuth state tokens
    
    def generate_state_token(self, platform: str) -> str:
        """Generate CSRF protection state token."""
        state = secrets.token_urlsafe(32)
        self.state_tokens[state] = {
            'platform': platform,
            'created_at': datetime.now(),
            'expires_at': datetime.now() + timedelta(minutes=10)
        }
        return state
    
    def verify_state_token(self, state: str, platform: str) -> bool:
        """Verify OAuth state token."""
        token_data = self.state_tokens.get(state)
        
        if not token_data:
            return False
        
        if token_data['platform'] != platform:
            return False
        
        if datetime.now() > token_data['expires_at']:
            del self.state_tokens[state]
            return False
        
        del self.state_tokens[state]
        return True
    
    def cleanup_expired_states(self):
        """Remove expired state tokens."""
        now = datetime.now()
        expired = [
            state for state, data in self.state_tokens.items()
            if now > data['expires_at']
        ]
        for state in expired:
            del self.state_tokens[state]


# Platform-specific OAuth helpers
class SlackOAuthHelper:
    """Slack OAuth flow helper."""
    
    AUTHORIZE_URL = "https://slack.com/oauth/v2/authorize"
    TOKEN_URL = "https://slack.com/api/oauth.v2.access"
    
    REQUIRED_SCOPES = [
        "channels:history",
        "channels:read",
        "groups:history",
        "im:history",
        "im:read",
        "mpim:history",
        "search:read",
        "users:read",
        "users:read.email"
    ]
    
    @staticmethod
    def get_authorization_url(client_id: str, redirect_uri: str, state: str) -> str:
        """Get Slack OAuth authorization URL."""
        scopes = ",".join(SlackOAuthHelper.REQUIRED_SCOPES)
        return (
            f"{SlackOAuthHelper.AUTHORIZE_URL}"
            f"?client_id={client_id}"
            f"&scope={scopes}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
        )
    
    @staticmethod
    async def exchange_code_for_token(
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str
    ) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        try:
            response = requests.post(
                SlackOAuthHelper.TOKEN_URL,
                data={
                    'code': code,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uri': redirect_uri
                }
            )
            
            data = response.json()
            
            if not data.get('ok'):
                raise HTTPException(status_code=400, detail=data.get('error', 'OAuth failed'))
            
            return {
                'access_token': data['authed_user']['access_token'],
                'token_type': data.get('token_type'),
                'scope': data.get('scope'),
                'user_id': data['authed_user']['id'],
                'team_id': data.get('team', {}).get('id')
            }
            
        except Exception as e:
            logger.error(f"Slack OAuth token exchange failed: {e}")
            raise


class DiscordOAuthHelper:
    """Discord OAuth flow helper."""
    
    AUTHORIZE_URL = "https://discord.com/api/oauth2/authorize"
    TOKEN_URL = "https://discord.com/api/oauth2/token"
    USER_URL = "https://discord.com/api/users/@me"
    
    REQUIRED_SCOPES = ["identify", "email", "messages.read"]
    
    @staticmethod
    def get_authorization_url(client_id: str, redirect_uri: str, state: str) -> str:
        """Get Discord OAuth authorization URL."""
        scopes = "%20".join(DiscordOAuthHelper.REQUIRED_SCOPES)
        return (
            f"{DiscordOAuthHelper.AUTHORIZE_URL}"
            f"?client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&response_type=code"
            f"&scope={scopes}"
            f"&state={state}"
        )
    
    @staticmethod
    async def exchange_code_for_token(
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str
    ) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        try:
            response = requests.post(
                DiscordOAuthHelper.TOKEN_URL,
                data={
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'grant_type': 'authorization_code',
                    'code': code,
                    'redirect_uri': redirect_uri
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="OAuth failed")
            
            data = response.json()
            
            # Get user info
            user_response = requests.get(
                DiscordOAuthHelper.USER_URL,
                headers={'Authorization': f"Bearer {data['access_token']}"}
            )
            
            user_data = user_response.json()
            
            return {
                'access_token': data['access_token'],
                'refresh_token': data.get('refresh_token'),
                'token_type': data.get('token_type'),
                'expires_in': data.get('expires_in'),
                'scope': data.get('scope'),
                'user_id': user_data.get('id'),
                'username': user_data.get('username'),
                'email': user_data.get('email')
            }
            
        except Exception as e:
            logger.error(f"Discord OAuth token exchange failed: {e}")
            raise


class LinkedInOAuthHelper:
    """LinkedIn OAuth flow helper."""
    
    AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
    TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
    USER_URL = "https://api.linkedin.com/v2/me"
    
    REQUIRED_SCOPES = ["r_liteprofile", "r_emailaddress", "w_member_social", "r_messaging"]
    
    @staticmethod
    def get_authorization_url(client_id: str, redirect_uri: str, state: str) -> str:
        """Get LinkedIn OAuth authorization URL."""
        scopes = "%20".join(LinkedInOAuthHelper.REQUIRED_SCOPES)
        return (
            f"{LinkedInOAuthHelper.AUTHORIZE_URL}"
            f"?response_type=code"
            f"&client_id={client_id}"
            f"&redirect_uri={redirect_uri}"
            f"&state={state}"
            f"&scope={scopes}"
        )
    
    @staticmethod
    async def exchange_code_for_token(
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str
    ) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        try:
            response = requests.post(
                LinkedInOAuthHelper.TOKEN_URL,
                data={
                    'grant_type': 'authorization_code',
                    'code': code,
                    'client_id': client_id,
                    'client_secret': client_secret,
                    'redirect_uri': redirect_uri
                },
                headers={'Content-Type': 'application/x-www-form-urlencoded'}
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=400, detail="OAuth failed")
            
            data = response.json()
            
            # Get user info
            user_response = requests.get(
                LinkedInOAuthHelper.USER_URL,
                headers={'Authorization': f"Bearer {data['access_token']}"}
            )
            
            user_data = user_response.json()
            
            return {
                'access_token': data['access_token'],
                'refresh_token': data.get('refresh_token'),
                'expires_in': data.get('expires_in'),
                'scope': data.get('scope'),
                'user_id': user_data.get('id'),
                'first_name': user_data.get('localizedFirstName'),
                'last_name': user_data.get('localizedLastName')
            }
            
        except Exception as e:
            logger.error(f"LinkedIn OAuth token exchange failed: {e}")
            raise
