"""
Database models and initialization for the Personal Dashboard.
"""

import sqlite3
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Database path - handle bundled apps properly
def get_database_path():
    """Get the appropriate database path for bundled vs script mode."""
    # Check if running as a PyInstaller bundle
    if getattr(sys, 'frozen', False) and hasattr(sys, '_MEIPASS'):
        # Running as bundle - store database in user's home directory
        config_dir = Path.home() / ".personal-dashboard"
        config_dir.mkdir(exist_ok=True)
        return str(config_dir / "dashboard.db")
    else:
        # Running as script - store in project root
        return str(Path(__file__).parent.parent / "dashboard.db")

DATABASE_PATH = get_database_path()


class DatabaseManager:
    """Manages SQLite database operations for the dashboard."""
    
    def __init__(self, db_path: str = DATABASE_PATH):
        """Initialize database manager."""
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize database tables."""
        try:
            # Ensure the directory exists for the database file
            db_dir = Path(self.db_path).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Credentials table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS credentials (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT UNIQUE NOT NULL,
                    credentials_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Authentication tokens table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS auth_tokens (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT UNIQUE NOT NULL,
                    token_data TEXT NOT NULL,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Collected data table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS collected_data (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT NOT NULL,
                    data_type TEXT NOT NULL,
                    data_content TEXT NOT NULL,
                    collection_date TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Settings table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    setting_key TEXT UNIQUE NOT NULL,
                    setting_value TEXT NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Dashboard sessions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dashboard_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_data TEXT NOT NULL,
                    kpis_data TEXT,
                    insights_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Email analysis table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    id TEXT PRIMARY KEY,
                    subject TEXT NOT NULL,
                    sender TEXT NOT NULL,
                    recipient TEXT,
                    body TEXT,
                    received_date TIMESTAMP,
                    priority TEXT DEFAULT 'medium',
                    is_analyzed INTEGER DEFAULT 0,
                    ollama_priority TEXT,
                    has_todos INTEGER DEFAULT 0,
                    is_archived INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Universal todos table (from all sources)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS universal_todos (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    due_date TIMESTAMP,
                    priority TEXT DEFAULT 'medium',
                    category TEXT,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    status TEXT DEFAULT 'pending',
                    assigned_to_service TEXT,
                    requires_response INTEGER DEFAULT 0,
                    email_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    FOREIGN KEY (email_id) REFERENCES emails (id)
                )
            """)
            
            # Suggested todos table (awaiting user approval)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS suggested_todos (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT,
                    context TEXT,
                    source TEXT NOT NULL,
                    source_id TEXT,
                    source_title TEXT,
                    source_url TEXT,
                    priority TEXT DEFAULT 'medium',
                    due_date TIMESTAMP,
                    status TEXT DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP,
                    auto_extracted INTEGER DEFAULT 1
                )
            """)
            
            # News articles table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news_articles (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    snippet TEXT,
                    source TEXT,
                    published_date TIMESTAMP,
                    topics TEXT,
                    relevance_score REAL,
                    is_liked INTEGER DEFAULT 0,
                    is_read INTEGER DEFAULT 0,
                    user_feedback TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Music content table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS music_content (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    artist TEXT,
                    album TEXT,
                    url TEXT,
                    source TEXT,
                    release_date TIMESTAMP,
                    genres TEXT,
                    is_liked INTEGER DEFAULT 0,
                    user_feedback TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # User preferences and personality profile table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_personality_profile (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content_type TEXT NOT NULL,
                    content_id TEXT NOT NULL,
                    preference_score REAL DEFAULT 0.0,
                    keywords TEXT,
                    topics TEXT,
                    sentiment TEXT,
                    interaction_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Vanity Alerts table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS vanity_alerts (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    url TEXT,
                    snippet TEXT,
                    source TEXT,
                    search_term TEXT,
                    confidence_score REAL DEFAULT 0.0,
                    is_liked INTEGER DEFAULT 0,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Data cleanup log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS data_cleanup_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    cleanup_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    content_type TEXT NOT NULL,
                    items_removed INTEGER DEFAULT 0,
                    items_preserved INTEGER DEFAULT 0,
                    notes TEXT
                )
            """)
            
            # User feedback table for AI training
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT NOT NULL,
                    item_type TEXT NOT NULL,
                    item_title TEXT,
                    item_content TEXT,
                    item_metadata TEXT,
                    feedback_type TEXT NOT NULL CHECK(feedback_type IN ('like', 'dislike')),
                    feedback_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    source_api TEXT,
                    category TEXT,
                    confidence_score REAL DEFAULT 0.5,
                    notes TEXT
                )
            """)
            
            # Dashboard projects table for persisting discovered dashboards
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS dashboard_projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    path TEXT NOT NULL,
                    type TEXT NOT NULL,
                    port INTEGER,
                    start_command TEXT,
                    url TEXT,
                    github_pages_url TEXT,
                    custom_domain TEXT,
                    brand TEXT,
                    description TEXT,
                    health_endpoint TEXT,
                    production_url TEXT,
                    api_url TEXT,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Add new columns if they don't exist (migration)
            try:
                cursor.execute("ALTER TABLE dashboard_projects ADD COLUMN production_url TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute("ALTER TABLE dashboard_projects ADD COLUMN api_url TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            # Create indexes for better performance
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_collected_data_service_date ON collected_data(service_name, collection_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_credentials_service ON credentials(service_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_auth_tokens_service ON auth_tokens(service_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_received_date ON emails(received_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_priority ON emails(priority)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_analyzed ON emails(is_analyzed)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_todos_due_date ON universal_todos(due_date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_todos_priority ON universal_todos(priority)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_todos_status ON universal_todos(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_todos_source ON universal_todos(source)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_articles_liked ON news_articles(is_liked)")
            
            # Migration: Add is_read column to news_articles if it doesn't exist
            try:
                cursor.execute("SELECT is_read FROM news_articles LIMIT 1")
            except sqlite3.OperationalError:
                logger.info("Adding is_read column to news_articles table")
                cursor.execute("ALTER TABLE news_articles ADD COLUMN is_read INTEGER DEFAULT 0")
            
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_articles_read ON news_articles(is_read)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_music_content_liked ON music_content(is_liked)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vanity_alerts_liked ON vanity_alerts(is_liked)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_personality_profile_type ON user_personality_profile(content_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_personality_profile_content ON user_personality_profile(content_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_created_at ON news_articles(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_music_created_at ON music_content(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_vanity_created_at ON vanity_alerts(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_feedback_type ON user_feedback(feedback_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_feedback_item ON user_feedback(item_type, item_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_feedback_timestamp ON user_feedback(feedback_timestamp)")
            
            # AI Assistant tables
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_providers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    provider_type TEXT NOT NULL,
                    base_url TEXT,
                    api_key TEXT,
                    model_name TEXT,
                    config_data TEXT,
                    is_active INTEGER DEFAULT 0,
                    is_default INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_conversations (
                    id TEXT PRIMARY KEY,
                    provider_id INTEGER NOT NULL,
                    title TEXT,
                    context_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (provider_id) REFERENCES ai_providers (id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES ai_conversations (id)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_training_data (
                    id TEXT PRIMARY KEY,
                    data_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    context TEXT,
                    user_feedback TEXT,
                    source_table TEXT,
                    source_id TEXT,
                    relevance_score REAL DEFAULT 0.5,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_model_training (
                    id TEXT PRIMARY KEY,
                    provider_id INTEGER NOT NULL,
                    training_status TEXT DEFAULT 'pending',
                    training_data_hash TEXT,
                    model_version TEXT,
                    training_started_at TIMESTAMP,
                    training_completed_at TIMESTAMP,
                    performance_metrics TEXT,
                    error_log TEXT,
                    FOREIGN KEY (provider_id) REFERENCES ai_providers (id)
                )
            """)
            
            # User profile table for AI personalization
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_profile (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    full_name TEXT,
                    preferred_name TEXT,
                    occupation TEXT,
                    company TEXT,
                    role TEXT,
                    work_focus TEXT,
                    interests TEXT,
                    communication_style TEXT,
                    timezone TEXT,
                    work_hours TEXT,
                    priorities TEXT,
                    bio TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # AI message feedback table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ai_message_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    conversation_id TEXT NOT NULL,
                    feedback_type TEXT NOT NULL,
                    rating INTEGER,
                    comment TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (message_id) REFERENCES ai_messages (id),
                    FOREIGN KEY (conversation_id) REFERENCES ai_conversations (id)
                )
            """)
            
            # Safe senders whitelist for email risk assessment
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS safe_email_senders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sender_email TEXT UNIQUE NOT NULL,
                    sender_domain TEXT NOT NULL,
                    added_reason TEXT,
                    marked_safe_count INTEGER DEFAULT 1,
                    last_seen TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for fast domain lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_safe_senders_domain 
                ON safe_email_senders(sender_domain)
            """)
            
            # News sources management table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS news_sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    url TEXT UNIQUE NOT NULL,
                    category TEXT DEFAULT 'general',
                    is_active INTEGER DEFAULT 1,
                    is_custom INTEGER DEFAULT 0,
                    last_fetched TIMESTAMP,
                    fetch_count INTEGER DEFAULT 0,
                    error_count INTEGER DEFAULT 0,
                    user_preference INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Investment tracking table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS investments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT NOT NULL,
                    name TEXT,
                    type TEXT NOT NULL, -- 'stock', 'crypto', 'currency'
                    exchange TEXT,
                    current_price REAL,
                    previous_price REAL,
                    change_percent REAL,
                    market_cap REAL,
                    volume REAL,
                    last_updated TIMESTAMP,
                    is_tracked INTEGER DEFAULT 1,
                    external_source TEXT, -- '5003_api', 'external_api', etc.
                    external_id TEXT,
                    user_notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Local services monitoring table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS local_services (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    service_name TEXT,
                    port INTEGER,
                    ip_address TEXT,
                    hostname TEXT,
                    service_type TEXT, -- 'web', 'api', 'database', etc.
                    status TEXT DEFAULT 'unknown', -- 'running', 'stopped', 'error'
                    last_checked TIMESTAMP,
                    response_time REAL,
                    endpoint_url TEXT,
                    is_monitored INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Network discovery table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS network_devices (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ip_address TEXT UNIQUE NOT NULL,
                    hostname TEXT,
                    mac_address TEXT,
                    device_type TEXT,
                    manufacturer TEXT,
                    open_ports TEXT, -- JSON array of open ports
                    services TEXT, -- JSON array of detected services
                    last_seen TIMESTAMP,
                    is_online INTEGER DEFAULT 0,
                    response_time REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # AI Assistant indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_providers_active ON ai_providers(is_active)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_providers_default ON ai_providers(is_default)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_conversations_provider ON ai_conversations(provider_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_messages_conversation ON ai_messages(conversation_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_messages_timestamp ON ai_messages(timestamp)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_training_data_type ON ai_training_data(data_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_training_data_created ON ai_training_data(created_at)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_model_training_provider ON ai_model_training(provider_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_ai_model_training_status ON ai_model_training(training_status)")
            
            # New table indexes
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_sources_active ON news_sources(is_active)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_news_sources_category ON news_sources(category)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_investments_symbol ON investments(symbol)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_investments_type ON investments(type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_investments_tracked ON investments(is_tracked)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_local_services_port ON local_services(port)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_local_services_status ON local_services(status)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_network_devices_ip ON network_devices(ip_address)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_network_devices_online ON network_devices(is_online)")
            
            conn.commit()
            logger.info("Database initialized successfully")
            
        except Exception as e:
            logger.error(f"Database initialization failed: {e}")
            # Attempt to rollback
            try:
                conn.rollback()
            except:
                pass
            raise RuntimeError(f"Database initialization failed: {e}")
        
        finally:
            try:
                conn.close()
            except:
                pass
    
    @contextmanager
    def get_connection(self):
        """Get database connection with automatic cleanup."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        try:
            yield conn
        finally:
            conn.close()
    
    # Credentials management
    def save_credentials(self, service_name: str, credentials: Dict[str, Any]):
        """Save service credentials."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            credentials_json = json.dumps(credentials)
            
            cursor.execute("""
                INSERT OR REPLACE INTO credentials (service_name, credentials_data, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (service_name, credentials_json))
            
            conn.commit()
            logger.info(f"Credentials saved for {service_name}")
    
    def get_credentials(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get service credentials."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT credentials_data FROM credentials WHERE service_name = ?",
                (service_name,)
            )
            
            row = cursor.fetchone()
            if row:
                return json.loads(row['credentials_data'])
            return None
    
    def list_configured_services(self) -> List[str]:
        """List all configured services."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT service_name FROM credentials")
            return [row['service_name'] for row in cursor.fetchall()]
    
    # Authentication tokens management
    def save_auth_token(self, service_name: str, access_token: str, refresh_token: Optional[str] = None, 
                       expires_in: Optional[int] = None, token_data: Optional[Dict[str, Any]] = None, 
                       expires_at: Optional[datetime] = None):
        """Save authentication token with flexible parameters."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Build token_data dict if not provided
            if token_data is None:
                token_data = {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "expires_in": expires_in
                }
            
            # Calculate expires_at if expires_in provided
            if expires_at is None and expires_in:
                expires_at = datetime.now() + timedelta(seconds=expires_in)
            
            token_json = json.dumps(token_data)
            
            cursor.execute("""
                INSERT OR REPLACE INTO auth_tokens (service_name, token_data, expires_at, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (service_name, token_json, expires_at))
            
            conn.commit()
            logger.info(f"Auth token saved for {service_name}")
    
    def save_oauth_state(self, service_name: str, state: str):
        """Save OAuth state for CSRF protection."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            expires_at = datetime.now() + timedelta(minutes=10)  # State expires in 10 minutes
            
            cursor.execute("""
                INSERT INTO auth_tokens (service_name, token_data, expires_at, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """, (f"{service_name}_oauth_state", json.dumps({"state": state}), expires_at))
            
            conn.commit()
    
    def verify_oauth_state(self, service_name: str, state: str) -> bool:
        """Verify OAuth state for CSRF protection."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT token_data, expires_at FROM auth_tokens 
                WHERE service_name = ? AND expires_at > CURRENT_TIMESTAMP
            """, (f"{service_name}_oauth_state",))
            
            row = cursor.fetchone()
            if row:
                stored_data = json.loads(row['token_data'])
                stored_state = stored_data.get("state")
                
                # Delete the state after verification (one-time use)
                cursor.execute("DELETE FROM auth_tokens WHERE service_name = ?", 
                             (f"{service_name}_oauth_state",))
                conn.commit()
                
                return stored_state == state
            return False
    
    def get_auth_token(self, service_name: str) -> Optional[Dict[str, Any]]:
        """Get authentication token."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT token_data, expires_at FROM auth_tokens WHERE service_name = ?",
                (service_name,)
            )
            
            row = cursor.fetchone()
            if row:
                token_data = json.loads(row['token_data'])
                # Check if token is expired
                if row['expires_at']:
                    expires_at = datetime.fromisoformat(row['expires_at'])
                    if expires_at < datetime.now():
                        logger.warning(f"Token for {service_name} has expired")
                        return None
                return token_data
            return None
    
    def is_service_authenticated(self, service_name: str) -> bool:
        """Check if service is authenticated."""
        # Check database first
        token = self.get_auth_token(service_name)
        credentials = self.get_credentials(service_name)
        
        if token is not None or credentials is not None:
            return True
        
        # For Google, also check file-based storage as fallback
        if service_name == "google":
            from pathlib import Path
            # Get project root (one level up from src/)
            project_root = Path(__file__).parent.parent
            google_file = project_root / "tokens" / "google_credentials.json"
            if google_file.exists():
                return True
                
        return False
    
    def get_auth_status(self) -> Dict[str, bool]:
        """Get authentication status for all services."""
        services = ['google', 'apple', 'todoist', 'ticktick', 'github', 'buildly']
        status = {}
        
        for service in services:
            status[service] = self.is_service_authenticated(service)
        
        return status
    
    # Data collection storage
    def save_collected_data(self, service_name: str, data_type: str, data: List[Dict[str, Any]], collection_date: datetime):
        """Save collected data."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            data_json = json.dumps(data, default=str)  # default=str handles datetime objects
            
            # Remove old data for the same service and type from the same day
            cursor.execute("""
                DELETE FROM collected_data 
                WHERE service_name = ? AND data_type = ? AND DATE(collection_date) = DATE(?)
            """, (service_name, data_type, collection_date))
            
            # Insert new data
            cursor.execute("""
                INSERT INTO collected_data (service_name, data_type, data_content, collection_date)
                VALUES (?, ?, ?, ?)
            """, (service_name, data_type, data_json, collection_date))
            
            conn.commit()
            logger.info(f"Saved {len(data)} {data_type} items for {service_name}")
    
    def get_collected_data(self, service_name: str, data_type: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Get collected data for a service and type within date range."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT data_content FROM collected_data 
                WHERE service_name = ? AND data_type = ? 
                AND collection_date BETWEEN ? AND ?
                ORDER BY collection_date DESC
            """, (service_name, data_type, start_date, end_date))
            
            all_data = []
            for row in cursor.fetchall():
                data = json.loads(row['data_content'])
                all_data.extend(data)
            
            return all_data
    
    def get_latest_collection_date(self, service_name: str) -> Optional[datetime]:
        """Get the latest collection date for a service."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT MAX(collection_date) as latest_date 
                FROM collected_data 
                WHERE service_name = ?
            """, (service_name,))
            
            row = cursor.fetchone()
            if row and row['latest_date']:
                return datetime.fromisoformat(row['latest_date'])
            return None
    
    # Settings management
    def save_setting(self, key: str, value: Any):
        """Save a setting."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            value_json = json.dumps(value)
            
            cursor.execute("""
                INSERT OR REPLACE INTO settings (setting_key, setting_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            """, (key, value_json))
            
            conn.commit()
    
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Get a setting."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT setting_value FROM settings WHERE setting_key = ?",
                (key,)
            )
            
            row = cursor.fetchone()
            if row:
                try:
                    # Try to parse as JSON first
                    return json.loads(row['setting_value'])
                except (json.JSONDecodeError, TypeError):
                    # If it fails, return the raw value (plain string)
                    return row['setting_value']
            return default
    
    # Dashboard sessions
    def save_dashboard_session(self, session_data: Dict[str, Any], kpis_data: Dict[str, Any], insights_data: List[str]):
        """Save dashboard session data."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            session_json = json.dumps(session_data, default=str)
            kpis_json = json.dumps(kpis_data, default=str)
            insights_json = json.dumps(insights_data)
            
            cursor.execute("""
                INSERT INTO dashboard_sessions (session_data, kpis_data, insights_data)
                VALUES (?, ?, ?)
            """, (session_json, kpis_json, insights_json))
            
            conn.commit()
            return cursor.lastrowid
    
    def get_latest_dashboard_session(self) -> Optional[Dict[str, Any]]:
        """Get the latest dashboard session."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT session_data, kpis_data, insights_data, created_at
                FROM dashboard_sessions 
                ORDER BY created_at DESC 
                LIMIT 1
            """)
            
            row = cursor.fetchone()
            if row:
                return {
                    'session_data': json.loads(row['session_data']),
                    'kpis_data': json.loads(row['kpis_data']),
                    'insights_data': json.loads(row['insights_data']),
                    'created_at': row['created_at']
                }
            return None
    
    # Cleanup operations
    def cleanup_old_data(self, days_to_keep: int = 90):
        """Clean up old collected data."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - days_to_keep)
            
            cursor.execute("""
                DELETE FROM collected_data 
                WHERE collection_date < ?
            """, (cutoff_date,))
            
            cursor.execute("""
                DELETE FROM dashboard_sessions 
                WHERE created_at < ?
            """, (cutoff_date,))
            
            conn.commit()
            logger.info(f"Cleaned up data older than {days_to_keep} days")

    # Email and todo management methods
    
    def save_email(self, email_data: Dict[str, Any]) -> bool:
        """Save an email to the database."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO emails 
                    (id, subject, sender, recipient, body, received_date, 
                     priority, is_analyzed, ollama_priority, has_todos)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    email_data.get('id'),
                    email_data.get('subject'),
                    email_data.get('sender'),
                    email_data.get('recipient'),
                    email_data.get('body'),
                    email_data.get('received_date'),
                    email_data.get('priority', 'medium'),
                    1 if email_data.get('is_analyzed') else 0,
                    email_data.get('ollama_priority'),
                    1 if email_data.get('has_todos') else 0
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving email: {e}")
            return False
    
    def save_todo(self, todo_data: Dict[str, Any]) -> bool:
        """Save a todo item to the universal todos table."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO universal_todos 
                    (id, title, description, due_date, priority, category, 
                     source, source_id, status, assigned_to_service, 
                     requires_response, email_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    todo_data.get('id'),
                    todo_data.get('title'),
                    todo_data.get('description'),
                    todo_data.get('due_date'),
                    todo_data.get('priority', 'medium'),
                    todo_data.get('category'),
                    todo_data.get('source'),
                    todo_data.get('source_id'),
                    todo_data.get('status', 'pending'),
                    todo_data.get('assigned_to_service'),
                    1 if todo_data.get('requires_response') else 0,
                    todo_data.get('email_id')
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving todo: {e}")
            return False
    
    def get_emails_by_priority(self, priority: str = None, analyzed_only: bool = False) -> List[Dict[str, Any]]:
        """Get emails filtered by priority and analysis status."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM emails WHERE 1=1"
                params = []
                
                if priority:
                    query += " AND (priority = ? OR ollama_priority = ?)"
                    params.extend([priority, priority])
                
                if analyzed_only:
                    query += " AND is_analyzed = 1"
                
                query += " ORDER BY received_date DESC"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                emails = []
                for row in rows:
                    emails.append({
                        'id': row[0],
                        'subject': row[1],
                        'sender': row[2],
                        'recipient': row[3],
                        'body': row[4],
                        'received_date': row[5],
                        'priority': row[6],
                        'is_analyzed': bool(row[7]),
                        'ollama_priority': row[8],
                        'has_todos': bool(row[9]),
                        'is_archived': bool(row[10]),
                        'created_at': row[11]
                    })
                
                return emails
                
        except Exception as e:
            logger.error(f"Error getting emails: {e}")
            return []
    
    def get_todos_by_source(self, source: str = None, status: str = None) -> List[Dict[str, Any]]:
        """Get todos filtered by source and status."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM universal_todos WHERE 1=1"
                params = []
                
                if source:
                    query += " AND source = ?"
                    params.append(source)
                
                if status:
                    query += " AND status = ?"
                    params.append(status)
                
                query += " ORDER BY due_date ASC, priority DESC"
                
                cursor.execute(query, params)
                rows = cursor.fetchall()
                
                todos = []
                for row in rows:
                    todos.append({
                        'id': row['id'],
                        'title': row['title'],
                        'description': row['description'],
                        'due_date': row['due_date'],
                        'priority': row['priority'],
                        'category': row['category'],
                        'source': row['source'],
                        'source_id': row['source_id'],
                        'source_title': row['source_title'],
                        'source_url': row['source_url'],
                        'status': row['status'],
                        'assigned_to_service': row['assigned_to_service'],
                        'requires_response': bool(row['requires_response']),
                        'email_id': row['email_id'],
                        'created_at': row['created_at'],
                        'completed_at': row['completed_at']
                    })
                
                return todos
                
        except Exception as e:
            logger.error(f"Error getting todos: {e}")
            return []
    
    def update_email_analysis(self, email_id: str, ollama_priority: str, has_todos: bool) -> bool:
        """Update email analysis results."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE emails 
                    SET is_analyzed = 1, ollama_priority = ?, has_todos = ?
                    WHERE id = ?
                """, (ollama_priority, 1 if has_todos else 0, email_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            logger.error(f"Error updating email analysis: {e}")
            return False

    def get_todos(self, include_completed: bool = False, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """Get all todos from the database."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Build query with filters
                conditions = []
                if not include_completed:
                    conditions.append("status != 'completed'")
                if not include_deleted:
                    conditions.append("status != 'deleted'")
                
                query = "SELECT * FROM universal_todos"
                if conditions:
                    query += " WHERE " + " AND ".join(conditions)
                query += " ORDER BY due_date ASC, priority DESC, created_at DESC"
                
                cursor.execute(query)
                rows = cursor.fetchall()
                
                todos = []
                for row in rows:
                    todos.append({
                        'id': row['id'],
                        'title': row['title'],
                        'description': row['description'],
                        'due_date': row['due_date'],
                        'priority': row['priority'],
                        'category': row['category'],
                        'source': row['source'],
                        'source_id': row['source_id'],
                        'source_title': row['source_title'],
                        'source_url': row['source_url'],
                        'status': row['status'],
                        'assigned_to_service': row['assigned_to_service'],
                        'requires_response': bool(row['requires_response']),
                        'email_id': row['email_id'],
                        'created_at': row['created_at'],
                        'completed_at': row['completed_at']
                    })
                
                return todos
                
        except Exception as e:
            logger.error(f"Error getting todos: {e}")
            return []

    def update_todo_status(self, todo_id: str, status: str) -> bool:
        """Update a todo's status."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Add completed timestamp if marking as completed
                if status == 'completed':
                    cursor.execute("""
                        UPDATE universal_todos 
                        SET status = ?, completed_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (status, todo_id))
                else:
                    cursor.execute("""
                        UPDATE universal_todos 
                        SET status = ?, completed_at = NULL
                        WHERE id = ?
                    """, (status, todo_id))
                
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error updating todo status: {e}")
            return False

    def delete_todo(self, todo_id: str) -> bool:
        """Mark a todo as deleted (soft delete) to prevent recreation."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE universal_todos 
                    SET status = 'deleted', completed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (todo_id,))
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error deleting todo: {e}")
            return False
    
    def permanently_delete_todo(self, todo_id: str) -> bool:
        """Permanently delete a todo from the database (hard delete)."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM universal_todos WHERE id = ?", (todo_id,))
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error permanently deleting todo: {e}")
            return False

    def update_todo_source_id(self, todo_id: str, source_id: str) -> bool:
        """Update a todo's source_id (e.g., TickTick ID)."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE universal_todos 
                    SET source_id = ?
                    WHERE id = ?
                """, (source_id, todo_id))
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error updating todo source_id: {e}")
            return False

    # Suggested todos methods
    
    def add_suggested_todo(self, todo_data: Dict[str, Any]) -> str:
        """Add a new suggested todo awaiting user approval."""
        import uuid
        
        try:
            todo_id = todo_data.get('id', str(uuid.uuid4()))
            
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO suggested_todos 
                    (id, title, description, context, source, source_id, source_title, source_url, priority, due_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    todo_id,
                    todo_data.get('title'),
                    todo_data.get('description', ''),
                    todo_data.get('context', ''),
                    todo_data.get('source'),
                    todo_data.get('source_id'),
                    todo_data.get('source_title'),
                    todo_data.get('source_url'),
                    todo_data.get('priority', 'medium'),
                    todo_data.get('due_date'),
                    'pending'
                ))
                conn.commit()
                return todo_id
                
        except Exception as e:
            logger.error(f"Error adding suggested todo: {e}")
            return None

    def get_suggested_todos(self, status: str = 'pending') -> List[Dict[str, Any]]:
        """Get suggested todos by status."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, description, context, source, source_id, source_title, 
                           source_url, priority, due_date, status, created_at, reviewed_at
                    FROM suggested_todos
                    WHERE status = ?
                    ORDER BY created_at DESC
                """, (status,))
                
                rows = cursor.fetchall()
                todos = []
                for row in rows:
                    todos.append({
                        'id': row[0],
                        'title': row[1],
                        'description': row[2],
                        'context': row[3],
                        'source': row[4],
                        'source_id': row[5],
                        'source_title': row[6],
                        'source_url': row[7],
                        'priority': row[8],
                        'due_date': row[9],
                        'status': row[10],
                        'created_at': row[11],
                        'reviewed_at': row[12]
                    })
                
                return todos
                
        except Exception as e:
            logger.error(f"Error getting suggested todos: {e}")
            return []
    
    def get_suggested_todos_by_source(self, source: str, source_id: str) -> List[Dict[str, Any]]:
        """Get suggested todos by source and source_id."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, description, context, source, source_id, source_title, 
                           source_url, priority, due_date, status, created_at, reviewed_at
                    FROM suggested_todos
                    WHERE source = ? AND source_id = ?
                    ORDER BY created_at DESC
                """, (source, source_id))
                
                rows = cursor.fetchall()
                todos = []
                for row in rows:
                    todos.append({
                        'id': row[0],
                        'title': row[1],
                        'description': row[2],
                        'context': row[3],
                        'source': row[4],
                        'source_id': row[5],
                        'source_title': row[6],
                        'source_url': row[7],
                        'priority': row[8],
                        'due_date': row[9],
                        'status': row[10],
                        'created_at': row[11],
                        'reviewed_at': row[12]
                    })
                
                return todos
                
        except Exception as e:
            logger.error(f"Error getting suggested todos by source: {e}")
            return []

    def approve_suggested_todo(self, suggestion_id: str) -> bool:
        """Approve a suggested todo and move it to the main todos list."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get the suggestion
                cursor.execute("SELECT * FROM suggested_todos WHERE id = ?", (suggestion_id,))
                row = cursor.fetchone()
                
                if not row:
                    logger.error(f"Suggested todo {suggestion_id} not found")
                    return False
                
                # Create the actual todo
                import uuid
                todo_id = str(uuid.uuid4())
                cursor.execute("""
                    INSERT INTO universal_todos 
                    (id, title, description, source, source_id, source_title, source_url, priority, due_date, status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending')
                """, (
                    todo_id,
                    row[1],  # title
                    row[2] or row[3],  # description or context
                    row[4],  # source
                    row[5],  # source_id
                    row[6],  # source_title
                    row[7],  # source_url
                    row[8],  # priority
                    row[9]   # due_date
                ))
                
                # Mark suggestion as approved
                cursor.execute("""
                    UPDATE suggested_todos 
                    SET status = 'approved', reviewed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (suggestion_id,))
                
                conn.commit()
                
                # Try to sync to TickTick (async, non-blocking)
                try:
                    import asyncio
                    from collectors.ticktick_collector import TickTickCollector
                    
                    # Create sync task in background
                    async def sync_to_ticktick():
                        try:
                            ticktick = TickTickCollector()
                            
                            # Map priority: 0=None, 1=Low, 3=Medium, 5=High
                            priority_map = {'low': 1, 'medium': 3, 'high': 5}
                            ticktick_priority = priority_map.get(row[8], 0) if row[8] else 0
                            
                            # Parse due date if present
                            due_date = None
                            if row[9]:  # due_date
                                from datetime import datetime
                                try:
                                    due_date = datetime.fromisoformat(row[9])
                                except:
                                    pass
                            
                            # Create task in TickTick
                            result = await ticktick.create_task(
                                title=row[1],  # title
                                content=row[2] or row[3] or "",  # description or context
                                due_date=due_date,
                                priority=ticktick_priority,
                                tags=['dashboard']
                            )
                            
                            if result:
                                logger.info(f"Synced todo '{row[1]}' to TickTick")
                            else:
                                logger.warning(f"Failed to sync todo '{row[1]}' to TickTick")
                                
                        except Exception as e:
                            logger.error(f"Error syncing to TickTick: {e}")
                    
                    # Run sync in background (don't wait)
                    try:
                        loop = asyncio.get_event_loop()
                        if loop.is_running():
                            asyncio.create_task(sync_to_ticktick())
                        else:
                            asyncio.run(sync_to_ticktick())
                    except:
                        # If we can't get event loop, skip sync
                        logger.warning("Could not sync to TickTick - no event loop")
                        
                except Exception as e:
                    logger.warning(f"TickTick sync skipped: {e}")
                
                return True
                
        except Exception as e:
            logger.error(f"Error approving suggested todo: {e}")
            return False

    def reject_suggested_todo(self, suggestion_id: str) -> bool:
        """Reject a suggested todo."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE suggested_todos 
                    SET status = 'rejected', reviewed_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (suggestion_id,))
                conn.commit()
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error(f"Error rejecting suggested todo: {e}")
            return False

    # Content lifecycle management methods
    
    def save_news_article(self, article_data: Dict[str, Any]) -> bool:
        """Save a news article to the database."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO news_articles 
                    (id, title, url, snippet, source, published_date, topics, relevance_score, user_feedback, is_read)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE((SELECT is_read FROM news_articles WHERE id = ?), 0))
                """, (
                    article_data.get('id'),
                    article_data.get('title'),
                    article_data.get('url'),
                    article_data.get('snippet'),
                    article_data.get('source'),
                    article_data.get('published_date'),
                    json.dumps(article_data.get('topics', [])),
                    article_data.get('relevance_score', 0.0),
                    article_data.get('user_feedback'),
                    article_data.get('id')  # For the subquery
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving news article: {e}")
            return False
    
    def mark_article_read(self, article_id: str) -> bool:
        """Mark a news article as read."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE news_articles SET is_read = 1 WHERE id = ?
                """, (article_id,))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error marking article as read: {e}")
            return False
    
    def get_unread_articles(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get unread news articles."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id, title, url, snippet, source, published_date, topics, relevance_score, is_liked, is_read
                    FROM news_articles
                    WHERE is_read = 0
                    ORDER BY published_date DESC, relevance_score DESC
                    LIMIT ?
                """, (limit,))
                
                articles = []
                for row in cursor.fetchall():
                    articles.append({
                        'id': row[0],
                        'title': row[1],
                        'url': row[2],
                        'snippet': row[3],
                        'source': row[4],
                        'published_date': row[5],
                        'topics': json.loads(row[6]) if row[6] else [],
                        'relevance_score': row[7],
                        'is_liked': bool(row[8]),
                        'is_read': bool(row[9])
                    })
                return articles
        except Exception as e:
            logger.error(f"Error getting unread articles: {e}")
            return []

    def save_music_content(self, music_data: Dict[str, Any]) -> bool:
        """Save music content to the database."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO music_content 
                    (id, title, artist, album, url, source, release_date, genres, user_feedback)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    music_data.get('id'),
                    music_data.get('title'),
                    music_data.get('artist'),
                    music_data.get('album'),
                    music_data.get('url'),
                    music_data.get('source'),
                    music_data.get('release_date'),
                    json.dumps(music_data.get('genres', [])),
                    music_data.get('user_feedback')
                ))
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error saving music content: {e}")
            return False

    def like_content(self, content_type: str, content_id: str, is_liked: bool = True) -> bool:
        """Mark content as liked/unliked and update personality profile."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Update the content table
                if content_type == 'news':
                    cursor.execute("""
                        UPDATE news_articles SET is_liked = ? WHERE id = ?
                    """, (1 if is_liked else 0, content_id))
                elif content_type == 'music':
                    cursor.execute("""
                        UPDATE music_content SET is_liked = ? WHERE id = ?
                    """, (1 if is_liked else 0, content_id))
                elif content_type == 'vanity_alert':
                    cursor.execute("""
                        UPDATE vanity_alerts SET is_liked = ? WHERE id = ?
                    """, (1 if is_liked else 0, content_id))
                
                # Update personality profile
                if is_liked:
                    self._update_personality_profile(cursor, content_type, content_id, 'like')
                else:
                    self._update_personality_profile(cursor, content_type, content_id, 'unlike')
                
                conn.commit()
                return True
        except Exception as e:
            logger.error(f"Error updating content like status: {e}")
            return False

    def _update_personality_profile(self, cursor, content_type: str, content_id: str, interaction_type: str):
        """Update user personality profile based on interaction."""
        try:
            # Get content details for personality analysis
            content_data = self._get_content_for_profile(cursor, content_type, content_id)
            
            if content_data:
                # Calculate preference score
                preference_score = 1.0 if interaction_type == 'like' else -0.5
                
                # Insert or update personality profile entry
                cursor.execute("""
                    INSERT OR REPLACE INTO user_personality_profile 
                    (content_type, content_id, preference_score, keywords, topics, sentiment, interaction_type, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    content_type,
                    content_id,
                    preference_score,
                    json.dumps(content_data.get('keywords', [])),
                    json.dumps(content_data.get('topics', [])),
                    content_data.get('sentiment', 'neutral'),
                    interaction_type,
                    datetime.now()
                ))
        except Exception as e:
            logger.error(f"Error updating personality profile: {e}")

    def _get_content_for_profile(self, cursor, content_type: str, content_id: str) -> Optional[Dict[str, Any]]:
        """Get content data for personality profile analysis."""
        try:
            if content_type == 'news':
                cursor.execute("""
                    SELECT title, topics, snippet FROM news_articles WHERE id = ?
                """, (content_id,))
                result = cursor.fetchone()
                if result:
                    return {
                        'keywords': result[0].split()[:10],  # Extract keywords from title
                        'topics': json.loads(result[1]) if result[1] else [],
                        'sentiment': 'positive'  # Could be enhanced with sentiment analysis
                    }
            elif content_type == 'music':
                cursor.execute("""
                    SELECT title, artist, genres FROM music_content WHERE id = ?
                """, (content_id,))
                result = cursor.fetchone()
                if result:
                    return {
                        'keywords': [result[1], result[0]],  # Artist and title
                        'topics': json.loads(result[2]) if result[2] else [],
                        'sentiment': 'positive'
                    }
            elif content_type == 'vanity_alert':
                cursor.execute("""
                    SELECT title, search_term, snippet FROM vanity_alerts WHERE id = ?
                """, (content_id,))
                result = cursor.fetchone()
                if result:
                    return {
                        'keywords': [result[1]],  # Search term
                        'topics': [result[1]],
                        'sentiment': 'positive'
                    }
            return None
        except Exception as e:
            logger.error(f"Error getting content for profile: {e}")
            return None

    def cleanup_unliked_content(self) -> Dict[str, int]:
        """Clean up old content that hasn't been liked (nightly cleanup)."""
        cleanup_stats = {'news': 0, 'music': 0, 'vanity_alerts': 0, 'preserved': 0}
        
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cutoff_date = datetime.now() - timedelta(days=1)  # Content from yesterday
                
                # Clean up news articles (keep liked ones)
                cursor.execute("""
                    SELECT COUNT(*) FROM news_articles 
                    WHERE created_at < ? AND (is_liked = 0 OR is_liked IS NULL)
                """, (cutoff_date,))
                cleanup_stats['news'] = cursor.fetchone()[0]
                
                cursor.execute("""
                    DELETE FROM news_articles 
                    WHERE created_at < ? AND (is_liked = 0 OR is_liked IS NULL)
                """, (cutoff_date,))
                
                # Clean up music content (keep liked ones)
                cursor.execute("""
                    SELECT COUNT(*) FROM music_content 
                    WHERE created_at < ? AND (is_liked = 0 OR is_liked IS NULL)
                """, (cutoff_date,))
                cleanup_stats['music'] = cursor.fetchone()[0]
                
                cursor.execute("""
                    DELETE FROM music_content 
                    WHERE created_at < ? AND (is_liked = 0 OR is_liked IS NULL)
                """, (cutoff_date,))
                
                # Clean up vanity alerts (keep liked ones)
                cursor.execute("""
                    SELECT COUNT(*) FROM vanity_alerts 
                    WHERE timestamp < ? AND (is_liked = 0 OR is_liked IS NULL)
                """, (cutoff_date,))
                cleanup_stats['vanity_alerts'] = cursor.fetchone()[0]
                
                cursor.execute("""
                    DELETE FROM vanity_alerts 
                    WHERE timestamp < ? AND (is_liked = 0 OR is_liked IS NULL)
                """, (cutoff_date,))
                
                # Count preserved items
                cursor.execute("""
                    SELECT COUNT(*) FROM 
                    (SELECT id FROM news_articles WHERE is_liked = 1
                     UNION ALL
                     SELECT id FROM music_content WHERE is_liked = 1
                     UNION ALL
                     SELECT id FROM vanity_alerts WHERE is_liked = 1)
                """)
                cleanup_stats['preserved'] = cursor.fetchone()[0]
                
                # Log cleanup
                cursor.execute("""
                    INSERT INTO data_cleanup_log (content_type, items_removed, items_preserved, notes)
                    VALUES (?, ?, ?, ?)
                """, (
                    'all_content',
                    cleanup_stats['news'] + cleanup_stats['music'] + cleanup_stats['vanity_alerts'],
                    cleanup_stats['preserved'],
                    f"Nightly cleanup: News({cleanup_stats['news']}), Music({cleanup_stats['music']}), Vanity({cleanup_stats['vanity_alerts']})"
                ))
                
                conn.commit()
                logger.info(f"Nightly cleanup completed: {cleanup_stats}")
                
        except Exception as e:
            logger.error(f"Error during content cleanup: {e}")
            
        return cleanup_stats

    def get_personality_profile(self) -> Dict[str, Any]:
        """Get user's personality profile based on liked content."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get preference statistics
                cursor.execute("""
                    SELECT content_type, 
                           COUNT(*) as interactions,
                           AVG(preference_score) as avg_score,
                           topics, keywords
                    FROM user_personality_profile 
                    WHERE preference_score > 0
                    GROUP BY content_type
                """)
                
                preferences = cursor.fetchall()
                
                # Aggregate topics and keywords
                all_topics = []
                all_keywords = []
                
                cursor.execute("""
                    SELECT topics, keywords FROM user_personality_profile 
                    WHERE preference_score > 0
                """)
                
                for row in cursor.fetchall():
                    if row[0]:  # topics
                        all_topics.extend(json.loads(row[0]))
                    if row[1]:  # keywords
                        all_keywords.extend(json.loads(row[1]))
                
                # Count frequencies
                from collections import Counter
                topic_counts = Counter(all_topics)
                keyword_counts = Counter(all_keywords)
                
                return {
                    'preferences_by_type': {pref[0]: {
                        'interactions': pref[1],
                        'avg_score': pref[2]
                    } for pref in preferences},
                    'top_topics': dict(topic_counts.most_common(10)),
                    'top_keywords': dict(keyword_counts.most_common(20)),
                    'total_liked_items': sum(pref[1] for pref in preferences),
                    'last_updated': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting personality profile: {e}")
            return {}

    def get_liked_content_summary(self) -> Dict[str, Any]:
        """Get summary of all liked content for AI personality training."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get liked news
                cursor.execute("""
                    SELECT title, topics, snippet, source FROM news_articles 
                    WHERE is_liked = 1 ORDER BY created_at DESC
                """)
                liked_news = cursor.fetchall()
                
                # Get liked music
                cursor.execute("""
                    SELECT title, artist, album, genres FROM music_content 
                    WHERE is_liked = 1 ORDER BY created_at DESC
                """)
                liked_music = cursor.fetchall()
                
                # Get liked vanity alerts
                cursor.execute("""
                    SELECT title, search_term, snippet, source FROM vanity_alerts 
                    WHERE is_liked = 1 ORDER BY timestamp DESC
                """)
                liked_vanity = cursor.fetchall()
                
                return {
                    'liked_news': [{'title': n[0], 'topics': json.loads(n[1]) if n[1] else [], 
                                   'snippet': n[2], 'source': n[3]} for n in liked_news],
                    'liked_music': [{'title': m[0], 'artist': m[1], 'album': m[2], 
                                    'genres': json.loads(m[3]) if m[3] else []} for m in liked_music],
                    'liked_vanity_alerts': [{'title': v[0], 'search_term': v[1], 
                                           'snippet': v[2], 'source': v[3]} for v in liked_vanity],
                    'total_count': len(liked_news) + len(liked_music) + len(liked_vanity),
                    'generated_at': datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error getting liked content summary: {e}")
            return {}
    
    def get_database_stats(self) -> Dict[str, int]:
        """Get database statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            stats = {}
            
            # Count records in each table
            tables = ['credentials', 'auth_tokens', 'collected_data', 'settings', 'dashboard_sessions']
            for table in tables:
                cursor.execute(f"SELECT COUNT(*) as count FROM {table}")
                stats[table] = cursor.fetchone()['count']
            
            # Get database file size
            db_path = Path(self.db_path)
            if db_path.exists():
                stats['database_size_mb'] = round(db_path.stat().st_size / (1024 * 1024), 2)
            else:
                stats['database_size_mb'] = 0
            
            return stats

    async def unlike_content(self, content_id: str, content_type: str) -> bool:
        """Unlike content (wrapper for like_content with is_liked=False)."""
        return self.like_content(content_type, content_id, is_liked=False)

    async def save_music_feedback(self, content_id: str, feedback: str) -> bool:
        """Save user feedback for music content."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Update the music content with feedback
                cursor.execute("""
                    UPDATE music_content 
                    SET user_feedback = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (feedback, content_id))
                
                if cursor.rowcount > 0:
                    conn.commit()
                    return True
                else:
                    return False
                    
        except Exception as e:
            logger.error(f"Error saving music feedback: {e}")
            return False

    async def get_liked_content(self, content_type: str = None) -> List[Dict[str, Any]]:
        """Get all liked content, optionally filtered by type."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                liked_content = []
                
                # Get liked news articles
                if content_type is None or content_type == 'news':
                    cursor.execute("""
                        SELECT id, title, url, snippet, source, published_date, 
                               topics, relevance_score, created_at, 'news' as content_type
                        FROM news_articles 
                        WHERE is_liked = 1 
                        ORDER BY created_at DESC
                    """)
                    news_results = cursor.fetchall()
                    for row in news_results:
                        liked_content.append({
                            'id': row[0],
                            'title': row[1],
                            'url': row[2],
                            'snippet': row[3],
                            'source': row[4],
                            'published_date': row[5],
                            'topics': row[6],
                            'relevance_score': row[7],
                            'created_at': row[8],
                            'content_type': row[9]
                        })
                
                # Get liked music content
                if content_type is None or content_type == 'music':
                    cursor.execute("""
                        SELECT id, title, artist, album, source, 
                               url, release_date, genres, created_at, 'music' as type
                        FROM music_content 
                        WHERE is_liked = 1 
                        ORDER BY created_at DESC
                    """)
                    music_results = cursor.fetchall()
                    for row in music_results:
                        liked_content.append({
                            'id': row[0],
                            'title': row[1],
                            'artist': row[2],
                            'album': row[3],
                            'source': row[4],
                            'url': row[5],
                            'release_date': row[6],
                            'genres': row[7],
                            'created_at': row[8],
                            'content_type': row[9]
                        })
                
                # Get liked vanity alerts
                if content_type is None or content_type == 'vanity_alert':
                    cursor.execute("""
                        SELECT id, title, url, snippet, source, search_term,
                               confidence_score, timestamp, 'vanity_alert' as content_type
                        FROM vanity_alerts 
                        WHERE is_liked = 1 
                        ORDER BY timestamp DESC
                    """)
                    vanity_results = cursor.fetchall()
                    for row in vanity_results:
                        liked_content.append({
                            'id': row[0],
                            'title': row[1],
                            'url': row[2],
                            'snippet': row[3],
                            'source': row[4],
                            'search_term': row[5],
                            'confidence_score': row[6],
                            'created_at': row[7],  # Using timestamp as created_at
                            'content_type': row[8]
                        })
                
                # Sort by creation date (most recent first)
                liked_content.sort(key=lambda x: x.get('created_at', ''), reverse=True)
                
                return liked_content
                
        except Exception as e:
            logger.error(f"Error getting liked content: {e}")
            return []

    def save_user_feedback(self, item_id: str, item_type: str, feedback_type: str, 
                          item_title: str = None, item_content: str = None, 
                          item_metadata: Dict[str, Any] = None, source_api: str = None, 
                          category: str = None, confidence_score: float = 0.5, notes: str = None) -> bool:
        """Save user feedback (like/dislike) for AI training."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Convert metadata to JSON string
                metadata_json = json.dumps(item_metadata) if item_metadata else None
                
                cursor.execute("""
                    INSERT INTO user_feedback 
                    (item_id, item_type, item_title, item_content, item_metadata, 
                     feedback_type, source_api, category, confidence_score, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (item_id, item_type, item_title, item_content, metadata_json,
                      feedback_type, source_api, category, confidence_score, notes))
                
                conn.commit()
                logger.info(f"Saved {feedback_type} feedback for {item_type}: {item_id}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving user feedback: {e}")
            return False
            
    def get_user_feedback(self, item_type: str = None, feedback_type: str = None, 
                         limit: int = 100) -> List[Dict[str, Any]]:
        """Get user feedback for AI training analysis."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM user_feedback WHERE 1=1"
                params = []
                
                if item_type:
                    query += " AND item_type = ?"
                    params.append(item_type)
                    
                if feedback_type:
                    query += " AND feedback_type = ?"
                    params.append(feedback_type)
                    
                query += " ORDER BY feedback_timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                feedback_rows = cursor.fetchall()
                
                feedback_list = []
                for row in feedback_rows:
                    feedback_data = {
                        'id': row['id'],
                        'item_id': row['item_id'],
                        'item_type': row['item_type'],
                        'item_title': row['item_title'],
                        'item_content': row['item_content'],
                        'item_metadata': json.loads(row['item_metadata']) if row['item_metadata'] else {},
                        'feedback_type': row['feedback_type'],
                        'feedback_timestamp': row['feedback_timestamp'],
                        'source_api': row['source_api'],
                        'category': row['category'],
                        'confidence_score': row['confidence_score'],
                        'notes': row['notes']
                    }
                    feedback_list.append(feedback_data)
                    
                return feedback_list
                
        except Exception as e:
            logger.error(f"Error getting user feedback: {e}")
            return []
            
    def get_user_preferences_summary(self) -> Dict[str, Any]:
        """Get summary of user preferences for AI training."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get feedback counts by type and category
                cursor.execute("""
                    SELECT item_type, feedback_type, category, COUNT(*) as count,
                           AVG(confidence_score) as avg_confidence
                    FROM user_feedback
                    GROUP BY item_type, feedback_type, category
                    ORDER BY count DESC
                """)
                
                summary_data = []
                for row in cursor.fetchall():
                    summary_data.append({
                        'item_type': row['item_type'],
                        'feedback_type': row['feedback_type'],
                        'category': row['category'],
                        'count': row['count'],
                        'avg_confidence': row['avg_confidence']
                    })
                    
                # Get total feedback counts
                cursor.execute("""
                    SELECT feedback_type, COUNT(*) as total_count
                    FROM user_feedback
                    GROUP BY feedback_type
                """)
                
                totals = {row['feedback_type']: row['total_count'] for row in cursor.fetchall()}
                
                return {
                    'detailed_summary': summary_data,
                    'totals': totals,
                    'total_feedback_items': sum(totals.values())
                }
                
        except Exception as e:
            logger.error(f"Error getting user preferences summary: {e}")
            return {'detailed_summary': [], 'totals': {}, 'total_feedback_items': 0}
    
    def get_rated_item_ids(self, item_type: str = None) -> Set[str]:
        """Get set of item IDs that have been rated (liked or disliked) to filter them out."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT DISTINCT item_id FROM user_feedback WHERE 1=1"
                params = []
                
                if item_type:
                    query += " AND item_type = ?"
                    params.append(item_type)
                
                cursor.execute(query, params)
                return {row['item_id'] for row in cursor.fetchall()}
                
        except Exception as e:
            logger.error(f"Error getting rated item IDs: {e}")
            return set()
    
    def get_liked_items(self, item_type: str = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Get items that have been liked for the 'Liked Items' section."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = """
                    SELECT item_id, item_type, item_title, item_content, item_metadata,
                           feedback_timestamp, source_api, category
                    FROM user_feedback 
                    WHERE feedback_type = 'like'
                """
                params = []
                
                if item_type:
                    query += " AND item_type = ?"
                    params.append(item_type)
                
                query += " ORDER BY feedback_timestamp DESC LIMIT ?"
                params.append(limit)
                
                cursor.execute(query, params)
                liked_items = []
                
                for row in cursor.fetchall():
                    item_data = {
                        'id': row['item_id'],
                        'type': row['item_type'],
                        'title': row['item_title'],
                        'content': row['item_content'] or '',
                        'metadata': json.loads(row['item_metadata']) if row['item_metadata'] else {},
                        'liked_at': row['feedback_timestamp'],
                        'source': row['source_api'],
                        'category': row['category'] or 'General'
                    }
                    liked_items.append(item_data)
                
                return liked_items
                
        except Exception as e:

                    logger.error(f"Error getting liked items: {e}")
                    return []

    # AI Assistant methods
    def save_ai_provider(self, name: str, provider_type: str, config: Dict[str, Any]) -> str:
        """Save AI provider configuration - updates if exists, creates if new."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Check if provider with this type and model already exists
            base_url = config.get('base_url', '')
            model_name = config.get('model_name', '')
            
            cursor.execute("""
                SELECT id FROM ai_providers 
                WHERE provider_type = ? AND model_name = ?
            """, (provider_type, model_name))
            
            existing = cursor.fetchone()
            
            # If this is set as default, unset ALL others first
            if config.get('is_default', False):
                cursor.execute("UPDATE ai_providers SET is_default = 0")
            
            if existing:
                # UPDATE existing provider
                provider_id = existing['id']
                cursor.execute("""
                    UPDATE ai_providers 
                    SET name = ?, base_url = ?, api_key = ?, config_data = ?, 
                        is_active = ?, is_default = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    name, base_url, config.get('api_key'),
                    json.dumps(config), config.get('is_active', 1), 
                    config.get('is_default', 0), provider_id
                ))
            else:
                # INSERT new provider
                cursor.execute("""
                    INSERT INTO ai_providers (name, provider_type, base_url, api_key, model_name, 
                                            config_data, is_active, is_default)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    name, provider_type, base_url, config.get('api_key'),
                    model_name, json.dumps(config), 
                    config.get('is_active', 1), config.get('is_default', 0)
                ))
                provider_id = cursor.lastrowid
            
            conn.commit()
            return str(provider_id)

    def get_ai_providers(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """Get AI providers."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM ai_providers"
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY is_default DESC, name"
            
            cursor.execute(query)
            providers = []
            for row in cursor.fetchall():
                provider = dict(row)
                provider['config_data'] = json.loads(provider['config_data']) if provider['config_data'] else {}
                providers.append(provider)
            return providers

    def get_default_ai_provider(self) -> Optional[Dict[str, Any]]:
        """Get default AI provider."""
        providers = self.get_ai_providers(active_only=True)
        for provider in providers:
            if provider['is_default']:
                return provider
        return providers[0] if providers else None

    def save_ai_conversation(self, conversation_id: str, provider_id: int, title: str = None, context: Dict = None):
        """Save AI conversation."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO ai_conversations (id, provider_id, title, context_data, updated_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            """, (conversation_id, provider_id, title, json.dumps(context or {})))
            conn.commit()

    def save_ai_message(self, message_id: str, conversation_id: str, role: str, content: str, metadata: Dict = None):
        """Save AI message."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ai_messages (id, conversation_id, role, content, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (message_id, conversation_id, role, content, json.dumps(metadata or {})))
            conn.commit()

    def get_ai_conversation_history(self, conversation_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get AI conversation history."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM ai_messages 
                WHERE conversation_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (conversation_id, limit))
            
            messages = []
            for row in cursor.fetchall():
                message = dict(row)
                message['metadata'] = json.loads(message['metadata']) if message['metadata'] else {}
                messages.append(message)
            return list(reversed(messages))  # Return in chronological order

    def save_ai_training_data(self, data_type: str, content: str, context: str = None, 
                             source_table: str = None, source_id: str = None, relevance_score: float = 0.5):
        """Save training data for AI models."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            training_id = f"training_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
            cursor.execute("""
                INSERT INTO ai_training_data (id, data_type, content, context, source_table, source_id, relevance_score)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (training_id, data_type, content, context, source_table, source_id, relevance_score))
            conn.commit()
            return training_id

    def get_ai_training_data(self, data_types: List[str] = None, limit: int = 1000) -> List[Dict[str, Any]]:
        """Get training data for AI models."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if data_types:
                placeholders = ','.join('?' * len(data_types))
                query = f"""
                    SELECT * FROM ai_training_data 
                    WHERE data_type IN ({placeholders})
                    ORDER BY created_at DESC 
                    LIMIT ?
                """
                cursor.execute(query, data_types + [limit])
            else:
                cursor.execute("""
                    SELECT * FROM ai_training_data 
                    ORDER BY created_at DESC 
                    LIMIT ?
                """, (limit,))
            
            return [dict(row) for row in cursor.fetchall()]

    def update_ai_training_from_feedback(self):
        """Update training data based on user feedback."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Get recent liked items for training
                cursor.execute("""
                    SELECT item_type, item_id, item_title, item_content, item_metadata, category
                    FROM user_feedback 
                    WHERE feedback_type = 'like' 
                    AND feedback_timestamp > datetime('now', '-30 days')
                """)
                
                liked_items = cursor.fetchall()
                for item in liked_items:
                    content = f"Title: {item['item_title']}\nContent: {item['item_content']}"
                    if item['item_metadata']:
                        try:
                            metadata = json.loads(item['item_metadata'])
                            content += f"\nMetadata: {json.dumps(metadata)}"
                        except:
                            content += f"\nMetadata: {item['item_metadata']}"
                    
                    self.save_ai_training_data(
                        data_type=f"liked_{item['item_type']}",
                        content=content,
                        context=f"User liked this {item['item_type']} content",
                        source_table="user_feedback",
                        source_id=item['item_id'],
                        relevance_score=0.8
                    )
                
                logger.info(f"Updated AI training data with {len(liked_items)} liked items")
                
        except Exception as e:
            logger.error(f"Error updating AI training from feedback: {e}")

    # News Sources Management
    def add_news_source(self, name: str, url: str, category: str = 'general', is_custom: bool = True) -> int:
        """Add a new news source."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO news_sources (name, url, category, is_custom)
                VALUES (?, ?, ?, ?)
            """, (name, url, category, 1 if is_custom else 0))
            conn.commit()
            return cursor.lastrowid

    def get_news_sources(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all news sources."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM news_sources"
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY user_preference DESC, name"
            
            cursor.execute(query)
            return [dict(row) for row in cursor.fetchall()]

    def update_news_source_preference(self, source_id: int, preference: int):
        """Update user preference for a news source (0-5 scale)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE news_sources 
                SET user_preference = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (preference, source_id))
            conn.commit()

    def toggle_news_source(self, source_id: int, active: bool):
        """Toggle news source active status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE news_sources 
                SET is_active = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (1 if active else 0, source_id))
            conn.commit()

    def update_news_source_stats(self, source_id: int, success: bool = True):
        """Update news source fetch statistics."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if success:
                cursor.execute("""
                    UPDATE news_sources 
                    SET fetch_count = fetch_count + 1, last_fetched = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (source_id,))
            else:
                cursor.execute("""
                    UPDATE news_sources 
                    SET error_count = error_count + 1, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (source_id,))
            conn.commit()

    # Investment Tracking
    def save_investment_data(self, symbol: str, name: str, inv_type: str, data: Dict[str, Any]):
        """Save investment data."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO investments 
                (symbol, name, type, exchange, current_price, previous_price, 
                 change_percent, market_cap, volume, last_updated, external_source, external_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                symbol, name, inv_type, 
                data.get('exchange'), data.get('current_price'), data.get('previous_price'),
                data.get('change_percent'), data.get('market_cap'), data.get('volume'),
                datetime.now(), data.get('source'), data.get('external_id')
            ))
            conn.commit()

    def get_tracked_investments(self) -> List[Dict[str, Any]]:
        """Get all tracked investments."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM investments WHERE is_tracked = 1 
                ORDER BY type, symbol
            """)
            return [dict(row) for row in cursor.fetchall()]

    def toggle_investment_tracking(self, investment_id: int, tracked: bool):
        """Toggle investment tracking."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE investments SET is_tracked = ? WHERE id = ?
            """, (1 if tracked else 0, investment_id))
            conn.commit()

    # Local Services Monitoring
    def save_local_service(self, service_name: str, port: int, ip_address: str = '127.0.0.1', 
                          service_type: str = 'web', endpoint_url: str = None):
        """Save or update local service information."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO local_services 
                (service_name, port, ip_address, service_type, endpoint_url, last_checked)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (service_name, port, ip_address, service_type, endpoint_url, datetime.now()))
            conn.commit()
            return cursor.lastrowid

    def update_service_status(self, service_id: int, status: str, response_time: float = None):
        """Update service status and response time."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE local_services 
                SET status = ?, response_time = ?, last_checked = ?
                WHERE id = ?
            """, (status, response_time, datetime.now(), service_id))
            conn.commit()

    def get_monitored_services(self) -> List[Dict[str, Any]]:
        """Get all monitored services."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM local_services WHERE is_monitored = 1 
                ORDER BY port
            """)
            return [dict(row) for row in cursor.fetchall()]

    # Network Device Discovery
    def save_network_device(self, ip_address: str, hostname: str = None, mac_address: str = None,
                           device_type: str = None, manufacturer: str = None, open_ports: List[int] = None,
                           services: List[str] = None, is_online: bool = True, response_time: float = None):
        """Save or update network device information."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO network_devices 
                (ip_address, hostname, mac_address, device_type, manufacturer, 
                 open_ports, services, last_seen, is_online, response_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ip_address, hostname, mac_address, device_type, manufacturer,
                json.dumps(open_ports or []), json.dumps(services or []),
                datetime.now(), 1 if is_online else 0, response_time
            ))
            conn.commit()
            return cursor.lastrowid

    def get_network_devices(self, online_only: bool = False) -> List[Dict[str, Any]]:
        """Get network devices."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM network_devices"
            if online_only:
                query += " WHERE is_online = 1"
            query += " ORDER BY ip_address"
            
            cursor.execute(query)
            devices = []
            for row in cursor.fetchall():
                device = dict(row)
                # Parse JSON fields
                try:
                    device['open_ports'] = json.loads(device['open_ports']) if device['open_ports'] else []
                    device['services'] = json.loads(device['services']) if device['services'] else []
                except:
                    device['open_ports'] = []
                    device['services'] = []
                devices.append(device)
            return devices

    def start_ai_model_training(self, provider_id: int, training_data_hash: str) -> str:
        """Start AI model training."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            training_id = f"training_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            cursor.execute("""
                INSERT INTO ai_model_training (id, provider_id, training_status, training_data_hash, training_started_at)
                VALUES (?, ?, 'started', ?, CURRENT_TIMESTAMP)
            """, (training_id, provider_id, training_data_hash))
            conn.commit()
            return training_id

    def update_ai_model_training_status(self, training_id: str, status: str, model_version: str = None, 
                                       performance_metrics: Dict = None, error_log: str = None):
        """Update AI model training status."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            update_fields = ["training_status = ?"]
            params = [status]
            
            if status == 'completed':
                update_fields.append("training_completed_at = CURRENT_TIMESTAMP")
            
            if model_version:
                update_fields.append("model_version = ?")
                params.append(model_version)
                
            if performance_metrics:
                update_fields.append("performance_metrics = ?")
                params.append(json.dumps(performance_metrics))
                
            if error_log:
                update_fields.append("error_log = ?")
                params.append(error_log)
            
            params.append(training_id)
            
            cursor.execute(f"""
                UPDATE ai_model_training 
                SET {', '.join(update_fields)}
                WHERE id = ?
            """, params)
            conn.commit()
    
    def save_dashboard_project(self, project_data: Dict[str, Any]) -> int:
        """Save or update a dashboard project configuration."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Debug logging
            logger.info(f"Saving dashboard - start_command: {project_data.get('start_command')}")
            logger.info(f"Saving dashboard - production_url: {project_data.get('production_url')}")
            logger.info(f"Saving dashboard - api_url: {project_data.get('api_url')}")
            
            cursor.execute("""
                INSERT INTO dashboard_projects 
                (name, path, type, port, start_command, url, github_pages_url, 
                 custom_domain, brand, description, health_endpoint, production_url, 
                 api_url, is_active, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(name) DO UPDATE SET
                    path = excluded.path,
                    type = excluded.type,
                    port = excluded.port,
                    start_command = excluded.start_command,
                    url = excluded.url,
                    github_pages_url = excluded.github_pages_url,
                    custom_domain = excluded.custom_domain,
                    brand = excluded.brand,
                    description = excluded.description,
                    health_endpoint = excluded.health_endpoint,
                    production_url = excluded.production_url,
                    api_url = excluded.api_url,
                    is_active = excluded.is_active,
                    updated_at = CURRENT_TIMESTAMP
            """, (
                project_data.get('name'),
                project_data.get('path', ''),
                project_data.get('type'),
                project_data.get('port'),
                project_data.get('start_command'),
                project_data.get('url'),
                project_data.get('github_pages_url'),
                project_data.get('custom_domain'),
                project_data.get('brand'),
                project_data.get('description'),
                project_data.get('health_endpoint'),
                project_data.get('production_url'),
                project_data.get('api_url'),
                project_data.get('is_active', 1) if isinstance(project_data.get('is_active'), int) else (1 if project_data.get('active', True) else 0)
            ))
            
            project_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            logger.info(f"Saved dashboard project: {project_data.get('name')}")
            return project_id
            
        except Exception as e:
            logger.error(f"Error saving dashboard project: {e}")
            raise
    
    def get_dashboard_projects(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Get all saved dashboard projects."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            query = "SELECT * FROM dashboard_projects"
            if active_only:
                query += " WHERE is_active = 1"
            query += " ORDER BY name"
            
            cursor.execute(query)
            rows = cursor.fetchall()
            conn.close()
            
            return [dict(row) for row in rows]
            
        except Exception as e:
            logger.error(f"Error getting dashboard projects: {e}")
            return []
    
    def update_dashboard_project(self, name: str, updates: Dict[str, Any]) -> bool:
        """Update specific fields of a dashboard project."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Build dynamic update query
            update_fields = []
            params = []
            
            allowed_fields = ['path', 'type', 'port', 'start_command', 'url', 
                            'github_pages_url', 'custom_domain', 'brand', 
                            'description', 'health_endpoint', 'production_url', 
                            'api_url', 'is_active']
            
            for field in allowed_fields:
                if field in updates:
                    update_fields.append(f"{field} = ?")
                    params.append(updates[field])
            
            if not update_fields:
                return False
            
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(name)
            
            cursor.execute(f"""
                UPDATE dashboard_projects 
                SET {', '.join(update_fields)}
                WHERE name = ?
            """, params)
            
            affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            if affected > 0:
                logger.info(f"Updated dashboard project: {name}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error updating dashboard project {name}: {e}")
            return False
    
    def delete_dashboard_project(self, name: str) -> bool:
        """Delete a dashboard project."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("DELETE FROM dashboard_projects WHERE name = ?", (name,))
            affected = cursor.rowcount
            conn.commit()
            conn.close()
            
            if affected > 0:
                logger.info(f"Deleted dashboard project: {name}")
                return True
            return False
            
        except Exception as e:
            logger.error(f"Error deleting dashboard project {name}: {e}")
            return False
    
    # User Profile Management
    def get_user_profile(self) -> Dict[str, Any]:
        """Get user profile for AI personalization."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT full_name, preferred_name, occupation, company, role, 
                       work_focus, interests, communication_style, timezone, 
                       work_hours, priorities, bio, updated_at,
                       github_username, soundcloud_url, bandcamp_url,
                       music_artist_name, music_label_name, book_title,
                       project_paths, vanity_search_terms
                FROM user_profile
                WHERE id = 1
            """)
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return {
                    'full_name': row[0],
                    'preferred_name': row[1],
                    'occupation': row[2],
                    'company': row[3],
                    'role': row[4],
                    'work_focus': row[5],
                    'interests': row[6],
                    'communication_style': row[7],
                    'timezone': row[8],
                    'work_hours': row[9],
                    'priorities': row[10],
                    'bio': row[11],
                    'updated_at': row[12],
                    'github_username': row[13] or '',
                    'soundcloud_url': row[14] or '',
                    'bandcamp_url': row[15] or '',
                    'music_artist_name': row[16] or '',
                    'music_label_name': row[17] or '',
                    'book_title': row[18] or '',
                    'project_paths': row[19] or '[]',
                    'vanity_search_terms': row[20] or '{}'
                }
            return {}
            
        except Exception as e:
            logger.error(f"Error getting user profile: {e}")
            return {}
    
    def save_user_profile(self, profile: Dict[str, Any]) -> bool:
        """Save or update user profile."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO user_profile (
                    id, full_name, preferred_name, occupation, company, role,
                    work_focus, interests, communication_style, timezone,
                    work_hours, priorities, bio, updated_at,
                    github_username, soundcloud_url, bandcamp_url,
                    music_artist_name, music_label_name, book_title,
                    project_paths, vanity_search_terms
                ) VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP,
                          ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                profile.get('full_name'),
                profile.get('preferred_name'),
                profile.get('occupation'),
                profile.get('company'),
                profile.get('role'),
                profile.get('work_focus'),
                profile.get('interests'),
                profile.get('communication_style'),
                profile.get('timezone'),
                profile.get('work_hours'),
                profile.get('priorities'),
                profile.get('bio'),
                profile.get('github_username'),
                profile.get('soundcloud_url'),
                profile.get('bandcamp_url'),
                profile.get('music_artist_name'),
                profile.get('music_label_name'),
                profile.get('book_title'),
                profile.get('project_paths'),
                profile.get('vanity_search_terms')
            ))
            
            conn.commit()
            conn.close()
            logger.info("User profile saved successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error saving user profile: {e}")
            return False
    
    def save_ai_message_feedback(self, message_id: str, conversation_id: str, 
                                  feedback_type: str, rating: int = None, 
                                  comment: str = None) -> bool:
        """Save feedback for an AI message."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                INSERT INTO ai_message_feedback (
                    message_id, conversation_id, feedback_type, rating, comment
                ) VALUES (?, ?, ?, ?, ?)
            """, (message_id, conversation_id, feedback_type, rating, comment))
            
            conn.commit()
            conn.close()
            logger.info(f"Saved feedback for message {message_id}: {feedback_type}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving message feedback: {e}")
            return False
    
    def get_conversation_feedback_stats(self, conversation_id: str) -> Dict[str, Any]:
        """Get feedback statistics for a conversation."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT feedback_type, COUNT(*), AVG(rating)
                FROM ai_message_feedback
                WHERE conversation_id = ?
                GROUP BY feedback_type
            """, (conversation_id,))
            
            stats = {}
            for row in cursor.fetchall():
                stats[row[0]] = {
                    'count': row[1],
                    'avg_rating': row[2] if row[2] else 0
                }
            
            conn.close()
            return stats
            
        except Exception as e:
            logger.error(f"Error getting feedback stats: {e}")
            return {}
    
    # Safe Email Senders Management
    def add_safe_sender(self, sender_email: str, reason: str = "User marked as safe") -> bool:
        """Add an email sender to the safe senders whitelist."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Extract domain from email
            import re
            domain_match = re.search(r'@([a-zA-Z0-9.-]+)', sender_email)
            sender_domain = domain_match.group(1).lower() if domain_match else ''
            
            cursor.execute("""
                INSERT INTO safe_email_senders (sender_email, sender_domain, added_reason, last_seen, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT(sender_email) DO UPDATE SET
                    marked_safe_count = marked_safe_count + 1,
                    last_seen = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
            """, (sender_email.lower(), sender_domain, reason))
            
            conn.commit()
            logger.info(f"Added safe sender: {sender_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error adding safe sender {sender_email}: {e}")
            return False
    
    def is_safe_sender(self, sender_email: str) -> bool:
        """Check if an email sender is in the safe senders whitelist."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id FROM safe_email_senders
                WHERE sender_email = ? COLLATE NOCASE
            """, (sender_email.lower(),))
            
            result = cursor.fetchone()
            return result is not None
            
        except Exception as e:
            logger.error(f"Error checking safe sender {sender_email}: {e}")
            return False
    
    def is_safe_domain(self, domain: str) -> bool:
        """Check if a domain has any safe senders."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id FROM safe_email_senders
                WHERE sender_domain = ? COLLATE NOCASE
                LIMIT 1
            """, (domain.lower(),))
            
            result = cursor.fetchone()
            return result is not None
            
        except Exception as e:
            logger.error(f"Error checking safe domain {domain}: {e}")
            return False
    
    def get_safe_senders(self) -> List[Dict[str, Any]]:
        """Get all safe senders."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT sender_email, sender_domain, added_reason, 
                       marked_safe_count, last_seen, created_at
                FROM safe_email_senders
                ORDER BY last_seen DESC
            """)
            
            safe_senders = []
            for row in cursor.fetchall():
                safe_senders.append({
                    'sender_email': row[0],
                    'sender_domain': row[1],
                    'added_reason': row[2],
                    'marked_safe_count': row[3],
                    'last_seen': row[4],
                    'created_at': row[5]
                })
            
            return safe_senders
            
        except Exception as e:
            logger.error(f"Error getting safe senders: {e}")
            return []
    
    def remove_safe_sender(self, sender_email: str) -> bool:
        """Remove an email sender from the safe senders whitelist."""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            cursor.execute("""
                DELETE FROM safe_email_senders
                WHERE sender_email = ? COLLATE NOCASE
            """, (sender_email.lower(),))
            
            conn.commit()
            logger.info(f"Removed safe sender: {sender_email}")
            return True
            
        except Exception as e:
            logger.error(f"Error removing safe sender {sender_email}: {e}")
            return False


# Global database instance
# Database instance will be created lazily
_db = None

def get_db() -> DatabaseManager:
    """Get the global database instance, creating it if needed."""
    global _db
    if _db is None:
        _db = DatabaseManager()
    return _db

# For backward compatibility, expose as 'db'
class DatabaseProxy:
    """Proxy that forwards all attribute access to the lazy-loaded database."""
    def __getattr__(self, name):
        return getattr(get_db(), name)

db = DatabaseProxy()


# Convenience functions  
def get_database_manager() -> DatabaseManager:
    """Get the global database instance."""
    return get_db()


def save_credentials(service_name: str, credentials: Dict[str, Any]):
    """Save credentials for a service."""
    return db.save_credentials(service_name, credentials)


def get_credentials(service_name: str) -> Optional[Dict[str, Any]]:
    """Get credentials for a service."""
    return db.get_credentials(service_name)


def save_auth_token(service_name: str, token_data: Dict[str, Any], expires_at: Optional[datetime] = None):
    """Save authentication token."""
    return db.save_auth_token(service_name, token_data, expires_at)


def get_auth_token(service_name: str) -> Optional[Dict[str, Any]]:
    """Get authentication token."""
    return db.get_auth_token(service_name)


def get_auth_status() -> Dict[str, bool]:
    """Get authentication status."""
    return db.get_auth_status()


def save_collected_data(service_name: str, data_type: str, data: List[Dict[str, Any]], collection_date: datetime = None):
    """Save collected data."""
    if collection_date is None:
        collection_date = datetime.now()
    return db.save_collected_data(service_name, data_type, data, collection_date)


def get_collected_data(service_name: str, data_type: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
    """Get collected data."""
    return db.get_collected_data(service_name, data_type, start_date, end_date)
