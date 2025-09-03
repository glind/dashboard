#!/bin/bash
"""
Setup script for vanity alerts cron job.
This script sets up a cron job to run the vanity alerts monitor every hour.
"""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
MONITOR_SCRIPT="$PROJECT_DIR/scripts/vanity_alerts_monitor.py"
VENV_PATH="$PROJECT_DIR/venv"

echo "Setting up vanity alerts hourly monitoring..."
echo "Project directory: $PROJECT_DIR"
echo "Monitor script: $MONITOR_SCRIPT"

# Check if the monitor script exists
if [ ! -f "$MONITOR_SCRIPT" ]; then
    echo "Error: Monitor script not found at $MONITOR_SCRIPT"
    exit 1
fi

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Error: Virtual environment not found at $VENV_PATH"
    echo "Please run ./startup.sh first to create the virtual environment"
    exit 1
fi

# Create the cron job entry
CRON_JOB="0 * * * * cd $PROJECT_DIR && source $VENV_PATH/bin/activate && python $MONITOR_SCRIPT >> $PROJECT_DIR/vanity_alerts_cron.log 2>&1"

# Check if cron job already exists
if crontab -l 2>/dev/null | grep -q "vanity_alerts_monitor.py"; then
    echo "Vanity alerts cron job already exists. Updating..."
    # Remove existing cron job
    crontab -l 2>/dev/null | grep -v "vanity_alerts_monitor.py" | crontab -
fi

# Add the new cron job
(crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -

echo "✅ Cron job added successfully!"
echo "The vanity alerts monitor will now run every hour."
echo ""
echo "To check the cron job:"
echo "  crontab -l"
echo ""
echo "To view the logs:"
echo "  tail -f $PROJECT_DIR/vanity_alerts_cron.log"
echo "  tail -f $PROJECT_DIR/vanity_alerts.log"
echo ""
echo "To remove the cron job:"
echo "  crontab -l | grep -v 'vanity_alerts_monitor.py' | crontab -"
echo ""
echo "To test the monitor manually:"
echo "  cd $PROJECT_DIR"
echo "  source $VENV_PATH/bin/activate"
echo "  python $MONITOR_SCRIPT"
