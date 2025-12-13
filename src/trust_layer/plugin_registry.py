"""
Plugin registry and base verifier plugin interface.
"""

import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

from .models import VerificationContext, TrustClaim, Finding

logger = logging.getLogger(__name__)


class VerifierPlugin(ABC):
    """
    Base class for verifier plugins.
    
    All verifier plugins must inherit from this class and implement
    the gather_signals method. Optional methods include request_verification
    and complete_verification for interactive verification flows.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the plugin.
        
        Args:
            config: Plugin-specific configuration
        """
        self.config = config or {}
        self.enabled = self.config.get('enabled', True)
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin name (must be unique)."""
        pass
    
    @property
    def description(self) -> str:
        """Plugin description."""
        return ""
    
    @property
    def version(self) -> str:
        """Plugin version."""
        return "1.0.0"
    
    @abstractmethod
    async def gather_signals(self, context: VerificationContext) -> List[TrustClaim]:
        """
        Gather trust signals and return claims.
        
        This is the main method that every plugin must implement.
        It analyzes the context and returns a list of trust claims.
        
        Args:
            context: Verification context with email data
            
        Returns:
            List of TrustClaim objects
            
        Raises:
            Exception: If signal gathering fails (plugins should handle gracefully)
        """
        pass
    
    async def get_findings(self, context: VerificationContext) -> List[Finding]:
        """
        Get specific findings for the trust report.
        
        Optional method for plugins that want to provide structured findings
        in addition to claims. Findings are used for scoring.
        
        Args:
            context: Verification context
            
        Returns:
            List of Finding objects
        """
        return []
    
    async def request_verification(
        self,
        context: VerificationContext,
        **kwargs
    ) -> Optional[Dict[str, Any]]:
        """
        Initiate an external verification request.
        
        Optional method for plugins that support interactive verification.
        For example, requesting a LinkedIn verification from the sender.
        
        Args:
            context: Verification context
            **kwargs: Additional parameters
            
        Returns:
            Dict with verification request details, or None if not supported
        """
        return None
    
    async def complete_verification(
        self,
        callback_data: Dict[str, Any]
    ) -> Optional[List[TrustClaim]]:
        """
        Complete a verification request with callback data.
        
        Optional method for plugins that handle verification callbacks.
        
        Args:
            callback_data: Data from the verification callback
            
        Returns:
            List of TrustClaim objects if verification succeeded, None otherwise
        """
        return None
    
    async def healthcheck(self) -> bool:
        """
        Check if the plugin is healthy and can operate.
        
        Returns:
            True if healthy, False otherwise
        """
        return self.enabled


class PluginRegistry:
    """
    Registry for managing verifier plugins.
    """
    
    def __init__(self):
        """Initialize the plugin registry."""
        self._plugins: Dict[str, VerifierPlugin] = {}
        self._load_order: List[str] = []
    
    def register(self, plugin: VerifierPlugin) -> None:
        """
        Register a verifier plugin.
        
        Args:
            plugin: Plugin instance to register
            
        Raises:
            ValueError: If a plugin with the same name is already registered
        """
        if plugin.name in self._plugins:
            logger.warning(f"Plugin '{plugin.name}' is already registered. Replacing.")
        
        self._plugins[plugin.name] = plugin
        if plugin.name not in self._load_order:
            self._load_order.append(plugin.name)
        
        logger.info(f"Registered verifier plugin: {plugin.name} v{plugin.version}")
    
    def unregister(self, plugin_name: str) -> None:
        """
        Unregister a plugin by name.
        
        Args:
            plugin_name: Name of the plugin to unregister
        """
        if plugin_name in self._plugins:
            del self._plugins[plugin_name]
            self._load_order.remove(plugin_name)
            logger.info(f"Unregistered plugin: {plugin_name}")
    
    def get(self, plugin_name: str) -> Optional[VerifierPlugin]:
        """
        Get a plugin by name.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            Plugin instance or None if not found
        """
        return self._plugins.get(plugin_name)
    
    def get_all(self) -> List[VerifierPlugin]:
        """
        Get all registered plugins in load order.
        
        Returns:
            List of plugin instances
        """
        return [self._plugins[name] for name in self._load_order if name in self._plugins]
    
    def get_enabled(self) -> List[VerifierPlugin]:
        """
        Get all enabled plugins.
        
        Returns:
            List of enabled plugin instances
        """
        return [p for p in self.get_all() if p.enabled]
    
    async def gather_all_signals(
        self,
        context: VerificationContext
    ) -> Dict[str, List[TrustClaim]]:
        """
        Gather signals from all enabled plugins.
        
        Args:
            context: Verification context
            
        Returns:
            Dict mapping plugin names to lists of trust claims
        """
        results = {}
        
        for plugin in self.get_enabled():
            try:
                logger.debug(f"Gathering signals from plugin: {plugin.name}")
                claims = await plugin.gather_signals(context)
                results[plugin.name] = claims
                logger.debug(f"Plugin {plugin.name} returned {len(claims)} claims")
            except Exception as e:
                logger.error(f"Error in plugin {plugin.name}: {e}", exc_info=True)
                results[plugin.name] = []
        
        return results
    
    async def gather_all_findings(
        self,
        context: VerificationContext
    ) -> Dict[str, List[Finding]]:
        """
        Gather findings from all enabled plugins.
        
        Args:
            context: Verification context
            
        Returns:
            Dict mapping plugin names to lists of findings
        """
        results = {}
        
        for plugin in self.get_enabled():
            try:
                findings = await plugin.get_findings(context)
                if findings:
                    results[plugin.name] = findings
                    logger.debug(f"Plugin {plugin.name} returned {len(findings)} findings")
            except Exception as e:
                logger.error(f"Error getting findings from {plugin.name}: {e}", exc_info=True)
                results[plugin.name] = []
        
        return results
    
    def list_plugins(self) -> List[Dict[str, Any]]:
        """
        List all registered plugins with metadata.
        
        Returns:
            List of plugin metadata dicts
        """
        return [
            {
                'name': p.name,
                'description': p.description,
                'version': p.version,
                'enabled': p.enabled
            }
            for p in self.get_all()
        ]


# Global plugin registry instance
_registry = PluginRegistry()


def get_registry() -> PluginRegistry:
    """Get the global plugin registry instance."""
    return _registry
