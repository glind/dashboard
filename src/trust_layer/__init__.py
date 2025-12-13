"""
Trust Layer for Anti-Scam Email Analysis
Provides pluggable verification and scoring for inbound email threats.
"""

from .models import (
    VerificationContext,
    TrustClaim,
    TrustReport,
    Finding,
    RiskLevel,
    FindingSeverity
)
from .plugin_registry import PluginRegistry, VerifierPlugin, get_registry
from .scoring_engine import ScoringEngine
from .report_generator import ReportGenerator

__all__ = [
    'VerificationContext',
    'TrustClaim',
    'TrustReport',
    'Finding',
    'RiskLevel',
    'FindingSeverity',
    'PluginRegistry',
    'VerifierPlugin',
    'get_registry',
    'ScoringEngine',
    'ReportGenerator',
]
