<!-- Use this file to provide workspace-specific custom instructions to Copilot. For more details, visit https://code.visualstudio.com/docs/copilot/copilot-customization#_use-a-githubcopilotinstructionsmd-file -->

## 🚨 CRITICAL STARTUP PROTOCOL 🚨
**ALWAYS use `./startup.sh` to start the dashboard - NEVER use `python3 main.py` directly!**
- ✅ Correct: `./startup.sh`
- ❌ Wrong: `python3 main.py`
- ❌ Wrong: `python -m uvicorn`
- ❌ Wrong: Any other method

**Why?** The startup.sh script:
- Activates the virtual environment
- Installs/updates dependencies
- Initializes the database
- Sets up proper environment variables
- Starts the server on the correct port (8008)

## Memory System
- Always check `LONG_TERM_MEMORY.md` before starting any work
- Update memory files when user preferences change
- User wants ALL data displayed with like/dislike functionality for learning preferences

## AI Assistant Memory System 🧠
**BEFORE starting any work, READ THESE FILES:**
1. `.github/prompts/ai-instructions.md` - Critical rules and guidelines
2. `.github/prompts/startup-protocol.md` - Mandatory startup process  
3. `.github/prompts/user-preferences.md` - User requirements and behavior
4. `.github/prompts/project-status.md` - Current system state
5. `.github/prompts/session-memory.md` - Session history and preferences

**This ensures ALL AI assistants have consistent, up-to-date information about:**
- How to start the server correctly
- User preferences and requirements
- Current working features
- Project architecture and status
- What NOT to break

## Completed Project Milestones
- [x] Verify that the copilot-instructions.md file in the .github directory is created.

- [x] Clarify Project Requirements
	<!-- Personal Dashboard Application with Python/Bash integration for Ollama, Google APIs, Apple APIs, GitHub, Todoist, etc. -->

- [x] Scaffold the Project
	<!-- Create Python project structure with data collectors, dashboard generator, and configuration -->

- [x] Customize the Project
	<!-- Implement API integrations, data processing, and HTML/Tailwind dashboard generation -->

- [x] Install Required Extensions
	<!-- Python extension for VS Code -->

- [x] Compile the Project
	<!-- Created startup.sh script that handles virtual environment and dependency installation -->

- [x] Create and Run Task
	<!-- Created startup.sh and dev.sh scripts for easy project management -->

- [x] Launch the Project
	<!-- Use ./startup.sh to run the dashboard application -->

- [x] Ensure Documentation is Complete
	<!-- README.md updated with comprehensive setup and usage instructions -->

## Project Overview
Personal Dashboard Application that:
- Connects to Ollama server for AI processing
- Integrates with Google APIs (Gmail, Calendar)
- Connects to Apple APIs and Reminders
- Pulls data from Todoist and GitHub Issues
- Integrates with Buildly Labs API
- Generates HTML dashboard with Tailwind CSS
- Provides KPIs and metrics for weekly/monthly tracking
- Identifies follow-up tasks and important items
