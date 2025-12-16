"""
Provider Management API Endpoints
Handles user-facing OAuth flows and provider configuration
"""

import logging
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, HTTPException, Query, Depends
from pydantic import BaseModel
from datetime import datetime

# Add project root to path to import providers
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from providers import ProviderManager, GoogleProvider, MicrosoftProvider, ProtonProvider
from config.settings import Settings
from database import DatabaseManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/providers", tags=["providers"])


class ProviderConfig(BaseModel):
    """Provider configuration model."""
    provider_type: str  # "google", "microsoft", "proton"
    provider_name: str  # User-friendly name like "Work Email", "Personal Gmail"
    config: Dict[str, Any] = {}


class ProtonCredentials(BaseModel):
    """Proton Bridge credentials."""
    username: str
    password: str


@router.get("/list")
async def list_providers():
    """List all configured providers with their status."""
    try:
        db = DatabaseManager()
        settings = Settings()
        manager = ProviderManager(db)
        
        # Get all provider configs from database
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT provider_id, provider_name, enabled, capabilities, last_auth_date
                FROM provider_configs
                ORDER BY created_at
            """)
            rows = cursor.fetchall()
        
        # Also check for legacy Google credentials (not in provider_configs table yet)
        has_legacy_google = False
        google_token_path = Path(__file__).parent.parent.parent.parent / "tokens" / "google_credentials.json"
        if google_token_path.exists():
            has_legacy_google = True
            logger.info(f"Found legacy Google credentials at {google_token_path}")
        
        providers = []
        for row in rows:
            provider_id, provider_type, enabled, capabilities_json, last_auth = row
            
            import json
            capabilities = json.loads(capabilities_json) if capabilities_json else []
            
            # Check authentication status
            is_authenticated = False
            try:
                if provider_type == "google":
                    provider = GoogleProvider(provider_id, settings, db)
                    # Check OAuth authentication first
                    import asyncio
                    is_authenticated = asyncio.get_event_loop().run_until_complete(provider.is_authenticated())
                    # If not authenticated via OAuth, check for legacy credentials
                    if not is_authenticated and has_legacy_google:
                        is_authenticated = True
                        logger.info(f"Using legacy Google credentials for {provider_id}")
                elif provider_type == "microsoft":
                    provider = MicrosoftProvider(provider_id, settings, db)
                    import asyncio
                    is_authenticated = asyncio.get_event_loop().run_until_complete(provider.is_authenticated())
                elif provider_type == "proton":
                    provider = ProtonProvider(provider_id, settings, db)
                    import asyncio
                    is_authenticated = asyncio.get_event_loop().run_until_complete(provider.is_authenticated())
                else:
                    continue
            except Exception as e:
                logger.error(f"Error checking auth for {provider_id}: {e}")
            
            provider_name = provider_id.replace(f"{provider_type}_", "").replace("_", " ").title()
            # Add "(Legacy)" suffix if using legacy credentials
            if provider_type == "google" and has_legacy_google and is_authenticated:
                provider_name += " (Legacy)"
            
            providers.append({
                "id": provider_id,
                "type": provider_type,
                "name": provider_name,
                "enabled": bool(enabled),
                "authenticated": is_authenticated,
                "capabilities": capabilities,
                "last_auth": last_auth
            })
        
        # Only add separate legacy Google provider if NO google providers exist in database
        if has_legacy_google and not any(p["type"] == "google" for p in providers):
            google_provider = GoogleProvider("google_default", settings, db)
            is_google_authenticated = False
            try:
                import asyncio
                is_google_authenticated = asyncio.get_event_loop().run_until_complete(google_provider.is_authenticated())
            except Exception as e:
                logger.error(f"Error checking Google auth: {e}")
            
            providers.append({
                "id": "google_default",
                "type": "google",
                "name": "Google (Legacy)",
                "enabled": True,
                "authenticated": is_google_authenticated,
                "capabilities": ["email", "calendar", "notes"],
                "last_auth": None
            })
            logger.info("Added legacy Google provider to list")
        
        return {
            "providers": providers,
            "total": len(providers)
        }
        
    except Exception as e:
        logger.error(f"Error listing providers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/add")
async def add_provider(config: ProviderConfig):
    """Add a new provider configuration."""
    try:
        db = DatabaseManager()
        
        # Generate provider ID
        provider_id = f"{config.provider_type}_{config.provider_name.lower().replace(' ', '_')}"
        
        # Save to database
        import json
        with db.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            # Determine capabilities based on provider type
            capabilities = []
            if config.provider_type == "google":
                capabilities = ["email", "calendar", "notes"]
            elif config.provider_type == "microsoft":
                capabilities = ["email", "calendar", "notes"]
            elif config.provider_type == "proton":
                capabilities = ["email"]
            
            cursor.execute("""
                INSERT INTO provider_configs 
                (provider_id, provider_name, enabled, capabilities, config_data, created_at, updated_at)
                VALUES (?, ?, 1, ?, ?, ?, ?)
            """, (
                provider_id,
                config.provider_type,
                json.dumps(capabilities),
                json.dumps(config.config),
                now,
                now
            ))
            conn.commit()
        
        logger.info(f"Added provider: {provider_id}")
        
        return {
            "success": True,
            "provider_id": provider_id,
            "message": "Provider added successfully"
        }
        
    except Exception as e:
        logger.error(f"Error adding provider: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail={
                "error": str(e),
                "type": type(e).__name__,
                "provider_type": config.provider_type if config else None
            }
        )


@router.delete("/{provider_id}")
async def remove_provider(provider_id: str):
    """Remove a provider configuration."""
    try:
        db = DatabaseManager()
        
        with db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Delete provider config
            cursor.execute("DELETE FROM provider_configs WHERE provider_id = ?", (provider_id,))
            
            # Delete auth tokens
            cursor.execute("DELETE FROM comms_auth WHERE platform = ? OR platform LIKE ?", 
                          (provider_id, f"%{provider_id}%"))
            
            conn.commit()
        
        logger.info(f"Removed provider: {provider_id}")
        
        return {
            "success": True,
            "message": "Provider removed successfully"
        }
        
    except Exception as e:
        logger.error(f"Error removing provider: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{provider_id}/auth-url")
async def get_auth_url(provider_id: str):
    """Get OAuth authorization URL for a provider."""
    try:
        db = DatabaseManager()
        settings = Settings()
        
        # Get provider type from database
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT provider_name FROM provider_configs WHERE provider_id = ?", (provider_id,))
            row = cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Provider not found")
            
            provider_type = row[0]
        
        # Generate auth URL based on provider type
        if provider_type == "google":
            # Google uses existing OAuth flow
            return {
                "auth_url": "/auth/google/authorize",
                "instructions": "Click the link to authorize with Google"
            }
        
        elif provider_type == "microsoft":
            provider = MicrosoftProvider(provider_id, settings, db)
            auth_url = await provider.get_auth_url()
            
            if not auth_url:
                raise HTTPException(status_code=500, detail="Microsoft OAuth not configured. Add MICROSOFT_CLIENT_ID and MICROSOFT_CLIENT_SECRET to .env")
            
            return {
                "auth_url": auth_url,
                "instructions": "Click the link to authorize with Microsoft"
            }
        
        elif provider_type == "proton":
            return {
                "auth_url": None,
                "instructions": "Proton requires IMAP credentials. Use the credentials endpoint.",
                "requires_credentials": True
            }
        
        else:
            raise HTTPException(status_code=400, detail="Unknown provider type")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{provider_id}/credentials")
async def set_proton_credentials(provider_id: str, credentials: ProtonCredentials):
    """Set Proton Bridge IMAP credentials."""
    try:
        db = DatabaseManager()
        
        # Verify this is a Proton provider
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT provider_name FROM provider_configs WHERE provider_id = ?", (provider_id,))
            row = cursor.fetchone()
            
            if not row or row[0] != "proton":
                raise HTTPException(status_code=400, detail="This endpoint is only for Proton providers")
        
        # Save credentials (encrypted in production!)
        import json
        with db.get_connection() as conn:
            cursor = conn.cursor()
            now = datetime.now().isoformat()
            
            # Store in comms_auth table
            cursor.execute("""
                INSERT INTO comms_auth 
                (platform, user_identifier, access_token, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(platform) DO UPDATE SET
                    user_identifier = excluded.user_identifier,
                    access_token = excluded.access_token,
                    updated_at = excluded.updated_at
            """, (
                f"proton_{provider_id}",
                credentials.username,
                json.dumps({"username": credentials.username, "password": credentials.password}),
                now,
                now
            ))
            conn.commit()
        
        # Test authentication
        settings = Settings()
        settings.proton_username = credentials.username
        settings.proton_password = credentials.password
        
        provider = ProtonProvider(provider_id, settings, db)
        authenticated = await provider.authenticate()
        
        if not authenticated:
            raise HTTPException(status_code=401, detail="Failed to authenticate with Proton Bridge. Check credentials and ensure Bridge is running.")
        
        return {
            "success": True,
            "message": "Proton credentials saved and verified"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error setting Proton credentials: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_providers_status():
    """Get authentication status for all providers."""
    try:
        db = DatabaseManager()
        settings = Settings()
        manager = ProviderManager(db)
        
        # Get all providers from database
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT provider_id, provider_name, enabled 
                FROM provider_configs 
                WHERE enabled = 1
            """)
            rows = cursor.fetchall()
        
        status = {}
        for provider_id, provider_type, enabled in rows:
            try:
                if provider_type == "google":
                    provider = GoogleProvider(provider_id, settings, db)
                elif provider_type == "microsoft":
                    provider = MicrosoftProvider(provider_id, settings, db)
                elif provider_type == "proton":
                    provider = ProtonProvider(provider_id, settings, db)
                else:
                    continue
                
                is_auth = await provider.is_authenticated()
                status[provider_id] = {
                    "provider_type": provider_type,
                    "authenticated": is_auth,
                    "capabilities": [cap.value for cap in provider.capabilities]
                }
            except Exception as e:
                logger.error(f"Error checking status for {provider_id}: {e}")
                status[provider_id] = {
                    "provider_type": provider_type,
                    "authenticated": False,
                    "error": str(e)
                }
        
        return status
        
    except Exception as e:
        logger.error(f"Error getting provider status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/emails")
async def collect_all_emails(days: int = Query(default=7, ge=1, le=90)):
    """Collect emails from all authenticated providers."""
    try:
        db = DatabaseManager()
        settings = Settings()
        manager = ProviderManager(db)
        
        # Load and register all enabled providers
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT provider_id, provider_name 
                FROM provider_configs 
                WHERE enabled = 1
            """)
            rows = cursor.fetchall()
        
        for provider_id, provider_type in rows:
            try:
                if provider_type == "google":
                    provider = GoogleProvider(provider_id, settings, db)
                elif provider_type == "microsoft":
                    provider = MicrosoftProvider(provider_id, settings, db)
                elif provider_type == "proton":
                    provider = ProtonProvider(provider_id, settings, db)
                else:
                    continue
                
                manager.register_provider(provider)
            except Exception as e:
                logger.error(f"Error registering {provider_id}: {e}")
        
        # Collect emails
        from datetime import timedelta
        start_date = datetime.now() - timedelta(days=days)
        end_date = datetime.now()
        
        all_emails = await manager.collect_all_emails(start_date, end_date, max_results=100)
        
        # Flatten and combine
        combined_emails = []
        for provider_id, emails in all_emails.items():
            combined_emails.extend(emails)
        
        # Sort by date
        combined_emails.sort(key=lambda x: x.get('received_date', ''), reverse=True)
        
        return {
            "emails": combined_emails,
            "total": len(combined_emails),
            "by_provider": {k: len(v) for k, v in all_emails.items()},
            "days": days
        }
        
    except Exception as e:
        logger.error(f"Error collecting emails: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calendar")
async def collect_all_calendar(days: int = Query(default=7, ge=1, le=90)):
    """Collect calendar events from all authenticated providers."""
    try:
        db = DatabaseManager()
        settings = Settings()
        manager = ProviderManager(db)
        
        # Load and register all enabled providers with calendar capability
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT provider_id, provider_name 
                FROM provider_configs 
                WHERE enabled = 1 AND capabilities LIKE '%calendar%'
            """)
            rows = cursor.fetchall()
        
        for provider_id, provider_type in rows:
            try:
                if provider_type == "google":
                    provider = GoogleProvider(provider_id, settings, db)
                elif provider_type == "microsoft":
                    provider = MicrosoftProvider(provider_id, settings, db)
                else:
                    continue
                
                manager.register_provider(provider)
            except Exception as e:
                logger.error(f"Error registering {provider_id}: {e}")
        
        # Collect events
        from datetime import timedelta
        start_date = datetime.now()
        end_date = datetime.now() + timedelta(days=days)
        
        all_events = await manager.collect_all_calendar_events(start_date, end_date, max_results=100)
        
        # Flatten and combine
        combined_events = []
        for provider_id, events in all_events.items():
            combined_events.extend(events)
        
        # Sort by start time
        combined_events.sort(key=lambda x: x.get('start_time', ''))
        
        return {
            "events": combined_events,
            "total": len(combined_events),
            "by_provider": {k: len(v) for k, v in all_events.items()},
            "days": days
        }
        
    except Exception as e:
        logger.error(f"Error collecting calendar events: {e}")
        raise HTTPException(status_code=500, detail=str(e))
