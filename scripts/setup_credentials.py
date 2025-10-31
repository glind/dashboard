#!/usr/bin/env python3
"""
Credentials setup helper for the Personal Dashboard
"""

import yaml
import sys
import os
from pathlib import Path

def load_credentials():
    """Load current credentials."""
    creds_file = Path("config/credentials.yaml")
    if creds_file.exists():
        with open(creds_file, 'r') as f:
            return yaml.safe_load(f) or {}
    return {}

def save_credentials(creds):
    """Save credentials to file."""
    creds_file = Path("config/credentials.yaml")
    creds_file.parent.mkdir(exist_ok=True)
    
    with open(creds_file, 'w') as f:
        yaml.dump(creds, f, default_flow_style=False, sort_keys=False)
    
    print(f"✅ Credentials saved to {creds_file}")

def setup_ticktick():
    """Set up TickTick credentials."""
    print("🎯 TickTick Setup")
    print("================")
    print("You mentioned you have a TickTick token.")
    print("We'll add it to your credentials for API access.")
    print()
    
    token = input("Enter your TickTick API token: ").strip()
    if not token:
        print("❌ No token provided")
        return
    
    # Load existing credentials
    creds = load_credentials()
    
    # Update TickTick section
    if 'ticktick' not in creds:
        creds['ticktick'] = {}
    
    creds['ticktick']['api_token'] = token
    
    # Save credentials
    save_credentials(creds)
    
    print("✅ TickTick token configured!")
    print("You can now use TickTick integration in the dashboard.")

def setup_google():
    """Set up Google OAuth."""
    print("📧 Google APIs Setup")
    print("==================")
    print("For Google Calendar and Gmail integration:")
    print("1. Go to https://console.cloud.google.com")
    print("2. Create a new project or select existing")
    print("3. Enable Gmail API and Calendar API")
    print("4. Go to Credentials → Create Credentials → OAuth 2.0 Client IDs")
    print("5. Set application type to 'Web application'")
    print("6. Add authorized redirect URI: http://localhost:8008/auth/google/callback")
    print("7. Download the JSON file")
    print("8. Save it as: config/google_oauth_config.json")
    print()
    print("Then restart the dashboard and use the Connect buttons in the admin panel.")

def main():
    """Main setup function."""
    if len(sys.argv) < 2:
        print("Personal Dashboard Credentials Setup")
        print("====================================")
        print()
        print("Usage:")
        print("  python setup_credentials.py ticktick  - Set up TickTick token")
        print("  python setup_credentials.py google    - Google OAuth instructions")
        print("  python setup_credentials.py all       - Show all setup options")
        return
    
    command = sys.argv[1].lower()
    
    if command == "ticktick":
        setup_ticktick()
    elif command == "google":
        setup_google()
    elif command == "all":
        print("Available integrations:")
        print("- ticktick: Task management")
        print("- google: Calendar and Gmail")
        print("Run with specific service name for setup instructions.")
    else:
        print(f"Unknown command: {command}")
        print("Available: ticktick, google, all")

if __name__ == "__main__":
    main()