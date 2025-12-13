# Lead Collection & Email Risk Learning System

## Overview
Comprehensive system for discovering business leads from emails, calendar events, and notes, with machine learning capabilities to improve email risk scoring over time.

## Features

### 1. Lead Discovery
- **Sources**: Gmail, Google Calendar, Obsidian Notes
- **Lead Types**: Customers, Investors, Partners
- **Scoring**: 0-100 with confidence levels (0.0-1.0)
- **Scam Protection**: FounderShield integration for risk assessment

### 2. Email Risk Learning
- **Feedback Tracking**: Records user assessments (safe/risky/spam)
- **Pattern Recognition**: Learns from domain patterns and email signals
- **Score Adjustment**: Applies -3 to +3 adjustments based on confidence
- **Accuracy Metrics**: Tracks false positives/negatives
- **Safe Sender Whitelist**: Marks trusted senders

### 3. Deleted Lead Tracking
- **Memory System**: Remembers rejected leads to prevent re-suggestions
- **Reason Tracking**: Records why leads were deleted (not_relevant/spam/etc.)
- **Learning Integration**: Uses deletion patterns to improve future lead scoring

## API Endpoints

### Lead Collection
```bash
# Collect leads from multiple sources
POST /api/leads/collect?days_back=7&sources=email,calendar,notes
```

### Lead Management
```bash
# List all leads
GET /api/leads/list?limit=10&offset=0

# Get specific lead
GET /api/leads/{lead_id}

# Confirm a potential lead
POST /api/leads/{lead_id}/confirm

# Delete a lead (with learning)
DELETE /api/leads/{lead_id}?reason=spam

# Get lead statistics
GET /api/leads/stats/summary
```

### Email Risk Learning
```bash
# Submit feedback on email risk assessment
POST /api/leads/feedback/email-risk
{
  "email_id": "string",
  "sender_email": "string",
  "original_score": 8,
  "original_level": "high",
  "user_assessment": "safe",
  "reason": "Known business partner",
  "signals": "commercial,automated"
}

# Get learning statistics
GET /api/leads/learning/stats
```

### FounderShield Integration
```bash
# Generate email risk report
POST /foundershield/v1/generate-report
{
  "email_address": "sender@example.com",
  "email_content": "Full email text...",
  "headers": {"authentication-results": "..."}
}

# Quick risk check
GET /foundershield/v1/check-email?email=sender@example.com
```

## Daily Automation

### Setup
```bash
# Install cron job for daily collection
./scripts/setup_daily_leads_cron.sh
```

### Configuration
- **Schedule**: Daily at 8:00 AM
- **Days Back**: 1 (collects yesterday's leads)
- **Sources**: email, calendar, notes
- **Log File**: `data/daily_lead_collection.log`

### Monitoring
```bash
# View automation logs
tail -f data/daily_lead_collection.log

# Test manual collection
./scripts/daily_lead_collection.sh

# Remove cron job
crontab -l | grep -v 'daily_lead_collection.sh' | crontab -
```

## Lead Scoring Algorithm

### Base Score (0-100)
- **Pattern Matching**: Keywords and phrases indicating lead type
- **Signal Strength**: Number and quality of detected signals
- **Confidence Level**: 0.0-1.0 based on signal clarity

### FounderShield Risk Assessment
- DNS checks (MX, SPF, DMARC, MTA-STS)
- WHOIS domain age verification
- Email authentication parsing
- Content pattern analysis
- Scam keyword detection

### Learned Adjustments
- **Domain Learning**: -3 to +3 adjustment based on historical feedback
- **Signal Learning**: Pattern recognition from user feedback
- **Confidence Threshold**: Domain patterns >0.7, Signal patterns >0.6

### Final Score Calculation
```
final_score = base_score + foundershield_adjustment + learned_adjustment
risk_level = 'low' (score ≤ 3) | 'medium' (4-7) | 'high' (≥ 8)
```

## Learning System Tables

### email_risk_feedback
Tracks user assessments of email risk scores
- Stores original score vs. user assessment
- Records feedback reasons and signals
- Tracks accuracy over time

### learned_risk_patterns
Stores learned patterns with confidence scores
- Domain-based patterns
- Signal-based patterns
- Confidence calculated from correct/match ratios

### deleted_leads
Prevents re-suggesting rejected leads
- Records contact email, name, company
- Stores deletion reason
- Used to filter future lead collection

## Lead Status Workflow

1. **potential** → Lead discovered, awaiting review
2. **new** → User confirmed, not yet contacted
3. **contacted** → Outreach sent
4. **engaged** → Active conversation
5. **qualified** → Meets criteria
6. **converted** → Successfully closed
7. **archived** → No longer active

## Usage Examples

### Collect Leads from Last Week
```bash
curl -X POST "http://localhost:8008/api/leads/collect?days_back=7&sources=email"
```

### Review Potential Leads
```bash
curl "http://localhost:8008/api/leads/list?status=potential&limit=20"
```

### Confirm a Lead
```bash
curl -X POST "http://localhost:8008/api/leads/lead_example@company.com_123456/confirm"
```

### Delete Spam Lead
```bash
curl -X DELETE "http://localhost:8008/api/leads/lead_spam@fake.com_789012?reason=spam"
```

### Mark Email as Safe
```bash
curl -X POST "http://localhost:8008/api/leads/feedback/email-risk" \
  -H "Content-Type: application/json" \
  -d '{
    "email_id": "abc123",
    "sender_email": "partner@trusted.com",
    "original_score": 8,
    "original_level": "high",
    "user_assessment": "safe",
    "reason": "Known business partner"
  }'
```

### Check Learning Stats
```bash
curl "http://localhost:8008/api/leads/learning/stats"
```

## Benefits

### For Lead Management
- **Automated Discovery**: Finds leads you might miss
- **Risk Protection**: Filters out scams and spam
- **Context Preservation**: Saves conversation history
- **Task Generation**: Creates follow-up actions

### For Email Risk Assessment
- **Continuous Improvement**: Learns from your feedback
- **Personalized Scoring**: Adapts to your business context
- **Reduced False Positives**: Fewer legitimate emails marked as risky
- **Pattern Recognition**: Identifies common characteristics of safe/risky emails

### For Time Management
- **Daily Automation**: No manual work required
- **Prioritized Leads**: Focus on highest-scoring opportunities
- **Deduplication**: Won't suggest deleted leads again
- **Smart Filtering**: Excludes newsletters, automated messages

## Troubleshooting

### No Leads Found
- Check email sources are configured in `config/config.yaml`
- Verify Gmail API credentials in `config/credentials.yaml`
- Increase `days_back` parameter
- Check logs: `tail -f dashboard.log | grep lead_collector`

### High False Positive Rate
- Submit feedback via `/api/leads/feedback/email-risk`
- Mark legitimate emails as safe
- System will learn and adjust future scoring
- Check learning stats to verify feedback is being recorded

### Deleted Lead Re-appearing
- Verify deletion was successful: check learning stats
- Check database: `SELECT * FROM deleted_leads WHERE contact_email = 'email@example.com'`
- Restart server to ensure learning system is loaded

### Cron Job Not Running
- Verify installation: `crontab -l`
- Check logs: `tail -f data/daily_lead_collection.log`
- Verify server is running when cron executes
- Test manually: `./scripts/daily_lead_collection.sh`

## Database Schema

### leads Table
```sql
- lead_id (PRIMARY KEY)
- source (email/calendar/notes)
- lead_type (customer/investor/partner)
- contact_name, contact_email, company
- status (potential/new/contacted/engaged/qualified/converted/archived)
- score (0-100), confidence (0.0-1.0)
- signals (comma-separated patterns detected)
- context (original text)
- foundershield_score, risk_level
- conversation_count
- next_action
- metadata (JSON)
- timestamps
```

### lead_tasks Table
```sql
- task_id (PRIMARY KEY)
- lead_id (FOREIGN KEY)
- task_type (email/call/meeting/research/follow_up/proposal)
- description
- due_date
- status (pending/completed/cancelled)
- priority (low/medium/high)
- timestamps
```

### lead_interactions Table
```sql
- interaction_id (PRIMARY KEY)
- lead_id (FOREIGN KEY)
- interaction_type (email/call/meeting/note)
- content
- direction (inbound/outbound)
- sentiment (positive/neutral/negative)
- timestamp
```

## Future Enhancements

- [ ] LinkedIn integration for lead enrichment
- [ ] Automatic email drafting for follow-ups
- [ ] CRM integration (HubSpot, Salesforce)
- [ ] Meeting scheduling automation
- [ ] AI-powered lead qualification questions
- [ ] Sentiment analysis for email conversations
- [ ] Pipeline forecasting based on lead patterns
