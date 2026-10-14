"""Base class for music providers."""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class TrackMatch:
    """Result of matching a track to a provider."""
    provider_id: str  # YouTube video ID, Spotify track URI, Apple Music ID, etc.
    provider: str  # 'youtube', 'spotify', 'apple_music'
    title: str
    artist: str
    album: Optional[str] = None
    duration_seconds: Optional[int] = None
    match_confidence: float = 0.0  # 0.0-1.0
    url: Optional[str] = None


class BaseMusicProvider(ABC):
    """Abstract base class for music providers."""

    def __init__(self, provider_name: str):
        """Initialize provider."""
        self.provider_name = provider_name
        self.is_authenticated = False

    @abstractmethod
    async def search_track(self, title: str, artist: str, album: Optional[str] = None) -> Optional[TrackMatch]:
        """Search for a track and return best match.

        Args:
            title: Track title
            artist: Artist name
            album: Album name (optional)

        Returns:
            TrackMatch if found, None otherwise
        """
        pass

    @abstractmethod
    async def create_playlist(self, title: str, description: Optional[str] = None) -> Optional[str]:
        """Create a new playlist.

        Args:
            title: Playlist title
            description: Playlist description

        Returns:
            Playlist ID if successful, None otherwise
        """
        pass

    @abstractmethod
    async def add_tracks_to_playlist(self, playlist_id: str, track_ids: List[str]) -> Dict[str, Any]:
        """Add tracks to a playlist.

        Args:
            playlist_id: ID of the playlist
            track_ids: List of track IDs to add

        Returns:
            Dict with 'success' bool and 'added_count' int
        """
        pass

    @abstractmethod
    async def get_playlist(self, playlist_id: str) -> Optional[Dict[str, Any]]:
        """Get playlist details.

        Args:
            playlist_id: ID of the playlist

        Returns:
            Playlist data or None
        """
        pass

    @abstractmethod
    async def authenticate(self, credentials: Dict[str, str]) -> bool:
        """Authenticate with the provider.

        Args:
            credentials: Provider-specific credentials

        Returns:
            True if authentication successful
        """
        pass

    async def validate_token(self) -> bool:
        """Check if current token is valid."""
        return self.is_authenticated

    def get_provider_name(self) -> str:
        """Get provider name."""
        return self.provider_name
