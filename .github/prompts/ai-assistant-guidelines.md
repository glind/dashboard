# AI Assistant Guidelines for Buildly Projects

## 🤖 Core AI Assistant Principles

When working on Buildly projects, ALL AI assistants must follow these guidelines to ensure consistency, quality, and proper project management.

## 🔍 Pre-Work Investigation Protocol

### STEP 1: Read Memory Files (ALWAYS FIRST)
Before starting ANY work, read these files in order:
1. `.github/copilot-instructions.md` - Project-specific instructions
2. `.github/prompts/buildly-development-standards.md` - Development standards
3. `.github/prompts/project-structure.md` - File organization rules
4. `devdocs/README.md` - Project overview and status
5. `devdocs/code-organization.md` - Current architecture

### STEP 2: Understand Project Context
- **Check database content**: What real data exists?
- **Review recent changes**: Check git logs or recent file modifications
- **Identify working features**: What's currently functional?
- **Understand user preferences**: Check for preference files or settings

### STEP 3: Gather Task-Specific Context
- **Read relevant files**: Don't assume, verify current implementation
- **Check dependencies**: What other files/systems are affected?
- **Review documentation**: Understand the intended behavior
- **Test current state**: Verify what's working before making changes

## 🎯 Task Execution Standards

### Always Use Proper Startup Process
```bash
✅ CORRECT: ./startup.sh
❌ NEVER:   python main.py
❌ NEVER:   python3 -m uvicorn main:app
❌ NEVER:   Any other startup method
```

### Data Quality Standards
- **Always use REAL user data** - Never return placeholder text like "[Company Name]" or "example@email.com"
- **Verify data exists** - Check database content before making assumptions
- **Provide real-time data** - Access current data, not cached or example data
- **Handle missing data gracefully** - Show "No data available" rather than fake data

### Code Organization Requirements
- **Follow established patterns** - Match existing code style and structure
- **Use proper imports** - Follow the import order standards
- **Implement error handling** - Every function should handle potential failures
- **Add comprehensive logging** - Help with debugging and monitoring

### Documentation Standards
- **All docs go in `devdocs/`** - NEVER put documentation in project root
- **Update existing docs** - Don't create duplicate documentation
- **Include examples** - Provide real, working examples
- **Keep current** - Update docs when changing functionality

## 🧠 AI Chat & Analysis Guidelines

### Context Building Rules
When providing AI chat responses:
1. **Access real-time data** - Use `build_ai_context()` to get current information
2. **Combine multiple sources** - Emails, calendar, GitHub issues, etc.
3. **Provide specific insights** - Actionable recommendations based on actual data
4. **Reference real events** - Use actual email subjects, meeting titles, issue numbers

### Response Quality Standards
```python
# ✅ GOOD: Real data with specific details
"Based on your 15 unread emails, including the urgent GitHub security alert 
from yesterday and the meeting request from Sarah for next Tuesday's project 
review, I recommend..."

# ❌ BAD: Generic placeholder responses
"Based on your emails from [Sender Name] about [Topic], I recommend..."
```

### Learning & Adaptation
- **Track user preferences** - Learn from user interactions and feedback
- **Adapt responses** - Adjust communication style based on user needs
- **Remember context** - Use conversation history for better responses
- **Improve over time** - Continuously enhance based on usage patterns

## 🛠 Development Workflow

### Adding New Features
1. **Plan first** - Understand requirements fully before coding
2. **Check existing patterns** - Follow established code organization
3. **Create proper structure** - Use correct directories and naming
4. **Write comprehensive tests** - Ensure functionality works correctly
5. **Document thoroughly** - Add to appropriate `devdocs/` sections
6. **Test integration** - Verify feature works with existing system

### Debugging Issues
1. **Reproduce the problem** - Understand exactly what's failing
2. **Check logs and data** - Review `dashboard.log` and database content
3. **Trace the flow** - Follow data from collection to display
4. **Test systematically** - Isolate the specific failing component
5. **Fix root cause** - Don't just patch symptoms
6. **Verify solution** - Test the complete user workflow

### Code Quality Standards
- **Use type hints** - All function parameters and returns should be typed
- **Write docstrings** - Document what functions do and how to use them
- **Handle errors gracefully** - Provide meaningful error messages
- **Follow naming conventions** - Use clear, descriptive names
- **Keep functions focused** - Single responsibility principle

## ⚠️ Critical Don'ts

### Critical Don'ts

### Never Do These Things
1. **DON'T start services incorrectly** - Always use `./startup.sh`
2. **DON'T put docs in root** - Only use `devdocs/` for documentation
3. **DON'T return fake data** - Always use real user data from database
4. **DON'T ignore existing patterns** - Follow established code organization
5. **DON'T skip error handling** - Every function should handle failures
6. **DON'T forget to test** - Verify changes work before completing tasks
7. **🔐 DON'T HARDCODE SECRETS** - NEVER put API keys, tokens, or passwords in code files
8. **🔐 DON'T COMMIT SECRETS** - Always use .env files and proper .gitignore
9. **🔐 DON'T EXPOSE CREDENTIALS** - Never log, print, or display secret values

### Data Handling Warnings
- **Never hardcode example data** - Use real data from APIs and database
- **Never show placeholder emails** - Remove or replace any mock data
- **Never cache stale data** - Always get current information
- **Never expose credentials** - Keep API keys and tokens secure

### 🔐 CRITICAL SECURITY RULES

#### Secrets and Token Management
**ABSOLUTE RULES - NO EXCEPTIONS:**

1. **NEVER store secrets in code files**
   ```python
   # ❌ NEVER DO THIS - Hardcoded secrets in code
   GITHUB_TOKEN = "ghp_1234567890abcdef"
   OPENAI_API_KEY = "sk-1234567890abcdef"
   GMAIL_CLIENT_SECRET = "GOCSPX-abcd1234"
   
   # ✅ ALWAYS DO THIS - Load from environment
   GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
   OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
   GMAIL_CLIENT_SECRET = os.getenv("GMAIL_CLIENT_SECRET")
   ```

2. **ALWAYS use .env file for secrets**
   ```bash
   # .env file (NEVER commit this file)
   GITHUB_TOKEN=your_actual_token_here
   OPENAI_API_KEY=your_actual_key_here
   GMAIL_CLIENT_ID=your_client_id_here
   GMAIL_CLIENT_SECRET=your_client_secret_here
   ```

3. **ALWAYS provide .env.example template**
   ```bash
   # .env.example (safe to commit - no real values)
   GITHUB_TOKEN=your_github_token_here
   OPENAI_API_KEY=your_openai_api_key_here
   GMAIL_CLIENT_ID=your_gmail_client_id_here
   GMAIL_CLIENT_SECRET=your_gmail_client_secret_here
   ```

4. **ALWAYS check .gitignore includes secrets**
   ```gitignore
   # Environment variables and secrets
   .env
   .env.local
   .env.production
   
   # Token files
   tokens/
   credentials/
   *.key
   *.pem
   *_credentials.json
   ```

#### Security Validation Checklist
Before completing ANY task involving API keys or credentials:

- [ ] No hardcoded secrets in any .py files
- [ ] All secrets loaded via `os.getenv()` or similar
- [ ] .env file exists with actual values (not committed)
- [ ] .env.example exists with placeholder values (safe to commit)
- [ ] .gitignore properly excludes all secret files
- [ ] No credentials visible in code comments or docstrings
- [ ] No API keys in configuration files committed to git
- [ ] Token files stored in gitignored directories only

#### Common Security Violations to Avoid
```python
# ❌ NEVER - Hardcoded in code
class GmailCollector:
    def __init__(self):
        self.client_id = "123456789.apps.googleusercontent.com"
        self.client_secret = "GOCSPX-abcd1234"

# ❌ NEVER - In configuration files committed to git
# config/config.yaml (if committed)
gmail:
  client_id: "real_client_id_here"
  client_secret: "real_secret_here"

# ❌ NEVER - In comments or docstrings
def setup_gmail():
    """
    Setup Gmail API client.
    Use client_id: 123456789.apps.googleusercontent.com
    Use client_secret: GOCSPX-abcd1234
    """

# ✅ ALWAYS - Proper environment variable usage
class GmailCollector:
    def __init__(self):
        self.client_id = os.getenv("GMAIL_CLIENT_ID")
        self.client_secret = os.getenv("GMAIL_CLIENT_SECRET")
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Gmail credentials not found in environment variables")
```

#### Emergency Response
If secrets are accidentally committed:
1. **Immediately revoke/regenerate** all exposed credentials
2. **Remove from git history** using git filter or BFG Repo-Cleaner
3. **Update .gitignore** to prevent future exposure
4. **Verify .env file** contains new credentials
5. **Test application** works with new credentials

## 🎯 Success Criteria

### Task Completion Checklist
- [ ] Feature works as expected with real data
- [ ] Code follows established patterns and conventions
- [ ] Documentation is updated in appropriate `devdocs/` section
- [ ] Error handling is implemented and tested
- [ ] Integration with existing features verified
- [ ] User can successfully use the feature via proper startup process

### Quality Assurance
- [ ] No placeholder or example data in responses
- [ ] All file organization follows project structure guidelines
- [ ] Proper error messages for failure scenarios
- [ ] Performance is acceptable for expected usage
- [ ] Security considerations are addressed
- [ ] Code is maintainable and well-documented

## 🔄 Continuous Improvement

### Learning from Each Session
- **Document new patterns** - Add successful approaches to guidelines
- **Identify common issues** - Update troubleshooting documentation
- **Refine processes** - Improve development workflow based on experience
- **Update standards** - Evolve guidelines as project grows

### User Feedback Integration
- **Track user preferences** - Remember what users like and dislike
- **Adapt communication style** - Match user's preferred level of detail
- **Improve suggestions** - Learn from which recommendations users follow
- **Enhance accuracy** - Continuously improve data interpretation and insights

This framework ensures all AI assistants provide consistent, high-quality assistance while maintaining project integrity and user satisfaction.
