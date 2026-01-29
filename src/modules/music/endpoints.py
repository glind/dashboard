from datetime import datetime
import uuid
import json
import logging

from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# Import database manager
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from database import DatabaseManager

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/music", tags=["music"])

# Initialize database manager
db = DatabaseManager()

@router.get("/playlists")
async def get_playlists():
    """Get all saved playlists from database."""
    playlists = db.get_playlists()
    return {"playlists": playlists}

@router.get("/playlists/{playlist_id}")
async def get_playlist(playlist_id: str):
    """Get a single playlist by ID."""
    playlist = db.get_playlist(playlist_id)
    if not playlist:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return {"playlist": playlist}

@router.delete("/playlists/{playlist_id}")
async def delete_playlist(playlist_id: str):
    """Delete a playlist from database."""
    success = db.delete_playlist(playlist_id)
    if not success:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return {"success": True, "message": "Playlist deleted"}

class SavePlaylistRequest(BaseModel):
    id: Optional[str] = None
    name: str
    mood: Optional[str] = None
    artists: Optional[List[str]] = None
    genres: Optional[List[str]] = None
    tracks: List[Dict[str, Any]]

@router.post("/playlists")
async def save_playlist(request: SavePlaylistRequest):
    """Save a playlist to the database."""
    playlist_id = request.id or str(uuid.uuid4())
    playlist_data = {
        "id": playlist_id,
        "name": request.name,
        "mood": request.mood,
        "artists": request.artists or [],
        "genres": request.genres or [],
        "tracks": request.tracks
    }
    success = db.save_playlist(playlist_data)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save playlist")
    return {"success": True, "playlist": playlist_data}

# Liked songs endpoints
@router.get("/liked-songs")
async def get_liked_songs():
    """Get all liked songs from database."""
    songs = db.get_liked_songs()
    return {"songs": songs}

@router.post("/liked-songs")
async def like_song(request: Request):
    """Add a song to liked songs."""
    data = await request.json()
    artist = data.get('artist', '')
    title = data.get('title', '')
    youtube_id = data.get('youtube_id')
    
    if not artist or not title:
        raise HTTPException(status_code=400, detail="Artist and title are required")
    
    success = db.save_liked_song(artist, title, youtube_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to save liked song")
    return {"success": True, "message": f"Liked: {artist} - {title}"}

@router.delete("/liked-songs")
async def unlike_song(request: Request):
    """Remove a song from liked songs."""
    data = await request.json()
    artist = data.get('artist', '')
    title = data.get('title', '')
    
    if not artist or not title:
        raise HTTPException(status_code=400, detail="Artist and title are required")
    
    success = db.remove_liked_song(artist, title)
    return {"success": success, "message": f"Removed: {artist} - {title}" if success else "Song not found"}

@router.get("/liked-songs/check")
async def check_song_liked(artist: str, title: str):
    """Check if a song is liked."""
    is_liked = db.is_song_liked(artist, title)
    return {"liked": is_liked}

# Legacy endpoint for compatibility
class PlaylistRequest(BaseModel):
    mood: Optional[str] = None
    artists: Optional[List[str]] = None
    songs: Optional[List[str]] = None
    max_tracks: int = 30
    use_ai: bool = True

class Track(BaseModel):
    artist: str
    title: str

class PlaylistResponse(BaseModel):
    tracks: List[Track]
    mood: Optional[str] = None
    artists: Optional[List[str]] = None
    songs: Optional[List[str]] = None

@router.post("/playlist", response_model=PlaylistResponse)
async def generate_playlist(request: PlaylistRequest):
    """Legacy endpoint - generates and saves a playlist."""
    # This endpoint generates mock data - actual AI generation is done in frontend
    tracks = []
    if request.songs:
        for song in request.songs:
            tracks.append({"artist": "AI Artist", "title": song})
    if request.artists:
        for artist in request.artists:
            tracks.append({"artist": artist, "title": "AI Song"})
    if request.mood:
        for i in range(max(0, request.max_tracks - len(tracks))):
            tracks.append({"artist": f"{request.mood.title()} AI Artist {i+1}", "title": f"{request.mood.title()} AI Song {i+1}"})
    tracks = tracks[:request.max_tracks]
    
    # Save playlist to database
    playlist_id = str(uuid.uuid4())
    playlist_data = {
        "id": playlist_id,
        "name": f"{request.mood.title() if request.mood else 'Custom'} Playlist",
        "mood": request.mood,
        "artists": request.artists or [],
        "genres": [],
        "tracks": tracks
    }
    db.save_playlist(playlist_data)
    
    return PlaylistResponse(tracks=tracks, mood=request.mood, artists=request.artists, songs=request.songs)


# ==================== PLAYBACK STATE ENDPOINTS ====================

class PlaybackStateRequest(BaseModel):
    playlist_id: Optional[str] = None
    playlist_name: Optional[str] = "Current Queue"
    tracks: List[Dict[str, Any]]
    current_index: int = 0

@router.get("/playback-state")
async def get_playback_state():
    """Get the last saved playback state from database."""
    state = db.get_playback_state()
    if state:
        return {"success": True, "state": state}
    return {"success": False, "state": None, "message": "No saved playback state"}

@router.post("/playback-state")
async def save_playback_state(request: PlaybackStateRequest):
    """Save the current playback state to database."""
    success = db.save_playback_state(
        playlist_id=request.playlist_id or "custom",
        playlist_name=request.playlist_name,
        tracks=request.tracks,
        current_index=request.current_index
    )
    if success:
        return {"success": True, "message": "Playback state saved"}
    raise HTTPException(status_code=500, detail="Failed to save playback state")

@router.put("/playback-state/index")
async def update_playback_index(request: Request):
    """Update just the current track index."""
    data = await request.json()
    index = data.get('index', 0)
    success = db.update_playback_index(index)
    if success:
        return {"success": True, "index": index}
    raise HTTPException(status_code=500, detail="Failed to update playback index")

@router.get("/initial-data")
async def get_initial_music_data():
    """Get all music data needed for initial page load - playlists, liked songs, and playback state."""
    try:
        playlists = db.get_playlists()
        liked_songs = db.get_liked_songs()
        playback_state = db.get_playback_state()
        
        return {
            "success": True,
            "playlists": playlists,
            "liked_songs": liked_songs,
            "playback_state": playback_state
        }
    except Exception as e:
        logger.error(f"Error getting initial music data: {e}")
        return {
            "success": False,
            "playlists": [],
            "liked_songs": [],
            "playback_state": None,
            "error": str(e)
        }
