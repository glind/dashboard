#!/usr/bin/env python3
"""
Personalized AI Training Script
Creates training data from collected personal data to fine-tune Ollama for personal assistance.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from database import db
from processors.ai_providers import ai_manager, OllamaProvider
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PersonalizedAITrainer:
    """Creates personalized training data from user's collected information."""
    
    def __init__(self):
        self.training_samples = []
    
    def collect_email_insights(self) -> List[Dict[str, Any]]:
        """Extract patterns and insights from collected emails."""
        training_samples = []
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get emails with analysis
            cursor.execute("""
                SELECT subject, sender, body, priority, ollama_priority, 
                       has_todos, is_archived, created_at
                FROM emails 
                WHERE body IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 50
            """)
            
            emails = cursor.fetchall()
            
            for email in emails:
                # Extract sender domain/company
                sender_match = re.search(r'@([^>]+)', email['sender'])
                domain = sender_match.group(1) if sender_match else 'unknown'
                
                # Create training context based on email characteristics
                context_parts = []
                if email['priority'] == 'high':
                    context_parts.append("high priority")
                if email['has_todos']:
                    context_parts.append("contains actionable items")
                if domain != 'unknown':
                    context_parts.append(f"from {domain}")
                
                # Create personal context about email handling preferences
                content = f"Email from {email['sender']}\nSubject: {email['subject']}"
                if email['body']:
                    # Get first 200 chars of body for context
                    body_preview = email['body'][:200].replace('\n', ' ').replace('\r', ' ')
                    content += f"\nContent preview: {body_preview}..."
                
                context = f"User typically handles emails from {domain}"
                if email['priority']:
                    context += f" as {email['priority']} priority"
                if email['ollama_priority']:
                    context += f", AI suggested priority: {email['ollama_priority']}"
                
                training_sample = {
                    'data_type': 'email_handling',
                    'content': content,
                    'context': context,
                    'metadata': {
                        'domain': domain,
                        'priority': email['priority'],
                        'has_todos': bool(email['has_todos']),
                        'sender_type': self._classify_sender(email['sender'])
                    },
                    'timestamp': email['created_at'],
                    'relevance_score': 0.7
                }
                
                training_samples.append(training_sample)
        
        logger.info(f"Collected {len(training_samples)} email insight samples")
        return training_samples
    
    def collect_music_preferences(self) -> List[Dict[str, Any]]:
        """Extract music taste patterns from collected music data."""
        training_samples = []
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Get music content
            cursor.execute("""
                SELECT title, artist, album, genres, source, is_liked, user_feedback
                FROM music_content 
                WHERE title IS NOT NULL
                ORDER BY created_at DESC
                LIMIT 100
            """)
            
            music_items = cursor.fetchall()
            
            # Analyze music preferences
            liked_genres = set()
            liked_artists = set()
            sources = set()
            
            for item in music_items:
                if item['genres']:
                    try:
                        genres = json.loads(item['genres'])
                        for genre in genres:
                            liked_genres.add(genre)
                    except:
                        pass
                
                if item['artist']:
                    liked_artists.add(item['artist'])
                    
                if item['source']:
                    sources.add(item['source'])
            
            # Create training sample about music preferences
            if liked_genres or liked_artists:
                content = "User's Music Preferences:\n"
                if liked_genres:
                    content += f"Preferred genres: {', '.join(list(liked_genres)[:10])}\n"
                if liked_artists:
                    content += f"Liked artists: {', '.join(list(liked_artists)[:10])}\n"
                if sources:
                    content += f"Music sources: {', '.join(sources)}"
                
                context = f"User listens to {len(liked_genres)} different genres and {len(liked_artists)} artists"
                
                training_sample = {
                    'data_type': 'music_preferences',
                    'content': content,
                    'context': context,
                    'metadata': {
                        'genre_count': len(liked_genres),
                        'artist_count': len(liked_artists),
                        'top_genres': list(liked_genres)[:5],
                        'sources': list(sources)
                    },
                    'timestamp': datetime.now().isoformat(),
                    'relevance_score': 0.8
                }
                
                training_samples.append(training_sample)
        
        logger.info(f"Collected {len(training_samples)} music preference samples")
        return training_samples
    
    def collect_communication_patterns(self) -> List[Dict[str, Any]]:
        """Analyze communication patterns from emails."""
        training_samples = []
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Analyze sender patterns
            cursor.execute("""
                SELECT sender, COUNT(*) as email_count,
                       MAX(created_at) as last_email,
                       AVG(CASE WHEN priority = 'high' THEN 1 ELSE 0 END) as high_priority_rate
                FROM emails 
                GROUP BY sender
                HAVING email_count > 1
                ORDER BY email_count DESC
                LIMIT 20
            """)
            
            sender_patterns = cursor.fetchall()
            
            for pattern in sender_patterns:
                # Extract company/domain from sender
                sender_match = re.search(r'@([^>]+)', pattern['sender'])
                domain = sender_match.group(1) if sender_match else 'personal'
                
                content = f"Communication pattern with {pattern['sender']}"
                context_parts = [
                    f"{pattern['email_count']} emails received",
                    f"last contact: {pattern['last_email']}"
                ]
                
                if pattern['high_priority_rate'] > 0.5:
                    context_parts.append("usually high priority")
                elif pattern['high_priority_rate'] == 0:
                    context_parts.append("typically low priority")
                
                context = f"Regular contact from {domain}: " + ", ".join(context_parts)
                
                training_sample = {
                    'data_type': 'communication_patterns',
                    'content': content,
                    'context': context,
                    'metadata': {
                        'domain': domain,
                        'frequency': pattern['email_count'],
                        'high_priority_rate': pattern['high_priority_rate'],
                        'contact_type': self._classify_sender(pattern['sender'])
                    },
                    'timestamp': pattern['last_email'],
                    'relevance_score': min(0.9, pattern['email_count'] / 10.0)
                }
                
                training_samples.append(training_sample)
        
        logger.info(f"Collected {len(training_samples)} communication pattern samples")
        return training_samples
    
    def _classify_sender(self, sender: str) -> str:
        """Classify sender type based on email address."""
        sender_lower = sender.lower()
        
        if any(keyword in sender_lower for keyword in ['noreply', 'no-reply', 'donotreply']):
            return 'automated'
        elif any(keyword in sender_lower for keyword in ['linkedin', 'facebook', 'twitter', 'instagram']):
            return 'social_media'
        elif any(keyword in sender_lower for keyword in ['github', 'gitlab', 'bitbucket']):
            return 'development'
        elif any(keyword in sender_lower for keyword in ['newsletter', 'digest', 'update']):
            return 'newsletter'
        elif re.search(r'@(gmail|yahoo|hotmail|outlook)\.', sender_lower):
            return 'personal'
        else:
            return 'business'
    
    def create_personal_system_prompt(self) -> str:
        """Create a personalized system prompt based on collected data."""
        
        # Gather insights from data
        insights = []
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Email insights
            cursor.execute("SELECT COUNT(*) as count FROM emails")
            email_count = cursor.fetchone()['count']
            if email_count > 0:
                insights.append(f"You have access to {email_count} recent emails showing communication patterns")
            
            # Music insights
            cursor.execute("SELECT COUNT(DISTINCT artist) as artists, COUNT(DISTINCT source) as sources FROM music_content")
            music_stats = cursor.fetchone()
            if music_stats['artists'] > 0:
                insights.append(f"User listens to {music_stats['artists']} different artists across {music_stats['sources']} platforms")
            
            # Priority patterns
            cursor.execute("SELECT priority, COUNT(*) as count FROM emails GROUP BY priority")
            priorities = cursor.fetchall()
            priority_info = ", ".join([f"{p['count']} {p['priority']}" for p in priorities])
            if priority_info:
                insights.append(f"Email priorities: {priority_info}")
        
        system_prompt = f"""You are Gregory's personal AI assistant with deep knowledge of his preferences and patterns.

PERSONAL CONTEXT:
- {'. '.join(insights)}
- You should provide personalized recommendations based on his actual data
- Learn from his communication patterns, music tastes, and priorities
- Help manage tasks, analyze emails, and provide relevant insights

YOUR ROLE:
- Analyze and prioritize information based on Gregory's patterns
- Suggest actions based on his typical email handling
- Provide music recommendations aligned with his taste  
- Help identify important communications and tasks
- Be concise but insightful, personal but professional

INTERACTION STYLE:
- Reference his actual data and patterns when relevant
- Provide specific, actionable insights
- Learn from his feedback to improve future recommendations
- Focus on productivity and personal workflow optimization"""

        return system_prompt
    
    async def create_personalized_training_dataset(self) -> List[Dict[str, Any]]:
        """Create complete personalized training dataset."""
        all_samples = []
        
        # Collect different types of training data
        all_samples.extend(self.collect_email_insights())
        all_samples.extend(self.collect_music_preferences())
        all_samples.extend(self.collect_communication_patterns())
        
        # Sort by relevance score
        all_samples.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        # Save to database
        for sample in all_samples:
            db.save_ai_training_data(
                data_type=sample['data_type'],
                content=sample['content'],
                context=sample['context'],
                source_table='emails',  # Most data comes from emails
                relevance_score=sample['relevance_score']
            )
        
        logger.info(f"Created personalized training dataset with {len(all_samples)} samples")
        return all_samples
    
    async def train_ollama_model(self) -> Dict[str, Any]:
        """Train/fine-tune the Ollama model with personalized data."""
        
        # Get training data
        training_dataset = await self.create_personalized_training_dataset()
        
        if not training_dataset:
            return {
                'status': 'error',
                'message': 'No training data available'
            }
        
        # Get Ollama configuration from database
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM ai_providers WHERE is_active = 1 AND provider_type = "ollama"')
            provider_row = cursor.fetchone()
        
        if not provider_row:
            return {
                'status': 'error',
                'message': 'No active Ollama provider configured in database'
            }
        
        # Create Ollama provider instance
        import json
        config = json.loads(provider_row['config_data'])
        ollama_provider = OllamaProvider(provider_row['name'], config)
        
        # Test connection
        if not await ollama_provider.health_check():
            return {
                'status': 'error',
                'message': f'Cannot connect to Ollama server at {config.get("base_url", "unknown")}'
            }
        
        # Create personalized system prompt
        personal_prompt = self.create_personal_system_prompt()
        
        # Create training data with personal context
        enhanced_training_data = []
        for sample in training_dataset[:30]:  # Limit to avoid overwhelming
            enhanced_sample = {
                **sample,
                'system_prompt': personal_prompt,
                'personal_context': True
            }
            enhanced_training_data.append(enhanced_sample)
        
        # Train the model
        try:
            result = await ollama_provider.train(enhanced_training_data)
            
            # Update system prompt for future conversations
            ollama_provider.system_prompt = personal_prompt
            
            # Save the personalized prompt to database for future use
            db.save_setting('personalized_system_prompt', personal_prompt)
            
            return {
                'status': 'success',
                'training_samples': len(enhanced_training_data),
                'model_result': result,
                'personal_prompt_created': True,
                'ollama_config': f"{config.get('base_url')} with model {config.get('model_name')}",
                'message': f'Successfully trained Ollama with {len(enhanced_training_data)} personalized samples'
            }
            
        except Exception as e:
            logger.error(f"Training failed: {e}")
            return {
                'status': 'error',
                'message': f'Training failed: {str(e)}'
            }


async def main():
    """Main function to run personalized AI training."""
    
    print("🤖 Starting Personalized AI Training...")
    print("=" * 50)
    
    trainer = PersonalizedAITrainer()
    
    # Check what data we have
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM emails")
        email_count = cursor.fetchone()['count']
        cursor.execute("SELECT COUNT(*) as count FROM music_content")
        music_count = cursor.fetchone()['count']
    
    print(f"📧 Emails available: {email_count}")
    print(f"🎵 Music items available: {music_count}")
    print()
    
    if email_count == 0 and music_count == 0:
        print("❌ No data available for training. Please collect some data first.")
        return
    
    # Create personalized training
    print("📊 Creating personalized training dataset...")
    result = await trainer.train_ollama_model()
    
    print("Training Result:")
    print(f"Status: {result['status']}")
    print(f"Message: {result['message']}")
    
    if result['status'] == 'success':
        print(f"✅ Training completed with {result['training_samples']} samples")
        if 'model_result' in result:
            print(f"Model result: {result['model_result']}")
    else:
        print(f"❌ Training failed: {result['message']}")
    
    print("\n" + "=" * 50)
    print("🎯 Your AI assistant is now personalized!")
    print("Try chatting with it to see how it uses your data.")


if __name__ == "__main__":
    asyncio.run(main())