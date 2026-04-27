# Focus Playlists Feature Guide

## Overview

Focus Playlists is a mood-based playlist generation system that helps founders and builders stay focused during work. The feature allows users to:

- Generate playlists tailored to different moods and work contexts
- Search for tracks on YouTube
- Sync playlists to Spotify or Apple Music
- Save and manage multiple playlists
- Play tracks directly with YouTube embeds

## Architecture

### Provider-First Model

The system uses a **Buildly-owned playlist model** where:

- **Canonical Source of Truth**: All playlists are stored in the Buildly database
- **External Providers**: YouTube, Spotify, and Apple Music are destinations, not sources
- **Metadata Storage**: Only IDs and metadata are stored; audio is never downloaded or hosted

### Core Components

```
src/
├── services/music/
│   ├── playlist_generator.py      # Playlist generation service
│   └── providers/
│       ├── base.py                # Abstract provider interface
│       ├── youtube.py             # YouTube search & embed
│       ├── spotify.py             # Spotify API integration
│       └── apple_music.py         # Apple Music API integration
├── modules/music/
│   └── focus_playlists_endpoints.py  # FastAPI endpoints
└── static/
    ├── focus-playlists.js         # Frontend UI
    └── focus-playlists.css        # Styling
```

## Mood Presets

### Available Moods

1. **Deep Work** (Energy: 4/10)
   - Genres: ambient, electronic, minimalist, post-rock
   - Tempo: 60-100 BPM
   - Preference: Instrumental
   - Duration: 90 min

2. **Debugging** (Energy: 5/10)
   - Genres: lo-fi hip hop, chill electronic, ambient jazz
   - Tempo: 85-110 BPM
   - Preference: Instrumental
   - Duration: 60 min

3. **Pitch Deck Sprint** (Energy: 8/10)
   - Genres: electronic, funk, indie rock, synthwave
   - Tempo: 120-140 BPM
   - Preference: Mixed
   - Duration: 45 min

4. **Late Night Hack** (Energy: 6/10)
   - Genres: synthwave, vaporwave, chillwave, experimental
   - Tempo: 90-120 BPM
   - Preference: Instrumental
   - Duration: 120 min

5. **Calm Focus** (Energy: 2/10)
   - Genres: ambient, classical, meditation, nature sounds
   - Tempo: 40-80 BPM
   - Preference: Instrumental
   - Duration: 90 min

6. **Launch Day Energy** (Energy: 9/10)
   - Genres: pop, indie pop, dance, electronic
   - Tempo: 130-150 BPM
   - Preference: Mixed
   - Duration: 60 min

## Setup

### Environment Variables

Add to your `.env` file:

```bash
# YouTube API (for track searching)
YOUTUBE_API_KEY=your_youtube_api_key_here

# Spotify API (for playlist sync)
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://localhost:8008/api/spotify/callback

# Apple Music API (for playlist sync)
APPLE_MUSIC_TEAM_ID=your_team_id
APPLE_MUSIC_KEY_ID=your_key_id
APPLE_MUSIC_PRIVATE_KEY=your_private_key
APPLE_MUSIC_DEVELOPER_TOKEN=your_developer_token

# Optional: AI-powered playlist generation
ENABLE_PLAYLIST_AI=false  # Set to true if Ollama is running
OLLAMA_HOST=http://localhost:11434
```

### YouTube API Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project
3. Enable YouTube Data API v3
4. Create an API key (Credentials → Create Credentials → API Key)
5. Add to `.env`: `YOUTUBE_API_KEY=your_key`

### Spotify Integration (Optional)

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create an app
3. Note your Client ID and Client Secret
4. Add to `.env`:
   ```bash
   SPOTIFY_CLIENT_ID=your_id
   SPOTIFY_CLIENT_SECRET=your_secret
   ```

### Apple Music Integration (Optional)

1. Enroll in [Apple Developer Program](https://developer.apple.com/musickit/)
2. Create an API key
3. Add to `.env`:
   ```bash
   APPLE_MUSIC_TEAM_ID=your_team_id
   APPLE_MUSIC_KEY_ID=your_key_id
   APPLE_MUSIC_DEVELOPER_TOKEN=your_token
   ```

## API Endpoints

### Mood Presets

**GET** `/api/focus-playlists/mood-presets`

Returns all available mood presets with descriptions and energy levels.

```json
{
  "success": true,
  "moods": [
    {
      "id": "deep-work",
      "name": "Deep Work",
      "description": "Focus music for intense, uninterrupted work sessions",
      "energy_level": 4,
      "default_duration_minutes": 90
    }
  ]
}
```

### Generate Playlist

**POST** `/api/focus-playlists/generate`

Generate a new mood-based playlist.

**Request:**
```json
{
  "mood": "deep-work",
  "duration_minutes": 60,
  "context": "Working on database optimization"  // optional
}
```

**Response:**
```json
{
  "success": true,
  "playlist": {
    "id": "uuid",
    "title": "Deep Work - 60min",
    "mood": "deep-work",
    "duration_minutes": 60,
    "track_count": 15,
    "tracks": [
      {
        "id": "uuid",
        "title": "Bloom",
        "artist": "The Midnight",
        "duration_seconds": 240,
        "position": 1,
        "youtube_video_id": "dQw4w9WgXcQ",
        "match_confidence": 0.95
      }
    ],
    "created_at": "2026-04-27T10:00:00"
  },
  "note": "YouTube matching in progress. Refresh to see video IDs."
}
```

### Get Playlists

**GET** `/api/focus-playlists/`

Get all playlists for the current user.

**Response:**
```json
{
  "success": true,
  "playlists": [
    {
      "id": "uuid",
      "title": "Deep Work - 60min",
      "mood": "deep-work",
      "duration_minutes": 60,
      "track_count": 15,
      "created_at": "2026-04-27T10:00:00"
    }
  ]
}
```

### Get Playlist Details

**GET** `/api/focus-playlists/{id}`

Get full playlist with all tracks.

### Delete Playlist

**DELETE** `/api/focus-playlists/{id}`

Delete a playlist and all its tracks.

### Sync to Provider

**POST** `/api/focus-playlists/{id}/sync/{provider}`

Sync playlist to Spotify or Apple Music.

**Parameters:**
- `provider`: `spotify` or `apple_music`

**Response:**
```json
{
  "success": true,
  "sync_job_id": "uuid",
  "status": "pending",
  "message": "Playlist sync to spotify started"
}
```

## Database Schema

### Tables

#### `mood_presets`
```sql
CREATE TABLE mood_presets (
  id TEXT PRIMARY KEY,
  name TEXT UNIQUE NOT NULL,
  description TEXT,
  energy_level INTEGER DEFAULT 5,
  genres TEXT,  -- JSON array
  tempo_range TEXT,
  instrumental_preference TEXT,
  default_duration_minutes INTEGER DEFAULT 60,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `focus_playlists`
```sql
CREATE TABLE focus_playlists (
  id TEXT PRIMARY KEY,
  user_id TEXT DEFAULT 'default',
  title TEXT NOT NULL,
  mood TEXT,
  description TEXT,
  duration_minutes INTEGER,
  source TEXT DEFAULT 'buildly',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### `focus_playlist_tracks`
```sql
CREATE TABLE focus_playlist_tracks (
  id TEXT PRIMARY KEY,
  playlist_id TEXT NOT NULL,
  title TEXT NOT NULL,
  artist TEXT NOT NULL,
  album TEXT,
  duration_seconds INTEGER,
  position INTEGER NOT NULL,
  youtube_video_id TEXT,
  spotify_track_id TEXT,
  apple_music_track_id TEXT,
  match_confidence REAL DEFAULT 0.0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (playlist_id) REFERENCES focus_playlists(id),
  UNIQUE(playlist_id, position)
);
```

#### `user_music_connections`
```sql
CREATE TABLE user_music_connections (
  id TEXT PRIMARY KEY,
  user_id TEXT DEFAULT 'default',
  provider TEXT NOT NULL,
  access_token TEXT,
  refresh_token TEXT,
  token_expires_at TIMESTAMP,
  provider_user_id TEXT,
  is_default INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(user_id, provider)
);
```

#### `sync_jobs`
```sql
CREATE TABLE sync_jobs (
  id TEXT PRIMARY KEY,
  user_id TEXT DEFAULT 'default',
  playlist_id TEXT NOT NULL,
  provider TEXT NOT NULL,
  status TEXT DEFAULT 'pending',
  external_playlist_id TEXT,
  matched_tracks INTEGER DEFAULT 0,
  failed_tracks INTEGER DEFAULT 0,
  error_message TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (playlist_id) REFERENCES focus_playlists(id),
  UNIQUE(playlist_id, provider)
);
```

## Frontend Usage

### Initialization

The frontend is automatically initialized when the page loads. The UI includes:

1. **Mood Selector**: Interactive cards for selecting playlist mood
2. **Duration Selector**: Choose playlist length (30-120 min)
3. **YouTube Player**: Embedded YouTube player for track playback
4. **Playlist Controls**: Play/pause, next/previous track buttons
5. **Sync Buttons**: Save to Spotify or Apple Music
6. **Playlist Manager**: View and delete saved playlists

### Files

- `src/static/focus-playlists.js` - UI logic and API integration
- `src/static/focus-playlists.css` - Styling

Include in your HTML:
```html
<link rel="stylesheet" href="/static/focus-playlists.css">
<script src="/static/focus-playlists.js"></script>
```

## Testing

Run tests with:

```bash
pytest tests/test_focus_playlists.py -v
```

### Test Coverage

- Playlist generation
- Mood preset management
- YouTube track matching
- Database operations
- Provider integration (mocked)

## Future Enhancements

### Phase 2
- [ ] Full OAuth flows for Spotify and Apple Music
- [ ] Playlist sharing
- [ ] Custom mood creation
- [ ] Track recommendations based on user history
- [ ] Integration with Buildly ML for better track matching

### Phase 3
- [ ] Collaborative playlists
- [ ] Real-time sync across devices
- [ ] Analytics (mood preferences, listening patterns)
- [ ] Integration with task management (auto-select mood for tasks)

## Troubleshooting

### YouTube Videos Not Found

- Verify `YOUTUBE_API_KEY` is set and valid
- Check API quota limits
- Try with exact artist/title spellings

### Sync Not Working

- Verify provider credentials are correct
- Check user has authorized the app with the provider
- Review sync job status in database

### Performance Issues

- YouTube matching runs asynchronously; refresh to see results
- Limit playlist queries with pagination
- Archive old playlists

## Architecture Decision: Provider-First Model

This system explicitly chooses a **Buildly-owned canonical source** rather than a provider-centric approach. This means:

### Benefits
- ✅ Playlist independence from any single provider
- ✅ Easy provider switching without data loss
- ✅ Custom metadata and annotations
- ✅ No vendor lock-in
- ✅ Unified UI across all platforms

### Tradeoffs
- ⚠️ Manual provider sync required (we don't auto-push to providers)
- ⚠️ Provider updates don't sync back automatically
- ⚠️ Storage of metadata not provided by APIs (user ratings, notes)

## References

- [YouTube Data API v3](https://developers.google.com/youtube/v3)
- [Spotify Web API](https://developer.spotify.com/documentation/web-api)
- [Apple Music API](https://developer.apple.com/documentation/applemusicapi)
- [MusicKit JS](https://js-cdn.music.apple.com/musickit/v3/musickit.js)
