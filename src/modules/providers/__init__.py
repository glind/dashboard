"""
Provider management module for multi-provider authentication.
"""

from .endpoints import router
from .oauth import router as oauth_router

__all__ = ['router', 'oauth_router']
