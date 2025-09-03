"""
News Collector for Personal Dashboard

Collects news articles about Oregon State University, Portland Timbers, 
Star Wars, and Star Trek from multiple sources.
"""

import asyncio
import aiohttp
import feedparser
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import json
import os
from urllib.parse import urlencode
import re
from dataclasses import dataclass
import sqlite3

logger = logging.getLogger(__name__)

@dataclass
class NewsArticle:
    """Represents a news article."""
    title: str
    url: str
    snippet: str
    source: str
    published_date: datetime
    topics: List[str]
    relevance_score: float = 0.0
    user_feedback: Optional[str] = None  # 'positive', 'negative', None

class NewsCollector:
    """Collects news from multiple sources and learns from user feedback."""
    
    def __init__(self):
        self.topics = {
            'oregon_state': [
                'Oregon State University', 'OSU Beavers', 'Corvallis', 'OSU', 'Oregon State',
                'Beavers football', 'Beavers basketball', 'OSU athletics', 'Pac-12 Oregon State',
                'Oregon State research', 'OSU campus', 'Reser Stadium', 'Gill Coliseum'
            ],
            'portland_timbers': [
                'Portland Timbers', 'Timbers', 'MLS Portland', 'Providence Park', 'PTFC',
                'Timbers Army', 'Rose City', 'MLS Cup', 'Western Conference', 'Cascadia Cup',
                'Portland soccer', 'Timbers FC', 'Major League Soccer Portland'
            ],
            'star_wars': [
                'Star Wars', 'Lucasfilm', 'Disney Star Wars', 'Mandalorian', 'Jedi', 'Sith',
                'Luke Skywalker', 'Darth Vader', 'Empire', 'Rebellion', 'Force', 'lightsaber',
                'Millennium Falcon', 'Death Star', 'Tatooine', 'Coruscant', 'Yoda', 'Obi-Wan',
                'Princess Leia', 'Han Solo', 'Chewbacca', 'R2-D2', 'C-3PO', 'Baby Yoda', 'Grogu',
                'Ahsoka', 'Boba Fett', 'Clone Wars', 'Rebels', 'Bad Batch', 'Andor', 'Book of Boba Fett'
            ],
            'star_trek': [
                'Star Trek', 'Paramount', 'Enterprise', 'Federation', 'Starfleet', 'USS Enterprise',
                'Kirk', 'Spock', 'McCoy', 'Picard', 'Data', 'Worf', 'Riker', 'Janeway', 'Sisko',
                'Vulcan', 'Klingon', 'Romulan', 'Borg', 'Deep Space Nine', 'Voyager', 'Discovery',
                'Next Generation', 'TNG', 'TOS', 'DS9', 'VOY', 'Lower Decks', 'Prodigy', 'Strange New Worlds',
                'United Federation of Planets', 'warp drive', 'transporter', 'phaser', 'tricorder'
            ]
        }
        
        # RSS feeds for each topic
        self.rss_feeds = {
            'oregon_state': [
                'https://today.oregonstate.edu/rss.xml',
                'https://feeds.feedburner.com/OregonStateBeavers',
                'https://www.gazettetimes.com/search/?f=rss&t=article&c=news&l=25&s=start_time&sd=desc&q=Oregon+State+University',
                'https://www.oregonlive.com/oregon-state-beavers/index.ssf/rss.xml',
                'https://www.espn.com/espn/rss/college-football/team/_/id/204',  # OSU ESPN
                'https://247sports.com/college/oregon-state/rss/',
                'https://www.oregonstate.edu/main/rss.xml'
            ],
            'portland_timbers': [
                'https://www.mlssoccer.com/feeds/442.rss',
                'https://www.oregonlive.com/timbers/index.ssf/rss.xml',
                'https://feeds.feedburner.com/StumpTownFooty',
                'https://www.espn.com/espn/rss/soccer/team/_/id/19693',  # Timbers ESPN
                'https://www.sounderatheart.com/rss/current',  # Rival coverage
                'https://mlsmultiplex.com/rss',
                'https://www.dirtysouthsoccer.com/rss/current'
            ],
            'star_wars': [
                'https://www.starwars.com/news/feed',
                'https://feeds.feedburner.com/starwarscom',
                'https://www.hollywoodreporter.com/topic/star-wars/feed/',
                'https://io9.gizmodo.com/rss',
                'https://www.denofgeek.com/movies/star-wars/feed/',
                'https://www.slashfilm.com/category/movie/star-wars/feed/',
                'https://www.space.com/searchresults?q=star+wars&t=article&o=date&rss=1',
                'https://wegotthiscovered.com/category/movies/star-wars/feed/',
                'https://comicbook.com/category/star-wars/exclusive.rss'
            ],
            'star_trek': [
                'https://feeds.feedburner.com/startrek-com-news',
                'https://treknews.net/feed/',
                'https://www.hollywoodreporter.com/topic/star-trek/feed/',
                'https://io9.gizmodo.com/rss',
                'https://www.denofgeek.com/tv/star-trek/feed/',
                'https://www.space.com/searchresults?q=star+trek&t=article&o=date&rss=1',
                'https://comicbook.com/category/star-trek/exclusive.rss',
                'https://www.slashfilm.com/category/tv/star-trek/feed/',
                'https://wegotthiscovered.com/category/tv/star-trek/feed/'
            ]
        }
        
        # News API sources (if API key available)
        self.news_api_key = os.getenv('NEWS_API_KEY')
        self.news_api_sources = [
            'espn', 'entertainment-weekly', 'ign', 'the-verge',
            'techcrunch', 'cnn', 'bbc-news', 'associated-press'
        ]
        
        # Reddit sources for additional news
        self.reddit_subreddits = {
            'oregon_state': ['OregonStateUniv', 'CFB', 'CollegeBasketball', 'Corvallis'],
            'portland_timbers': ['timbers', 'MLS', 'soccer', 'PTFC'],
            'star_wars': ['StarWars', 'starwarsspeculation', 'TheMandalorianTV', 'PrequelMemes'],
            'star_trek': ['startrek', 'DeepSpaceNine', 'nextgeneration', 'voyager', 'discovery']
        }
        
        # Additional general news sources
        self.general_rss_feeds = [
            'https://feeds.reuters.com/reuters/topNews',
            'https://feeds.bbci.co.uk/news/rss.xml',
            'https://rss.cnn.com/rss/edition.rss',
            'https://feeds.npr.org/1001/rss.xml',
            'https://feeds.washingtonpost.com/rss/world',
            'https://www.espn.com/espn/rss/news',
            'https://www.ign.com/articles?format=rss',
            'https://www.theverge.com/rss/index.xml'
        ]
        
    async def collect_all_news(self) -> List[NewsArticle]:
        """Collect news from all sources and topics."""
        all_articles = []
        
        # Collect from RSS feeds
        for topic, feeds in self.rss_feeds.items():
            topic_articles = await self._collect_rss_articles(topic, feeds)
            all_articles.extend(topic_articles)
        
        # Collect from general news sources and filter by relevance
        general_articles = await self._collect_general_news()
        all_articles.extend(general_articles)
        
        # Collect from Reddit if available
        reddit_articles = await self._collect_reddit_news()
        all_articles.extend(reddit_articles)
        
        # Collect from News API if available
        if self.news_api_key:
            api_articles = await self._collect_news_api_articles()
            all_articles.extend(api_articles)
        
        # Remove duplicates and sort by relevance and date
        unique_articles = self._deduplicate_articles(all_articles)
        scored_articles = self._score_relevance(unique_articles)
        
        # Sort by relevance score and date
        scored_articles.sort(key=lambda x: (x.relevance_score, x.published_date), reverse=True)
        
        return scored_articles[:50]  # Return top 50 articles
    
    async def _collect_rss_articles(self, topic: str, feeds: List[str]) -> List[NewsArticle]:
        """Collect articles from RSS feeds for a specific topic."""
        articles = []
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for feed_url in feeds:
                tasks.append(self._fetch_rss_feed(session, feed_url, topic))
            
            feed_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in feed_results:
                if isinstance(result, list):
                    articles.extend(result)
                elif isinstance(result, Exception):
                    logger.warning(f"RSS feed error: {result}")
        
        return articles
    
    async def _fetch_rss_feed(self, session: aiohttp.ClientSession, feed_url: str, topic: str) -> List[NewsArticle]:
        """Fetch and parse a single RSS feed."""
        articles = []
        
        try:
            async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Parse RSS feed
                    feed = feedparser.parse(content)
                    
                    for entry in feed.entries:
                        # Extract article info
                        title = entry.get('title', '').strip()
                        url = entry.get('link', '').strip()
                        
                        # Get description/summary
                        snippet = ''
                        if hasattr(entry, 'summary'):
                            snippet = self._clean_html(entry.summary)
                        elif hasattr(entry, 'description'):
                            snippet = self._clean_html(entry.description)
                        
                        # Parse date
                        published_date = datetime.now()
                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                            try:
                                published_date = datetime(*entry.published_parsed[:6])
                            except:
                                pass
                        
                        # Determine relevant topics
                        article_topics = self._identify_topics(title + ' ' + snippet)
                        
                        if title and url and article_topics:
                            article = NewsArticle(
                                title=title,
                                url=url,
                                snippet=snippet[:300] + '...' if len(snippet) > 300 else snippet,
                                source=self._extract_domain(feed_url),
                                published_date=published_date,
                                topics=article_topics
                            )
                            articles.append(article)
                            
        except Exception as e:
            logger.debug(f"Error fetching RSS feed {feed_url}: {e}")
        
        return articles
    
    async def _collect_news_api_articles(self) -> List[NewsArticle]:
        """Collect articles from News API."""
        articles = []
        
        if not self.news_api_key:
            return articles
        
        async with aiohttp.ClientSession() as session:
            # Search for each topic
            for topic, keywords in self.topics.items():
                for keyword in keywords[:2]:  # Limit to avoid API quota
                    try:
                        # Build News API URL
                        params = {
                            'q': keyword,
                            'apiKey': self.news_api_key,
                            'language': 'en',
                            'sortBy': 'publishedAt',
                            'pageSize': 10,
                            'from': (datetime.now() - timedelta(days=7)).isoformat()
                        }
                        
                        url = f"https://newsapi.org/v2/everything?{urlencode(params)}"
                        
                        async with session.get(url) as response:
                            if response.status == 200:
                                data = await response.json()
                                
                                for article_data in data.get('articles', []):
                                    title = article_data.get('title', '').strip()
                                    url = article_data.get('url', '').strip()
                                    description = article_data.get('description', '')
                                    source = article_data.get('source', {}).get('name', 'Unknown')
                                    
                                    # Parse date
                                    published_at = article_data.get('publishedAt', '')
                                    published_date = datetime.now()
                                    if published_at:
                                        try:
                                            published_date = datetime.fromisoformat(published_at.replace('Z', '+00:00'))
                                        except:
                                            pass
                                    
                                    # Identify topics
                                    article_topics = self._identify_topics(title + ' ' + description)
                                    
                                    if title and url and article_topics:
                                        article = NewsArticle(
                                            title=title,
                                            url=url,
                                            snippet=description[:300] + '...' if len(description) > 300 else description,
                                            source=source,
                                            published_date=published_date,
                                            topics=article_topics
                                        )
                                        articles.append(article)
                            
                            # Small delay to respect rate limits
                            await asyncio.sleep(0.1)
                            
                    except Exception as e:
                        logger.error(f"Error fetching from News API for {keyword}: {e}")
        
        return articles
    
    async def _collect_general_news(self) -> List[NewsArticle]:
        """Collect articles from general news sources and filter by relevance."""
        articles = []
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for feed_url in self.general_rss_feeds:
                task = self._fetch_general_rss_feed(session, feed_url)
                tasks.append(task)
            
            # Execute all tasks concurrently
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    articles.extend(result)
                elif isinstance(result, Exception):
                    logger.warning(f"General RSS feed error: {result}")
        
        return articles
    
    async def _fetch_general_rss_feed(self, session: aiohttp.ClientSession, feed_url: str) -> List[NewsArticle]:
        """Fetch and parse a general RSS feed, filtering for relevant content."""
        articles = []
        
        try:
            async with session.get(feed_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    content = await response.text()
                    
                    # Parse RSS feed
                    feed = feedparser.parse(content)
                    
                    for entry in feed.entries:
                        title = entry.get('title', '').strip()
                        url = entry.get('link', '').strip()
                        summary = entry.get('summary', '') or entry.get('description', '')
                        
                        # Check if article is relevant to our topics
                        content_text = title + ' ' + summary
                        relevant_topics = self._identify_topics(content_text)
                        
                        if relevant_topics:  # Only include if relevant to our topics
                            # Parse date
                            published_date = datetime.now()
                            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                try:
                                    published_date = datetime(*entry.published_parsed[:6])
                                except:
                                    pass
                            
                            # Extract source from feed info or URL
                            source = getattr(feed.feed, 'title', 'General News')
                            
                            if title and url:
                                article = NewsArticle(
                                    title=title,
                                    url=url,
                                    snippet=summary[:300] + '...' if len(summary) > 300 else summary,
                                    source=source,
                                    published_date=published_date,
                                    topics=relevant_topics
                                )
                                articles.append(article)
                        
        except Exception as e:
            logger.debug(f"Error fetching general RSS feed {feed_url}: {e}")
        
        return articles
    
    async def _collect_reddit_news(self) -> List[NewsArticle]:
        """Collect articles from Reddit using RSS feeds."""
        articles = []
        
        async with aiohttp.ClientSession() as session:
            for topic, subreddits in self.reddit_subreddits.items():
                for subreddit in subreddits:
                    try:
                        # Reddit RSS feed URL
                        reddit_url = f"https://www.reddit.com/r/{subreddit}/hot.rss"
                        
                        async with session.get(reddit_url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                            if response.status == 200:
                                content = await response.text()
                                
                                # Parse RSS feed
                                feed = feedparser.parse(content)
                                
                                for entry in feed.entries:
                                    title = entry.get('title', '').strip()
                                    url = entry.get('link', '').strip()
                                    summary = entry.get('summary', '') or entry.get('description', '')
                                    
                                    # Check relevance
                                    content_text = title + ' ' + summary
                                    relevant_topics = self._identify_topics(content_text)
                                    
                                    # Include if relevant or from topic-specific subreddit
                                    if relevant_topics or topic in ['oregon_state', 'portland_timbers', 'star_wars', 'star_trek']:
                                        # Parse date
                                        published_date = datetime.now()
                                        if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                            try:
                                                published_date = datetime(*entry.published_parsed[:6])
                                            except:
                                                pass
                                        
                                        if title and url:
                                            article = NewsArticle(
                                                title=title,
                                                url=url,
                                                snippet=summary[:300] + '...' if len(summary) > 300 else summary,
                                                source=f"Reddit r/{subreddit}",
                                                published_date=published_date,
                                                topics=relevant_topics or [topic]
                                            )
                                            articles.append(article)
                            
                            # Small delay between requests
                            await asyncio.sleep(0.2)
                            
                    except Exception as e:
                        logger.error(f"Error fetching from Reddit r/{subreddit}: {e}")
        
        return articles
    
    def _identify_topics(self, text: str) -> List[str]:
        """Identify which topics are relevant to the given text."""
        text_lower = text.lower()
        relevant_topics = []
        
        for topic, keywords in self.topics.items():
            for keyword in keywords:
                if keyword.lower() in text_lower:
                    if topic not in relevant_topics:
                        relevant_topics.append(topic)
                    break
        
        return relevant_topics
    
    def _score_relevance(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Score articles based on relevance and user feedback history."""
        # Load user feedback history
        feedback_patterns = self._load_feedback_patterns()
        
        for article in articles:
            score = 0.0
            
            # Base score from topic matching
            score += len(article.topics) * 0.3
            
            # Boost score based on user feedback patterns
            title_words = set(article.title.lower().split())
            snippet_words = set(article.snippet.lower().split())
            
            for pattern, feedback_score in feedback_patterns.items():
                pattern_words = set(pattern.lower().split())
                
                # Check overlap with title and snippet
                title_overlap = len(title_words.intersection(pattern_words)) / max(len(pattern_words), 1)
                snippet_overlap = len(snippet_words.intersection(pattern_words)) / max(len(pattern_words), 1)
                
                if title_overlap > 0.3 or snippet_overlap > 0.2:
                    score += feedback_score
            
            # Recent articles get slight boost
            days_old = (datetime.now() - article.published_date).days
            if days_old <= 1:
                score += 0.3
            elif days_old <= 3:
                score += 0.1
            
            article.relevance_score = max(0.0, score)
        
        return articles
    
    def _load_feedback_patterns(self) -> Dict[str, float]:
        """Load user feedback patterns from database."""
        patterns = {}
        
        try:
            # This would connect to your database
            # For now, return empty patterns
            # TODO: Implement database connection for feedback patterns
            pass
        except Exception as e:
            logger.error(f"Error loading feedback patterns: {e}")
        
        return patterns
    
    def save_user_feedback(self, article_url: str, feedback: str):
        """Save user feedback for an article."""
        try:
            # TODO: Implement database storage for user feedback
            # This will be used to train the relevance scoring
            logger.info(f"User feedback saved: {article_url} -> {feedback}")
        except Exception as e:
            logger.error(f"Error saving user feedback: {e}")
    
    def _deduplicate_articles(self, articles: List[NewsArticle]) -> List[NewsArticle]:
        """Remove duplicate articles based on title similarity."""
        unique_articles = []
        seen_titles = set()
        
        for article in articles:
            # Normalize title for comparison
            normalized_title = re.sub(r'[^\w\s]', '', article.title.lower()).strip()
            
            if normalized_title not in seen_titles:
                seen_titles.add(normalized_title)
                unique_articles.append(article)
        
        return unique_articles
    
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags from text."""
        import re
        clean = re.compile('<.*?>')
        return re.sub(clean, '', text).strip()
    
    def _extract_domain(self, url: str) -> str:
        """Extract domain name from URL."""
        from urllib.parse import urlparse
        try:
            domain = urlparse(url).netloc
            # Remove 'www.' prefix
            if domain.startswith('www.'):
                domain = domain[4:]
            return domain
        except:
            return 'Unknown'

    async def collect_data(self) -> Dict[str, Any]:
        """Collect news data and save to database."""
        try:
            logger.info("Collecting news data...")
            
            # Collect all news articles
            articles = await self.collect_all_news()
            
            # Save articles to database
            from database import DatabaseManager
            db = DatabaseManager()
            
            saved_count = 0
            for article in articles:
                # Generate unique ID for article
                import hashlib
                article_id = hashlib.sha256(f"{article.url}{article.title}".encode()).hexdigest()[:16]
                
                article_data = {
                    'id': article_id,
                    'title': article.title,
                    'url': article.url,
                    'snippet': article.snippet,
                    'source': article.source,
                    'published_date': article.published_date.isoformat(),
                    'topics': article.topics,
                    'relevance_score': article.relevance_score,
                    'user_feedback': article.user_feedback
                }
                
                if db.save_news_article(article_data):
                    saved_count += 1
            
            # Return summary for API
            result = {
                'articles': [
                    {
                        'id': hashlib.sha256(f"{article.url}{article.title}".encode()).hexdigest()[:16],
                        'title': article.title,
                        'url': article.url,
                        'snippet': article.snippet,
                        'source': article.source,
                        'published_date': article.published_date.isoformat(),
                        'topics': article.topics,
                        'relevance_score': article.relevance_score,
                        'user_feedback': article.user_feedback
                    }
                    for article in articles
                ],
                'total': len(articles),
                'saved_to_database': saved_count,
                'timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Collected {len(articles)} news articles, saved {saved_count} to database")
            return result
            
        except Exception as e:
            logger.error(f"Error collecting news data: {e}")
            return {
                'articles': [],
                'total': 0,
                'saved_to_database': 0,
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }

# Example usage
async def main():
    """Test the news collector."""
    collector = NewsCollector()
    articles = await collector.collect_all_news()
    
    print(f"Collected {len(articles)} articles:")
    for article in articles[:5]:
        print(f"- {article.title}")
        print(f"  Source: {article.source}")
        print(f"  Topics: {', '.join(article.topics)}")
        print(f"  Score: {article.relevance_score:.2f}")
        print()

if __name__ == "__main__":
    asyncio.run(main())
