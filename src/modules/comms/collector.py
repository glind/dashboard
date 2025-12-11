"""
Communications Collector
Fetches messages from LinkedIn, Slack, and Discord
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import requests
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parents[3]))

from src.database import DatabaseManager

logger = logging.getLogger(__name__)


class CommsCollector:
    """Collects messages from multiple communication platforms."""
    
    def __init__(self, auth_manager=None):
        """Initialize collector with optional auth manager."""
        self.auth_manager = auth_manager
        if not self.auth_manager:
            # Create default auth manager
            from .auth import CommsAuthManager
            db = DatabaseManager()
            self.auth_manager = CommsAuthManager(db)
        
    def _get_credentials(self, platform: str) -> Dict[str, Any]:
        """Get credentials from database."""
        creds = self.auth_manager.get_credentials(platform)
        if not creds:
            logger.warning(f"No credentials found for {platform}")
            return {}
        return creds
    
    async def collect_all(self, hours_back: int = 24) -> Dict[str, List[Dict[str, Any]]]:
        """Collect messages from all platforms."""
        logger.info(f"Collecting communications from last {hours_back} hours")
        
        results = {
            'linkedin': await self.collect_linkedin(hours_back),
            'slack': await self.collect_slack(hours_back),
            'discord': await self.collect_discord(hours_back),
            'collected_at': datetime.now().isoformat()
        }
        
        total = sum(len(results[k]) for k in ['linkedin', 'slack', 'discord'])
        logger.info(f"Collected {total} total messages")
        
        return results
    
    async def collect_linkedin(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """Collect LinkedIn messages and mentions."""
        credentials = self._get_credentials('linkedin')
        if not credentials.get('access_token'):
            logger.warning("LinkedIn not connected - please login in the dashboard")
            return []
        
        try:
            messages = []
            access_token = credentials['access_token']
            headers = {'Authorization': f'Bearer {access_token}'}
            
            # Get conversations (LinkedIn Messaging API)
            conversations_url = 'https://api.linkedin.com/v2/messages'
            response = requests.get(conversations_url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                cutoff_time = datetime.now() - timedelta(hours=hours_back)
                
                for conversation in data.get('elements', []):
                    msg_time = datetime.fromtimestamp(conversation.get('lastActivityAt', 0) / 1000)
                    
                    if msg_time < cutoff_time:
                        continue
                    
                    # Get conversation details
                    conv_id = conversation.get('conversationId')
                    if conv_id:
                        messages.append({
                            'id': conv_id,
                            'platform': 'linkedin',
                            'type': 'message',
                            'from_user': conversation.get('participants', [{}])[0].get('name', 'Unknown'),
                            'from_id': conversation.get('participants', [{}])[0].get('id'),
                            'preview': conversation.get('lastMessage', {}).get('text', '')[:200],
                            'timestamp': msg_time.isoformat(),
                            'unread': conversation.get('unread', False),
                            'link': f"https://www.linkedin.com/messaging/thread/{conv_id}/",
                            'raw': conversation
                        })
            
            logger.info(f"Collected {len(messages)} LinkedIn messages")
            return messages
            
        except Exception as e:
            logger.error(f"Error collecting LinkedIn messages: {e}")
            return []
    
    async def collect_slack(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """Collect Slack mentions and DMs."""
        credentials = self._get_credentials('slack')
        if not credentials.get('access_token'):
            logger.warning("Slack not connected - please login in the dashboard")
            return []
        
        try:
            messages = []
            token = credentials['access_token']
            headers = {'Authorization': f'Bearer {token}'}
            
            # Get user ID first
            user_response = requests.get(
                'https://slack.com/api/auth.test',
                headers=headers,
                timeout=10
            )
            
            if user_response.status_code != 200:
                logger.error("Failed to authenticate with Slack")
                return []
            
            user_id = user_response.json().get('user_id')
            cutoff_timestamp = (datetime.now() - timedelta(hours=hours_back)).timestamp()
            
            # Search for mentions
            search_url = 'https://slack.com/api/search.messages'
            search_params = {
                'query': f'<@{user_id}>',
                'count': 100,
                'sort': 'timestamp',
                'sort_dir': 'desc'
            }
            
            search_response = requests.get(
                search_url,
                headers=headers,
                params=search_params,
                timeout=10
            )
            
            if search_response.status_code == 200:
                search_data = search_response.json()
                
                for match in search_data.get('messages', {}).get('matches', []):
                    msg_timestamp = float(match.get('ts', 0))
                    
                    if msg_timestamp < cutoff_timestamp:
                        continue
                    
                    channel = match.get('channel', {})
                    permalink = match.get('permalink')
                    
                    messages.append({
                        'id': f"{channel.get('id')}_{match.get('ts')}",
                        'platform': 'slack',
                        'type': 'mention',
                        'from_user': match.get('username', 'Unknown'),
                        'from_id': match.get('user'),
                        'channel': channel.get('name', 'Unknown'),
                        'channel_id': channel.get('id'),
                        'text': match.get('text', '')[:500],
                        'timestamp': datetime.fromtimestamp(msg_timestamp).isoformat(),
                        'link': permalink,
                        'raw': match
                    })
            
            # Get direct messages
            conversations_url = 'https://slack.com/api/conversations.list'
            conversations_params = {
                'types': 'im',
                'exclude_archived': True
            }
            
            conv_response = requests.get(
                conversations_url,
                headers=headers,
                params=conversations_params,
                timeout=10
            )
            
            if conv_response.status_code == 200:
                for channel in conv_response.json().get('channels', []):
                    # Get recent messages from DM
                    history_url = 'https://slack.com/api/conversations.history'
                    history_params = {
                        'channel': channel['id'],
                        'oldest': str(cutoff_timestamp),
                        'limit': 50
                    }
                    
                    history_response = requests.get(
                        history_url,
                        headers=headers,
                        params=history_params,
                        timeout=10
                    )
                    
                    if history_response.status_code == 200:
                        for msg in history_response.json().get('messages', []):
                            # Skip messages from self
                            if msg.get('user') == user_id:
                                continue
                            
                            msg_timestamp = float(msg.get('ts', 0))
                            messages.append({
                                'id': f"{channel['id']}_{msg.get('ts')}",
                                'platform': 'slack',
                                'type': 'dm',
                                'from_user': msg.get('user', 'Unknown'),
                                'from_id': msg.get('user'),
                                'channel': 'Direct Message',
                                'channel_id': channel['id'],
                                'text': msg.get('text', '')[:500],
                                'timestamp': datetime.fromtimestamp(msg_timestamp).isoformat(),
                                'link': f"https://slack.com/app_redirect?channel={channel['id']}&message={msg.get('ts')}",
                                'raw': msg
                            })
            
            logger.info(f"Collected {len(messages)} Slack messages")
            return messages
            
        except Exception as e:
            logger.error(f"Error collecting Slack messages: {e}")
            return []
    
    async def collect_discord(self, hours_back: int = 24) -> List[Dict[str, Any]]:
        """Collect Discord mentions and DMs."""
        credentials = self._get_credentials('discord')
        if not credentials.get('access_token'):
            logger.warning("Discord not connected - please login in the dashboard")
            return []
        
        try:
            messages = []
            token = credentials['access_token']
            # For OAuth tokens, use 'Bearer', for bot tokens use 'Bot'
            auth_type = 'Bearer' if not token.startswith('Bot ') else ''
            headers = {'Authorization': f'{auth_type} {token}'.strip()}
            
            # Get current user
            user_response = requests.get(
                'https://discord.com/api/v10/users/@me',
                headers=headers,
                timeout=10
            )
            
            if user_response.status_code != 200:
                logger.error("Failed to authenticate with Discord")
                return []
            
            user_id = user_response.json().get('id')
            cutoff_time = datetime.now() - timedelta(hours=hours_back)
            
            # Get guilds (servers)
            guilds_response = requests.get(
                'https://discord.com/api/v10/users/@me/guilds',
                headers=headers,
                timeout=10
            )
            
            if guilds_response.status_code == 200:
                for guild in guilds_response.json():
                    guild_id = guild.get('id')
                    
                    # Get channels in guild
                    channels_response = requests.get(
                        f'https://discord.com/api/v10/guilds/{guild_id}/channels',
                        headers=headers,
                        timeout=10
                    )
                    
                    if channels_response.status_code == 200:
                        for channel in channels_response.json():
                            # Only text channels
                            if channel.get('type') not in [0, 5]:  # 0=text, 5=announcement
                                continue
                            
                            channel_id = channel.get('id')
                            
                            # Get recent messages
                            try:
                                messages_response = requests.get(
                                    f'https://discord.com/api/v10/channels/{channel_id}/messages',
                                    headers=headers,
                                    params={'limit': 100},
                                    timeout=10
                                )
                                
                                if messages_response.status_code == 200:
                                    for msg in messages_response.json():
                                        msg_time = datetime.fromisoformat(msg.get('timestamp').replace('Z', '+00:00'))
                                        
                                        if msg_time < cutoff_time:
                                            continue
                                        
                                        # Check if message mentions user
                                        mentions = msg.get('mentions', [])
                                        is_mentioned = any(m.get('id') == user_id for m in mentions)
                                        
                                        # Check if message is reply to user
                                        is_reply = False
                                        if msg.get('referenced_message'):
                                            ref_author = msg['referenced_message'].get('author', {})
                                            is_reply = ref_author.get('id') == user_id
                                        
                                        if is_mentioned or is_reply:
                                            author = msg.get('author', {})
                                            messages.append({
                                                'id': msg.get('id'),
                                                'platform': 'discord',
                                                'type': 'mention' if is_mentioned else 'reply',
                                                'from_user': f"{author.get('username')}#{author.get('discriminator')}",
                                                'from_id': author.get('id'),
                                                'channel': channel.get('name', 'Unknown'),
                                                'channel_id': channel_id,
                                                'guild': guild.get('name', 'Unknown'),
                                                'guild_id': guild_id,
                                                'text': msg.get('content', '')[:500],
                                                'timestamp': msg_time.isoformat(),
                                                'link': f"https://discord.com/channels/{guild_id}/{channel_id}/{msg.get('id')}",
                                                'raw': msg
                                            })
                            except Exception as e:
                                logger.debug(f"Could not fetch messages from channel {channel_id}: {e}")
                                continue
            
            # Get DM channels
            dm_response = requests.get(
                'https://discord.com/api/v10/users/@me/channels',
                headers=headers,
                timeout=10
            )
            
            if dm_response.status_code == 200:
                for dm_channel in dm_response.json():
                    if dm_channel.get('type') != 1:  # 1 = DM
                        continue
                    
                    channel_id = dm_channel.get('id')
                    
                    try:
                        messages_response = requests.get(
                            f'https://discord.com/api/v10/channels/{channel_id}/messages',
                            headers=headers,
                            params={'limit': 50},
                            timeout=10
                        )
                        
                        if messages_response.status_code == 200:
                            for msg in messages_response.json():
                                # Skip own messages
                                if msg.get('author', {}).get('id') == user_id:
                                    continue
                                
                                msg_time = datetime.fromisoformat(msg.get('timestamp').replace('Z', '+00:00'))
                                
                                if msg_time < cutoff_time:
                                    continue
                                
                                author = msg.get('author', {})
                                messages.append({
                                    'id': msg.get('id'),
                                    'platform': 'discord',
                                    'type': 'dm',
                                    'from_user': f"{author.get('username')}#{author.get('discriminator')}",
                                    'from_id': author.get('id'),
                                    'channel': 'Direct Message',
                                    'channel_id': channel_id,
                                    'text': msg.get('content', '')[:500],
                                    'timestamp': msg_time.isoformat(),
                                    'link': f"https://discord.com/channels/@me/{channel_id}/{msg.get('id')}",
                                    'raw': msg
                                })
                    except Exception as e:
                        logger.debug(f"Could not fetch DM channel {channel_id}: {e}")
                        continue
            
            logger.info(f"Collected {len(messages)} Discord messages")
            return messages
            
        except Exception as e:
            logger.error(f"Error collecting Discord messages: {e}")
            return []
