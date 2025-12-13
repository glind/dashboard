"""
Transparent scoring engine for trust reports.
"""

import logging
from typing import List, Dict, Any
from dataclasses import dataclass

from .models import TrustReport, Finding, TrustClaim, RiskLevel, FindingSeverity

logger = logging.getLogger(__name__)


@dataclass
class ScoringRule:
    """A scoring rule configuration."""
    rule_id: str
    description: str
    points_delta: int
    applies_to_claim_type: str = ""
    applies_to_finding_rule: str = ""


class ScoringEngine:
    """
    Transparent scoring engine that calculates trust scores based on findings.
    
    The engine starts with a base score of 100 and applies point deltas
    from findings to calculate a final score and risk level.
    """
    
    # Default scoring rules (configurable)
    DEFAULT_RULES = {
        'domain_age_new': ScoringRule(
            rule_id='domain_age_new',
            description='Domain is less than 540 days old',
            points_delta=-25
        ),
        'dmarc_missing': ScoringRule(
            rule_id='dmarc_missing',
            description='Domain has no DMARC policy',
            points_delta=-10
        ),
        'spf_fail': ScoringRule(
            rule_id='spf_fail',
            description='SPF authentication failed',
            points_delta=-20
        ),
        'dkim_fail': ScoringRule(
            rule_id='dkim_fail',
            description='DKIM authentication failed',
            points_delta=-20
        ),
        'dmarc_fail': ScoringRule(
            rule_id='dmarc_fail',
            description='DMARC authentication failed',
            points_delta=-20
        ),
        'alignment_fail': ScoringRule(
            rule_id='alignment_fail',
            description='From/Return-Path/DKIM domain misalignment',
            points_delta=-15
        ),
        'pay_to_pitch': ScoringRule(
            rule_id='pay_to_pitch',
            description='Mentions paying for investor diligence/access',
            points_delta=-35
        ),
        'budget_anchoring': ScoringRule(
            rule_id='budget_anchoring',
            description='Premature budget anchoring ("what\'s your budget?")',
            points_delta=-10
        ),
        'urgency_pressure': ScoringRule(
            rule_id='urgency_pressure',
            description='Aggressive urgency tactics',
            points_delta=-15
        ),
        'authority_garnish': ScoringRule(
            rule_id='authority_garnish',
            description='Excessive self-referential authority claims',
            points_delta=-10
        ),
        'url_reputation_flagged': ScoringRule(
            rule_id='url_reputation_flagged',
            description='URL flagged by reputation service',
            points_delta=-25
        ),
        'suspicious_attachment': ScoringRule(
            rule_id='suspicious_attachment',
            description='Unexpected or suspicious attachment',
            points_delta=-15
        ),
        'domain_lookalike': ScoringRule(
            rule_id='domain_lookalike',
            description='Domain looks like a known brand (typosquatting)',
            points_delta=-30
        ),
    }
    
    def __init__(self, ruleset_version: str = "1.0", custom_rules: Dict[str, ScoringRule] = None):
        """
        Initialize scoring engine.
        
        Args:
            ruleset_version: Version identifier for the ruleset
            custom_rules: Optional custom scoring rules to add/override defaults
        """
        self.ruleset_version = ruleset_version
        self.rules = dict(self.DEFAULT_RULES)
        
        if custom_rules:
            self.rules.update(custom_rules)
        
        logger.info(f"Initialized scoring engine with ruleset v{ruleset_version} ({len(self.rules)} rules)")
    
    def calculate_score(
        self,
        findings: List[Finding],
        claims: List[TrustClaim] = None,
        start_score: int = 100
    ) -> int:
        """
        Calculate trust score based on findings.
        
        Args:
            findings: List of findings from verifiers
            claims: Optional list of trust claims (for future use)
            start_score: Starting score (default 100)
            
        Returns:
            Final score (0-100)
        """
        score = start_score
        
        # Apply point deltas from findings
        for finding in findings:
            score += finding.points_delta
            logger.debug(
                f"Applied finding {finding.rule_id}: {finding.points_delta} points "
                f"(score now: {score})"
            )
        
        # Clamp score to valid range
        score = max(0, min(100, score))
        
        return score
    
    def generate_summary(
        self,
        score: int,
        risk_level: RiskLevel,
        findings: List[Finding],
        claims: List[TrustClaim] = None
    ) -> str:
        """
        Generate a human-readable summary of the trust report.
        
        Args:
            score: Trust score
            risk_level: Risk level
            findings: List of findings
            claims: Optional list of claims
            
        Returns:
            Summary text
        """
        # Count findings by severity
        high_severity = sum(1 for f in findings if f.severity == FindingSeverity.HIGH)
        medium_severity = sum(1 for f in findings if f.severity == FindingSeverity.MEDIUM)
        low_severity = sum(1 for f in findings if f.severity == FindingSeverity.LOW)
        
        # Risk level descriptions
        risk_descriptions = {
            RiskLevel.LIKELY_OK: "This email appears legitimate with no significant red flags.",
            RiskLevel.CAUTION: "This email has some concerns that warrant caution.",
            RiskLevel.HIGH_RISK: "This email has multiple red flags suggesting potential scam or fraud."
        }
        
        summary_parts = [
            f"Trust Score: {score}/100 ({risk_level.value.replace('_', ' ').title()})",
            risk_descriptions.get(risk_level, ""),
        ]
        
        if high_severity > 0:
            summary_parts.append(f"{high_severity} high-severity issue(s) detected.")
        if medium_severity > 0:
            summary_parts.append(f"{medium_severity} medium-severity issue(s) detected.")
        if low_severity > 0:
            summary_parts.append(f"{low_severity} low-severity issue(s) detected.")
        
        if not findings:
            summary_parts.append("No issues detected.")
        
        return " ".join(summary_parts)
    
    def create_report(
        self,
        thread_id: str,
        primary_message_id: str,
        findings: List[Finding],
        claims: List[TrustClaim],
        signals: Dict[str, Any] = None
    ) -> TrustReport:
        """
        Create a complete trust report.
        
        Args:
            thread_id: Email thread ID
            primary_message_id: Primary message ID
            findings: List of findings from verifiers
            claims: List of trust claims from verifiers
            signals: Optional raw signals data
            
        Returns:
            Complete TrustReport object
        """
        # Calculate score
        score = self.calculate_score(findings, claims)
        
        # Create report
        report = TrustReport(
            thread_id=thread_id,
            primary_message_id=primary_message_id,
            score=score,
            findings=findings,
            claims=claims,
            signals=signals or {},
            ruleset_version=self.ruleset_version
        )
        
        # Determine risk level
        report.risk_level = report.determine_risk_level()
        
        # Generate summary
        report.summary = self.generate_summary(
            report.score,
            report.risk_level,
            report.findings,
            report.claims
        )
        
        logger.info(
            f"Created trust report for thread {thread_id}: "
            f"score={score}, risk={report.risk_level.value}, "
            f"findings={len(findings)}, claims={len(claims)}"
        )
        
        return report
    
    def get_rule(self, rule_id: str) -> ScoringRule:
        """
        Get a scoring rule by ID.
        
        Args:
            rule_id: Rule identifier
            
        Returns:
            ScoringRule object or None
        """
        return self.rules.get(rule_id)
    
    def list_rules(self) -> List[Dict[str, Any]]:
        """
        List all scoring rules.
        
        Returns:
            List of rule dictionaries
        """
        return [
            {
                'rule_id': rule.rule_id,
                'description': rule.description,
                'points_delta': rule.points_delta
            }
            for rule in self.rules.values()
        ]
