"""
Integration Example: FounderShield with Existing Email System

This file demonstrates how to integrate FounderShield with the existing
EmailRiskChecker to provide comprehensive email risk analysis.
"""

import asyncio
import logging
from typing import Dict, Any, Optional

from processors.email_risk_checker import EmailRiskChecker
from modules.foundershield.service import FounderShieldService
from database import DatabaseManager

logger = logging.getLogger(__name__)


class EnhancedEmailRiskChecker(EmailRiskChecker):
    """
    Enhanced Email Risk Checker with FounderShield integration.
    
    Combines the basic email risk checks with FounderShield's deep
    domain and authentication analysis.
    """
    
    def __init__(self, db: Optional[DatabaseManager] = None):
        """Initialize enhanced risk checker."""
        super().__init__(db)
        self.foundershield = FounderShieldService()
    
    async def analyze_email_comprehensive(self, email_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Comprehensive email analysis combining basic and FounderShield checks.
        
        Args:
            email_data: Email data dict with sender, subject, body, headers, etc.
            
        Returns:
            Combined risk analysis with both basic and FounderShield results.
        """
        # Get basic risk analysis (existing functionality)
        basic_analysis = self.analyze_email(email_data)
        
        # Extract email components for FounderShield
        sender = email_data.get('sender', email_data.get('from', ''))
        raw_headers = email_data.get('raw_headers', email_data.get('headers', ''))
        body = email_data.get('body', '')
        
        # Run FounderShield deep analysis
        try:
            fs_report = await self.foundershield.generate_report(
                email_address=sender,
                raw_headers=raw_headers,
                raw_body=body
            )
        except Exception as e:
            logger.error(f"FounderShield analysis failed: {e}")
            fs_report = None
        
        # Combine results
        combined_analysis = self._combine_analyses(basic_analysis, fs_report)
        
        return combined_analysis
    
    def _combine_analyses(
        self,
        basic: Dict[str, Any],
        foundershield: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Combine basic and FounderShield analyses into unified report.
        
        Strategy:
        - Use FounderShield score as primary (more comprehensive)
        - Add basic checks as additional context
        - Merge all findings
        - Provide unified risk level and recommendation
        """
        if not foundershield:
            # FounderShield unavailable, use basic only
            return {
                'risk_score': basic['risk_score'],
                'risk_level': self._convert_risk_level(basic['risk_score']),
                'should_create_task': basic.get('should_create_task', False),
                'recommended_action': basic.get('recommended_action', 'Review manually'),
                'basic_checks': basic,
                'foundershield': None,
                'analysis_type': 'basic_only'
            }
        
        # Convert FounderShield score (0-100) to match basic scale (1-10)
        fs_score_normalized = 10 - (foundershield['score'] / 10)  # Higher FS score = lower risk
        
        # Weighted average (FounderShield 70%, basic 30%)
        combined_score = (fs_score_normalized * 0.7) + (basic['risk_score'] * 0.3)
        combined_score = max(1, min(10, combined_score))  # Clamp to 1-10
        
        # Merge findings
        all_findings = []
        
        # Add FounderShield findings with source
        for finding in foundershield.get('findings', []):
            all_findings.append({
                'source': 'foundershield',
                'id': finding['id'],
                'severity': finding['severity'],
                'details': finding['details']
            })
        
        # Add basic check flags with source
        for flag in basic.get('flags', []):
            all_findings.append({
                'source': 'basic_checks',
                'id': flag.upper().replace(' ', '_'),
                'severity': 'medium',
                'details': flag
            })
        
        # Determine final risk level
        risk_level = self._determine_combined_risk_level(
            combined_score,
            foundershield['risk_level'],
            basic.get('risk_level', 'moderate')
        )
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            risk_level,
            foundershield['score'],
            len(all_findings)
        )
        
        return {
            'combined_score': round(combined_score, 1),
            'risk_level': risk_level,
            'foundershield_score': foundershield['score'],
            'basic_score': basic['risk_score'],
            'should_create_task': basic.get('should_create_task', False),
            'recommended_action': recommendation,
            'findings': all_findings,
            'basic_checks': basic,
            'foundershield': foundershield,
            'analysis_type': 'comprehensive',
            'is_whitelisted': basic.get('is_whitelisted', False)
        }
    
    def _determine_combined_risk_level(
        self,
        combined_score: float,
        fs_risk: str,
        basic_risk: str
    ) -> str:
        """
        Determine final risk level from combined inputs.
        
        If either system flags as high_risk, use high_risk.
        Otherwise use the more conservative rating.
        """
        if fs_risk == 'high_risk' or basic_risk == 'critical':
            return 'high_risk'
        
        if combined_score >= 7:
            return 'high_risk'
        elif combined_score >= 4:
            return 'caution'
        else:
            return 'likely_ok'
    
    def _generate_recommendation(
        self,
        risk_level: str,
        fs_score: int,
        finding_count: int
    ) -> str:
        """Generate action recommendation based on risk."""
        if risk_level == 'high_risk':
            return '⚠️ DO NOT RESPOND - Likely scam/phishing. Delete and report.'
        elif risk_level == 'caution':
            return '⚡ REVIEW CAREFULLY - Verify sender through other channels before responding.'
        else:
            if finding_count > 0:
                return '✓ Likely safe, but review flagged items before taking action.'
            return '✅ Safe to proceed - No significant risk indicators found.'
    
    def _convert_risk_level(self, score: int) -> str:
        """Convert numeric score to risk level string."""
        if score >= 7:
            return 'high_risk'
        elif score >= 4:
            return 'caution'
        else:
            return 'likely_ok'


# Example usage functions

async def analyze_single_email_example():
    """Example: Analyze a single suspicious email."""
    
    checker = EnhancedEmailRiskChecker()
    
    # Suspicious investment scam email
    email_data = {
        'sender': 'john@globalinvestorsnetwork.com',
        'subject': 'Investment Opportunity - $5M Available',
        'body': '''
            Dear Founder,
            
            We have reviewed your company and are interested in investing $5M.
            To proceed, please pay $5,000 for our due diligence service.
            What is your budget for this project?
            
            Review testimonials: https://bit.ly/abc123
        ''',
        'raw_headers': 'Authentication-Results: spf=fail dkim=fail dmarc=none',
        'date': '2024-12-13T10:00:00',
        'labels': []
    }
    
    result = await checker.analyze_email_comprehensive(email_data)
    
    print("\n" + "="*80)
    print("EMAIL RISK ANALYSIS - SUSPICIOUS EMAIL")
    print("="*80)
    print(f"From: {email_data['sender']}")
    print(f"Subject: {email_data['subject']}")
    print(f"\nCombined Risk Score: {result['combined_score']}/10")
    print(f"Risk Level: {result['risk_level'].upper()}")
    print(f"FounderShield Score: {result['foundershield_score']}/100")
    print(f"\n{result['recommended_action']}")
    print(f"\nFindings ({len(result['findings'])} total):")
    for finding in result['findings']:
        print(f"  [{finding['source']}] {finding['severity'].upper()}: {finding['details']}")
    print("="*80 + "\n")


async def analyze_legitimate_email_example():
    """Example: Analyze a legitimate email."""
    
    checker = EnhancedEmailRiskChecker()
    
    # Legitimate email from established company
    email_data = {
        'sender': 'partner@sequoiacap.com',
        'subject': 'Follow up from YC Demo Day',
        'body': '''
            Hi there,
            
            Great meeting you at Demo Day yesterday. I'd love to schedule
            a call next week to discuss your company further.
            
            Best,
            Partner @ Sequoia Capital
        ''',
        'raw_headers': 'Authentication-Results: spf=pass dkim=pass dmarc=pass',
        'date': '2024-12-13T11:00:00',
        'labels': []
    }
    
    result = await checker.analyze_email_comprehensive(email_data)
    
    print("\n" + "="*80)
    print("EMAIL RISK ANALYSIS - LEGITIMATE EMAIL")
    print("="*80)
    print(f"From: {email_data['sender']}")
    print(f"Subject: {email_data['subject']}")
    print(f"\nCombined Risk Score: {result['combined_score']}/10")
    print(f"Risk Level: {result['risk_level'].upper()}")
    print(f"FounderShield Score: {result['foundershield_score']}/100")
    print(f"\n{result['recommended_action']}")
    if result['findings']:
        print(f"\nFindings ({len(result['findings'])} total):")
        for finding in result['findings']:
            print(f"  [{finding['source']}] {finding['severity'].upper()}: {finding['details']}")
    else:
        print("\n✓ No risk indicators found")
    print("="*80 + "\n")


async def batch_analyze_emails_example():
    """Example: Batch analyze multiple emails."""
    
    checker = EnhancedEmailRiskChecker()
    
    # Simulate inbox
    emails = [
        {
            'sender': 'scammer@newdomain.xyz',
            'subject': 'Urgent: Verify Account',
            'body': 'Your account will be suspended unless you verify now.',
            'raw_headers': 'Authentication-Results: spf=fail',
        },
        {
            'sender': 'team@stripe.com',
            'subject': 'Your payment succeeded',
            'body': 'Payment of $50 succeeded for your subscription.',
            'raw_headers': 'Authentication-Results: spf=pass dkim=pass dmarc=pass',
        },
        {
            'sender': 'investor@newventure.io',
            'subject': 'Investment interest',
            'body': 'We would like to discuss potential investment. See our Forbes article: https://forbescouncils.com/article/123',
            'raw_headers': 'Authentication-Results: spf=pass dkim=pass',
        }
    ]
    
    print("\n" + "="*80)
    print("BATCH EMAIL RISK ANALYSIS")
    print("="*80)
    
    high_risk_count = 0
    
    for i, email in enumerate(emails, 1):
        result = await checker.analyze_email_comprehensive(email)
        
        print(f"\n[{i}] {email['sender']}")
        print(f"    Subject: {email['subject']}")
        print(f"    Risk: {result['risk_level'].upper()} (Score: {result['combined_score']}/10)")
        print(f"    Action: {result['recommended_action']}")
        
        if result['risk_level'] == 'high_risk':
            high_risk_count += 1
    
    print(f"\n{'='*80}")
    print(f"Summary: {high_risk_count} high-risk email(s) detected out of {len(emails)} total")
    print("="*80 + "\n")


if __name__ == '__main__':
    # Run examples
    print("\nFounderShield Integration Examples\n")
    
    asyncio.run(analyze_single_email_example())
    asyncio.run(analyze_legitimate_email_example())
    asyncio.run(batch_analyze_emails_example())
