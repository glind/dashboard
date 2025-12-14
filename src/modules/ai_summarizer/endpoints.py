"""
AI Summarizer API Endpoints
Summarizes items and extracts tasks using AI
"""

import logging
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime

from database import DatabaseManager
from config.settings import Settings
from pathlib import Path
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processors.task_manager import TaskManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai/summarize", tags=["ai-summarizer"])

# Initialize
db = DatabaseManager()
task_manager = TaskManager()
config_path = Path(__file__).parent.parent.parent / "config" / "config.yaml"
app_settings = Settings.from_yaml(str(config_path)) if config_path.exists() else Settings()


class SummarizeRequest(BaseModel):
    """Request to summarize an item."""
    item_type: str  # 'note', 'email', 'calendar'
    item_id: str
    content: str
    title: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = {}


async def get_ai_summary_and_tasks(content: str, title: str = "", item_type: str = "item") -> Dict[str, Any]:
    """
    Use AI to summarize content and extract tasks.
    
    Args:
        content: The content to summarize
        title: Optional title for context
        item_type: Type of item (note, email, calendar)
    
    Returns:
        Dictionary with summary and extracted tasks
    """
    try:
        # Use Ollama as default AI provider
        ai_provider = "ollama"
        
        prompt = f"""Analyze this {item_type} and provide:
1. A concise summary (2-3 sentences)
2. A list of actionable tasks with full context and details

{item_type.upper()}: {title}

CONTENT:
{content[:2000]}  

IMPORTANT: For each task, provide a COMPLETE, ACTIONABLE description with:
- What needs to be done
- Relevant context from the source (who, what, when, why)
- Any deadlines or urgency indicators
- Related details that make the task clear

BAD EXAMPLE: "Send email"
GOOD EXAMPLE: "Send project proposal to Alice by Friday EOD with updated pricing for Q1 features discussed in meeting"

Respond in this exact format:
SUMMARY: [your summary here]

TASKS:
- [Complete task description with full context from content]
- [Another complete task description with all relevant details]
- [Or "None" if no tasks found]
"""
        
        summary = ""
        tasks = []
        
        if ai_provider == 'ollama':
            try:
                import requests
                ollama_url = f"http://{app_settings.ollama.host}:{app_settings.ollama.port}/api/generate"
                logger.info(f"Calling Ollama at {ollama_url} with model {app_settings.ollama.model}")
                
                response = requests.post(
                    ollama_url,
                    json={
                        'model': app_settings.ollama.model,
                        'prompt': prompt,
                        'stream': False,
                        'options': {
                            'temperature': 0.3,
                            'num_predict': 500
                        }
                    },
                    timeout=30
                )
                
                if response.status_code == 200:
                    result = response.json()
                    ai_response = result.get('response', '')
                    
                    logger.info(f"✅ Ollama responded with {len(ai_response)} chars")
                    logger.info(f"📄 Response preview: {ai_response[:500]}")
                    
                    # Parse response - try structured format first
                    if 'SUMMARY:' in ai_response and 'TASKS:' in ai_response:
                        summary_part = ai_response.split('SUMMARY:')[1].split('TASKS:')[0].strip()
                        summary = summary_part
                        
                        tasks_part = ai_response.split('TASKS:')[1].strip()
                        if tasks_part.lower() != 'none' and 'none' not in tasks_part.lower():
                            for line in tasks_part.split('\n'):
                                line = line.strip()
                                if line.startswith('-') or line.startswith('•') or line.startswith('*'):
                                    task_text = line.lstrip('-•* ').strip()
                                    if len(task_text) > 10:  # Minimum task length
                                        tasks.append(task_text)
                    else:
                        # Fallback: use entire response as summary
                        summary = ai_response.strip()
                        logger.warning(f"AI response not in expected format, using raw response")
                else:
                    logger.error(f"Ollama API error: {response.status_code}")
                    
            except Exception as e:
                logger.error(f"Error calling Ollama: {e}")
                # Fallback: basic extraction without AI
                summary = f"{title}: " + content[:200] + "..."
                
                # Try to extract obvious action items
                import re
                for line in content.split('\n'):
                    # Look for common task patterns
                    if re.search(r'action item|todo|task|need to|must|should|follow up', line, re.IGNORECASE):
                        task_match = re.sub(r'^[-*•\d.)]\s*', '', line.strip())
                        if len(task_match) > 15:
                            tasks.append(task_match[:200])
                
        elif ai_provider == 'openai':
            try:
                from openai import OpenAI
                client = OpenAI(api_key=app_settings.openai.api_key)
                
                response = client.chat.completions.create(
                    model=app_settings.openai.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that summarizes content and extracts actionable tasks."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=500
                )
                
                ai_response = response.choices[0].message.content
                
                # Parse response
                if 'SUMMARY:' in ai_response:
                    summary_part = ai_response.split('SUMMARY:')[1].split('TASKS:')[0].strip()
                    summary = summary_part
                
                if 'TASKS:' in ai_response:
                    tasks_part = ai_response.split('TASKS:')[1].strip()
                    if tasks_part.lower() != 'none':
                        for line in tasks_part.split('\n'):
                            line = line.strip()
                            if line.startswith('-') or line.startswith('•'):
                                task_text = line[1:].strip()
                                if len(task_text) > 10:
                                    tasks.append(task_text)
                                    
            except Exception as e:
                logger.error(f"Error calling OpenAI: {e}")
        
        # Fallback if no AI response
        if not summary:
            summary = f"Summary of {title}: " + content[:200] + "..."
        
        return {
            'summary': summary,
            'tasks': tasks
        }
        
    except Exception as e:
        logger.error(f"Error in AI summary: {e}", exc_info=True)
        return {
            'summary': f"Error generating summary: {str(e)}",
            'tasks': []
        }


@router.post("/item")
async def summarize_item(request: SummarizeRequest):
    """
    Summarize an item and extract tasks using AI.
    
    Returns:
        Dictionary with summary, tasks created, and task IDs
    """
    try:
        start_time = datetime.now()
        
        # Get AI summary and tasks
        result = await get_ai_summary_and_tasks(
            content=request.content,
            title=request.title or "Untitled",
            item_type=request.item_type
        )
        
        summary = result['summary']
        extracted_tasks = result['tasks']
        
        # Create tasks as suggested todos (require user approval)
        task_ids = []
        for task_text in extracted_tasks:
            try:
                # Create as suggested todo with full context
                todo_data = {
                    'title': task_text[:200],  # Limit title length
                    'description': task_text,  # Full task description with context
                    'context': f"{request.item_type}: {request.title}",
                    'source': request.item_type,
                    'source_id': request.item_id,
                    'source_title': request.title,
                    'source_url': request.metadata.get('url', ''),
                    'source_content': request.content[:5000],  # Store first 5000 chars for popup
                    'priority': 'medium',
                    'due_date': None
                }
                
                suggestion_id = db.add_suggested_todo(todo_data)
                if suggestion_id:
                    task_ids.append(suggestion_id)
                    logger.info(f"Created suggested task from {request.item_type}: {task_text[:50]}...")
                    
            except Exception as e:
                logger.error(f"Error creating suggested task: {e}")
                continue
        
        # Store summary in database (add to metadata)
        try:
            # For now, we'll return it - later we can add a summaries table
            pass
        except Exception as e:
            logger.error(f"Error storing summary: {e}")
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        return {
            'success': True,
            'summary': summary,
            'tasks_extracted': len(extracted_tasks),
            'tasks_created': len(task_ids),
            'task_ids': task_ids,
            'duration_seconds': duration
        }
        
    except Exception as e:
        logger.error(f"Error in summarize_item: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{item_type}/{item_id}")
async def get_summary_history(item_type: str, item_id: str):
    """Get previous summaries for an item."""
    try:
        # For now, return empty - we can add a summaries table later
        return {
            'success': True,
            'summaries': [],
            'task_count': 0
        }
    except Exception as e:
        logger.error(f"Error getting summary history: {e}")
        raise HTTPException(status_code=500, detail=str(e))
