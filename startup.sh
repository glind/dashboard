#!/bin/bash

# Personal Dashboard Startup Script
# This script MUST be used to start the dashboard - never start manually!

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
VENV_DIR=".venv"
PYTHON_CMD="python3"
SERVER_FILE="main.py"
SERVER_PORT="8008"  # Server runs on 0.0.0.0:8008 (accessible from network)
PID_FILE="dashboard.pid"

echo -e "${BLUE}🚀 Personal Dashboard Startup${NC}"
echo "=================================="

# Function to check if server is already running
check_server_running() {
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${YELLOW}⚠️  Dashboard already running (PID: $pid)${NC}"
            echo -e "   URL: http://localhost:$SERVER_PORT"
            echo -e "   To restart: ./startup.sh restart"
            exit 0
        else
            # Stale PID file
            rm -f "$PID_FILE"
        fi
    fi
}

# Function to stop existing server
stop_server() {
    echo -e "${YELLOW}🛑 Stopping existing dashboard...${NC}"
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            kill "$pid"
            sleep 2
            if ps -p "$pid" > /dev/null 2>&1; then
                kill -9 "$pid" 2>/dev/null || true
            fi
        fi
        rm -f "$PID_FILE"
    fi
    # Also kill any processes on the port
    pkill -f "$SERVER_FILE" 2>/dev/null || true
    sleep 1
}

# Function to setup virtual environment
setup_venv() {
    echo -e "${BLUE}🔧 Setting up virtual environment...${NC}"
    
    if [ ! -d "$VENV_DIR" ]; then
        echo "   Creating virtual environment..."
        $PYTHON_CMD -m venv "$VENV_DIR"
    fi
    
    echo "   Activating virtual environment..."
    source "$VENV_DIR/bin/activate"
    
    # Verify activation
    if [[ "$VIRTUAL_ENV" != *"$VENV_DIR"* ]]; then
        echo -e "${RED}❌ Failed to activate virtual environment${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}   ✅ Virtual environment active${NC}"
}

# Function to install requirements
install_requirements() {
    echo -e "${BLUE}📦 Checking dependencies...${NC}"
    
    if [ ! -f "requirements.txt" ]; then
        echo -e "${RED}❌ requirements.txt not found${NC}"
        exit 1
    fi
    
    # Always install requirements to ensure they're up to date
    echo "   Installing/updating dependencies..."
    pip install --upgrade pip --quiet
    pip install -r requirements.txt --quiet
    echo -e "${GREEN}   ✅ Dependencies up to date${NC}"
}

# Function to verify configuration
check_config() {
    echo -e "${BLUE}⚙️  Checking configuration...${NC}"
    
    # Check if server file exists
    if [ ! -f "$SERVER_FILE" ]; then
        echo -e "${RED}❌ Server file $SERVER_FILE not found${NC}"
        exit 1
    fi
    
    # Create config directories if they don't exist
    mkdir -p config tokens data
    
    # Check for example config files
    if [ ! -f "config/config.yaml" ] && [ -f "config/config.yaml.example" ]; then
        echo -e "${YELLOW}   ⚠️  Copying example config (please customize)${NC}"
        cp "config/config.yaml.example" "config/config.yaml"
    fi
    
    if [ ! -f "config/credentials.yaml" ] && [ -f "config/credentials.yaml.example" ]; then
        echo -e "${YELLOW}   ⚠️  Copying example credentials (please add your API keys)${NC}"
        cp "config/credentials.yaml.example" "config/credentials.yaml"
    fi
    
    echo -e "${GREEN}   ✅ Configuration ready${NC}"
}

# Function to check database integrity
check_database() {
    echo -e "${BLUE}🗄️  Checking database integrity...${NC}"
    
    if [ -f "dashboard.db" ]; then
        # Check if we can access the database and key tables exist
        if sqlite3 dashboard.db "SELECT name FROM sqlite_master WHERE type='table' AND name='vanity_alerts';" | grep -q vanity_alerts; then
            echo -e "${GREEN}   ✅ Database integrity check passed${NC}"
        else
            echo -e "${YELLOW}   ⚠️  Database appears corrupted, will be recreated on startup${NC}"
            mv dashboard.db "dashboard.db.corrupted.$(date +%s)" 2>/dev/null || true
        fi
    else
        echo -e "${BLUE}   ℹ️  Database will be created on first startup${NC}"
    fi
}

# Function to start the server
start_server() {
    echo -e "${BLUE}🌟 Starting dashboard server...${NC}"
    
    # Make sure we're in the virtual environment
    source "$VENV_DIR/bin/activate"
    
    # Load environment variables from .env file if it exists
    if [ -f ".env" ]; then
        echo -e "${BLUE}   Loading environment variables from .env${NC}"
        export $(grep -v '^#' .env | xargs)
    fi
    
    # Start server in background with proper environment
    cd "$(dirname "$0")"
    nohup "$VENV_DIR/bin/python" "$SERVER_FILE" > dashboard.log 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    
    # Wait a moment and check if it started successfully
    sleep 3
    if ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${GREEN}✅ Dashboard started successfully!${NC}"
        echo ""
        echo -e "${GREEN}📍 Dashboard URL (Local): http://localhost:$SERVER_PORT${NC}"
        echo -e "${GREEN}📍 Dashboard URL (Network): http://$(ipconfig getifaddr en0 2>/dev/null || echo "localhost"):$SERVER_PORT${NC}"
        echo -e "${GREEN}🔧 API Docs: http://localhost:$SERVER_PORT/docs${NC}"
        echo -e "${GREEN}📋 Process ID: $pid${NC}"
        echo ""
        echo -e "${BLUE}📊 To view logs: tail -f dashboard.log${NC}"
        echo -e "${BLUE}🛑 To stop: ./startup.sh stop${NC}"
        
        # Test the server is responding
        sleep 2
        if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$SERVER_PORT" | grep -q "200"; then
            echo -e "${GREEN}🎉 Server health check passed!${NC}"
        else
            echo -e "${YELLOW}⚠️  Server started but health check failed (may still be initializing)${NC}"
        fi
    else
        echo -e "${RED}❌ Failed to start server${NC}"
        echo "Check dashboard.log for errors:"
        tail -10 dashboard.log 2>/dev/null || echo "No log file found"
        rm -f "$PID_FILE"
        exit 1
    fi
}

# Function to show status
show_status() {
    echo -e "${BLUE}📊 Dashboard Status${NC}"
    echo "==================="
    
    if [ -f "$PID_FILE" ]; then
        local pid=$(cat "$PID_FILE")
        if ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ Running (PID: $pid)${NC}"
            echo -e "   Local URL: http://localhost:$SERVER_PORT"
            echo -e "   Network URL: http://$(ipconfig getifaddr en0 2>/dev/null || echo "localhost"):$SERVER_PORT"
            echo -e "   Uptime: $(ps -o etime= -p "$pid" | tr -d ' ')"
        else
            echo -e "${RED}❌ Not running (stale PID file)${NC}"
            rm -f "$PID_FILE"
        fi
    else
        echo -e "${RED}❌ Not running${NC}"
    fi
}

# Main execution logic
case "${1:-start}" in
    "start")
        check_server_running
        setup_venv
        install_requirements
        check_config
        check_database
        start_server
        ;;
    "stop")
        stop_server
        echo -e "${GREEN}✅ Dashboard stopped${NC}"
        ;;
    "restart")
        stop_server
        sleep 2
        setup_venv
        install_requirements
        check_config
        check_database
        start_server
        ;;
    "status")
        show_status
        ;;
    "logs")
        if [ -f "dashboard.log" ]; then
            tail -f dashboard.log
        else
            echo -e "${RED}❌ No log file found${NC}"
        fi
        ;;
    "repair")
        echo -e "${YELLOW}🔧 Repairing database...${NC}"
        stop_server
        if [ -f "dashboard.db" ]; then
            backup_name="dashboard.db.backup.$(date +%s)"
            mv dashboard.db "$backup_name"
            echo -e "${BLUE}   Backed up database to $backup_name${NC}"
        fi
        echo -e "${GREEN}   Database will be recreated on next startup${NC}"
        echo -e "${BLUE}   Run './startup.sh start' to recreate and start${NC}"
        ;;
    *)
        echo -e "${BLUE}Personal Dashboard Control Script${NC}"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  start    - Start the dashboard (default)"
        echo "  stop     - Stop the dashboard"
        echo "  restart  - Restart the dashboard"
        echo "  status   - Show dashboard status"
        echo "  logs     - Show live logs"
        echo "  repair   - Repair/recreate corrupted database"
        echo ""
        echo -e "${YELLOW}🚨 IMPORTANT: Always use this script to start the dashboard${NC}"
        echo -e "${YELLOW}   Never use 'python3 main.py' directly${NC}"
        ;;
esac
