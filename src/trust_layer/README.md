# Trust Layer - Anti-Scam Email Analysis

## Overview

The Trust Layer is a comprehensive email security system that evaluates inbound emails for potential scams, phishing, and fraud. It provides a transparent, plugin-based architecture for analyzing email authentication, content patterns, sender reputation, and domain validity.

## Features

- **Transparent Scoring**: Clear, explainable scoring from 0-100 with documented rules
- **Plugin Architecture**: Modular verifiers that can be enabled/disabled
- **Email Authentication**: SPF, DKIM, DMARC parsing and validation
- **Domain Analysis**: Age verification, WHOIS data, DNS records
- **Content Heuristics**: Pattern matching for common scam tactics
- **URL Reputation**: Integration with Safe Browsing, VirusTotal, URLhaus
- **External Verification**: Request verification from senders (e.g., LinkedIn)
- **Compliance First**: No scraping, no unauthorized data access

## Risk Levels

- **Likely OK** (80-100): Email appears legitimate
- **Caution** (55-79): Some concerns warrant attention
- **High Risk** (0-54): Multiple red flags detected

## Architecture

```
trust_layer/
├── models.py              # Data models (TrustReport, TrustClaim, Finding)
├── plugin_registry.py     # Plugin management system
├── scoring_engine.py      # Transparent scoring algorithm
├── report_generator.py    # Trust report creation
├── plugins/               # Verifier plugins
│   ├── email_auth.py      # SPF/DKIM/DMARC verification
│   ├── dns_records.py     # DNS checks (MX, SPF, DMARC, MTA-STS)
│   ├── domain_whois.py    # Domain age and registration
│   ├── content_heuristics.py  # Scam pattern detection
│   ├── url_reputation.py  # URL safety checks
│   └── linkedin_verified.py   # LinkedIn OAuth integration
└── api/
    └── endpoints.py       # REST API for trust reports
```

## Environment Variables

```bash
# Core settings
TRUST_LAYER_ENABLED=true
TRUST_LAYER_RULESET_VERSION=1.0

# Google Safe Browsing (optional)
GOOGLE_SAFE_BROWSING_API_KEY=your_key_here

# VirusTotal (optional)
VIRUSTOTAL_API_KEY=your_key_here

# LinkedIn OAuth (for verified status)
LINKEDIN_CLIENT_ID=your_client_id
LINKEDIN_CLIENT_SECRET=your_client_secret
LINKEDIN_REDIRECT_URI=http://localhost:8008/v1/providers/linkedin/oauth/callback

# Plugin Configuration
PLUGIN_EMAIL_AUTH_ENABLED=true
PLUGIN_DNS_RECORDS_ENABLED=true
PLUGIN_DOMAIN_WHOIS_ENABLED=true
PLUGIN_CONTENT_HEURISTICS_ENABLED=true
PLUGIN_URL_REPUTATION_ENABLED=true
PLUGIN_LINKEDIN_ENABLED=false
```

## Scoring Rules

### Authentication Issues
- Missing DMARC: -10 points
- SPF/DKIM/DMARC failure: -20 points each
- Domain misalignment: -15 points

### Domain Issues
- Domain age < 540 days: -25 points
- Domain lookalike detected: -30 points

### Content Patterns
- Pay-to-pitch language: -35 points
- Budget anchoring: -10 points
- Urgency pressure: -15 points
- Authority garnish: -10 points

### URL & Attachments
- URL flagged by reputation service: -25 points
- Suspicious attachment: -15 points

## API Endpoints

### Get Trust Report
```http
GET /v1/trust/reports/{thread_id}
```

Returns the trust report for an email thread.

### Create Trust Report
```http
POST /v1/trust/reports
Content-Type: application/json

{
  "message_id": "msg_123",
  "thread_id": "thread_456"
}
```

### Request Verification
```http
POST /v1/trust/reports/{report_id}/verification-requests
Content-Type: application/json

{
  "provider": "linkedin",
  "target_email": "sender@example.com"
}
```

### List Providers
```http
GET /v1/trust/providers
```

Returns available verification providers and their status.

## Plugin Development

### Creating a Custom Plugin

```python
from trust_layer import VerifierPlugin, VerificationContext, TrustClaim

class CustomVerifier(VerifierPlugin):
    @property
    def name(self) -> str:
        return "custom_verifier"
    
    @property
    def description(self) -> str:
        return "Custom verification logic"
    
    async def gather_signals(self, context: VerificationContext) -> List[TrustClaim]:
        claims = []
        
        # Your verification logic here
        if context.sender_domain == "trusted.com":
            claims.append(TrustClaim(
                provider=self.name,
                claim_type="trusted_domain",
                subject=context.sender_domain,
                issuer=self.name,
                confidence=0.9
            ))
        
        return claims
```

### Registering a Plugin

```python
from trust_layer import get_registry

registry = get_registry()
registry.register(CustomVerifier())
```

## Security & Compliance

### Data Handling
- Email content is processed in-memory only
- Headers and metadata are stored for analysis
- Full email bodies are NOT stored by default
- All API tokens are encrypted at rest

### LinkedIn Integration
- Uses official OAuth 2.0 flow only
- NO scraping or automation
- User consent required for all data access
- Only accesses data explicitly authorized
- Verification requests are opt-in

### Audit Logging
All trust system actions are logged:
- Provider connections/disconnections
- Verification requests created
- Trust reports generated
- Score changes and reasons

## Testing

### Run Unit Tests
```bash
pytest tests/trust_layer/test_scoring.py
pytest tests/trust_layer/test_plugins.py
```

### Run Integration Tests
```bash
pytest tests/trust_layer/test_integration.py
```

## Local Development

### Setup
```bash
# Install dependencies
pip install -r requirements.txt

# Run database migrations
python scripts/init_trust_layer.py

# Start the server
./ops/startup.sh
```

### Testing a Plugin
```python
from trust_layer import VerificationContext, get_registry

# Create test context
context = VerificationContext(
    message_id="test_123",
    thread_id="thread_456",
    sender_email="test@example.com",
    sender_domain="example.com"
)

# Get plugin and test
registry = get_registry()
plugin = registry.get("email_auth")
claims = await plugin.gather_signals(context)
```

## Roadmap

### Phase 1 (Current)
- ✅ Core plugin architecture
- ✅ Email authentication verification
- ✅ DNS record checks
- ✅ Content heuristics
- ✅ Scoring engine
- ⏳ Basic UI

### Phase 2
- ⏳ URL reputation checks
- ⏳ LinkedIn OAuth integration
- ⏳ Advanced pattern learning
- ⏳ Sender reputation database

### Phase 3
- ⏳ Additional verification providers
- ⏳ Machine learning enhancements
- ⏳ Automated response suggestions
- ⏳ CRM integrations

## Support

For questions or issues:
1. Check the documentation in `/devdocs/trust-layer/`
2. Review the API docs at `http://localhost:8008/docs`
3. File an issue on GitHub

## License

BSL 1.1 → Apache 2.0 (converts November 5, 2027)
