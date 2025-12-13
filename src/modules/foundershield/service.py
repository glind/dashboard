"""
FounderShield Email Risk Analysis Service

Comprehensive email and domain risk scoring with DNS checks, WHOIS lookup,
authentication verification, and content analysis.
"""

import re
import logging
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from urllib.parse import urlparse
import dns.resolver
import whois
from email.parser import HeaderParser

logger = logging.getLogger(__name__)


class FounderShieldService:
    """Email and domain risk analysis service."""
    
    # Risk thresholds
    RISK_LIKELY_OK = 70  # >= 70 points
    RISK_CAUTION = 40     # 40-69 points
    RISK_HIGH = 0         # < 40 points
    
    # Suspicious URL patterns
    SUSPICIOUS_URLS = [
        (r'drive\.google\.com/(?:file|drive|open)', 'GOOGLE_DRIVE_LINK', 'medium'),
        (r'forbescouncils\.com', 'FORBES_COUNCILS_LINK', 'medium'),
        (r'/testimonials?/', 'SELF_HOSTED_TESTIMONIAL', 'low'),
        (r'bit\.ly|tinyurl\.com|goo\.gl', 'URL_SHORTENER', 'high'),
        (r'\d+\.\d+\.\d+\.\d+', 'IP_ADDRESS_URL', 'high'),
    ]
    
    # Scam content patterns
    SCAM_PATTERNS = [
        (r'pay.*(?:due diligence|risk mitigation|investor protection)', 35, 'PAY_FOR_SERVICE'),
        (r'what is your budget', 10, 'BUDGET_QUESTION'),
        (r'urgent.*(?:action|response|reply)', 15, 'URGENCY_PRESSURE'),
        (r'(?:verify|confirm).*account', 20, 'ACCOUNT_VERIFICATION'),
        (r'suspended.*account', 25, 'ACCOUNT_THREAT'),
    ]
    
    def __init__(self):
        """Initialize FounderShield service."""
        self.dns_resolver = dns.resolver.Resolver()
        self.dns_resolver.timeout = 3
        self.dns_resolver.lifetime = 3
    
    async def generate_report(
        self,
        email_address: str,
        raw_headers: Optional[str] = None,
        raw_body: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate comprehensive email risk report.
        
        Args:
            email_address: Email address to analyze
            raw_headers: Optional raw email headers
            raw_body: Optional raw email body
            
        Returns:
            Risk report dictionary with score, risk_level, findings, etc.
        """
        # Extract domain
        domain = self._extract_domain(email_address)
        if not domain:
            return self._error_report("Invalid email address")
        
        # Initialize scoring (start at 100, subtract for issues)
        score = 100
        findings = []
        signals = {}
        
        # 1. DNS Checks
        dns_data = await self._check_dns(domain)
        signals['dns'] = dns_data
        
        if not dns_data.get('mx_records'):
            findings.append({
                'id': 'NO_MX_RECORDS',
                'severity': 'high',
                'details': f'Domain {domain} has no MX records configured'
            })
            score -= 30
        
        if not dns_data.get('spf_record'):
            findings.append({
                'id': 'NO_SPF',
                'severity': 'medium',
                'details': 'Domain has no SPF record configured'
            })
            score -= 5
        
        if not dns_data.get('dmarc_record'):
            findings.append({
                'id': 'DMARC_MISSING',
                'severity': 'high',
                'details': 'Domain has no DMARC policy configured'
            })
            score -= 10
        
        # 2. WHOIS Check
        whois_data = await self._check_whois(domain)
        signals['whois'] = whois_data
        
        if whois_data.get('created_date'):
            domain_age_days = (datetime.now() - whois_data['created_date']).days
            if domain_age_days < 548:  # 18 months
                findings.append({
                    'id': 'YOUNG_DOMAIN',
                    'severity': 'high',
                    'details': f'Domain is only {domain_age_days} days old (< 18 months)'
                })
                score -= 25
        
        # 3. Authentication Results (if headers provided)
        auth_results = {}
        if raw_headers:
            auth_results = self._parse_auth_headers(raw_headers)
            signals['auth_results'] = auth_results
            
            if auth_results.get('spf') == 'fail':
                findings.append({
                    'id': 'SPF_FAIL',
                    'severity': 'critical',
                    'details': 'Email failed SPF authentication'
                })
                score -= 20
            
            if auth_results.get('dkim') == 'fail':
                findings.append({
                    'id': 'DKIM_FAIL',
                    'severity': 'critical',
                    'details': 'Email failed DKIM authentication'
                })
                score -= 20
            
            if auth_results.get('dmarc') == 'fail':
                findings.append({
                    'id': 'DMARC_FAIL',
                    'severity': 'critical',
                    'details': 'Email failed DMARC authentication'
                })
                score -= 20
        
        # 4. Content Analysis (if body provided)
        if raw_body:
            content_findings = self._analyze_content(raw_body)
            findings.extend(content_findings['findings'])
            score -= content_findings['score_deduction']
            signals['content'] = content_findings['details']
        
        # Ensure score stays in bounds
        score = max(0, min(100, score))
        
        # Determine risk level
        risk_level = self._calculate_risk_level(score)
        
        return {
            'score': score,
            'risk_level': risk_level,
            'findings': findings,
            'domain': domain,
            'signals': signals,
            'email': email_address,
            'timestamp': datetime.now().isoformat()
        }
    
    def _extract_domain(self, email_address: str) -> Optional[str]:
        """Extract domain from email address."""
        match = re.search(r'@([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})$', email_address)
        return match.group(1).lower() if match else None
    
    async def _check_dns(self, domain: str) -> Dict[str, Any]:
        """Check DNS records for domain."""
        results = {
            'mx_records': [],
            'spf_record': None,
            'dmarc_record': None,
            'mta_sts': False,
            'tlsrpt': False
        }
        
        try:
            # MX Records
            try:
                mx_records = self.dns_resolver.resolve(domain, 'MX')
                results['mx_records'] = [
                    {'priority': r.preference, 'host': str(r.exchange)}
                    for r in mx_records
                ]
            except Exception as e:
                logger.debug(f"No MX records for {domain}: {e}")
            
            # TXT records (SPF)
            try:
                txt_records = self.dns_resolver.resolve(domain, 'TXT')
                for record in txt_records:
                    txt_value = ''.join([s.decode() if isinstance(s, bytes) else s for s in record.strings])
                    if txt_value.startswith('v=spf1'):
                        results['spf_record'] = txt_value
                        break
            except Exception as e:
                logger.debug(f"No SPF record for {domain}: {e}")
            
            # DMARC
            try:
                dmarc_records = self.dns_resolver.resolve(f'_dmarc.{domain}', 'TXT')
                for record in dmarc_records:
                    txt_value = ''.join([s.decode() if isinstance(s, bytes) else s for s in record.strings])
                    if txt_value.startswith('v=DMARC1'):
                        results['dmarc_record'] = txt_value
                        break
            except Exception as e:
                logger.debug(f"No DMARC record for {domain}: {e}")
            
            # MTA-STS
            try:
                self.dns_resolver.resolve(f'_mta-sts.{domain}', 'TXT')
                results['mta_sts'] = True
            except:
                pass
            
            # TLSRPT
            try:
                self.dns_resolver.resolve(f'_smtp._tls.{domain}', 'TXT')
                results['tlsrpt'] = True
            except:
                pass
                
        except Exception as e:
            logger.error(f"Error checking DNS for {domain}: {e}")
        
        return results
    
    async def _check_whois(self, domain: str) -> Dict[str, Any]:
        """Check WHOIS information for domain."""
        results = {
            'created_date': None,
            'registrar': None,
            'available': True
        }
        
        try:
            w = whois.whois(domain)
            
            # Handle creation date (can be list or single value)
            created = w.creation_date
            if isinstance(created, list):
                created = created[0] if created else None
            
            if created:
                results['created_date'] = created
                results['available'] = False
            
            results['registrar'] = w.registrar if hasattr(w, 'registrar') else None
            
        except Exception as e:
            logger.debug(f"WHOIS lookup failed for {domain}: {e}")
        
        return results
    
    def _parse_auth_headers(self, raw_headers: str) -> Dict[str, str]:
        """Parse Authentication-Results header."""
        auth_results = {
            'spf': 'none',
            'dkim': 'none',
            'dmarc': 'none'
        }
        
        try:
            parser = HeaderParser()
            headers = parser.parsestr(raw_headers)
            auth_header = headers.get('Authentication-Results', '')
            
            # Parse SPF
            spf_match = re.search(r'spf=(\w+)', auth_header, re.IGNORECASE)
            if spf_match:
                auth_results['spf'] = spf_match.group(1).lower()
            
            # Parse DKIM
            dkim_match = re.search(r'dkim=(\w+)', auth_header, re.IGNORECASE)
            if dkim_match:
                auth_results['dkim'] = dkim_match.group(1).lower()
            
            # Parse DMARC
            dmarc_match = re.search(r'dmarc=(\w+)', auth_header, re.IGNORECASE)
            if dmarc_match:
                auth_results['dmarc'] = dmarc_match.group(1).lower()
                
        except Exception as e:
            logger.error(f"Error parsing auth headers: {e}")
        
        return auth_results
    
    def _analyze_content(self, raw_body: str) -> Dict[str, Any]:
        """Analyze email body for suspicious content."""
        findings = []
        score_deduction = 0
        details = {
            'suspicious_urls': [],
            'scam_patterns': []
        }
        
        body_lower = raw_body.lower()
        
        # Check for scam patterns
        for pattern, points, pattern_id in self.SCAM_PATTERNS:
            if re.search(pattern, body_lower, re.IGNORECASE):
                findings.append({
                    'id': pattern_id,
                    'severity': 'high' if points >= 20 else 'medium',
                    'details': f'Suspicious pattern detected: {pattern_id}'
                })
                score_deduction += points
                details['scam_patterns'].append(pattern_id)
        
        # Extract and check URLs
        urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', raw_body)
        for url in urls:
            for pattern, url_id, severity in self.SUSPICIOUS_URLS:
                if re.search(pattern, url, re.IGNORECASE):
                    findings.append({
                        'id': url_id,
                        'severity': severity,
                        'details': f'Suspicious URL found: {url[:100]}'
                    })
                    details['suspicious_urls'].append({
                        'url': url,
                        'type': url_id
                    })
                    if severity == 'high':
                        score_deduction += 15
                    elif severity == 'medium':
                        score_deduction += 8
        
        return {
            'findings': findings,
            'score_deduction': score_deduction,
            'details': details
        }
    
    def _calculate_risk_level(self, score: int) -> str:
        """Calculate risk level from score."""
        if score >= self.RISK_LIKELY_OK:
            return 'likely_ok'
        elif score >= self.RISK_CAUTION:
            return 'caution'
        else:
            return 'high_risk'
    
    def _error_report(self, error_message: str) -> Dict[str, Any]:
        """Generate error report."""
        return {
            'score': 0,
            'risk_level': 'error',
            'findings': [{
                'id': 'ERROR',
                'severity': 'critical',
                'details': error_message
            }],
            'domain': None,
            'signals': {},
            'timestamp': datetime.now().isoformat()
        }
