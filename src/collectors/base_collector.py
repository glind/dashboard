"""
Base collector class for personal dashboard collectors.
"""

from typing import Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass

@dataclass
class CollectionResult:
    """Result from a data collection operation."""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: Optional[datetime] = None

class BaseCollector:
    """Base class for all data collectors."""
    
    def __init__(self, settings=None):
        self.settings = settings
    
    async def collect_data(self) -> CollectionResult:
        """Override this method in subclasses."""
        raise NotImplementedError("Subclasses must implement collect_data()")
    
    def get_fallback_data(self) -> Dict[str, Any]:
        """Override this method to provide fallback data."""
        return {}
