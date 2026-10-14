"""
Communications Module
Aggregates messages from LinkedIn, Slack, and Discord with AI-powered prioritization
"""

from .collector import CommsCollector
from .processor import CommsProcessor
from .endpoints import router

__all__ = ['CommsCollector', 'CommsProcessor', 'router']
