"""
Communications Module API Endpoints
"""

import logging
import sys
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from typing import Optional
from pydantic import BaseModel

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parents[3]))

from .collector import CommsCollector
from .processor import CommsProcessor
from .auth import CommsAuthManager, OAuthFlowManager, SlackOAuthHelper, DiscordOAuthHelper, LinkedInOAuthHelper
from src.database import DatabaseManager, get_credentials

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/modules/comms", tags=["comms"])

# Initialize components
db = DatabaseManager()
auth_manager = CommsAuthManager(db)
oauth_manager = OAuthFlowManager()
collector = CommsCollector(auth_manager=auth_manager)
processor = CommsProcessor(db=db)


def get_platform_oauth_config(platform: str):
    """Get OAuth configuration for a platform."""
    try:
        creds = get_credentials(platform)
        if creds and creds.get('client_id'):
            return {
                'client_id': creds['client_id'],
                'client_secret': creds['client_secret'],
                'redirect_uri': f"http://localhost:8008/api/modules/comms/auth/{platform}/callback"
            }
    except Exception as e:
        logger.warning(f"Could not load OAuth config for {platform}: {e}")
    return None


class MessageAnalysisRequest(BaseModel):
    """Request model for single message analysis."""
    message_id: str
    platform: str
    from_user: str
    text: str
    channel: Optional[str] = None


class ManualTokenRequest(BaseModel):
    """Request body for manual token entry."""
    access_token: str
    refresh_token: Optional[str] = None


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "module": "comms",
        "platforms": ["linkedin", "slack", "discord"]
    }


# ============ OAuth Endpoints ============

@router.get("/auth/status")
async def get_auth_status():
    """Get authentication status for all platforms."""
    status = {}
    for platform in ['slack', 'discord', 'linkedin']:
        creds = auth_manager.get_credentials(platform)
        if creds:
            status[platform] = {
                'connected': True,
                'user': creds.get('user_info', {}).get('name', 'Connected'),
                'expires_at': creds.get('expires_at')
            }
        else:
            status[platform] = {'connected': False}
    return status


@router.get("/auth/{platform}/connect")
async def connect_platform(platform: str):
    """Initiate OAuth flow for a platform."""
    if platform not in ['slack', 'discord', 'linkedin']:
        raise HTTPException(status_code=400, detail="Invalid platform")
    
    # Get OAuth configuration
    config = get_platform_oauth_config(platform)
    if not config:
        raise HTTPException(
            status_code=500, 
            detail=f"{platform.capitalize()} OAuth not configured. Please add client_id and client_secret to credentials.yaml"
        )
    
    # Generate state token for CSRF protection
    state = oauth_manager.generate_state_token(platform)
    
    # Get OAuth URL from appropriate helper
    if platform == 'slack':
        oauth_url = SlackOAuthHelper.get_authorization_url(
            config['client_id'],
            config['redirect_uri'],
            state
        )
    elif platform == 'discord':
        oauth_url = DiscordOAuthHelper.get_authorization_url(
            config['client_id'],
            config['redirect_uri'],
            state
        )
    elif platform == 'linkedin':
        oauth_url = LinkedInOAuthHelper.get_authorization_url(
            config['client_id'],
            config['redirect_uri'],
            state
        )
    
    return RedirectResponse(url=oauth_url)


@router.get("/auth/slack/callback")
async def slack_callback(code: str, state: str):
    """Handle Slack OAuth callback."""
    if not oauth_manager.verify_state_token(state, 'slack'):
        raise HTTPException(status_code=400, detail="Invalid state token")
    
    config = get_platform_oauth_config('slack')
    if not config:
        raise HTTPException(status_code=500, detail="Slack OAuth not configured")
    
    try:
        token_data = await SlackOAuthHelper.exchange_code_for_token(
            code,
            config['client_id'],
            config['client_secret'],
            config['redirect_uri']
        )
        user_info = await SlackOAuthHelper.get_user_info(token_data['access_token'])
        
        auth_manager.save_credentials(
            platform='slack',
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            expires_in=token_data.get('expires_in'),
            user_info=user_info
        )
        
        return RedirectResponse(url="/?connected=slack")
    except Exception as e:
        logger.error(f"Slack OAuth error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/discord/callback")
async def discord_callback(code: str, state: str):
    """Handle Discord OAuth callback."""
    if not oauth_manager.verify_state_token(state, 'discord'):
        raise HTTPException(status_code=400, detail="Invalid state token")
    
    config = get_platform_oauth_config('discord')
    if not config:
        raise HTTPException(status_code=500, detail="Discord OAuth not configured")
    
    try:
        token_data = await DiscordOAuthHelper.exchange_code_for_token(
            code,
            config['client_id'],
            config['client_secret'],
            config['redirect_uri']
        )
        user_info = await DiscordOAuthHelper.get_user_info(token_data['access_token'])
        
        auth_manager.save_credentials(
            platform='discord',
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            expires_in=token_data.get('expires_in', 604800),  # Discord default 7 days
            user_info=user_info
        )
        
        return RedirectResponse(url="/?connected=discord")
    except Exception as e:
        logger.error(f"Discord OAuth error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/auth/linkedin/callback")
async def linkedin_callback(code: str, state: str):
    """Handle LinkedIn OAuth callback."""
    if not oauth_manager.verify_state_token(state, 'linkedin'):
        raise HTTPException(status_code=400, detail="Invalid state token")
    
    config = get_platform_oauth_config('linkedin')
    if not config:
        raise HTTPException(status_code=500, detail="LinkedIn OAuth not configured")
    
    try:
        token_data = await LinkedInOAuthHelper.exchange_code_for_token(
            code,
            config['client_id'],
            config['client_secret'],
            config['redirect_uri']
        )
        user_info = await LinkedInOAuthHelper.get_user_info(token_data['access_token'])
        
        auth_manager.save_credentials(
            platform='linkedin',
            access_token=token_data['access_token'],
            refresh_token=token_data.get('refresh_token'),
            expires_in=token_data.get('expires_in', 5184000),  # LinkedIn default 60 days
            user_info=user_info
        )
        
        return RedirectResponse(url="/?connected=linkedin")
    except Exception as e:
        logger.error(f"LinkedIn OAuth error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/auth/{platform}/disconnect")
async def disconnect_platform(platform: str):
    """Disconnect a platform and delete stored credentials."""
    if platform not in ['slack', 'discord', 'linkedin']:
        raise HTTPException(status_code=400, detail="Invalid platform")
    
    auth_manager.delete_credentials(platform)
    return {"status": "disconnected", "platform": platform}


@router.post("/auth/{platform}/manual")
async def manual_token_entry(platform: str, token_data: ManualTokenRequest):
    """Manually enter API token for a platform."""
    if platform not in ['slack', 'discord', 'linkedin']:
        raise HTTPException(status_code=400, detail="Invalid platform")
    
    # Save manually entered token
    auth_manager.save_credentials(
        platform=platform,
        access_token=token_data.access_token,
        refresh_token=token_data.refresh_token,
        expires_in=None,  # Manual tokens don't expire
        user_info={'name': 'Manual Entry', 'manual': True}
    )
    
    return {"status": "connected", "platform": platform, "method": "manual"}


# ============ Data Collection Endpoints ============

@router.get("/data")
async def get_communications(
    hours_back: int = Query(default=24, ge=1, le=168)
):
    """
    Get all communications from LinkedIn, Slack, and Discord.
    
    Args:
        hours_back: How many hours back to fetch (default 24, max 168/1 week)
    """
    try:
        collector = CommsCollector()
        processor = CommsProcessor()
        
        # Collect messages
        messages = await collector.collect_all(hours_back)
        
        # Process and prioritize
        processed = await processor.process_messages(messages)
        
        return {
            "success": True,
            "data": processed,
            "raw_messages": messages
        }
        
    except Exception as e:
        logger.error(f"Error fetching communications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze")
async def analyze_messages(
    hours_back: int = Query(default=24, ge=1, le=168)
):
    """
    Collect and analyze communications with AI prioritization.
    
    Returns prioritized messages with suggested actions.
    """
    try:
        collector = CommsCollector()
        processor = CommsProcessor()
        
        # Collect messages
        messages = await collector.collect_all(hours_back)
        
        # Process with AI
        analysis = await processor.process_messages(messages)
        
        return {
            "success": True,
            "analysis": analysis
        }
        
    except Exception as e:
        logger.error(f"Error analyzing communications: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze-single")
async def analyze_single_message(request: MessageAnalysisRequest):
    """
    Analyze a single message for detailed insights.
    """
    try:
        processor = CommsProcessor()
        
        message_data = {
            'id': request.message_id,
            'platform': request.platform,
            'from_user': request.from_user,
            'text': request.text,
            'channel': request.channel
        }
        
        analysis = await processor.analyze_single_message(message_data)
        
        return {
            "success": True,
            "analysis": analysis
        }
        
    except Exception as e:
        logger.error(f"Error analyzing single message: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/platforms/{platform}")
async def get_platform_messages(
    platform: str,
    hours_back: int = Query(default=24, ge=1, le=168)
):
    """
    Get messages from a specific platform only.
    
    Args:
        platform: One of 'linkedin', 'slack', 'discord'
        hours_back: How many hours back to fetch
    """
    if platform not in ['linkedin', 'slack', 'discord']:
        raise HTTPException(
            status_code=400,
            detail="Platform must be one of: linkedin, slack, discord"
        )
    
    try:
        collector = CommsCollector()
        
        if platform == 'linkedin':
            messages = await collector.collect_linkedin(hours_back)
        elif platform == 'slack':
            messages = await collector.collect_slack(hours_back)
        else:  # discord
            messages = await collector.collect_discord(hours_back)
        
        return {
            "success": True,
            "platform": platform,
            "count": len(messages),
            "messages": messages
        }
        
    except Exception as e:
        logger.error(f"Error fetching {platform} messages: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
