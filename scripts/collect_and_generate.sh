#!/bin/bash

# Personal Dashboard - Data Collection and Generation Script
# This script collects data from all sources and generates the dashboard

set -e  # Exit on any error

echo "🚀 Starting Personal Dashboard data collection and generation..."

# Check if Python virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/update dependencies
echo "📋 Installing dependencies..."
pip install -r requirements.txt

# Check if Ollama is running (optional)
echo "🤖 Checking Ollama server..."
if curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    echo "✅ Ollama server is running"
else
    echo "⚠️  Ollama server not detected. AI analysis will use fallback mode."
fi

# Run the dashboard application
echo "📊 Running dashboard data collection and generation..."
python main.py

echo "✅ Dashboard generation complete!"
echo "🌐 Your dashboard is available at: http://localhost:8000"
echo ""
echo "📁 Files generated:"
echo "   - output/dashboard_latest.html (Main dashboard)"
echo "   - output/dashboard_data.json (Raw data)"
echo ""
echo "💡 To view the dashboard:"
echo "   - Open http://localhost:8000 in your browser"
echo "   - Or open output/dashboard_latest.html directly"
