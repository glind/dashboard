"""
Application settings and configuration management.
"""

import os
from pathlib import Path
from typing import Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import Field
import yaml


class OllamaSettings(BaseSettings):
    """Ollama server configuration."""
    host: str = Field(default="pop-os.local", description="Ollama server host")
    port: int = Field(default=11434, description="Ollama server port")
    model: str = Field(default="llama3.2:1b", description="Default model to use")
    
    @property
    def base_url(self) -> str:
        return f"http://{self.host}:{self.port}"


class GoogleSettings(BaseSettings):
    """Google APIs configuration."""
    credentials_file: Optional[str] = Field(default=None, description="Path to Google credentials JSON")
    scopes: list = Field(default_factory=lambda: [
        'https://www.googleapis.com/auth/gmail.readonly',
        'https://www.googleapis.com/auth/calendar.readonly'
    ])


class AppleSettings(BaseSettings):
    """Apple APIs configuration."""
    # Apple doesn't have a public API for Reminders, we'll use alternative approaches
    reminders_export_path: Optional[str] = Field(default=None, description="Path to exported reminders")


class TodoistSettings(BaseSettings):
    """Todoist API configuration."""
    api_token: Optional[str] = Field(default=None, description="Todoist API token")
    
    class Config:
        env_prefix = "TODOIST_"


class TickTickSettings(BaseSettings):
    """TickTick API configuration."""
    client_id: Optional[str] = Field(default="LWv12xUi59IkcCP5Gx", description="TickTick client ID")
    client_secret: Optional[str] = Field(default="A%8ImK5zniXiA92@q)#mY_&8RqgF70^2", description="TickTick client secret")
    redirect_uri: Optional[str] = Field(default="http://localhost:8008/auth/ticktick/callback", description="OAuth redirect URI")
    
    class Config:
        env_prefix = "TICKTICK_"


class GitHubSettings(BaseSettings):
    """GitHub API configuration."""
    token: Optional[str] = Field(default=None, description="GitHub personal access token")
    username: Optional[str] = Field(default=None, description="GitHub username")
    
    class Config:
        env_prefix = "GITHUB_"


class BuildlySettings(BaseSettings):
    """Buildly Labs API configuration."""
    base_url: Optional[str] = Field(default=None, description="Buildly Labs API base URL")
    api_key: Optional[str] = Field(default=None, description="Buildly Labs API key")
    
    class Config:
        env_prefix = "BUILDLY_"


class WeatherSettings(BaseSettings):
    """Weather API configuration."""
    api_key: Optional[str] = Field(default=None, description="OpenWeatherMap API key")
    location: str = Field(default="Oregon City, OR", description="Default weather location")
    lat: float = Field(default=45.3573, description="Latitude for weather location")
    lon: float = Field(default=-122.6068, description="Longitude for weather location")
    units: str = Field(default="imperial", description="Temperature units (imperial/metric)")
    
    class Config:
        env_prefix = "WEATHER_"


class DashboardSettings(BaseSettings):
    """Dashboard configuration."""
    output_dir: str = Field(default="output", description="Dashboard output directory")
    template_dir: str = Field(default="templates", description="Dashboard templates directory")
    static_dir: str = Field(default="static", description="Static files directory")
    
    # KPI Configuration
    weekly_goals: Dict[str, Any] = Field(default_factory=lambda: {
        "emails_processed": 100,
        "meetings_attended": 10,
        "tasks_completed": 20,
        "github_commits": 15
    })
    
    monthly_goals: Dict[str, Any] = Field(default_factory=lambda: {
        "emails_processed": 400,
        "meetings_attended": 40,
        "tasks_completed": 80,
        "github_commits": 60
    })


class Settings(BaseSettings):
    """Main application settings."""
    # Environment
    environment: str = Field(default="development", description="Application environment")
    debug: bool = Field(default=True, description="Enable debug mode")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    
    # Data collection
    data_retention_days: int = Field(default=90, description="Days to retain collected data")
    collection_interval_hours: int = Field(default=6, description="Hours between data collection")
    
    # Component settings
    ollama: OllamaSettings = Field(default_factory=OllamaSettings)
    google: GoogleSettings = Field(default_factory=GoogleSettings)
    apple: AppleSettings = Field(default_factory=AppleSettings)
    todoist: TodoistSettings = Field(default_factory=TodoistSettings)
    ticktick: TickTickSettings = Field(default_factory=TickTickSettings)
    github: GitHubSettings = Field(default_factory=GitHubSettings)
    buildly: BuildlySettings = Field(default_factory=BuildlySettings)
    weather: WeatherSettings = Field(default_factory=WeatherSettings)
    dashboard: DashboardSettings = Field(default_factory=DashboardSettings)
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "allow"
    
    @classmethod
    def from_yaml(cls, config_path: str) -> "Settings":
        """Load settings from YAML file."""
        config_file = Path(config_path)
        if config_file.exists():
            with open(config_file, 'r') as f:
                config_data = yaml.safe_load(f)
            return cls(**config_data)
        return cls()
    
    def to_yaml(self, config_path: str) -> None:
        """Save settings to YAML file."""
        config_file = Path(config_path)
        config_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_file, 'w') as f:
            yaml.dump(self.dict(), f, default_flow_style=False, indent=2)


# Global settings instance
settings = Settings()
