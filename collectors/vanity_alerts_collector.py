"""
Vanity alerts collector for monitoring mentions of Buildly, Gregory Lind, music, and book.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import aiohttp
import json
import hashlib
from dataclasses import dataclass
from urllib.parse import quote_plus
import feedparser
import re
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class VanityAlert:
    """Container for vanity alert data."""
    id: str
    title: str
    content: str
    url: str
    source: str
    search_term: str
    timestamp: datetime
    confidence_score: float
    is_liked: Optional[bool] = None
    is_validated: Optional[bool] = None
    snippet: str = ""


class VanityAlertsCollector:
    """Collector for vanity alerts about Gregory Lind, Buildly, music, and book."""
    
    def __init__(self):
        """Initialize the vanity alerts collector."""
        self.search_terms = {
            'buildly': [
                '"Buildly"',
                '"Buildly Labs"',
                '"buildly.io"',
                'Buildly',
                'buildly.io'
            ],
            'gregory_lind': [
                '"Gregory Lind"',
                '"Greg Lind"',
                '"Gregory A Lind"',
                'Gregory Lind',
                'Greg Lind'
            ],
            'book': [
                '"Radical Therapy for Software Teams"',
                '"Radical Therapy" software',
                'Gregory Lind book',
                'Radical Therapy'
            ],
            'music': [
                '"Gregory Lind" music',
                '"Greg Lind" musician',
                '"Gregory Lind" composer',
                '"My Evil Robot Army"',
                '"Null Records"',
                '"nullrecords"',
                'My Evil Robot Army',
                'Null Records',
                'nullrecords',
                'Gregory Lind electronic'
            ]
        }
        
        # Search engines and news sources to monitor
        self.sources = {
            'google_news': 'https://news.google.com/rss/search',
            'bing_news': 'https://www.bing.com/news/search',
            'reddit': 'https://www.reddit.com/search.json',
            'hackernews': 'https://hn.algolia.com/api/v1/search',
            'github': 'https://api.github.com/search/repositories',
            'stackoverflow': 'https://api.stackexchange.com/2.3/search',
            'digg': 'https://digg.com/api/search'
        }
        
        # User agent for web scraping
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
    
    def _generate_alert_id(self, title: str, url: str, source: str) -> str:
        """Generate unique ID for an alert."""
        content = f"{title}{url}{source}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def _calculate_confidence_score(self, title: str, content: str, search_term: str) -> float:
        """Calculate confidence score for relevance."""
        score = 0.0
        
        # Ensure all inputs are strings
        title = title or ''
        content = content or ''
        search_term = search_term or ''
        
        # Check for exact matches in title (higher weight)
        if search_term.lower() in title.lower():
            score += 0.4
        
        # Check for exact matches in content
        if search_term.lower() in content.lower():
            score += 0.3
        
        # Check for related terms
        related_terms = {
            'buildly': ['software', 'development', 'platform', 'api', 'framework'],
            'gregory_lind': ['ceo', 'founder', 'developer', 'engineer', 'author'],
            'book': ['therapy', 'software', 'teams', 'radical', 'development'],
            'music': ['composer', 'musician', 'album', 'song', 'recording']
        }
        
        term_category = None
        for category, terms in self.search_terms.items():
            if any(term.lower().replace('"', '') in search_term.lower() for term in terms):
                term_category = category
                break
        
        if term_category and term_category in related_terms:
            for related_term in related_terms[term_category]:
                if related_term in content.lower():
                    score += 0.1
        
        return min(score, 1.0)
    
    async def search_google_news(self, search_term: str) -> List[VanityAlert]:
        """Search Google News RSS for mentions."""
        alerts = []
        try:
            query = quote_plus(search_term)
            url = f"{self.sources['google_news']}?q={query}&hl=en-US&gl=US&ceid=US:en"
            
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        feed = feedparser.parse(content)
                        
                        for entry in feed.entries[:10]:  # Limit to 10 results
                            alert = VanityAlert(
                                id=self._generate_alert_id(entry.title, entry.link, 'google_news'),
                                title=entry.title,
                                content=entry.get('summary', ''),
                                url=entry.link,
                                source='Google News',
                                search_term=search_term,
                                timestamp=datetime.now(),
                                confidence_score=self._calculate_confidence_score(
                                    entry.title, 
                                    entry.get('summary', ''), 
                                    search_term
                                ),
                                snippet=entry.get('summary', '')[:200] + '...' if len(entry.get('summary', '')) > 200 else entry.get('summary', '')
                            )
                            alerts.append(alert)
        except Exception as e:
            logger.error(f"Error searching Google News for '{search_term}': {e}")
        
        return alerts
    
    async def search_reddit(self, search_term: str) -> List[VanityAlert]:
        """Search Reddit for mentions."""
        alerts = []
        try:
            query = quote_plus(search_term)
            url = f"{self.sources['reddit']}?q={query}&sort=new&limit=10"
            
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for post in data.get('data', {}).get('children', []):
                            post_data = post.get('data', {})
                            
                            alert = VanityAlert(
                                id=self._generate_alert_id(post_data.get('title', ''), 
                                                         f"https://reddit.com{post_data.get('permalink', '')}", 
                                                         'reddit'),
                                title=post_data.get('title', ''),
                                content=post_data.get('selftext', ''),
                                url=f"https://reddit.com{post_data.get('permalink', '')}",
                                source=f"Reddit r/{post_data.get('subreddit', 'unknown')}",
                                search_term=search_term,
                                timestamp=datetime.fromtimestamp(post_data.get('created_utc', 0)),
                                confidence_score=self._calculate_confidence_score(
                                    post_data.get('title', ''), 
                                    post_data.get('selftext', ''), 
                                    search_term
                                ),
                                snippet=post_data.get('selftext', '')[:200] + '...' if len(post_data.get('selftext', '')) > 200 else post_data.get('selftext', '')
                            )
                            alerts.append(alert)
        except Exception as e:
            logger.error(f"Error searching Reddit for '{search_term}': {e}")
        
        return alerts
    
    async def search_hackernews(self, search_term: str) -> List[VanityAlert]:
        """Search Hacker News for mentions."""
        alerts = []
        try:
            query = quote_plus(search_term)
            url = f"{self.sources['hackernews']}?query={query}&tags=story&hitsPerPage=10"
            
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for hit in data.get('hits', []):
                            alert = VanityAlert(
                                id=self._generate_alert_id(hit.get('title', ''), 
                                                         hit.get('url', f"https://news.ycombinator.com/item?id={hit.get('objectID')}"), 
                                                         'hackernews'),
                                title=hit.get('title', ''),
                                content=hit.get('story_text', ''),
                                url=hit.get('url', f"https://news.ycombinator.com/item?id={hit.get('objectID')}"),
                                source='Hacker News',
                                search_term=search_term,
                                timestamp=datetime.fromtimestamp(hit.get('created_at_i', 0)),
                                confidence_score=self._calculate_confidence_score(
                                    hit.get('title', ''), 
                                    hit.get('story_text', ''), 
                                    search_term
                                ),
                                snippet=hit.get('story_text', '')[:200] + '...' if len(hit.get('story_text', '')) > 200 else hit.get('story_text', '')
                            )
                            alerts.append(alert)
        except Exception as e:
            logger.error(f"Error searching Hacker News for '{search_term}': {e}")
        
        return alerts
    
    async def search_github(self, search_term: str) -> List[VanityAlert]:
        """Search GitHub for mentions."""
        alerts = []
        try:
            query = quote_plus(search_term)
            url = f"{self.sources['github']}?q={query}&sort=updated&per_page=10"
            
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        for repo in data.get('items', []):
                            alert = VanityAlert(
                                id=self._generate_alert_id(repo.get('full_name', ''), 
                                                         repo.get('html_url', ''), 
                                                         'github'),
                                title=f"Repository: {repo.get('full_name', '')}",
                                content=repo.get('description', ''),
                                url=repo.get('html_url', ''),
                                source='GitHub',
                                search_term=search_term,
                                timestamp=datetime.fromisoformat(repo.get('updated_at', datetime.now().isoformat()).replace('Z', '+00:00')).replace(tzinfo=None) if repo.get('updated_at') else datetime.now(),
                                confidence_score=self._calculate_confidence_score(
                                    repo.get('full_name', ''), 
                                    repo.get('description', '') or '', 
                                    search_term
                                ),
                                snippet=(repo.get('description') or '')[:200] + '...' if len(repo.get('description') or '') > 200 else (repo.get('description') or '')
                            )
                            alerts.append(alert)
        except Exception as e:
            logger.error(f"Error searching GitHub for '{search_term}': {e}")
        
        return alerts
    
    async def search_digg(self, search_term: str) -> List[VanityAlert]:
        """Search Digg for mentions (using their RSS-like endpoints)."""
        alerts = []
        try:
            # Digg doesn't have a simple API, but we can search via URL patterns
            query = quote_plus(search_term)
            # Try to search Digg through their search URL
            url = f"https://digg.com/search?q={query}"
            
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url) as response:
                    if response.status == 200:
                        content = await response.text()
                        # Basic HTML parsing for Digg results
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(content, 'html.parser')
                        
                        # Look for article titles and links (simplified parsing)
                        articles = soup.find_all('a', href=True)[:5]  # Limit results
                        
                        for article in articles:
                            title = article.get_text(strip=True)
                            if title and len(title) > 10 and search_term.lower().replace('"', '') in title.lower():
                                alert = VanityAlert(
                                    id=self._generate_alert_id(title, article['href'], 'digg'),
                                    title=title,
                                    content='',
                                    url=article['href'] if article['href'].startswith('http') else f"https://digg.com{article['href']}",
                                    source='Digg',
                                    search_term=search_term,
                                    timestamp=datetime.now(),
                                    confidence_score=self._calculate_confidence_score(title, '', search_term),
                                    snippet=title[:200]
                                )
                                alerts.append(alert)
        except Exception as e:
            logger.error(f"Error searching Digg for '{search_term}': {e}")
        
        return alerts
    
    async def collect_all_alerts(self) -> List[VanityAlert]:
        """Collect all vanity alerts from all sources."""
        all_alerts = []
        
        for category, terms in self.search_terms.items():
            for term in terms:
                logger.info(f"Searching for '{term}' in category '{category}'")
                
                # Search all sources concurrently
                tasks = [
                    self.search_google_news(term),
                    self.search_reddit(term),
                    self.search_hackernews(term),
                    self.search_github(term),
                    self.search_digg(term)
                ]
                
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, list):
                        all_alerts.extend(result)
                    elif isinstance(result, Exception):
                        logger.error(f"Error in search task: {result}")
        
        # Remove duplicates based on ID
        seen_ids = set()
        unique_alerts = []
        for alert in all_alerts:
            if alert.id not in seen_ids:
                seen_ids.add(alert.id)
                unique_alerts.append(alert)
        
        # Sort by confidence score and timestamp
        unique_alerts.sort(key=lambda x: (x.confidence_score, x.timestamp), reverse=True)
        
        logger.info(f"Collected {len(unique_alerts)} unique vanity alerts")
        return unique_alerts

    async def collect_data(self) -> Dict[str, Any]:
        """Collect vanity alerts data for the dashboard."""
        try:
            logger.info("Collecting vanity alerts data...")
            
            # Collect all alerts
            alerts = await self.collect_all_alerts()
            
            # Save to database
            if alerts:
                self.save_alerts_to_database(alerts)
            
            # Return summary data
            result = {
                'total_alerts': len(alerts),
                'alerts': [
                    {
                        'id': alert.id,
                        'title': alert.title,
                        'url': alert.url,
                        'source': alert.source,
                        'search_term': alert.search_term,
                        'timestamp': alert.timestamp.isoformat(),
                        'confidence_score': alert.confidence_score,
                        'snippet': alert.snippet
                    }
                    for alert in alerts[:10]  # Return top 10 for display
                ],
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Collected {len(alerts)} vanity alerts")
            return result
            
        except Exception as e:
            logger.error(f"Error collecting vanity alerts data: {e}")
            return {
                'total_alerts': 0,
                'alerts': [],
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def save_alerts_to_database(self, alerts: List[VanityAlert]):
        """Save alerts to database for persistence and liking functionality."""
        import sqlite3
        
        try:
            # Connect directly to database
            conn = sqlite3.connect('dashboard.db')
            cursor = conn.cursor()
            
            # Create table if it doesn't exist
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS vanity_alerts (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT,
                    url TEXT NOT NULL,
                    source TEXT NOT NULL,
                    search_term TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    confidence_score REAL NOT NULL,
                    is_liked INTEGER DEFAULT NULL,
                    is_validated INTEGER DEFAULT NULL,
                    snippet TEXT
                )
            ''')
            
            # Insert or update alerts
            for alert in alerts:
                cursor.execute('''
                INSERT OR REPLACE INTO vanity_alerts 
                (id, title, content, url, source, search_term, timestamp, confidence_score, snippet)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                alert.id,
                alert.title,
                alert.content or '',
                alert.url,
                alert.source,
                alert.search_term,
                alert.timestamp.isoformat(),
                alert.confidence_score,
                alert.snippet or ''
            ))
        
            conn.commit()
            conn.close()
            logger.info(f"Saved {len(alerts)} alerts to database")
            
        except Exception as e:
            logger.error(f"Error saving alerts to database: {e}")
    
    def load_alerts_from_database(self, days_back: int = 7) -> List[VanityAlert]:
        """Load alerts from database."""
        from database import get_db
        
        alerts = []
        try:
            db = get_db()
            with db.get_connection() as conn:
                cursor = conn.cursor()
                
                # Load alerts from last N days
                cutoff_date = (datetime.now() - timedelta(days=days_back)).isoformat()
                
                cursor.execute('''
                    SELECT id, title, content, url, source, search_term, timestamp, 
                           confidence_score, is_liked, is_validated, snippet
                    FROM vanity_alerts 
                    WHERE timestamp > ? 
                    ORDER BY confidence_score DESC, timestamp DESC
                ''', (cutoff_date,))
                
                for row in cursor.fetchall():
                    alert = VanityAlert(
                        id=row[0],
                        title=row[1],
                        content=row[2] or '',
                        url=row[3],
                        source=row[4],
                        search_term=row[5],
                        timestamp=datetime.fromisoformat(row[6]).replace(tzinfo=None) if '+' in row[6] or 'Z' in row[6] else datetime.fromisoformat(row[6]),
                        confidence_score=row[7],
                        is_liked=row[8] if row[8] is not None else None,
                        is_validated=row[9] if row[9] is not None else None,
                        snippet=row[10] or ''
                    )
                    alerts.append(alert)
            
            logger.info(f"Loaded {len(alerts)} alerts from database")
            
        except Exception as e:
            logger.error(f"Error loading alerts from database: {e}")
        
        return alerts
    
    def update_alert_like_status(self, alert_id: str, is_liked: bool):
        """Update the like status of an alert."""
        import sqlite3
        
        try:
            conn = sqlite3.connect('dashboard.db')
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE vanity_alerts 
                SET is_liked = ? 
                WHERE id = ?
            ''', (1 if is_liked else 0, alert_id))
            
            conn.commit()
            conn.close()
            logger.info(f"Updated like status for alert {alert_id}: {is_liked}")
            
        except Exception as e:
            logger.error(f"Error updating alert like status: {e}")


async def main():
    """Test the vanity alerts collector."""
    collector = VanityAlertsCollector()
    alerts = await collector.collect_all_alerts()
    
    print(f"\nCollected {len(alerts)} vanity alerts:")
    for i, alert in enumerate(alerts[:5]):  # Show top 5
        print(f"\n{i+1}. {alert.title}")
        print(f"   Source: {alert.source}")
        print(f"   Confidence: {alert.confidence_score:.2f}")
        print(f"   URL: {alert.url}")
        print(f"   Snippet: {alert.snippet}")
    
    # Save to database
    collector.save_alerts_to_database(alerts)


if __name__ == "__main__":
    asyncio.run(main())
