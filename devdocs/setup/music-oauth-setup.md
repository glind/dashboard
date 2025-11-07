# Music Services OAuth Setup Guide

This guide will help you set up OAuth authentication for Spotify and Apple Music to enable the Universal Music Player.

## Prerequisites

- Dashboard running at `http://localhost:8008`
- Access to developer accounts for each music service

---

## Spotify OAuth Setup

### Step 1: Create Spotify App

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Click **"Create App"**
3. Fill in the details:
   - **App name**: Personal Dashboard
   - **App description**: Personal music aggregator dashboard
   - **Redirect URI**: `http://localhost:8008/api/music/oauth/spotify/callback`
   - **APIs used**: Web API
4. Click **"Save"**

### Step 2: Get Credentials

1. On your app page, click **"Settings"**
2. Copy your **Client ID** and **Client Secret**

### Step 3: Configure Dashboard

1. Open your `.env` file in the dashboard root directory
2. Add these lines:
   ```bash
   MUSIC_SPOTIFY_CLIENT_ID=your_client_id_here
   MUSIC_SPOTIFY_CLIENT_SECRET=your_client_secret_here
   MUSIC_SPOTIFY_REDIRECT_URI=http://localhost:8008/api/music/oauth/spotify/callback
   ```
3. Replace `your_client_id_here` and `your_client_secret_here` with your actual credentials
4. Restart the dashboard: `./ops/startup.sh restart`

### Step 4: Connect Spotify

1. Go to your dashboard at `http://localhost:8008`
2. Navigate to the **Music** section
3. Click **"Connect"** on the Spotify service card
4. You'll be redirected to Spotify to authorize the app
5. After authorization, you'll be redirected back to the dashboard

**Scopes requested:**
- `user-read-private` - Read your profile data
- `user-read-email` - Read your email address  
- `user-library-read` - Access your saved tracks
- `user-top-read` - Read your top artists and tracks
- `playlist-read-private` - Access your playlists
- `streaming` - Play music in the web player

---

## Apple Music OAuth Setup

Apple Music uses a different authentication flow than Spotify. It requires:
1. A **Developer Token** (server-side, lasts up to 6 months)
2. A **User Token** (obtained via MusicKit JS in the browser)

### Step 1: Join Apple Developer Program

1. Enroll in the [Apple Developer Program](https://developer.apple.com/programs/) ($99/year)
2. Wait for approval (usually 24-48 hours)

### Step 2: Create MusicKit Identifier

1. Go to [Apple Developer Account](https://developer.apple.com/account)
2. Go to **Certificates, Identifiers & Profiles**
3. Click **Identifiers** → **+** button
4. Select **MusicKit Identifier** and click **Continue**
5. Enter details:
   - **Description**: Personal Dashboard Music Player
   - **Identifier**: `io.buildly.dashboard.music` (or your own bundle ID)
6. Click **Register**

### Step 3: Create MusicKit Private Key

1. In **Certificates, Identifiers & Profiles**, go to **Keys**
2. Click the **+** button
3. Enter a name: **Dashboard MusicKit Key**
4. Check **MusicKit**
5. Click **Configure** next to MusicKit
6. Select your MusicKit Identifier from the dropdown
7. Click **Save** → **Continue** → **Register**
8. **Download the key file** (`.p8` file) - you can only download this once!
9. Note your **Key ID** (shown on the download page)
10. Note your **Team ID** (found in Account → Membership)

### Step 4: Generate Developer Token

You need to create a JWT (JSON Web Token) signed with your private key. You can use the included script:

```bash
# Install dependencies
pip install PyJWT cryptography

# Create a token generator script
cat > generate_apple_token.py << 'EOF'
import jwt
import time
from pathlib import Path

# Configuration
KEY_ID = "YOUR_KEY_ID"  # From Step 3
TEAM_ID = "YOUR_TEAM_ID"  # From Step 3
KEY_FILE = "AuthKey_KEYID.p8"  # Your downloaded .p8 file

# Read private key
with open(KEY_FILE, 'r') as f:
    private_key = f.read()

# Generate token
headers = {
    "alg": "ES256",
    "kid": KEY_ID
}

payload = {
    "iss": TEAM_ID,
    "iat": int(time.time()),
    "exp": int(time.time()) + (180 * 24 * 60 * 60)  # 180 days
}

token = jwt.encode(payload, private_key, algorithm='ES256', headers=headers)
print(f"Developer Token:\n{token}")
EOF

# Run it
python generate_apple_token.py
```

### Step 5: Configure Dashboard

1. Open your `.env` file
2. Add these lines:
   ```bash
   MUSIC_APPLE_MUSIC_DEVELOPER_TOKEN=your_generated_jwt_token_here
   MUSIC_APPLE_MUSIC_TEAM_ID=YOUR_TEAM_ID
   MUSIC_APPLE_MUSIC_KEY_ID=YOUR_KEY_ID
   ```
3. Replace values with your actual credentials
4. Restart the dashboard: `./ops/startup.sh restart`

### Step 6: Connect Apple Music

1. Go to your dashboard at `http://localhost:8008`
2. Navigate to the **Music** section
3. Click **"Connect"** on the Apple Music service card
4. The MusicKit JS library will load
5. You'll be prompted to sign in with your Apple ID
6. Authorize the app to access your Apple Music
7. You're connected!

**Note**: The user token is obtained client-side and saved to the database. You need an active Apple Music subscription to use this feature.

---

## Troubleshooting

### Spotify Issues

**"Invalid client_id"**
- Double-check your Client ID in `.env`
- Make sure there are no extra spaces or quotes

**"Redirect URI mismatch"**
- Verify the redirect URI in your Spotify app settings matches exactly: `http://localhost:8008/api/music/oauth/spotify/callback`
- Check for `http` vs `https` and trailing slashes

**"Invalid scope"**
- Some scopes may require app review for production use
- During development, all scopes should work

### Apple Music Issues

**"Invalid developer token"**
- Make sure your token is properly formatted (no newlines)
- Check expiration - tokens last up to 180 days
- Verify your Team ID and Key ID are correct

**"MusicKit JS failed to load"**
- Check browser console for errors
- Ensure you have an active internet connection
- Try clearing browser cache

**"User not subscribed"**
- Apple Music API requires an active Apple Music subscription
- Even with a developer account, you need a paid subscription

**Token expired after 6 months**
- Generate a new developer token using the script
- Update `.env` and restart the dashboard

---

## Testing Your Setup

### Spotify Test

```bash
# Check if credentials are loaded
curl http://localhost:8008/api/music/services

# Initiate OAuth (in browser)
http://localhost:8008/api/music/oauth/spotify/login
```

### Apple Music Test

```bash
# Get Apple Music config
curl http://localhost:8008/api/music/oauth/apple/login

# Should return JSON with developer token
```

---

## Security Notes

1. **Never commit your `.env` file** - it contains sensitive credentials
2. **Keep your `.p8` key file secure** - treat it like a password
3. **Rotate tokens periodically** - especially the Apple Music developer token
4. **Use environment variables** - never hardcode credentials
5. **For production**: Use proper secret management (AWS Secrets Manager, Vault, etc.)

---

## Next Steps

Once connected, you can:
- View your unified music library from all services
- Create mood-based playlists
- Create custom playlists with genre/artist filters
- Play tracks across services
- Get AI-powered music recommendations

See the [Music Player Documentation](../collectors/music-player.md) for more details on using the player.
