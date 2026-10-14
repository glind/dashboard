"""
Music News Module - Collector
Aggregates music industry news from multiple sources.
"""

import aiohttp
import feedparser
import logging
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

# Import existing music collector functionality
try:
    from collectors.music_collector import MusicCollector
    MUSIC_COLLECTOR_AVAILABLE = True
except ImportError:
    MUSIC_COLLECTOR_AVAILABLE = False
    logger.warning("Music collector not available")


async def collect_music_news(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Collect music industry news from configured sources.
    
    Args:
        config: Configuration dict with RSS feeds, API keys, etc.
        
    Returns:
        Dict with collected news articles and metadata
    """
    if not MUSIC_COLLECTOR_AVAILABLE:
        return {
            'success': False,
            'error': 'Music collector not available',
            'music_news': []
        }
    
    try:
        # Use existing music collector
        collector = MusicCollector(None)  # Database not needed for news collection
        
        # Collect music news
        music_news = await collector._collect_music_news()
        
        return {
            'success': True,
            'music_news': [
                {
                    'title': news.title,
                    'url': news.url,
                    'snippet': news.snippet,
                    'source': news.source,
                    'published_date': news.published_date.isoformat() if isinstance(news.published_date, datetime) else news.published_date,
                    'relevance_score': news.relevance_score,
                    'tags': news.tags or []
                }
                for news in music_news
            ],
            'count': len(music_news),
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Error collecting music news: {e}")
        return {
            'success': False,
            'error': str(e),
            'music_news': [],
            'timestamp': datetime.now().isoformat()
        }
