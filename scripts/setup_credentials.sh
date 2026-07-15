#!/bin/bash
# Setup credential files from examples
# Run this once after cloning the repository

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔐 Setting up credential files..."

# Function to copy example file if target doesn't exist
setup_file() {
    local example_file="$1"
    local target_file="${example_file%.example}"
    
    if [ -f "$target_file" ]; then
        echo "⏭️  Skipping $target_file (already exists)"
    elif [ -f "$example_file" ]; then
        cp "$example_file" "$target_file"
        echo "✅ Created $target_file from example"
    else
        echo "⚠️  Warning: $example_file not found"
    fi
}

# Setup config directory files
cd "$PROJECT_ROOT"
setup_file "config/config.yaml.example"
setup_file "config/credentials.yaml.example"
setup_file "config/google_oauth_config.json.example"

# Setup src/config files (if different)
setup_file "src/config/config.yaml.example"
setup_file "src/config/credentials.yaml.example"
setup_file "src/config/google_oauth_config.json.example"

# Setup environment files
setup_file ".env.example"
setup_file "ops/.env.example"

# Create tokens directory if it doesn't exist
mkdir -p tokens
echo "✅ Created tokens/ directory"

# Create voice cache directories
mkdir -p data/voice_cache
mkdir -p data/voice_models
echo "✅ Created voice system directories"

echo ""
echo "✨ Setup complete!"
echo ""
echo "📝 Next steps:"
echo "1. Edit config/credentials.yaml with your API keys"
echo "2. Download your Google OAuth credentials from:"
echo "   https://console.cloud.google.com/apis/credentials"
echo "3. Save as config/google_oauth_config.json"
echo "4. Run ./ops/startup.sh to start the dashboard"
echo ""
echo "⚠️  IMPORTANT: Never commit real credentials to git!"
echo "   All credential files are gitignored for your safety."
