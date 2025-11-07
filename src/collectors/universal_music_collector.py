"""
Universal Music Collector for Personal Dashboard

Aggregates music from Apple Music, Spotify, and Amazon Music.
Creates unified playlists based on user preferences, mood, and AI recommendations.
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import os
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class UniversalTrack:
    """Represents a track from any music service."""
    id: str
    title: str
    artist: str
    album: str
    duration_ms: int
    service: str  # 'apple_music', 'spotify', 'amazon_music'
    service_id: str  # ID in the original service
    preview_url: Optional[str] = None
    artwork_url: Optional[str] = None
    release_date: Optional[str] = None
    genre: Optional[str] = None
    mood: Optional[str] = None  # 'energetic', 'calm', 'happy', 'sad', 'focused'
    energy_level: float = 0.5  # 0.0 to 1.0
    valence: float = 0.5  # 0.0 (sad) to 1.0 (happy)
    popularity: int = 0
    user_rating: Optional[int] = None  # 1-5 stars
    play_count: int = 0
    last_played: Optional[datetime] = None
    is_liked: bool = False

@dataclass
class UniversalPlaylist:
    """Represents a unified playlist across services."""
    id: str
    name: str
    description: str
    tracks: List[UniversalTrack]
    created_at: datetime
    updated_at: datetime
    mood: Optional[str] = None
    created_by: str = 'user'  # 'user' or 'ai'
    total_duration_ms: int = 0
    services_used: List[str] = None

class UniversalMusicCollector:
    """Aggregates music from multiple streaming services."""
    
    def __init__(self):
        self.apple_music_token = os.getenv('APPLE_MUSIC_TOKEN')
        self.spotify_token = os.getenv('SPOTIFY_TOKEN')
        self.amazon_music_token = os.getenv('AMAZON_MUSIC_TOKEN')
        
        # Database for storing unified music library
        try:
            from database import DatabaseManager
            self.db = DatabaseManager()
        except ImportError:
            self.db = None
            logger.warning("Database not available")
        
        # Mood to audio features mapping
        self.mood_profiles = {
            'energetic': {'energy_min': 0.7, 'valence_min': 0.5, 'tempo_min': 120},
            'calm': {'energy_max': 0.4, 'valence_min': 0.3, 'tempo_max': 100},
            'happy': {'valence_min': 0.7, 'energy_min': 0.5},
            'sad': {'valence_max': 0.4, 'energy_max': 0.4},
            'focused': {'energy_min': 0.4, 'energy_max': 0.7, 'valence_min': 0.3, 'valence_max': 0.7},
            'party': {'energy_min': 0.8, 'valence_min': 0.7, 'tempo_min': 130},
            'workout': {'energy_min': 0.8, 'tempo_min': 140},
            'sleep': {'energy_max': 0.3, 'valence_max': 0.5, 'tempo_max': 80},
            'romantic': {'valence_min': 0.6, 'energy_max': 0.5},
            'study': {'energy_min': 0.3, 'energy_max': 0.6, 'valence_min': 0.4, 'valence_max': 0.6}
        }
    
    async def get_available_services(self) -> List[str]:
        """Check which music services are configured."""
        services = []
        if self.apple_music_token:
            services.append('apple_music')
        if self.spotify_token:
            services.append('spotify')
        if self.amazon_music_token:
            services.append('amazon_music')
        return services
    
    async def aggregate_liked_tracks(self) -> List[UniversalTrack]:
        """Aggregate liked/favorited tracks from all services."""
        all_tracks = []
        services = await self.get_available_services()
        
        tasks = []
        if 'spotify' in services:
            tasks.append(self._get_spotify_liked_tracks())
        if 'apple_music' in services:
            tasks.append(self._get_apple_music_liked_tracks())
        if 'amazon_music' in services:
            tasks.append(self._get_amazon_music_liked_tracks())
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, list):
                    all_tracks.extend(result)
                elif isinstance(result, Exception):
                    logger.error(f"Error fetching liked tracks: {result}")
        
        # Deduplicate by (title, artist)
        seen = set()
        unique_tracks = []
        for track in all_tracks:
            key = (track.title.lower(), track.artist.lower())
            if key not in seen:
                seen.add(key)
                unique_tracks.append(track)
        
        return unique_tracks
    
    async def create_mood_playlist(
        self, 
        mood: str, 
        max_tracks: int = 30,
        use_ai_recommendations: bool = True
    ) -> UniversalPlaylist:
        """Create a playlist based on mood across all services."""
        # Get all liked tracks
        all_tracks = await self.aggregate_liked_tracks()
        
        # Filter by mood profile
        mood_profile = self.mood_profiles.get(mood, {})
        filtered_tracks = []
        
        for track in all_tracks:
            matches_mood = True
            
            if 'energy_min' in mood_profile and track.energy_level < mood_profile['energy_min']:
                matches_mood = False
            if 'energy_max' in mood_profile and track.energy_level > mood_profile['energy_max']:
                matches_mood = False
            if 'valence_min' in mood_profile and track.valence < mood_profile['valence_min']:
                matches_mood = False
            if 'valence_max' in mood_profile and track.valence > mood_profile['valence_max']:
                matches_mood = False
            
            if matches_mood:
                filtered_tracks.append(track)
        
        # Sort by user preferences (liked tracks first, then by play count)
        filtered_tracks.sort(key=lambda t: (t.is_liked, t.play_count, t.popularity), reverse=True)
        
        # Limit to max_tracks
        selected_tracks = filtered_tracks[:max_tracks]
        
        # Get AI recommendations to fill if needed
        if use_ai_recommendations and len(selected_tracks) < max_tracks:
            ai_tracks = await self._get_ai_recommendations(mood, max_tracks - len(selected_tracks), all_tracks)
            selected_tracks.extend(ai_tracks)
        
        # Calculate total duration
        total_duration = sum(t.duration_ms for t in selected_tracks)
        
        # Determine which services were used
        services_used = list(set(t.service for t in selected_tracks))
        
        playlist = UniversalPlaylist(
            id=f"mood_{mood}_{datetime.now().timestamp()}",
            name=f"{mood.capitalize()} Mix",
            description=f"A {mood} playlist created from your favorite tracks across {', '.join(services_used)}",
            tracks=selected_tracks,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            mood=mood,
            created_by='ai' if use_ai_recommendations else 'user',
            total_duration_ms=total_duration,
            services_used=services_used
        )
        
        # Save to database
        if self.db:
            await self._save_playlist(playlist)
        
        return playlist
    
    async def create_custom_playlist(
        self,
        name: str,
        criteria: Dict[str, Any],
        max_tracks: int = 50
    ) -> UniversalPlaylist:
        """Create a custom playlist with specific criteria."""
        all_tracks = await self.aggregate_liked_tracks()
        filtered_tracks = []
        
        for track in all_tracks:
            matches = True
            
            # Filter by criteria
            if 'genres' in criteria and track.genre:
                if track.genre not in criteria['genres']:
                    matches = False
            
            if 'artists' in criteria:
                if track.artist not in criteria['artists']:
                    matches = False
            
            if 'min_popularity' in criteria:
                if track.popularity < criteria['min_popularity']:
                    matches = False
            
            if 'liked_only' in criteria and criteria['liked_only']:
                if not track.is_liked:
                    matches = False
            
            if 'services' in criteria:
                if track.service not in criteria['services']:
                    matches = False
            
            if matches:
                filtered_tracks.append(track)
        
        # Sort and limit
        filtered_tracks.sort(key=lambda t: (t.is_liked, t.play_count, t.popularity), reverse=True)
        selected_tracks = filtered_tracks[:max_tracks]
        
        total_duration = sum(t.duration_ms for t in selected_tracks)
        services_used = list(set(t.service for t in selected_tracks))
        
        playlist = UniversalPlaylist(
            id=f"custom_{name}_{datetime.now().timestamp()}",
            name=name,
            description=criteria.get('description', f"Custom playlist: {name}"),
            tracks=selected_tracks,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            created_by='user',
            total_duration_ms=total_duration,
            services_used=services_used
        )
        
        if self.db:
            await self._save_playlist(playlist)
        
        return playlist
    
    async def _get_spotify_liked_tracks(self) -> List[UniversalTrack]:
        """Fetch liked tracks from Spotify."""
        # TODO: Implement Spotify API integration
        # This is a placeholder - you'll need to implement OAuth and API calls
        logger.info("Spotify liked tracks fetch not yet implemented")
        return []
    
    async def _get_apple_music_liked_tracks(self) -> List[UniversalTrack]:
        """Fetch liked tracks from Apple Music."""
        # TODO: Implement Apple Music API integration
        logger.info("Apple Music liked tracks fetch not yet implemented")
        return []
    
    async def _get_amazon_music_liked_tracks(self) -> List[UniversalTrack]:
        """Fetch liked tracks from Amazon Music."""
        # TODO: Implement Amazon Music API integration
        logger.info("Amazon Music liked tracks fetch not yet implemented")
        return []
    
    async def _get_ai_recommendations(
        self, 
        mood: str, 
        count: int,
        existing_tracks: List[UniversalTrack]
    ) -> List[UniversalTrack]:
        """Get AI-powered track recommendations based on mood and existing tracks."""
        # TODO: Implement AI recommendations using user's listening history
        # and the Ollama model to find similar tracks
        logger.info(f"AI recommendations for mood '{mood}' not yet implemented")
        return []
    
    async def _save_playlist(self, playlist: UniversalPlaylist):
        """Save playlist to database."""
        if not self.db:
            return
        
        try:
            # Save playlist metadata
            playlist_data = {
                'id': playlist.id,
                'name': playlist.name,
                'description': playlist.description,
                'mood': playlist.mood,
                'created_by': playlist.created_by,
                'created_at': playlist.created_at.isoformat(),
                'updated_at': playlist.updated_at.isoformat(),
                'total_duration_ms': playlist.total_duration_ms,
                'services_used': json.dumps(playlist.services_used),
                'track_count': len(playlist.tracks),
                'tracks': json.dumps([asdict(t) for t in playlist.tracks])
            }
            
            # You'll need to add this method to DatabaseManager
            # self.db.save_universal_playlist(playlist_data)
            logger.info(f"Saved playlist: {playlist.name}")
        except Exception as e:
            logger.error(f"Error saving playlist: {e}")
    
    async def get_saved_playlists(self) -> List[UniversalPlaylist]:
        """Retrieve all saved playlists."""
        # TODO: Implement database retrieval
        logger.info("Playlist retrieval not yet implemented")
        return []
