#!/usr/bin/env python3
"""
Fix News Collector SSL Issues and Test Real RSS Feeds
"""

import asyncio
import aiohttp
import feedparser
import ssl
from datetime import datetime
import sys
sys.path.append('/Users/greglind/Projects/me/dashboard')

from database import db
import json

async def test_rss_feeds():
    """Test RSS feeds that should work without SSL issues."""
    
    print("🔍 Testing RSS Feeds for News...")
    
    # RSS feeds that typically don't have SSL issues
    test_feeds = [
        ('BBC News', 'http://feeds.bbci.co.uk/news/rss.xml'),
        ('Reuters', 'http://feeds.reuters.com/reuters/topNews'),
        ('NPR News', 'https://feeds.npr.org/1001/rss.xml'),
        ('ESPN', 'https://www.espn.com/espn/rss/news')
    ]
    
    # Create SSL context that's more permissive
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    connector = aiohttp.TCPConnector(ssl=ssl_context)
    
    articles_collected = []
    
    async with aiohttp.ClientSession(connector=connector, timeout=aiohttp.ClientTimeout(total=10)) as session:
        for source_name, feed_url in test_feeds:
            print(f"\nTesting {source_name}: {feed_url}")
            
            try:
                async with session.get(feed_url) as response:
                    if response.status == 200:
                        content = await response.text()
                        
                        # Parse RSS content
                        feed = feedparser.parse(content)
                        
                        if feed.entries:
                            print(f"✅ {source_name}: Found {len(feed.entries)} articles")
                            
                            # Get first few articles
                            for entry in feed.entries[:3]:
                                title = entry.get('title', 'No title')
                                link = entry.get('link', '')
                                summary = entry.get('summary', entry.get('description', ''))
                                
                                # Clean up summary
                                if summary:
                                    # Remove HTML tags
                                    import re
                                    summary = re.sub(r'<[^>]+>', '', summary)
                                    summary = summary[:200] + '...' if len(summary) > 200 else summary
                                
                                # Get publication date
                                pub_date = entry.get('published_parsed')
                                if pub_date:
                                    pub_datetime = datetime(*pub_date[:6])
                                else:
                                    pub_datetime = datetime.now()
                                
                                article = {
                                    'title': title,
                                    'url': link,
                                    'snippet': summary,
                                    'source': source_name,
                                    'published_date': pub_datetime.isoformat(),
                                    'topics': json.dumps(['general', 'news']),
                                    'relevance_score': 0.6
                                }
                                
                                articles_collected.append(article)
                                
                            print(f"   Sample: {feed.entries[0].get('title', 'No title')}")
                        else:
                            print(f"❌ {source_name}: No articles found in feed")
                    else:
                        print(f"❌ {source_name}: HTTP {response.status}")
                        
            except Exception as e:
                print(f"❌ {source_name}: Error - {e}")
    
    # Save collected articles to database
    if articles_collected:
        print(f"\n💾 Saving {len(articles_collected)} real news articles...")
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            for article in articles_collected:
                try:
                    cursor.execute('''
                        INSERT OR REPLACE INTO news_articles 
                        (title, url, snippet, source, published_date, topics, relevance_score)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        article['title'],
                        article['url'],
                        article['snippet'],
                        article['source'],
                        article['published_date'],
                        article['topics'],
                        article['relevance_score']
                    ))
                except Exception as e:
                    print(f"Error saving article: {e}")
            
            conn.commit()
            
            # Check total count
            cursor.execute('SELECT COUNT(*) as count FROM news_articles')
            total_count = cursor.fetchone()['count']
            
            print(f"✅ Total news articles in database: {total_count}")
    
    await connector.close()

if __name__ == "__main__":
    asyncio.run(test_rss_feeds())