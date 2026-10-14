"""
Music News Module - API Endpoints
Provides REST API for music news data and AI analysis.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Create router for this module
router = APIRouter(prefix="/api/modules/music-news", tags=["custom_modules", "music"])


class AnalysisRequest(BaseModel):
    """Request model for AI analysis."""
    data: list = []
    prompt: str = None


@router.get("/data")
async def get_music_news() -> Dict[str, Any]:
    """
    Get latest music industry news.
    
    Returns:
        Dict with music news articles and metadata
    """
    try:
        from .collector import collect_music_news
        from database import get_credentials
        
        # Get module configuration
        config = get_credentials('music_news') or {}
        
        # Collect news
        result = await collect_music_news(config)
        
        return result
        
    except Exception as e:
        logger.error(f"Error in music news endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_music_news(request: AnalysisRequest) -> Dict[str, Any]:
    """
    Analyze music news with AI.
    
    Args:
        request: Analysis request with data and optional custom prompt
        
    Returns:
        AI analysis results with insights and recommendations
    """
    try:
        from .processor import process_music_news
        from database import get_database, get_settings
        
        db = get_database()
        settings = get_settings()
        
        # Process with AI
        result = await process_music_news(
            data=request.data,
            db=db,
            settings=settings,
            analysis_prompt=request.prompt
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing music news: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for music news module."""
    return {
        "status": "healthy",
        "module": "music_news",
        "version": "1.0.0"
    }
