"""
FounderShield Unit Tests
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from service import FounderShieldService


class TestFounderShieldService:
    """Test FounderShield email risk analysis."""
    
    @pytest.fixture
    def service(self):
        """Create service instance."""
        return FounderShieldService()
    
    def test_extract_domain_valid(self, service):
        """Test domain extraction from email."""
        assert service._extract_domain('john@example.com') == 'example.com'
        assert service._extract_domain('test@subdomain.example.org') == 'subdomain.example.org'
    
    def test_extract_domain_invalid(self, service):
        """Test domain extraction with invalid email."""
        assert service._extract_domain('notanemail') is None
        assert service._extract_domain('invalid@') is None
    
    def test_parse_auth_headers_spf_pass(self, service):
        """Test parsing SPF pass from headers."""
        headers = """Authentication-Results: mx.google.com;
           spf=pass (google.com: domain of sender@example.com designates 1.2.3.4 as permitted sender)
           """
        result = service._parse_auth_headers(headers)
        assert result['spf'] == 'pass'
    
    def test_parse_auth_headers_spf_fail(self, service):
        """Test parsing SPF fail from headers."""
        headers = """Authentication-Results: mx.google.com;
           spf=fail (google.com: domain of sender@example.com does not designate 5.6.7.8 as permitted sender)
           """
        result = service._parse_auth_headers(headers)
        assert result['spf'] == 'fail'
    
    def test_parse_auth_headers_dkim_pass(self, service):
        """Test parsing DKIM pass from headers."""
        headers = """Authentication-Results: mx.google.com;
           dkim=pass header.i=@example.com header.s=selector header.b=ABC123;
           """
        result = service._parse_auth_headers(headers)
        assert result['dkim'] == 'pass'
    
    def test_parse_auth_headers_dmarc_pass(self, service):
        """Test parsing DMARC pass from headers."""
        headers = """Authentication-Results: mx.google.com;
           dmarc=pass (p=QUARANTINE sp=NONE dis=NONE) header.from=example.com
           """
        result = service._parse_auth_headers(headers)
        assert result['dmarc'] == 'pass'
    
    def test_parse_auth_headers_all_fail(self, service):
        """Test parsing all auth failures."""
        headers = """Authentication-Results: mx.google.com;
           spf=fail dkim=fail dmarc=fail
           """
        result = service._parse_auth_headers(headers)
        assert result['spf'] == 'fail'
        assert result['dkim'] == 'fail'
        assert result['dmarc'] == 'fail'
    
    def test_analyze_content_pay_for_service(self, service):
        """Test detection of pay-for-service scam."""
        body = """
        Dear Investor,
        
        To proceed with our investment opportunity, please pay for our
        due diligence service. This is standard practice.
        """
        result = service._analyze_content(body)
        
        assert result['score_deduction'] >= 35
        assert any(f['id'] == 'PAY_FOR_SERVICE' for f in result['findings'])
    
    def test_analyze_content_budget_question(self, service):
        """Test detection of budget question."""
        body = "Hi there! What is your budget for this project?"
        result = service._analyze_content(body)
        
        assert result['score_deduction'] >= 10
        assert any(f['id'] == 'BUDGET_QUESTION' for f in result['findings'])
    
    def test_analyze_content_google_drive_link(self, service):
        """Test detection of Google Drive links."""
        body = "Please review the document here: https://drive.google.com/file/d/abc123/view"
        result = service._analyze_content(body)
        
        assert any(f['id'] == 'GOOGLE_DRIVE_LINK' for f in result['findings'])
        assert len(result['details']['suspicious_urls']) > 0
    
    def test_analyze_content_forbes_councils(self, service):
        """Test detection of Forbes Councils links."""
        body = "Check out our article: https://www.forbescouncils.com/article/12345"
        result = service._analyze_content(body)
        
        assert any(f['id'] == 'FORBES_COUNCILS_LINK' for f in result['findings'])
    
    def test_analyze_content_url_shortener(self, service):
        """Test detection of URL shorteners."""
        body = "Click here: https://bit.ly/abc123"
        result = service._analyze_content(body)
        
        assert any(f['id'] == 'URL_SHORTENER' for f in result['findings'])
        assert result['score_deduction'] >= 15  # High severity
    
    def test_analyze_content_clean_email(self, service):
        """Test analysis of clean email."""
        body = """
        Hi John,
        
        Thanks for your interest in our product. I'd be happy to schedule
        a demo at your convenience. When would be a good time for you?
        
        Best regards,
        Sales Team
        """
        result = service._analyze_content(body)
        
        assert result['score_deduction'] == 0
        assert len(result['findings']) == 0
    
    def test_calculate_risk_level_likely_ok(self, service):
        """Test risk level calculation for safe emails."""
        assert service._calculate_risk_level(100) == 'likely_ok'
        assert service._calculate_risk_level(75) == 'likely_ok'
        assert service._calculate_risk_level(70) == 'likely_ok'
    
    def test_calculate_risk_level_caution(self, service):
        """Test risk level calculation for moderate risk."""
        assert service._calculate_risk_level(69) == 'caution'
        assert service._calculate_risk_level(50) == 'caution'
        assert service._calculate_risk_level(40) == 'caution'
    
    def test_calculate_risk_level_high_risk(self, service):
        """Test risk level calculation for high risk."""
        assert service._calculate_risk_level(39) == 'high_risk'
        assert service._calculate_risk_level(20) == 'high_risk'
        assert service._calculate_risk_level(0) == 'high_risk'
    
    @pytest.mark.asyncio
    async def test_check_dns_valid_domain(self, service):
        """Test DNS checks for valid domain."""
        # Note: This test requires network access
        # In production, mock the DNS resolver
        result = await service._check_dns('gmail.com')
        
        assert len(result['mx_records']) > 0
        assert result['spf_record'] is not None
        assert result['dmarc_record'] is not None
    
    @pytest.mark.asyncio
    async def test_check_whois_young_domain(self, service):
        """Test WHOIS check detects young domains."""
        with patch('whois.whois') as mock_whois:
            # Mock a domain created 6 months ago
            mock_result = Mock()
            mock_result.creation_date = datetime.now() - timedelta(days=180)
            mock_result.registrar = 'Test Registrar'
            mock_whois.return_value = mock_result
            
            result = await service._check_whois('example.com')
            
            assert result['created_date'] is not None
            assert (datetime.now() - result['created_date']).days < 548
    
    @pytest.mark.asyncio
    async def test_generate_report_high_risk_email(self, service):
        """Test full report generation for high-risk email."""
        with patch.object(service, '_check_dns') as mock_dns, \
             patch.object(service, '_check_whois') as mock_whois:
            
            # Mock young domain with no security configs
            mock_dns.return_value = {
                'mx_records': [{'priority': 10, 'host': 'mail.example.com'}],
                'spf_record': None,
                'dmarc_record': None,
                'mta_sts': False,
                'tlsrpt': False
            }
            
            mock_whois.return_value = {
                'created_date': datetime.now() - timedelta(days=100),
                'registrar': 'Test',
                'available': False
            }
            
            headers = "Authentication-Results: spf=fail dkim=fail dmarc=fail"
            body = "Please pay for our due diligence service. What is your budget?"
            
            report = await service.generate_report(
                'scammer@newdomain.com',
                raw_headers=headers,
                raw_body=body
            )
            
            assert report['score'] < 40  # Should be high risk
            assert report['risk_level'] == 'high_risk'
            assert len(report['findings']) > 0
            assert report['domain'] == 'newdomain.com'
    
    @pytest.mark.asyncio
    async def test_generate_report_safe_email(self, service):
        """Test full report generation for safe email."""
        with patch.object(service, '_check_dns') as mock_dns, \
             patch.object(service, '_check_whois') as mock_whois:
            
            # Mock established domain with security configs
            mock_dns.return_value = {
                'mx_records': [{'priority': 10, 'host': 'mail.google.com'}],
                'spf_record': 'v=spf1 include:_spf.google.com ~all',
                'dmarc_record': 'v=DMARC1; p=quarantine;',
                'mta_sts': True,
                'tlsrpt': True
            }
            
            mock_whois.return_value = {
                'created_date': datetime.now() - timedelta(days=3650),  # 10 years
                'registrar': 'Google Domains',
                'available': False
            }
            
            headers = "Authentication-Results: spf=pass dkim=pass dmarc=pass"
            body = "Hello! I'd like to schedule a meeting to discuss your product."
            
            report = await service.generate_report(
                'user@gmail.com',
                raw_headers=headers,
                raw_body=body
            )
            
            assert report['score'] >= 70  # Should be likely OK
            assert report['risk_level'] == 'likely_ok'
            assert report['domain'] == 'gmail.com'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
