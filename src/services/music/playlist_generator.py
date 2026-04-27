"""Playlist generation service using AI and mood-based curation."""

import uuid
import logging
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import httpx
import json
from pathlib import Path

logger = logging.getLogger(__name__)


# Predefined mood presets
MOOD_PRESETS = {
    'deep-work': {
        'id': 'deep-work',
        'name': 'Deep Work',
        'description': 'Focus music for intense, uninterrupted work sessions',
        'energy_level': 4,
        'genres': ['ambient', 'electronic', 'minimalist', 'post-rock'],
        'tempo_range': '60-100',
        'instrumental_preference': 'instrumental',
        'default_duration_minutes': 90
    },
    'debugging': {
        'id': 'debugging',
        'name': 'Debugging',
        'description': 'Steady, concentration-friendly music for problem-solving',
        'energy_level': 5,
        'genres': ['lo-fi hip hop', 'chill electronic', 'ambient jazz'],
        'tempo_range': '85-110',
        'instrumental_preference': 'instrumental',
        'default_duration_minutes': 60
    },
    'pitch-deck-sprint': {
        'id': 'pitch-deck-sprint',
        'name': 'Pitch Deck Sprint',
        'description': 'Energetic, motivating music for high-energy creative work',
        'energy_level': 8,
        'genres': ['electronic', 'funk', 'indie rock', 'synthwave'],
        'tempo_range': '120-140',
        'instrumental_preference': 'mixed',
        'default_duration_minutes': 45
    },
    'late-night-hack': {
        'id': 'late-night-hack',
        'name': 'Late Night Hack',
        'description': 'Atmospheric, late-night coding vibes',
        'energy_level': 6,
        'genres': ['synthwave', 'vaporwave', 'chillwave', 'experimental'],
        'tempo_range': '90-120',
        'instrumental_preference': 'instrumental',
        'default_duration_minutes': 120
    },
    'calm-focus': {
        'id': 'calm-focus',
        'name': 'Calm Focus',
        'description': 'Peaceful, meditative background for mindful work',
        'energy_level': 2,
        'genres': ['ambient', 'classical', 'meditation', 'nature sounds'],
        'tempo_range': '40-80',
        'instrumental_preference': 'instrumental',
        'default_duration_minutes': 90
    },
    'launch-day-energy': {
        'id': 'launch-day-energy',
        'name': 'Launch Day Energy',
        'description': 'Uplifting, celebratory music for important moments',
        'energy_level': 9,
        'genres': ['pop', 'indie pop', 'dance', 'electronic'],
        'tempo_range': '130-150',
        'instrumental_preference': 'mixed',
        'default_duration_minutes': 60
    }
}


class PlaylistGenerator:
    """Generate mood-based playlists using AI or predefined track lists."""

    def __init__(self, db):
        """Initialize playlist generator.

        Args:
            db: DatabaseManager instance
        """
        self.db = db
        self.ollama_host = os.getenv('OLLAMA_HOST', 'http://localhost:11434')
        self.use_ai = os.getenv('ENABLE_PLAYLIST_AI', 'false').lower() == 'true'

    def get_mood_presets(self) -> Dict[str, Dict[str, Any]]:
        """Get all available mood presets."""
        return MOOD_PRESETS

    def get_mood_preset(self, mood_id: str) -> Optional[Dict[str, Any]]:
        """Get a specific mood preset."""
        return MOOD_PRESETS.get(mood_id)

    async def initialize_mood_presets(self):
        """Initialize mood presets in the database."""
        try:
            for mood_id, preset in MOOD_PRESETS.items():
                with self.db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("""
                        INSERT OR IGNORE INTO mood_presets 
                        (id, name, description, energy_level, genres, tempo_range,
                         instrumental_preference, default_duration_minutes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        preset['id'],
                        preset['name'],
                        preset['description'],
                        preset['energy_level'],
                        json.dumps(preset['genres']),
                        preset['tempo_range'],
                        preset['instrumental_preference'],
                        preset['default_duration_minutes']
                    ))
                    conn.commit()
                    
            logger.info('Mood presets initialized in database')
        except Exception as e:
            logger.error(f'Error initializing mood presets: {e}')

    async def generate_playlist(
        self,
        mood: str,
        duration_minutes: int,
        context: Optional[str] = None,
        user_id: str = 'default'
    ) -> Optional[Dict[str, Any]]:
        """Generate a mood-based playlist.

        Args:
            mood: Mood preset ID
            duration_minutes: Target playlist duration
            context: Additional context/prompt for AI generation
            user_id: User ID

        Returns:
            Playlist dict with tracks, or None if generation failed
        """
        preset = self.get_mood_preset(mood)
        if not preset:
            logger.error(f'Unknown mood preset: {mood}')
            return None

        try:
            # Generate track list using AI if enabled, otherwise use curated list
            if self.use_ai and context:
                tracks = await self._generate_with_ai(preset, duration_minutes, context)
            else:
                tracks = await self._generate_curated(preset, duration_minutes)

            if not tracks:
                logger.warning(f'No tracks generated for mood: {mood}')
                return None

            # Create playlist record
            playlist_id = str(uuid.uuid4())
            playlist_title = f"{preset['name']} - {duration_minutes}min"

            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO focus_playlists 
                    (id, user_id, title, mood, description, duration_minutes, source)
                    VALUES (?, ?, ?, ?, ?, ?, 'buildly')
                """, (
                    playlist_id,
                    user_id,
                    playlist_title,
                    mood,
                    f"Generated {preset['name']} playlist",
                    duration_minutes
                ))

                # Insert tracks
                for position, track in enumerate(tracks, 1):
                    track_id = str(uuid.uuid4())
                    cursor.execute("""
                        INSERT INTO focus_playlist_tracks
                        (id, playlist_id, title, artist, album, duration_seconds, position,
                         match_confidence)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        track_id,
                        playlist_id,
                        track['title'],
                        track['artist'],
                        track.get('album'),
                        track.get('duration_seconds', 180),
                        position,
                        track.get('match_confidence', 0.5)
                    ))

                conn.commit()

            logger.info(f'Generated playlist: {playlist_title} with {len(tracks)} tracks')

            return {
                'id': playlist_id,
                'title': playlist_title,
                'mood': mood,
                'duration_minutes': duration_minutes,
                'track_count': len(tracks),
                'tracks': tracks,
                'created_at': datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f'Error generating playlist: {e}')
            return None

    async def _generate_with_ai(
        self,
        preset: Dict[str, Any],
        duration_minutes: int,
        context: str
    ) -> List[Dict[str, Any]]:
        """Generate playlist using AI/LLM.

        Args:
            preset: Mood preset
            duration_minutes: Target duration
            context: Additional context

        Returns:
            List of track dicts with title and artist
        """
        try:
            prompt = f"""Generate a {duration_minutes}-minute playlist for: {preset['name']}

Context: {context}

Requirements:
- Genres: {', '.join(preset['genres'])}
- Instrumental preference: {preset['instrumental_preference']}
- Energy level: {preset['energy_level']}/10
- Tempo: {preset['tempo_range']} BPM

Format your response as a JSON array with objects containing "title" and "artist" fields.
Generate approximately {max(5, duration_minutes // 4)} tracks (assuming ~4 minutes per track).
Return ONLY valid JSON, no other text.

Example format:
[
  {{"title": "Track Name", "artist": "Artist Name"}},
  {{"title": "Another Track", "artist": "Another Artist"}}
]"""

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f'{self.ollama_host}/api/generate',
                    json={
                        'model': 'mistral',
                        'prompt': prompt,
                        'stream': False,
                        'temperature': 0.7
                    },
                    timeout=30.0
                )
                response.raise_for_status()
                data = response.json()

            # Parse response
            response_text = data.get('response', '').strip()
            
            # Extract JSON from response
            try:
                # Find JSON array in response
                start_idx = response_text.find('[')
                end_idx = response_text.rfind(']') + 1
                if start_idx >= 0 and end_idx > start_idx:
                    json_str = response_text[start_idx:end_idx]
                    tracks = json.loads(json_str)
                    return tracks[:20]  # Limit to 20 tracks
            except json.JSONDecodeError:
                logger.warning('Failed to parse AI-generated playlist JSON')
                return []

            return []

        except Exception as e:
            logger.error(f'AI playlist generation error: {e}')
            return []

    async def _generate_curated(
        self,
        preset: Dict[str, Any],
        duration_minutes: int
    ) -> List[Dict[str, Any]]:
        """Generate playlist using curated track list for the mood.

        Args:
            preset: Mood preset
            duration_minutes: Target duration

        Returns:
            List of track dicts with title and artist
        """
        # Curated track lists for each mood
        curated_tracks = {
            'deep-work': [
                {'title': 'Bloom', 'artist': 'The Midnight'},
                {'title': 'Weightless', 'artist': 'Marconi Union'},
                {'title': 'Teardrop', 'artist': 'Massive Attack'},
                {'title': 'Arrival of the Birds', 'artist': 'Sigur Rós'},
                {'title': 'Untitled', 'artist': 'Ólafur Arnalds'},
                {'title': 'Electric Feel', 'artist': 'MGMT'},
                {'title': 'Glass Animals', 'artist': 'Porcupine Tree'},
                {'title': 'Crystallised', 'artist': 'The xx'},
                {'title': 'Elegant People', 'artist': 'Jon Hopkins'},
                {'title': 'Airstreams', 'artist': 'Jon Hopkins'},
            ],
            'debugging': [
                {'title': 'Chill Vibes', 'artist': 'Lofi Girl'},
                {'title': 'Background Chill', 'artist': 'Sleepy Fish'},
                {'title': 'Ambient Study', 'artist': 'Study MD'},
                {'title': 'Lo-Fi Hip Hop', 'artist': 'Chillhop Essentials'},
                {'title': 'Peaceful Piano', 'artist': 'Soft Piano'},
                {'title': 'Jazz Relaxation', 'artist': 'Modern Jazz'},
                {'title': 'Cafe Ambient', 'artist': 'Ambient Cafe'},
                {'title': 'Study Music', 'artist': 'Focus Sounds'},
            ],
            'pitch-deck-sprint': [
                {'title': 'Blinding Lights', 'artist': 'The Weeknd'},
                {'title': 'Take On Me', 'artist': 'a-ha'},
                {'title': 'Mr. Brightside', 'artist': 'The Killers'},
                {'title': 'Such Great Heights', 'artist': 'The Postal Service'},
                {'title': 'Electric' , 'artist': 'Alina Baraz'},
                {'title': 'Midnight City', 'artist': 'M83'},
                {'title': 'Nightcall', 'artist': 'Kavinsky'},
                {'title': 'Pursuit', 'artist': 'Gesaffelstein'},
            ],
            'late-night-hack': [
                {'title': 'Neon Lights', 'artist': 'Kavinsky'},
                {'title': 'A Thing Called Truth', 'artist': 'Carpenter Brut'},
                {'title': 'The Less I Know The Better', 'artist': 'Tame Impala'},
                {'title': 'Phantogram', 'artist': 'When the Sun Hits'},
                {'title': 'Crystalised', 'artist': 'The xx'},
                {'title': 'Digital Witness', 'artist': 'St. Vincent'},
                {'title': 'Synth 1', 'artist': 'Perturbator'},
                {'title': 'Night Drive', 'artist': 'Hotline Miami'},
            ],
            'calm-focus': [
                {'title': 'Gymnopédie No. 1', 'artist': 'Erik Satie'},
                {'title': 'Claire de Lune', 'artist': 'Claude Debussy'},
                {'title': 'Clair de lune', 'artist': 'Ludovico Einaudi'},
                {'title': 'The Luckiest', 'artist': 'Ben Folds'},
                {'title': 'Breathe', 'artist': 'Télépopmusik'},
                {'title': 'Peace', 'artist': 'Ólafur Arnalds'},
                {'title': 'Meditation', 'artist': 'Yanni'},
            ],
            'launch-day-energy': [
                {'title': 'Uptown Funk', 'artist': 'Mark Ronson ft. Bruno Mars'},
                {'title': 'Walking on Sunshine', 'artist': 'Katrina & The Waves'},
                {'title': 'Happy', 'artist': 'Pharrell Williams'},
                {'title': 'Good As Hell', 'artist': 'Lizzo'},
                {'title': 'Electric Sunsett', 'artist': 'Dua Lipa'},
                {'title': 'Don\'t Stop Me Now', 'artist': 'Queen'},
                {'title': 'Levitating', 'artist': 'Dua Lipa'},
            ]
        }

        mood_id = list(MOOD_PRESETS.keys())[0]  # Get first mood as fallback
        for mid, p in MOOD_PRESETS.items():
            if p['name'] == preset.get('name'):
                mood_id = mid
                break

        tracks = curated_tracks.get(mood_id, curated_tracks['deep-work'])
        
        # Adjust track count based on duration
        avg_track_duration = 240  # 4 minutes average
        target_track_count = max(3, duration_minutes * 60 // avg_track_duration)
        
        return tracks[:target_track_count]
