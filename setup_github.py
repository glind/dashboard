#!/usr/bin/env python3
"""
Quick GitHub credentials setup
"""

import yaml

def setup_github():
    print("🐙 GitHub Setup")
    print("===============")
    print("1. Go to: https://github.com/settings/tokens")
    print("2. Click 'Generate new token (classic)'")
    print("3. Select scopes: repo, read:user")
    print("4. Copy the token")
    print()
    
    token = input("Enter your GitHub token (ghp_...): ").strip()
    username = input("Enter your GitHub username: ").strip()
    
    if not token or not username:
        print("❌ Both token and username are required")
        return
    
    # Load and update credentials
    with open('config/credentials.yaml', 'r') as f:
        creds = yaml.safe_load(f)
    
    creds['github'] = {
        'token': token,
        'username': username
    }
    
    with open('config/credentials.yaml', 'w') as f:
        yaml.dump(creds, f, default_flow_style=False, sort_keys=False)
    
    # Also save to database
    from database import save_credentials
    save_credentials('github', {'token': token, 'username': username})
    
    print("✅ GitHub credentials saved!")
    print("Restart the dashboard to see GitHub data.")

if __name__ == "__main__":
    setup_github()