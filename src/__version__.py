"""
Personal Dashboard Version Information
"""

__version__ = "0.5.0"
__version_info__ = (0, 5, 0)
__release_name__ = "Multi-Provider Edition"
__release_date__ = "2025-12-15"

# Version history
VERSION_HISTORY = {
    "0.5.0": {
        "date": "2025-12-15",
        "name": "Multi-Provider Edition",
        "highlights": [
            "Multi-provider authentication system (Google, Microsoft, Proton)",
            "User-facing OAuth flows for email/calendar/notes",
            "Provider management UI with add/remove/test functionality",
            "Multi-account support per provider",
            "Trust layer with on-demand email scanning",
            "Unified data collection across all providers"
        ]
    },
    "0.4.0": {
        "date": "2025-11-XX",
        "name": "Task Intelligence Edition",
        "highlights": [
            "Task suggestions system",
            "AI-powered task approval workflow",
            "Personalized AI analysis"
        ]
    }
}

def get_version() -> str:
    """Get the current version string."""
    return __version__

def get_version_info() -> dict:
    """Get detailed version information."""
    return {
        "version": __version__,
        "version_info": __version_info__,
        "release_name": __release_name__,
        "release_date": __release_date__
    }
