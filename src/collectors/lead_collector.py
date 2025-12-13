"""
Lead Collector - Discovers customer and investor leads from communications

Analyzes emails, calendar events, and notes to identify potential leads:
- Customers showing interest in products/services
- Investors reaching out about funding
- Partners proposing collaborations
- High-value contacts for outreach

Integrates with FounderShield to filter out scams and verify legitimacy.
"""

import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, asdict
from collections import defaultdict
import asyncio

from database import DatabaseManager
from modules.foundershield.service import FounderShieldService
from processors.email_risk_learning import EmailRiskLearningSystem

logger = logging.getLogger(__name__)


@dataclass
class Lead:
    """A verified lead from communications."""
    lead_id: str
    source: str  # 'email', 'calendar', 'notes'
    lead_type: str  # 'customer', 'investor', 'partner', 'other'
    contact_name: str
    contact_email: str
    company: Optional[str]
    status: str  # 'new', 'contacted', 'qualified', 'converted', 'closed'
    score: int  # 0-100
    confidence: float  # 0-1
    signals: List[str]
    context: str
    first_seen: datetime
    last_contact: datetime
    conversation_count: int
    foundershield_score: Optional[int]
    risk_level: Optional[str]
    next_action: Optional[str]
    tasks: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class LeadCollector:
    """Collects and qualifies leads from multiple communication sources."""
    
    # Lead type indicators
    CUSTOMER_SIGNALS = [
        r'interested in.*(?:product|service|solution)',
        r'pricing|quote|demo|trial',
        r'how (?:much|does it cost)',
        r'can you help.*with',
        r'looking for.*(?:vendor|solution|tool)',
        r'evaluate|assessment|comparing',
        r'need.*(?:asap|urgently|soon)',
        r'budget',
        r'purchase|buy|subscription'
    ]
    
    INVESTOR_SIGNALS = [
        r'invest(?:ment|or|ing)',
        r'funding|round|capital',
        r'VC|venture capital|angel',
        r'valuation|equity|shares',
        r'pitch deck|cap table',
        r'traction|metrics|growth',
        r'lead investor|follow-on',
        r'term sheet|due diligence',
        r'portfolio company'
    ]
    
    PARTNER_SIGNALS = [
        r'partner(?:ship)?|collaboration',
        r'integrate|integration|API',
        r'white label|resell',
        r'co-market|joint',
        r'strategic|alliance',
        r'channel partner',
        r'affiliate program'
    ]
    
    # Spam/scam exclusions
    SPAM_PATTERNS = [
        r'unsubscribe',
        r'this is an advertisement',
        r'to stop receiving',
        r'click here to.*(?:unsubscribe|opt out)',
        r'marketing@',
        r'no-?reply@',
        r'newsletter',
        r'digest',
        r'\[AUTOMATED\]'
    ]
    
    def __init__(self, db: Optional[DatabaseManager] = None):
        """Initialize lead collector."""
        self.db = db or DatabaseManager()
        self.foundershield = FounderShieldService()
        self.learning_system = EmailRiskLearningSystem(db=self.db)
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Ensure leads database tables exist."""
        try:
            with self.db.get_connection() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS leads (
                        lead_id TEXT PRIMARY KEY,
                        source TEXT NOT NULL,
                        lead_type TEXT NOT NULL,
                        contact_name TEXT,
                        contact_email TEXT NOT NULL,
                        company TEXT,
                        status TEXT DEFAULT 'new',
                        score INTEGER DEFAULT 0,
                        confidence REAL DEFAULT 0,
                        signals TEXT,
                        context TEXT,
                        first_seen TIMESTAMP,
                        last_contact TIMESTAMP,
                        conversation_count INTEGER DEFAULT 0,
                        foundershield_score INTEGER,
                        risk_level TEXT,
                        next_action TEXT,
                        metadata TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS lead_interactions (
                        interaction_id TEXT PRIMARY KEY,
                        lead_id TEXT NOT NULL,
                        interaction_type TEXT,
                        direction TEXT,
                        content_summary TEXT,
                        timestamp TIMESTAMP,
                        source_id TEXT,
                        metadata TEXT,
                        FOREIGN KEY (lead_id) REFERENCES leads(lead_id)
                    )
                """)
                
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS lead_tasks (
                        task_id TEXT PRIMARY KEY,
                        lead_id TEXT NOT NULL,
                        task_type TEXT,
                        description TEXT,
                        status TEXT DEFAULT 'pending',
                        priority TEXT,
                        due_date TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        FOREIGN KEY (lead_id) REFERENCES leads(lead_id)
                    )
                """)
                
                conn.commit()
                logger.info("✅ Lead tables created/verified")
        except Exception as e:
            logger.error(f"Error creating lead tables: {e}")
    
    async def collect_from_gmail(
        self,
        emails: List[Dict[str, Any]],
        days_back: int = 30
    ) -> List[Lead]:
        """
        Collect leads from Gmail emails.
        
        Args:
            emails: List of email dicts from GmailCollector
            days_back: Only process emails from last N days
            
        Returns:
            List of discovered leads
        """
        logger.info(f"Analyzing {len(emails)} emails for leads...")
        
        cutoff_date = datetime.now() - timedelta(days=days_back)
        leads = []
        
        for email in emails:
            try:
                # Skip old emails
                email_date = email.get('date')
                if isinstance(email_date, str):
                    try:
                        email_date = datetime.fromisoformat(email_date.replace('Z', '+00:00'))
                    except:
                        email_date = datetime.now()
                elif email_date is None:
                    email_date = datetime.now()
                
                if email_date < cutoff_date:
                    continue
                
                # Skip spam/newsletters
                if self._is_spam(email):
                    continue
                
                # Analyze for lead signals
                lead = await self._analyze_email_for_lead(email)
                if lead:
                    leads.append(lead)
                    
            except Exception as e:
                logger.error(f"Error processing email: {e}")
                continue
        
        logger.info(f"✅ Found {len(leads)} potential leads from emails")
        return leads
    
    async def collect_from_calendar(
        self,
        events: List[Dict[str, Any]]
    ) -> List[Lead]:
        """
        Collect leads from calendar events (meetings with potential leads).
        
        Args:
            events: List of calendar events from CalendarCollector
            
        Returns:
            List of discovered leads
        """
        logger.info(f"Analyzing {len(events)} calendar events for leads...")
        
        leads = []
        
        for event in events:
            try:
                lead = await self._analyze_calendar_event_for_lead(event)
                if lead:
                    leads.append(lead)
            except Exception as e:
                logger.error(f"Error processing calendar event: {e}")
                continue
        
        logger.info(f"✅ Found {len(leads)} potential leads from calendar")
        return leads
    
    async def collect_from_notes(
        self,
        notes: List[Dict[str, Any]]
    ) -> List[Lead]:
        """
        Collect leads from notes (meeting notes, contact info, etc).
        
        Args:
            notes: List of notes from NotesCollector
            
        Returns:
            List of discovered leads
        """
        logger.info(f"Analyzing {len(notes)} notes for leads...")
        
        leads = []
        
        for note in notes:
            try:
                lead = await self._analyze_note_for_lead(note)
                if lead:
                    leads.append(lead)
            except Exception as e:
                logger.error(f"Error processing note: {e}")
                continue
        
        logger.info(f"✅ Found {len(leads)} potential leads from notes")
        return leads
    
    def _is_spam(self, email: Dict[str, Any]) -> bool:
        """Check if email is spam/newsletter."""
        subject = email.get('subject', '').lower()
        body = email.get('body', '').lower()
        sender = email.get('sender', '').lower()
        labels = email.get('labels', [])
        
        # Check labels
        spam_labels = ['spam', 'promotions', 'social']
        if any(label.lower() in spam_labels for label in labels):
            return True
        
        # Check patterns
        text = f"{subject} {body} {sender}"
        for pattern in self.SPAM_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        return False
    
    async def _analyze_email_for_lead(
        self,
        email: Dict[str, Any]
    ) -> Optional[Lead]:
        """Analyze single email for lead signals."""
        
        sender = email.get('sender', email.get('from', ''))
        subject = email.get('subject', '')
        body = email.get('body', '')
        email_date = email.get('date')
        
        if not sender:
            return None
        
        # Extract email address
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', sender)
        if not email_match:
            return None
        
        contact_email = email_match.group(0)
        
        # Check if this contact was previously deleted
        if self.learning_system.was_lead_deleted(contact_email):
            logger.debug(f"Skipping previously deleted lead: {contact_email}")
            return None
        
        # Extract name
        name_match = re.search(r'^([^<]+?)\s*<', sender)
        contact_name = name_match.group(1).strip() if name_match else contact_email.split('@')[0]
        
        # Combine text for analysis
        text = f"{subject} {body}".lower()
        
        # Determine lead type and collect signals
        lead_type, signals, score = self._classify_lead_type(text)
        
        if not lead_type:
            return None  # No lead signals detected
        
        # Use FounderShield to verify legitimacy
        try:
            fs_report = await self.foundershield.generate_report(
                email_address=contact_email,
                raw_headers=email.get('raw_headers', email.get('headers', '')),
                raw_body=body
            )
            fs_score = fs_report.get('score', 50)
            risk_level = fs_report.get('risk_level', 'unknown')
            
            # Adjust confidence based on risk
            if risk_level == 'high_risk':
                return None  # Skip scams
            elif risk_level == 'caution':
                score = int(score * 0.7)  # Reduce score for caution leads
                
        except Exception as e:
            logger.warning(f"FounderShield check failed: {e}")
            fs_score = None
            risk_level = None
        
        # Extract company from email domain or signature
        company = self._extract_company(sender, body)
        
        # Generate lead ID
        lead_id = f"lead_{contact_email}_{int(datetime.now().timestamp())}"
        
        # Determine next action
        next_action = self._suggest_next_action(lead_type, signals, text)
        
        # Create lead
        lead = Lead(
            lead_id=lead_id,
            source='email',
            lead_type=lead_type,
            contact_name=contact_name,
            contact_email=contact_email,
            company=company,
            status='potential',
            score=score,
            confidence=min(len(signals) / 5.0, 1.0),  # More signals = higher confidence
            signals=signals,
            context=f"{subject}\n\n{body[:500]}...",
            first_seen=email_date if isinstance(email_date, datetime) else datetime.now(),
            last_contact=email_date if isinstance(email_date, datetime) else datetime.now(),
            conversation_count=1,
            foundershield_score=fs_score,
            risk_level=risk_level,
            next_action=next_action,
            tasks=[],
            metadata={
                'subject': subject,
                'email_id': email.get('id'),
                'thread_id': email.get('thread_id')
            }
        )
        
        return lead
    
    def _classify_lead_type(self, text: str) -> Tuple[Optional[str], List[str], int]:
        """
        Classify lead type and collect signals.
        
        Returns:
            (lead_type, signals, score)
        """
        customer_matches = []
        investor_matches = []
        partner_matches = []
        
        # Check customer signals
        for pattern in self.CUSTOMER_SIGNALS:
            if re.search(pattern, text, re.IGNORECASE):
                customer_matches.append(pattern)
        
        # Check investor signals
        for pattern in self.INVESTOR_SIGNALS:
            if re.search(pattern, text, re.IGNORECASE):
                investor_matches.append(pattern)
        
        # Check partner signals
        for pattern in self.PARTNER_SIGNALS:
            if re.search(pattern, text, re.IGNORECASE):
                partner_matches.append(pattern)
        
        # Determine primary type (highest match count)
        matches = {
            'customer': customer_matches,
            'investor': investor_matches,
            'partner': partner_matches
        }
        
        if not any(matches.values()):
            return None, [], 0
        
        lead_type = max(matches, key=lambda k: len(matches[k]))
        signals = matches[lead_type]
        
        # Calculate score based on number and quality of signals
        base_score = 40
        signal_score = min(len(signals) * 15, 50)
        urgency_boost = 10 if re.search(r'urgently?|asap|soon|immediately', text, re.IGNORECASE) else 0
        
        score = base_score + signal_score + urgency_boost
        
        # Format signals for readability
        formatted_signals = [pattern.replace(r'\?', '').replace(r'\|', ' or ') for pattern in signals]
        
        return lead_type, formatted_signals[:5], min(score, 100)
    
    def _extract_company(self, sender: str, body: str) -> Optional[str]:
        """Extract company name from email."""
        # Try to extract from email domain
        domain_match = re.search(r'@([\w-]+)\.\w+', sender)
        if domain_match:
            domain = domain_match.group(1)
            # Skip common email providers
            if domain not in ['gmail', 'yahoo', 'outlook', 'hotmail', 'aol']:
                return domain.replace('-', ' ').title()
        
        # Try to extract from signature
        signature_patterns = [
            r'(?:^|\n)([A-Z][^\n]{3,30})\n[^\n]*(?:CEO|Founder|Director|VP)',
            r'(?:^|\n)\s*([A-Z][A-Z\s&]{2,30}(?:Inc|LLC|Ltd|Corp|Company))',
        ]
        
        for pattern in signature_patterns:
            match = re.search(pattern, body, re.MULTILINE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _suggest_next_action(
        self,
        lead_type: str,
        signals: List[str],
        text: str
    ) -> str:
        """Suggest next action based on lead type and signals."""
        if lead_type == 'customer':
            if 'demo' in text or 'trial' in text:
                return "Schedule product demo"
            elif 'pricing' in text or 'quote' in text:
                return "Send pricing information"
            else:
                return "Send introduction and capabilities overview"
        
        elif lead_type == 'investor':
            if 'pitch deck' in text:
                return "Send updated pitch deck"
            elif 'meeting' in text or 'call' in text:
                return "Schedule investor call"
            else:
                return "Send company overview and traction metrics"
        
        elif lead_type == 'partner':
            if 'integration' in text or 'API' in text:
                return "Send API documentation and integration guide"
            else:
                return "Schedule partnership discussion call"
        
        return "Respond to inquiry"
    
    async def _analyze_calendar_event_for_lead(
        self,
        event: Dict[str, Any]
    ) -> Optional[Lead]:
        """Analyze calendar event for lead signals."""
        
        summary = event.get('summary', '').lower()
        description = event.get('description', '').lower()
        attendees = event.get('attendees', [])
        
        # Skip if no external attendees
        if not attendees:
            return None
        
        # Look for meeting keywords
        lead_keywords = [
            'demo', 'pitch', 'intro', 'introduction',
            'sales', 'call', 'meeting', 'discussion',
            'investor', 'funding', 'partnership'
        ]
        
        text = f"{summary} {description}"
        if not any(keyword in text for keyword in lead_keywords):
            return None
        
        # Extract first external attendee as lead
        for attendee in attendees:
            email = attendee.get('email', '')
            if email and not email.endswith(('@gmail.com', '@me.com')):  # Skip personal emails
                lead_type, signals, score = self._classify_lead_type(text)
                
                if not lead_type:
                    lead_type = 'customer'  # Default for meetings
                    signals = ['calendar_meeting']
                    score = 60
                
                lead_id = f"lead_{email}_{int(datetime.now().timestamp())}"
                
                return Lead(
                    lead_id=lead_id,
                    source='calendar',
                    lead_type=lead_type,
                    contact_name=attendee.get('displayName', email.split('@')[0]),
                    contact_email=email,
                    company=self._extract_company(email, description),
                    status='contacted',  # Already have meeting scheduled
                    score=score,
                    confidence=0.8,
                    signals=signals,
                    context=f"{summary}\n{description}",
                    first_seen=event.get('start', datetime.now()),
                    last_contact=event.get('start', datetime.now()),
                    conversation_count=1,
                    foundershield_score=None,
                    risk_level=None,
                    next_action="Prepare for scheduled meeting",
                    tasks=[],
                    metadata={'event_id': event.get('id')}
                )
        
        return None
    
    async def _analyze_note_for_lead(
        self,
        note: Dict[str, Any]
    ) -> Optional[Lead]:
        """Analyze note for lead information."""
        
        content = note.get('content', '').lower()
        title = note.get('title', '').lower()
        
        # Look for contact information patterns
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', content)
        if not email_match:
            return None
        
        contact_email = email_match.group(0)
        
        # Check for lead signals
        lead_type, signals, score = self._classify_lead_type(f"{title} {content}")
        
        if not lead_type and not any(keyword in content for keyword in ['contact', 'follow up', 'reach out']):
            return None
        
        # Extract name (look for patterns like "Name: John Doe" or "Contact: John")
        name_match = re.search(r'(?:name|contact):\s*([A-Z][a-z]+(?: [A-Z][a-z]+)*)', content, re.IGNORECASE)
        contact_name = name_match.group(1) if name_match else contact_email.split('@')[0]
        
        lead_id = f"lead_{contact_email}_{int(datetime.now().timestamp())}"
        
        return Lead(
            lead_id=lead_id,
            source='notes',
            lead_type=lead_type or 'other',
            contact_name=contact_name,
            contact_email=contact_email,
            company=self._extract_company(contact_email, content),
            status='potential',
            score=score or 50,
            confidence=0.6,
            signals=signals,
            context=content[:500],
            first_seen=note.get('created', datetime.now()),
            last_contact=note.get('modified', datetime.now()),
            conversation_count=0,
            foundershield_score=None,
            risk_level=None,
            next_action="Initial outreach",
            tasks=[],
            metadata={'note_id': note.get('id')}
        )
    
    async def save_lead(self, lead: Lead) -> bool:
        """Save or update lead in database."""
        try:
            with self.db.get_connection() as conn:
                # Check if lead already exists by email
                existing = conn.execute(
                    "SELECT lead_id, conversation_count FROM leads WHERE contact_email = ?",
                    (lead.contact_email,)
                ).fetchone()
                
                if existing:
                    # Get current status
                    current_status = conn.execute(
                        "SELECT status FROM leads WHERE lead_id = ?",
                        (existing[0],)
                    ).fetchone()[0]
                    
                    # Only keep existing status if it's been confirmed by user
                    # Otherwise keep as 'potential' for new leads
                    keep_status = current_status if current_status in ['new', 'contacted', 'engaged', 'qualified', 'converted'] else lead.status
                    
                    # Update existing lead
                    conn.execute("""
                        UPDATE leads SET
                            last_contact = ?,
                            conversation_count = ?,
                            score = ?,
                            status = ?,
                            signals = ?,
                            context = ?,
                            next_action = ?,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE lead_id = ?
                    """, (
                        lead.last_contact,
                        existing[1] + 1,
                        max(lead.score, existing[1] * 5),  # Increase score with engagement
                        keep_status,
                        ','.join(lead.signals),
                        lead.context,
                        lead.next_action,
                        existing[0]
                    ))
                    lead_id = existing[0]
                else:
                    # Insert new lead
                    conn.execute("""
                        INSERT INTO leads (
                            lead_id, source, lead_type, contact_name, contact_email,
                            company, status, score, confidence, signals, context,
                            first_seen, last_contact, conversation_count,
                            foundershield_score, risk_level, next_action, metadata
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        lead.lead_id, lead.source, lead.lead_type, lead.contact_name,
                        lead.contact_email, lead.company, lead.status, lead.score,
                        lead.confidence, ','.join(lead.signals), lead.context,
                        lead.first_seen, lead.last_contact, lead.conversation_count,
                        lead.foundershield_score, lead.risk_level, lead.next_action,
                        str(lead.metadata)
                    ))
                    lead_id = lead.lead_id
                
                conn.commit()
                logger.info(f"✅ Saved lead: {lead.contact_email}")
                return True
                
        except Exception as e:
            logger.error(f"Error saving lead: {e}")
            return False
    
    async def create_task_for_lead(
        self,
        lead_id: str,
        task_type: str,
        description: str,
        priority: str = 'medium',
        due_days: int = 7
    ) -> Optional[str]:
        """Create a task associated with a lead."""
        try:
            task_id = f"task_{lead_id}_{int(datetime.now().timestamp())}"
            due_date = datetime.now() + timedelta(days=due_days)
            
            with self.db.get_connection() as conn:
                conn.execute("""
                    INSERT INTO lead_tasks (
                        task_id, lead_id, task_type, description,
                        status, priority, due_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    task_id, lead_id, task_type, description,
                    'pending', priority, due_date
                ))
                conn.commit()
            
            logger.info(f"✅ Created task for lead {lead_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Error creating task: {e}")
            return None
    
    async def get_all_leads(
        self,
        lead_type: Optional[str] = None,
        status: Optional[str] = None,
        min_score: int = 0
    ) -> List[Dict[str, Any]]:
        """Get all leads with optional filters."""
        try:
            query = "SELECT * FROM leads WHERE score >= ?"
            params = [min_score]
            
            if lead_type:
                query += " AND lead_type = ?"
                params.append(lead_type)
            
            if status:
                query += " AND status = ?"
                params.append(status)
            
            query += " ORDER BY score DESC, last_contact DESC"
            
            with self.db.get_connection() as conn:
                rows = conn.execute(query, params).fetchall()
                
                leads = []
                for row in rows:
                    lead_dict = dict(row)
                    # Parse signals back to list
                    if lead_dict.get('signals'):
                        lead_dict['signals'] = lead_dict['signals'].split(',')
                    leads.append(lead_dict)
                
                return leads
                
        except Exception as e:
            logger.error(f"Error getting leads: {e}")
            return []
    
    async def export_to_crm(
        self,
        lead_id: str,
        crm_type: str = 'generic'
    ) -> Dict[str, Any]:
        """
        Export lead to CRM format.
        
        Supported CRM types: generic, hubspot, salesforce, pipedrive
        """
        try:
            with self.db.get_connection() as conn:
                row = conn.execute(
                    "SELECT * FROM leads WHERE lead_id = ?",
                    (lead_id,)
                ).fetchone()
                
                if not row:
                    return {'success': False, 'error': 'Lead not found'}
                
                lead = dict(row)
                
                # Generic CRM format
                crm_data = {
                    'contact': {
                        'first_name': lead['contact_name'].split()[0] if lead['contact_name'] else '',
                        'last_name': ' '.join(lead['contact_name'].split()[1:]) if lead['contact_name'] and len(lead['contact_name'].split()) > 1 else '',
                        'email': lead['contact_email'],
                        'company': lead['company']
                    },
                    'deal': {
                        'title': f"{lead['lead_type'].title()} - {lead['contact_name']}",
                        'value': 0,  # To be filled manually
                        'stage': lead['status'],
                        'priority': 'high' if lead['score'] >= 75 else 'medium' if lead['score'] >= 50 else 'low'
                    },
                    'notes': lead['context'],
                    'source': lead['source'],
                    'custom_fields': {
                        'lead_type': lead['lead_type'],
                        'lead_score': lead['score'],
                        'signals': lead['signals'],
                        'risk_level': lead['risk_level']
                    }
                }
                
                return {
                    'success': True,
                    'crm_type': crm_type,
                    'data': crm_data
                }
                
        except Exception as e:
            logger.error(f"Error exporting lead to CRM: {e}")
            return {'success': False, 'error': str(e)}
