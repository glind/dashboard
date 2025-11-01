#!/usr/bin/env python3
"""
Test the personalized AI assistant with actual user data.
"""

import asyncio
import json
import sys
import os
sys.path.append('/Users/greglind/Projects/me/dashboard')

from database import db
from processors.ai_providers import OllamaProvider

async def test_personalized_ai():
    """Test the AI assistant with personalized context."""
    
    print("🤖 Testing Personalized AI Assistant")
    print("=" * 50)
    
    # Get the Ollama configuration
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ai_providers WHERE is_active = 1 AND provider_type = "ollama"')
        provider_row = cursor.fetchone()
    
    if not provider_row:
        print("❌ No active Ollama provider found")
        return
    
    config = json.loads(provider_row['config_data'])
    print(f"🔗 Connected to: {config.get('base_url')} with model {config.get('model_name')}")
    
    # Create Ollama provider with personalized system prompt
    personal_prompt = db.get_setting('personalized_system_prompt', '')
    if personal_prompt:
        config['system_prompt'] = personal_prompt
        print("✅ Using personalized system prompt")
    else:
        print("⚠️ No personalized prompt found, using default")
    
    ollama = OllamaProvider(provider_row['name'], config)
    
    # Test connection
    if not await ollama.health_check():
        print(f"❌ Cannot connect to Ollama at {config.get('base_url')}")
        return
    
    print("✅ Ollama connection healthy")
    print()
    
    # Test conversations with personal context
    test_queries = [
        "What can you tell me about my email patterns?",
        "Based on my data, what should I prioritize today?", 
        "What insights do you have about my communication habits?",
        "Analyze my music preferences and suggest similar content",
        "What are the most important emails I should focus on?"
    ]
    
    for i, query in enumerate(test_queries, 1):
        print(f"🔍 Test {i}: {query}")
        print("-" * 30)
        
        messages = [{'role': 'user', 'content': query}]
        
        try:
            response = await ollama.chat(messages)
            print(f"🤖 AI Response:\n{response}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("\n" + "=" * 50 + "\n")
    
    # Show some actual data for context
    print("📊 Your Data Context:")
    print("-" * 20)
    
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Show email stats
        cursor.execute("""
            SELECT sender, COUNT(*) as count, priority
            FROM emails 
            GROUP BY sender, priority
            ORDER BY count DESC
            LIMIT 5
        """)
        email_stats = cursor.fetchall()
        
        print("📧 Top Email Senders:")
        for stat in email_stats:
            print(f"   • {stat['sender'][:50]}... ({stat['count']} emails, {stat['priority']} priority)")
        
        # Show music stats
        cursor.execute("""
            SELECT artist, COUNT(*) as count
            FROM music_content 
            WHERE artist IS NOT NULL AND artist != 'NullRecords'
            GROUP BY artist
            ORDER BY count DESC
            LIMIT 5
        """)
        music_stats = cursor.fetchall()
        
        print("\n🎵 Top Artists:")
        for stat in music_stats:
            print(f"   • {stat['artist']} ({stat['count']} tracks)")

if __name__ == "__main__":
    asyncio.run(test_personalized_ai())