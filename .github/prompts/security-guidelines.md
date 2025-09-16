# Security Guidelines for Buildly Projects

## 🔐 CRITICAL SECURITY RULES

**These rules are ABSOLUTE and apply to ALL AI assistants working on Buildly projects.**

## 🚨 Secret Management - ZERO TOLERANCE POLICY

### Rule #1: NEVER Store Secrets in Code
```python
# ❌ ABSOLUTELY FORBIDDEN - Hardcoded secrets
API_KEY = "sk-1234567890abcdef"
CLIENT_SECRET = "your-secret-here"
DATABASE_PASSWORD = "mypassword123"
OAUTH_TOKEN = "bearer-token-value"

# ✅ ALWAYS REQUIRED - Environment variable loading
API_KEY = os.getenv("API_KEY")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD")
OAUTH_TOKEN = os.getenv("OAUTH_TOKEN")
```

### Rule #2: ALWAYS Use .env Files
```bash
# .env file structure (NEVER commit this file)
# API Keys and Secrets
OPENAI_API_KEY=sk-your-actual-openai-key-here
GITHUB_TOKEN=ghp_your-actual-github-token-here
GMAIL_CLIENT_ID=123456789.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=GOCSPX-your-actual-client-secret
OPENWEATHER_API_KEY=your-actual-weather-api-key

# Database Credentials
DATABASE_URL=postgresql://user:password@localhost/db
REDIS_PASSWORD=your-redis-password

# OAuth and Authentication
JWT_SECRET_KEY=your-jwt-secret-key
SESSION_SECRET=your-session-secret
```

### Rule #3: ALWAYS Provide Safe Templates
```bash
# .env.example file (SAFE to commit)
# Copy this to .env and replace with real values
OPENAI_API_KEY=your_openai_api_key_here
GITHUB_TOKEN=your_github_personal_access_token_here
GMAIL_CLIENT_ID=your_gmail_client_id_here
GMAIL_CLIENT_SECRET=your_gmail_client_secret_here
OPENWEATHER_API_KEY=your_openweather_api_key_here

# Database Configuration
DATABASE_URL=sqlite:///./dashboard.db

# Authentication Secrets
JWT_SECRET_KEY=generate_a_secure_random_key_here
SESSION_SECRET=generate_another_secure_random_key_here
```

### Rule #4: ALWAYS Protect with .gitignore
```gitignore
# Environment files with secrets
.env
.env.local
.env.production
.env.staging
.env.development

# Credential files
*_credentials.json
credentials/
tokens/
*.key
*.pem
*.p12
*.pfx

# OAuth state files
*_oauth_state.json
google_state.txt
oauth_cache/

# API key files
api_keys/
secrets/
private/

# Certificate files
*.crt
*.cert
*.ca-bundle
```

## 🛡️ Secure Coding Patterns

### Environment Variable Loading
```python
import os
from typing import Optional

class SecureConfig:
    """Secure configuration management."""
    
    def __init__(self):
        # Required secrets - fail fast if missing
        self.openai_api_key = self._get_required_env("OPENAI_API_KEY")
        self.github_token = self._get_required_env("GITHUB_TOKEN")
        
        # Optional secrets - graceful fallback
        self.gmail_client_id = os.getenv("GMAIL_CLIENT_ID")
        self.gmail_client_secret = os.getenv("GMAIL_CLIENT_SECRET")
        
    def _get_required_env(self, key: str) -> str:
        """Get required environment variable or raise error."""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Required environment variable {key} not set")
        return value
    
    def _mask_secret(self, secret: str, show_chars: int = 4) -> str:
        """Safely mask secret for logging."""
        if len(secret) <= show_chars:
            return "*" * len(secret)
        return secret[:show_chars] + "*" * (len(secret) - show_chars)
```

### Safe Logging Practices
```python
import logging

class SecureLogger:
    """Logger that automatically masks sensitive information."""
    
    SENSITIVE_KEYS = [
        'password', 'secret', 'key', 'token', 'api_key',
        'client_secret', 'auth', 'credential', 'private'
    ]
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def log_config(self, config: dict):
        """Log configuration with secrets masked."""
        safe_config = {}
        for key, value in config.items():
            if any(sensitive in key.lower() for sensitive in self.SENSITIVE_KEYS):
                safe_config[key] = self._mask_value(str(value))
            else:
                safe_config[key] = value
        
        self.logger.info(f"Configuration loaded: {safe_config}")
    
    def _mask_value(self, value: str) -> str:
        """Mask sensitive values for logging."""
        if len(value) <= 8:
            return "*" * len(value)
        return value[:4] + "*" * (len(value) - 8) + value[-4:]

# Usage example
logger = SecureLogger("config")
config = {
    "api_url": "https://api.example.com",
    "api_key": "sk-1234567890abcdef",
    "timeout": 30
}
logger.log_config(config)
# Output: Configuration loaded: {'api_url': 'https://api.example.com', 'api_key': 'sk-1****def', 'timeout': 30}
```

### Secure API Client Pattern
```python
import aiohttp
from typing import Optional

class SecureAPIClient:
    """Base class for secure API clients."""
    
    def __init__(self, api_key: str, base_url: str):
        if not api_key:
            raise ValueError("API key is required")
        
        self.api_key = api_key
        self.base_url = base_url
        self.session: Optional[aiohttp.ClientSession] = None
    
    async def __aenter__(self):
        """Async context manager entry."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "Dashboard/1.0"
        }
        self.session = aiohttp.ClientSession(headers=headers)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    async def make_request(self, endpoint: str, **kwargs):
        """Make secure API request with error handling."""
        if not self.session:
            raise RuntimeError("Client not properly initialized")
        
        url = f"{self.base_url}/{endpoint}"
        
        try:
            async with self.session.get(url, **kwargs) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientError as e:
            # Log error without exposing API key
            logging.error(f"API request failed to {self.base_url}: {e}")
            raise

# Usage
async def fetch_data():
    api_key = os.getenv("API_KEY")
    async with SecureAPIClient(api_key, "https://api.example.com") as client:
        return await client.make_request("data")
```

## 🔍 Security Validation Checklist

### Before Committing Any Code:
- [ ] **No hardcoded secrets** - Scan all .py files for API keys, passwords, tokens
- [ ] **Environment variables used** - All secrets loaded via `os.getenv()`
- [ ] **.env file excluded** - Verify .gitignore contains .env patterns
- [ ] **.env.example provided** - Template file with placeholder values
- [ ] **Secrets validation** - Code fails gracefully when secrets missing
- [ ] **Safe logging** - No secrets visible in log output
- [ ] **Error messages safe** - No secrets exposed in error messages

### Security Scanning Commands:
```bash
# Check for potential hardcoded secrets
grep -r "sk-" . --exclude-dir=.git --exclude="*.example"
grep -r "ghp_" . --exclude-dir=.git --exclude="*.example"
grep -r "GOCSPX-" . --exclude-dir=.git --exclude="*.example"
grep -r "api_key.*=" . --exclude-dir=.git --exclude="*.example"

# Verify .env is not tracked
git status --ignored | grep ".env"

# Check for credential files
find . -name "*credential*" -o -name "*secret*" -o -name "*.key"
```

## 🚨 Emergency Response Protocol

### If Secrets Are Accidentally Committed:

1. **IMMEDIATE ACTIONS (within minutes):**
   ```bash
   # Revoke all exposed credentials immediately
   # - GitHub: Settings → Developer settings → Personal access tokens
   # - OpenAI: API keys → Revoke
   # - Google: Credentials → Delete OAuth client
   ```

2. **CLEAN GIT HISTORY:**
   ```bash
   # Remove from git history (use BFG Repo-Cleaner for large repos)
   git filter-branch --force --index-filter \
     'git rm --cached --ignore-unmatch .env' \
     --prune-empty --tag-name-filter cat -- --all
   
   # Force push (DANGEROUS - coordinate with team)
   git push origin --force --all
   ```

3. **REGENERATE ALL CREDENTIALS:**
   - Generate new API keys
   - Update .env file with new values
   - Test application functionality
   - Verify no references to old credentials remain

4. **PREVENT FUTURE INCIDENTS:**
   - Add pre-commit hooks to scan for secrets
   - Review and update .gitignore
   - Team training on security practices

## 🛠️ Recommended Tools

### Secret Scanning
- **git-secrets** - Prevent committing secrets
- **detect-secrets** - Find secrets in codebase
- **truffleHog** - Search for high entropy strings

### Environment Management
- **python-dotenv** - Load .env files in Python
- **environs** - Environment variable parsing
- **pydantic-settings** - Type-safe configuration

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/Yelp/detect-secrets
    rev: v1.4.0
    hooks:
      - id: detect-secrets
        args: ['--baseline', '.secrets.baseline']
```

Remember: **Security is not optional**. These guidelines protect both the project and users' data. When in doubt, err on the side of caution and ask for security review.
