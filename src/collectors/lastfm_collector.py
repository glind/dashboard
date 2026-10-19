"""
Last.fm API Collector
Fetches music data from Last.fm for the Demon theme music player
"""

import os
import logging
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Last.fm API base URL
LASTFM_API_BASE = "https://ws.audioscrobbler.com/2.0/"

# Genre/tag mappings for stations
STATION_TAGS = {
    "90s_alternative": "90s alternative",
    "gothic_rock": "gothic rock", 
    "darkwave": "darkwave",
    "musicals": "musical",
    "industrial": "industrial",
    "shoegaze": "shoegaze",
    "post_punk": "post-punk",
    "grunge": "grunge",
    "trip_hop": "trip-hop"
}


def _get_lastfm_credentials() -> Dict[str, str]:
    """Get Last.fm credentials from app_config, falling back to credentials table or environment."""
    try:
        from database import DatabaseManager
        db = DatabaseManager()
        
        # Try app_config first (new location)
        api_key = db.get_app_config('lastfm.api_key')
        if api_key:
            return {
                'api_key': api_key,
                'shared_secret': db.get_app_config('lastfm.shared_secret') or '',
                'username': db.get_app_config('lastfm.username') or ''
            }
        
        # Fallback to credentials table (legacy)
        creds = db.get_credentials('lastfm')
        if creds and creds.get('api_key'):
            return creds
    except Exception as e:
        logger.debug(f"Could not load Last.fm credentials from database: {e}")
    
    # Fallback to environment variables
    return {
        'api_key': os.getenv('LASTFM_API_KEY', ''),
        'shared_secret': os.getenv('LASTFM_SHARED_SECRET', ''),
        'username': os.getenv('LASTFM_USERNAME', '')
    }


class LastFMCollector:
    """Collector for Last.fm music data"""
    
    def __init__(self):
        creds = _get_lastfm_credentials()
        self.api_key = creds.get('api_key', '')
        self.shared_secret = creds.get('shared_secret', '')
        self.username = creds.get('username', '')
        
        if not self.api_key:
            logger.warning("Last.fm API key not configured - features will be limited")
        else:
            logger.info(f"Last.fm collector initialized for user: {self.username}")
    
    async def _make_request(self, method: str, params: Dict[str, str]) -> Optional[Dict]:
        """Make an async request to Last.fm API"""
        if not self.api_key:
            return None
            
        params.update({
            'method': method,
            'api_key': self.api_key,
            'format': 'json'
        })
        
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(LASTFM_API_BASE, params=params)
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Last.fm API error: {e}")
            return None
    
    async def get_top_tracks_by_tag(self, tag: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top tracks for a specific tag/genre"""
        data = await self._make_request('tag.gettoptracks', {
            'tag': tag,
            'limit': str(limit)
        })
        
        if not data or 'tracks' not in data:
            return []
        
        tracks = []
        for track in data.get('tracks', {}).get('track', []):
            tracks.append({
                'name': track.get('name', 'Unknown'),
                'artist': track.get('artist', {}).get('name', 'Unknown'),
                'url': track.get('url', ''),
                'listeners': track.get('listeners', '0'),
                'image': self._get_image(track.get('image', []))
            })
        
        return tracks
    
    async def get_top_artists_by_tag(self, tag: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top artists for a specific tag/genre"""
        data = await self._make_request('tag.gettopartists', {
            'tag': tag,
            'limit': str(limit)
        })
        
        if not data or 'topartists' not in data:
            return []
        
        artists = []
        for artist in data.get('topartists', {}).get('artist', []):
            artists.append({
                'name': artist.get('name', 'Unknown'),
                'url': artist.get('url', ''),
                'listeners': artist.get('listeners', '0'),
                'image': self._get_image(artist.get('image', []))
            })
        
        return artists
    
    async def get_similar_artists(self, artist: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Get similar artists"""
        data = await self._make_request('artist.getsimilar', {
            'artist': artist,
            'limit': str(limit)
        })
        
        if not data or 'similarartists' not in data:
            return []
        
        similar = []
        for artist in data.get('similarartists', {}).get('artist', []):
            similar.append({
                'name': artist.get('name', 'Unknown'),
                'url': artist.get('url', ''),
                'match': artist.get('match', '0'),
                'image': self._get_image(artist.get('image', []))
            })
        
        return similar
    
    async def get_artist_info(self, artist: str) -> Optional[Dict[str, Any]]:
        """Get detailed artist info"""
        data = await self._make_request('artist.getinfo', {
            'artist': artist
        })
        
        if not data or 'artist' not in data:
            return None
        
        artist_data = data['artist']
        return {
            'name': artist_data.get('name', 'Unknown'),
            'url': artist_data.get('url', ''),
            'listeners': artist_data.get('stats', {}).get('listeners', '0'),
            'playcount': artist_data.get('stats', {}).get('playcount', '0'),
            'bio': artist_data.get('bio', {}).get('summary', ''),
            'tags': [t.get('name') for t in artist_data.get('tags', {}).get('tag', [])],
            'similar': [s.get('name') for s in artist_data.get('similar', {}).get('artist', [])],
            'image': self._get_image(artist_data.get('image', []))
        }
    
    async def get_station_data(self, station_id: str) -> Dict[str, Any]:
        """Get data for a music station (tag-based)"""
        tag = STATION_TAGS.get(station_id, station_id)
        
        tracks = await self.get_top_tracks_by_tag(tag, limit=10)
        artists = await self.get_top_artists_by_tag(tag, limit=5)
        
        return {
            'station_id': station_id,
            'tag': tag,
            'tracks': tracks,
            'artists': artists,
            'updated_at': datetime.now().isoformat()
        }
    
    async def search_tracks(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search for tracks"""
        data = await self._make_request('track.search', {
            'track': query,
            'limit': str(limit)
        })
        
        if not data or 'results' not in data:
            return []
        
        tracks = []
        for track in data.get('results', {}).get('trackmatches', {}).get('track', []):
            tracks.append({
                'name': track.get('name', 'Unknown'),
                'artist': track.get('artist', 'Unknown'),
                'url': track.get('url', ''),
                'listeners': track.get('listeners', '0'),
                'image': self._get_image(track.get('image', []))
            })
        
        return tracks
    
    def _get_image(self, images: List[Dict], size: str = 'large') -> str:
        """Extract image URL from Last.fm image array"""
        if not images:
            return ''
        
        # Try to get requested size, fall back to any available
        for img in images:
            if img.get('size') == size and img.get('#text'):
                return img['#text']
        
        # Fall back to last (usually largest) image
        for img in reversed(images):
            if img.get('#text'):
                return img['#text']
        
        return ''


# Singleton instance
_collector: Optional[LastFMCollector] = None

def get_lastfm_collector() -> LastFMCollector:
    """Get the Last.fm collector singleton"""
    global _collector
    if _collector is None or not _collector.api_key:  # re-read creds until a key is configured
        _collector = LastFMCollector()
    return _collector
