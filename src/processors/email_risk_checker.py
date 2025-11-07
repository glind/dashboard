#!/usr/bin/env python3
"""
Email Risk Checker
==================

Analyzes emails for security risks, spam indicators, and phishing attempts.
Provides a risk score (1-10) and recommendations for action.

Risk Scoring:
- 1-3: Safe/Trusted (legitimate business, known contacts)
- 4-6: Moderate Risk (promotional, marketing, unknown sender)
- 7-8: High Risk (suspicious patterns, potential phishing)
- 9-10: Critical Risk (clear scam/phishing indicators)
"""

import re
import logging
from typing import Dict, List, Any, Optional
from urllib.parse import urlparse
from datetime import datetime
import sys
from pathlib import Path

# Add parent directory to path for database imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from database import DatabaseManager

logger = logging.getLogger(__name__)


class EmailRiskChecker:
    """Analyzes emails for security risks and spam indicators."""
    
    def __init__(self, db: Optional[DatabaseManager] = None):
        # Database for safe senders whitelist
        self.db = db or DatabaseManager()
        
        # Known safe domains (major companies, services)
        self.trusted_domains = {
            'gmail.com', 'google.com', 'github.com', 'linkedin.com',
            'microsoft.com', 'apple.com', 'amazon.com', 'stripe.com',
            'paypal.com', 'slack.com', 'zoom.us', 'atlassian.com',
            'heroku.com', 'netlify.com', 'vercel.com', 'cloudflare.com'
        }
        
        # Common spam/scam indicators in subject lines
        self.spam_keywords = [
            'urgent action required', 'verify your account', 'suspended',
            'confirm your identity', 'unusual activity', 'account will be closed',
            'claim your prize', 'you\'ve won', 'free money', 'act now',
            'limited time', 'click here now', 're:', 'fwd:', 'invoice attached',
            'payment failed', 'update payment method', 'security alert'
        ]
        
        # High-risk sender patterns
        self.suspicious_sender_patterns = [
            r'noreply@.*\.xyz$',  # .xyz domains often used for scams
            r'admin@.*\.top$',     # .top domains suspicious
            r'support@.*\.loan$',  # .loan domains
            r'.*@.*\d{5,}',        # Random numbers in email
            r'.*@(?!.*\.com$|.*\.org$|.*\.net$|.*\.edu$|.*\.gov$)',  # Non-standard TLDs
        ]
        
        # Phishing URL patterns
        self.phishing_url_patterns = [
            r'bit\.ly',
            r'tinyurl',
            r'goo\.gl',
            r'ow\.ly',
            r'short\.io',
            r'\d+\.\d+\.\d+\.\d+',  # IP addresses
            r'http://.*\@',  # Username in URL (phishing technique)
        ]
        
    def analyze_email(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze an email for risk factors.
        
        Returns:
            dict with:
                - risk_score: int (1-10)
                - risk_level: str (safe, moderate, high, critical)
                - flags: list of detected issues
                - should_create_task: bool
                - recommended_action: str
                - details: dict of specific findings
                - is_whitelisted: bool
        """
        flags = []
        risk_score = 1  # Start with safe
        details = {}
        
        sender = email_data.get('sender', email_data.get('from', ''))
        subject = email_data.get('subject', '')
        body = email_data.get('body', '')
        labels = email_data.get('labels', [])
        
        # 0. CHECK SAFE SENDERS WHITELIST FIRST
        is_whitelisted = self.db.is_safe_sender(sender)
        if is_whitelisted:
            # Whitelisted senders get automatic low risk score
            return {
                'risk_score': 1,
                'risk_level': 'safe',
                'flags': ['Whitelisted sender - marked as safe by user'],
                'should_create_task': True,
                'recommended_action': 'none',
                'details': {'sender_domain': self._extract_domain(sender)},
                'is_whitelisted': True
            }
        
        # 1. Check sender domain
        domain_score, domain_flags = self._check_sender_domain(sender)
        risk_score += domain_score
        flags.extend(domain_flags)
        details['sender_domain'] = self._extract_domain(sender)
        
        # 2. Check subject line for spam keywords
        subject_score, subject_flags = self._check_subject(subject)
        risk_score += subject_score
        flags.extend(subject_flags)
        
        # 3. Check for suspicious URLs in body
        url_score, url_flags, urls = self._check_urls(body)
        risk_score += url_score
        flags.extend(url_flags)
        details['suspicious_urls'] = urls
        
        # 4. Check Gmail labels (SPAM, PROMOTIONS, etc.)
        label_score, label_flags = self._check_labels(labels)
        risk_score += label_score
        flags.extend(label_flags)
        
        # 5. Check sender/domain mismatch (spoofing/clickjacking)
        spoof_score, spoof_flags = self._check_spoofing(sender, body)
        risk_score += spoof_score
        flags.extend(spoof_flags)
        
        # 6. Check for urgency manipulation
        urgency_score, urgency_flags = self._check_urgency(subject, body)
        risk_score += urgency_score
        flags.extend(urgency_flags)
        
        # Cap at 10
        risk_score = min(risk_score, 10)
        
        # Determine risk level
        if risk_score <= 3:
            risk_level = 'safe'
            recommended_action = 'none'
        elif risk_score <= 6:
            risk_level = 'moderate'
            recommended_action = 'review'
        elif risk_score <= 8:
            risk_level = 'high'
            recommended_action = 'mark_spam'
        else:
            risk_level = 'critical'
            recommended_action = 'delete'
        
        # Decide if task should be created
        # Don't create tasks for risky emails, promotional content, or obvious spam
        should_create_task = self._should_create_task(
            risk_score, labels, subject, body, sender
        )
        
        return {
            'risk_score': risk_score,
            'risk_level': risk_level,
            'flags': flags,
            'should_create_task': should_create_task,
            'recommended_action': recommended_action,
            'details': details,
            'is_whitelisted': False  # Not whitelisted if we got this far
        }
    
    def _extract_domain(self, email: str) -> Optional[str]:
        """Extract domain from email address."""
        try:
            match = re.search(r'@([a-zA-Z0-9.-]+)', email)
            if match:
                return match.group(1).lower()
        except:
            pass
        return None
    
    def _check_sender_domain(self, sender: str) -> tuple[int, List[str]]:
        """Check if sender domain is trusted or suspicious."""
        score = 0
        flags = []
        
        domain = self._extract_domain(sender)
        if not domain:
            return 2, ['No valid sender domain']
        
        # Check if trusted
        if domain in self.trusted_domains:
            return 0, []  # Trusted, no additional risk
        
        # Check for suspicious patterns
        for pattern in self.suspicious_sender_patterns:
            if re.match(pattern, sender.lower()):
                score += 3
                flags.append(f'Suspicious sender pattern: {domain}')
                break
        
        # Check TLD
        tld = domain.split('.')[-1] if '.' in domain else ''
        suspicious_tlds = ['xyz', 'top', 'loan', 'click', 'download', 'review']
        if tld in suspicious_tlds:
            score += 2
            flags.append(f'Suspicious TLD: .{tld}')
        
        # Newly registered or uncommon domains get moderate risk
        if score == 0 and domain not in self.trusted_domains:
            score += 1  # Slight risk for unknown domains
        
        return score, flags
    
    def _check_subject(self, subject: str) -> tuple[int, List[str]]:
        """Check subject line for spam indicators."""
        score = 0
        flags = []
        subject_lower = subject.lower()
        
        # Check for spam keywords
        for keyword in self.spam_keywords:
            if keyword in subject_lower:
                score += 2
                flags.append(f'Spam keyword in subject: "{keyword}"')
        
        # Check for excessive punctuation
        if re.search(r'[!?]{2,}', subject):
            score += 1
            flags.append('Excessive punctuation in subject')
        
        # Check for all caps
        if subject.isupper() and len(subject) > 10:
            score += 1
            flags.append('Subject in all caps')
        
        return score, flags
    
    def _check_urls(self, body: str) -> tuple[int, List[str], List[str]]:
        """Check for suspicious URLs in email body."""
        score = 0
        flags = []
        suspicious_urls = []
        
        # Find all URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        urls = re.findall(url_pattern, body)
        
        for url in urls:
            for pattern in self.phishing_url_patterns:
                if re.search(pattern, url, re.IGNORECASE):
                    score += 2
                    flags.append(f'Suspicious URL pattern detected')
                    suspicious_urls.append(url)
                    break
        
        # Too many URLs is suspicious
        if len(urls) > 5:
            score += 1
            flags.append(f'Excessive URLs ({len(urls)} found)')
        
        return score, flags, suspicious_urls
    
    def _check_labels(self, labels: List[str]) -> tuple[int, List[str]]:
        """Check Gmail labels for spam/promotional indicators."""
        score = 0
        flags = []
        
        if 'SPAM' in labels:
            score += 5
            flags.append('Marked as SPAM by Gmail')
        
        if 'CATEGORY_PROMOTIONS' in labels:
            score += 2
            flags.append('Promotional email')
        
        if 'CATEGORY_SOCIAL' in labels:
            score += 1  # Social notifications often don't need tasks
        
        return score, flags
    
    def _check_spoofing(self, sender: str, body: str) -> tuple[int, List[str]]:
        """Check for potential domain spoofing and clickjacking."""
        score = 0
        flags = []
        
        # Check if body mentions a different company than sender domain
        sender_domain = self._extract_domain(sender)
        if not sender_domain:
            return 0, []
        
        # Extract all domains from URLs in the email body
        body_domains = self._extract_all_domains_from_body(body)
        
        # Check for sender domain vs content domain mismatches
        if body_domains:
            # Get the main sender domain (e.g., "google.com" from "noreply@google.com")
            sender_base = self._get_base_domain(sender_domain)
            
            # Check if ANY domain in the body doesn't match the sender
            mismatched_domains = []
            for domain in body_domains:
                domain_base = self._get_base_domain(domain)
                
                # Skip common legitimate domains (CDNs, tracking, unsubscribe services)
                if self._is_legitimate_third_party(domain):
                    continue
                
                # If domain doesn't match sender, it's suspicious
                if domain_base and sender_base and domain_base != sender_base:
                    # Check if it's not a subdomain of the same organization
                    if not (sender_base in domain_base or domain_base in sender_base):
                        mismatched_domains.append(domain)
            
            if mismatched_domains:
                score += 4
                flags.append(f'Domain mismatch: sender is {sender_domain} but links to {mismatched_domains[:3]}')
        
        # Common companies people might impersonate
        companies = ['paypal', 'amazon', 'apple', 'microsoft', 'google', 'bank', 'netflix', 'facebook']
        
        for company in companies:
            if company in body.lower() and company not in sender_domain.lower():
                score += 3
                flags.append(f'Possible spoofing: mentions {company} but sender is {sender_domain}')
                break
        
        return score, flags
    
    def _extract_all_domains_from_body(self, body: str) -> List[str]:
        """Extract all domains from URLs in email body."""
        domains = []
        
        # Pattern to match URLs
        url_pattern = r'https?://([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        matches = re.findall(url_pattern, body)
        
        for match in matches:
            domain = match.lower().strip()
            if domain and domain not in domains:
                domains.append(domain)
        
        return domains
    
    def _get_base_domain(self, domain: str) -> Optional[str]:
        """Get base domain from a full domain (e.g., 'google.com' from 'mail.google.com')."""
        if not domain:
            return None
        
        parts = domain.split('.')
        if len(parts) >= 2:
            # Return last two parts (base domain)
            return '.'.join(parts[-2:])
        return domain
    
    def _is_legitimate_third_party(self, domain: str) -> bool:
        """Check if domain is a known legitimate third-party service."""
        legitimate_services = [
            'unsubscribe', 'emaildelivery', 'sendgrid', 'mailchimp', 'constantcontact',
            'amazonses.com', 'mcsv.net', 'list-manage.com', 'campaign-archive.com',
            'images-amazon.com', 'ssl-images-amazon.com', 'cloudfront.net',
            'tracking', 'analytics', 'click', 'redirect'
        ]
        
        domain_lower = domain.lower()
        return any(service in domain_lower for service in legitimate_services)
    
    def _check_urgency(self, subject: str, body: str) -> tuple[int, List[str]]:
        """Check for urgency manipulation tactics."""
        score = 0
        flags = []
        
        urgency_keywords = [
            'urgent', 'immediate action', 'act now', 'expires today',
            'last chance', 'limited time', 'hurry', 'don\'t miss',
            'within 24 hours', 'account will be closed'
        ]
        
        text = f"{subject} {body}".lower()
        
        for keyword in urgency_keywords:
            if keyword in text:
                score += 1
                flags.append(f'Urgency manipulation: "{keyword}"')
                break  # Only count once
        
        return score, flags
    
    def _should_create_task(
        self, 
        risk_score: int, 
        labels: List[str], 
        subject: str,
        body: str,
        sender: str
    ) -> bool:
        """
        Determine if a task should be created for this email.
        
        Rules:
        - No tasks for high/critical risk emails (>6)
        - No tasks for promotional/social emails
        - No tasks for newsletters/automated notifications
        - Yes for emails asking questions or requiring response
        - Yes for emails with clear action items
        """
        # Don't create tasks for risky emails
        if risk_score > 6:
            return False
        
        # Don't create tasks for promotional/social
        if 'CATEGORY_PROMOTIONS' in labels or 'CATEGORY_SOCIAL' in labels:
            return False
        
        # Check for newsletter patterns
        unsubscribe_pattern = r'unsubscribe|opt.?out|manage.?preferences'
        if re.search(unsubscribe_pattern, body.lower()):
            return False
        
        # Check for automated notifications (no-reply addresses)
        if 'noreply' in sender.lower() or 'no-reply' in sender.lower():
            # Some no-reply emails are still actionable (e.g., payment confirmations)
            actionable_keywords = ['payment', 'invoice', 'receipt', 'order', 'shipment']
            if not any(kw in subject.lower() for kw in actionable_keywords):
                return False
        
        # Positive signals for task creation
        task_indicators = [
            r'\?',  # Questions
            r'please',
            r'could you',
            r'can you',
            r'need you to',
            r'action required',
            r'review',
            r'feedback',
            r'response needed',
            r'reply',
            r'let me know',
            r'thoughts\?',
            r'meeting',
            r'schedule',
            r'deadline',
            r'by \w+ \d+',  # Date mentions
        ]
        
        text = f"{subject} {body}".lower()
        for indicator in task_indicators:
            if re.search(indicator, text):
                return True
        
        # Default: don't create task for unknown/uncertain emails
        return False


def analyze_email_risk(email_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convenience function to analyze email risk.
    
    Args:
        email_data: Email dictionary with sender, subject, body, labels
        
    Returns:
        Risk analysis results
    """
    checker = EmailRiskChecker()
    return checker.analyze_email(email_data)


if __name__ == "__main__":
    # Test the risk checker
    test_emails = [
        {
            'sender': 'support@paypal.com',
            'subject': 'Your payment confirmation',
            'body': 'Thank you for your payment.',
            'labels': ['INBOX']
        },
        {
            'sender': 'admin@secure-login.xyz',
            'subject': 'URGENT: Verify your account NOW!!!',
            'body': 'Click here http://192.168.1.1/verify to verify your PayPal account.',
            'labels': ['INBOX']
        },
        {
            'sender': 'notifications@linkedin.com',
            'subject': 'You have 3 new messages',
            'body': 'Check your LinkedIn inbox.',
            'labels': ['CATEGORY_SOCIAL', 'INBOX']
        }
    ]
    
    checker = EmailRiskChecker()
    for i, email in enumerate(test_emails, 1):
        print(f"\n=== Test Email {i} ===")
        print(f"From: {email['sender']}")
        print(f"Subject: {email['subject']}")
        result = checker.analyze_email(email)
        print(f"Risk Score: {result['risk_score']}/10 ({result['risk_level']})")
        print(f"Should Create Task: {result['should_create_task']}")
        print(f"Recommended Action: {result['recommended_action']}")
        if result['flags']:
            print(f"Flags: {', '.join(result['flags'])}")
