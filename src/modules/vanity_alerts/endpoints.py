"""
Vanity Alerts Module - API Endpoints
Provides REST API for vanity alerts and AI analysis.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

# Create router for this module
router = APIRouter(prefix="/api/modules/vanity-alerts", tags=["custom_modules", "vanity"])


class AnalysisRequest(BaseModel):
    """Request model for AI analysis."""
    data: list = []
    prompt: str = None


class SingleAlertRequest(BaseModel):
    """Request model for single alert analysis."""
    alert: dict


@router.get("/data")
async def get_vanity_alerts() -> Dict[str, Any]:
    """
    Get recent vanity alert mentions.
    
    Returns:
        Dict with vanity alerts and metadata
    """
    try:
        from .collector import collect_vanity_alerts
        from database import get_credentials
        
        # Get module configuration
        config = get_credentials('vanity_alerts') or {}
        
        # Collect alerts
        result = await collect_vanity_alerts(config)
        
        return result
        
    except Exception as e:
        logger.error(f"Error in vanity alerts endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_vanity_alerts(request: AnalysisRequest) -> Dict[str, Any]:
    """
    Analyze vanity alerts with AI for sentiment and insights.
    
    Args:
        request: Analysis request with data and optional custom prompt
        
    Returns:
        AI analysis results with sentiment and recommendations
    """
    try:
        from .processor import process_vanity_alerts
        from database import get_database, get_settings
        
        db = get_database()
        settings = get_settings()
        
        # Process with AI
        result = await process_vanity_alerts(
            data=request.data,
            db=db,
            settings=settings,
            analysis_prompt=request.prompt
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing vanity alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-single")
async def analyze_single_alert(request: SingleAlertRequest) -> Dict[str, Any]:
    """
    Analyze a single vanity alert.
    
    Args:
        request: Request with single alert data
        
    Returns:
        AI analysis of the alert
    """
    try:
        from .processor import analyze_single_alert
        from database import get_database, get_settings
        
        db = get_database()
        settings = get_settings()
        
        result = await analyze_single_alert(
            alert=request.alert,
            db=db,
            settings=settings
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error analyzing single alert: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Health check endpoint for vanity alerts module."""
    return {
        "status": "healthy",
        "module": "vanity_alerts",
        "version": "1.0.0"
    }
