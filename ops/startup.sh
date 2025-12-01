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
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_ROOT/.venv"
PYTHON_CMD="python3"
SERVER_FILE="$PROJECT_ROOT/src/main.py"
SERVER_PORT="8008"  # Server runs on 0.0.0.0:8008 (accessible from network)
PID_FILE="$PROJECT_ROOT/dashboard.pid"

echo -e "${BLUE}🚀 Personal Dashboard Startup${NC}"
echo "=================================="

# Function to check prerequisites
check_prerequisites() {
    echo -e "${BLUE}🔍 Checking prerequisites...${NC}"
    
    # Check Python 3
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}❌ Python 3 is not installed${NC}"
        echo -e "${YELLOW}   Please install Python 3.8 or higher from https://python.org${NC}"
        exit 1
    fi
    
    # Check Python version
    local python_version=$(python3 --version 2>&1 | awk '{print $2}')
    local major=$(echo "$python_version" | cut -d. -f1)
    local minor=$(echo "$python_version" | cut -d. -f2)
    
    if [ "$major" -lt 3 ] || ([ "$major" -eq 3 ] && [ "$minor" -lt 8 ]); then
        echo -e "${RED}❌ Python $python_version is too old${NC}"
        echo -e "${YELLOW}   Python 3.8 or higher is required${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}   ✅ Python $python_version found${NC}"
    
    # Check pip
    if ! python3 -m pip --version &> /dev/null; then
        echo -e "${RED}❌ pip is not installed${NC}"
        echo -e "${YELLOW}   Installing pip...${NC}"
        python3 -m ensurepip --upgrade || {
            echo -e "${RED}❌ Failed to install pip${NC}"
            exit 1
        }
    fi
    
    echo -e "${GREEN}   ✅ pip is available${NC}"
    
    # Check for venv module
    if ! python3 -m venv --help &> /dev/null; then
        echo -e "${RED}❌ Python venv module is not available${NC}"
        echo -e "${YELLOW}   On Ubuntu/Debian, install with: sudo apt-get install python3-venv${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}   ✅ venv module available${NC}"
}

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
    
    # Check if pip is working in the venv
    if ! python -m pip --version &> /dev/null; then
        echo -e "${YELLOW}⚠️  Virtual environment pip is corrupted, recreating...${NC}"
        deactivate 2>/dev/null || true
        rm -rf "$VENV_DIR"
        echo "   Creating fresh virtual environment..."
        $PYTHON_CMD -m venv "$VENV_DIR"
        source "$VENV_DIR/bin/activate"
        
        if ! python -m pip --version &> /dev/null; then
            echo -e "${RED}❌ Failed to create working virtual environment${NC}"
            exit 1
        fi
    fi
    
    echo -e "${GREEN}   ✅ Virtual environment active${NC}"
}

# Function to install requirements
install_requirements() {
    echo -e "${BLUE}📦 Checking dependencies...${NC}"
    
    if [ ! -f "$PROJECT_ROOT/requirements.txt" ]; then
        echo -e "${RED}❌ requirements.txt not found at $PROJECT_ROOT/requirements.txt${NC}"
        exit 1
    fi
    
    # Check if we need to install/update
    local requirements_hash=""
    local installed_hash=""
    
    if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
        requirements_hash=$(md5sum "$PROJECT_ROOT/requirements.txt" 2>/dev/null | awk '{print $1}')
    fi
    
    if [ -f "$VENV_DIR/.requirements_hash" ]; then
        installed_hash=$(cat "$VENV_DIR/.requirements_hash")
    fi
    
    if [ "$requirements_hash" != "$installed_hash" ] || [ -z "$installed_hash" ]; then
        echo "   Installing/updating dependencies..."
        
        # Upgrade pip first (show output for transparency)
        echo "   Upgrading pip..."
        python -m pip install --upgrade pip || {
            echo -e "${RED}❌ Failed to upgrade pip${NC}"
            exit 1
        }
        
        # Install requirements (show progress)
        echo "   Installing requirements..."
        python -m pip install -r "$PROJECT_ROOT/requirements.txt" || {
            echo -e "${RED}❌ Failed to install dependencies${NC}"
            echo -e "${YELLOW}   Check the error above and verify requirements.txt${NC}"
            exit 1
        }
        
        # Save hash to skip reinstall next time
        echo "$requirements_hash" > "$VENV_DIR/.requirements_hash"
        echo -e "${GREEN}   ✅ Dependencies installed successfully${NC}"
    else
        echo -e "${GREEN}   ✅ Dependencies already up to date${NC}"
    fi
    
    # Verify critical dependencies are installed
    echo -e "${BLUE}   Verifying critical packages...${NC}"
    local critical_packages=("fastapi" "uvicorn" "pydantic" "requests" "pyyaml")
    local missing_packages=()
    
    for package in "${critical_packages[@]}"; do
        if ! python -m pip show "$package" &> /dev/null; then
            missing_packages+=("$package")
        fi
    done
    
    if [ ${#missing_packages[@]} -gt 0 ]; then
        echo -e "${RED}❌ Critical packages missing: ${missing_packages[*]}${NC}"
        echo -e "${YELLOW}   Attempting to reinstall requirements...${NC}"
        python -m pip install -r "$PROJECT_ROOT/requirements.txt" || exit 1
    else
        echo -e "${GREEN}   ✅ All critical packages verified${NC}"
    fi
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
    mkdir -p "$PROJECT_ROOT/config" "$PROJECT_ROOT/tokens" "$PROJECT_ROOT/data"
    
    # Check for example config files
    if [ ! -f "$PROJECT_ROOT/config/config.yaml" ] && [ -f "$PROJECT_ROOT/config/config.yaml.example" ]; then
        echo -e "${YELLOW}   ⚠️  Copying example config (please customize)${NC}"
        cp "$PROJECT_ROOT/config/config.yaml.example" "$PROJECT_ROOT/config/config.yaml"
    fi
    
    if [ ! -f "$PROJECT_ROOT/config/credentials.yaml" ] && [ -f "$PROJECT_ROOT/config/credentials.yaml.example" ]; then
        echo -e "${YELLOW}   ⚠️  Copying example credentials (please add your API keys)${NC}"
        cp "$PROJECT_ROOT/config/credentials.yaml.example" "$PROJECT_ROOT/config/credentials.yaml"
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
    cd "$PROJECT_ROOT/src"  # Change to src directory for correct imports
    export PYTHONPATH="$PROJECT_ROOT/src:$PYTHONPATH"
    echo -e "${BLUE}   Starting server from: $(pwd)${NC}"
    echo -e "${BLUE}   Python path: $PYTHONPATH${NC}"
    echo -e "${BLUE}   Log file: $PROJECT_ROOT/dashboard.log${NC}"
    
    nohup "$VENV_DIR/bin/python" main.py > "$PROJECT_ROOT/dashboard.log" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"
    echo -e "${BLUE}   Process started with PID: $pid${NC}"
    
    # Wait and check if process is still running
    echo -e "${BLUE}   Waiting for server to initialize...${NC}"
    sleep 3
    
    if ! ps -p "$pid" > /dev/null 2>&1; then
        echo -e "${RED}❌ Process died immediately!${NC}"
        echo -e "${RED}Last 20 lines of log:${NC}"
        tail -20 "$PROJECT_ROOT/dashboard.log" 2>/dev/null || echo "No log file found"
        rm -f "$PID_FILE"
        return 1
    fi
    
    echo -e "${BLUE}   Process is running, checking server response...${NC}"
    
    # Wait longer for server to fully start (FastAPI can take time)
    local max_attempts=15
    local attempt=1
    local server_ready=false
    
    while [ $attempt -le $max_attempts ]; do
        echo -e "${BLUE}   Attempt $attempt/$max_attempts: Testing server...${NC}"
        
        if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$SERVER_PORT" 2>/dev/null | grep -q "200"; then
            server_ready=true
            break
        fi
        
        if ! ps -p "$pid" > /dev/null 2>&1; then
            echo -e "${RED}❌ Process died during startup!${NC}"
            echo -e "${RED}Last 20 lines of log:${NC}"
            tail -20 "$PROJECT_ROOT/dashboard.log"
            rm -f "$PID_FILE"
            return 1
        fi
        
        sleep 2
        ((attempt++))
    done
    
    if [ "$server_ready" = true ]; then
        echo -e "${GREEN}✅ Dashboard started successfully!${NC}"
        echo ""
        echo -e "${GREEN}📍 Dashboard URL (Local): http://localhost:$SERVER_PORT${NC}"
        echo -e "${GREEN}📍 Dashboard URL (Network): http://$(ipconfig getifaddr en0 2>/dev/null || echo "localhost"):$SERVER_PORT${NC}"
        echo -e "${GREEN}🔧 API Docs: http://localhost:$SERVER_PORT/docs${NC}"
        echo -e "${GREEN}📋 Process ID: $pid${NC}"
        echo ""
        echo -e "${BLUE}📊 To view logs: tail -f $PROJECT_ROOT/dashboard.log${NC}"
        echo -e "${BLUE}🛑 To stop: ./startup.sh stop${NC}"
        echo -e "${GREEN}🎉 Server health check passed!${NC}"
    else
        echo -e "${YELLOW}⚠️  Server process is running but not responding to HTTP requests${NC}"
        echo -e "${YELLOW}   This might indicate a startup issue. Check the logs:${NC}"
        echo -e "${BLUE}   tail -f $PROJECT_ROOT/dashboard.log${NC}"
        echo ""
        echo -e "${BLUE}📋 Process ID: $pid${NC}"
        echo -e "${BLUE}🛑 To stop: ./startup.sh stop${NC}"
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
            
            # Check if server is responding
            if curl -s -o /dev/null -w "%{http_code}" "http://localhost:$SERVER_PORT" 2>/dev/null | grep -q "200"; then
                echo -e "${GREEN}✅ Server is responding to HTTP requests${NC}"
            else
                echo -e "${YELLOW}⚠️  Process is running but server is not responding${NC}"
                echo -e "${YELLOW}   Server may still be starting up...${NC}"
            fi
        else
            echo -e "${RED}❌ Not running (stale PID file)${NC}"
            rm -f "$PID_FILE"
        fi
    else
        echo -e "${RED}❌ Not running${NC}"
    fi
    
    # Show recent log entries if available
    if [ -f "$PROJECT_ROOT/dashboard.log" ]; then
        echo ""
        echo -e "${BLUE}📋 Recent log entries (last 5 lines):${NC}"
        echo -e "${CYAN}$(tail -5 "$PROJECT_ROOT/dashboard.log")${NC}"
    fi
}

# Function to show logs
show_logs() {
    if [ -f "$PROJECT_ROOT/dashboard.log" ]; then
        echo -e "${BLUE}📋 Dashboard Logs${NC}"
        echo "=================="
        echo ""
        if [ "$1" = "follow" ] || [ "$1" = "-f" ]; then
            echo -e "${BLUE}Following logs (press Ctrl+C to stop)...${NC}"
            tail -f "$PROJECT_ROOT/dashboard.log"
        else
            local lines="${1:-50}"
            echo -e "${BLUE}Last $lines lines:${NC}"
            tail -"$lines" "$PROJECT_ROOT/dashboard.log"
        fi
    else
        echo -e "${RED}❌ No log file found at: $PROJECT_ROOT/dashboard.log${NC}"
        echo -e "${BLUE}💡 Start the dashboard first: ./startup.sh${NC}"
    fi
}

# Main execution logic
case "${1:-start}" in
    "start")
        check_prerequisites
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
        check_prerequisites
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
        show_logs "$2"
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
        echo "Usage: $0 [command] [options]"
        echo ""
        echo "Commands:"
        echo "  start           - Start the dashboard (default)"
        echo "  stop            - Stop the dashboard"
        echo "  restart         - Restart the dashboard"
        echo "  status          - Show dashboard status with health check"
        echo "  logs [lines]    - Show recent logs (default: 50 lines)"
        echo "  logs follow     - Follow logs in real-time"
        echo "  repair          - Repair/recreate corrupted database"
        echo ""
        echo "Examples:"
        echo "  $0 start        # Start the dashboard"
        echo "  $0 logs 100     # Show last 100 log lines"
        echo "  $0 logs follow  # Follow logs in real-time"
        echo ""
        echo -e "${YELLOW}🚨 IMPORTANT: Always use this script to start the dashboard${NC}"
        echo -e "${YELLOW}   Never use 'python3 main.py' directly${NC}"
        ;;
esac
