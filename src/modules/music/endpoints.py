from datetime import datetime
import uuid
import json

from pathlib import Path
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional

router = APIRouter(prefix="/api/music", tags=["music"])

PLAYLISTS_FILE = Path(__file__).parent / "playlists.json"

def load_playlists():
    if PLAYLISTS_FILE.exists():
        with open(PLAYLISTS_FILE, "r") as f:
            return json.load(f)
    return []

def save_playlists(playlists):
    with open(PLAYLISTS_FILE, "w") as f:
        json.dump(playlists, f)

@router.get("/playlists")
async def get_playlists():
    playlists = load_playlists()
    return {"playlists": playlists}

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
    # Always use AI (mock) to generate playlist
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
    # Save playlist
    playlists = load_playlists()
    playlist_id = str(uuid.uuid4())
    playlist = {
        "id": playlist_id,
        "name": f"{request.mood.title() if request.mood else 'Custom'} Playlist",
        "mood": request.mood,
        "artists": request.artists,
        "songs": request.songs,
        "tracks": tracks,
        "created_at": datetime.utcnow().isoformat()
    }
    playlists.append(playlist)
    save_playlists(playlists)
    return PlaylistResponse(tracks=tracks, mood=request.mood, artists=request.artists, songs=request.songs)
