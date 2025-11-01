#!/usr/bin/env python3
import asyncio
import json
import sys
import requests
sys.path.append('/Users/greglind/Projects/me/dashboard')

from database import db
from processors.ai_providers import OllamaProvider

async def test_ollama():
    print('🔍 Testing Ollama connection (pop-os2.local)...')
    
    # Test direct connection
    try:
        response = requests.get('http://pop-os2.local:11434/api/tags', timeout=5)
        if response.status_code == 200:
            data = response.json()
            models = [m['name'] for m in data.get('models', [])]
            print(f'✅ pop-os2.local:11434 is accessible!')
            print(f'Available models: {models}')
        else:
            print(f'❌ Server returned status: {response.status_code}')
            return False
    except Exception as e:
        print(f'❌ Cannot reach pop-os2.local:11434: {e}')
        return False
    
    # Test through AI provider
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM ai_providers WHERE is_active = 1')
        provider_row = cursor.fetchone()
    
    config = json.loads(provider_row['config_data'])
    ollama = OllamaProvider(provider_row['name'], config)
    
    # Test health check
    health = await ollama.health_check()
    print(f'Health check: {"✅ Healthy" if health else "❌ Unhealthy"}')
    
    if health:
        # Test simple chat
        print('🤖 Testing AI chat...')
        messages = [{'role': 'user', 'content': 'Hello! Please just respond with: I am working correctly'}]
        response = await ollama.chat(messages)
        print(f'AI Response: {response}')
        return True
    
    return False

if __name__ == "__main__":
    result = asyncio.run(test_ollama())
    print(f'\nOverall result: {"✅ Ready for personalized AI!" if result else "❌ Connection issues remain"}')