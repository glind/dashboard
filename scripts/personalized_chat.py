#!/usr/bin/env python3
"""
Enhanced AI chat interface with personalized context.
"""

import asyncio
import json
import sys
import os
sys.path.append('/Users/greglind/Projects/me/dashboard')

from database import db
from processors.ai_providers import OllamaProvider

class PersonalizedAIChat:
    """AI chat interface with personalized context."""
    
    def __init__(self):
        self.ollama = None
        self.personal_context = ""
    
    async def initialize(self):
        """Initialize the AI with personalized context."""
        
        # Get Ollama configuration
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ai_providers WHERE is_active = 1 AND provider_type = "ollama"')
            provider_row = cursor.fetchone()
        
        if not provider_row:
            print("❌ No active Ollama provider found")
            return False
        
        config = json.loads(provider_row['config_data'])
        
        # Create personalized context from actual data
        self.personal_context = await self.build_personal_context()
        
        # Override the system prompt with personalized one
        config['system_prompt'] = self.personal_context
        
        self.ollama = OllamaProvider(provider_row['name'], config)
        self.ollama.system_prompt = self.personal_context  # Ensure it's set
        
        # Test connection
        if not await self.ollama.health_check():
            print(f"❌ Cannot connect to Ollama at {config.get('base_url')}")
            return False
        
        print(f"✅ Connected to {config.get('base_url')} with model {config.get('model_name')}")
        return True
    
    async def build_personal_context(self) -> str:
        """Build comprehensive personal context from actual data."""
        
        context_parts = []
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Email analysis
            cursor.execute("""
                SELECT sender, subject, priority, body 
                FROM emails 
                ORDER BY created_at DESC 
                LIMIT 10
            """)
            recent_emails = cursor.fetchall()
            
            # Communication patterns
            cursor.execute("""
                SELECT sender, COUNT(*) as count, 
                       GROUP_CONCAT(DISTINCT priority) as priorities
                FROM emails 
                GROUP BY sender
                ORDER BY count DESC
                LIMIT 5
            """)
            top_senders = cursor.fetchall()
            
            # Music preferences
            cursor.execute("""
                SELECT artist, COUNT(*) as count
                FROM music_content
                WHERE artist != 'NullRecords' AND artist IS NOT NULL
                GROUP BY artist
                ORDER BY count DESC
                LIMIT 5
            """)
            music_prefs = cursor.fetchall()
        
        # Build comprehensive context
        base_prompt = """You are Gregory's personal AI assistant with access to his actual data and communication patterns.

PERSONAL DATA CONTEXT:"""
        
        # Email context
        if recent_emails:
            base_prompt += f"\n\nRECENT EMAILS ({len(recent_emails)} samples):"
            for email in recent_emails[:5]:
                sender_domain = email['sender'].split('@')[-1].split('>')[0] if '@' in email['sender'] else email['sender']
                base_prompt += f"\n- From {sender_domain}: \"{email['subject']}\" (Priority: {email['priority']})"
        
        # Communication patterns
        if top_senders:
            base_prompt += f"\n\nTOP COMMUNICATION PARTNERS:"
            for sender in top_senders:
                sender_domain = sender['sender'].split('@')[-1].split('>')[0] if '@' in sender['sender'] else sender['sender']
                base_prompt += f"\n- {sender_domain}: {sender['count']} emails (Priorities: {sender['priorities']})"
        
        # Music preferences
        if music_prefs:
            base_prompt += f"\n\nMUSIC PREFERENCES:"
            for artist in music_prefs:
                base_prompt += f"\n- {artist['artist']}: {artist['count']} tracks"
        
        base_prompt += """

YOUR CAPABILITIES:
- Analyze Gregory's email patterns and suggest prioritization
- Provide insights about communication habits based on actual data
- Recommend actions based on his workflow patterns
- Reference specific emails, senders, and music preferences when relevant
- Help optimize productivity based on observed patterns

INTERACTION STYLE:
- Be specific and reference actual data points
- Provide actionable insights based on real patterns
- Help prioritize tasks and communications
- Be concise but comprehensive in analysis"""

        return base_prompt
    
    async def chat(self, user_message: str) -> str:
        """Have a conversation with personalized context."""
        if not self.ollama:
            return "AI not initialized"
        
        # Create messages with explicit system prompt
        messages = [
            {'role': 'system', 'content': self.personal_context},
            {'role': 'user', 'content': user_message}
        ]
        
        try:
            response = await self.ollama.chat(messages)
            return response
        except Exception as e:
            return f"Error: {e}"

async def main():
    """Main chat interface."""
    
    print("🤖 Gregory's Personalized AI Assistant")
    print("=" * 50)
    
    ai = PersonalizedAIChat()
    
    if not await ai.initialize():
        print("Failed to initialize AI")
        return
    
    print("💡 Ready! The AI now has context about your emails, music, and patterns.")
    print("Type 'quit' to exit\n")
    
    # Example queries to test personalization
    test_queries = [
        "Analyze my recent email patterns and tell me what's most important",
        "Based on my communication history, who should I prioritize responding to?",
        "What insights do you have about my music preferences?",
        "Which emails require immediate attention based on my usual patterns?",
        "Suggest how I should organize my workflow today based on my data"
    ]
    
    print("🔍 Here are some example queries to try:")
    for i, query in enumerate(test_queries, 1):
        print(f"{i}. {query}")
    print()
    
    while True:
        try:
            user_input = input("📝 Your question: ").strip()
            
            if user_input.lower() in ['quit', 'exit', 'bye']:
                print("👋 Goodbye!")
                break
            
            if not user_input:
                continue
            
            print("\n🤖 AI Assistant:")
            print("-" * 30)
            
            response = await ai.chat(user_input)
            print(response)
            print("\n" + "=" * 50 + "\n")
            
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(main())