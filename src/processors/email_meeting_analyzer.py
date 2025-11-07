"""
Email Meeting Analyzer - Extracts meeting patterns and company interactions from Gmail data.

This module analyzes:
- Meeting scheduling patterns and company types
- Email thread analysis for business development patterns
- Company domain analysis and industry classification
- Follow-up patterns and conversion rates
"""

import logging
import asyncio
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass
from collections import defaultdict, Counter
import json
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class CompanyProfile:
    """Profile of a company extracted from email interactions."""
    name: str
    domain: str
    industry: Optional[str]
    size_estimate: Optional[str]
    interaction_count: int
    meeting_count: int
    last_interaction: datetime
    contact_names: List[str]
    email_addresses: List[str]
    interaction_quality: float  # 0-1 score based on engagement
    business_potential: float   # 0-1 score based on patterns
    keywords: List[str]
    meeting_patterns: Dict[str, Any]


@dataclass
class MeetingPattern:
    """Pattern extracted from meeting scheduling behavior."""
    company_type: str
    typical_duration: str
    preferred_times: List[str]
    preparation_time: str
    follow_up_rate: float
    conversion_indicators: List[str]


class EmailMeetingAnalyzer:
    """Analyzes Gmail data to extract meeting and company interaction patterns."""
    
    def __init__(self, gmail_collector=None):
        self.gmail_collector = gmail_collector
        self.company_profiles = {}
        self.meeting_patterns = []
        self.known_companies = {
            'buildly': {'name': 'Buildly', 'industry': 'Software Development Platform'},
            'openbuild': {'name': 'Open Build', 'industry': 'Development Tools'},
            'oregon-software': {'name': 'Oregon Software', 'industry': 'Custom Software'}
        }
        
    async def analyze_email_patterns(self, emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze email data to extract company and meeting patterns."""
        try:
            logger.info("Analyzing email patterns for company and meeting insights...")
            
            if not emails:
                logger.warning("No email data provided for analysis")
                return self._empty_analysis()
            
            # Extract company profiles from email interactions
            company_profiles = self._extract_company_profiles(emails)
            
            # Analyze meeting scheduling patterns
            meeting_patterns = self._analyze_meeting_patterns(emails)
            
            # Extract business development patterns
            business_patterns = self._analyze_business_patterns(emails, company_profiles)
            
            # Identify high-potential leads and patterns
            lead_patterns = self._identify_lead_patterns(company_profiles, emails)
            
            # Analyze follow-up effectiveness
            followup_patterns = self._analyze_followup_patterns(emails)
            
            analysis_results = {
                'company_profiles': [self._serialize_company_profile(cp) for cp in company_profiles.values()],
                'meeting_patterns': [self._serialize_meeting_pattern(mp) for mp in meeting_patterns],
                'business_patterns': business_patterns,
                'lead_patterns': lead_patterns,
                'followup_patterns': followup_patterns,
                'total_companies': len(company_profiles),
                'total_meetings': sum(cp.meeting_count for cp in company_profiles.values()),
                'analysis_timestamp': datetime.now().isoformat()
            }
            
            logger.info(f"Email analysis completed: {len(company_profiles)} companies, {len(meeting_patterns)} patterns")
            return analysis_results
            
        except Exception as e:
            logger.error(f"Error analyzing email patterns: {e}")
            return self._empty_analysis()
    
    def _extract_company_profiles(self, emails: List[Dict[str, Any]]) -> Dict[str, CompanyProfile]:
        """Extract company profiles from email interactions."""
        company_profiles = {}
        
        for email in emails:
            try:
                # Extract sender information
                sender = email.get('sender', '')
                sender_email = self._extract_email_address(sender)
                sender_name = self._extract_sender_name(sender)
                
                if not sender_email:
                    continue
                
                # Extract company domain
                domain = self._extract_domain(sender_email)
                if not domain or self._is_personal_domain(domain):
                    continue
                
                # Extract or generate company name
                company_name = self._extract_company_name(domain, sender_name, email.get('subject', ''))
                
                # Initialize or update company profile
                if company_name not in company_profiles:
                    company_profiles[company_name] = CompanyProfile(
                        name=company_name,
                        domain=domain,
                        industry=self._classify_industry(domain, email.get('subject', '') + ' ' + email.get('snippet', '')),
                        size_estimate=self._estimate_company_size(domain),
                        interaction_count=0,
                        meeting_count=0,
                        last_interaction=datetime.now(),
                        contact_names=[],
                        email_addresses=[],
                        interaction_quality=0.0,
                        business_potential=0.0,
                        keywords=[],
                        meeting_patterns={}
                    )
                
                profile = company_profiles[company_name]
                
                # Update profile with email data
                profile.interaction_count += 1
                
                if sender_name and sender_name not in profile.contact_names:
                    profile.contact_names.append(sender_name)
                
                if sender_email not in profile.email_addresses:
                    profile.email_addresses.append(sender_email)
                
                # Check if this email is meeting-related
                if self._is_meeting_related(email):
                    profile.meeting_count += 1
                
                # Update last interaction
                email_date = self._parse_email_date(email.get('date', ''))
                if email_date and email_date > profile.last_interaction:
                    profile.last_interaction = email_date
                
                # Extract keywords
                keywords = self._extract_business_keywords(email.get('subject', '') + ' ' + email.get('snippet', ''))
                profile.keywords.extend(keywords)
                
            except Exception as e:
                logger.error(f"Error processing email for company extraction: {e}")
                continue
        
        # Post-process profiles to calculate scores
        for profile in company_profiles.values():
            profile.interaction_quality = self._calculate_interaction_quality(profile)
            profile.business_potential = self._calculate_business_potential(profile)
            profile.keywords = list(set(profile.keywords))  # Remove duplicates
        
        return company_profiles
    
    def _analyze_meeting_patterns(self, emails: List[Dict[str, Any]]) -> List[MeetingPattern]:
        """Analyze meeting scheduling and conduct patterns."""
        meeting_emails = [email for email in emails if self._is_meeting_related(email)]
        
        if not meeting_emails:
            return []
        
        patterns = []
        
        # Group meetings by company type/domain
        meetings_by_domain = defaultdict(list)
        for email in meeting_emails:
            sender_email = self._extract_email_address(email.get('sender', ''))
            if sender_email:
                domain = self._extract_domain(sender_email)
                meetings_by_domain[domain].append(email)
        
        # Analyze patterns for each domain
        for domain, domain_meetings in meetings_by_domain.items():
            if len(domain_meetings) < 2:  # Need multiple meetings to identify patterns
                continue
            
            company_type = self._classify_company_type(domain, domain_meetings)
            
            pattern = MeetingPattern(
                company_type=company_type,
                typical_duration=self._analyze_meeting_duration(domain_meetings),
                preferred_times=self._analyze_preferred_meeting_times(domain_meetings),
                preparation_time=self._analyze_preparation_patterns(domain_meetings),
                follow_up_rate=self._calculate_followup_rate(domain_meetings),
                conversion_indicators=self._identify_conversion_indicators(domain_meetings)
            )
            
            patterns.append(pattern)
        
        return patterns
    
    def _analyze_business_patterns(self, emails: List[Dict[str, Any]], company_profiles: Dict[str, CompanyProfile]) -> Dict[str, Any]:
        """Analyze business development and sales patterns."""
        business_emails = [email for email in emails if self._is_business_related(email)]
        
        # Analyze communication stages
        stage_patterns = self._analyze_communication_stages(business_emails)
        
        # Identify successful engagement patterns
        success_patterns = self._identify_success_patterns(business_emails, company_profiles)
        
        # Analyze industry preferences
        industry_patterns = self._analyze_industry_patterns(company_profiles)
        
        # Company size preferences
        size_patterns = self._analyze_company_size_patterns(company_profiles)
        
        return {
            'communication_stages': stage_patterns,
            'success_patterns': success_patterns,
            'industry_preferences': industry_patterns,
            'company_size_preferences': size_patterns,
            'total_business_emails': len(business_emails)
        }
    
    def _identify_lead_patterns(self, company_profiles: Dict[str, CompanyProfile], emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Identify patterns that indicate high-quality leads."""
        high_quality_companies = [cp for cp in company_profiles.values() if cp.business_potential > 0.7]
        
        # Extract common characteristics of high-quality leads
        common_industries = Counter([cp.industry for cp in high_quality_companies if cp.industry])
        common_sizes = Counter([cp.size_estimate for cp in high_quality_companies if cp.size_estimate])
        common_keywords = Counter()
        for cp in high_quality_companies:
            common_keywords.update(cp.keywords)
        
        # Analyze interaction patterns of successful leads
        successful_interaction_patterns = self._analyze_successful_interaction_patterns(high_quality_companies, emails)
        
        return {
            'high_quality_count': len(high_quality_companies),
            'common_industries': dict(common_industries.most_common(5)),
            'common_company_sizes': dict(common_sizes.most_common()),
            'key_success_keywords': [kw for kw, count in common_keywords.most_common(10)],
            'interaction_patterns': successful_interaction_patterns,
            'quality_threshold': 0.7
        }
    
    def _analyze_followup_patterns(self, emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze follow-up effectiveness and timing patterns."""
        # Group emails by conversation threads
        threads = self._group_emails_by_thread(emails)
        
        followup_stats = {
            'average_response_time': 0,
            'followup_success_rate': 0,
            'optimal_followup_timing': [],
            'most_effective_followup_types': []
        }
        
        response_times = []
        successful_followups = 0
        total_followups = 0
        
        for thread in threads:
            if len(thread) > 1:  # Has follow-up emails
                # Analyze response timing
                for i in range(1, len(thread)):
                    prev_email = thread[i-1]
                    current_email = thread[i]
                    
                    prev_date = self._parse_email_date(prev_email.get('date', ''))
                    current_date = self._parse_email_date(current_email.get('date', ''))
                    
                    if prev_date and current_date and current_date > prev_date:
                        response_time = (current_date - prev_date).total_seconds() / 3600  # Hours
                        response_times.append(response_time)
                        
                        # Check if follow-up was successful (heuristic)
                        if self._is_successful_followup(current_email):
                            successful_followups += 1
                        total_followups += 1
        
        if response_times:
            followup_stats['average_response_time'] = sum(response_times) / len(response_times)
        
        if total_followups > 0:
            followup_stats['followup_success_rate'] = successful_followups / total_followups
        
        return followup_stats
    
    def _extract_email_address(self, sender_field: str) -> str:
        """Extract email address from sender field."""
        if not sender_field:
            return ""
        
        # Look for email in angle brackets or just the email itself
        email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        match = re.search(email_pattern, sender_field)
        return match.group(1) if match else ""
    
    def _extract_sender_name(self, sender_field: str) -> str:
        """Extract sender name from sender field."""
        if not sender_field:
            return ""
        
        # Remove email address and clean up name
        email_pattern = r'<[^>]+>'
        name = re.sub(email_pattern, '', sender_field).strip()
        name = name.strip('"').strip()
        
        return name if name and '@' not in name else ""
    
    def _extract_domain(self, email_address: str) -> str:
        """Extract domain from email address."""
        if '@' in email_address:
            return email_address.split('@')[1].lower()
        return ""
    
    def _is_personal_domain(self, domain: str) -> bool:
        """Check if domain is a personal email provider."""
        personal_domains = {
            'gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com', 'aol.com',
            'icloud.com', 'me.com', 'mac.com', 'protonmail.com'
        }
        return domain.lower() in personal_domains
    
    def _extract_company_name(self, domain: str, sender_name: str, subject: str) -> str:
        """Extract or generate company name from available information."""
        # Check if it's a known company first
        domain_key = domain.lower().replace('.com', '').replace('.', '-')
        if domain_key in self.known_companies:
            return self.known_companies[domain_key]['name']
        
        # Try to extract from domain
        company_part = domain.split('.')[0]
        
        # Clean up common domain parts
        if company_part.lower() in ['www', 'mail', 'info', 'contact']:
            parts = domain.split('.')
            if len(parts) > 1:
                company_part = parts[1]
        
        # Capitalize and format
        company_name = company_part.replace('-', ' ').replace('_', ' ').title()
        
        return company_name
    
    def _classify_industry(self, domain: str, content: str) -> str:
        """Classify company industry based on domain and email content."""
        content_lower = content.lower()
        
        # Industry keyword mapping
        industry_keywords = {
            'Software Development': ['software', 'development', 'coding', 'programming', 'tech', 'app', 'platform'],
            'Consulting': ['consulting', 'advisory', 'strategy', 'consultation'],
            'Marketing': ['marketing', 'advertising', 'campaign', 'promotion', 'brand'],
            'Finance': ['finance', 'banking', 'investment', 'financial', 'money'],
            'Healthcare': ['healthcare', 'medical', 'health', 'clinic', 'hospital'],
            'Education': ['education', 'training', 'learning', 'course', 'university'],
            'E-commerce': ['ecommerce', 'retail', 'store', 'shop', 'commerce'],
            'Manufacturing': ['manufacturing', 'production', 'factory', 'industrial']
        }
        
        # Score each industry based on keyword matches
        industry_scores = {}
        for industry, keywords in industry_keywords.items():
            score = sum(1 for keyword in keywords if keyword in content_lower)
            if score > 0:
                industry_scores[industry] = score
        
        # Return industry with highest score, or default
        if industry_scores:
            return max(industry_scores.keys(), key=lambda k: industry_scores[k])
        
        return "Technology"  # Default assumption
    
    def _estimate_company_size(self, domain: str) -> str:
        """Estimate company size based on domain and other indicators."""
        # This is a simplified heuristic - could be enhanced with external data
        
        # Check for enterprise indicators in domain
        if any(indicator in domain.lower() for indicator in ['corp', 'inc', 'ltd', 'llc']):
            return 'Medium'
        
        # Very basic heuristic based on domain length and structure
        if len(domain) > 20 or domain.count('.') > 2:
            return 'Large'
        elif len(domain) > 10:
            return 'Medium'
        else:
            return 'Small'
    
    def _is_meeting_related(self, email: Dict[str, Any]) -> bool:
        """Check if email is related to meetings or scheduling."""
        meeting_keywords = [
            'meeting', 'call', 'schedule', 'calendar', 'appointment', 'demo',
            'presentation', 'sync', 'standup', 'conference', 'zoom', 'teams'
        ]
        
        subject = email.get('subject', '').lower()
        snippet = email.get('snippet', '').lower()
        
        return any(keyword in subject or keyword in snippet for keyword in meeting_keywords)
    
    def _is_business_related(self, email: Dict[str, Any]) -> bool:
        """Check if email is related to business development or sales."""
        business_keywords = [
            'proposal', 'contract', 'partnership', 'collaboration', 'opportunity',
            'project', 'requirements', 'budget', 'timeline', 'deliverable',
            'client', 'customer', 'lead', 'prospect', 'quote', 'estimate'
        ]
        
        subject = email.get('subject', '').lower()
        snippet = email.get('snippet', '').lower()
        
        return any(keyword in subject or keyword in snippet for keyword in business_keywords)
    
    def _extract_business_keywords(self, text: str) -> List[str]:
        """Extract business-relevant keywords from email text."""
        business_terms = [
            'project', 'development', 'website', 'application', 'system', 'platform',
            'integration', 'api', 'database', 'cloud', 'mobile', 'web',
            'consulting', 'strategy', 'implementation', 'migration', 'upgrade',
            'budget', 'timeline', 'deliverable', 'milestone', 'requirement'
        ]
        
        text_lower = text.lower()
        found_keywords = []
        
        for term in business_terms:
            if term in text_lower:
                found_keywords.append(term)
        
        return found_keywords
    
    def _parse_email_date(self, date_str: str) -> Optional[datetime]:
        """Parse email date string to datetime object."""
        if not date_str:
            return None
        
        try:
            # Try common email date formats
            formats = [
                '%a, %d %b %Y %H:%M:%S %z',
                '%d %b %Y %H:%M:%S %z',
                '%Y-%m-%d %H:%M:%S',
                '%Y-%m-%dT%H:%M:%SZ'
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(date_str, fmt)
                except ValueError:
                    continue
            
            # If all formats fail, return current time as fallback
            return datetime.now()
            
        except Exception:
            return None
    
    def _calculate_interaction_quality(self, profile: CompanyProfile) -> float:
        """Calculate interaction quality score (0-1) based on various factors."""
        score = 0.0
        
        # Base score from interaction frequency
        score += min(profile.interaction_count / 10, 0.3)  # Max 0.3 for frequency
        
        # Bonus for meetings
        if profile.meeting_count > 0:
            score += min(profile.meeting_count / 5, 0.3)  # Max 0.3 for meetings
        
        # Bonus for multiple contacts
        if len(profile.contact_names) > 1:
            score += 0.2
        
        # Bonus for business keywords
        business_keyword_count = len([kw for kw in profile.keywords if kw in ['project', 'development', 'contract', 'budget']])
        score += min(business_keyword_count / 10, 0.2)  # Max 0.2 for business relevance
        
        return min(score, 1.0)
    
    def _calculate_business_potential(self, profile: CompanyProfile) -> float:
        """Calculate business potential score (0-1) based on various indicators."""
        score = 0.0
        
        # Industry scoring
        high_potential_industries = ['Software Development', 'Technology', 'Consulting', 'Finance']
        if profile.industry in high_potential_industries:
            score += 0.3
        
        # Company size scoring
        if profile.size_estimate == 'Medium':
            score += 0.2
        elif profile.size_estimate == 'Large':
            score += 0.3
        
        # Meeting engagement
        if profile.meeting_count > 0:
            score += 0.2
        
        # Recent interaction bonus
        days_since_last = (datetime.now() - profile.last_interaction).days
        if days_since_last <= 30:
            score += 0.3
        elif days_since_last <= 90:
            score += 0.2
        
        return min(score, 1.0)
    
    def _classify_company_type(self, domain: str, meetings: List[Dict[str, Any]]) -> str:
        """Classify company type based on domain and meeting patterns."""
        # Analyze meeting content for company type indicators
        content = " ".join([meeting.get('subject', '') + ' ' + meeting.get('snippet', '') for meeting in meetings])
        content_lower = content.lower()
        
        type_indicators = {
            'Enterprise Client': ['enterprise', 'corporation', 'large', 'fortune'],
            'Startup': ['startup', 'new', 'founding', 'early'],
            'SMB Client': ['small business', 'local', 'family'],
            'Technology Partner': ['integration', 'api', 'platform', 'tech'],
            'Service Provider': ['service', 'provider', 'vendor', 'supplier']
        }
        
        for company_type, indicators in type_indicators.items():
            if any(indicator in content_lower for indicator in indicators):
                return company_type
        
        return 'General Client'
    
    def _analyze_meeting_duration(self, meetings: List[Dict[str, Any]]) -> str:
        """Analyze typical meeting duration from meeting emails."""
        # This is a heuristic based on meeting type keywords
        content = " ".join([meeting.get('subject', '') + ' ' + meeting.get('snippet', '') for meeting in meetings])
        content_lower = content.lower()
        
        if any(keyword in content_lower for keyword in ['demo', 'presentation']):
            return '60 minutes'
        elif any(keyword in content_lower for keyword in ['sync', 'standup', 'check-in']):
            return '30 minutes'
        else:
            return '45 minutes'  # Default
    
    def _serialize_company_profile(self, profile: CompanyProfile) -> Dict[str, Any]:
        """Convert CompanyProfile to serializable dictionary."""
        return {
            'name': profile.name,
            'domain': profile.domain,
            'industry': profile.industry,
            'size_estimate': profile.size_estimate,
            'interaction_count': profile.interaction_count,
            'meeting_count': profile.meeting_count,
            'last_interaction': profile.last_interaction.isoformat(),
            'contact_names': profile.contact_names,
            'email_addresses': profile.email_addresses,
            'interaction_quality': profile.interaction_quality,
            'business_potential': profile.business_potential,
            'keywords': profile.keywords,
            'meeting_patterns': profile.meeting_patterns
        }
    
    def _serialize_meeting_pattern(self, pattern: MeetingPattern) -> Dict[str, Any]:
        """Convert MeetingPattern to serializable dictionary."""
        return {
            'company_type': pattern.company_type,
            'typical_duration': pattern.typical_duration,
            'preferred_times': pattern.preferred_times,
            'preparation_time': pattern.preparation_time,
            'follow_up_rate': pattern.follow_up_rate,
            'conversion_indicators': pattern.conversion_indicators
        }
    
    def _empty_analysis(self) -> Dict[str, Any]:
        """Return empty analysis structure."""
        return {
            'company_profiles': [],
            'meeting_patterns': [],
            'business_patterns': {},
            'lead_patterns': {},
            'followup_patterns': {},
            'total_companies': 0,
            'total_meetings': 0,
            'analysis_timestamp': datetime.now().isoformat()
        }
    
    # Additional helper methods for more complex analysis
    def _analyze_preferred_meeting_times(self, meetings: List[Dict[str, Any]]) -> List[str]:
        """Analyze preferred meeting times from email patterns."""
        # This would require more sophisticated email parsing
        # For now, return common business hours
        return ['10:00-12:00', '14:00-16:00']
    
    def _analyze_preparation_patterns(self, meetings: List[Dict[str, Any]]) -> str:
        """Analyze how much preparation time is typically needed."""
        return '2-3 days'  # Default heuristic
    
    def _calculate_followup_rate(self, meetings: List[Dict[str, Any]]) -> float:
        """Calculate follow-up rate for meetings with this domain."""
        # Simplified heuristic
        return 0.8 if len(meetings) > 2 else 0.5
    
    def _identify_conversion_indicators(self, meetings: List[Dict[str, Any]]) -> List[str]:
        """Identify indicators that suggest meeting conversion potential."""
        indicators = []
        content = " ".join([meeting.get('subject', '') + ' ' + meeting.get('snippet', '') for meeting in meetings])
        content_lower = content.lower()
        
        conversion_terms = [
            'proposal', 'contract', 'next steps', 'timeline', 'budget',
            'requirements', 'scope', 'deliverables', 'pricing'
        ]
        
        for term in conversion_terms:
            if term in content_lower:
                indicators.append(term)
        
        return indicators
    
    def _analyze_communication_stages(self, emails: List[Dict[str, Any]]) -> Dict[str, int]:
        """Analyze communication stages in business emails."""
        stages = {
            'initial_contact': 0,
            'discovery': 0,
            'proposal': 0,
            'negotiation': 0,
            'closing': 0
        }
        
        for email in emails:
            content = (email.get('subject', '') + ' ' + email.get('snippet', '')).lower()
            
            if any(term in content for term in ['introduction', 'hello', 'nice to meet']):
                stages['initial_contact'] += 1
            elif any(term in content for term in ['requirements', 'needs', 'goals', 'discovery']):
                stages['discovery'] += 1
            elif any(term in content for term in ['proposal', 'quote', 'estimate', 'scope']):
                stages['proposal'] += 1
            elif any(term in content for term in ['negotiation', 'terms', 'conditions', 'pricing']):
                stages['negotiation'] += 1
            elif any(term in content for term in ['contract', 'agreement', 'final', 'closing']):
                stages['closing'] += 1
        
        return stages
    
    def _identify_success_patterns(self, emails: List[Dict[str, Any]], profiles: Dict[str, CompanyProfile]) -> Dict[str, Any]:
        """Identify patterns that correlate with successful business outcomes."""
        successful_profiles = [p for p in profiles.values() if p.business_potential > 0.7]
        
        if not successful_profiles:
            return {}
        
        # Analyze common characteristics
        success_keywords = Counter()
        for profile in successful_profiles:
            success_keywords.update(profile.keywords)
        
        return {
            'common_success_keywords': dict(success_keywords.most_common(10)),
            'successful_industries': Counter([p.industry for p in successful_profiles if p.industry]),
            'average_interactions': sum(p.interaction_count for p in successful_profiles) / len(successful_profiles)
        }
    
    def _analyze_industry_patterns(self, profiles: Dict[str, CompanyProfile]) -> Dict[str, Any]:
        """Analyze industry distribution and preferences."""
        industry_counts = Counter([p.industry for p in profiles.values() if p.industry])
        industry_potential = defaultdict(list)
        
        for profile in profiles.values():
            if profile.industry:
                industry_potential[profile.industry].append(profile.business_potential)
        
        industry_avg_potential = {}
        for industry, potentials in industry_potential.items():
            industry_avg_potential[industry] = sum(potentials) / len(potentials)
        
        return {
            'industry_distribution': dict(industry_counts),
            'industry_avg_potential': industry_avg_potential,
            'top_industries_by_potential': sorted(industry_avg_potential.items(), key=lambda x: x[1], reverse=True)[:5]
        }
    
    def _analyze_company_size_patterns(self, profiles: Dict[str, CompanyProfile]) -> Dict[str, Any]:
        """Analyze company size preferences and success rates."""
        size_counts = Counter([p.size_estimate for p in profiles.values() if p.size_estimate])
        size_potential = defaultdict(list)
        
        for profile in profiles.values():
            if profile.size_estimate:
                size_potential[profile.size_estimate].append(profile.business_potential)
        
        size_avg_potential = {}
        for size, potentials in size_potential.items():
            size_avg_potential[size] = sum(potentials) / len(potentials)
        
        return {
            'size_distribution': dict(size_counts),
            'size_avg_potential': size_avg_potential,
            'preferred_company_sizes': sorted(size_avg_potential.items(), key=lambda x: x[1], reverse=True)
        }
    
    def _analyze_successful_interaction_patterns(self, successful_profiles: List[CompanyProfile], emails: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze interaction patterns of successful companies."""
        return {
            'avg_interactions_before_success': sum(p.interaction_count for p in successful_profiles) / len(successful_profiles) if successful_profiles else 0,
            'avg_meetings_in_success': sum(p.meeting_count for p in successful_profiles) / len(successful_profiles) if successful_profiles else 0,
            'common_success_timeframes': '30-90 days',  # Heuristic
            'key_engagement_indicators': ['multiple_contacts', 'meeting_scheduled', 'technical_discussion']
        }
    
    def _group_emails_by_thread(self, emails: List[Dict[str, Any]]) -> List[List[Dict[str, Any]]]:
        """Group emails by conversation threads."""
        # Simplified grouping by subject similarity
        threads = []
        processed = set()
        
        for i, email in enumerate(emails):
            if i in processed:
                continue
            
            thread = [email]
            processed.add(i)
            subject = email.get('subject', '').lower()
            
            # Find related emails
            for j, other_email in enumerate(emails[i+1:], i+1):
                if j in processed:
                    continue
                
                other_subject = other_email.get('subject', '').lower()
                
                # Simple heuristic: similar subjects or Re:/Fwd: patterns
                if (subject in other_subject or other_subject in subject or
                    any(prefix in other_subject for prefix in ['re:', 'fwd:', 'fw:'])):
                    thread.append(other_email)
                    processed.add(j)
            
            if len(thread) > 0:
                threads.append(thread)
        
        return threads
    
    def _is_successful_followup(self, email: Dict[str, Any]) -> bool:
        """Heuristic to determine if a follow-up was successful."""
        content = (email.get('subject', '') + ' ' + email.get('snippet', '')).lower()
        
        success_indicators = [
            'yes', 'agreed', 'sounds good', 'let\'s proceed', 'next steps',
            'schedule', 'meeting', 'call', 'interested', 'proposal'
        ]
        
        return any(indicator in content for indicator in success_indicators)