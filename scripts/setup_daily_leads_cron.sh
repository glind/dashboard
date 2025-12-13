#!/bin/bash
# Setup Daily Lead Collection Cron Job

SCRIPT_PATH="/Users/greglind/Projects/me/dashboard/scripts/daily_lead_collection.sh"
CRON_TIME="0 8 * * *"  # 8 AM every day

echo "🔧 Setting up daily lead collection automation..."

# Check if cron entry already exists
if crontab -l 2>/dev/null | grep -q "$SCRIPT_PATH"; then
    echo "⚠️  Cron job already exists. Removing old entry..."
    crontab -l | grep -v "$SCRIPT_PATH" | crontab -
fi

# Add new cron entry
(crontab -l 2>/dev/null; echo "$CRON_TIME $SCRIPT_PATH") | crontab -

# Verify installation
if crontab -l | grep -q "$SCRIPT_PATH"; then
    echo "✅ Daily lead collection cron job installed successfully!"
    echo "   Schedule: Daily at 8:00 AM"
    echo "   Script: $SCRIPT_PATH"
    echo ""
    echo "📋 Current cron jobs:"
    crontab -l | grep "$SCRIPT_PATH"
    echo ""
    echo "📝 To view logs: tail -f /Users/greglind/Projects/me/dashboard/data/daily_lead_collection.log"
    echo "🛑 To remove: crontab -l | grep -v '$SCRIPT_PATH' | crontab -"
else
    echo "❌ Failed to install cron job"
    exit 1
fi
