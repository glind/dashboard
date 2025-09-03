# 🚨 CRITICAL STARTUP PROTOCOL 🚨

## MANDATORY STARTUP COMMAND
**ALWAYS use `./startup.sh` to start the dashboard - NEVER use any other method!**

### ✅ CORRECT:
```bash
./startup.sh
```

### ❌ WRONG (DO NOT USE):
- `python3 main.py`
- `python -m uvicorn`
- `uvicorn dashboard.server:app`
- Any direct Python execution

## Why startup.sh is REQUIRED:
1. **Virtual Environment**: Activates the correct venv
2. **Dependencies**: Installs/updates all required packages
3. **Database**: Initializes SQLite database properly
4. **Environment**: Sets up proper environment variables
5. **Port Configuration**: Starts server on correct port (8008)
6. **Health Checks**: Verifies all systems are working

## Emergency Restart:
If the dashboard is stuck or not responding:
```bash
pkill -f "main.py"
./startup.sh
```

## Verification:
After starting, verify it's working:
```bash
curl http://localhost:8008/health
```

**This protocol MUST be followed by ALL AI assistants working on this project.**
