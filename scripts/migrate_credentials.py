#!/usr/bin/env python3
"""
Migration script to move credentials from .env to database.
This makes the dashboard generic and configurable for any user.
"""

import os
import sys
import sqlite3
import json
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from database import DatabaseManager

def load_env_file(env_path):
    """Load .env file and return dict of key-value pairs."""
    env_vars = {}
    if not os.path.exists(env_path):
        print(f"⚠️  .env file not found at {env_path}")
        return env_vars
    
    with open(env_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                env_vars[key.strip()] = value.strip()
    
    return env_vars

def migrate_credentials_to_database(db: DatabaseManager, env_vars: dict):
    """Migrate credentials from .env to database."""
    
    print("\n🔄 Migrating credentials to database...")
    
    # Mapping of env vars to database credential entries
    credential_mappings = {
        'todoist': {
            'api_token': env_vars.get('TODOIST_API_TOKEN', '')
        },
        'github': {
            'token': env_vars.get('GITHUB_TOKEN', ''),
            'username': env_vars.get('GITHUB_USERNAME', '')
        },
        'buildly': {
            'base_url': env_vars.get('BUILDLY_BASE_URL', ''),
            'api_key': env_vars.get('BUILDLY_API_KEY', '')
        },
        'openweather': {
            'api_key': env_vars.get('OPENWEATHER_API_KEY', '')
        },
        'ticktick': {
            'client_id': env_vars.get('TICKTICK_CLIENT_ID', ''),
            'client_secret': env_vars.get('TICKTICK_CLIENT_SECRET', '')
        },
        'spotify': {
            'client_id': env_vars.get('MUSIC_SPOTIFY_CLIENT_ID') or env_vars.get('SPOTIFY_CLIENT_ID', ''),
            'client_secret': env_vars.get('MUSIC_SPOTIFY_CLIENT_SECRET') or env_vars.get('SPOTIFY_CLIENT_SECRET', ''),
            'redirect_uri': env_vars.get('MUSIC_SPOTIFY_REDIRECT_URI', 'http://localhost:8008/api/music/oauth/spotify/callback')
        },
        'apple_music': {
            'developer_token': env_vars.get('MUSIC_APPLE_MUSIC_DEVELOPER_TOKEN', '')
        },
        'youtube': {
            'api_key': env_vars.get('YOUTUBE_API_KEY', '')
        },
        'lastfm': {
            'api_key': env_vars.get('LASTFM_API_KEY', '')
        },
        'news_api': {
            'api_key': env_vars.get('NEWS_API_KEY', '')
        }
    }
    
    migrated_count = 0
    skipped_count = 0
    
    for service, creds in credential_mappings.items():
        # Skip if no credentials provided
        if not any(creds.values()) or all(v.startswith('your_') for v in creds.values() if v):
            print(f"  ⏭️  Skipping {service} (no credentials or placeholder values)")
            skipped_count += 1
            continue
        
        try:
            db.save_credentials(service, creds)
            print(f"  ✅ Migrated {service}")
            migrated_count += 1
        except Exception as e:
            print(f"  ❌ Failed to migrate {service}: {e}")
    
    print(f"\n📊 Migration complete: {migrated_count} migrated, {skipped_count} skipped")
    return migrated_count

def update_user_profile_schema(db: DatabaseManager):
    """Add new columns to user_profile table."""
    
    print("\n🔧 Updating user_profile schema...")
    
    new_columns = [
        ('github_username', 'TEXT'),
        ('soundcloud_url', 'TEXT'),
        ('bandcamp_url', 'TEXT'),
        ('music_artist_name', 'TEXT'),
        ('music_label_name', 'TEXT'),
        ('book_title', 'TEXT'),
        ('project_paths', 'TEXT'),  # JSON array of project paths
        ('vanity_search_terms', 'TEXT'),  # JSON object of search terms
    ]
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Get existing columns
        cursor.execute("PRAGMA table_info(user_profile)")
        existing_columns = {row[1] for row in cursor.fetchall()}
        
        # Add missing columns
        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE user_profile ADD COLUMN {col_name} {col_type}")
                    print(f"  ✅ Added column: {col_name}")
                except Exception as e:
                    print(f"  ⚠️  Column {col_name} might already exist: {e}")
        
        conn.commit()
    
    print("✅ Schema update complete")

def set_default_user_profile(db: DatabaseManager, env_vars: dict):
    """Set default user profile from current hardcoded values."""
    
    print("\n👤 Setting up default user profile...")
    
    # Extract GitHub username from env
    github_username = env_vars.get('GITHUB_USERNAME', '')
    
    default_profile = {
        'full_name': 'Gregory Lind',
        'github_username': github_username,
        'soundcloud_url': 'https://soundcloud.com/gregory-lind',
        'bandcamp_url': 'https://nullrecords.bandcamp.com',
        'music_artist_name': 'Gregory Lind',
        'music_label_name': 'Null Records',
        'book_title': 'Radical Therapy for Software Teams',
        'project_paths': json.dumps([
            '/Users/greglind/Projects/me/dashboard',
            '/Users/greglind/Projects/me/marketing'
        ]),
        'vanity_search_terms': json.dumps({
            'buildly': [
                '"Buildly Labs"',
                '"buildly.io"',
                'site:buildly.io'
            ],
            'personal': [
                '"Gregory Lind" CEO',
                '"Gregory Lind" Buildly',
                '"Gregory Lind" author',
                '"Gregory A Lind"'
            ],
            'book': [
                '"Radical Therapy for Software Teams"',
                'Radical Therapy Software Teams book'
            ],
            'music': [
                '"Gregory Lind" composer',
                '"My Evil Robot Army" band',
                '"Null Records" Gregory Lind',
                'nullrecords Gregory Lind',
                '"Gregory Lind" electronic music'
            ]
        })
    }
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if profile exists
        cursor.execute("SELECT id FROM user_profile WHERE id = 1")
        exists = cursor.fetchone()
        
        if exists:
            # Update existing profile
            set_clause = ', '.join([f"{k} = ?" for k in default_profile.keys()])
            values = list(default_profile.values())
            cursor.execute(f"UPDATE user_profile SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = 1", values)
            print("  ✅ Updated existing user profile")
        else:
            # Insert new profile
            columns = ', '.join(['id'] + list(default_profile.keys()))
            placeholders = ', '.join(['?'] * (len(default_profile) + 1))
            values = [1] + list(default_profile.values())
            cursor.execute(f"INSERT INTO user_profile ({columns}) VALUES ({placeholders})", values)
            print("  ✅ Created new user profile")
        
        conn.commit()

def add_settings_helpers(db: DatabaseManager):
    """Add frequently used settings to database."""
    
    print("\n⚙️  Adding default settings...")
    
    settings_to_add = {
        'redirect_uri': 'http://localhost:8008',
        'music_spotify_redirect_uri': 'http://localhost:8008/api/music/oauth/spotify/callback',
    }
    
    for key, value in settings_to_add.items():
        try:
            existing = db.get_setting(key)
            if not existing:
                db.save_setting(key, value)
                print(f"  ✅ Added setting: {key}")
            else:
                print(f"  ⏭️  Setting already exists: {key}")
        except Exception as e:
            print(f"  ⚠️  Error adding setting {key}: {e}")

def create_env_example():
    """Create .env.example with placeholder values."""
    
    print("\n📝 Creating .env.example...")
    
    env_example_content = """# Environment variables for Personal Dashboard
# Copy this file to .env and fill in your actual values
# DO NOT commit .env to version control!

# Application Settings
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# All credentials below should be configured in the database via the Settings UI
# These environment variables are OPTIONAL fallbacks only

# Todoist (optional - can be set in Settings UI)
TODOIST_API_TOKEN=your_todoist_token_here

# GitHub (optional - can be set in Settings UI)
GITHUB_TOKEN=your_github_personal_access_token_here
GITHUB_USERNAME=your_github_username

# Buildly Labs (optional - can be set in Settings UI)
BUILDLY_BASE_URL=https://api.buildly.io
BUILDLY_API_KEY=your_buildly_api_key_here

# Weather API (optional - can be set in Settings UI)
OPENWEATHER_API_KEY=your_openweather_api_key_here

# TickTick OAuth (optional - can be set in Settings UI)
TICKTICK_CLIENT_ID=your_ticktick_client_id
TICKTICK_CLIENT_SECRET=your_ticktick_client_secret

# Music Services OAuth (optional - can be set in Settings UI)
MUSIC_SPOTIFY_CLIENT_ID=your_spotify_client_id
MUSIC_SPOTIFY_CLIENT_SECRET=your_spotify_client_secret
MUSIC_SPOTIFY_REDIRECT_URI=http://localhost:8008/api/music/oauth/spotify/callback

# Apple Music (optional - can be set in Settings UI)
MUSIC_APPLE_MUSIC_DEVELOPER_TOKEN=your_apple_music_jwt_token_here

# YouTube API (optional - can be set in Settings UI)
YOUTUBE_API_KEY=your_youtube_api_key_here

# Last.fm API (optional - can be set in Settings UI)
LASTFM_API_KEY=your_lastfm_api_key_here

# News API (optional - can be set in Settings UI)
NEWS_API_KEY=your_news_api_key_here

# NOTE: It's recommended to configure all credentials via the Settings UI
# instead of using environment variables. Environment variables are provided
# as a fallback mechanism only.
"""
    
    env_example_path = Path(__file__).parent.parent / '.env.example'
    
    with open(env_example_path, 'w') as f:
        f.write(env_example_content)
    
    print(f"  ✅ Created {env_example_path}")

def main():
    """Run the migration."""
    
    print("=" * 60)
    print("🔐 Credential Migration Tool")
    print("=" * 60)
    
    # Get paths
    project_root = Path(__file__).parent.parent
    env_path = project_root / '.env'
    
    # Initialize database
    db = DatabaseManager()
    
    # Step 1: Update schema
    update_user_profile_schema(db)
    
    # Step 2: Load .env
    env_vars = load_env_file(env_path)
    
    # Step 3: Migrate credentials
    if env_vars:
        migrated_count = migrate_credentials_to_database(db, env_vars)
        
        # Step 4: Set user profile
        if migrated_count > 0:
            set_default_user_profile(db, env_vars)
    else:
        print("\n⚠️  No .env file found - skipping credential migration")
        print("   You can configure credentials later via the Settings UI")
    
    # Step 5: Add helper settings
    add_settings_helpers(db)
    
    # Step 6: Create .env.example
    create_env_example()
    
    print("\n" + "=" * 60)
    print("✅ Migration complete!")
    print("=" * 60)
    print("\n📋 Next steps:")
    print("1. Verify credentials in Settings UI")
    print("2. Update your user profile in Settings > User Profile")
    print("3. Consider removing sensitive data from .env file")
    print("4. Restart the dashboard to apply changes")
    print("\n")

if __name__ == '__main__':
    main()
