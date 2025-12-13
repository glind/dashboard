"""
Data models for the Trust Layer system.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class RiskLevel(str, Enum):
    """Risk levels for trust reports."""
    LIKELY_OK = "likely_ok"
    CAUTION = "caution"
    HIGH_RISK = "high_risk"


class FindingSeverity(str, Enum):
    """Severity levels for individual findings."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass
class VerificationContext:
    """
    Context provided to verifier plugins.
    Contains all relevant information about an email for trust evaluation.
    """
    # Email identification
    message_id: str
    thread_id: str
    
    # Email metadata
    sender_email: str
    sender_domain: str
    reply_to: Optional[str] = None
    return_path: Optional[str] = None
    
    # Headers and authentication
    raw_headers: Dict[str, Any] = field(default_factory=dict)
    parsed_headers: Dict[str, str] = field(default_factory=dict)
    auth_results: List[Dict[str, Any]] = field(default_factory=list)
    
    # Content
    subject: str = ""
    body_text: str = ""
    body_html: str = ""
    snippet: str = ""
    
    # Extracted data
    extracted_urls: List[Dict[str, str]] = field(default_factory=list)
    extracted_domains: List[str] = field(default_factory=list)
    
    # Thread information
    thread_message_count: int = 1
    is_reply: bool = False
    previous_messages: List[Dict[str, Any]] = field(default_factory=list)
    
    # User context (if applicable)
    user_id: Optional[int] = None
    
    # Timestamp
    received_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'message_id': self.message_id,
            'thread_id': self.thread_id,
            'sender_email': self.sender_email,
            'sender_domain': self.sender_domain,
            'reply_to': self.reply_to,
            'return_path': self.return_path,
            'subject': self.subject,
            'snippet': self.snippet,
            'url_count': len(self.extracted_urls),
            'domain_count': len(self.extracted_domains),
            'thread_message_count': self.thread_message_count,
            'is_reply': self.is_reply,
            'received_at': self.received_at.isoformat() if self.received_at else None
        }


@dataclass
class Finding:
    """
    An individual finding from a verifier plugin.
    """
    finding_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    rule_id: str = ""
    rule_name: str = ""
    severity: FindingSeverity = FindingSeverity.LOW
    points_delta: int = 0  # Negative for risk, positive for trust
    description: str = ""
    evidence: str = ""  # Limited to 200 chars
    remediation: str = ""  # Suggested action
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'finding_id': self.finding_id,
            'rule_id': self.rule_id,
            'rule_name': self.rule_name,
            'severity': self.severity.value,
            'points_delta': self.points_delta,
            'description': self.description,
            'evidence': self.evidence[:200],  # Enforce limit
            'remediation': self.remediation,
            'metadata': self.metadata
        }


@dataclass
class TrustClaim:
    """
    A trust claim from a verifier plugin.
    Represents an attestation or verification result.
    """
    claim_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    provider: str = ""  # Plugin name
    claim_type: str = ""  # e.g., "spf_pass", "linkedin_verified", "domain_age"
    subject: str = ""  # What the claim is about (email, domain, etc.)
    issuer: str = ""  # Who issued the claim
    evidence: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.5  # 0-1
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'claim_id': self.claim_id,
            'provider': self.provider,
            'claim_type': self.claim_type,
            'subject': self.subject,
            'issuer': self.issuer,
            'evidence': self.evidence,
            'confidence': self.confidence,
            'created_at': self.created_at.isoformat()
        }


@dataclass
class TrustReport:
    """
    Complete trust report for an email thread.
    """
    report_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    thread_id: str = ""
    primary_message_id: str = ""
    score: int = 100  # 0-100
    risk_level: RiskLevel = RiskLevel.LIKELY_OK
    summary: str = ""
    findings: List[Finding] = field(default_factory=list)
    claims: List[TrustClaim] = field(default_factory=list)
    signals: Dict[str, Any] = field(default_factory=dict)  # Raw data from plugins
    version: int = 1
    ruleset_version: str = "1.0"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def determine_risk_level(self) -> RiskLevel:
        """Determine risk level based on score."""
        if self.score >= 80:
            return RiskLevel.LIKELY_OK
        elif self.score >= 55:
            return RiskLevel.CAUTION
        else:
            return RiskLevel.HIGH_RISK
    
    def get_top_findings(self, count: int = 5) -> List[Finding]:
        """Get top N findings by severity."""
        severity_order = {
            FindingSeverity.HIGH: 3,
            FindingSeverity.MEDIUM: 2,
            FindingSeverity.LOW: 1
        }
        sorted_findings = sorted(
            self.findings,
            key=lambda f: (severity_order.get(f.severity, 0), abs(f.points_delta)),
            reverse=True
        )
        return sorted_findings[:count]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'report_id': self.report_id,
            'thread_id': self.thread_id,
            'primary_message_id': self.primary_message_id,
            'score': self.score,
            'risk_level': self.risk_level.value,
            'summary': self.summary,
            'findings': [f.to_dict() for f in self.findings],
            'claims': [c.to_dict() for c in self.claims],
            'signals': self.signals,
            'version': self.version,
            'ruleset_version': self.ruleset_version,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
