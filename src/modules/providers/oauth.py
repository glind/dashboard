"""
Microsoft OAuth callback handler
"""

import logging
import sys
from pathlib import Path
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import RedirectResponse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from providers import MicrosoftProvider
from config.settings import Settings
from database import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/microsoft", tags=["auth"])


@router.get("/callback")
async def microsoft_oauth_callback(request: Request):
    """Handle Microsoft OAuth callback."""
    try:
        # Get authorization code and state from query params
        code = request.query_params.get('code')
        state = request.query_params.get('state')  # This is the provider_id
        error = request.query_params.get('error')
        
        if error:
            logger.error(f"Microsoft OAuth error: {error}")
            return RedirectResponse(
                url=f"/?error=microsoft_auth_failed&details={error}",
                status_code=302
            )
        
        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing code or state parameter")
        
        provider_id = state
        
        # Initialize provider and handle callback
        db = DatabaseManager()
        settings = Settings()
        
        provider = MicrosoftProvider(provider_id, settings, db)
        success = await provider.handle_callback(code, state)
        
        if not success:
            return RedirectResponse(
                url="/?error=microsoft_auth_failed",
                status_code=302
            )
        
        # Update last auth date
        from datetime import datetime
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE provider_configs 
                SET last_auth_date = ? 
                WHERE provider_id = ?
            """, (datetime.now().isoformat(), provider_id))
            conn.commit()
        
        logger.info(f"✅ Microsoft OAuth completed for {provider_id}")
        
        # Redirect back to dashboard with success message
        return RedirectResponse(
            url="/?success=microsoft_connected",
            status_code=302
        )
        
    except Exception as e:
        logger.error(f"Error in Microsoft OAuth callback: {e}")
        return RedirectResponse(
            url=f"/?error=microsoft_auth_failed&details={str(e)}",
            status_code=302
        )
