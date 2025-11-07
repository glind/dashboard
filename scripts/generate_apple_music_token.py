#!/usr/bin/env python3
"""
Generate Apple Music Developer Token (JWT)

This script creates a properly formatted JWT token for Apple Music API authentication.
The token follows Apple's specification:
- Algorithm: ES256
- Max expiration: 180 days (6 months)
- Required claims: iss (Team ID), iat (issued at), exp (expiration)

Requirements:
    pip install PyJWT cryptography

Usage:
    python generate_apple_music_token.py

You'll need:
1. Key ID (kid) - 10 character identifier from Apple Developer
2. Team ID (iss) - 10 character team identifier  
3. Private Key File (.p8) - Downloaded from Apple Developer
"""

import jwt
import time
from pathlib import Path
import sys

def generate_apple_music_token(key_id: str, team_id: str, key_file: str, expiration_days: int = 180) -> str:
    """
    Generate Apple Music Developer Token (JWT).
    
    Args:
        key_id: 10-character Key ID from Apple Developer
        team_id: 10-character Team ID from Apple Developer  
        key_file: Path to .p8 private key file
        expiration_days: Days until token expires (max 180 days / 6 months)
        
    Returns:
        JWT token string
    """
    # Validate expiration (Apple allows max 180 days)
    if expiration_days > 180:
        print(f"⚠️  Warning: Expiration reduced to 180 days (Apple's maximum)")
        expiration_days = 180
    
    # Read private key
    key_path = Path(key_file)
    if not key_path.exists():
        raise FileNotFoundError(f"Private key file not found: {key_file}")
    
    with open(key_path, 'r') as f:
        private_key = f.read()
    
    # Create JWT header
    headers = {
        "alg": "ES256",  # Required by Apple Music API
        "kid": key_id    # Your Key ID
    }
    
    # Create JWT payload with required claims
    current_time = int(time.time())
    expiration_time = current_time + (expiration_days * 24 * 60 * 60)
    
    payload = {
        "iss": team_id,           # Issuer (Team ID)
        "iat": current_time,      # Issued at time
        "exp": expiration_time    # Expiration time
    }
    
    # Optional: Add origin claim for web security
    # payload["origin"] = ["http://localhost:8008", "https://yourdomain.com"]
    
    # Generate and sign the token
    token = jwt.encode(payload, private_key, algorithm='ES256', headers=headers)
    
    return token

def main():
    print("🎵 Apple Music Developer Token Generator")
    print("=" * 50)
    print()
    
    # Get configuration from user
    print("Please enter your Apple Developer credentials:")
    print()
    
    key_id = input("Key ID (10 characters): ").strip()
    if len(key_id) != 10:
        print(f"❌ Error: Key ID should be 10 characters, got {len(key_id)}")
        sys.exit(1)
    
    team_id = input("Team ID (10 characters): ").strip()
    if len(team_id) != 10:
        print(f"❌ Error: Team ID should be 10 characters, got {len(team_id)}")
        sys.exit(1)
    
    key_file = input("Path to .p8 private key file: ").strip()
    
    expiration_input = input("Token expiration in days (default: 180, max: 180): ").strip()
    expiration_days = int(expiration_input) if expiration_input else 180
    
    print()
    print("Generating token...")
    
    try:
        token = generate_apple_music_token(key_id, team_id, key_file, expiration_days)
        
        print()
        print("✅ Token generated successfully!")
        print("=" * 50)
        print()
        print("Copy this token to your .env file:")
        print()
        print("MUSIC_APPLE_MUSIC_DEVELOPER_TOKEN=" + token)
        print()
        print("=" * 50)
        print()
        print(f"📅 Token valid for {expiration_days} days")
        print(f"⏰ Expires: {time.strftime('%Y-%m-%d', time.localtime(time.time() + expiration_days * 86400))}")
        print()
        print("Next steps:")
        print("1. Add the token to your .env file")
        print("2. Restart the dashboard: ./ops/startup.sh restart")
        print("3. Navigate to Music section and click 'Connect' on Apple Music")
        
    except FileNotFoundError as e:
        print(f"❌ Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error generating token: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
