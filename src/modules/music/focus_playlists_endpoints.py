"""Focus Playlists API endpoints."""

import uuid
from datetime import datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
import logging
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from database import db
from services.music.playlist_generator import PlaylistGenerator
from services.music.providers.youtube import YouTubeProvider

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/focus-playlists", tags=["focus-playlists"])

# Initialize services
playlist_generator = PlaylistGenerator(db)
youtube_provider = YouTubeProvider()


# ==================== Request/Response Models ====================

class GeneratePlaylistRequest(BaseModel):
    """Request to generate a playlist."""
    mood: str
    duration_minutes: int = 60
    context: Optional[str] = None


class PlaylistTrackResponse(BaseModel):
    """Playlist track response."""
    id: str
    title: str
    artist: str
    album: Optional[str] = None
    duration_seconds: int
    position: int
    youtube_video_id: Optional[str] = None
    spotify_track_id: Optional[str] = None
    apple_music_track_id: Optional[str] = None
    match_confidence: float


class PlaylistResponse(BaseModel):
    """Playlist response."""
    id: str
    title: str
    mood: str
    description: Optional[str] = None
    duration_minutes: int
    track_count: int
    tracks: Optional[List[PlaylistTrackResponse]] = None
    created_at: str
    updated_at: str


# ==================== Endpoints ====================

@router.post("/generate")
async def generate_playlist(
    request: GeneratePlaylistRequest,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Generate a mood-based playlist.

    Args:
        request: GeneratePlaylistRequest with mood, duration, optional context

    Returns:
        Generated playlist with tracks ready for playback
    """
    try:
        # Generate playlist
        playlist = await playlist_generator.generate_playlist(
            mood=request.mood,
            duration_minutes=request.duration_minutes,
            context=request.context,
            user_id='default'
        )

        if not playlist:
            raise HTTPException(
                status_code=400,
                detail=f"Could not generate playlist for mood: {request.mood}"
            )

        # Enrich tracks with YouTube IDs in background
        background_tasks.add_task(
            _enrich_playlist_with_youtube,
            playlist['id']
        )

        return {
            'success': True,
            'playlist': playlist,
            'note': 'YouTube matching in progress. Refresh to see video IDs.'
        }

    except Exception as e:
        logger.error(f"Error generating playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _enrich_playlist_with_youtube(playlist_id: str):
    """Enrich playlist tracks with YouTube video IDs.

    Runs in background to find YouTube videos for each track.

    Args:
        playlist_id: Playlist ID to enrich
    """
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Get all tracks for this playlist
            cursor.execute("""
                SELECT id, title, artist FROM focus_playlist_tracks
                WHERE playlist_id = ? AND youtube_video_id IS NULL
                ORDER BY position
            """, (playlist_id,))

            tracks = cursor.fetchall()

            for track in tracks:
                track_id, title, artist = track

                # Search YouTube
                match = await youtube_provider.search_track(title, artist)

                if match:
                    cursor.execute("""
                        UPDATE focus_playlist_tracks
                        SET youtube_video_id = ?, match_confidence = ?
                        WHERE id = ?
                    """, (match.provider_id, match.match_confidence, track_id))

                    conn.commit()
                    logger.info(f"Matched track: {title} - {artist} -> {match.provider_id}")
                else:
                    logger.warning(f"Could not match track: {title} - {artist}")

    except Exception as e:
        logger.error(f"Error enriching playlist: {e}")


@router.get("/")
async def get_playlists(limit: int = 50) -> Dict[str, Any]:
    """Get all focus playlists for the current user.

    Args:
        limit: Maximum number of playlists to return

    Returns:
        List of playlists
    """
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, mood, description, duration_minutes, 
                       source, created_at, updated_at
                FROM focus_playlists
                WHERE user_id = 'default'
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

            playlists = []
            for row in cursor.fetchall():
                # Get track count
                cursor.execute(
                    "SELECT COUNT(*) FROM focus_playlist_tracks WHERE playlist_id = ?",
                    (row[0],)
                )
                track_count = cursor.fetchone()[0]

                playlists.append({
                    'id': row[0],
                    'title': row[1],
                    'mood': row[2],
                    'description': row[3],
                    'duration_minutes': row[4],
                    'track_count': track_count,
                    'source': row[5],
                    'created_at': row[6],
                    'updated_at': row[7]
                })

            return {'success': True, 'playlists': playlists}

    except Exception as e:
        logger.error(f"Error fetching playlists: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{playlist_id}")
async def get_playlist(playlist_id: str) -> Dict[str, Any]:
    """Get playlist details with all tracks.

    Args:
        playlist_id: ID of the playlist

    Returns:
        Playlist with all tracks
    """
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Get playlist
            cursor.execute("""
                SELECT id, title, mood, description, duration_minutes,
                       source, created_at, updated_at
                FROM focus_playlists
                WHERE id = ? AND user_id = 'default'
            """, (playlist_id,))

            playlist_row = cursor.fetchone()
            if not playlist_row:
                raise HTTPException(status_code=404, detail="Playlist not found")

            # Get tracks
            cursor.execute("""
                SELECT id, title, artist, album, duration_seconds, position,
                       youtube_video_id, spotify_track_id, apple_music_track_id,
                       match_confidence
                FROM focus_playlist_tracks
                WHERE playlist_id = ?
                ORDER BY position
            """, (playlist_id,))

            tracks = []
            for track in cursor.fetchall():
                tracks.append({
                    'id': track[0],
                    'title': track[1],
                    'artist': track[2],
                    'album': track[3],
                    'duration_seconds': track[4],
                    'position': track[5],
                    'youtube_video_id': track[6],
                    'spotify_track_id': track[7],
                    'apple_music_track_id': track[8],
                    'match_confidence': track[9]
                })

            return {
                'success': True,
                'playlist': {
                    'id': playlist_row[0],
                    'title': playlist_row[1],
                    'mood': playlist_row[2],
                    'description': playlist_row[3],
                    'duration_minutes': playlist_row[4],
                    'track_count': len(tracks),
                    'tracks': tracks,
                    'source': playlist_row[5],
                    'created_at': playlist_row[6],
                    'updated_at': playlist_row[7]
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{playlist_id}")
async def delete_playlist(playlist_id: str) -> Dict[str, Any]:
    """Delete a playlist.

    Args:
        playlist_id: ID of the playlist

    Returns:
        Success confirmation
    """
    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Delete tracks first
            cursor.execute(
                "DELETE FROM focus_playlist_tracks WHERE playlist_id = ?",
                (playlist_id,)
            )

            # Delete playlist
            cursor.execute(
                "DELETE FROM focus_playlists WHERE id = ? AND user_id = 'default'",
                (playlist_id,)
            )

            conn.commit()

            if cursor.rowcount == 0:
                raise HTTPException(status_code=404, detail="Playlist not found")

            return {'success': True, 'message': 'Playlist deleted'}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting playlist: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{playlist_id}/sync/{provider}")
async def sync_playlist_to_provider(
    playlist_id: str,
    provider: str,
    background_tasks: BackgroundTasks
) -> Dict[str, Any]:
    """Sync a playlist to external music provider (Spotify/Apple Music).

    Args:
        playlist_id: ID of the playlist
        provider: Provider name ('spotify' or 'apple_music')

    Returns:
        Sync job status
    """
    try:
        if provider not in ['spotify', 'apple_music']:
            raise HTTPException(
                status_code=400,
                detail="Provider must be 'spotify' or 'apple_music'"
            )

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Check if playlist exists
            cursor.execute(
                "SELECT title FROM focus_playlists WHERE id = ?",
                (playlist_id,)
            )
            playlist_row = cursor.fetchone()
            if not playlist_row:
                raise HTTPException(status_code=404, detail="Playlist not found")

            # Create sync job
            sync_job_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO sync_jobs
                (id, user_id, playlist_id, provider, status)
                VALUES (?, 'default', ?, ?, 'pending')
            """, (sync_job_id, playlist_id, provider))

            conn.commit()

        # Start sync in background
        background_tasks.add_task(
            _sync_playlist_background,
            playlist_id,
            provider,
            sync_job_id
        )

        return {
            'success': True,
            'sync_job_id': sync_job_id,
            'status': 'pending',
            'message': f'Playlist sync to {provider} started'
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting playlist sync: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def _sync_playlist_background(playlist_id: str, provider: str, sync_job_id: str):
    """Sync playlist to external provider in background.

    Args:
        playlist_id: Playlist ID to sync
        provider: Provider name
        sync_job_id: Sync job ID
    """
    try:
        logger.info(f"Starting sync of playlist {playlist_id} to {provider}")

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Get playlist tracks
            cursor.execute("""
                SELECT title, artist, spotify_track_id, apple_music_track_id
                FROM focus_playlist_tracks
                WHERE playlist_id = ?
                ORDER BY position
            """, (playlist_id,))

            tracks = cursor.fetchall()

            # Count matches
            matched_count = 0
            failed_count = 0

            for track in tracks:
                title, artist, spotify_id, apple_id = track

                if provider == 'spotify' and not spotify_id:
                    failed_count += 1
                elif provider == 'apple_music' and not apple_id:
                    failed_count += 1
                else:
                    matched_count += 1

            # Update sync job
            cursor.execute("""
                UPDATE sync_jobs
                SET status = 'completed', matched_tracks = ?, failed_tracks = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (matched_count, failed_count, sync_job_id))

            conn.commit()

        logger.info(f"Sync completed: {matched_count} matched, {failed_count} failed")

    except Exception as e:
        logger.error(f"Error syncing playlist: {e}")

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE sync_jobs
                SET status = 'failed', error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (str(e), sync_job_id))
            conn.commit()


@router.get("/mood-presets")
async def get_mood_presets() -> Dict[str, Any]:
    """Get all available mood presets.

    Returns:
        List of mood presets with descriptions
    """
    try:
        presets = playlist_generator.get_mood_presets()

        mood_list = [
            {
                'id': preset_id,
                'name': preset['name'],
                'description': preset['description'],
                'energy_level': preset['energy_level'],
                'default_duration_minutes': preset['default_duration_minutes']
            }
            for preset_id, preset in presets.items()
        ]

        return {'success': True, 'moods': mood_list}

    except Exception as e:
        logger.error(f"Error fetching mood presets: {e}")
        raise HTTPException(status_code=500, detail=str(e))
