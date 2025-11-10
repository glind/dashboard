#!/bin/bash

# Security Setup Script for Dashboard
# This script helps set up secure configuration files from templates

set -e

echo "🔒 Setting up secure configuration..."

# Check if running in project root
if [ ! -f "requirements.txt" ] || [ ! -d "src" ]; then
    echo "❌ Please run this script from the project root directory"
    exit 1
fi

# Create credentials.yaml if it doesn't exist
if [ ! -f "src/config/credentials.yaml" ]; then
    echo "📝 Creating credentials.yaml from template..."
    cp src/config/credentials.yaml.template src/config/credentials.yaml
    echo "✅ Created src/config/credentials.yaml"
    echo "⚠️  Remember to update it with your actual credentials"
else
    echo "⚠️  credentials.yaml already exists"
fi

# Create google_oauth_config.json if it doesn't exist  
if [ ! -f "src/config/google_oauth_config.json" ]; then
    echo "📝 Creating google_oauth_config.json from template..."
    cp src/config/google_oauth_config.json.template src/config/google_oauth_config.json
    echo "✅ Created src/config/google_oauth_config.json" 
    echo "⚠️  Remember to update it with your Google OAuth credentials"
else
    echo "⚠️  google_oauth_config.json already exists"
fi

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "📝 Creating .env from example..."
    cp .env.example .env 2>/dev/null || echo "⚠️  No .env.example found"
    echo "✅ Created .env"
    echo "⚠️  Remember to update it with your actual environment variables"
else
    echo "⚠️  .env already exists"
fi

echo ""
echo "🎉 Configuration files created!"
echo ""
echo "📋 NEXT STEPS:"
echo "1. Edit src/config/credentials.yaml with your API tokens"
echo "2. Edit src/config/google_oauth_config.json with your Google OAuth credentials"
echo "3. Edit .env with your environment variables"
echo "4. NEVER commit these files to git!"
echo ""
echo "🔗 Get credentials from:"
echo "- GitHub: https://github.com/settings/tokens"
echo "- Google: https://console.cloud.google.com/apis/credentials"
echo "- TickTick: TickTick developer settings"
echo "- OpenWeather: https://openweathermap.org/api"