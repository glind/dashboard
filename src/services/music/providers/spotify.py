"""Spotify provider implementation (stub)."""

import os
import logging
from typing import Dict, List, Any, Optional
import httpx
from .base import BaseMusicProvider, TrackMatch

logger = logging.getLogger(__name__)


class SpotifyProvider(BaseMusicProvider):
    """Spotify provider for searching and syncing playlists."""

    def __init__(self, client_id: Optional[str] = None, client_secret: Optional[str] = None,
                 access_token: Optional[str] = None):
        """Initialize Spotify provider.

        Args:
            client_id: Spotify API client ID
            client_secret: Spotify API client secret
            access_token: User access token for playlist operations
        """
        super().__init__('spotify')
        self.client_id = client_id or os.getenv('SPOTIFY_CLIENT_ID')
        self.client_secret = client_secret or os.getenv('SPOTIFY_CLIENT_SECRET')
        self.access_token = access_token
        self.base_url = 'https://api.spotify.com/v1'
        self.auth_url = 'https://accounts.spotify.com/api/token'
        self.is_authenticated = bool(self.access_token)

    async def search_track(self, title: str, artist: str, album: Optional[str] = None) -> Optional[TrackMatch]:
        """Search for a track on Spotify.

        Args:
            title: Track title
            artist: Artist name
            album: Album name (optional)

        Returns:
            TrackMatch if found
        """
        if not self.is_authenticated:
            logger.warning('Spotify provider not authenticated')
            return None

        try:
            query = f'track:{title} artist:{artist}'
            if album:
                query += f' album:{album}'

            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f'{self.base_url}/search',
                    params={
                        'q': query,
                        'type': 'track',
                        'limit': 5
                    },
                    headers={'Authorization': f'Bearer {self.access_token}'},
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()

            if not data['tracks']['items']:
                logger.debug(f'No Spotify results for: {query}')
                return None

            # Return best match
            track = data['tracks']['items'][0]
            return TrackMatch(
                provider_id=track['id'],
                provider='spotify',
                title=track['name'],
                artist=track['artists'][0]['name'] if track['artists'] else '',
                album=track['album']['name'] if track['album'] else None,
                duration_seconds=track.get('duration_ms', 0) // 1000,
                match_confidence=0.9,
                url=track['external_urls']['spotify']
            )

        except Exception as e:
            logger.error(f'Spotify search error: {e}')
            return None

    async def create_playlist(self, title: str, description: Optional[str] = None) -> Optional[str]:
        """Create a new playlist on Spotify.

        Args:
            title: Playlist title
            description: Playlist description

        Returns:
            Playlist ID if successful
        """
        if not self.is_authenticated:
            logger.warning('Spotify provider not authenticated')
            return None

        try:
            # This requires user context. For now, returns None.
            logger.info(f'Spotify playlist creation requires OAuth user context: {title}')
            return None

        except Exception as e:
            logger.error(f'Spotify playlist creation error: {e}')
            return None

    async def add_tracks_to_playlist(self, playlist_id: str, track_ids: List[str]) -> Dict[str, Any]:
        """Add tracks to a Spotify playlist.

        Args:
            playlist_id: Spotify playlist ID
            track_ids: List of Spotify track IDs

        Returns:
            Dict with success status
        """
        if not self.is_authenticated:
            logger.warning('Spotify provider not authenticated')
            return {'success': False, 'added_count': 0}

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f'{self.base_url}/playlists/{playlist_id}/tracks',
                    json={'uris': [f'spotify:track:{tid}' for tid in track_ids]},
                    headers={'Authorization': f'Bearer {self.access_token}'},
                    timeout=10.0
                )
                response.raise_for_status()

            return {'success': True, 'added_count': len(track_ids)}

        except Exception as e:
            logger.error(f'Spotify add tracks error: {e}')
            return {'success': False, 'added_count': 0}

    async def get_playlist(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """Get Spotify playlist details.

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            Playlist data
        """
        if not self.is_authenticated:
            return None

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f'{self.base_url}/playlists/{playlist_id}',
                    headers={'Authorization': f'Bearer {self.access_token}'},
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()

            return {
                'id': data['id'],
                'title': data['name'],
                'description': data['description'],
                'item_count': data['tracks']['total']
            }

        except Exception as e:
            logger.error(f'Spotify get playlist error: {e}')
            return None

    async def authenticate(self, credentials: Dict[str, str]) -> bool:
        """Authenticate with Spotify.

        Args:
            credentials: Dict with 'access_token' and optionally client credentials

        Returns:
            True if authentication successful
        """
        self.access_token = credentials.get('access_token')
        self.client_id = credentials.get('client_id', self.client_id)
        self.client_secret = credentials.get('client_secret', self.client_secret)

        if not self.access_token:
            self.is_authenticated = False
            return False

        try:
            # Test token by making a simple request
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f'{self.base_url}/me',
                    headers={'Authorization': f'Bearer {self.access_token}'},
                    timeout=5.0
                )
                self.is_authenticated = response.status_code == 200
                if self.is_authenticated:
                    logger.info('Spotify authenticated successfully')

        except Exception as e:
            logger.error(f'Spotify authentication error: {e}')
            self.is_authenticated = False

        return self.is_authenticated
