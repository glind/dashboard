"""
Vanity Alerts Module - Processor
Handles sentiment analysis and AI insights for vanity alerts.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


async def process_vanity_alerts(
    data: List[Dict[str, Any]], 
    db, 
    settings,
    analysis_prompt: str = None
) -> Dict[str, Any]:
    """
    Process vanity alerts with AI sentiment analysis and insights.
    
    Args:
        data: Raw vanity alert mentions
        db: Database manager instance
        settings: Application settings
        analysis_prompt: Optional custom prompt for AI analysis
        
    Returns:
        Processed results with sentiment analysis and insights
    """
    try:
        from services.ai_service import get_ai_service
        
        # Get shared AI service
        ai_service = get_ai_service(db, settings)
        
        if not analysis_prompt:
            # Default analysis prompt for vanity alerts
            mentions_summary = "\n".join([
                f"- {alert.get('title')} ({alert.get('source')}) - {alert.get('snippet', '')[:100]}"
                for alert in data[:15]
            ])
            
            analysis_prompt = f"""Analyze these mentions and alerts:

{mentions_summary}

Please provide:
1. Overall sentiment analysis (positive, neutral, negative)
2. Key themes or topics being discussed
3. Any urgent items requiring attention
4. Recommendations for engagement or response"""
        
        # Use AI to analyze
        result = await ai_service.chat(
            message=analysis_prompt,
            include_context=False
        )
        
        # Calculate sentiment distribution
        sentiment_counts = {
            'positive': len([a for a in data if a.get('sentiment') == 'positive']),
            'neutral': len([a for a in data if a.get('sentiment') == 'neutral']),
            'negative': len([a for a in data if a.get('sentiment') == 'negative'])
        }
        
        return {
            'success': result.get('success', False),
            'alerts': data,
            'count': len(data),
            'sentiment_distribution': sentiment_counts,
            'ai_analysis': result.get('response'),
            'provider': result.get('provider'),
            'timestamp': result.get('timestamp')
        }
        
    except Exception as e:
        logger.error(f"Error processing vanity alerts: {e}")
        return {
            'success': False,
            'error': str(e),
            'alerts': data,
            'count': len(data)
        }


async def analyze_single_alert(
    alert: Dict[str, Any],
    db,
    settings
) -> Dict[str, Any]:
    """
    Analyze a single alert for sentiment and action items.
    
    Args:
        alert: Single vanity alert
        db: Database manager
        settings: Application settings
        
    Returns:
        Analysis of the alert
    """
    try:
        from services.ai_service import get_ai_service
        
        ai_service = get_ai_service(db, settings)
        
        prompt = f"""Analyze this mention:

Title: {alert.get('title')}
Source: {alert.get('source')}
Content: {alert.get('snippet', 'No snippet available')}

Provide:
1. Sentiment (positive/neutral/negative)
2. Key points
3. Should this require immediate attention? (yes/no)
4. Recommended response or action (if any)"""
        
        result = await ai_service.chat(
            message=prompt,
            include_context=False
        )
        
        return {
            'success': result.get('success', False),
            'alert': alert,
            'analysis': result.get('response'),
            'provider': result.get('provider')
        }
        
    except Exception as e:
        logger.error(f"Error analyzing single alert: {e}")
        return {
            'success': False,
            'error': str(e),
            'alert': alert
        }
