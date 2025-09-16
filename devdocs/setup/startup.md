# 🚨 STARTUP PROTOCOL 🚨

## ALWAYS use the startup script:
```bash
./startup.sh
```

## ❌ NEVER use these:
- `python3 main.py`
- `python3 main.py` 
- `python -m uvicorn`
- Any other direct method

## What the startup script does:
The startup script automatically:
- ✅ Creates and activates virtual environment (.venv)
- ✅ Installs/updates all dependencies from requirements.txt
- ✅ Copies example config files if needed
- ✅ Starts server detached on port 8008
- ✅ Creates PID file for process management
- ✅ Generates dashboard.log for debugging

## Available Commands

### Start Dashboard (default)
```bash
./startup.sh
# or
./startup.sh start
```

### Stop Dashboard
```bash
./startup.sh stop
```

### Restart Dashboard
```bash
./startup.sh restart
```

### Check Status
```bash
./startup.sh status
```

### View Live Logs
```bash
./startup.sh logs
```

## Verification
After startup, verify:
- Server running on http://localhost:8008
- Health check: http://localhost:8008/health
- No errors in dashboard.log
- All widgets loading data
- No 404 errors in browser console

## Process Management
- **PID file**: `dashboard.pid` contains process ID
- **Log file**: `dashboard.log` contains all output
- **Background**: Server runs detached (continues after terminal closes)
- **Auto-stop**: Detects if already running, prevents duplicates

## Troubleshooting

### Server won't start
```bash
# Check the logs
./startup.sh logs

# Or view last 20 lines
tail -20 dashboard.log
```

### Port already in use
```bash
# Check what's using port 8008
lsof -i :8008

# Force stop and restart
./startup.sh stop
./startup.sh start
```

### Virtual environment issues
```bash
# Remove and recreate venv
rm -rf .venv
./startup.sh
```
