#!/bin/bash

# Setup script for Personal Dashboard
# This script sets up the development environment and configuration

set -e

echo "🔧 Setting up Personal Dashboard development environment..."

# Create necessary directories
echo "📁 Creating project directories..."
mkdir -p output
mkdir -p templates
mkdir -p static
mkdir -p data
mkdir -p logs

# Create Python virtual environment
if [ ! -d "venv" ]; then
    echo "🐍 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "📦 Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create configuration files from examples
echo "⚙️ Setting up configuration files..."

if [ ! -f "config/config.yaml" ]; then
    cp config/config.yaml.example config/config.yaml
    echo "✅ Created config/config.yaml from example"
fi

if [ ! -f "config/credentials.yaml" ]; then
    cp config/credentials.yaml.example config/credentials.yaml
    echo "✅ Created config/credentials.yaml from example"
    echo "⚠️  Please edit config/credentials.yaml with your API keys"
fi

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    cat > .env << EOF
# Environment variables for Personal Dashboard
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=INFO

# Ollama settings
OLLAMA_HOST=localhost
OLLAMA_PORT=11434
OLLAMA_MODEL=llama2

# API credentials (alternatively, use config/credentials.yaml)
# TODOIST_API_TOKEN=your_token_here
# GITHUB_TOKEN=your_token_here
# GITHUB_USERNAME=your_username_here
# BUILDLY_BASE_URL=https://api.buildly.io
# BUILDLY_API_KEY=your_key_here
EOF
    echo "✅ Created .env file"
fi

# Create .gitignore if it doesn't exist
if [ ! -f ".gitignore" ]; then
    cat > .gitignore << EOF
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
.env

# Personal data and credentials
config/credentials.yaml
config/google_credentials.json
data/
logs/
output/

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Temporary files
*.tmp
*.log
EOF
    echo "✅ Created .gitignore file"
fi

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Edit config/credentials.yaml with your API keys"
echo "2. For Google APIs: Place your credentials JSON file in config/"
echo "3. Install and start Ollama (optional): https://ollama.ai/"
echo "4. Run: ./scripts/collect_and_generate.sh"
echo ""
echo "📚 Configuration files:"
echo "   - config/config.yaml (main settings)"
echo "   - config/credentials.yaml (API keys)"
echo "   - .env (environment variables)"
echo ""
echo "🔑 Required API credentials:"
echo "   - Todoist API token (optional)"
echo "   - GitHub personal access token (optional)"
echo "   - Google API credentials JSON (optional)"
echo "   - Buildly Labs API key (optional)"
echo ""
echo "💡 The dashboard will work with whatever APIs you configure."
echo "   Missing APIs will be skipped gracefully."
