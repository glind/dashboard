"""
Vanity Alerts Module - Collector
Monitors mentions across web, social media, and news sources.
"""

import logging
from typing import Dict, Any, List
from datetime import datetime

logger = logging.getLogger(__name__)


async def collect_vanity_alerts(config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Collect vanity alert mentions from various sources.
    
    Args:
        config: Configuration dict with search terms, sources, etc.
        
    Returns:
        Dict with collected mentions and metadata
    """
    try:
        from database import get_database
        
        db = get_database()
        
        # Get vanity alerts from database
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT id, title, search_term, snippet, source, url, timestamp, is_liked, sentiment
                FROM vanity_alerts
                WHERE timestamp >= datetime('now', '-7 days')
                ORDER BY timestamp DESC
                LIMIT 100
            """)
            
            alerts = []
            for row in cursor.fetchall():
                alerts.append({
                    'id': row['id'],
                    'title': row['title'],
                    'search_term': row['search_term'],
                    'snippet': row['snippet'],
                    'source': row['source'],
                    'url': row['url'],
                    'timestamp': row['timestamp'],
                    'is_liked': bool(row['is_liked']),
                    'sentiment': row['sentiment']
                })
        
        return {
            'success': True,
            'alerts': alerts,
            'count': len(alerts),
            'timestamp': datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error collecting vanity alerts: {e}")
        return {
            'success': False,
            'error': str(e),
            'alerts': [],
            'timestamp': datetime.now().isoformat()
        }


async def search_new_mentions(search_terms: List[str], config: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Search for new mentions across configured sources.
    
    Args:
        search_terms: List of terms to search for
        config: Configuration for search sources
        
    Returns:
        Dict with new mentions found
    """
    # TODO: Implement real-time search across Google News, Twitter API, etc.
    # For now, return existing alerts from database
    return await collect_vanity_alerts(config)
