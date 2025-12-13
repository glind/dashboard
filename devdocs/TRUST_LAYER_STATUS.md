# Trust Layer Implementation Status

## ✅ Completed Components

### 1. Database Schema
**File**: `src/database.py` (lines 445-530)

**Tables Created**:
- `trust_reports` - Main trust report storage
- `trust_claims` - Individual claims from verifiers
- `provider_accounts` - OAuth connections (LinkedIn, etc.)
- `verification_requests` - External verification tracking
- `trust_audit_log` - Audit trail

**Indexes**: Optimized for thread_id, created_at, risk_level lookups

### 2. Core Data Models
**File**: `src/trust_layer/models.py`

**Classes**:
- `VerificationContext` - Input data for plugins
- `TrustClaim` - Attestation from a verifier
- `Finding` - Individual issue/red flag
- `TrustReport` - Complete trust analysis
- `RiskLevel` - Enum (likely_ok, caution, high_risk)
- `FindingSeverity` - Enum (low, medium, high)

### 3. Plugin Architecture
**File**: `src/trust_layer/plugin_registry.py`

**Classes**:
- `VerifierPlugin` - Abstract base class for all plugins
- `PluginRegistry` - Central plugin management
  - Register/unregister plugins
  - Gather signals from all enabled plugins
  - Health checks
  - Plugin listing

### 4. Scoring Engine
**File**: `src/trust_layer/scoring_engine.py`

**Features**:
- Transparent scoring algorithm (start at 100, apply deltas)
- Configurable scoring rules
- Risk level determination
- Summary generation
- Complete trust report creation

**Default Rules** (18 total):
- Authentication: SPF/DKIM/DMARC failures (-20 each)
- Domain: Age < 540 days (-25), Lookalike (-30)
- Content: Pay-to-pitch (-35), Urgency (-15), etc.
- URLs: Reputation flagged (-25)

### 5. Email Authentication Plugin
**File**: `src/trust_layer/plugins/email_auth.py`

**Features**:
- Parse Authentication-Results header
- Extract SPF, DKIM, DMARC results
- Domain alignment checking
- Findings generation for failures

### 6. Documentation
**File**: `src/trust_layer/README.md`

Complete documentation including:
- Architecture overview
- API endpoints
- Environment variables
- Plugin development guide
- Security & compliance notes
- Testing instructions

## 🔄 Next Steps (To Complete Full System)

### Immediate Priority

1. **Create Additional Plugins** (1-2 hours each):
   - `dns_records.py` - MX, SPF, DMARC, MTA-STS checks
   - `domain_whois.py` - Domain age verification
   - `content_heuristics.py` - Scam pattern detection
   - `url_reputation.py` - Safe Browsing/VirusTotal integration

2. **Create Report Generator** (1 hour):
   - `report_generator.py` - Orchestrates plugin execution
   - Handles async plugin calls
   - Saves reports to database
   - Error handling and retries

3. **Create API Endpoints** (2 hours):
   - `api/endpoints.py` - FastAPI routes
   - GET /v1/trust/reports/{thread_id}
   - POST /v1/trust/reports (create new)
   - POST /v1/trust/reports/{id}/verification-requests
   - GET /v1/trust/providers

4. **Create Background Job System** (2 hours):
   - Auto-generate reports for new emails
   - Queue-based processing
   - Job status tracking

5. **Create LinkedIn OAuth** (3 hours):
   - OAuth start/callback endpoints
   - Token storage and encryption
   - Verification request flow

6. **Create UI Components** (4 hours):
   - Trust badge on email list
   - Detailed trust report modal
   - Verification request UI
   - Provider connection settings

7. **Add Tests** (2 hours):
   - Unit tests for scoring
   - Plugin tests with mocks
   - Integration test

### How to Continue

#### Step 1: Create DNS Records Plugin
```python
# src/trust_layer/plugins/dns_records.py
import dns.resolver
from ..plugin_registry import VerifierPlugin

class DNSRecordsPlugin(VerifierPlugin):
    # Check MX, SPF, DMARC, MTA-STS records
    pass
```

#### Step 2: Create Report Generator
```python
# src/trust_layer/report_generator.py
from .plugin_registry import get_registry
from .scoring_engine import ScoringEngine

class ReportGenerator:
    async def generate_report(self, context: VerificationContext):
        # 1. Gather claims from all plugins
        # 2. Gather findings from all plugins  
        # 3. Calculate score
        # 4. Save to database
        pass
```

#### Step 3: Create API Endpoints
```python
# src/trust_layer/api/endpoints.py
from fastapi import APIRouter

router = APIRouter(prefix="/v1/trust", tags=["trust"])

@router.get("/reports/{thread_id}")
async def get_report(thread_id: str):
    # Fetch from database or generate if missing
    pass
```

#### Step 4: Integrate with Email Flow
```python
# In src/main.py or collectors/gmail_collector.py
from trust_layer.report_generator import ReportGenerator

# After fetching email:
generator = ReportGenerator()
report = await generator.generate_report(context)
```

## 📋 Quick Start Guide (Once Complete)

### 1. Initialize Database
```bash
python scripts/init_trust_layer.py
```

### 2. Configure Environment
```bash
# .env
TRUST_LAYER_ENABLED=true
GOOGLE_SAFE_BROWSING_API_KEY=optional
VIRUSTOTAL_API_KEY=optional
```

### 3. Register Plugins
```python
from trust_layer.plugins.email_auth import EmailAuthPlugin
from trust_layer import get_registry

registry = get_registry()
registry.register(EmailAuthPlugin())
```

### 4. Generate Report
```python
from trust_layer import VerificationContext
from trust_layer.report_generator import ReportGenerator

context = VerificationContext(
    message_id=email['id'],
    thread_id=email['thread_id'],
    sender_email=email['from'],
    sender_domain=extract_domain(email['from']),
    raw_headers=email['headers'],
    body_text=email['body']
)

generator = ReportGenerator()
report = await generator.generate_report(context)

print(f"Score: {report.score}")
print(f"Risk: {report.risk_level}")
```

## 🔐 Security Considerations

### Already Implemented:
- ✅ Encrypted token storage schema
- ✅ Audit logging schema
- ✅ No full email body storage by default
- ✅ OAuth-only for external providers
- ✅ Transparent scoring rules

### To Implement:
- Actual token encryption (use `cryptography` library)
- Rate limiting on verification endpoints
- CSRF protection on OAuth callbacks
- Input validation and sanitization

## 📊 Scoring Example

```
Start: 100 points
- Domain age < 540 days: -25 → 75
- DMARC missing: -10 → 65
- Pay-to-pitch language: -35 → 30
Final: 30/100 (HIGH_RISK)
```

## 🧪 Testing Strategy

### Unit Tests
```python
def test_scoring_engine():
    engine = ScoringEngine()
    findings = [
        Finding(rule_id='spf_fail', points_delta=-20),
        Finding(rule_id='domain_age_new', points_delta=-25)
    ]
    score = engine.calculate_score(findings)
    assert score == 55  # 100 - 20 - 25
```

### Integration Test
```python
async def test_full_report_generation():
    context = create_test_context()
    registry = get_registry()
    registry.register(EmailAuthPlugin())
    
    generator = ReportGenerator()
    report = await generator.generate_report(context)
    
    assert report.score >= 0 and report.score <= 100
    assert report.risk_level in RiskLevel
```

## 📁 File Structure

```
src/trust_layer/
├── __init__.py ✅
├── README.md ✅
├── models.py ✅
├── plugin_registry.py ✅
├── scoring_engine.py ✅
├── report_generator.py ⏳
├── database_ops.py ⏳
├── plugins/
│   ├── __init__.py ⏳
│   ├── email_auth.py ✅
│   ├── dns_records.py ⏳
│   ├── domain_whois.py ⏳
│   ├── content_heuristics.py ⏳
│   ├── url_reputation.py ⏳
│   └── linkedin_verified.py ⏳
└── api/
    ├── __init__.py ⏳
    └── endpoints.py ⏳
```

## 🚀 Deployment Notes

### Dependencies to Add
```
# requirements.txt additions
dnspython>=2.0.0
python-whois>=0.8.0
requests>=2.28.0
cryptography>=40.0.0
```

### Database Migration
The trust layer tables are automatically created on next app startup.

### Configuration
Add to existing config.yaml:
```yaml
trust_layer:
  enabled: true
  ruleset_version: "1.0"
  plugins:
    email_auth: true
    dns_records: true
    content_heuristics: true
```

## 💡 Usage Examples

### Check Email Risk
```python
# In your email handler
from trust_layer.report_generator import ReportGenerator

async def process_email(email_data):
    # Generate trust report
    report = await generator.generate_report_from_email(email_data)
    
    if report.risk_level == RiskLevel.HIGH_RISK:
        # Show warning in UI
        logger.warning(f"High risk email detected: {report.summary}")
```

### Request LinkedIn Verification
```python
# User clicks "Request Verification" button
verification_req = await create_verification_request(
    report_id=report.report_id,
    provider="linkedin",
    target_email=sender_email
)

# Send email to sender with verification link
await send_verification_email(
    to=sender_email,
    link=verification_req.verification_url
)
```

## ⚖️ Compliance Notes

### GDPR/Privacy:
- Minimal data retention (configurable)
- User can request data deletion
- Audit log for all processing

### LinkedIn Policy:
- OAuth 2.0 only (no scraping)
- User consent required
- Limited to profile endpoints
- Rate limits respected

### CAN-SPAM:
- No automated email sending
- Reply templates only (user must send)
- Unsubscribe honored

---

**Implementation Time Estimate**: 20-30 hours total
- Core framework (DONE): ~8 hours
- Remaining plugins: ~6 hours
- API + Background jobs: ~6 hours
- UI components: ~6 hours
- Tests + docs: ~4 hours

**Current Progress**: ~35% complete (core foundation ready)
