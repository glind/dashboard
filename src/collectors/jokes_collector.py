"""
Jokes Collector - Fetches dad jokes and manages user preferences.
"""

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, List
import json

from .base_collector import BaseCollector, CollectionResult

logger = logging.getLogger(__name__)


class JokesCollector(BaseCollector):
    """Collector for dad jokes with user preference tracking."""
    
    def __init__(self, settings=None):
        """Initialize jokes collector."""
        super().__init__(settings)
        self.api_url = "https://icanhazdadjoke.com/"
        
    async def collect_data(self, start_date: datetime, end_date: datetime) -> CollectionResult:
        """
        Collect jokes data.
        For jokes, we don't use date range but fetch current jokes.
        """
        try:
            jokes = await self._fetch_jokes(count=5)  # Fetch 5 jokes at once
            
            return CollectionResult(
                source="jokes",
                data=jokes,
                metadata={
                    'count': len(jokes),
                    'api_source': 'icanhazdadjoke.com'
                },
                timestamp=datetime.now()
            )
            
        except Exception as e:
            self.logger.error(f"Error collecting jokes: {e}")
            return CollectionResult(
                source="jokes",
                data=[],
                metadata={},
                timestamp=datetime.now(),
                error=str(e),
                success=False
            )
    
    async def _fetch_jokes(self, count: int = 1) -> List[Dict[str, Any]]:
        """Fetch multiple jokes from the API."""
        jokes = []
        
        for _ in range(count):
            try:
                # Apply rate limiting
                await self._rate_limit()
                
                # Fetch joke
                headers = {"Accept": "application/json"}
                joke_data = await self._fetch_json(self.api_url, headers=headers)
                
                joke = {
                    'id': joke_data.get('id', f'unknown_{datetime.now().timestamp()}'),
                    'text': joke_data.get('joke', ''),
                    'source': 'icanhazdadjoke.com',
                    'fetched_at': datetime.now().isoformat(),
                    'is_liked': False  # Default value
                }
                
                jokes.append(joke)
                
            except Exception as e:
                self.logger.warning(f"Error fetching individual joke: {e}")
                # Add fallback joke
                jokes.append({
                    'id': f'fallback_{datetime.now().timestamp()}',
                    'text': "Why don't scientists trust atoms? Because they make up everything! 😄",
                    'source': 'fallback',
                    'fetched_at': datetime.now().isoformat(),
                    'is_liked': False
                })
        
        return jokes
    
    async def _fetch_single_joke(self) -> Dict[str, Any]:
        """Fetch a single fresh joke from the API."""
        try:
            jokes = await self._fetch_jokes(count=1)
            if jokes:
                return jokes[0]
            else:
                # Return fallback joke
                return {
                    'id': f'fallback_{datetime.now().timestamp()}',
                    'text': "Why don't scientists trust atoms? Because they make up everything! 😄",
                    'source': 'fallback',
                    'fetched_at': datetime.now().isoformat(),
                    'is_liked': False
                }
        except Exception as e:
            self.logger.error(f"Error fetching single joke: {e}")
            # Return fallback joke
            return {
                'id': f'fallback_{datetime.now().timestamp()}',
                'text': "Why don't scientists trust atoms? Because they make up everything! 😄",
                'source': 'fallback',
                'fetched_at': datetime.now().isoformat(),
                'is_liked': False
            }
    
    async def get_random_joke(self) -> Dict[str, Any]:
        """Get a single random joke."""
        cache_key = self._cache_key("random_joke")
        
        # Check cache first
        cached_joke = await self._get_cached(cache_key)
        if cached_joke:
            return cached_joke
        
        # Fetch new joke
        jokes = await self._fetch_jokes(count=1)
        if jokes:
            joke = jokes[0]
            # Check if liked in database
            joke['is_liked'] = await self._check_joke_liked(joke['id'])
            
            # Cache for short time
            self._set_cache(cache_key, joke)
            return joke
        
        # Fallback
        return {
            'id': 'fallback',
            'text': "Why don't scientists trust atoms? Because they make up everything! 😄",
            'source': 'fallback',
            'fetched_at': datetime.now().isoformat(),
            'is_liked': False
        }
    
    async def _check_joke_liked(self, joke_id: str) -> bool:
        """Check if a joke is liked in the database."""
        try:
            from database import get_db
            
            db = get_db()
            cursor = db.cursor()
            cursor.execute("SELECT is_liked FROM jokes WHERE joke_id = ?", (joke_id,))
            result = cursor.fetchone()
            cursor.close()
            
            return result[0] if result else False
            
        except Exception as e:
            self.logger.debug(f"Error checking joke like status: {e}")
            return False
    
    async def like_joke(self, joke_id: str, is_liked: bool) -> Dict[str, Any]:
        """Update joke like status."""
        try:
            from database import get_db
            
            db = get_db()
            cursor = db.cursor()
            
            cursor.execute("""
                INSERT OR REPLACE INTO jokes (joke_id, is_liked, liked_at, fetched_at) 
                VALUES (?, ?, ?, ?)
            """, (
                joke_id, 
                is_liked, 
                datetime.now().isoformat() if is_liked else None,
                datetime.now().isoformat()
            ))
            
            db.commit()
            cursor.close()
            
            return {
                'success': True,
                'joke_id': joke_id,
                'is_liked': is_liked
            }
            
        except Exception as e:
            self.logger.error(f"Error updating joke like status: {e}")
            return {
                'success': False,
                'error': str(e)
            }
    
    async def get_liked_jokes(self) -> List[Dict[str, Any]]:
        """Get all liked jokes."""
        try:
            from database import get_db
            
            db = get_db()
            cursor = db.cursor()
            cursor.execute("""
                SELECT joke_id, liked_at, fetched_at 
                FROM jokes 
                WHERE is_liked = 1 
                ORDER BY liked_at DESC
            """)
            results = cursor.fetchall()
            cursor.close()
            
            return [
                {
                    'id': row[0],
                    'liked_at': row[1],
                    'fetched_at': row[2]
                }
                for row in results
            ]
            
        except Exception as e:
            self.logger.error(f"Error getting liked jokes: {e}")
            return []
    
    def get_data_schema(self) -> Dict[str, Any]:
        """Return the database schema for jokes."""
        return {
            'joke_id': 'TEXT PRIMARY KEY',
            'text': 'TEXT',
            'source': 'TEXT',
            'is_liked': 'BOOLEAN DEFAULT FALSE',
            'liked_at': 'TEXT',
            'fetched_at': 'TEXT DEFAULT CURRENT_TIMESTAMP'
        }
    
    async def health_check(self) -> Dict[str, Any]:
        """Health check for jokes API."""
        try:
            # Try to fetch a joke
            await self.get_random_joke()
            
            return {
                'collector': 'JokesCollector',
                'status': 'healthy',
                'api_url': self.api_url,
                'last_check': datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                'collector': 'JokesCollector',
                'status': 'unhealthy',
                'error': str(e),
                'api_url': self.api_url,
                'last_check': datetime.now().isoformat()
            }