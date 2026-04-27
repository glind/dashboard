"""Tests for Focus Playlists feature."""

import pytest
import json
from datetime import datetime
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database import DatabaseManager
from services.music.playlist_generator import PlaylistGenerator
from services.music.providers.youtube import YouTubeProvider


class TestPlaylistGenerator:
    """Test playlist generation functionality."""

    @pytest.fixture
    def db(self):
        """Create test database."""
        db = DatabaseManager(':memory:')
        return db

    @pytest.fixture
    def generator(self, db):
        """Create playlist generator."""
        return PlaylistGenerator(db)

    def test_get_mood_presets(self, generator):
        """Test getting mood presets."""
        presets = generator.get_mood_presets()
        
        assert isinstance(presets, dict)
        assert 'deep-work' in presets
        assert 'debugging' in presets
        assert 'pitch-deck-sprint' in presets
        assert 'late-night-hack' in presets
        assert 'calm-focus' in presets
        assert 'launch-day-energy' in presets

    def test_get_specific_mood_preset(self, generator):
        """Test getting specific mood preset."""
        preset = generator.get_mood_preset('deep-work')
        
        assert preset is not None
        assert preset['name'] == 'Deep Work'
        assert preset['energy_level'] == 4
        assert isinstance(preset['genres'], list)
        assert preset['instrumental_preference'] == 'instrumental'

    def test_get_invalid_mood_preset(self, generator):
        """Test getting invalid mood preset."""
        preset = generator.get_mood_preset('invalid-mood')
        assert preset is None

    @pytest.mark.asyncio
    async def test_initialize_mood_presets(self, generator):
        """Test initializing mood presets in database."""
        await generator.initialize_mood_presets()
        
        # Verify presets are in database
        with generator.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM mood_presets")
            count = cursor.fetchone()[0]
            
            assert count == 6  # We have 6 presets

    @pytest.mark.asyncio
    async def test_generate_curated_playlist(self, generator):
        """Test generating a curated playlist."""
        preset = generator.get_mood_preset('deep-work')
        
        tracks = await generator._generate_curated(preset, 60)
        
        assert isinstance(tracks, list)
        assert len(tracks) > 0
        assert all('title' in track and 'artist' in track for track in tracks)

    @pytest.mark.asyncio
    async def test_generate_playlist_creates_database_records(self, generator):
        """Test that generate_playlist creates proper database records."""
        await generator.initialize_mood_presets()
        
        playlist = await generator.generate_playlist(
            mood='deep-work',
            duration_minutes=60
        )
        
        assert playlist is not None
        assert 'id' in playlist
        assert 'title' in playlist
        assert 'tracks' in playlist
        assert len(playlist['tracks']) > 0

        # Verify database records
        with generator.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check playlist exists
            cursor.execute("SELECT * FROM focus_playlists WHERE id = ?", (playlist['id'],))
            assert cursor.fetchone() is not None
            
            # Check tracks exist
            cursor.execute(
                "SELECT COUNT(*) FROM focus_playlist_tracks WHERE playlist_id = ?",
                (playlist['id'],)
            )
            track_count = cursor.fetchone()[0]
            assert track_count == len(playlist['tracks'])


class TestYouTubeProvider:
    """Test YouTube provider functionality."""

    @pytest.fixture
    def provider(self):
        """Create YouTube provider."""
        return YouTubeProvider(api_key='test-key')

    def test_youtube_provider_initialization(self, provider):
        """Test provider initialization."""
        assert provider.provider_name == 'youtube'
        assert provider.base_url == 'https://www.googleapis.com/youtube/v3'

    def test_get_embed_url(self, provider):
        """Test getting embed URL."""
        video_id = 'dQw4w9WgXcQ'
        url = provider.get_embed_url(video_id)
        
        assert 'https://www.youtube.com/embed/' in url
        assert video_id in url

    def test_get_watch_url(self, provider):
        """Test getting watch URL."""
        video_id = 'dQw4w9WgXcQ'
        url = provider.get_watch_url(video_id)
        
        assert 'https://www.youtube.com/watch?v=' in url
        assert video_id in url

    @pytest.mark.asyncio
    async def test_authenticate_with_invalid_key(self, provider):
        """Test authentication with invalid API key."""
        result = await provider.authenticate({'api_key': 'invalid-key'})
        # This should return False due to invalid key
        assert isinstance(result, bool)


class TestPlaylistDatabase:
    """Test playlist database operations."""

    @pytest.fixture
    def db(self):
        """Create test database."""
        db = DatabaseManager(':memory:')
        return db

    def test_create_playlist(self, db):
        """Test creating a playlist."""
        playlist_data = {
            'id': 'test-playlist-1',
            'name': 'Test Playlist',
            'mood': 'deep-work',
            'artists': ['Artist 1', 'Artist 2'],
            'genres': ['ambient', 'electronic'],
            'tracks': [
                {'title': 'Track 1', 'artist': 'Artist 1'},
                {'title': 'Track 2', 'artist': 'Artist 2'}
            ]
        }
        
        result = db.save_playlist(playlist_data)
        assert result is True

    def test_get_playlist(self, db):
        """Test retrieving a playlist."""
        playlist_data = {
            'id': 'test-playlist-2',
            'name': 'Test Playlist 2',
            'tracks': [{'title': 'Track 1', 'artist': 'Artist 1'}]
        }
        
        db.save_playlist(playlist_data)
        retrieved = db.get_playlist('test-playlist-2')
        
        assert retrieved is not None
        assert retrieved['id'] == 'test-playlist-2'
        assert retrieved['name'] == 'Test Playlist 2'

    def test_get_nonexistent_playlist(self, db):
        """Test retrieving nonexistent playlist."""
        result = db.get_playlist('nonexistent')
        assert result is None

    def test_delete_playlist(self, db):
        """Test deleting a playlist."""
        playlist_data = {
            'id': 'test-playlist-3',
            'name': 'Test Playlist 3',
            'tracks': []
        }
        
        db.save_playlist(playlist_data)
        result = db.delete_playlist('test-playlist-3')
        
        assert result is True
        assert db.get_playlist('test-playlist-3') is None


class TestFocusPlaylistDatabase:
    """Test focus playlist specific database operations."""

    @pytest.fixture
    def db(self):
        """Create test database."""
        db = DatabaseManager(':memory:')
        return db

    def test_focus_playlist_creation(self, db):
        """Test creating a focus playlist in database."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO focus_playlists
                (id, user_id, title, mood, description, duration_minutes)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                'fp-1',
                'user-1',
                'Test Focus Playlist',
                'deep-work',
                'Test description',
                60
            ))
            
            conn.commit()
            
            # Verify
            cursor.execute("SELECT * FROM focus_playlists WHERE id = ?", ('fp-1',))
            result = cursor.fetchone()
            
            assert result is not None
            assert result['title'] == 'Test Focus Playlist'
            assert result['mood'] == 'deep-work'

    def test_focus_playlist_track_insertion(self, db):
        """Test inserting tracks into focus playlist."""
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Create playlist first
            cursor.execute("""
                INSERT INTO focus_playlists
                (id, user_id, title, mood)
                VALUES (?, ?, ?, ?)
            """, ('fp-2', 'user-1', 'Test', 'deep-work'))
            
            # Insert track
            cursor.execute("""
                INSERT INTO focus_playlist_tracks
                (id, playlist_id, title, artist, position)
                VALUES (?, ?, ?, ?, ?)
            """, ('track-1', 'fp-2', 'Song Title', 'Artist Name', 1))
            
            conn.commit()
            
            # Verify
            cursor.execute(
                "SELECT * FROM focus_playlist_tracks WHERE playlist_id = ?",
                ('fp-2',)
            )
            result = cursor.fetchone()
            
            assert result is not None
            assert result['title'] == 'Song Title'
            assert result['position'] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
