#!/usr/bin/env python3
"""
Quick fix for news API endpoint
"""

import sys
sys.path.append('/Users/greglind/Projects/me/dashboard')

from database import db
import json

def test_news_api_fix():
    """Test and show the correct way to access news articles"""
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT title, url, snippet, source, published_date, topics, relevance_score
            FROM news_articles 
            ORDER BY published_date DESC 
            LIMIT 5
        ''')
        articles = cursor.fetchall()
    
    print("News API Response Format:")
    api_articles = []
    
    for article in articles:
        # Create article ID
        article_id = f"news_{hash(article['title'] + article['url'])}"
        
        # Parse topics safely
        try:
            topics = json.loads(article['topics']) if article['topics'] else ['General']
        except:
            topics = ['General']
        
        # Create API response format
        article_data = {
            "id": article_id,
            "title": article['title'],
            "source": article['source'], 
            "url": article['url'],
            "description": article['snippet'] or "No description available",
            "published_at": article['published_date'],
            "category": ', '.join(topics),
            "relevance_score": article['relevance_score'] or 0.0
        }
        
        api_articles.append(article_data)
        
        print(f"✅ {article['title']} ({article['source']})")
    
    print(f"\nTotal articles processed: {len(api_articles)}")
    
    # Show what the API should return
    response = {
        "articles": api_articles,
        "filter": "all", 
        "total": len(api_articles),
        "source": "Database"
    }
    
    print("\nAPI Response Preview:")
    print(json.dumps(response, indent=2)[:500] + "...")

if __name__ == "__main__":
    test_news_api_fix()