#!/bin/bash
# Daily Lead Collection Script
# Runs lead collection automatically

# Configuration
DASHBOARD_URL="http://localhost:8008"
LOG_FILE="/Users/greglind/Projects/me/dashboard/data/daily_lead_collection.log"
DAYS_BACK=1

# Timestamp
echo "================================" >> "$LOG_FILE"
echo "$(date '+%Y-%m-%d %H:%M:%S') - Starting daily lead collection" >> "$LOG_FILE"

# Check if server is running
if ! curl -s "${DASHBOARD_URL}/health" > /dev/null 2>&1; then
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR: Dashboard server is not running" >> "$LOG_FILE"
    exit 1
fi

# Run lead collection
RESPONSE=$(curl -s -X POST "${DASHBOARD_URL}/api/leads/collect?days_back=${DAYS_BACK}&sources=email,calendar,notes")

# Log response
echo "$(date '+%Y-%m-%d %H:%M:%S') - Response: $RESPONSE" >> "$LOG_FILE"

# Check if successful
if echo "$RESPONSE" | grep -q '"success":true'; then
    LEADS_COUNT=$(echo "$RESPONSE" | grep -o '"leads_collected":[0-9]*' | grep -o '[0-9]*')
    echo "$(date '+%Y-%m-%d %H:%M:%S') - SUCCESS: Collected $LEADS_COUNT leads" >> "$LOG_FILE"
else
    echo "$(date '+%Y-%m-%d %H:%M:%S') - ERROR: Lead collection failed" >> "$LOG_FILE"
    exit 1
fi

echo "$(date '+%Y-%m-%d %H:%M:%S') - Daily lead collection completed" >> "$LOG_FILE"
