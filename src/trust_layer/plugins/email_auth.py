"""
Email Authentication Plugin - Verifies SPF, DKIM, DMARC.
"""

import logging
import re
from typing import List, Dict, Any, Optional
from email import message_from_string
from email.message import Message

from ..plugin_registry import VerifierPlugin
from ..models import VerificationContext, TrustClaim, Finding, FindingSeverity

logger = logging.getLogger(__name__)


class EmailAuthPlugin(VerifierPlugin):
    """
    Verifies email authentication (SPF, DKIM, DMARC).
    Parses Authentication-Results headers and checks domain alignment.
    """
    
    @property
    def name(self) -> str:
        return "email_auth"
    
    @property
    def description(self) -> str:
        return "Verifies SPF, DKIM, and DMARC authentication"
    
    async def gather_signals(self, context: VerificationContext) -> List[TrustClaim]:
        """Gather email authentication signals."""
        claims = []
        
        # Parse authentication results from headers
        auth_results = self._parse_auth_results(context.raw_headers)
        
        # Check SPF
        spf_result = auth_results.get('spf', {})
        if spf_result:
            claims.append(TrustClaim(
                provider=self.name,
                claim_type="spf_result",
                subject=context.sender_domain,
                issuer="email_server",
                evidence=spf_result,
                confidence=0.9 if spf_result.get('result') == 'pass' else 0.3
            ))
        
        # Check DKIM
        dkim_result = auth_results.get('dkim', {})
        if dkim_result:
            claims.append(TrustClaim(
                provider=self.name,
                claim_type="dkim_result",
                subject=dkim_result.get('domain', context.sender_domain),
                issuer="email_server",
                evidence=dkim_result,
                confidence=0.9 if dkim_result.get('result') == 'pass' else 0.3
            ))
        
        # Check DMARC
        dmarc_result = auth_results.get('dmarc', {})
        if dmarc_result:
            claims.append(TrustClaim(
                provider=self.name,
                claim_type="dmarc_result",
                subject=context.sender_domain,
                issuer="email_server",
                evidence=dmarc_result,
                confidence=0.9 if dmarc_result.get('result') == 'pass' else 0.3
            ))
        
        # Check domain alignment
        alignment = self._check_alignment(context, auth_results)
        if alignment:
            claims.append(TrustClaim(
                provider=self.name,
                claim_type="domain_alignment",
                subject=context.sender_domain,
                issuer=self.name,
                evidence=alignment,
                confidence=0.8 if alignment.get('aligned') else 0.2
            ))
        
        return claims
    
    async def get_findings(self, context: VerificationContext) -> List[Finding]:
        """Get specific findings for scoring."""
        findings = []
        auth_results = self._parse_auth_results(context.raw_headers)
        
        # SPF failures
        spf_result = auth_results.get('spf', {}).get('result', '')
        if spf_result in ['fail', 'softfail']:
            findings.append(Finding(
                rule_id='spf_fail',
                rule_name='SPF Failure',
                severity=FindingSeverity.HIGH,
                points_delta=-20,
                description='SPF authentication failed',
                evidence=f"SPF result: {spf_result}",
                remediation='Verify sender is authorized to send from this domain'
            ))
        
        # DKIM failures
        dkim_result = auth_results.get('dkim', {}).get('result', '')
        if dkim_result == 'fail':
            findings.append(Finding(
                rule_id='dkim_fail',
                rule_name='DKIM Failure',
                severity=FindingSeverity.HIGH,
                points_delta=-20,
                description='DKIM signature validation failed',
                evidence=f"DKIM result: {dkim_result}",
                remediation='Email may have been tampered with or sent from unauthorized server'
            ))
        
        # DMARC failures
        dmarc_result = auth_results.get('dmarc', {}).get('result', '')
        if dmarc_result == 'fail':
            findings.append(Finding(
                rule_id='dmarc_fail',
                rule_name='DMARC Failure',
                severity=FindingSeverity.HIGH,
                points_delta=-20,
                description='DMARC policy check failed',
                evidence=f"DMARC result: {dmarc_result}",
                remediation='Domain owner policy says this email should not be trusted'
            ))
        
        # No DMARC policy
        if not auth_results.get('dmarc'):
            findings.append(Finding(
                rule_id='dmarc_missing',
                rule_name='Missing DMARC',
                severity=FindingSeverity.MEDIUM,
                points_delta=-10,
                description='Domain has no DMARC policy',
                evidence=f"No DMARC record for {context.sender_domain}",
                remediation='Legitimate businesses typically have DMARC policies'
            ))
        
        # Domain misalignment
        alignment = self._check_alignment(context, auth_results)
        if alignment and not alignment.get('aligned'):
            findings.append(Finding(
                rule_id='alignment_fail',
                rule_name='Domain Misalignment',
                severity=FindingSeverity.MEDIUM,
                points_delta=-15,
                description='From/Return-Path/DKIM domains do not align',
                evidence=f"From: {context.sender_domain}, DKIM: {alignment.get('dkim_domain')}",
                remediation='Verify sender identity carefully - domains should match'
            ))
        
        return findings
    
    def _parse_auth_results(self, raw_headers: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
        """
        Parse Authentication-Results header.
        
        Returns dict with spf, dkim, dmarc results.
        """
        results = {}
        
        # Get Authentication-Results header (can appear multiple times)
        auth_header = raw_headers.get('Authentication-Results', '')
        if not auth_header:
            return results
        
        # Handle list of headers
        if isinstance(auth_header, list):
            auth_header = ' '.join(auth_header)
        
        # Parse SPF
        spf_match = re.search(r'spf=(\w+)(?:\s+.*?domain=([^\s;]+))?', auth_header, re.IGNORECASE)
        if spf_match:
            results['spf'] = {
                'result': spf_match.group(1).lower(),
                'domain': spf_match.group(2) if spf_match.group(2) else None
            }
        
        # Parse DKIM
        dkim_match = re.search(r'dkim=(\w+)(?:\s+.*?d=([^\s;]+))?', auth_header, re.IGNORECASE)
        if dkim_match:
            results['dkim'] = {
                'result': dkim_match.group(1).lower(),
                'domain': dkim_match.group(2) if dkim_match.group(2) else None
            }
        
        # Parse DMARC
        dmarc_match = re.search(r'dmarc=(\w+)(?:\s+.*?from=([^\s;]+))?', auth_header, re.IGNORECASE)
        if dmarc_match:
            results['dmarc'] = {
                'result': dmarc_match.group(1).lower(),
                'from_domain': dmarc_match.group(2) if dmarc_match.group(2) else None
            }
        
        return results
    
    def _check_alignment(
        self,
        context: VerificationContext,
        auth_results: Dict[str, Dict[str, str]]
    ) -> Dict[str, Any]:
        """Check if From, Return-Path, and DKIM domains align."""
        from_domain = context.sender_domain
        return_path_domain = None
        dkim_domain = auth_results.get('dkim', {}).get('domain')
        
        # Extract Return-Path domain if available
        if context.return_path:
            return_path_match = re.search(r'@([\w\.-]+)', context.return_path)
            if return_path_match:
                return_path_domain = return_path_match.group(1)
        
        # Check alignment
        aligned = True
        if dkim_domain and dkim_domain != from_domain:
            aligned = False
        if return_path_domain and return_path_domain != from_domain:
            aligned = False
        
        return {
            'aligned': aligned,
            'from_domain': from_domain,
            'return_path_domain': return_path_domain,
            'dkim_domain': dkim_domain
        }
