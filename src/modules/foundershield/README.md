# FounderShield Email Risk Analysis

Comprehensive email and domain risk scoring system that protects founders from scams and phishing attempts.

## Features

### 🔍 DNS Security Checks
- **MX Records**: Validates mail server configuration
- **SPF Records**: Checks Sender Policy Framework
- **DMARC**: Verifies domain-based message authentication
- **MTA-STS**: Checks for SMTP MTA Strict Transport Security
- **TLSRPT**: Verifies TLS reporting configuration

### 📅 Domain Age Analysis
- WHOIS lookup for domain creation date
- Flags domains < 18 months old (high risk)
- Handles privacy-protected WHOIS data safely

### ✉️ Email Authentication
- Parses `Authentication-Results` header
- Checks SPF pass/fail status
- Validates DKIM signatures
- Verifies DMARC policy compliance

### 🎯 Content Analysis
- **Scam Pattern Detection**:
  - "Pay for due diligence/risk mitigation" (-35 points)
  - "What is your budget?" (-10 points)
  - Urgency/pressure tactics (-15 points)
  - Account verification requests (-20 points)
  
- **Suspicious URL Detection**:
  - Google Drive links (medium risk)
  - Forbes Councils links (medium risk)
  - Self-hosted testimonial pages (low risk)
  - URL shorteners (high risk)
  - IP address URLs (high risk)

### 📊 Risk Scoring

**Scoring System** (starts at 100, deductions for issues):
- Domain age < 18 months: -25 points
- Missing DMARC: -10 points
- No MX records: -30 points
- SPF/DKIM/DMARC auth failures: -20 points each
- Scam content patterns: -10 to -35 points
- Suspicious URLs: -8 to -15 points

**Risk Levels**:
- `likely_ok`: Score ≥ 70 (safe to proceed)
- `caution`: Score 40-69 (review carefully)
- `high_risk`: Score < 40 (likely scam/phishing)

## API Usage

### Generate Risk Report

```bash
POST /v1/report
Content-Type: application/json

{
  "email": "john@globalinvestorsnetworks.com",
  "raw_headers": "Authentication-Results: spf=fail dkim=fail...",
  "raw_body": "Dear investor, please pay for our due diligence service..."
}
```

**Response**:
```json
{
  "score": 25,
  "risk_level": "high_risk",
  "domain": "globalinvestorsnetworks.com",
  "email": "john@globalinvestorsnetworks.com",
  "findings": [
    {
      "id": "YOUNG_DOMAIN",
      "severity": "high",
      "details": "Domain is only 120 days old (< 18 months)"
    },
    {
      "id": "DMARC_MISSING",
      "severity": "high",
      "details": "Domain has no DMARC policy configured"
    },
    {
      "id": "SPF_FAIL",
      "severity": "critical",
      "details": "Email failed SPF authentication"
    },
    {
      "id": "PAY_FOR_SERVICE",
      "severity": "high",
      "details": "Suspicious pattern detected: PAY_FOR_SERVICE"
    }
  ],
  "signals": {
    "dns": {
      "mx_records": [{"priority": 10, "host": "mail.example.com"}],
      "spf_record": null,
      "dmarc_record": null,
      "mta_sts": false,
      "tlsrpt": false
    },
    "whois": {
      "created_date": "2024-08-15T00:00:00",
      "registrar": "NameCheap",
      "available": false
    },
    "auth_results": {
      "spf": "fail",
      "dkim": "fail",
      "dmarc": "none"
    },
    "content": {
      "suspicious_urls": [],
      "scam_patterns": ["PAY_FOR_SERVICE"]
    }
  },
  "timestamp": "2024-12-13T10:30:00"
}
```

## Integration with Existing Email System

### Option 1: Automatic Risk Checking (Recommended)

Integrate with `GmailCollector` to automatically check all emails:

```python
# In src/collectors/gmail_collector.py

from modules.foundershield.service import FounderShieldService

class GmailCollector:
    def __init__(self, settings):
        self.settings = settings
        self.foundershield = FounderShieldService()
    
    async def _get_email_details(self, message_id):
        email_data = # ... existing code ...
        
        # Add FounderShield risk analysis
        sender = email_data.get('sender', '')
        headers = email_data.get('raw_headers', '')
        body = email_data.get('body', '')
        
        risk_report = await self.foundershield.generate_report(
            email_address=sender,
            raw_headers=headers,
            raw_body=body
        )
        
        email_data['foundershield_score'] = risk_report['score']
        email_data['foundershield_risk'] = risk_report['risk_level']
        email_data['foundershield_findings'] = risk_report['findings']
        
        return email_data
```

### Option 2: Enhanced EmailRiskChecker

Extend the existing `EmailRiskChecker` to use FounderShield:

```python
# In src/processors/email_risk_checker.py

from modules.foundershield.service import FounderShieldService

class EmailRiskChecker:
    def __init__(self, db=None):
        self.db = db or DatabaseManager()
        self.foundershield = FounderShieldService()
    
    async def analyze_email(self, email_data):
        # Existing basic checks...
        basic_analysis = self._basic_checks(email_data)
        
        # Add FounderShield deep analysis
        sender = email_data.get('sender', '')
        headers = email_data.get('raw_headers', '')
        body = email_data.get('body', '')
        
        fs_report = await self.foundershield.generate_report(
            email_address=sender,
            raw_headers=headers,
            raw_body=body
        )
        
        # Combine scores
        combined_score = (basic_analysis['risk_score'] + (100 - fs_report['score']) / 10) / 2
        
        return {
            'risk_score': combined_score,
            'foundershield': fs_report,
            'basic_checks': basic_analysis
        }
```

### Option 3: Standalone Microservice

Mount the FounderShield router in your main FastAPI app:

```python
# In src/main.py

from modules.foundershield.endpoints import router as foundershield_router

app.include_router(foundershield_router, prefix="/foundershield")
```

Then call it from anywhere:
```bash
curl -X POST http://localhost:8008/foundershield/v1/report \
  -H "Content-Type: application/json" \
  -d '{
    "email": "suspicious@newdomain.xyz",
    "raw_body": "Please pay for our investor verification service"
  }'
```

## Testing

Run unit tests:
```bash
cd src/modules/foundershield
pytest test_foundershield.py -v
```

Test specific scenarios:
```bash
# Test DNS parsing
pytest test_foundershield.py::TestFounderShieldService::test_check_dns_valid_domain -v

# Test scoring
pytest test_foundershield.py::TestFounderShieldService::test_calculate_risk_level_high_risk -v

# Test content analysis
pytest test_foundershield.py::TestFounderShieldService::test_analyze_content_pay_for_service -v
```

## Dependencies

Add to `requirements.txt`:
```
dnspython>=2.4.0
python-whois>=0.8.0
```

## Example Use Cases

### 1. Founder Receives Investment Email
```
From: john@globalinvestorsnetwork.com
Subject: Investment Opportunity - $5M Available

Dear Founder,

We have reviewed your company and are interested in investing $5M.
To proceed, please pay $5,000 for our due diligence service.

Click here to review our testimonials: https://bit.ly/abc123
```

**FounderShield Analysis**:
- Score: 15/100 (high_risk)
- Flags: Young domain, no DMARC, pay-for-service scam, URL shortener
- Recommendation: ⚠️ **DO NOT RESPOND - Likely Scam**

### 2. Legitimate VC Email
```
From: partner@sequoiacap.com
Subject: Follow up from YC Demo Day

Hi there,

Great meeting you at Demo Day yesterday. I'd love to schedule
a call next week to discuss your company further.

Best,
Partner @ Sequoia Capital
```

**FounderShield Analysis**:
- Score: 95/100 (likely_ok)
- Flags: None - established domain, proper auth, clean content
- Recommendation: ✅ **Safe to Respond**

## Configuration

Adjust risk thresholds in `service.py`:
```python
class FounderShieldService:
    RISK_LIKELY_OK = 70    # Adjust for stricter/looser filtering
    RISK_CAUTION = 40
    RISK_HIGH = 0
```

## Future Enhancements

- [ ] Machine learning model for pattern detection
- [ ] Integration with email reputation services (Spamhaus, etc.)
- [ ] Historical sender tracking
- [ ] Behavioral analysis across multiple emails
- [ ] Real-time alerting for high-risk emails
- [ ] Automatic response templates for scams

## License

Part of the Personal Dashboard project - see main LICENSE.md
