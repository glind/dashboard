"""
Multi-provider authentication and data collection system.
Supports Google, Microsoft Office 365, and Proton.
"""

from .base import BaseProvider, ProviderCapability
from .google_provider import GoogleProvider
from .microsoft_provider import MicrosoftProvider
from .proton_provider import ProtonProvider
from .manager import ProviderManager

__all__ = [
    'BaseProvider',
    'ProviderCapability',
    'GoogleProvider',
    'MicrosoftProvider',
    'ProtonProvider',
    'ProviderManager'
]
