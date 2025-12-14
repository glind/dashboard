"""
Provider Manager - orchestrates multiple provider instances.
Handles provider registration, authentication, and data collection.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from .base import BaseProvider, ProviderCapability

logger = logging.getLogger(__name__)


class ProviderManager:
    """Manages multiple provider instances and coordinates data collection."""
    
    def __init__(self, db_manager: Any):
        """
        Initialize provider manager.
        
        Args:
            db_manager: Database manager instance
        """
        self.db = db_manager
        self.providers: Dict[str, BaseProvider] = {}
        self._ensure_provider_table()
    
    def _ensure_provider_table(self):
        """Create provider configuration table if it doesn't exist."""
        try:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS provider_configs (
                        provider_id TEXT PRIMARY KEY,
                        provider_name TEXT NOT NULL,
                        enabled INTEGER DEFAULT 1,
                        capabilities TEXT NOT NULL,
                        config_data TEXT,
                        last_auth_date TEXT,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL
                    )
                """)
                conn.commit()
                logger.info("✅ Provider configs table ready")
        except Exception as e:
            logger.error(f"Error creating provider configs table: {e}")
    
    def register_provider(self, provider: BaseProvider):
        """
        Register a provider instance.
        
        Args:
            provider: Provider instance to register
        """
        self.providers[provider.provider_id] = provider
        
        # Save to database
        try:
            import json
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                now = datetime.now().isoformat()
                capabilities_json = json.dumps([cap.value for cap in provider.capabilities])
                
                cursor.execute("""
                    INSERT INTO provider_configs 
                    (provider_id, provider_name, enabled, capabilities, created_at, updated_at)
                    VALUES (?, ?, 1, ?, ?, ?)
                    ON CONFLICT(provider_id) DO UPDATE SET
                        provider_name = excluded.provider_name,
                        capabilities = excluded.capabilities,
                        updated_at = excluded.updated_at
                """, (
                    provider.provider_id,
                    provider.provider_name,
                    capabilities_json,
                    now,
                    now
                ))
                conn.commit()
                logger.info(f"✅ Registered provider: {provider.provider_id} ({provider.provider_name})")
        except Exception as e:
            logger.error(f"Error saving provider config: {e}")
    
    def get_provider(self, provider_id: str) -> Optional[BaseProvider]:
        """
        Get provider by ID.
        
        Args:
            provider_id: Provider identifier
            
        Returns:
            Provider instance or None if not found
        """
        return self.providers.get(provider_id)
    
    def get_providers_by_capability(
        self,
        capability: ProviderCapability
    ) -> List[BaseProvider]:
        """
        Get all providers that support a specific capability.
        
        Args:
            capability: Capability to filter by
            
        Returns:
            List of matching providers
        """
        return [
            provider for provider in self.providers.values()
            if capability in provider.capabilities
        ]
    
    async def collect_all_emails(
        self,
        start_date: datetime,
        end_date: datetime,
        max_results: int = 100
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Collect emails from all providers that support email.
        
        Args:
            start_date: Start date for collection
            end_date: End date for collection
            max_results: Maximum results per provider
            
        Returns:
            Dictionary mapping provider_id to list of emails
        """
        results = {}
        email_providers = self.get_providers_by_capability(ProviderCapability.EMAIL)
        
        for provider in email_providers:
            try:
                if not await provider.is_authenticated():
                    logger.warning(f"Provider {provider.provider_id} not authenticated, skipping")
                    continue
                
                emails = await provider.collect_emails(start_date, end_date, max_results)
                results[provider.provider_id] = emails
                logger.info(f"Collected {len(emails)} emails from {provider.provider_id}")
            except Exception as e:
                logger.error(f"Error collecting emails from {provider.provider_id}: {e}")
                results[provider.provider_id] = []
        
        return results
    
    async def collect_all_calendar_events(
        self,
        start_date: datetime,
        end_date: datetime,
        max_results: int = 100
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Collect calendar events from all providers that support calendar.
        
        Args:
            start_date: Start date for collection
            end_date: End date for collection
            max_results: Maximum results per provider
            
        Returns:
            Dictionary mapping provider_id to list of events
        """
        results = {}
        calendar_providers = self.get_providers_by_capability(ProviderCapability.CALENDAR)
        
        for provider in calendar_providers:
            try:
                if not await provider.is_authenticated():
                    logger.warning(f"Provider {provider.provider_id} not authenticated, skipping")
                    continue
                
                events = await provider.collect_calendar_events(start_date, end_date, max_results)
                results[provider.provider_id] = events
                logger.info(f"Collected {len(events)} events from {provider.provider_id}")
            except Exception as e:
                logger.error(f"Error collecting events from {provider.provider_id}: {e}")
                results[provider.provider_id] = []
        
        return results
    
    async def collect_all_notes(
        self,
        folder_id: Optional[str] = None,
        max_results: int = 100
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Collect notes from all providers that support notes.
        
        Args:
            folder_id: Optional folder ID to filter by
            max_results: Maximum results per provider
            
        Returns:
            Dictionary mapping provider_id to list of notes
        """
        results = {}
        notes_providers = self.get_providers_by_capability(ProviderCapability.NOTES)
        
        for provider in notes_providers:
            try:
                if not await provider.is_authenticated():
                    logger.warning(f"Provider {provider.provider_id} not authenticated, skipping")
                    continue
                
                notes = await provider.collect_notes(folder_id, max_results)
                results[provider.provider_id] = notes
                logger.info(f"Collected {len(notes)} notes from {provider.provider_id}")
            except Exception as e:
                logger.error(f"Error collecting notes from {provider.provider_id}: {e}")
                results[provider.provider_id] = []
        
        return results
    
    def get_authentication_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get authentication status for all registered providers.
        
        Returns:
            Dictionary with provider authentication status
        """
        status = {}
        for provider_id, provider in self.providers.items():
            try:
                # Note: This is sync wrapper, providers should implement async properly
                import asyncio
                is_auth = asyncio.get_event_loop().run_until_complete(provider.is_authenticated())
                status[provider_id] = {
                    'provider_name': provider.provider_name,
                    'authenticated': is_auth,
                    'capabilities': [cap.value for cap in provider.capabilities]
                }
            except Exception as e:
                logger.error(f"Error checking auth status for {provider_id}: {e}")
                status[provider_id] = {
                    'provider_name': provider.provider_name,
                    'authenticated': False,
                    'error': str(e)
                }
        
        return status
