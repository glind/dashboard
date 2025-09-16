# Coding Conventions for Buildly Projects

## 🐍 Python Code Standards

### File Organization
```python
"""
Module docstring describing purpose and usage.

This module handles email collection from Gmail API.
Provides EmailCollector class for async email fetching.
"""

# Standard library imports (alphabetical)
import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Union

# Third-party imports (alphabetical)
import aiohttp
from fastapi import HTTPException
from pydantic import BaseModel, ValidationError

# Local application imports
from config.settings import Settings
from collectors.base_collector import BaseCollector
from database import DatabaseManager
```

### Class Structure
```python
class EmailCollector(BaseCollector):
    """
    Collects email data from Gmail API.
    
    Inherits from BaseCollector and implements standard collection interface.
    Handles OAuth authentication and rate limiting automatically.
    
    Attributes:
        service_name (str): Name of the service for logging
        auth_client: Authenticated Gmail API client
        
    Example:
        collector = EmailCollector()
        emails = await collector.collect_data()
    """
    
    def __init__(self, config: Settings) -> None:
        """Initialize collector with configuration."""
        super().__init__(config)
        self.service_name = "gmail"
        self.auth_client = None
        self._setup_logging()
    
    async def collect_data(self) -> List[Dict]:
        """
        Collect recent emails from Gmail.
        
        Returns:
            List[Dict]: Email data with standard format
            
        Raises:
            APIException: When Gmail API is unavailable
            AuthError: When authentication fails
        """
        try:
            # Implementation here
            pass
        except Exception as e:
            self.logger.error(f"Failed to collect emails: {e}")
            raise
    
    def _setup_logging(self) -> None:
        """Configure logging for this collector."""
        self.logger = logging.getLogger(f"collectors.{self.service_name}")
```

### Function Standards
```python
async def process_email_content(
    email_data: Dict[str, Any],
    include_attachments: bool = False,
    max_content_length: int = 10000
) -> ProcessedEmail:
    """
    Process raw email data into structured format.
    
    Args:
        email_data: Raw email data from Gmail API
        include_attachments: Whether to download and process attachments
        max_content_length: Maximum content length to process
        
    Returns:
        ProcessedEmail: Structured email object with cleaned content
        
    Raises:
        ValueError: When email_data is invalid or missing required fields
        ProcessingError: When content processing fails
        
    Example:
        email = await process_email_content(
            raw_data,
            include_attachments=True,
            max_content_length=5000
        )
    """
    if not email_data or 'id' not in email_data:
        raise ValueError("Invalid email data: missing required 'id' field")
    
    try:
        # Processing logic here
        return processed_email
    except Exception as e:
        logging.error(f"Failed to process email {email_data.get('id')}: {e}")
        raise ProcessingError(f"Email processing failed: {e}") from e
```

### Error Handling Patterns
```python
# ✅ GOOD: Specific exception handling with logging
try:
    result = await api_call()
    return result
except aiohttp.ClientTimeout:
    self.logger.warning("API timeout, retrying with longer timeout")
    return await self._retry_with_backoff(api_call)
except aiohttp.ClientError as e:
    self.logger.error(f"API client error: {e}")
    raise APIException(f"Failed to connect to service: {e}")
except Exception as e:
    self.logger.error(f"Unexpected error in {self.__class__.__name__}: {e}")
    raise

# ❌ BAD: Generic exception handling
try:
    result = api_call()
    return result
except:
    return None
```

### Configuration Handling
```python
from pydantic import BaseSettings, Field
from typing import Optional
import os

class CollectorSettings(BaseSettings):
    """Configuration for data collectors."""
    
    gmail_enabled: bool = Field(True, description="Enable Gmail collection")
    gmail_max_emails: int = Field(50, description="Maximum emails to collect")
    gmail_oauth_scopes: List[str] = Field(
        default=["https://www.googleapis.com/auth/gmail.readonly"],
        description="Gmail OAuth scopes"
    )
    
    # 🔐 SECURITY: Always load secrets from environment
    gmail_client_id: Optional[str] = Field(None, description="Gmail OAuth client ID")
    gmail_client_secret: Optional[str] = Field(None, description="Gmail OAuth client secret")
    github_token: Optional[str] = Field(None, description="GitHub API token")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    
    class Config:
        env_file = ".env"
        env_prefix = "DASHBOARD_"
        
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Validate critical secrets are present
        if self.gmail_enabled and not self.gmail_client_id:
            raise ValueError("GMAIL_CLIENT_ID environment variable required when Gmail is enabled")
            
        if self.gmail_enabled and not self.gmail_client_secret:
            raise ValueError("GMAIL_CLIENT_SECRET environment variable required when Gmail is enabled")

# ❌ NEVER DO THIS - Hardcoded secrets
class BadSettings:
    GMAIL_CLIENT_ID = "123456789.apps.googleusercontent.com"  # NEVER!
    GMAIL_CLIENT_SECRET = "GOCSPX-abcd1234"  # NEVER!
    GITHUB_TOKEN = "ghp_1234567890"  # NEVER!

# ✅ ALWAYS DO THIS - Environment-based secrets
class GoodSettings:
    def __init__(self):
        self.gmail_client_id = os.getenv("GMAIL_CLIENT_ID")
        self.gmail_client_secret = os.getenv("GMAIL_CLIENT_SECRET")
        self.github_token = os.getenv("GITHUB_TOKEN")
        
        # Validate required secrets
        if not self.gmail_client_id:
            raise ValueError("GMAIL_CLIENT_ID environment variable not set")
```

## 🎨 Frontend Code Standards

### HTML Structure (Embedded in Python)
```python
def generate_dashboard_html() -> str:
    """Generate responsive dashboard HTML with Tailwind CSS."""
    return f"""
    <!DOCTYPE html>
    <html lang="en" class="h-full">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Personal Dashboard</title>
        <script src="https://cdn.tailwindcss.com"></script>
        <link rel="stylesheet" href="/static/dashboard.css">
    </head>
    <body class="h-full bg-gray-50">
        <div id="app" class="min-h-full">
            {generate_header_section()}
            {generate_main_content()}
            {generate_footer_section()}
        </div>
        <script src="/static/dashboard.js"></script>
    </body>
    </html>
    """
```

### CSS Classes (Tailwind)
```python
# ✅ GOOD: Consistent, semantic class usage
def create_card_component(title: str, content: str, urgent: bool = False) -> str:
    """Create a styled card component."""
    urgency_classes = "border-red-500 bg-red-50" if urgent else "border-gray-200 bg-white"
    
    return f"""
    <div class="rounded-lg border-2 {urgency_classes} p-6 shadow-sm hover:shadow-md transition-shadow">
        <h3 class="text-lg font-semibold text-gray-900 mb-3">{title}</h3>
        <div class="text-gray-700 space-y-2">
            {content}
        </div>
    </div>
    """

# ❌ BAD: Inconsistent styling
def bad_card(title, content):
    return f'<div style="border: 1px solid #ccc; padding: 10px">{title}: {content}</div>'
```

### JavaScript (Embedded)
```python
def generate_dashboard_js() -> str:
    """Generate dashboard JavaScript with proper error handling."""
    return """
    class Dashboard {
        constructor() {
            this.apiBase = '/api/v1';
            this.refreshInterval = 30000; // 30 seconds
            this.init();
        }
        
        async init() {
            try {
                await this.loadInitialData();
                this.setupEventListeners();
                this.startAutoRefresh();
            } catch (error) {
                console.error('Dashboard initialization failed:', error);
                this.showError('Failed to initialize dashboard');
            }
        }
        
        async loadInitialData() {
            const endpoints = [
                'emails/recent',
                'calendar/today',
                'github/issues'
            ];
            
            const promises = endpoints.map(endpoint => 
                this.fetchWithTimeout(`${this.apiBase}/${endpoint}`)
            );
            
            const results = await Promise.allSettled(promises);
            results.forEach((result, index) => {
                if (result.status === 'fulfilled') {
                    this.renderSection(endpoints[index], result.value);
                } else {
                    console.warn(`Failed to load ${endpoints[index]}:`, result.reason);
                }
            });
        }
        
        async fetchWithTimeout(url, timeout = 5000) {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), timeout);
            
            try {
                const response = await fetch(url, {
                    signal: controller.signal,
                    headers: {
                        'Accept': 'application/json',
                        'Content-Type': 'application/json'
                    }
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP ${response.status}: ${response.statusText}`);
                }
                
                return await response.json();
            } finally {
                clearTimeout(timeoutId);
            }
        }
    }
    
    // Initialize when DOM is ready
    document.addEventListener('DOMContentLoaded', () => {
        new Dashboard();
    });
    """
```

## 🗄️ Database Code Standards

### Model Definitions
```python
from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class Email(Base):
    """Email message model with full metadata."""
    
    __tablename__ = 'emails'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(String(255), unique=True, nullable=False, index=True)
    thread_id = Column(String(255), nullable=True, index=True)
    sender = Column(String(255), nullable=False, index=True)
    recipient = Column(String(255), nullable=False)
    subject = Column(Text, nullable=False)
    body_text = Column(Text, nullable=True)
    body_html = Column(Text, nullable=True)
    received_date = Column(DateTime, nullable=False, index=True)
    is_read = Column(Boolean, default=False, nullable=False)
    is_important = Column(Boolean, default=False, nullable=False)
    labels = Column(JSON, nullable=True)
    attachments = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self) -> str:
        return f"<Email(id={self.id}, sender='{self.sender}', subject='{self.subject[:50]}...')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert email to dictionary for JSON serialization."""
        return {
            'id': self.id,
            'message_id': self.message_id,
            'sender': self.sender,
            'subject': self.subject,
            'received_date': self.received_date.isoformat(),
            'is_read': self.is_read,
            'is_important': self.is_important,
            'labels': self.labels or [],
            'preview': self.body_text[:200] if self.body_text else ''
        }
```

### Database Operations
```python
class DatabaseManager:
    """Centralized database operations with proper error handling."""
    
    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.session_factory = None
        
    async def connect(self) -> None:
        """Initialize database connection."""
        try:
            self.engine = create_async_engine(self.database_url)
            self.session_factory = async_sessionmaker(self.engine)
            logging.info("Database connection established")
        except Exception as e:
            logging.error(f"Database connection failed: {e}")
            raise DatabaseError(f"Failed to connect to database: {e}")
    
    async def save_emails(self, emails: List[Dict[str, Any]]) -> int:
        """
        Save multiple emails to database with deduplication.
        
        Args:
            emails: List of email dictionaries
            
        Returns:
            int: Number of emails actually saved (excluding duplicates)
            
        Raises:
            DatabaseError: When save operation fails
        """
        if not emails:
            return 0
            
        saved_count = 0
        async with self.session_factory() as session:
            try:
                for email_data in emails:
                    # Check for existing email
                    existing = await session.execute(
                        select(Email).where(Email.message_id == email_data['message_id'])
                    )
                    
                    if existing.scalar_one_or_none() is None:
                        email = Email(**email_data)
                        session.add(email)
                        saved_count += 1
                
                await session.commit()
                logging.info(f"Saved {saved_count} new emails to database")
                return saved_count
                
            except Exception as e:
                await session.rollback()
                logging.error(f"Failed to save emails: {e}")
                raise DatabaseError(f"Email save operation failed: {e}")
```

## 🧪 Testing Standards

### Unit Test Structure
```python
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from collectors.gmail_collector import GmailCollector

class TestGmailCollector:
    """Test suite for Gmail collector functionality."""
    
    @pytest.fixture
    def collector(self):
        """Create collector instance for testing."""
        config = MagicMock()
        config.gmail_enabled = True
        config.gmail_max_emails = 10
        return GmailCollector(config)
    
    @pytest.mark.asyncio
    async def test_collect_data_success(self, collector):
        """Test successful email collection."""
        # Arrange
        mock_emails = [
            {
                'id': 'email1',
                'sender': 'test@example.com',
                'subject': 'Test Email',
                'received_date': '2023-01-01T10:00:00Z'
            }
        ]
        
        with patch.object(collector, '_fetch_emails', return_value=mock_emails):
            # Act
            result = await collector.collect_data()
            
            # Assert
            assert len(result) == 1
            assert result[0]['sender'] == 'test@example.com'
            assert result[0]['subject'] == 'Test Email'
    
    @pytest.mark.asyncio
    async def test_collect_data_api_error(self, collector):
        """Test handling of API errors."""
        # Arrange
        with patch.object(collector, '_fetch_emails', side_effect=Exception("API Error")):
            # Act & Assert
            with pytest.raises(Exception) as exc_info:
                await collector.collect_data()
            
            assert "API Error" in str(exc_info.value)
    
    def test_email_processing(self, collector):
        """Test email data processing and validation."""
        # Arrange
        raw_email = {
            'payload': {
                'headers': [
                    {'name': 'From', 'value': 'sender@example.com'},
                    {'name': 'Subject', 'value': 'Test Subject'}
                ]
            },
            'internalDate': '1640995200000'
        }
        
        # Act
        processed = collector._process_email(raw_email)
        
        # Assert
        assert processed['sender'] == 'sender@example.com'
        assert processed['subject'] == 'Test Subject'
        assert 'received_date' in processed
```

## 🔧 Configuration Standards

### Environment Variables
```bash
# .env.example - SAFE TO COMMIT (template with placeholders)
# Database Configuration
DATABASE_URL=sqlite:///./dashboard.db
DATABASE_ECHO=false

# API Configuration
DASHBOARD_PORT=8008
DASHBOARD_HOST=0.0.0.0
DASHBOARD_DEBUG=false

# 🔐 SECRETS - Replace with actual values in .env file
# Gmail Configuration (OAuth 2.0)
GMAIL_ENABLED=true
GMAIL_MAX_EMAILS=50
GMAIL_CLIENT_ID=your_gmail_client_id_here
GMAIL_CLIENT_SECRET=your_gmail_client_secret_here

# GitHub Configuration
GITHUB_ENABLED=true
GITHUB_TOKEN=your_github_personal_access_token_here
GITHUB_USERNAME=your_github_username_here

# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-3.5-turbo

# Weather API
OPENWEATHER_API_KEY=your_openweather_api_key_here

# Logging Configuration
LOG_LEVEL=INFO
LOG_FILE=dashboard.log
LOG_MAX_SIZE=10MB
LOG_BACKUP_COUNT=5
```

```bash
# .env - NEVER COMMIT THIS FILE (contains real secrets)
# This file should be in .gitignore and contain actual API keys
GMAIL_CLIENT_ID=123456789.apps.googleusercontent.com
GMAIL_CLIENT_SECRET=GOCSPX-abcd1234567890
GITHUB_TOKEN=ghp_abcdef1234567890
OPENAI_API_KEY=sk-abcdef1234567890
OPENWEATHER_API_KEY=1234567890abcdef
```

```gitignore
# .gitignore - Ensure these patterns are included
# Environment files with secrets
.env
.env.local
.env.production
.env.staging

# API credentials and tokens
*_credentials.json
tokens/
*.key
*.pem
credentials/

# OAuth state files
google_state.txt
*_oauth_state.json
```

### YAML Configuration
```yaml
# config/config.yaml
dashboard:
  title: "Personal Dashboard"
  refresh_interval: 300  # 5 minutes
  timezone: "UTC"
  
collections:
  gmail:
    enabled: true
    max_emails: 50
    include_labels: ["INBOX", "IMPORTANT"]
    exclude_labels: ["SPAM", "TRASH"]
  
  github:
    enabled: true
    include_repos: ["personal/*", "work/*"]
    issue_states: ["open"]
  
  calendar:
    enabled: true
    days_ahead: 7
    include_all_day: true

ai:
  default_provider: "ollama"
  fallback_provider: "openai"
  conversation_history: 50
  
  providers:
    ollama:
      base_url: "http://localhost:11434"
      model: "llama2"
      timeout: 30
    
    openai:
      model: "gpt-3.5-turbo"
      max_tokens: 1000
      temperature: 0.7

logging:
  level: "INFO"
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
  handlers:
    - type: "file"
      filename: "dashboard.log"
      max_size: "10MB"
      backup_count: 5
    - type: "console"
      level: "DEBUG"
```

These coding conventions ensure consistency, maintainability, and quality across all Buildly projects. Follow these patterns when implementing new features or modifying existing code.
