# 🚨 CRITICAL STARTUP PROTOCOL 🚨

## MANDATORY STARTUP COMMAND
**ALWAYS use `./startup.sh` to start the dashboard - NEVER use any other method!**

### ✅ CORRECT:
```bash
./startup.sh
```

### ❌ WRONG (DO NOT USE):
- `python3 main.py`
- `python3 simple_main.py`
- `python -m uvicorn`
- `uvicorn simple_main:app`
- Any direct Python execution

## What the startup script AUTOMATICALLY handles:
- 🔧 Virtual environment setup and activation
- 📦 Dependency installation and updates
- ⚙️ Configuration file initialization  
- 🚀 Server launch (detached on port 8008)
- 🔍 Health checks and verification
- 📊 Process ID management and logging

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

## 📚 Additional References
For detailed implementation guides, see `devdocs/setup/startup.md`
