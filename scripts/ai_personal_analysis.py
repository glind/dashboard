#!/usr/bin/env python3
"""
Personal AI Assistant with Data-Driven Context
Creates specific insights based on Gregory's actual collected data.
"""

import asyncio
import json
import sys
import re
sys.path.append('/Users/greglind/Projects/me/dashboard')

from database import db
from processors.ai_providers import OllamaProvider

async def analyze_with_personal_data():
    """Generate specific insights using Gregory's actual data."""
    
    print("🤖 Personal AI Analysis with Real Data")
    print("=" * 50)
    
    # Get Ollama configuration
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ai_providers WHERE is_active = 1 AND provider_type = "ollama"')
        provider_row = cursor.fetchone()
    
    if not provider_row:
        print("❌ No Ollama provider found")
        return
    
    config = json.loads(provider_row['config_data'])
    ollama = OllamaProvider(provider_row['name'], config)
    
    # Test connection
    if not await ollama.health_check():
        print(f"❌ Cannot connect to Ollama at {config.get('base_url')}")
        return
    
    print(f"✅ Connected to {config.get('base_url')} with {config.get('model_name')}")
    print()
    
    # Gather actual data for analysis
    with db.get_connection() as conn:
        cursor = conn.cursor()
        
        # Get detailed email data
        cursor.execute("""
            SELECT sender, subject, priority, 
                   SUBSTR(body, 1, 200) as snippet,
                   created_at
            FROM emails 
            WHERE body IS NOT NULL
            ORDER BY 
                CASE priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END,
                created_at DESC
            LIMIT 15
        """)
        emails = cursor.fetchall()
        
        # Get sender statistics
        cursor.execute("""
            SELECT sender, COUNT(*) as email_count,
                   GROUP_CONCAT(DISTINCT priority) as priorities,
                   MAX(created_at) as last_email
            FROM emails
            GROUP BY sender
            ORDER BY email_count DESC
            LIMIT 10
        """)
        sender_stats = cursor.fetchall()
        
        # Get music data
        cursor.execute("""
            SELECT artist, title, source, genres
            FROM music_content
            WHERE artist != 'NullRecords' AND artist IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 20
        """)
        music_data = cursor.fetchall()
    
    # Create data-rich context for AI analysis
    data_context = f"""I am Gregory's personal AI assistant. Here is Gregory's actual data to analyze:

RECENT EMAILS (prioritized by urgency):
"""
    
    for i, email in enumerate(emails, 1):
        sender_clean = re.sub(r'<.*?>', '', email['sender']).strip().strip('"')
        data_context += f"{i}. FROM: {sender_clean}\n"
        data_context += f"   SUBJECT: {email['subject']}\n"
        data_context += f"   PRIORITY: {email['priority']}\n"
        data_context += f"   PREVIEW: {email['snippet']}...\n"
        data_context += f"   DATE: {email['created_at']}\n\n"
    
    data_context += "COMMUNICATION PATTERNS:\n"
    for stat in sender_stats:
        sender_clean = re.sub(r'<.*?>', '', stat['sender']).strip().strip('"')
        data_context += f"• {sender_clean}: {stat['email_count']} emails (priorities: {stat['priorities']})\n"
    
    data_context += f"\nMUSIC PREFERENCES:\n"
    for music in music_data[:10]:
        genres_str = music['genres'] if music['genres'] else 'Unknown'
        data_context += f"• {music['artist']} - {music['title']} ({music['source']}) [{genres_str}]\n"
    
    # Now ask specific analytical questions
    queries = [
        "Based on Gregory's actual email data above, which 3 emails should he prioritize TODAY and why? Be specific about senders and subjects.",
        
        "Analyze Gregory's communication patterns from the data. Who are his most frequent contacts and what does this tell us about his workflow?",
        
        "Looking at Gregory's music preferences, what genres does he prefer and what does this suggest about his personality for work productivity?",
        
        "Based on the email priorities and content previews, what are the main themes Gregory deals with professionally?",
        
        "Create a personalized productivity plan for Gregory based on his email patterns and suggest the best times for different types of work."
    ]
    
    for i, query in enumerate(queries, 1):
        print(f"🔍 Analysis {i}: {query.split('?')[0]}?")
        print("-" * 60)
        
        # Combine data context with specific query
        full_prompt = data_context + f"\n\nQUESTION: {query}\n\nProvide a specific, actionable analysis based only on the actual data provided above."
        
        messages = [{'role': 'user', 'content': full_prompt}]
        
        try:
            response = await ollama.chat(messages)
            print(f"🤖 **Analysis Result:**\n{response}")
            
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print("\n" + "=" * 70 + "\n")
    
    print("✅ Personal AI analysis complete!")
    print("🎯 The AI has now analyzed your actual emails, music, and patterns!")

if __name__ == "__main__":
    asyncio.run(analyze_with_personal_data())