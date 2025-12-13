"""
Content Heuristics Plugin - Detects scam patterns in email content.
"""

import logging
import re
from typing import List, Dict, Any, Tuple

from ..plugin_registry import VerifierPlugin
from ..models import VerificationContext, TrustClaim, Finding, FindingSeverity

logger = logging.getLogger(__name__)


class ContentHeuristicsPlugin(VerifierPlugin):
    """
    Analyzes email content for common scam patterns.
    Uses explainable regex-based rules to detect suspicious language.
    """
    
    # Scam pattern definitions
    PATTERNS = {
        'pay_to_pitch': {
            'regex': r'(pay|fee|charge|cost).{0,30}(investor|due diligence|access|pitch|meeting|introduction)',
            'severity': FindingSeverity.HIGH,
            'points': -35,
            'description': 'Mentions paying for investor access or diligence',
            'remediation': 'Legitimate investors do not charge founders for pitches or due diligence'
        },
        'budget_anchoring': {
            'regex': r"(what'?s|what is|how much).{0,20}(your |the )?budget",
            'severity': FindingSeverity.LOW,
            'points': -10,
            'description': 'Premature budget anchoring',
            'remediation': 'Be cautious of early budget questions before value discussion'
        },
        'urgency_pressure': {
            'regex': r'(urgent|immediately|asap|final notice|today only|expires|deadline|limited time|act now|hurry)',
            'severity': FindingSeverity.MEDIUM,
            'points': -15,
            'description': 'Aggressive urgency tactics',
            'remediation': 'Artificial urgency is a common manipulation tactic'
        },
        'authority_garnish': {
            'regex': r'(forbes|inc\.com|entrepreneur).{0,50}(featured|published|recognized|awarded)',
            'severity': FindingSeverity.LOW,
            'points': -10,
            'description': 'Excessive authority claims',
            'remediation': 'Verify claims independently; scammers often fabricate credentials'
        },
        'suspicious_payment': {
            'regex': r'(wire transfer|bitcoin|crypto|gift card|prepaid card|western union|moneygram)',
            'severity': FindingSeverity.HIGH,
            'points': -30,
            'description': 'Suspicious payment methods mentioned',
            'remediation': 'Legitimate businesses do not request untraceable payment methods'
        },
        'vague_opportunity': {
            'regex': r'(incredible opportunity|exclusive offer|secret|limited spots|once in a lifetime|guaranteed returns)',
            'severity': FindingSeverity.MEDIUM,
            'points': -12,
            'description': 'Vague opportunity language',
            'remediation': 'Legitimate opportunities provide specific, verifiable details'
        },
        'credential_pressure': {
            'regex': r'(harvard|stanford|mit|ycombinator|y combinator|500 startups|techstars).{0,30}(alum|alumni|graduate|founder)',
            'severity': FindingSeverity.LOW,
            'points': -5,
            'description': 'Name-dropping prestigious credentials',
            'remediation': 'Verify credentials through official channels (LinkedIn, etc.)'
        },
        'roi_promises': {
            'regex': r'(\d+%|\d+x).{0,30}(return|roi|profit|growth|revenue)',
            'severity': FindingSeverity.HIGH,
            'points': -25,
            'description': 'Unrealistic ROI promises',
            'remediation': 'Guaranteed returns are impossible; this is a major red flag'
        },
        'spelling_errors': {
            'regex': r'(recieve|teh |wiht |youre |there |occured|seperate|definately)',
            'severity': FindingSeverity.LOW,
            'points': -8,
            'description': 'Multiple spelling errors',
            'remediation': 'Professional communications should be proofread'
        }
    }
    
    @property
    def name(self) -> str:
        return "content_heuristics"
    
    @property
    def description(self) -> str:
        return "Detects scam patterns in email content"
    
    async def gather_signals(self, context: VerificationContext) -> List[TrustClaim]:
        """Gather content-based trust signals."""
        claims = []
        
        # Combine subject and body for analysis
        content = f"{context.subject} {context.body_text} {context.snippet}"
        content_lower = content.lower()
        
        # Check each pattern
        matches = self._check_patterns(content_lower)
        
        if matches:
            claims.append(TrustClaim(
                provider=self.name,
                claim_type="scam_patterns_detected",
                subject=context.sender_email,
                issuer=self.name,
                evidence={
                    'patterns_matched': [m[0] for m in matches],
                    'match_count': len(matches)
                },
                confidence=0.7
            ))
        else:
            claims.append(TrustClaim(
                provider=self.name,
                claim_type="no_scam_patterns",
                subject=context.sender_email,
                issuer=self.name,
                evidence={'clean': True},
                confidence=0.6
            ))
        
        return claims
    
    async def get_findings(self, context: VerificationContext) -> List[Finding]:
        """Get content-based findings for scoring."""
        findings = []
        
        # Combine content
        content = f"{context.subject} {context.body_text} {context.snippet}"
        content_lower = content.lower()
        
        # Check all patterns
        matches = self._check_patterns(content_lower)
        
        for pattern_id, evidence_snippet in matches:
            pattern = self.PATTERNS[pattern_id]
            
            findings.append(Finding(
                rule_id=pattern_id,
                rule_name=pattern_id.replace('_', ' ').title(),
                severity=pattern['severity'],
                points_delta=pattern['points'],
                description=pattern['description'],
                evidence=evidence_snippet[:200],  # Limit to 200 chars
                remediation=pattern['remediation']
            ))
        
        return findings
    
    def _check_patterns(self, content: str) -> List[Tuple[str, str]]:
        """
        Check content against all patterns.
        
        Returns:
            List of (pattern_id, evidence_snippet) tuples
        """
        matches = []
        
        for pattern_id, pattern_config in self.PATTERNS.items():
            regex = pattern_config['regex']
            
            match = re.search(regex, content, re.IGNORECASE)
            if match:
                # Extract context around match (50 chars before and after)
                start = max(0, match.start() - 50)
                end = min(len(content), match.end() + 50)
                evidence = content[start:end].strip()
                
                matches.append((pattern_id, evidence))
                logger.debug(f"Pattern '{pattern_id}' matched: {evidence[:100]}")
        
        return matches
    
    def _count_links(self, content: str) -> int:
        """Count links in content."""
        # Simple link counting
        return len(re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', content))
    
    def _extract_phone_numbers(self, content: str) -> List[str]:
        """Extract phone numbers from content."""
        phone_pattern = r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        return re.findall(phone_pattern, content)
