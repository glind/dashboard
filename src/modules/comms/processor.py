"""
Communications Processor
Processes and prioritizes messages using AI
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parents[3]))

from src.services.ai_service import get_ai_service

logger = logging.getLogger(__name__)


class CommsProcessor:
    """Processes and prioritizes communications using AI."""
    
    def __init__(self, db=None):
        self.ai_service = get_ai_service(db)
    
    async def process_messages(
        self,
        messages: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Process and prioritize all messages."""
        logger.info("Processing communications with AI prioritization")
        
        # Flatten all messages
        all_messages = []
        for platform in ['linkedin', 'slack', 'discord']:
            for msg in messages.get(platform, []):
                all_messages.append(msg)
        
        if not all_messages:
            return {
                'total_messages': 0,
                'by_platform': {'linkedin': 0, 'slack': 0, 'discord': 0},
                'priority_messages': [],
                'by_priority': {'urgent': 0, 'high': 0, 'medium': 0, 'low': 0},
                'suggested_actions': []
            }
        
        # Sort by timestamp (newest first)
        all_messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Get AI analysis for prioritization
        prioritized = await self._prioritize_with_ai(all_messages)
        
        # Calculate statistics
        stats = self._calculate_stats(prioritized)
        
        # Generate suggested actions
        actions = await self._generate_actions(prioritized)
        
        return {
            'total_messages': len(all_messages),
            'by_platform': {
                'linkedin': len(messages.get('linkedin', [])),
                'slack': len(messages.get('slack', [])),
                'discord': len(messages.get('discord', []))
            },
            'priority_messages': prioritized,
            'by_priority': stats,
            'suggested_actions': actions,
            'processed_at': datetime.now().isoformat()
        }
    
    async def _prioritize_with_ai(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Use AI to prioritize messages."""
        
        # Prepare message summaries for AI
        message_summaries = []
        for idx, msg in enumerate(messages):
            summary = (
                f"{idx}. [{msg['platform'].upper()}] "
                f"From: {msg.get('from_user', 'Unknown')} "
                f"| Channel: {msg.get('channel', msg.get('type', 'N/A'))} "
                f"| {msg.get('text', msg.get('preview', ''))[:200]}"
            )
            message_summaries.append(summary)
        
        # Build AI prompt
        prompt = f"""Analyze these communication messages and assign priority levels (urgent, high, medium, low).

Consider:
- Time sensitivity and deadlines
- Sender importance (leadership, clients, key stakeholders)
- Action requirements (questions, requests, decisions needed)
- Business impact
- Channel context (DMs often more urgent than channel mentions)

Messages:
{chr(10).join(message_summaries)}

Respond in JSON format:
{{
  "priorities": [
    {{"index": 0, "priority": "urgent|high|medium|low", "reason": "brief explanation", "action_needed": "what needs to be done"}},
    ...
  ]
}}

Focus on identifying truly urgent items that need immediate attention."""
        
        try:
            # Get AI analysis
            response = await self.ai_service.generate_completion(
                prompt,
                system_message="You are a communications prioritization assistant. Analyze messages and assign appropriate priority levels based on urgency and importance."
            )
            
            # Parse AI response
            import json
            try:
                # Try to extract JSON from response
                json_start = response.find('{')
                json_end = response.rfind('}') + 1
                if json_start >= 0 and json_end > json_start:
                    ai_data = json.loads(response[json_start:json_end])
                    priorities = ai_data.get('priorities', [])
                else:
                    logger.warning("Could not find JSON in AI response")
                    priorities = []
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response: {e}")
                priorities = []
            
            # Apply AI priorities to messages
            for priority_info in priorities:
                idx = priority_info.get('index')
                if idx is not None and idx < len(messages):
                    messages[idx]['priority'] = priority_info.get('priority', 'medium')
                    messages[idx]['priority_reason'] = priority_info.get('reason', '')
                    messages[idx]['action_needed'] = priority_info.get('action_needed', '')
            
            # Set default priority for messages without AI analysis
            for msg in messages:
                if 'priority' not in msg:
                    msg['priority'] = 'medium'
                    msg['priority_reason'] = 'Not analyzed'
                    msg['action_needed'] = ''
            
        except Exception as e:
            logger.error(f"Error in AI prioritization: {e}")
            # Fallback: basic prioritization
            for msg in messages:
                msg['priority'] = self._basic_priority(msg)
                msg['priority_reason'] = 'Basic rule-based priority'
                msg['action_needed'] = ''
        
        # Sort by priority (urgent > high > medium > low) then by timestamp
        priority_order = {'urgent': 0, 'high': 1, 'medium': 2, 'low': 3}
        messages.sort(
            key=lambda x: (
                priority_order.get(x.get('priority', 'medium'), 2),
                x.get('timestamp', '')
            ),
            reverse=True
        )
        
        return messages
    
    def _basic_priority(self, message: Dict[str, Any]) -> str:
        """Basic rule-based priority as fallback."""
        # DMs are higher priority
        if message.get('type') in ['dm', 'message']:
            return 'high'
        
        # Recent mentions in last 6 hours
        try:
            msg_time = datetime.fromisoformat(message.get('timestamp', ''))
            hours_ago = (datetime.now() - msg_time).total_seconds() / 3600
            if hours_ago < 6:
                return 'high'
        except:
            pass
        
        return 'medium'
    
    def _calculate_stats(self, messages: List[Dict[str, Any]]) -> Dict[str, int]:
        """Calculate priority statistics."""
        stats = {'urgent': 0, 'high': 0, 'medium': 0, 'low': 0}
        
        for msg in messages:
            priority = msg.get('priority', 'medium')
            stats[priority] = stats.get(priority, 0) + 1
        
        return stats
    
    async def _generate_actions(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate suggested actions for top priority messages."""
        
        # Get top 5 urgent/high priority messages
        top_messages = [
            msg for msg in messages
            if msg.get('priority') in ['urgent', 'high']
        ][:5]
        
        if not top_messages:
            return []
        
        actions = []
        for msg in top_messages:
            action = {
                'message_id': msg.get('id'),
                'platform': msg.get('platform'),
                'from_user': msg.get('from_user'),
                'priority': msg.get('priority'),
                'suggested_action': msg.get('action_needed', 'Review and respond'),
                'link': msg.get('link'),
                'preview': msg.get('text', msg.get('preview', ''))[:150]
            }
            actions.append(action)
        
        return actions
    
    async def analyze_single_message(
        self,
        message: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze a single message for detailed insights."""
        
        prompt = f"""Analyze this communication message and provide insights:

Platform: {message.get('platform')}
From: {message.get('from_user')}
Channel: {message.get('channel', 'Direct Message')}
Content: {message.get('text', message.get('preview', ''))}

Provide:
1. Sentiment analysis (positive/neutral/negative)
2. Key topics mentioned
3. Questions or action items
4. Suggested response approach
5. Urgency assessment

Respond in JSON format."""
        
        try:
            response = await self.ai_service.generate_completion(
                prompt,
                system_message="You are a communications analysis assistant."
            )
            
            return {
                'message_id': message.get('id'),
                'analysis': response,
                'analyzed_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error analyzing message: {e}")
            return {
                'message_id': message.get('id'),
                'error': str(e)
            }
