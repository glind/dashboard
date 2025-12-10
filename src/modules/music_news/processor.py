"""
Music News Module - Processor
Handles data processing and AI analysis for music news.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


async def process_music_news(
    data: List[Dict[str, Any]], 
    db, 
    settings,
    analysis_prompt: str = None
) -> Dict[str, Any]:
    """
    Process music news data with optional AI analysis.
    
    Args:
        data: Raw music news articles
        db: Database manager instance
        settings: Application settings
        analysis_prompt: Optional custom prompt for AI analysis
        
    Returns:
        Processed results with AI insights
    """
    try:
        from services.ai_service import get_ai_service
        
        # Get shared AI service
        ai_service = get_ai_service(db, settings)
        
        if not analysis_prompt:
            # Default analysis prompt for music news
            analysis_prompt = f"""Analyze these music industry news articles and provide insights:

{chr(10).join([f"- {article.get('title')} ({article.get('source')})" for article in data[:10]])}

Please provide:
1. Key trends in the music industry
2. Important announcements or changes
3. Opportunities or threats for independent labels
4. Recommendations for follow-up actions"""
        
        # Use AI to analyze
        result = await ai_service.chat(
            message=analysis_prompt,
            include_context=False  # Don't need full dashboard context for this
        )
        
        return {
            'success': result.get('success', False),
            'articles': data,
            'count': len(data),
            'ai_analysis': result.get('response'),
            'provider': result.get('provider'),
            'timestamp': result.get('timestamp')
        }
        
    except Exception as e:
        logger.error(f"Error processing music news: {e}")
        return {
            'success': False,
            'error': str(e),
            'articles': data,
            'count': len(data)
        }
