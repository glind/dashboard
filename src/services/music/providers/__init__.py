"""Music provider abstraction layer."""

from .base import BaseMusicProvider
from .youtube import YouTubeProvider

__all__ = ['BaseMusicProvider', 'YouTubeProvider']
