# Lead Collection System 🎯

Automated lead discovery from your communications - finds customers, investors, and partners from emails, calendar, and notes.

## Features

### 📧 Email Lead Discovery
- Analyzes Gmail for customer inquiries, investor interest, and partnership opportunities
- Detects intent signals (pricing questions, demo requests, investment interest)
- Uses FounderShield to filter out scams and verify legitimacy
- Extracts contact information and company details automatically

### 📅 Calendar Intelligence
- Identifies leads from scheduled meetings
- Tracks upcoming conversations with prospects
- Creates prep tasks for important meetings

### 📝 Notes Integration
- Finds contact information in meeting notes
- Discovers follow-up opportunities
- Captures offline lead sources

### 🤖 Automated Task Generation
- Creates follow-up tasks automatically
- Prioritizes based on lead score and urgency
- Suggests next actions (demo, pricing, intro call)

### 🔗 CRM Export
- Export to generic CRM format
- Supports HubSpot, Salesforce, Pipedrive
- Includes all context and conversation history

## How It Works

### Lead Classification

**Customer Signals:**
- "Interested in your product/service"
- "Pricing" or "quote" or "demo"
- "How much does it cost?"
- "Looking for a solution/vendor"
- Budget discussions

**Investor Signals:**
- "Investment" or "funding" or "capital"
- "VC" or "venture capital" or "angel"
- "Pitch deck" or "cap table"
- "Traction" or "metrics"
- Term sheet discussions

**Partner Signals:**
- "Partnership" or "collaboration"
- "Integration" or "API"
- "White label" or "resell"
- "Co-marketing" opportunities

### Lead Scoring

Leads are scored 0-100 based on:
- **Signal strength** (40-90 points)
- **Number of matching signals** (+15 per signal, up to 50)
- **Urgency indicators** (+10 for "ASAP", "urgent", etc.)
- **FounderShield risk check** (-30% for caution leads)
- **Engagement level** (+5 per interaction)

### Risk Verification

Every email lead is verified with FounderShield:
- Domain age and DNS security
- Email authentication (SPF, DKIM, DMARC)
- Content analysis for scam patterns
- Scams are automatically filtered out

## API Usage

### Collect Leads from All Sources

```bash
POST /api/leads/collect?days_back=30&sources=email,calendar,notes
```

**Response:**
```json
{
  "success": true,
  "leads_collected": 15,
  "statistics": {
    "total_collected": 15,
    "by_type": {
      "customer": 8,
      "investor": 4,
      "partner": 3
    },
    "by_source": {
      "email": 10,
      "calendar": 3,
      "notes": 2
    },
    "by_risk": {
      "likely_ok": 12,
      "caution": 3
    }
  }
}
```

### List All Leads

```bash
GET /api/leads/list?lead_type=customer&min_score=70
```

**Response:**
```json
{
  "success": true,
  "count": 5,
  "leads": [
    {
      "lead_id": "lead_john@acmecorp.com_1702492800",
      "source": "email",
      "lead_type": "customer",
      "contact_name": "John Smith",
      "contact_email": "john@acmecorp.com",
      "company": "Acme Corp",
      "status": "new",
      "score": 85,
      "confidence": 0.8,
      "signals": ["pricing", "demo", "interested in product"],
      "context": "Subject: Interested in your SaaS platform...",
      "first_seen": "2024-12-13T10:00:00",
      "last_contact": "2024-12-13T10:00:00",
      "conversation_count": 1,
      "foundershield_score": 92,
      "risk_level": "likely_ok",
      "next_action": "Send pricing information and schedule demo"
    }
  ]
}
```

### Get Lead Details

```bash
GET /api/leads/{lead_id}
```

Returns full lead profile including:
- Contact information
- All interactions
- Associated tasks
- Conversation history

### Create Task for Lead

```bash
POST /api/leads/{lead_id}/task
Content-Type: application/json

{
  "lead_id": "lead_john@acmecorp.com_1702492800",
  "task_type": "follow_up",
  "description": "Send demo link and pricing sheet",
  "priority": "high",
  "due_days": 2
}
```

### Update Lead Status

```bash
POST /api/leads/{lead_id}/status?status=contacted
```

Statuses:
- `new` - Just discovered
- `contacted` - Initial outreach sent
- `qualified` - Verified as real opportunity
- `converted` - Deal closed
- `closed` - No longer pursuing

### Export to CRM

```bash
POST /api/leads/export
Content-Type: application/json

{
  "lead_id": "lead_john@acmecorp.com_1702492800",
  "crm_type": "hubspot"
}
```

**Response:**
```json
{
  "success": true,
  "crm_type": "hubspot",
  "data": {
    "contact": {
      "first_name": "John",
      "last_name": "Smith",
      "email": "john@acmecorp.com",
      "company": "Acme Corp"
    },
    "deal": {
      "title": "Customer - John Smith",
      "stage": "new",
      "priority": "high"
    },
    "notes": "Interested in SaaS platform, asked about pricing...",
    "custom_fields": {
      "lead_score": 85,
      "lead_type": "customer",
      "signals": "pricing,demo,interested in product"
    }
  }
}
```

### Get Statistics

```bash
GET /api/leads/stats/summary
```

**Response:**
```json
{
  "success": true,
  "total_leads": 42,
  "high_priority_leads": 12,
  "recent_leads_7d": 8,
  "by_type": {
    "customer": 25,
    "investor": 10,
    "partner": 7
  },
  "by_status": {
    "new": 15,
    "contacted": 18,
    "qualified": 6,
    "converted": 3
  },
  "by_source": {
    "email": 30,
    "calendar": 8,
    "notes": 4
  }
}
```

## Integration Examples

### Daily Lead Collection

Run this daily to discover new leads:

```bash
curl -X POST "http://localhost:8008/api/leads/collect?days_back=1&sources=email,calendar"
```

### High-Priority Lead Alert

Get leads that need immediate attention:

```bash
curl "http://localhost:8008/api/leads/list?min_score=75&status=new"
```

### Weekly Lead Review

Export all qualified leads for CRM update:

```bash
# Get all qualified leads
curl "http://localhost:8008/api/leads/list?status=qualified"

# Export each to your CRM
curl -X POST "http://localhost:8008/api/leads/export" \
  -H "Content-Type: application/json" \
  -d '{"lead_id": "lead_xxx", "crm_type": "hubspot"}'
```

## Database Schema

### leads table
```sql
- lead_id (PK): Unique identifier
- source: email, calendar, notes
- lead_type: customer, investor, partner, other
- contact_name: Full name
- contact_email: Email address
- company: Company name
- status: new, contacted, qualified, converted, closed
- score: 0-100 lead quality score
- confidence: 0-1 confidence in classification
- signals: Comma-separated indicators
- context: Original message/note content
- first_seen: When first discovered
- last_contact: Most recent interaction
- conversation_count: Number of interactions
- foundershield_score: Email security score
- risk_level: likely_ok, caution, high_risk
- next_action: Suggested next step
```

### lead_interactions table
```sql
- interaction_id (PK)
- lead_id (FK)
- interaction_type: email_received, email_sent, meeting, call
- direction: inbound, outbound
- content_summary: Brief description
- timestamp: When it occurred
- source_id: Original message/event ID
```

### lead_tasks table
```sql
- task_id (PK)
- lead_id (FK)
- task_type: follow_up, demo, pricing, meeting_prep
- description: What needs to be done
- status: pending, completed, cancelled
- priority: high, medium, low
- due_date: When it's due
- completed_at: When completed (if done)
```

## Real-World Examples

### Example 1: Customer Inquiry

**Email Received:**
```
From: Sarah Chen <sarah@techstartup.io>
Subject: Interested in your analytics platform

Hi there,

We're looking for a better analytics solution for our SaaS product.
Can you share pricing information and schedule a demo?

Thanks,
Sarah
```

**Lead Created:**
```json
{
  "lead_type": "customer",
  "score": 85,
  "signals": ["pricing", "demo", "interested in product"],
  "next_action": "Send pricing information and schedule demo",
  "task_created": "Send demo link and pricing sheet (due in 2 days)"
}
```

### Example 2: Investor Outreach

**Email Received:**
```
From: Michael Partner <michael@seedvc.com>
Subject: Investment opportunity

Hello,

I'm a partner at Seed VC. We're interested in learning more about
your company and potential investment opportunities. Would you be
available for a call next week?

Best regards,
Michael
```

**Lead Created:**
```json
{
  "lead_type": "investor",
  "score": 90,
  "signals": ["investment", "VC", "partner"],
  "next_action": "Send company overview and schedule investor call",
  "task_created": "Prepare investor materials and schedule call (due in 3 days)"
}
```

### Example 3: Meeting Follow-up

**Calendar Event:**
```
Meeting: Product Discussion with Acme Corp
Attendees: john@acmecorp.com
Description: Discuss integration possibilities
```

**Lead Created:**
```json
{
  "source": "calendar",
  "lead_type": "partner",
  "score": 75,
  "status": "contacted",
  "signals": ["integration", "discussion"],
  "next_action": "Prepare for scheduled meeting",
  "task_created": "Prepare integration docs for meeting (due in 1 day)"
}
```

## Best Practices

1. **Run collection daily** to catch fresh leads quickly
2. **Review high-score leads** (75+) immediately
3. **Update lead status** as you progress through conversations
4. **Export to CRM weekly** to keep systems in sync
5. **Create custom tasks** for unique follow-up needs
6. **Check FounderShield scores** - don't waste time on scams

## Future Enhancements

- [ ] AI-powered response suggestions
- [ ] Automatic email drafting for common scenarios
- [ ] LinkedIn profile enrichment
- [ ] Company size and funding data integration
- [ ] Predictive lead scoring with ML
- [ ] Automated follow-up sequences
- [ ] Integration with more CRMs (Monday.com, Airtable)
- [ ] Slack/Teams notifications for hot leads
- [ ] Lead qualification chatbot

## Support

For issues or questions, check the logs:
```bash
tail -f /Users/greglind/Projects/me/dashboard/dashboard.log | grep -i "lead"
```
