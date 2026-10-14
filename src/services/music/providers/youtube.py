"""YouTube Music provider implementation."""

import os
import logging
from typing import Dict, List, Any, Optional
import httpx
from rapidfuzz import fuzz
from .base import BaseMusicProvider, TrackMatch

logger = logging.getLogger(__name__)


class YouTubeProvider(BaseMusicProvider):
    """YouTube Music provider for searching and managing tracks."""

    def __init__(self, api_key: Optional[str] = None):
        """Initialize YouTube provider.

        Args:
            api_key: YouTube Data API v3 key. If not provided, uses YOUTUBE_API_KEY env var.
        """
        super().__init__('youtube')
        self.api_key = api_key or os.getenv('YOUTUBE_API_KEY')
        self.base_url = 'https://www.googleapis.com/youtube/v3'
        self.is_authenticated = bool(self.api_key)

        if not self.is_authenticated:
            logger.warning('YouTube API key not configured')

    async def search_track(self, title: str, artist: str, album: Optional[str] = None) -> Optional[TrackMatch]:
        """Search for a track on YouTube.

        Performs a search for "{title} {artist}" and returns the top result
        with confidence scoring based on title/artist matching.

        Args:
            title: Track title
            artist: Artist name
            album: Album name (optional, not used for YouTube search)

        Returns:
            TrackMatch with YouTube video ID if found
        """
        if not self.is_authenticated:
            logger.warning('YouTube provider not authenticated')
            return None

        try:
            query = f'{title} {artist}'.strip()
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f'{self.base_url}/search',
                    params={
                        'part': 'snippet',
                        'q': query,
                        'type': 'video',
                        'maxResults': 5,
                        'key': self.api_key
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()

            if not data.get('items'):
                logger.debug(f'No YouTube results for: {query}')
                return None

            # Score results and pick the best match
            best_match = None
            best_score = 0

            for item in data['items']:
                video_id = item['id']['videoId']
                snippet = item['snippet']
                video_title = snippet['title']
                channel_name = snippet['channelTitle']

                # Calculate match confidence
                title_ratio = fuzz.token_set_ratio(title.lower(), video_title.lower())
                artist_ratio = fuzz.token_set_ratio(artist.lower(), channel_name.lower())
                combined_score = (title_ratio * 0.7 + artist_ratio * 0.3) / 100

                if combined_score > best_score:
                    best_score = combined_score
                    best_match = {
                        'video_id': video_id,
                        'title': video_title,
                        'channel': channel_name,
                        'score': combined_score
                    }

            if best_match and best_score > 0.4:  # Confidence threshold
                return TrackMatch(
                    provider_id=best_match['video_id'],
                    provider='youtube',
                    title=best_match['title'],
                    artist=best_match['channel'],
                    match_confidence=best_score,
                    url=f"https://www.youtube.com/watch?v={best_match['video_id']}"
                )

            logger.debug(f'No confident match for: {query} (best score: {best_score})')
            return None

        except httpx.HTTPError as e:
            logger.error(f'YouTube search error: {e}')
            return None
        except Exception as e:
            logger.error(f'Unexpected error in YouTube search: {e}')
            return None

    async def create_playlist(self, title: str, description: Optional[str] = None) -> Optional[str]:
        """YouTube doesn't support playlist creation via API v3 in simple mode.

        This is a no-op that returns None. Playlists should be created manually
        or via OAuth with appropriate scopes.

        Args:
            title: Playlist title
            description: Playlist description

        Returns:
            None (not supported)
        """
        logger.info(f'Note: YouTube playlist creation requires OAuth setup. Playlist: {title}')
        return None

    async def add_tracks_to_playlist(self, playlist_id: str, track_ids: List[str]) -> Dict[str, Any]:
        """YouTube playlist item addition requires OAuth.

        This is a placeholder that would need OAuth implementation.

        Args:
            playlist_id: YouTube playlist ID
            track_ids: List of YouTube video IDs

        Returns:
            Dict with success=False (not implemented)
        """
        logger.warning('YouTube playlist item addition requires OAuth authentication')
        return {'success': False, 'added_count': 0, 'error': 'OAuth required'}

    async def get_playlist(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """Get YouTube playlist details.

        Args:
            playlist_id: YouTube playlist ID

        Returns:
            Playlist data
        """
        if not self.is_authenticated:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f'{self.base_url}/playlists',
                    params={
                        'part': 'snippet,contentDetails',
                        'id': playlist_id,
                        'key': self.api_key
                    },
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()

            if not data.get('items'):
                return None

            item = data['items'][0]
            return {
                'id': item['id'],
                'title': item['snippet']['title'],
                'description': item['snippet']['description'],
                'item_count': item['contentDetails']['itemCount']
            }

        except Exception as e:
            logger.error(f'Error getting YouTube playlist: {e}')
            return None

    async def authenticate(self, credentials: Dict[str, str]) -> bool:
        """Authenticate with YouTube API.

        Args:
            credentials: Dict with 'api_key' field

        Returns:
            True if API key is valid
        """
        self.api_key = credentials.get('api_key')
        if not self.api_key:
            self.is_authenticated = False
            return False

        try:
            # Test API key by making a simple request
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f'{self.base_url}/search',
                    params={
                        'part': 'snippet',
                        'q': 'test',
                        'maxResults': 1,
                        'key': self.api_key
                    },
                    timeout=5.0
                )
                self.is_authenticated = response.status_code == 200
                if self.is_authenticated:
                    logger.info('YouTube API authenticated successfully')
                else:
                    logger.warning(f'YouTube API authentication failed: {response.status_code}')

        except Exception as e:
            logger.error(f'YouTube authentication error: {e}')
            self.is_authenticated = False

        return self.is_authenticated

    def get_embed_url(self, video_id: str) -> str:
        """Get embeddable URL for YouTube video.

        Args:
            video_id: YouTube video ID

        Returns:
            Embed URL for iframe
        """
        return f'https://www.youtube.com/embed/{video_id}'

    def get_watch_url(self, video_id: str) -> str:
        """Get watch URL for YouTube video.

        Args:
            video_id: YouTube video ID

        Returns:
            Watch URL
        """
        return f'https://www.youtube.com/watch?v={video_id}'
