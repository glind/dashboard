#!/usr/bin/env python3
"""
Initialize default news sources and populate the database.
"""

import os
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import DatabaseManager

def initialize_default_news_sources():
    """Initialize default news sources in the database."""
    db = DatabaseManager()
    
    # Default news sources with RSS feeds
    default_sources = [
        {
            "name": "BBC News",
            "url": "https://feeds.bbci.co.uk/news/rss.xml",
            "category": "general",
            "is_custom": False
        },
        {
            "name": "BBC Technology",
            "url": "https://feeds.bbci.co.uk/news/technology/rss.xml",
            "category": "tech",
            "is_custom": False
        },
        {
            "name": "ESPN",
            "url": "https://www.espn.com/espn/rss/news",
            "category": "sports",
            "is_custom": False
        },
        {
            "name": "NPR News",
            "url": "https://feeds.npr.org/1001/rss.xml",
            "category": "general",
            "is_custom": False
        },
        {
            "name": "NPR Technology",
            "url": "https://feeds.npr.org/1019/rss.xml",
            "category": "tech",
            "is_custom": False
        },
        {
            "name": "Hacker News",
            "url": "https://hnrss.org/frontpage",
            "category": "tech",
            "is_custom": False
        },
        {
            "name": "TechCrunch",
            "url": "https://techcrunch.com/feed/",
            "category": "tech",
            "is_custom": False
        },
        {
            "name": "Reuters",
            "url": "https://feeds.reuters.com/reuters/topNews",
            "category": "general",
            "is_custom": False
        },
        {
            "name": "Associated Press",
            "url": "https://feeds.apnews.com/rss/apf-topnews",
            "category": "general",
            "is_custom": False
        },
        # Portland/Oregon specific
        {
            "name": "The Oregonian",
            "url": "https://www.oregonlive.com/arc/outboundfeeds/rss/category/sports/?outputType=xml",
            "category": "oregon",
            "is_custom": False
        },
        {
            "name": "Portland Timbers",
            "url": "https://www.timbers.com/feeds/news",
            "category": "timbers",
            "is_custom": False
        },
        # Star Wars/Trek
        {
            "name": "StarWars.com",
            "url": "https://www.starwars.com/news/feed",
            "category": "starwars",
            "is_custom": False
        }
    ]
    
    print("Initializing default news sources...")
    
    # Get existing sources to avoid duplicates
    existing_sources = db.get_news_sources(active_only=False)
    existing_urls = {source['url'] for source in existing_sources}
    
    added_count = 0
    for source in default_sources:
        if source['url'] not in existing_urls:
            try:
                db.add_news_source(
                    name=source['name'],
                    url=source['url'],
                    category=source['category'],
                    is_custom=source['is_custom']
                )
                print(f"✅ Added: {source['name']}")
                added_count += 1
            except Exception as e:
                print(f"❌ Failed to add {source['name']}: {e}")
        else:
            print(f"⏭️  Skipped: {source['name']} (already exists)")
    
    print(f"\n🎉 Added {added_count} new news sources")
    print(f"📰 Total sources: {len(db.get_news_sources(active_only=False))}")

if __name__ == "__main__":
    initialize_default_news_sources()