"""
DNS Records Plugin - Verifies MX, SPF, DMARC, MTA-STS records.
"""

import logging
from typing import List, Dict, Any, Optional

from ..plugin_registry import VerifierPlugin
from ..models import VerificationContext, TrustClaim, Finding, FindingSeverity

logger = logging.getLogger(__name__)

# Try to import dnspython
try:
    import dns.resolver
    import dns.exception
    DNS_AVAILABLE = True
except ImportError:
    DNS_AVAILABLE = False
    logger.warning("dnspython not available, DNS checks will be skipped")


class DNSRecordsPlugin(VerifierPlugin):
    """
    Verifies DNS records for email domains.
    Checks MX, SPF, DMARC, and MTA-STS records.
    """
    
    @property
    def name(self) -> str:
        return "dns_records"
    
    @property
    def description(self) -> str:
        return "Verifies DNS records (MX, SPF, DMARC, MTA-STS)"
    
    async def gather_signals(self, context: VerificationContext) -> List[TrustClaim]:
        """Gather DNS-based trust signals."""
        if not DNS_AVAILABLE:
            logger.warning("DNS checks skipped - dnspython not installed")
            return []
        
        claims = []
        domain = context.sender_domain
        
        # Check MX records
        mx_records = self._check_mx(domain)
        if mx_records:
            claims.append(TrustClaim(
                provider=self.name,
                claim_type="mx_records",
                subject=domain,
                issuer="dns",
                evidence={'mx_records': mx_records, 'count': len(mx_records)},
                confidence=0.8
            ))
        
        # Check SPF record
        spf_record = self._check_spf(domain)
        if spf_record:
            claims.append(TrustClaim(
                provider=self.name,
                claim_type="spf_record",
                subject=domain,
                issuer="dns",
                evidence={'spf': spf_record},
                confidence=0.9
            ))
        
        # Check DMARC record
        dmarc_record = self._check_dmarc(domain)
        if dmarc_record:
            claims.append(TrustClaim(
                provider=self.name,
                claim_type="dmarc_record",
                subject=domain,
                issuer="dns",
                evidence={'dmarc': dmarc_record},
                confidence=0.9
            ))
        
        # Check MTA-STS
        mta_sts = self._check_mta_sts(domain)
        if mta_sts:
            claims.append(TrustClaim(
                provider=self.name,
                claim_type="mta_sts",
                subject=domain,
                issuer="dns",
                evidence={'mta_sts': mta_sts},
                confidence=0.7
            ))
        
        return claims
    
    async def get_findings(self, context: VerificationContext) -> List[Finding]:
        """Get DNS-related findings for scoring."""
        if not DNS_AVAILABLE:
            return []
        
        findings = []
        domain = context.sender_domain
        
        # Check for missing DMARC
        dmarc_record = self._check_dmarc(domain)
        if not dmarc_record:
            findings.append(Finding(
                rule_id='dmarc_missing',
                rule_name='Missing DMARC Policy',
                severity=FindingSeverity.MEDIUM,
                points_delta=-10,
                description='Domain has no DMARC policy configured',
                evidence=f"No DMARC record found for {domain}",
                remediation='Legitimate businesses typically publish DMARC policies'
            ))
        
        # Check for missing SPF
        spf_record = self._check_spf(domain)
        if not spf_record:
            findings.append(Finding(
                rule_id='spf_missing',
                rule_name='Missing SPF Record',
                severity=FindingSeverity.LOW,
                points_delta=-5,
                description='Domain has no SPF record',
                evidence=f"No SPF record found for {domain}",
                remediation='SPF helps prevent email spoofing'
            ))
        
        # Check for missing MX records
        mx_records = self._check_mx(domain)
        if not mx_records:
            findings.append(Finding(
                rule_id='mx_missing',
                rule_name='Missing MX Records',
                severity=FindingSeverity.HIGH,
                points_delta=-20,
                description='Domain has no mail servers configured',
                evidence=f"No MX records found for {domain}",
                remediation='Legitimate email domains should have MX records'
            ))
        
        return findings
    
    def _check_mx(self, domain: str) -> List[str]:
        """Check MX records for domain."""
        try:
            answers = dns.resolver.resolve(domain, 'MX')
            return [str(rdata.exchange) for rdata in answers]
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException) as e:
            logger.debug(f"No MX records for {domain}: {e}")
            return []
    
    def _check_spf(self, domain: str) -> Optional[str]:
        """Check SPF record for domain."""
        try:
            answers = dns.resolver.resolve(domain, 'TXT')
            for rdata in answers:
                txt = str(rdata).strip('"')
                if txt.startswith('v=spf1'):
                    return txt
            return None
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException) as e:
            logger.debug(f"No SPF record for {domain}: {e}")
            return None
    
    def _check_dmarc(self, domain: str) -> Optional[str]:
        """Check DMARC record for domain."""
        dmarc_domain = f"_dmarc.{domain}"
        try:
            answers = dns.resolver.resolve(dmarc_domain, 'TXT')
            for rdata in answers:
                txt = str(rdata).strip('"')
                if txt.startswith('v=DMARC1'):
                    return txt
            return None
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException) as e:
            logger.debug(f"No DMARC record for {domain}: {e}")
            return None
    
    def _check_mta_sts(self, domain: str) -> Optional[str]:
        """Check MTA-STS record for domain."""
        mta_sts_domain = f"_mta-sts.{domain}"
        try:
            answers = dns.resolver.resolve(mta_sts_domain, 'TXT')
            for rdata in answers:
                txt = str(rdata).strip('"')
                if 'v=STSv1' in txt:
                    return txt
            return None
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer, dns.exception.DNSException) as e:
            logger.debug(f"No MTA-STS record for {domain}: {e}")
            return None
