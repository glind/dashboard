"""
AI Provider implementations for multiple backends (Ollama, OpenAI, Gemini).
"""

import json
import logging
import hashlib
import asyncio
from datetime import datetime
from typing import Dict, Any, List, Optional, AsyncGenerator
from abc import ABC, abstractmethod

import aiohttp
import openai
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """Base class for AI providers."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        self.name = name
        self.config = config
        self.provider_type = self.__class__.__name__.lower().replace('provider', '')
    
    @abstractmethod
    async def chat(self, messages: List[Dict[str, str]], stream: bool = False) -> str:
        """Send chat messages to AI provider."""
        pass
    
    @abstractmethod
    async def train(self, training_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Train or fine-tune the model."""
        pass
    
    @abstractmethod
    async def health_check(self) -> bool:
        """Check if provider is available."""
        pass
    
    def generate_training_hash(self, training_data: List[Dict[str, Any]]) -> str:
        """Generate hash for training data to detect changes."""
        content = json.dumps(training_data, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()


class OllamaProvider(AIProvider):
    """Ollama local AI provider."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.base_url = config.get('base_url', 'http://localhost:11434')
        self.model_name = config.get('model_name', 'llama2')
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build system prompt based on user preferences and context."""
        return """You are a personal AI assistant integrated into a comprehensive dashboard system. 
        You have access to the user's calendar events, emails, news preferences, music tastes, and activity data.
        
        Your role is to:
        - Help analyze and prioritize tasks and information
        - Provide insights based on the user's patterns and preferences  
        - Suggest actions and follow-ups based on collected data
        - Learn from user feedback (likes/dislikes) to improve recommendations
        
        Always be concise, helpful, and personalized based on the available context."""
    
    async def chat(self, messages: List[Dict[str, str]], stream: bool = False) -> str:
        """Send chat messages to Ollama."""
        try:
            # Add system message if not present
            if not messages or messages[0].get('role') != 'system':
                messages.insert(0, {'role': 'system', 'content': self.system_prompt})
            
            async with aiohttp.ClientSession() as session:
                payload = {
                    'model': self.model_name,
                    'messages': messages,
                    'stream': stream
                }
                
                async with session.post(f"{self.base_url}/api/chat", json=payload) as response:
                    if response.status == 200:
                        if stream:
                            # Handle streaming response
                            content = ""
                            async for line in response.content:
                                if line:
                                    try:
                                        line_text = line.decode().strip()
                                        if line_text:
                                            data = json.loads(line_text)
                                            if 'message' in data and 'content' in data['message']:
                                                content += data['message']['content']
                                    except json.JSONDecodeError:
                                        continue
                            return content
                        else:
                            # Handle non-streaming response - get full JSON response
                            response_text = await response.text()
                            data = json.loads(response_text)
                            if 'message' in data and 'content' in data['message']:
                                return data['message']['content']
                            else:
                                return "No content received from Ollama"
                    else:
                        error_msg = f"Ollama API error: {response.status}"
                        logger.error(error_msg)
                        return f"Error: {error_msg}"
                        
        except Exception as e:
            logger.error(f"Error communicating with Ollama: {e}")
            return f"Error: Could not connect to Ollama server"
    
    async def train(self, training_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Train Ollama model with new data."""
        try:
            # For Ollama, we create a custom model with fine-tuning data
            modelfile_content = self._create_modelfile(training_data)
            
            async with aiohttp.ClientSession() as session:
                payload = {
                    'name': f"{self.model_name}_finetuned_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    'modelfile': modelfile_content
                }
                
                async with session.post(f"{self.base_url}/api/create", json=payload) as response:
                    if response.status == 200:
                        return {
                            'status': 'success',
                            'model_name': payload['name'],
                            'training_samples': len(training_data)
                        }
                    else:
                        return {
                            'status': 'error',
                            'error': f"Training failed: {response.status}"
                        }
                        
        except Exception as e:
            logger.error(f"Error training Ollama model: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _create_modelfile(self, training_data: List[Dict[str, Any]]) -> str:
        """Create Ollama modelfile with training data."""
        examples = []
        for item in training_data[:50]:  # Limit examples
            if item['data_type'].startswith('liked_'):
                examples.append(f"User liked: {item['content'][:200]}...")
        
        system_prompt = self.system_prompt + "\n\nUser preferences based on liked content:\n" + "\n".join(examples)
        
        return f"""FROM {self.model_name}
SYSTEM "{system_prompt}"
PARAMETER temperature 0.7
PARAMETER top_p 0.9"""
    
    async def health_check(self) -> bool:
        """Check Ollama server health."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.base_url}/api/tags") as response:
                    return response.status == 200
        except:
            return False


class OpenAIProvider(AIProvider):
    """OpenAI GPT provider."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.api_key = config.get('api_key')
        self.model_name = config.get('model_name', 'gpt-3.5-turbo')
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build system prompt based on user preferences."""
        return """You are a personal AI assistant with access to comprehensive dashboard data including 
        calendar events, emails, news preferences, music tastes, and user activity patterns.
        
        Use this context to provide personalized assistance, insights, and recommendations.
        Learn from user feedback to improve future responses."""
    
    async def chat(self, messages: List[Dict[str, str]], stream: bool = False) -> str:
        """Send chat messages to OpenAI."""
        try:
            # Add system message if not present
            if not messages or messages[0].get('role') != 'system':
                messages.insert(0, {'role': 'system', 'content': self.system_prompt})
            
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=1000,
                stream=stream
            )
            
            if stream:
                content = ""
                async for chunk in response:
                    if chunk.choices[0].delta.content:
                        content += chunk.choices[0].delta.content
                return content
            else:
                return response.choices[0].message.content
                
        except Exception as e:
            logger.error(f"Error with OpenAI API: {e}")
            return f"Error: OpenAI API error - {str(e)}"
    
    async def train(self, training_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Fine-tune OpenAI model."""
        try:
            # Prepare training data in OpenAI format
            training_file_data = self._prepare_training_data(training_data)
            
            # Upload training file
            training_file = await self.client.files.create(
                file=training_file_data,
                purpose="fine-tune"
            )
            
            # Create fine-tuning job
            fine_tune_job = await self.client.fine_tuning.jobs.create(
                training_file=training_file.id,
                model=self.model_name
            )
            
            return {
                'status': 'started',
                'job_id': fine_tune_job.id,
                'training_samples': len(training_data)
            }
            
        except Exception as e:
            logger.error(f"Error fine-tuning OpenAI model: {e}")
            return {
                'status': 'error',
                'error': str(e)
            }
    
    def _prepare_training_data(self, training_data: List[Dict[str, Any]]) -> str:
        """Prepare training data in OpenAI JSONL format."""
        training_examples = []
        
        for item in training_data:
            if item['data_type'].startswith('liked_'):
                # Create training example from liked content
                example = {
                    "messages": [
                        {"role": "system", "content": self.system_prompt},
                        {"role": "user", "content": f"What do you think about this {item['data_type']}?"},
                        {"role": "assistant", "content": f"Based on your preferences, this {item['data_type']} seems relevant because {item.get('context', 'you liked similar content')}. {item['content'][:100]}..."}
                    ]
                }
                training_examples.append(json.dumps(example))
        
        return "\n".join(training_examples)
    
    async def health_check(self) -> bool:
        """Check OpenAI API health."""
        try:
            await self.client.models.list()
            return True
        except:
            return False


class GeminiProvider(AIProvider):
    """Google Gemini provider."""
    
    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.api_key = config.get('api_key')
        self.model_name = config.get('model_name', 'gemini-pro')
        self.base_url = config.get('base_url', 'https://generativelanguage.googleapis.com/v1beta')
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build system prompt for Gemini."""
        return """You are a personal AI assistant integrated with a comprehensive dashboard system.
        You have context about the user's calendar, emails, preferences, and activity patterns.
        Provide helpful, personalized assistance based on this context."""
    
    async def chat(self, messages: List[Dict[str, str]], stream: bool = False) -> str:
        """Send chat messages to Gemini."""
        try:
            # Convert messages to Gemini format
            contents = self._convert_messages_to_gemini_format(messages)
            
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/models/{self.model_name}:generateContent"
                headers = {'Content-Type': 'application/json'}
                payload = {
                    'contents': contents,
                    'generationConfig': {
                        'temperature': 0.7,
                        'maxOutputTokens': 1000,
                    }
                }
                
                async with session.post(url, json=payload, headers=headers, params={'key': self.api_key}) as response:
                    if response.status == 200:
                        data = await response.json()
                        return data.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', '')
                    else:
                        error_msg = f"Gemini API error: {response.status}"
                        logger.error(error_msg)
                        return f"Error: {error_msg}"
                        
        except Exception as e:
            logger.error(f"Error with Gemini API: {e}")
            return f"Error: Gemini API error - {str(e)}"
    
    def _convert_messages_to_gemini_format(self, messages: List[Dict[str, str]]) -> List[Dict]:
        """Convert chat messages to Gemini format."""
        contents = []
        
        for msg in messages:
            if msg['role'] == 'system':
                # Gemini doesn't have system role, prepend to first user message
                continue
            elif msg['role'] == 'user':
                contents.append({
                    'role': 'user',
                    'parts': [{'text': msg['content']}]
                })
            elif msg['role'] == 'assistant':
                contents.append({
                    'role': 'model', 
                    'parts': [{'text': msg['content']}]
                })
        
        # Add system prompt to first user message if exists
        if contents and messages and messages[0]['role'] == 'system':
            if contents[0]['role'] == 'user':
                contents[0]['parts'][0]['text'] = f"{messages[0]['content']}\n\n{contents[0]['parts'][0]['text']}"
        
        return contents
    
    async def train(self, training_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Train Gemini model (placeholder - actual fine-tuning requires specialized setup)."""
        # Note: Gemini fine-tuning requires Google AI Studio or Vertex AI
        # This is a placeholder implementation
        return {
            'status': 'not_supported',
            'message': 'Gemini fine-tuning requires Google AI Studio setup'
        }
    
    async def health_check(self) -> bool:
        """Check Gemini API health."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.base_url}/models"
                async with session.get(url, params={'key': self.api_key}) as response:
                    return response.status == 200
        except:
            return False


class AIProviderManager:
    """Manages multiple AI providers."""
    
    def __init__(self):
        self.providers: Dict[str, AIProvider] = {}
        self.default_provider: Optional[str] = None
    
    def register_provider(self, provider: AIProvider, is_default: bool = False):
        """Register an AI provider."""
        self.providers[provider.name] = provider
        if is_default or not self.default_provider:
            self.default_provider = provider.name
    
    def get_provider(self, name: str = None) -> Optional[AIProvider]:
        """Get provider by name or default."""
        if name:
            return self.providers.get(name)
        return self.providers.get(self.default_provider) if self.default_provider else None
    
    def list_providers(self) -> List[Dict[str, Any]]:
        """List all providers with their status."""
        return [
            {
                'name': name,
                'type': provider.provider_type,
                'is_default': name == self.default_provider
            }
            for name, provider in self.providers.items()
        ]
    
    async def health_check_all(self) -> Dict[str, bool]:
        """Check health of all providers."""
        results = {}
        for name, provider in self.providers.items():
            try:
                results[name] = await provider.health_check()
            except:
                results[name] = False
        return results


# Global provider manager instance
ai_manager = AIProviderManager()


def create_provider(provider_type: str, name: str, config: Dict[str, Any]) -> AIProvider:
    """Factory function to create AI providers."""
    providers = {
        'ollama': OllamaProvider,
        'openai': OpenAIProvider,
        'gemini': GeminiProvider
    }
    
    provider_class = providers.get(provider_type.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider type: {provider_type}")
    
    return provider_class(name, config)
